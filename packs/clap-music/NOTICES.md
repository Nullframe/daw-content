# clap-music model pack: notices

**Model.** LAION-CLAP, checkpoint `music_audioset_epoch_15_esc_90.14.pt` (HTSAT-base audio
encoder + RoBERTa text encoder, trained by LAION on music, AudioSet and LAION-Audio-630K).
Downloaded from the Hugging Face repository `lukewys/laion_clap` at commit
`b3708341862f581175dba5c356a4ebf74a9b6651` (sha256
`fae3e9c087f2909c28a09dc31c8dfcdacbc42ba44c70e972b58c1bd1caf6dedd`). The model card's licence
is `cc0-1.0`. The model code (`laion_clap` 1.1.7, https://github.com/LAION-AI/CLAP) is also
CC0 1.0 Universal; the full text is in `LICENSE`.

Paper: Yusong Wu, Ke Chen, Tianyu Zhang, Yuchen Hui, Taylor Berg-Kirkpatrick and Shlomo
Dubnov, "Large-scale Contrastive Language-Audio Pretraining with Feature Fusion and
Keyword-to-Caption Augmentation", ICASSP 2023. CC0 asks for nothing; we credit LAION anyway.

**What this pack contains.**

- `clap-music-audio.onnx`: only the audio tower (HTSAT-base and the audio projection, output
  L2-normalised), exported with `build.py` and checked against the PyTorch model.
- `clap-music-prompts.json`: text embeddings of a fixed set of prompts, computed with the
  checkpoint's own text tower. The text tower itself is not included. Its tokenizer is
  `roberta-base`'s (MIT), which was used only to compute these vectors and is not
  redistributed.
- `provenance.json`: the upstream URL, commit and hash, the tool versions and the
  verification results.

**Use in daw.** The pack is optional: `daw library install clap-music`. daw uses it only to
score samples for quality and character (wet/dry, bright/dark, punchy/soft, distorted/clean).
It is not used to listen to mixes or as the main search.
