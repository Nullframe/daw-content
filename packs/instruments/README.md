# The instruments pack: bundled GPL synths

Three free synths that producers keep using, built from source by us and shipped as a content
pack (design §8.5, layer 3): **Vitalium** (DISTRHO's wavetable synth), **Dexed** and **OB-Xf**. Each is an ordinary VST3 plugin that `daw` loads in its out-of-process plugin worker
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
**public** Nullframe release, never the internal `daw` repository: [Nullframe/daw-content
`instruments-2026.09.2`](https://github.com/Nullframe/daw-content/releases/tag/instruments-2026.09.2)
(see [Publishing a release](#publishing-a-release)).

**Status (2026-09-30): published.** GitHub Actions in Nullframe/daw-content built the pack
from the pinned upstream commits for Linux x86_64 and aarch64 and macOS universal, and published
it with its source archive. `pack.json` pins that release's sha256 values, so `daw pack install
instruments` downloads, verifies, clears macOS quarantine and indexes it. That was checked end to
end on macOS (arm64) from the real release: all three plugins scan and load, and all 487 OB-Xf
presets are taken (none rejected). Vitalium and Dexed are tier A. OB-Xf was tier C in that
first release (2026.09.0); **2026.09.1** adds a seed patch (`patches/obxf/`, daw-content only)
and OB-Xf is tier A, see [Determinism](#determinism-tier-a). **2026.09.2** (same upstream commits
and code) adds Vitalium's GPL-3 text, which DISTRHO-Ports' tree lacks, and attaches every licence
text and the source offer to the release. The Linux archives are built and hash-pinned; the published release has not been installed on a real Linux machine yet (a local
Linux x86_64 build of OB-Xf was).

## What's in it

| Instrument | Upstream (pinned) | Licence | Factory presets | `--plugin` | `--preset FILE` |
|---|---|---|---|---|---|
| Vitalium | [DISTRHO/DISTRHO-Ports](https://github.com/DISTRHO/DISTRHO-Ports) `ports-juce6.0/vitalium` `d3b62da2`, from [mtytel/vital](https://github.com/mtytel/vital) | GPL-3.0-or-later | none: the port has none, and Vital's are not free | `vitalium`, `vital` | `.vital` (JSON) |
| Dexed 1.0.1 | [asb2m10/dexed](https://github.com/asb2m10/dexed) `v1.0.1` `bce5deee` | GPL-3.0-or-later (its `msfa` FM engine is Apache-2.0) | none: its built-in DX7 banks have no clear authorship or licence and are removed from the build (init voice only) | `dexed`, `dx7` | — |
| OB-Xf 1.0.3 | [surge-synthesizer/OB-Xf](https://github.com/surge-synthesizer/OB-Xf) `v1.0.3` `1223e6f7` | GPL-3.0-or-later | its factory library: the 487 of 488 `.fxp` patches that declare an author and a CC0 licence (in the source tree's installer assets; the plugin doesn't embed them), converted to `.vstpreset` | `obxf`, `ob-xf` | `.fxp` |

Surge XT is not in the pack: it duplicates Vitalium, so it was dropped. The pins,
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
collects licences, writes the source offer and `NOTICES.md`, converts factory presets, runs the
admission check and packages a reproducible archive (GNU tar, sorted, fixed times;
byte-identical on re-runs) and the source archive.

```sh
packs/instruments/build.sh                         # all three
packs/instruments/build.sh --only vitalium,dexed   # a partial pack, for local testing
packs/instruments/build.sh --limit-presets 20      # quick: at most 20 presets each
packs/instruments/build.sh --skip-index            # no daw needed: daw indexes on install (CI)
daw pack install instruments --from packs/instruments/.build/dist/daw-instruments-<version>-<platform>.tar.gz
```

It needs the `daw` CLI (built with `cargo build --release -p daw-cli` if missing) and the
plugin host worker (`host/README.md`): conversion and the admission check run the real plugins.
With `--skip-index` it needs neither: the archive then ships the licence-filtered patch files
as they are (`patch-files/<id>/<path in the upstream tree>`) instead of `presets/` and
`content.json`, and `daw pack install` runs the same index and admission check on the user's
machine (`indexed_on_install: true` in its result). That is how the published release is built
(see [Publishing a release](#publishing-a-release)), because the public build runs where daw's
source isn't available.
Everything goes to `packs/instruments/.build/` (gitignored): `src/`, `build/`, `stage/` (the
unpacked pack, also installable with `--from`), `dist/` (archives, `.sha256` files,
`artifact-<platform>.json` and `source-digest-<platform>.txt`, a per-file hash of the source
tree used to check that every platform was built from the same source).

### Linux (Ubuntu 24.04; CI)

```sh
sudo apt-get install git cmake ninja-build meson python3 g++ pkg-config \
  libx11-dev libxrandr-dev libxinerama-dev libxcursor-dev libxext-dev libxcomposite-dev \
  libxi-dev libxrender-dev libfreetype-dev libfontconfig1-dev libasound2-dev libgl-dev \
  libglu1-mesa-dev libcurl4-openssl-dev libjack-jackd2-dev libgtk-3-dev libfftw3-dev
cmake -S host -B host/build -G Ninja -DCMAKE_BUILD_TYPE=Release && cmake --build host/build
packs/instruments/build.sh
```

### macOS (local run)

```sh
xcode-select --install                              # Xcode 16 or later (OB-Xf's C++20)
brew install cmake ninja meson python gnu-tar      # gnu-tar: a byte-reproducible archive
cmake -S host -B host/build -G Ninja -DCMAKE_BUILD_TYPE=Release && cmake --build host/build
packs/instruments/build.sh                          # universal (arm64 + x86_64), macOS 11+
```

Bundles are ad-hoc signed by the linker, which is enough for `daw`'s worker to load them.
They are not signed with a Developer ID or notarized, so Gatekeeper would refuse them if they
carried the quarantine attribute, which a browser adds to what it downloads. How `daw` handles
that:

- `daw pack install` (and `library-sync --pack`) downloads with curl, which doesn't set the
  attribute.
- An archive the user downloaded with a browser and passes with `--from` is quarantined, and
  what is unpacked from it can inherit that. So after `daw` has checked an archive's sha256 (against
  its `.sha256` file or the pinned manifest) and unpacked it into its own staging folder, it
  removes `com.apple.quarantine` from everything in that folder (`pack::clear_quarantine`,
  `xattr -r -d`). It touches only files it just unpacked from a verified archive, and never
  anything else on disk. An archive with the wrong hash is refused before anything is unpacked.
- A stage *folder* passed with `--from` isn't hash-checked, so its attributes are left as they
  are; clear them yourself if you trust it (`xattr -dr com.apple.quarantine <folder>`).

Signing and notarizing with a Developer ID is a release step to add when we distribute
signed `daw` builds.

### What each recipe does (`recipes/`)

| Recipe | Build | Notes |
|---|---|---|
| `vitalium.sh` | `meson setup -Dplugins=vitalium -Dbuild-juce60-only=true -Dbuild-vst3=true` (+ `-Dbuild-universal=true` on macOS), `ninja` | Needs meson and fftw3. Not `-Dlinux-headless`, which builds LV2 only. On macOS it renames the library to `vitalium` and adds an `Info.plist`, since meson's bundle (`vitalium.dylib`, no plist) doesn't load |
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
(`patches/README.md`). A release built with `--skip-index` is checked on install instead,
and install doesn't refuse: an instrument that fails is installed as tier C (usable, not
bit-exact) and `content.json` records the differing renders.

**Measured on the first release (macOS, arm64):** Vitalium and Dexed are tier A; OB-Xf was
tier C: its init patch and all three presets rendered differently in two fresh workers with the
same seed. The cause was `juce::Random`'s default seed (it mixes in an object address and the
clock) for the per-voice "slop" and the LFO sample-and-hold, which the shim can't pin. From
pack **2026.09.1**, `patches/obxf/01-seed-rng-from-rand.patch` seeds both from `std::rand()`,
which the shim does pin, and OB-Xf is tier A (init and three presets, each pair bit-identical,
on Linux x86_64). The patch is GPL, so it lives only in daw-content's copy of this folder;
daw-content's NOTICES records it. The same fix exposed that OB-Xf's `.fxp` chunks are its
*program* state, which its plugin state wraps in a `<program>` element: daw now wraps them
(`vstpreset::program_to_plugin_state`), and the indexer renders once after resetting to the
init patch, because OB-Xf defers a patch load while changes are still queued for its audio
thread. Before that, the randomness hid that the presets weren't loading. After install, `daw plugin-scan` still double-renders each plugin, and a
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
  `licenses/`, `SOURCE-OFFER.md`, `NOTICES.md`, `source/`. A release built with
  `--skip-index` has `patch-files/<id>/…` instead of `content.json` and `presets/`; install
  makes those.
- **Install** (`daw pack install`): download `base_url + file` (curl) or take `--from` an
  archive (checked against the `.sha256` next to it, else the manifest) or a stage folder
  (not hash-checked; a warning says so); verify sha256; unpack to a staging folder; check id,
  platform, bundles, licences and source offer (after clearing macOS quarantine and, for an
  unindexed archive, indexing it with the local worker); replace `$DAW_HOME/packs/<id>/`; write
  `installed.json` (source, sha256, what it was verified against); scan the pack's `vst3/`.
- **Registration**: a default `plugin-scan` also searches `$DAW_HOME/packs/*/vst3` (after the
  standard folders, `$DAW_VST3_PATH` and config `plugin_paths`) and lists `.vstpreset` files from
  `packs/*/presets/vst3`. Catalog entries from a pack carry `pack` and `aliases`.
- `daw pack list` shows known packs and what's installed, `daw pack remove <id>` uninstalls
  (then `daw plugin-scan`).

## Publishing a release

The pack is hosted on releases of the **public** repository
[Nullframe/daw-content](https://github.com/Nullframe/daw-content), never on the internal `daw`
repository (the GPL source offer has to be reachable by everyone who gets the binaries). Its
workflow `build-instruments` builds the pack on GitHub's runners (Linux x86_64 and aarch64 on
Ubuntu 22.04; macOS universal on `macos-14` with Xcode 16) from a copy of this folder
(`packs/instruments/` there), with `build.sh --skip-index`, and publishes the release
`instruments-<UTC date>`.

**What a release contains** (for `version` 2026.09.2):

| File | Built on |
|---|---|
| `daw-instruments-2026.09.2-linux-x86_64.tar.gz` (+ `.sha256`) | `ubuntu-22.04` |
| `daw-instruments-2026.09.2-linux-aarch64.tar.gz` (+ `.sha256`) | `ubuntu-22.04-arm` |
| `daw-instruments-2026.09.2-macos-universal.tar.gz` (+ `.sha256`) | `macos-14` (arm64 + x86_64, macOS 11+) |
| `daw-instruments-2026.09.2-src.tar.gz` (+ `.sha256`) | `ubuntu-22.04`: the complete corresponding source; the workflow refuses to publish unless every platform's source digest matches it |
| `LICENSE-vitalium.txt`, `LICENSE-dexed.txt`, `LICENSE-obxf.txt`, `licenses.tar.gz`, `SOURCE-OFFER.md` | each instrument's GPL-3 text, every licence file from the upstream trees, and the source offer (`release-licences.sh`) |
| `SHA256SUMS`, `artifacts.json` (file, sha256, bytes per platform), `NOTICES.md` | |

`release-licences.sh` writes the licence assets and fails the build (on PRs too) unless the
source archive holds every instrument's upstream tree, our patches and the build scripts, and
each instrument has its GPL-3 text. DISTRHO-Ports keeps only GPL-2 and LGPL-3 texts in `doc/`,
while Vitalium's files are "version 3 or later", so `build.sh` adds the FSF's text
(`licence-texts/GPL-3.0.txt`) as `licenses/vitalium/GPL-3.0.txt`; 2026.09.1 and earlier lacked it.

**Steps.**

1. Change `packs/instruments/` here and in daw-content together (a PR in each). Bump `version`
   (and the file names) whenever a pin, patch, recipe or preset rule changes: archives are
   immutable once `pack.json` pins them.
2. Run `build-instruments` in daw-content (Actions → Run workflow; or push a tag
   `instruments-<date>`). A PR there builds every platform without publishing.
3. Set `release.base_url` to the release's download URL and copy its `artifacts.json` into
   `pack.json`'s `artifacts`, in a PR here. From that `daw` build on, `daw pack install
   instruments` (and `daw library-sync --pack instruments`) downloads, verifies and indexes.

## Not yet

- Cardinal (VCV Rack, optional in §8.5) and a CLAP build of each synth.
- A typed JSON patch API with natural units (§8.5): today Vitalium's JSON is the plugin's own
  format, loaded as is, and the other synths' parameters are set by name in display units like
  any plugin's.
- Windows.
