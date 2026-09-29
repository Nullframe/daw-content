# Dexed (https://github.com/asb2m10/dexed, GPL-3.0): CMake + JUCE (a submodule).
# No DX7 cartridges ship (pack.json, presets.banks): Dexed's built-in banks (Dexed_01 and
# SynprezFM_01-32, compiled into the plugin from assets/builtin_pgm.zip) are voices from DX7
# SysEx archives with unknown authors and no stated terms. So before building we replace that
# zip with one holding only Dexed_01.syx: 32 copies of Dexed's own INIT VOICE (the init_voice
# table in Source/PluginData.cpp, packed as a DX7 32-voice bulk dump). Dexed needs a
# Dexed_01.syx in the zip at startup; nothing else in it is required. The source archive ships
# this modified tree, so it matches the binary.
# The host spike measured Dexed bit-identical across renders without help (tier B at least);
# the admission check confirms tier A with the shim.
# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

dexed_init_cartridge() { # out.zip
  python3 - "$1" <<'PY'
import sys, zipfile
# Dexed's init voice, unpacked (155 bytes): 6 operators x 21, then pitch EG, algorithm, LFO, name.
op = [99, 99, 99, 99, 99, 99, 99, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 7]
op1 = op[:16] + [99] + op[17:]  # operator 1 (last in the table) at full output
v = op * 5 + op1 + [99, 99, 99, 99, 50, 50, 50, 50, 0, 0, 1, 35, 0, 0, 0, 1, 0, 3, 24] + list(b"INIT VOICE")
assert len(v) == 155
def pack(v):  # Cartridge::packProgram in Dexed's Source/PluginData.cpp (all operators on)
    b = [0] * 128
    for o in range(6):
        u, p = o * 21, o * 17
        b[p:p + 11] = v[u:u + 11]
        b[p + 11] = (v[u + 11] & 3) | ((v[u + 12] & 3) << 2)
        b[p + 12] = (v[u + 13] & 7) | ((v[u + 20] & 15) << 3)
        b[p + 13] = (v[u + 14] & 3) | ((v[u + 15] & 7) << 2)
        b[p + 14] = v[u + 16]
        b[p + 15] = (v[u + 17] & 1) | ((v[u + 18] & 31) << 1)
        b[p + 16] = v[u + 19]
    b[102:111] = v[126:135]
    b[111] = (v[135] & 7) | ((v[136] & 1) << 3)
    b[112:116] = v[137:141]
    b[116] = (v[141] & 1) | ((v[142] & 7) << 1) | ((v[143] & 7) << 4)
    b[117] = v[144]
    b[118:128] = v[145:155]
    return b
data = pack(v) * 32
syx = bytes([0xF0, 0x43, 0x00, 0x09, 0x20, 0x00] + data + [(-sum(data)) & 0x7F, 0xF7])
assert len(syx) == 4104
with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(zipfile.ZipInfo("Dexed_01.syx", date_time=(2014, 1, 19, 0, 0, 0)), syx)
PY
}

recipe_build() {
  dexed_init_cartridge "$SRC/assets/builtin_pgm.zip"
  cmake_build Dexed_VST3
}
