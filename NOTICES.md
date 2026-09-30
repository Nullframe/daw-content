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

**Unmodified upstream builds**, with two exceptions. First, Dexed compiles its built-in DX7 cartridges (`assets/builtin_pgm.zip`: `Dexed_01` and `SynprezFM_01`–`32`) into the plugin. Those voices have no known per-voice authors and no stated redistribution terms. So before building, `packs/instruments/recipes/dexed.sh` replaces that zip with one holding only `Dexed_01.syx`: 32 copies of Dexed's own INIT VOICE (its `init_voice` table, from its GPL source), packed as a DX7 bulk dump. Second, from pack 2026.09.1 (`instruments-2026.09.1`), OB-Xf is patched for determinism: [`packs/instruments/patches/obxf/01-seed-rng-from-rand.patch`](packs/instruments/patches/obxf/01-seed-rng-from-rand.patch) seeds its per-voice "slop" and LFO sample-and-hold RNGs from `std::rand()` instead of `juce::Random`'s default seed, which mixes in an object address and the clock. Without it, two fresh processes render the same notes differently. The amount and character of the variation are unchanged. No other code is changed; the patch is in each archive's `source/` and in the source archive.

One packaging step on macOS: DISTRHO-Ports' meson build leaves Vitalium's library as `vitalium.vst3/Contents/MacOS/vitalium.dylib` with no `Info.plist`, which VST3 hosts can't load. `recipes/vitalium.sh` renames it to `vitalium`, adds a minimal `Info.plist` and ad-hoc signs the bundle. The compiled code is unchanged.

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

## Real rooms IR pack (`real-rooms-*` releases)

34 recorded impulse responses, modified by conditioning: DC removal, W channel of B-format, 48 kHz, trim, noise-floor tail cut, -1 dBFS peak. Built by [`.github/workflows/build-real-rooms.yml`](.github/workflows/build-real-rooms.yml) from the sources in [`packs/real-rooms/recipes.json`](packs/real-rooms/recipes.json). Each release's `NOTICES.md` has the full per-file attribution, the licence evidence and the MIT text. Each release's `provenance.json` has the upstream URL, licence and sha256 of every source file.

| Collection | Files | Licence | Attribution |
|---|---|---|---|
| [OpenAIR](https://www.openair.hosted.york.ac.uk/), AudioLab, University of York | 25 | CC-BY-4.0 | "OpenAIR, AudioLab, University of York", plus the space name |
| [Aachen Impulse Response (AIR) database](https://www.iks.rwth-aachen.de/en/research/tools-downloads/databases/aachen-impulse-response-database/) v1.4, IKS, RWTH Aachen | 5 | MIT | keep the MIT notice |
| [Open Database of Spatial Room Impulse Responses at Detmold University of Music](https://zenodo.org/records/4116247) | 3 | CC-BY-4.0 | the record's authors |
| [BBC Maida Vale Impulse Response Dataset](https://zenodo.org/records/10020866) (University of York and BBC R&D) | 1 | CC-BY-3.0 | Kearney, Daffern et al. |

OpenAIR licence evidence: the OpenAIR site was suspended on 2026-09-30, the day this was checked. The per-space CC BY 4.0 statement was confirmed through search-engine copies of each space's page and through audEERING's public `openair` redistribution (CC-BY-4.0, commercial). Re-check the pages when the site returns.

## Recorded drums (`drums-recorded-cc0-*` releases)

Built by [`.github/workflows/build-drums-recorded.yml`](.github/workflows/build-drums-recorded.yml) with the scripts in [`packs/drums-recorded/`](packs/drums-recorded/), from these CC0 recordings at the commits pinned in [`packs/drums-recorded/recipes.json`](packs/drums-recorded/recipes.json):

| Library | Author | Upstream | Licence |
|---|---|---|---|
| Versilian Community Sample Library (VCSL) | Versilian Studios LLC (Sam Gossner) and contributors | [sgossner/VCSL](https://github.com/sgossner/VCSL) `c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e` | CC0-1.0 |
| Big Rusty Drums | Karoryfer Samples | [sfzinstruments/karoryfer.big-rusty-drums](https://github.com/sfzinstruments/karoryfer.big-rusty-drums) `f07ce00df34a46b6b08375be56fe116cf15782bc` | CC0-1.0 |
| Swirly Drums | Karoryfer Samples | [sfzinstruments/karoryfer.swirly-drums](https://github.com/sfzinstruments/karoryfer.swirly-drums) `c40dafe0011cb2e54c0c220ff0fa308a11fc60f5` | CC0-1.0 |

The one-shots are trimmed, mixed from the upstream microphones, levelled and level-matched, and are CC0-1.0 too. No credit is required; each release's `NOTICES.md` gives it anyway, and `provenance.json` lists every upstream file behind every one-shot.
