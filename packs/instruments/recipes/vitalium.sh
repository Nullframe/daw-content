# Vitalium: DISTRHO-Ports' build of Vital (https://github.com/DISTRHO/DISTRHO-Ports,
# ports-juce6.0/vitalium; Vital by Matt Tytel, GPL-3.0-or-later). "Vital" is a trademark, so we
# ship DISTRHO's renamed build ("Vitalium", its own plugin ids) rather than renaming Vital
# ourselves; build_index refuses a bundle whose plugin name is not "Vitalium". Its presets are
# JSON (.vital) and load with --preset FILE.vital. Vital's factory presets are not free and are
# not shipped.
# Needs meson and ninja (brew install meson ninja / apt-get install meson ninja-build), fftw3 and,
# on Linux, the X11/freetype/ALSA/GL dev packages listed in README.md. Not -Dlinux-headless:
# DISTRHO-Ports builds only LV2 plugins with it.
recipe_build() {
  command -v meson >/dev/null || { echo "meson is required for vitalium" >&2; return 1; }
  local opts=(--buildtype release -Dplugins=vitalium -Dbuild-juce60-only=true -Dbuild-lv2=false
              -Dbuild-vst2=false -Dbuild-vst3=true)
  [[ "$PLATFORM" == macos-* ]] && opts+=(-Dbuild-universal=true)
  if [[ -f "$OUT/build.ninja" ]]; then
    meson setup --reconfigure "$OUT" "$SRC" "${opts[@]}"
  else
    meson setup "$OUT" "$SRC" "${opts[@]}"
  fi
  ninja -C "$OUT" -j "$JOBS"
  [[ "$PLATFORM" == macos-* ]] && vitalium_macos_bundle
  return 0
}

# DISTRHO-Ports' meson build leaves the macOS bundle as vitalium.vst3/Contents/MacOS/vitalium.dylib
# with no Info.plist, which CFBundle (and so JUCE's and the VST3 SDK's hosting) can't load: the
# executable must be named after the bundle. Packaging only: the binary is renamed, a minimal
# Info.plist is added (version from its JucePluginCharacteristics.h) and the bundle is ad-hoc
# signed again. The code is untouched.
vitalium_macos_bundle() {
  local b
  b="$(find "$OUT" -type d -name vitalium.vst3 -prune | head -n 1)"
  [[ -n "$b" ]] || { echo "vitalium: no vitalium.vst3 under $OUT" >&2; return 1; }
  if [[ -f "$b/Contents/MacOS/vitalium.dylib" ]]; then
    mv "$b/Contents/MacOS/vitalium.dylib" "$b/Contents/MacOS/vitalium"
  fi
  [[ -f "$b/Contents/MacOS/vitalium" ]] || { echo "vitalium: no binary in $b/Contents/MacOS" >&2; return 1; }
  cat >"$b/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key><string>English</string>
  <key>CFBundleExecutable</key><string>vitalium</string>
  <key>CFBundleIdentifier</key><string>studio.kx.distrho.vitalium</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleName</key><string>vitalium</string>
  <key>CFBundlePackageType</key><string>BNDL</string>
  <key>CFBundleSignature</key><string>????</string>
  <key>CFBundleShortVersionString</key><string>1.0.6</string>
  <key>CFBundleVersion</key><string>1.0.6</string>
</dict>
</plist>
PLIST
  printf 'BNDL????' >"$b/Contents/PkgInfo"
  codesign --force --sign - "$b"
}
