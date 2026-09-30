# clap-music: optional sample quality and character model for daw

Installed on demand with `daw library install clap-music`. It is never part of daw's core
install. The pack is LAION's CC0 music CLAP checkpoint, cut down to what daw runs:

| File | What |
|---|---|
| `clap-music-audio.onnx` | The audio tower (HTSAT-base + projection) as ONNX, opset 17. Input `waveform` [1, 480000]: 10 s of mono audio at 48 kHz, repeat-padded and int16-quantised as laion_clap does. Output `embedding` [1, 512], L2-normalised. It runs in daw on `tract`, in pure Rust. |
| `clap-music-prompts.json` | The fixed prompt set, with text embeddings precomputed from the checkpoint's text tower. Per axis, the positive and negative phrasings and a `center`/`scale` that map the contrast to 0..1. |
| `provenance.json` | The upstream checkpoint (URL, Hugging Face commit, sha256), tool versions, and how the ONNX output compared with PyTorch on the test clips. |
| `LICENSE`, `NOTICES.md` | CC0 1.0 and credits. |
| `SHA256SUMS` | The hash of every file. daw pins these in `content/models/clap-music/model.json`. |

## Build

```sh
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
python3 build.py out/ --cache .cache
```

`build.py` does five things:

1. It downloads the checkpoint from `lukewys/laion_clap` at a pinned commit and checks its
   sha256.
2. It exports the audio tower. The bicubic time resize is baked into a constant matrix, so the
   graph has no `Resize` op. The graph is then simplified with onnxsim.
3. It checks the ONNX graph against laion_clap's own `get_audio_embedding` on five
   deterministic clips. The limits are a max |diff| of 1e-4 and a cosine of at least 0.9999;
   if either fails, the build fails.
4. It computes the prompt embeddings.
5. It writes the provenance file and `SHA256SUMS`.

The workflow [`build-clap-music`](../../.github/workflows/build-clap-music.yml) runs the same
steps on GitHub's runners. On a pull request it only builds. When run by hand (or on a
pushed `models-clap-music-*` tag), it also publishes the release.

## Prompt axes

`prompts.json` holds the prompts; daw reads the version with the embeddings added.

| Axis | 1 means | 0 means |
|---|---|---|
| `quality` | sounds professionally recorded ("professional studio one-shot") | amateur or cheaply synthesized |
| `wet` | reverberant | dry |
| `bright` | bright | dark |
| `punchy` | hard attack | soft attack |
| `distorted` | saturated or overdriven | clean |

Other candidate axes are dropped when they fail validation. daw's
`docs/research/clap-model-pack.md` has the validation results (per-class AUC on CC0
material) and how `center` and `scale` were set.
