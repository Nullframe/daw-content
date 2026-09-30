# Pianos: sampled acoustic pianos for daw's `sampler@1`

Two multisampled pianos, packaged for daw as one uncompressed tar of FLAC files each:

| Archive | Instrument | Source | Licence |
|---|---|---|---|
| `salamander-grand-v1.tar` (747,294,720 bytes, 643 files) | `instrument/salamander-grand@1` (presets `grand`, `grand-bright`, `grand-soft`) | Salamander Grand Piano V3 by Alexander Holm (Yamaha C5), FreePats SFZ+FLAC edition | Public domain (author's dedication, 4 March 2022); originally CC BY 3.0. We credit him either way. |
| `upright-kw-v1.tar` (32,870,400 bytes, 69 files) | `instrument/upright-kw@1` (preset `upright`) | Upright Piano KW by Gonzalo and Roberto (FreePats) | CC0 1.0 |

Each archive holds the upstream FLAC files byte for byte, the upstream readme and licence, and a
`NOTICE.txt` with the attribution and licence evidence. `NOTICES.md` in each release repeats the
attribution. Tuning, level and mapping corrections live in daw's `instrument.json`, not in the
audio.

`package.sh`, `package.py` and `analysis.py` are copied from the daw repository's
`scripts/instruments/` (daw commit `2742920`); keep them in sync. `package.sh NAME WORK OUT` downloads
the pinned upstream archive, checks its sha256, and writes `OUT/NAME-v1.tar` byte-identically for
the same input (numpy, soundfile and py7zr are pinned).

The workflow [`build-pianos`](../../.github/workflows/build-pianos.yml) builds both archives and
checks each against the sha256 that daw pins (`content/instruments/<name>/instrument.json`,
`archive.sha256`). On a pull request it only builds. A manual run, or a pushed `pianos-*` tag,
publishes the release. Then daw's `content/instruments/release.json` points `base_url` at it, and
`voyager-daw library install salamander-grand` (or `upright-kw`) downloads, verifies and unpacks
the archive.
