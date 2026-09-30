# Recorded drums (CC0)

`voyager-daw library install drums-recorded-cc0` (or the name of one of its kits:
`trailer-recorded`, `orchestral-recorded`, `acoustic-recorded`) installs recorded drum and
percussion one-shots and three round-robin kits from a `drums-recorded-cc0-<date>` release. They
are built by [`build-drums-recorded`](../../.github/workflows/build-drums-recorded.yml) from the
upstream recordings pinned in [`recipes.json`](recipes.json). **No audio is committed.**

Why: synthesized drums sounded blunt in every trailer the agents made, while recorded percussion
sounded pro in the same arrangements. Most users have no sample library, so daw needs recorded
drums it may ship.

## Sources and licences

Only CC0 sources, each checked at the pinned commit (the LICENSE file) and on the publisher's page
(2026-09-30):

| Library | Author | Upstream (pinned commit) | Licence |
|---|---|---|---|
| Versilian Community Sample Library (VCSL) | Versilian Studios LLC | [sgossner/VCSL](https://github.com/sgossner/VCSL) `c1ea7bc` | CC0-1.0 (LICENSE; the README says "essentially public domain") |
| Big Rusty Drums | Karoryfer Samples | [sfzinstruments/karoryfer.big-rusty-drums](https://github.com/sfzinstruments/karoryfer.big-rusty-drums) `f07ce00` | CC0-1.0 (LICENSE) |
| Swirly Drums | Karoryfer Samples | [sfzinstruments/karoryfer.swirly-drums](https://github.com/sfzinstruments/karoryfer.swirly-drums) `c40dafe` | CC0-1.0 (`license` file) |

Karoryfer's [free-samples page](https://shop.karoryfer.com/pages/free-samples) states: "All our
free sample libraries are under a Creative Commons Zero license ... Only Marie Ork has a different
license" (Marie Ork is not used). Files come from GitHub (git and raw.githubusercontent.com), no
account needed. VCSL's Gong 2 exists only as MP3 and is not used.

The pack is CC0-1.0. `NOTICES.md` credits the sources anyway; `provenance.json` has, per file,
every upstream file mixed into it (repository, commit, path, sha256, mic gain), the processing
and the measurements.

**Gap:** there is no free, redistributable recording of a taiko or trailer-drum *ensemble*. The
closest are Big Rusty's 22- and 18-inch toms played with felt mallets (tagged `taiko-like`), the
marching and concert bass drums and the large frame drum; daw's `trailer-hybrid` pack layers them
with modal@1 bodies. SCC Taiko Drums is CC-BY-SA (ShareAlike), so it is out. A commissioned taiko
session remains the way to close the gap (docs/research/default-library-sourcing.md in daw).

## What is in it

`select.py` picks the hits from local checkouts and writes `recipes.json`: the loudest one or two
velocity layers of each stroke with all their round robins (Big Rusty: close and overhead mics
at the library's own default mix, close 100 / overhead 70; the kick adds its overhead at 0.5,
the snare its bottom mic; hats sit closer), VCSL's orchestral percussion (concert bass drums,
two timpani sets, concert and field snares, concert and tenor toms, frame drums, suspended and
clash cymbals, cymbal swells, gong, rolls) and hand and small percussion, and Swirly's marching
bass drum and hand drums.

`build.py` rebuilds every file from the pinned upstream files: mic mix, 20 Hz high-pass, L/R
balance (centred instruments), trim to the onset and the decay into the noise floor with
raised-cosine fades, a length cap per class, a transient limiter and gentle saturation for low
hits whose first peak stands far over their body (recorded drums peak 9-14 dB over their first
100 ms; commercial one-shots 2.6-6.5 dB), -1.1 dBTP, and level-matching within each round-robin
group. It measures every file and tags its character within its class (`bright`, `dark`,
`tight`, `roomy`, `punchy`, `big`); `uses` says what it suits (`trailer`, `cinematic`,
`orchestral`, `acoustic`, `launch`). The same inputs give the same bytes (pinned numpy, scipy,
soundfile).

`curation.json` holds the kits and the drops. Drops come from daw's own one-shot checks, run over
the built files by `check_with_daw.py` (the checks every factory pack passes: hits, truncation,
DC, peaks, plus the weight, harshness, tonality, partial, tail and cut flags): double hits and
rattles, takes too tonal for their class, a floor tom with a weak transient, crash takes with a
whistling partial, bass drums with no sub. What stays flagged is by nature (rolls have many hits;
suspended cymbals, open hats and the undamped kick ring long; anvil, brake drums and log drums are
tonal).

Kits (every pad a round-robin group):

- `kit/trailer-recorded@1`: marching bass drum, 22/18/15-inch mallet toms, rimshot snare,
  slapstick, claves, woodblock, large frame drum, cymbal swell, clash cymbals, low timpani,
  concert bass drum.
- `kit/orchestral-recorded@1`: concert bass drum, concert snare, three timpani, clash and
  suspended cymbals, swell, tambourine, triangle, woodblock, slapstick, tam-tam.
- `kit/acoustic-recorded@1`: 24-inch kick, 14-inch snare and side stick, 14-inch hats, 14/15/18
  toms, 17-inch crash, 22-inch ride, claps, tambourine.

## Rebuilding and publishing

```sh
pip install numpy==2.4.6 scipy==1.17.1 soundfile==0.14.0
python3 build.py OUT --cache .cache            # fetches the pinned upstream files
python3 check_with_daw.py OUT --daw voyager-daw  # optional: daw's checks over the result
```

To publish, run the workflow (Actions → build-drums-recorded → Run workflow) or push a tag
`drums-recorded-cc0-<date>`. It builds, checks every file against `SHA256SUMS`, and creates the
release with every WAV, `SHA256SUMS`, `NOTICES.md`, `provenance.json` and
`drums-recorded-cc0.json`, the manifest daw pins as `content/recorded/drums-recorded-cc0.json`.
Published files are never replaced under the same tag once daw pins them.
