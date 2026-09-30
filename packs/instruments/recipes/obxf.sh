# OB-Xf (https://github.com/surge-synthesizer/OB-Xf, GPL-3.0): CMake + JUCE. Its factory presets
# are the .fxp files under assets/installer/ that declare a CC0 licence (pack.json,
# require_license), converted by daw pack index. OB-Xf's
# "voice variation" (analog-style per-voice drift) and LFO sample-and-hold used juce::Random's
# address- and clock-based default seed, which the worker shim can't pin, so OB-Xf rendered
# differently in every fresh worker (tier C). patches/obxf/01-seed-rng-from-rand.patch seeds
# them from std::rand(), which the shim does pin (tier A from pack 2026.09.1).
# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
recipe_build() {
  cmake_build OB-Xf_VST3
}
