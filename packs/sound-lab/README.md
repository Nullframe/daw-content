# sound-lab sources

The recordings that daw's **sound-lab** pack (`content/packs/sound-lab` in Nullframe/daw)
transforms: pads stretched out of a glass tap, booms made from an octave-down wood hit over a
sub, risers from a reversed bell in a big space, tuned plucks from clicks rung through a
resonator. Every sound in that pack is a `daw sound chain` recipe over these sources. The
recipes fetch each file from this repository's release by URL and pin its sha256.

- **CC0 or public domain only**: FSD50K clips whose Freesound licence is CC0, Kenney audio packs
  (CC0), and US National Park Service sound-gallery recordings (public domain). Our own synth
  sources are not here: the recipes render them in the project (`track:ID`).
- `sources.json` is one entry per file: title, author, licence, upstream page, how to fetch it
  (an FSD50K clip read by range out of the dataset's split zip on Zenodo, a Kenney zip member,
  or an NPS MP3) and, for a long recording, the excerpt in whole seconds.
- `build.py OUT` fetches and conditions every source the same way each time: decode, resample
  to 48 kHz with scipy's polyphase filter when needed, cut the excerpt, write 24-bit FLAC.
  numpy, scipy and soundfile are pinned so the bytes are reproducible. It also writes
  `SHA256SUMS`, `provenance.json` and `NOTICES.md`.
- `pins.json` holds the sha256 the daw recipes pin; `check.py OUT` fails the build when a file
  differs (a changed upstream, a changed library).
- `reel.json` indexes the highlight reel (`sound-lab-reel.mp3`, rendered by daw from these
  sources and our own synthesis): each sound's start time, category, chain and sources. The
  reel is added to the release separately, because it is rendered by daw, not by this build.

The workflow [`build-sound-lab`](../../.github/workflows/build-sound-lab.yml) runs the build.
On a pull request it only builds and checks the pins. A manual run, or a pushed `sound-lab-*`
tag, publishes the release named in `sources.json`.
