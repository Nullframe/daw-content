# daw-content

Downloadable third-party content for [`daw`](https://nullframe.ai). This repo contains no daw source code.

daw fetches these files on first use (`daw library-sync`) and checks each one against a pinned sha256. They are published as **GitHub release assets**. The repo itself holds this README, the licence notices and the scripts that build the assets.

| Asset | Upstream | Licence |
|---|---|---|
| Vitalium, Dexed, OB-Xf plugin builds (+ matching source archives) | see `NOTICES.md` | GPL-3.0-or-later |
| OB-Xf presets (487, from 13 named authors) | OB-Xf | CC0-1.0 |
| Spleeter 4-stem model, converted for daw's runtime | deezer/spleeter | MIT |
| Basic Pitch model | spotify/basic-pitch | Apache-2.0 |
| Real rooms IR pack (34 recorded impulse responses) | OpenAIR (York), Aachen AIR, Detmold SRIR, BBC Maida Vale; see `packs/real-rooms` and each release's `NOTICES.md` | CC-BY-4.0, CC-BY-3.0, MIT |

Each release lists its exact upstream versions, conversion scripts and checksums. The source for every GPL binary is attached to the same release as the binary.

## Instruments pack

`daw pack install instruments` installs Vitalium, Dexed and OB-Xf from an `instruments-<date>` release. The workflow [`build-instruments`](.github/workflows/build-instruments.yml) builds them from their official upstream sources at the commits pinned in [`packs/instruments/pack.json`](packs/instruments/pack.json). It builds on GitHub's runners for Linux x86_64 and aarch64 (Ubuntu 22.04) and macOS (a universal arm64 + x86_64 build on `macos-14`). These are unmodified upstream builds, except that Dexed's built-in DX7 banks are replaced by its init voice before building. The only presets are OB-Xf's CC0 patches. `NOTICES.md` has the details.

- A pull request that touches `packs/instruments/` builds every platform and keeps the results as workflow artifacts. It does not publish a release.
- To publish, run the workflow by hand (Actions → build-instruments → Run workflow) or push a tag `instruments-<date>`. The release is `instruments-<UTC date>` unless you give a tag. Rerunning for an existing tag replaces its assets, so only do that before daw pins the release's sha256 values.
- Then copy the release's `artifacts.json` (file, sha256 and bytes per platform) and its URL into `packs/instruments/pack.json` in the daw repository. That manifest is compiled into daw, which uses it to verify downloads.

`packs/instruments/` is a copy of the same folder in the daw repository (`build.sh`, the `recipes/`, `pack.json`). Change both together. Bump `version` in `pack.json` when a pin, recipe or preset rule changes, because published archives are never replaced under the same name.

## Real rooms IR pack

`daw library install real-rooms` installs recorded impulse responses of real spaces from a `real-rooms-<date>` release. Those are built by [`build-real-rooms`](.github/workflows/build-real-rooms.yml) from the upstream sources in [`packs/real-rooms/recipes.json`](packs/real-rooms/recipes.json). No audio is committed. [`packs/real-rooms/README.md`](packs/real-rooms/README.md) has the details.
