# Synthesis benchmark reference sounds (CC0)

The reference sounds of daw's synthesis benchmark (`daw-bench synth`, docs/research/synthesis-gaps.md
in daw). 65 targets across what users ask a synth for: drums, cinematic hits and transitions,
tonal instruments, textures, UI/SFX, a few oddballs and 12 electronic synth sounds (supersaw,
reese, 808, acid, wobble, hoover and others). Each has a short text description of the
sound, which is all an agent gets in the benchmark's design-from-description track.

They are built by [`build-synth-bench`](../../.github/workflows/build-synth-bench.yml) from the
upstream files pinned in [`recipes.json`](recipes.json) and published as a `synth-bench-<date>`
release. **No audio is committed.**

## Sources and licences

CC0 recordings, pinned by commit, URL or dataset id, with each upstream file's sha256:

| Library | Upstream | Licence |
|---|---|---|
| Recorded drums (CC0) | this repo's `drums-recorded-cc0-2026-09-30` release (VCSL, Karoryfer) | CC0-1.0 |
| Versilian Community Sample Library (VCSL) | [sgossner/VCSL](https://github.com/sgossner/VCSL) `c1ea7bc` | CC0-1.0 |
| VSCO 2 Community Edition | [sgossner/VSCO-2-CE](https://github.com/sgossner/VSCO-2-CE) `4403009` | CC0-1.0 |
| Sonic Pi sample set | [sonic-pi-net/sonic-pi](https://github.com/sonic-pi-net/sonic-pi) `4a9b201`, `etc/samples` (Freesound CC0 uploads and The Black Dog's CC0 donation; `loop_amen*` not used) | CC0-1.0 |
| Kenney Sci-Fi Sounds, Interface Sounds | kenney.nl (the zips' `License.txt`) | CC0-1.0 |
| FSD50K | [Zenodo 4060432](https://zenodo.org/records/4060432), CC0 clips only, range-read out of the split zip (>= 10 s between requests) | CC0-1.0 per clip (the dataset compilation is CC-BY-4.0) |

Freesound itself is never fetched: its robots.txt and API terms rule that out, so Freesound
sounds come only through FSD50K and Sonic Pi.

**Synthetic targets.** Nine of the electronic targets are our own renders, marked `synthetic` in
`targets.json`. They are made in the same workflow from the code in [`render/`](render):

| Engine | Upstream | Licence | Patches |
|---|---|---|---|
| fundsp 0.23.0 | crates.io, locked in `render/Cargo.lock`; Rust 1.97.0 (`render/rust-toolchain.toml`) | MIT OR Apache-2.0 | `render/src/main.rs`: lead-supersaw, bass-808-glide, pluck-house, pad-moving, bass-wobble, bass-growl, lead-hoover, riser-synth |
| Open303 | [RobinSchmidt/Open303](https://github.com/RobinSchmidt/Open303) `313bf0d` (git-fetched by commit) | MIT | `render/open303/acid.cpp`: bass-acid |

- Every patch is written by hand from textbook synthesis (detuned saws, ladder filters, FM,
  formant band-passes); none comes from a synth's presets.
- The renders are released as CC0-1.0, like the rest of the pack.
- `recipes.json` pins each render's sha256, so the build fails if a render stops being
  byte-identical to the one that was reviewed.
- A render made with an architecture daw also implements is an easy target, so daw reports
  `synthetic` targets on their own leaderboard row, outside the overall number.
- No GPL code is used.

## Electronic targets (2026-10-01)

Added for the synth upgrade plan's electronic category (E0, docs/research/synth-upgrade-plan.md
in daw). Three are recordings from the Sonic Pi sample set; nine are synthetic renders (above).

| id | Source | Licence evidence | What it is |
|---|---|---|---|
| `bass-reese` | Sonic Pi `bass_voxy_c` (Freesound 165325, ani_music) | Sonic Pi's samples README: Freesound samples "placed in the public domain via the Creative Commons 0 License". FSD50K's metadata lists the uploader's other sounds from the same batch (165315, 165321, 165326, 165330, 165331) as CC0. Freesound page not opened (see below) | C2 reese, 6 s: a comb of notches sweeping through the harmonics about every 3 s, mono low end, wide highs |
| `stab-chord` | Sonic Pi `tbd_highkey_c4` (The Black Dog) | Sonic Pi's samples README: "Donated by The Black Dog under a CC0 license" (the same evidence as the existing `pad-synth`) | G minor 7 chord stab around G4 (the file name says C4; measured peaks are G, B flat, D, F), about 1 s decay, wide |
| `bell-fm` | Sonic Pi `elec_chime` (Freesound 13138, looppool) | Sonic Pi's samples README (as above). Not in FSD50K; Freesound page not opened | Inharmonic electronic chime, partials from about 1.7 to 8 kHz, about 2 s; the source clips 46 samples in its first 53 ms |
| `lead-supersaw` | fundsp render | ours, CC0 | 7-voice supersaw, A4, wide |
| `bass-808-glide` | fundsp render | ours, CC0 | 808 on F1 gliding up to A#1 at 0.6 s, long sub tail |
| `pluck-house` | fundsp render | ours, CC0 | C4 saw pluck with a fast ladder-filter envelope |
| `pad-moving` | fundsp render | ours, CC0 | Cmaj9 pulse-wave pad, drifting pulse widths, lowpass opening and closing over 4.6 s |
| `bass-wobble` | fundsp render | ours, CC0 | F1 wobble, cutoff LFO at 1/8 of 140 BPM |
| `bass-acid` | Open303 render | ours, CC0 | accented C2 sliding into G2 |
| `lead-hoover` | fundsp render | ours, CC0 | C3 hoover: stacked PWM pulses, pitch dive in, octave fall out, chorus |
| `bass-growl` | fundsp render | ours, CC0 | F2 FM growl through moving "o"-"a" formants, sine sub |
| `riser-synth` | fundsp render | ours, CC0 | 4 s noise-plus-saw riser, band-pass sweep to 9 kHz, saws up two octaves |

Each was measured before it was chosen (pitch, partials, spectral centroid over time, stereo
correlation, clipping), and the Sonic Pi files were picked because the measurement matched the
sound: `bass_voxy_c` over `bass_dnb_f` (a static, noisy F1 with no phase movement) for the reese,
for example. Nobody listened to them; the founder's labelled listening check is still to do.

**Not used, and why:**
- **Freesound picked by hand.** Approved, but it needs a person: Freesound's robots.txt bars
  ClaudeBot from the whole site and originals need a login, so the agent could not open the
  pages or download originals (web.archive.org is also outside its network policy). FSD50K's CC0
  clips were searched instead (title, tags, uploader descriptions): it has almost no electronic
  synth one-shots (no supersaw, reese, wobble, hoover or acid sound; "Good Pad", 135484, is a
  gated sequence, not one pad). A person can add Freesound CC0 originals from uploaders who
  say they made the sound, with a provenance line each (sound id, uploader, licence on the
  download date), in a later release.
- **Surge XT and Vital init-patch renders.** Their content licences were read on 2026-10-01:
  - Surge XT ([surge-synthesizer/surge](https://github.com/surge-synthesizer/surge)
    `88f042b`): the repository and its installer licence are GPL-3.0; no separate content
    licence covers `resources/data`; third-party items carry their own terms
    (`resources/data/impulses_3rdparty/Voxengo/license.txt` forbids selling the IRs;
    `patches_3rdparty` and `wavetables_3rdparty` are by named authors).
  - Vital ([mtytel/vital](https://github.com/mtytel/vital), README): the source is GPL-3.0;
    "Do not distribute the presets that come with the free version of Vital. They're under a
    separate license that does not allow redistribution"; the names "Vital" and "Vital Audio"
    may not be used for builds.
  - Finding: the GPL covers the programs, not audio they output, and a hand-built init patch
    (built-in oscillators only, no factory or third-party patch, wavetable or IR) uses none of
    that content. So renders of hand-built init patches are allowed; factory presets are not
    used, per the founder's rule. No such render is in this release: Surge has no Python
    package to pin (surgepy must be built from source, about 20 minutes per CI run) and Vital
    would need a plugin host, which must not be daw. They are the next way to add third-party
    renders.

## Processing

`build.py` renders the synthetic targets (above), then treats every file alike. It keeps each
file's own sample rate and channels (identical channels become mono),
removes a DC offset, trims from 5 ms before the onset to a per-target length or to where it falls
70 dB under its peak, fades both ends, scales to a -1 dBFS peak and writes 24-bit WAV. No EQ,
compression or reverb: the benchmark compares synthesis with the recording as recorded.

## Descriptions

Each target's `description` was written from the source's own metadata (instrument, articulation,
note, the uploader's title and tags) and daw's measurements of the built file (pitch, attack,
decay, stereo correlation, how tonal it is, and how its spectrum moves over time). They say what a
user would ask for, including the note and the approximate length where that matters.
