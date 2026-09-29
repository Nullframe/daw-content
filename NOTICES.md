# Notices

Filled in per release: the upstream project, exact version/commit, licence text, and the attribution each asset requires.

## Instruments pack (`instruments-*` releases)

Built by [`.github/workflows/build-instruments.yml`](.github/workflows/build-instruments.yml) with the scripts in [`packs/instruments/`](packs/instruments/), from each project's official upstream repository at the commit pinned in [`packs/instruments/pack.json`](packs/instruments/pack.json). They are separate VST3 plugins. daw runs them in its out-of-process plugin worker and does not link them.

| Instrument | Upstream | Commit | Licence |
|---|---|---|---|
| Vitalium | [DISTRHO/DISTRHO-Ports](https://github.com/DISTRHO/DISTRHO-Ports), `ports-juce6.0/vitalium` (DISTRHO's renamed build of [Vital](https://github.com/mtytel/vital)) | `d3b62da2e83c69b0866af5bb2e29ac78dc8014cf` | GPL-3.0-or-later |
| Dexed 1.0.1 | [asb2m10/dexed](https://github.com/asb2m10/dexed) | `bce5deee7c41bf5515b806d0b7de8b5c0bb49467` (`v1.0.1`) | GPL-3.0-or-later (its `msfa` FM engine is Apache-2.0) |
| OB-Xf 1.0.3 | [surge-synthesizer/OB-Xf](https://github.com/surge-synthesizer/OB-Xf) | `1223e6f7b209b9affa91331c26f39d4095a4088e` (`v1.0.3`) | GPL-3.0-or-later |

Copyright notices and full licence texts are in each archive's `licenses/<id>/`, copied from the upstream tree and its submodules.

**Unmodified upstream builds**, with one exception. Dexed compiles its built-in DX7 cartridges (`assets/builtin_pgm.zip`: `Dexed_01` and `SynprezFM_01`–`32`) into the plugin. Those voices have no known per-voice authors and no stated redistribution terms. So before building, `packs/instruments/recipes/dexed.sh` replaces that zip with one holding only `Dexed_01.syx`: 32 copies of Dexed's own INIT VOICE (its `init_voice` table, from its GPL source), packed as a DX7 bulk dump. No code is changed and no patches are applied (`packs/instruments/patches/` is empty).

One packaging step on macOS: DISTRHO-Ports' meson build leaves Vitalium's library as `vitalium.vst3/Contents/MacOS/vitalium.dylib` with no `Info.plist`, which VST3 hosts can't load. `recipes/vitalium.sh` renames it to `vitalium`, adds a minimal `Info.plist` and ad-hoc signs the bundle. The binary itself is as built.

"Vital" is a trademark of Matt Tytel. The pack ships DISTRHO's community build, which is already renamed Vitalium and has its own plugin ids.

**Presets.** Only OB-Xf's factory patches that declare a CC0 licence in their own metadata ship: 487 of the 488 `.fxp` files in `assets/installer/Surge Synth Team/OB-Xf/Patches` at v1.0.3. The one with no author or licence, `Bells/Singing Noise.fxp`, is left out of the pack and of the source archive (no binary uses it). The authors, as each patch declares them: Saif Sameer, Aleksey Zhehanov, Black Sided Sun, Ocean Swift, Jacky Ligon, 0.5°, Fedir Tkachov, Artur Rembe, Vincent Zauhar, Pebblestream, John Valentine, Den Rize and EvilDragon. No Dexed or Vitalium presets ship: Vital's factory presets are not free, and Dexed's built-in banks are removed as described above.

**Each release contains:**

- `daw-instruments-<version>-<platform>.tar.gz` for `linux-x86_64`, `linux-aarch64` and `macos-universal` (arm64 + x86_64, macOS 11+). Each holds:
  - the three `.vst3` bundles;
  - `licenses/<id>/`: every `LICENSE*` and `COPYING*` file in the upstream tree and its submodules, plus `UPSTREAM.txt` (repository, commit, preset provenance);
  - `NOTICES.md` and `SOURCE-OFFER.md`;
  - the build scripts (`source/`);
  - the CC0 OB-Xf patches (`patch-files/obxf/`). daw converts and checks them when it installs the pack.
- `daw-instruments-<version>-src.tar.gz`: the **complete corresponding source** of every binary in the release. It holds each upstream tree at its pinned commit with its submodules (Dexed's cartridge zip swapped as described), any sources the builds fetched themselves, and the build scripts. Before publishing, the workflow checks that every platform was built from byte-identical sources.
- A `.sha256` file per archive, `SHA256SUMS`, `artifacts.json` (file, sha256 and size per platform, for daw's manifest) and `NOTICES.md`.

The macOS bundles are ad-hoc signed by the linker. They are not signed with a Developer ID or notarized. `daw pack install` checks each archive's sha256 against daw's pinned manifest, then removes the quarantine attribute from the files it unpacked.

**Written offer.** For three years from each release, we will provide the same source on a physical medium for no more than the cost of performing the distribution. To ask, open an issue in this repository.
