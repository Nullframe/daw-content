# daw-content

Downloadable third-party content for [`daw`](https://nullframe.ai). This repo contains no daw source code.

daw fetches these files on first use (`daw library-sync`) and checks each one against a pinned sha256. They are published as **GitHub release assets**. The repo itself only holds this README and the licence notices.

| Asset | Upstream | Licence |
|---|---|---|
| Vitalium, Dexed, OB-Xf plugin builds (+ matching source archives) | see `NOTICES.md` | GPL-3.0-or-later |
| OB-Xf presets (487, from 13 named authors) | OB-Xf | CC0-1.0 |
| Spleeter 4-stem model, converted for daw's runtime | deezer/spleeter | MIT |
| Basic Pitch model | spotify/basic-pitch | Apache-2.0 |

Each release lists its exact upstream versions, conversion scripts and checksums. The source for every GPL binary is attached to the same release as the binary.
