# OB-Xf (https://github.com/surge-synthesizer/OB-Xf, GPL-3.0): CMake + JUCE. Its factory presets
# are the .fxp files under assets/installer/ that declare a CC0 licence (pack.json,
# require_license), converted by daw pack index. OB-Xf's
# "voice variation" (analog-style per-voice drift) draws from rand()/random_device, which the
# worker shim seeds; if the admission check ever finds it not bit-identical, add a seed patch in patches/obxf/.
# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
recipe_build() {
  cmake_build OB-Xf_VST3
}
