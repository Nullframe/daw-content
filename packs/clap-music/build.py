#!/usr/bin/env python3
"""Build the clap-music model pack for daw from LAION's CC0 music CLAP checkpoint.

    python3 build.py OUT_DIR [--cache DIR]

1. Downloads music_audioset_epoch_15_esc_90.14.pt from lukewys/laion_clap at the pinned commit
   and checks its sha256.
2. Exports ONLY the audio tower (HTSAT-base + the audio projection, L2-normalised) to ONNX:
   input `waveform` [1, 480000] (10 s, mono, 48 kHz), output `embedding` [1, 512]. The
   log-mel front end (torchlibrosa STFT + mel) is inside the graph; the bicubic time resize
   (1001 -> 1024 frames) is baked as a constant matrix so the graph has no Resize op. The
   graph is simplified with onnxsim (fixed shapes) for tract.
3. Verifies the ONNX graph against the PyTorch model (laion_clap's own get_audio_embedding)
   on deterministic test clips: max |diff| <= 1e-4 and cosine >= 0.9999, else fails.
4. Precomputes the text embeddings of the fixed prompt set in prompts.json with the
   checkpoint's own text tower, into clap-music-prompts.json.
5. Writes provenance.json, LICENSE (CC0 1.0), NOTICES.md and SHA256SUMS.
"""
import argparse, hashlib, json, os, platform, sys, urllib.request
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
CKPT = "music_audioset_epoch_15_esc_90.14.pt"
HF_REPO = "lukewys/laion_clap"
HF_COMMIT = "b3708341862f581175dba5c356a4ebf74a9b6651"
CKPT_SHA256 = "fae3e9c087f2909c28a09dc31c8dfcdacbc42ba44c70e972b58c1bd1caf6dedd"
CKPT_URL = f"https://huggingface.co/{HF_REPO}/resolve/{HF_COMMIT}/{CKPT}"
ONNX_NAME = "clap-music-audio.onnx"
PROMPTS_NAME = "clap-music-prompts.json"
SR, N = 48000, 480000


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch_ckpt(cache):
    os.makedirs(cache, exist_ok=True)
    p = os.path.join(cache, CKPT)
    if not (os.path.exists(p) and sha256(p) == CKPT_SHA256):
        print("downloading", CKPT_URL, flush=True)
        urllib.request.urlretrieve(CKPT_URL, p + ".part")
        os.replace(p + ".part", p)
    got = sha256(p)
    if got != CKPT_SHA256:
        sys.exit(f"{CKPT}: sha256 {got}, expected {CKPT_SHA256}")
    return p


def load_clap(path):
    import laion_clap
    m = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-base")
    ck = torch.load(path, map_location="cpu", weights_only=False)
    sd = ck["state_dict"] if "state_dict" in ck else ck
    sd = {k[7:] if k.startswith("module.") else k: v for k, v in sd.items()}
    r = m.model.load_state_dict(sd, strict=False)
    # position_ids is a constant buffer newer transformers no longer store; nothing else may differ.
    if r.missing_keys or set(r.unexpected_keys) - {"text_branch.embeddings.position_ids"}:
        sys.exit(f"checkpoint mismatch: missing {r.missing_keys}, unexpected {r.unexpected_keys}")
    m.eval()
    return m


