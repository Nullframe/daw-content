# Vitalium: DISTRHO-Ports' build of Vital (https://github.com/DISTRHO/DISTRHO-Ports,
# ports-juce6.0/vitalium; Vital by Matt Tytel, GPL-3.0-or-later). "Vital" is a trademark, so we
# ship DISTRHO's renamed build ("Vitalium", its own plugin ids) rather than renaming Vital
# ourselves; build_index refuses a bundle whose plugin name is not "Vitalium". Its presets are
# JSON (.vital) and load with --preset FILE.vital. Vital's factory presets are not free and are
# not shipped.
# Needs meson and ninja (brew install meson ninja / apt-get install meson ninja-build) and, on
# Linux, the X11/freetype/ALSA dev packages listed in host/README.md.
recipe_build() {
  command -v meson >/dev/null || { echo "meson is required for vitalium" >&2; return 1; }
  local opts=(--buildtype release -Dplugins=vitalium -Dbuild-juce60-only=true -Dbuild-lv2=false
              -Dbuild-vst2=false -Dbuild-vst3=true)
  [[ "$PLATFORM" == linux-* ]] && opts+=(-Dlinux-headless=true)
  [[ "$PLATFORM" == macos-* ]] && opts+=(-Dbuild-universal=true)
  if [[ -f "$OUT/build.ninja" ]]; then
    meson setup --reconfigure "$OUT" "$SRC" "${opts[@]}"
  else
    meson setup "$OUT" "$SRC" "${opts[@]}"
  fi
  ninja -C "$OUT" -j "$JOBS"
}
