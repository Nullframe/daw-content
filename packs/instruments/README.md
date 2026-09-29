# The instruments pack: bundled GPL synths

Three free synths that producers keep using, built from source by us and shipped as a content
pack (design §8.5, layer 3): **Vitalium** (a renamed build of Vital), **Dexed** and **OB-Xf**. Each is an ordinary VST3 plugin that `daw` loads in its out-of-process plugin worker
(`host/`), so agents use them like any other device:

```sh
daw pack install instruments                      # download, verify sha256, install, scan
daw preset-search warm pad --device obxf          # factory presets, with tags and levels
daw track add lead --plugin obxf --preset "NAME"  # NAME from preset-search (its "use" field)
daw track add keys --plugin dexed                 # Dexed ships its init voice only (see Presets)
daw track add pad  --plugin vitalium --preset ~/presets/glass.vital   # patch files as data
daw pack verify instruments                       # each renders bit-identically twice (tier A)
daw doctor                                        # lists the pack: present, registered, tier
```

`daw library-sync --pack instruments` does the same install as part of a library sync.

**Optional.** `daw` works fully without the pack: nothing in the core depends on it, `doctor`
passes without it, and a plain `daw library-sync` lists it under `optional_packs` with how to
get it (the install command, or the local build while no release is published).

**Founder decision (2026-09-29): ship, cautiously.** Only presets whose authorship and licence
are clear ship (see [Preset provenance](#preset-provenance)), and the archives are hosted on a
**public** Nullframe release, never the internal `daw` repository. That release doesn't exist
yet: `pack.json`'s `release.base_url` is a placeholder until it does (see
[Publishing a release](#publishing-a-release)).

**Status (2026-09-29).** The pack format, install, registration, preset index, patch-file
loading, admission check and `doctor` are implemented and tested end to end with the in-repo
test instrument (`crates/daw-cli/tests/pack.rs`). The build recipes below are written against
the pinned upstreams but **have not yet been run against them**: the cloud session that wrote
them could not fetch upstream sources. The first local run is the check; every step fails
loudly (wrong commit, missing target or bundle, a plugin name that isn't the expected one, a
preset the plugin ignores, a render that isn't bit-identical). No release is published yet, so
`daw pack install instruments` without `--from` says `pack_not_published` and how to build.

## What's in it

| Instrument | Upstream (pinned) | Licence | Factory presets | `--plugin` | `--preset FILE` |
|---|---|---|---|---|---|
| Vitalium | [DISTRHO/DISTRHO-Ports](https://github.com/DISTRHO/DISTRHO-Ports) `ports-juce6.0/vitalium` `d3b62da2`, from [mtytel/vital](https://github.com/mtytel/vital) | GPL-3.0-or-later | none: the port has none, and Vital's are not free | `vitalium`, `vital` | `.vital` (JSON) |
| Dexed 1.0.1 | [asb2m10/dexed](https://github.com/asb2m10/dexed) `v1.0.1` `bce5deee` | GPL-3.0-or-later (its `msfa` FM engine is Apache-2.0) | none: its built-in DX7 banks have no clear authorship or licence and are removed from the build (init voice only) | `dexed`, `dx7` | — |
| OB-Xf 1.0.3 | [surge-synthesizer/OB-Xf](https://github.com/surge-synthesizer/OB-Xf) `v1.0.3` `1223e6f7` | GPL-3.0-or-later | its factory library: the 487 of 488 `.fxp` patches that declare an author and a CC0 licence (in the source tree's installer assets; the plugin doesn't embed them), converted to `.vstpreset` | `obxf`, `ob-xf` | `.fxp` |

Surge XT is not in the pack: it duplicates Vital (Vitalium), so it was dropped. The pins,
aliases and preset sources live in [`pack.json`](pack.json), which is compiled into `daw`
(`crates/daw-plugins/src/pack.rs`).

## Licences, the source offer and what stays out of `daw`

- **Licence tier (AGENTS.md).** All three are GPL projects, which AGENTS.md lists under "never
  copy code from": Vital/Vitalium (GPL-3.0-or-later), Dexed (GPL-3.0-or-later) and OB-Xf
  (GPL-3.0-or-later, the OB-Xd lineage). None of their code is in this repository or linked
  into `daw`. The pack is **separate plugin binaries the user downloads** (`daw pack install`)
  and `daw` hosts them out of process, exactly as it hosts a user's own plugins.
- **Separate programs, never linked.** The synths are GPL-3.0 plugins. `daw` (Apache-2.0) talks
  to them only through the plugin worker's pipes and shared memory, like any user plugin; no
  Rust crate links them or JUCE. Nothing GPL is committed to this repository: only pins,
  scripts and this README. Converted presets and the preset index are made at build time and
  shipped inside the pack, under the synth's licence.
- **Licence texts ship with the binaries**: `licenses/<id>/` holds every `LICENSE*`,
  `LICENCE*`, `COPYING*` found in the upstream tree and its submodules, plus `UPSTREAM.txt`
  (repository, commit, our patches with their sha256, preset provenance).
- **Complete corresponding source, from the same place** (GPL-3.0 §6(d)): every release
  publishes `daw-instruments-<version>-src.tar.gz` next to the binary archives: each upstream
  tree at its pinned commit with our patches applied, plus these scripts. The pack's
  `SOURCE-OFFER.md` says so and adds a three-year written offer (§6(b)); `source/` in the pack
  holds the build scripts.
- **No DRM, no activation, no telemetry.** We add nothing to the plugins except the patches in
  `patches/` (none today). One change removes content: Dexed's built-in cartridge zip is
  replaced by an init-voice cartridge before building (`recipes/dexed.sh`; see below).
- **Trademarks.** "Vital" is a trademark of Matt Tytel. We ship DISTRHO's community build,
  already renamed **Vitalium** with its own plugin ids, and `daw pack index` refuses a bundle
  whose plugin name isn't the one in `pack.json`. Dexed and OB-Xf are shipped under
  their own names, as their projects distribute them.
- The GPL allows all of this without asking the authors, and we don't contact them.

## Building

The build fetches each pinned commit (shallow, with submodules), checks it is that commit,
applies `patches/<id>/*.patch`, builds the VST3 bundles with each project's own build system,
collects licences, writes the source offer, converts factory presets, runs the admission check
and packages a reproducible archive (GNU tar, sorted, fixed times; byte-identical on re-runs).

```sh
packs/instruments/build.sh                         # all three
packs/instruments/build.sh --only vitalium,dexed   # a partial pack, for local testing
packs/instruments/build.sh --limit-presets 20      # quick: at most 20 presets each
daw pack install instruments --from packs/instruments/.build/dist/daw-instruments-<version>-<platform>.tar.gz
```

It needs the `daw` CLI (built with `cargo build --release -p daw-cli` if missing) and the
plugin host worker (`host/README.md`): conversion and the admission check run the real plugins.
Everything goes to `packs/instruments/.build/` (gitignored): `src/`, `build/`, `stage/` (the
unpacked pack, also installable with `--from`), `dist/` (archives, `.sha256` files and
`artifact-<platform>.json`).

### Linux (Ubuntu 24.04; CI)

```sh
sudo apt-get install git cmake ninja-build meson python3 g++ pkg-config \
  libx11-dev libxrandr-dev libxinerama-dev libxcursor-dev libxext-dev libxcomposite-dev \
  libxi-dev libfreetype-dev libfontconfig1-dev libasound2-dev libgl-dev libcurl4-openssl-dev \
  libjack-jackd2-dev
cmake -S host -B host/build -G Ninja -DCMAKE_BUILD_TYPE=Release && cmake --build host/build
packs/instruments/build.sh
```

### macOS (local run)

```sh
xcode-select --install
brew install cmake ninja meson python gnu-tar      # gnu-tar: a byte-reproducible archive
cmake -S host -B host/build -G Ninja -DCMAKE_BUILD_TYPE=Release && cmake --build host/build
packs/instruments/build.sh                          # universal (arm64 + x86_64), macOS 11+
```

Bundles are ad-hoc signed by the linker, which is enough for `daw`'s worker to load them. A
pack downloaded with a browser (rather than by `daw pack install`, which uses curl) gets the
quarantine attribute: `xattr -dr com.apple.quarantine ~/Music/daw/packs/instruments`.
Signing and notarizing with a Developer ID is a release step to add when we distribute
signed `daw` builds.

### What each recipe does (`recipes/`)

| Recipe | Build | Notes |
|---|---|---|
| `vitalium.sh` | `meson setup -Dplugins=vitalium -Dbuild-vst3=true` (+ `-Dlinux-headless=true` / `-Dbuild-universal=true`), `ninja` | Needs meson |
| `dexed.sh` | CMake target `Dexed_VST3` | First replaces `assets/builtin_pgm.zip` with an init-voice cartridge ([Preset provenance](#preset-provenance)) |
| `obxf.sh` | CMake target `OB-Xf_VST3` | |

A named target that doesn't exist falls back to the default target; `build.sh` then looks for
the bundle by name and stops if it isn't there. These target and option names are the ones to
check on the first real run.

## Determinism (tier A)

Design §11.3 promises bit-exact renders for admitted bundled plugins. The worker's shim pins the
clock and OS randomness that plugin code sees to the project seed (host/README.md), which the
host spike showed makes Dexed bit-identical across fresh workers. So we
**prefer the shim and patch only if needed**.

The **admission check** (`daw pack index`, run by `build.sh`, and `daw pack verify
instruments` at any time) renders a four-note phrase with each instrument's init patch and with
up to three factory presets, each twice in fresh workers with the same seed (7), and requires
every pair to be bit-identical and finite. `build.sh` refuses to package an instrument that
isn't tier A (`--allow-tier-c` for a local test build); the fix is a seed patch
(`patches/README.md`). After install, `daw plugin-scan` still double-renders each plugin, and a
pack plugin is marked tier A only when its pack's admission passed and the scan agrees
(`plugin-list`, `plugin-info`, `doctor`).

## Presets: patch files as data

Every factory preset becomes a `.vstpreset` under the pack's
`presets/vst3/<vendor>/<plugin>/<category>/`, which `plugin-scan` lists for the plugin, so
`--preset NAME` works like any VST3 preset; `presets/index.json` adds what search needs.

- **Patch files** (Vitalium `.vital`, OB-Xf `.fxp`): a `.vstpreset` is a header plus chunks
  (VST3 SDK format, MIT); its `Comp` chunk is the plugin's component state, which JUCE plugins
  take as their `setStateInformation` data. Vital's state is the JSON of its `.vital` files;
  OB-Xf's `.fxp` is its state behind a 60-byte VST2 program header, which is stripped. The class
  id comes from a preset the plugin saves itself (`crates/daw-plugins/src/vstpreset.rs`). The
  same conversion runs when a user passes `--preset FILE.vital` or `--preset FILE.fxp`, so
  Vitalium patches are editable JSON that load straight into a project.
- **Programs** (`format: programs`): each program in the plugin's own list is selected and
  saved by the plugin. No instrument uses this today (Dexed's programs are its excluded banks).
- **Licence filter**: with `require_license` set (OB-Xf: `CC0`, `CC0 / Public Domain`), a patch
  ships only if it declares one of those licences in its own metadata; its declared author and
  licence go into the preset index. Anything else is listed under `rejected_presets`.
- Each preset is then loaded into the plugin and rendered (C3 + C4, 1 s). A converted patch
  that sounds exactly like the init patch was ignored by the plugin: it is left out and listed
  under `rejected_presets` in `content.json`. The probe's peak and RMS are recorded.
- Names are unique per plugin (a clash gets ` (Category)`); tags come from the category
  (`Basses` → `bass`) and a small sound vocabulary matched in the name (`E.PIANO 1` →
  `epiano`, `keys`, `piano`), plus `quiet` below −60 dBFS RMS.

`daw preset-search` returns pack presets after library presets (at most 50; `--device obxf`
narrows), each with `use` (`--plugin obxf --preset "<name>"`), tags, category, author,
level and licence. `daw preset-list --device obxf` lists one instrument's presets.

## Preset provenance

Rule: a bank ships only when its authors are known and its terms allow redistribution;
anything unclear stays out. The same record is in `pack.json` (`presets.banks`, checked by a
unit test) and in each pack's `licenses/<id>/UPSTREAM.txt`.

| Instrument | Bank | Authors | Terms | In? | Why |
|---|---|---|---|---|---|
| Vitalium | Vital factory presets | Vital Audio / Matt Tytel | proprietary, not in the GPL source | out | Not free. DISTRHO's Vitalium port contains no presets. |
| Dexed | `Dexed_01` (32 voices, the startup cartridge in `assets/builtin_pgm.zip`) | unknown; compiled by Jean-Marc Desprez (SynprezFM) from DX7 SysEx archives | none stated | out | No per-voice authors, no redistribution terms. |
| Dexed | `SynprezFM_01`–`SynprezFM_32` (1024 voices, same zip) | unknown per voice; selected from ~22,000 patches circulating online. Dexed's README credits the compilation, not the sounds | none stated | out | Same; archives like these can include voices from Yamaha or commercial cartridges. |
| Dexed | Yamaha DX7 ROM1A–4B and VRC cartridges | Yamaha | no redistribution grant | out | Yamaha's. Not in Dexed's source; never shipped. |
| OB-Xf | Factory library (`assets/installer/Surge Synth Team/OB-Xf/Patches`, 487 patches) | Saif Sameer, Aleksey Zhehanov, Black Sided Sun, Ocean Swift, Jacky Ligon, 0.5°, Fedir Tkachov, Artur Rembe, Vincent Zauhar, Pebblestream, John Valentine, Den Rize, EvilDragon | CC0: each patch declares `license="CC0"` or `"CC0 / Public Domain"` and its `author` | **in** | Made for OB-Xf by named authors (OB-Xd patches aren't compatible) and dedicated to the public domain in the file. |
| OB-Xf | `Bells/Singing Noise.fxp` | none declared | none declared | out | The only patch with no author or licence; the licence filter drops it. |

**Dexed binary.** Dexed compiles its banks into the plugin (`BinaryData::builtin_pgm_zip`) and
loads `Dexed_01` at startup, so leaving them out of the index isn't enough. `recipes/dexed.sh`
replaces `assets/builtin_pgm.zip` before building with a zip holding only `Dexed_01.syx`: 32
copies of Dexed's own INIT VOICE (its `init_voice` table, GPL-3.0), packed as a DX7 bulk dump.
The shipped plugin and the source archive therefore carry no third-party DX7 voices. Users
load their own cartridges in Dexed. Adding a Dexed bank later needs named authors and
redistributable terms (for example a CC0 or CC-BY bank) recorded in `presets.banks`.

## Pack format (`daw-pack/1`)

- **Manifest** `pack.json` (`crates/daw-plugins/src/pack.rs`: `Manifest`): id, version,
  instruments (bundle, aliases, licence, upstream pin, patch formats, preset source),
  `release.base_url`, and per platform (`linux-x86_64`, `linux-aarch64`, `macos-universal`)
  the archive name, `sha256` and size. `sha256: null` means not published.
- **Archive** `daw-instruments-<version>-<platform>.tar.gz`: `content.json` (what was built:
  plugin names, kinds, versions, aliases, preset counts, rejected presets, settle mode, the
  admission renders and tier), `vst3/`, `presets/index.json` + `presets/vst3/…`,
  `licenses/`, `SOURCE-OFFER.md`, `source/`.
- **Install** (`daw pack install`): download `base_url + file` (curl) or take `--from` an
  archive (checked against the `.sha256` next to it, else the manifest) or a stage folder
  (not hash-checked; a warning says so); verify sha256; unpack to a staging folder; check id,
  platform, bundles, licences and source offer; replace `$DAW_HOME/packs/<id>/`; write
  `installed.json` (source, sha256, what it was verified against); scan the pack's `vst3/`.
- **Registration**: a default `plugin-scan` also searches `$DAW_HOME/packs/*/vst3` (after the
  standard folders, `$DAW_VST3_PATH` and config `plugin_paths`) and lists `.vstpreset` files from
  `packs/*/presets/vst3`. Catalog entries from a pack carry `pack` and `aliases`.
- `daw pack list` shows known packs and what's installed, `daw pack remove <id>` uninstalls
  (then `daw plugin-scan`).

## Publishing a release

The pack is hosted on a **public** Nullframe GitHub release, never on the internal `daw`
repository (the GPL source offer has to be reachable by everyone who gets the binaries).
Neither the repository nor the release exists yet; creating them is a founder step.

**One config value.** `pack.json` → `release.base_url` is where every archive is fetched
from (`base_url + file`), and `build.sh` derives the source offer's URLs from it. It is a
placeholder today:

```
https://github.com/Nullframe/daw-content/releases/download/<tag>/
```

While it contains `<tag>`, `daw` treats the pack as unpublished (`pack_not_published`, with
the local-build command) even if hashes are filled in. Suggested tag:
`instruments-<version>`, e.g. `instruments-2026.09.0`.

**What the release must contain** (for `version` 2026.09.0). Each `.sha256` file is one line,
`<sha256>  <file>`, written by `build.sh`; the platform values also go into `pack.json`.

| File | Built on | sha256 |
|---|---|---|
| `daw-instruments-2026.09.0-linux-x86_64.tar.gz` | Linux x86_64 | its `.sha256`; → `pack.json` `artifacts.linux-x86_64.sha256` (+ `bytes`) |
| `daw-instruments-2026.09.0-linux-aarch64.tar.gz` | Linux aarch64 | its `.sha256`; → `artifacts.linux-aarch64` |
| `daw-instruments-2026.09.0-macos-universal.tar.gz` | macOS (arm64 + x86_64) | its `.sha256`; → `artifacts.macos-universal` |
| `daw-instruments-2026.09.0-src.tar.gz` | any one of the above | its `.sha256` (the complete corresponding source) |
| the four `*.tar.gz.sha256` files | | |

The values are not known until the first real build (the recipes haven't run yet), so
`pack.json` holds `sha256: null` for now. The source archive holds only sources and scripts;
build it once and upload that one (every run produces it).

**Steps.**

1. Set `release.base_url` to the real tag (and bump `version` and the file names if anything
   changed), in a PR.
2. On each platform (see [Building](#building); GNU tar for byte-reproducible archives):
   `packs/instruments/build.sh`. Output in `packs/instruments/.build/dist/`: the platform
   archive and its `.sha256`, `artifact-<platform>.json` (`file`, `sha256`, `bytes`), and the
   source archive and its `.sha256`.
3. Create the release on the public repository and upload every file in the table.
4. Copy each `artifact-<platform>.json`'s `sha256` and `bytes` into `pack.json`'s `artifacts`,
   in a PR. From that `daw` build on, `daw pack install instruments` (and `daw library-sync
   --pack instruments`) downloads and verifies.

Bump `version` (and the file names) whenever a pin, patch, recipe or preset rule changes;
archives are immutable once published.

## Not yet

- Cardinal (VCV Rack, optional in §8.5) and a CLAP build of each synth.
- A typed JSON patch API with natural units (§8.5): today Vitalium's JSON is the plugin's own
  format, loaded as is, and the other synths' parameters are set by name in display units like
  any plugin's.
- Windows.
