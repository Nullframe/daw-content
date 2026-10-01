# daw-content

Downloadable third-party content for [`daw`](https://nullframe.ai). This repo contains no daw source code.

daw fetches these files on first use (`daw library-sync`) and checks each one against a pinned sha256. They are published as **GitHub release assets**. The repo itself holds this README, the licence notices and the scripts that build the assets.

| Asset | Upstream | Licence |
|---|---|---|
| Vitalium, Dexed, OB-Xf plugin builds (+ matching source archives) | see `NOTICES.md` | GPL-3.0-or-later |
| OB-Xf presets (487, from 13 named authors) | OB-Xf | CC0-1.0 |
| Spleeter 4-stem model, converted for daw's runtime | deezer/spleeter | MIT |
| Basic Pitch model | spotify/basic-pitch | Apache-2.0 |
| CLAP music model pack (optional; audio tower as ONNX + prompt embeddings), see `packs/clap-music` | LAION-AI/CLAP `music_audioset_epoch_15_esc_90.14` | CC0-1.0 |
| Recorded drums (CC0): 264 drum and percussion one-shots and three round-robin kits, see `packs/drums-recorded` | Versilian VCSL; Karoryfer Big Rusty Drums and Swirly Drums | CC0-1.0 |
| Orchestral (CC0): 1,624 FLAC samples (strings, brass, woodwinds, harp, mallets; 56 articulations) for daw's sampler@1, see `packs/orchestral-cc0` | Versilian VSCO 2 CE and VCSL | CC0-1.0 |
| Synthesis benchmark reference sounds (53 one-shots and textures, each with a text description), see `packs/synth-bench` | daw-content recorded drums, VCSL, VSCO 2 CE, Sonic Pi samples, Kenney, FSD50K (CC0 clips) | CC0-1.0 |
| Real rooms IR pack (34 recorded impulse responses) | OpenAIR (York), Aachen AIR, Detmold SRIR, BBC Maida Vale; see `packs/real-rooms` and each release's `NOTICES.md` | CC-BY-4.0, CC-BY-3.0, MIT |

Each release lists its exact upstream versions, conversion scripts and checksums. The source for every GPL binary is attached to the same release as the binary.

## Instruments pack

`daw pack install instruments` installs Vitalium, Dexed and OB-Xf from an `instruments-<date>` release. The workflow [`build-instruments`](.github/workflows/build-instruments.yml) builds them from their official upstream sources at the commits pinned in [`packs/instruments/pack.json`](packs/instruments/pack.json). It builds on GitHub's runners for Linux x86_64 and aarch64 (Ubuntu 22.04) and macOS (a universal arm64 + x86_64 build on `macos-14`). These are unmodified upstream builds, except that Dexed's built-in DX7 banks are replaced by its init voice before building, and OB-Xf carries a small determinism patch (seeded RNGs; `packs/instruments/patches/obxf/`). The only presets are OB-Xf's CC0 patches. `NOTICES.md` has the details.

- A pull request that touches `packs/instruments/` builds every platform and keeps the results as workflow artifacts. It does not publish a release.
- To publish, run the workflow by hand (Actions → build-instruments → Run workflow) or push a tag `instruments-<date>`. The release is `instruments-<UTC date>` unless you give a tag. Rerunning for an existing tag replaces its assets, so only do that before daw pins the release's sha256 values.
- Then copy the release's `artifacts.json` (file, sha256 and bytes per platform) and its URL into `packs/instruments/pack.json` in the daw repository. That manifest is compiled into daw, which uses it to verify downloads.

`packs/instruments/` is a copy of the same folder in the daw repository (`build.sh`, the `recipes/`, `pack.json`). Change both together. Bump `version` in `pack.json` when a pin, recipe or preset rule changes, because published archives are never replaced under the same name.

## Real rooms IR pack

`daw library install real-rooms` installs recorded impulse responses of real spaces from a `real-rooms-<date>` release. Those are built by [`build-real-rooms`](.github/workflows/build-real-rooms.yml) from the upstream sources in [`packs/real-rooms/recipes.json`](packs/real-rooms/recipes.json). No audio is committed. [`packs/real-rooms/README.md`](packs/real-rooms/README.md) has the details.

## CLAP music model pack

`daw library install clap-music` installs an optional sample quality and character model from a `models-clap-music-<date>` release. The workflow [`build-clap-music`](.github/workflows/build-clap-music.yml) builds it from LAION's CC0 checkpoint at a pinned commit. It exports only the audio tower to ONNX, checks it against PyTorch, and precomputes the text embeddings of a fixed prompt set. No weights are committed. [`packs/clap-music/README.md`](packs/clap-music/README.md) has the details.

## Recorded drums (CC0)

`voyager-daw library install drums-recorded-cc0` installs recorded drum and percussion one-shots and three round-robin kits (`kit/trailer-recorded@1`, `kit/orchestral-recorded@1`, `kit/acoustic-recorded@1`) from a `drums-recorded-cc0-<date>` release. The workflow [`build-drums-recorded`](.github/workflows/build-drums-recorded.yml) builds them from CC0 recordings pinned in [`packs/drums-recorded/recipes.json`](packs/drums-recorded/recipes.json). No audio is committed. [`packs/drums-recorded/README.md`](packs/drums-recorded/README.md) has the details.

## Orchestral (CC0)

`voyager-daw library install orchestral-cc0` installs a recorded orchestra (`instrument/orchestral-cc0@1`, played by daw's `sampler@1/*-cc0` presets) from an `orchestral-cc0-<date>` release. The workflow [`build-orchestral`](.github/workflows/build-orchestral.yml) builds it from VSCO 2 CE and VCSL at the commits pinned in [`packs/orchestral-cc0/recipes.json`](packs/orchestral-cc0/recipes.json) and checks the archive against the sha256 daw pins. No audio is committed. [`packs/orchestral-cc0/README.md`](packs/orchestral-cc0/README.md) has the details.

## Listening reels

Short renders by daw (of CC0 material and daw's own synthesis), published so they can be heard without building daw, as assets of the release they belong to (for example the drum comparison reel on `drums-recorded-cc0-2026-09-30`). They are rendered by daw on a developer's machine and uploaded by [`publish-reel`](.github/workflows/publish-reel.yml), a manual workflow that takes the file base64-encoded in parts (a dispatch's inputs are capped at 64 KB), joins them and checks the sha256. No audio is committed.

## Synthesis benchmark (CC0)

daw's synthesis benchmark (`daw-bench synth`) fetches its 53 reference sounds from a `synth-bench-<date>` release. The workflow [`build-synth-bench`](.github/workflows/build-synth-bench.yml) builds them from CC0 sources pinned in [`packs/synth-bench/recipes.json`](packs/synth-bench/recipes.json): daw-content's recorded drums, VCSL, VSCO 2 CE, the Sonic Pi samples, Kenney and FSD50K's CC0 clips. No audio is committed. [`packs/synth-bench/README.md`](packs/synth-bench/README.md) has the details.
