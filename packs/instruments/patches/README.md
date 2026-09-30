# Patches to upstream sources

`build.sh` applies `patches/<instrument id>/*.patch` (in name order, with `git apply`) to the
pinned upstream checkout before building, and records each patch's sha256 in the pack's
`licenses/<id>/UPSTREAM.txt` and `SOURCE-OFFER.md`. Patched sources are what the source archive
ships.

One today: `obxf/01-seed-rng-from-rand.patch` (from pack 2026.09.1), which seeds OB-Xf's
voice "slop" and LFO sample-and-hold RNGs from `std::rand()` so the worker's shim makes it
bit-identical across fresh workers. The policy (design §8.5, §11.3):

- **Determinism**: prefer the worker's clock/RNG shim, which already makes Dexed bit-identical
  across fresh workers with the same seed. Add a seed patch only when the pack's
  admission check (`daw pack index`, run by `build.sh`; `daw pack verify instruments`) reports an
  instrument as not tier A. Name it `NN-seed-<what>.patch` and keep it minimal: route the
  synth's internal randomness through a seed the host can set (for example read at
  construction from an environment variable; the worker would then set it per take, a small
  change in `host/`).
- **Patch as data**: Vitalium's patches are already JSON (`.vital`) and load with
  `--preset FILE` without patches. Add a patch only when
  a synth's state can't be produced from its own patch files.
- Keep patches small, one concern each, with a comment header saying why. Never remove
  licence notices or add DRM.
