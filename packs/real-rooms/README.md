# Real rooms IR pack

Recorded impulse responses (IRs) of real spaces for daw's `convolution@1`: 34 IRs covering rooms, a studio live room, drum rooms, wood and marble halls, concert and chamber halls, a theatre, a cathedral and churches, stairwells, a warehouse and a concrete hall, a railway tunnel, a cave, outdoor spaces and a spring. Only sources whose licence allows commercial use, modification and redistribution are included: CC BY 4.0, CC BY 3.0 and MIT. `NOTICES.md` in each release lists attribution and evidence.

- `recipes.json` is one entry per IR: the upstream URL (a WAV, or a member of a zip read with HTTP range requests), the channel choice, and the tags that daw's manifest carries (space, size, uses, licence, author, source page).
- `build.py OUT` downloads the sources and conditions each IR:
  - removes DC offset;
  - keeps B-format's W channel;
  - resamples to 48 kHz;
  - trims to the direct sound;
  - cuts the tail at the noise floor;
  - normalises the peak to -1 dBFS;
  - writes 24-bit WAV.

  It also measures each IR (RT60 from T30, EDT, octave RT60s, spectral balance) and writes `SHA256SUMS`, `measurements.json` and `provenance.json`, which holds the upstream URL and sha256 per file.
- `notices.py OUT` writes `NOTICES.md`.
- `manifest.py OUT TAG` writes daw's pack manifest (`content/irs/packs/real-rooms.json` in the daw repository).

The workflow [`build-real-rooms`](../../.github/workflows/build-real-rooms.yml) runs all of this. On a pull request it only builds. A manual run, or a pushed `real-rooms-*` tag, publishes the release. Versions of numpy, scipy and soundfile are pinned so the bytes are reproducible. After publishing, copy the release's `real-rooms.json` into the daw repository. daw pins every sha256 from it and `daw library install real-rooms` verifies each download.

Rejected sources and the reason for each are recorded in the daw PR that added the pack. They include:
- NonCommercial or ShareAlike licences: C4DM/Isophonics, PAN-AR, BBC BRIRs, ACE.
- No redistribution: EchoThief, Voxengo, Samplicity.
- No licence: MIT survey, Fokke van Saane.
- Blocked by robots.txt or needing an account: Freesound.
