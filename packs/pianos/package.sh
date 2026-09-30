#!/bin/sh
# Build a sampled instrument's release archive and its content/instruments/<name>/instrument.json
# from the official upstream archive (see package.py). Reproducible: the upstream archive is
# pinned by sha256, the Python packages are pinned, and the output is byte-identical for the
# same input. Needs python3 (3.10+) and network access; nothing is installed outside WORK_DIR.
#
#   scripts/instruments/package.sh salamander-grand /tmp/piano-work /tmp/piano-out
#   scripts/instruments/package.sh upright-kw      /tmp/piano-work /tmp/piano-out
#
# WORK_DIR keeps the upstream download (~740 MB for the grand) and a venv; OUT_DIR gets
# <name>-v1.tar, <name>-v1.tar.sha256 and <name>-report.json. Upload the .tar to the
# Nullframe/daw-content release named in content/instruments/release.json.
set -eu
name=${1:?usage: package.sh salamander-grand|upright-kw WORK_DIR OUT_DIR}
work=${2:?usage: package.sh NAME WORK_DIR OUT_DIR}
out=${3:?usage: package.sh NAME WORK_DIR OUT_DIR}
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$work" "$out"
venv="$work/venv"
if [ ! -x "$venv/bin/python" ]; then
  python3 -m venv "$venv"
  "$venv/bin/pip" install --quiet --disable-pip-version-check \
    numpy==2.4.6 soundfile==0.14.0 py7zr==1.1.3
fi
exec "$venv/bin/python" "$here/package.py" "$name" "$work" "$out"