class AudioTower(nn.Module):
    """waveform [B, 480000] -> L2-normalised 512-d embedding, exactly as
    CLAP.get_audio_embedding for a non-fusion model."""

    def __init__(self, clap):
        super().__init__()
        self.h = clap.model.audio_branch
        self.proj = clap.model.audio_projection
        frames = N // clap.model_cfg["audio_cfg"]["hop_size"] + 1  # 1001 STFT frames (centred)
        target = int(self.h.spec_size * self.h.freq_ratio)
        eye = torch.eye(frames).reshape(1, 1, frames, frames)
        R = F.interpolate(eye, (target, frames), mode="bicubic", align_corners=True)[0, 0]
        self.register_buffer("resize", R.contiguous())

    def forward(self, wav):
        h = self.h
        x = h.spectrogram_extractor(wav)
        x = h.logmel_extractor(x)
        x = x.transpose(1, 3)
        x = h.bn0(x)
        x = x.transpose(1, 3)
        x = torch.matmul(self.resize, x)
        B, C, T, Fq = x.shape
        x = x.permute(0, 1, 3, 2).reshape(B, C, Fq, h.freq_ratio, T // h.freq_ratio)
        x = x.permute(0, 1, 3, 2, 4).reshape(B, C, Fq * h.freq_ratio, T // h.freq_ratio)
        e = h.forward_features(x)["embedding"]
        return F.normalize(self.proj(e), dim=-1)


def test_clips():
    """Deterministic 10 s clips: noise, a decaying drum-like hit (repeat-padded like daw
    does), a chirp, a chord, near-silence."""
    rng = np.random.default_rng(20260930)
    t = np.arange(N) / SR
    clips = [(rng.standard_normal(N) * 0.1)]
    hit_t = np.arange(int(0.4 * SR)) / SR
    hit = np.sin(2 * np.pi * (50 + 120 * np.exp(-hit_t * 30)) * hit_t) * np.exp(-hit_t * 9)
    hit = hit + 0.3 * rng.standard_normal(hit.size) * np.exp(-hit_t * 60)
    clips.append(np.tile(hit, N // hit.size + 1)[:N] * 0.8)
    clips.append(0.5 * np.sin(2 * np.pi * (100 * t + 400 * t * t)))
    clips.append(0.2 * sum(np.sin(2 * np.pi * f * t) for f in (220, 277.2, 329.6)) * np.exp(-t * 0.3))
    clips.append(1e-4 * rng.standard_normal(N))
    out = []
    for c in clips:
        c = np.clip(c, -1, 1)
        c = (c * 32767).astype(np.int16).astype(np.float32) / 32767  # laion_clap's int16 quantise
        out.append(c.astype(np.float32))
    return np.stack(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--cache", default=os.path.join(HERE, ".cache"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    torch.manual_seed(0)
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    ckpt = fetch_ckpt(a.cache)
    clap = load_clap(ckpt)
    tower = AudioTower(clap).eval()

    # Export.
    import onnx, onnxsim, onnxruntime as ort
    raw = os.path.join(a.cache, "raw.onnx")
    dummy = torch.zeros(1, N)
    torch.onnx.export(tower, (dummy,), raw, input_names=["waveform"], output_names=["embedding"],
                      opset_version=17, dynamo=False, do_constant_folding=True)
    model, ok = onnxsim.simplify(onnx.load(raw))
    if not ok:
        sys.exit("onnxsim could not validate the simplified graph")
    model.doc_string = ("LAION-CLAP music_audioset_epoch_15_esc_90.14 audio tower (HTSAT-base + projection), "
                        "CC0-1.0. Input waveform [1,480000] mono 48 kHz; output L2-normalised embedding [1,512].")
    onnx_path = os.path.join(a.out, ONNX_NAME)
    onnx.save(model, onnx_path)
    os.remove(raw)

    # Verify against laion_clap's own path.
    clips = test_clips()
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    checks = []
    for i, c in enumerate(clips):
        with torch.no_grad():
            ref = clap.model.get_audio_embedding([{"waveform": torch.from_numpy(c)}]).numpy()[0]
        got = sess.run(None, {"waveform": c[None]})[0][0]
        d = float(np.abs(got - ref).max())
        cos = float(np.dot(got, ref) / (np.linalg.norm(got) * np.linalg.norm(ref)))
        checks.append({"clip": i, "max_abs_diff": d, "cosine": cos})
        print(f"clip {i}: max|diff| {d:.2e} cos {cos:.7f}", flush=True)
        if d > 1e-4 or cos < 0.9999:
            sys.exit(f"ONNX output does not match PyTorch on test clip {i}")
    np.save(os.path.join(a.cache, "test_clips.npy"), clips)

    # Prompt embeddings.
    spec = json.load(open(os.path.join(HERE, "prompts.json")))
    texts = sorted({t for ax in spec["axes"] for t in ax["pos"] + ax["neg"]})
    with torch.no_grad():
        emb = clap.get_text_embedding(texts, use_tensor=True).numpy().astype(np.float64)
    table = {t: [round(float(x), 7) for x in emb[i]] for i, t in enumerate(texts)}
    prompts = dict(spec)
    prompts["model"] = "model/clap-music@1"
    prompts["dim"] = int(emb.shape[1])
    prompts["text_embeddings"] = table
    with open(os.path.join(a.out, PROMPTS_NAME), "w") as f:
        json.dump(prompts, f, indent=1, sort_keys=False)
        f.write("\n")

    import transformers
    prov = {
        "pack": "clap-music",
        "model_id": "model/clap-music@1",
        "files": {
            ONNX_NAME: "audio tower of the checkpoint (HTSAT-base + audio projection), ONNX opset 17",
            PROMPTS_NAME: "text embeddings of the fixed prompt set, from the checkpoint's text tower",
        },
        "upstream": {
            "checkpoint": CKPT,
            "url": CKPT_URL,
            "sha256": CKPT_SHA256,
            "huggingface_repo": HF_REPO,
            "huggingface_commit": HF_COMMIT,
            "model_card_license": "cc0-1.0",
            "code": "https://github.com/LAION-AI/CLAP (LICENSE: CC0 1.0 Universal), model code from pip laion_clap 1.1.7",
            "paper": "Wu, Chen, Zhang, Hui, Berg-Kirkpatrick, Dubnov: Large-scale Contrastive Language-Audio Pretraining with Feature Fusion and Keyword-to-Caption Augmentation, ICASSP 2023",
            "authors": "LAION (Yusong Wu, Ke Chen, Tianyu Zhang, Yuchen Hui, Marianna Nezhurina, Taylor Berg-Kirkpatrick, Shlomo Dubnov)",
        },
        "license": "CC0-1.0",
        "conversion": {
            "script": "packs/clap-music/build.py in Nullframe/daw-content",
            "torch": torch.__version__, "onnx": onnx.__version__, "onnxsim": onnxsim.__version__,
            "onnxruntime": ort.__version__, "transformers": transformers.__version__,
            "python": platform.python_version(), "opset": 17,
            "text_tokenizer": "roberta-base tokenizer (MIT), used only to compute the prompt embeddings; not shipped",
        },
        "verification": {"tolerance": {"max_abs_diff": 1e-4, "cosine": 0.9999}, "clips": checks},
        "input": {"sample_rate": SR, "samples": N, "channels": 1,
                  "preparation": "mono, 48 kHz; shorter clips repeated then zero-padded to 10 s (laion_clap 'repeatpad'); longer clips cut to the first 10 s; int16-quantised (x*32767 -> int16 -> /32767)"},
    }
    json.dump(prov, open(os.path.join(a.out, "provenance.json"), "w"), indent=1)
    import shutil
    for f in ("LICENSE", "NOTICES.md"):
        shutil.copy(os.path.join(HERE, f), os.path.join(a.out, f))
    names = sorted(n for n in os.listdir(a.out) if n != "SHA256SUMS")
    with open(os.path.join(a.out, "SHA256SUMS"), "w") as f:
        for n in names:
            f.write(f"{sha256(os.path.join(a.out, n))}  {n}\n")
    print(open(os.path.join(a.out, "SHA256SUMS")).read())


if __name__ == "__main__":
    main()
