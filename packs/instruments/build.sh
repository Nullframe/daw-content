#!/usr/bin/env bash
# Builds the bundled-instruments content pack from pinned upstream sources (pack.json):
# Vitalium (DISTRHO's renamed Vital), Dexed and OB-Xf as separate VST3 plugins.
# They are GPL-3.0 programs that daw runs out of process in its plugin worker; nothing here is
# linked into daw. See README.md for licences, the source offer and what each step does.
#
#   packs/instruments/build.sh                      # everything: fetch, patch, build, index, package
#   packs/instruments/build.sh --only vitalium,dexed # a subset (a partial pack, for local testing)
#   packs/instruments/build.sh --limit-presets 20   # quick run: at most 20 presets per instrument
#   packs/instruments/build.sh --skip-index         # no daw needed (CI): daw indexes on install
#
# Output in packs/instruments/.build/ (gitignored):
#   src/<id>/        upstream checkouts at the pinned commits, with patches/<id>/*.patch applied
#   build/<id>/      build trees
#   stage/           the pack: vst3/, presets/ (or patch-files/), licenses/, source/,
#                    SOURCE-OFFER.md, NOTICES.md, content.json (not with --skip-index)
#   dist/            daw-instruments-<version>-<platform>.tar.gz (+ .sha256), the source archive
#                    daw-instruments-<version>-src.tar.gz (+ .sha256) and artifact.json
#
# DAW_PACK_BASE_URL overrides pack.json's release.base_url in the source offer and notices
# (the release workflow in Nullframe/daw-content sets it to the release being built).
#
# Then: daw pack install instruments --from packs/instruments/.build/dist/<archive>.tar.gz
#
# Upstream patches (patches/<id>/*.patch) live only in Nullframe/daw-content's copy of this folder
# (they change GPL code), which builds the published pack; see patches/README.md.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
B="${DAW_PACK_BUILD:-$here/.build}"
only=""
limit=0
jobs="$( (command -v nproc >/dev/null && nproc) || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
allow_c=""
skip_index=""
source_archive=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --only) only="$2"; shift 2 ;;
    --limit-presets) limit="$2"; shift 2 ;;
    --jobs|-j) jobs="$2"; shift 2 ;;
    --allow-tier-c) allow_c="--allow-tier-c"; shift ;;
    --skip-index|--no-index) skip_index=1; shift ;;
    --no-source-archive) source_archive=""; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown option $1 (see --help)" >&2; exit 1 ;;
  esac
done

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null || die "$1 is required: $2"; }

need git "install git"
need cmake "brew install cmake / apt-get install cmake"
need python3 "used to read pack.json"
need tar "tar"

# --- platform -------------------------------------------------------------------------------
case "$(uname -s)" in
  Darwin)
    platform=macos-universal
    # shellcheck disable=SC2034
    export CMAKE_OSX_ARCHITECTURES="arm64;x86_64"
    export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-11.0}"
    # shellcheck disable=SC2034
    cmake_platform=(-DCMAKE_OSX_ARCHITECTURES="arm64;x86_64" -DCMAKE_OSX_DEPLOYMENT_TARGET="$MACOSX_DEPLOYMENT_TARGET")
    ;;
  Linux)
    platform="linux-$(uname -m)"
    # shellcheck disable=SC2034
    cmake_platform=()
    ;;
  *) die "unsupported platform $(uname -s)" ;;
esac
# Used by the recipes (recipes/common.sh).
# shellcheck disable=SC2034
generator=()
# shellcheck disable=SC2034
command -v ninja >/dev/null && generator=(-G Ninja)

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

# A reproducible tar.gz: sorted names, fixed times and owners (GNU tar; gtar on macOS if present).
det_tar() { # out.tar.gz dir [paths...]
  local out="$1" dir="$2"; shift 2
  local t=tar
  command -v gtar >/dev/null && t=gtar
  if "$t" --version 2>/dev/null | grep -q GNU; then
    "$t" --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C "$dir" -cf - "$@" | gzip -n -9 >"$out"
  else
    echo "note: BSD tar: the archive is not byte-reproducible (brew install gnu-tar for that)" >&2
    COPYFILE_DISABLE=1 tar --uid 0 --gid 0 -C "$dir" -cf - "$@" | gzip -n -9 >"$out"
  fi
}

# --- manifest -------------------------------------------------------------------------------
manifest="$here/pack.json"
field() { python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); print(eval(sys.argv[2], {"m": m}))' "$manifest" "$1"; }
version="$(field 'm["version"]')"
all_ids="$(field '" ".join(i["id"] for i in m["instruments"])')"
ids="${only//,/ }"
[[ -n "$ids" ]] || ids="$all_ids"
for id in $ids; do [[ " $all_ids " == *" $id "* ]] || die "no instrument '$id' in pack.json ($all_ids)"; done
inst() { field "next(i for i in m['instruments'] if i['id']=='$1')$2"; }

mkdir -p "$B/src" "$B/build" "$B/dist"
stage="$B/stage"
rm -rf "$stage"
mkdir -p "$stage/vst3" "$stage/licenses" "$stage/source"

# --- fetch and patch ------------------------------------------------------------------------
# Fetches the pinned commit (shallow, with submodules) and checks it is that commit. Patches in
# patches/<id>/ are applied in name order; a marker records which, so re-runs are no-ops.
fetch() {
  local id="$1" repo_url commit src="$B/src/$1"
  repo_url="$(inst "$id" "['upstream']['repo']")"
  commit="$(inst "$id" "['upstream']['commit']")"
  local patches=()
  if compgen -G "$here/patches/$id/*.patch" >/dev/null; then patches=("$here/patches/$id/"*.patch); fi
  local want="$commit"
  for p in ${patches[@]+"${patches[@]}"}; do want="$want $(sha256 "$p")"; done
  if [[ -f "$src/.daw-pin" && "$(cat "$src/.daw-pin")" == "$want" ]]; then
    echo "$id: $commit (cached)"
    return
  fi
  log "fetch $id $repo_url @ $commit"
  rm -rf "$src"
  git init -q "$src"
  git -C "$src" remote add origin "$repo_url"
  git -C "$src" fetch -q --depth 1 origin "$commit"
  git -C "$src" -c advice.detachedHead=false checkout -q FETCH_HEAD
  [[ "$(git -C "$src" rev-parse HEAD)" == "$commit" ]] || die "$id: fetched $(git -C "$src" rev-parse HEAD), expected $commit"
  git -C "$src" submodule update -q --init --recursive --depth 1 || git -C "$src" submodule update -q --init --recursive
  for p in ${patches[@]+"${patches[@]}"}; do
    echo "$id: applying $(basename "$p")"
    git -C "$src" apply --check "$p" || die "$id: $(basename "$p") does not apply to $commit"
    git -C "$src" apply "$p"
  done
  echo "$want" >"$src/.daw-pin"
}

# --- build ----------------------------------------------------------------------------------
# Each recipes/<id>.sh defines recipe_build (SRC, OUT, JOBS and PLATFORM are exported; the
# arrays generator and cmake_platform hold CMake flags; expand them as ${a[@]+"${a[@]}"} for
# macOS's bash 3.2). Bundles are then found by name anywhere under OUT.
build() {
  local id="$1"
  export SRC="$B/src/$id" OUT="$B/build/$id" JOBS="$jobs" PLATFORM="$platform"
  log "build $id ($platform, $jobs jobs)"
  mkdir -p "$OUT"
  # shellcheck source=/dev/null
  ( source "$here/recipes/$id.sh"; recipe_build )
  local bundles=("$(inst "$id" "['bundle']")")
  while IFS= read -r b; do [[ -n "$b" ]] && bundles+=("$b"); done < <(field "'\n'.join(next(i for i in m['instruments'] if i['id']=='$id').get('extra_bundles', []))")
  for b in "${bundles[@]}"; do
    local found
    found="$(find "$OUT" -type d -name "$b" -prune 2>/dev/null | grep -v '/_deps/' | head -n 1 || true)"
    [[ -n "$found" ]] || die "$id: built, but no $b under $OUT (did the target name change? see recipes/$id.sh)"
    echo "$id: $found"
    rm -rf "$stage/vst3/$b"
    if [[ "$platform" == macos-* ]]; then ditto "$found" "$stage/vst3/$b"; else cp -R "$found" "$stage/vst3/$b"; fi
  done
}

# Licence files from the upstream tree (and its submodules), plus where it came from.
licenses() {
  local id="$1" src="$B/src/$1" dest="$stage/licenses/$1" pdir
  mkdir -p "$dest"
  # A repository of many plugins (DISTRHO-Ports): leave out the other plugins' folders.
  pdir="$(inst "$id" "['upstream'].get('plugin_dir', '')")"
  (cd "$src" && find . -maxdepth 5 -type f \( -iname 'LICENSE*' -o -iname 'LICENCE*' -o -iname 'COPYING*' -o -iname 'GPL*.txt' \) \
      -not -path './.git/*' | sort) | while IFS= read -r f; do
    if [[ -n "$pdir" && "$f" == ./ports-* && "$f" != "./$pdir/"* ]]; then continue; fi
    mkdir -p "$dest/$(dirname "$f")"
    cp "$src/$f" "$dest/$f"
  done
  [[ -n "$(ls -A "$dest")" ]] || die "$id: no licence file found in its source"
  {
    echo "$(inst "$id" "['name']") — $(inst "$id" "['license']")"
    echo "upstream: $(inst "$id" "['upstream']['repo']")"
    echo "commit:   $(inst "$id" "['upstream']['commit']") ($(inst "$id" "['upstream']['ref']"))"
    for p in "$here/patches/$id/"*.patch; do
      if [[ -f "$p" ]]; then echo "patch:    $(basename "$p") sha256 $(sha256 "$p")"; fi
    done
    echo "presets:  $(inst "$id" "['presets']['provenance']")"
    echo
    echo "Preset banks considered (pack.json presets.banks):"
    field "'\n'.join(('  [shipped]  ' if b['included'] else '  [excluded] ') + b['name'] + ': ' + ', '.join(b.get('authors', [])) + '; ' + b.get('license', '') + '. ' + b.get('reason', '') for b in next(i for i in m['instruments'] if i['id']=='$id')['presets'].get('banks', []))"
  } >"$dest/UPSTREAM.txt"
}

# Patch files a pack may ship (pack.json presets.format/dirs/require_license), relative to the
# instrument's source tree, one per line. `excluded` lists the ones the licence filter drops
# instead (the same rule as daw's index: a ` license="…"` attribute in the file, XML-unescaped,
# compared case-insensitively). Used for --skip-index packs and to keep excluded patches out of
# the source archive.
patch_files() { # id kept|excluded
  python3 - "$manifest" "$1" "$B/src/$1" "$2" <<'PY'
import html, json, os, sys
m = json.load(open(sys.argv[1]))
inst = next(i for i in m["instruments"] if i["id"] == sys.argv[2])
p, src, want = inst["presets"], sys.argv[3], sys.argv[4]
fmt = p.get("format", "none")
if fmt in ("none", "programs"):
    sys.exit(0)
req = [r.lower() for r in p.get("require_license", [])]
for d in p.get("dirs", []):
    for root, dirs, files in os.walk(os.path.join(src, d)):
        dirs.sort()
        for f in sorted(files):
            if not f.lower().endswith("." + fmt):
                continue
            path = os.path.join(root, f)
            text = open(path, "rb").read().decode("utf-8", "replace")
            lic = None
            k = text.find(' license="')
            if k >= 0:
                e = text.find('"', k + 10)
                if e >= 0:
                    lic = html.unescape(text[k + 10:e].strip()) or None
            ok = not req or (lic is not None and lic.strip().lower() in req)
            if ok == (want == "kept"):
                print(os.path.relpath(path, src))
PY
}

for id in $ids; do fetch "$id"; done
for id in $ids; do build "$id"; licenses "$id"; done

# --- the build scripts themselves, the source offer and the notices ---------------------------
cp -R "$here/build.sh" "$here/recipes" "$here/patches" "$here/pack.json" "$here/README.md" "$stage/source/"
scripts_commit="$(git -C "$repo" rev-parse HEAD 2>/dev/null || echo unknown)"
scripts_repo="$(git -C "$repo" config --get remote.origin.url 2>/dev/null || echo unknown)"
scripts_repo="${scripts_repo%.git}"
src_archive="$(field 'm["release"]["source_archive"]')"
base_url="${DAW_PACK_BASE_URL:-$(field 'm["release"]["base_url"]')}"
# The public release the pack is downloaded from (README.md, "Publishing a release").
release_repo="${base_url%%/releases/*}"
if [[ "$base_url" == *"<"* ]]; then
  echo "note: pack.json release.base_url is still a placeholder ($base_url); set the release tag (or DAW_PACK_BASE_URL) before building a pack to publish" >&2
fi
{
  echo "# Source offer"
  echo
  echo "The plugins in this pack are free software under the GNU General Public License, version 3"
  echo "or later (see licenses/). They are separate programs: daw loads them out of process and"
  echo "does not link them. No DRM, no activation."
  echo
  echo "The complete corresponding source is published next to this binary pack, from the same"
  echo "place, as \`$src_archive\` ($base_url$src_archive): each upstream tree at the commit"
  echo "below with our patches applied, the sources its build fetched, and the scripts that built"
  echo "this pack (also in source/ here)."
  echo "Dexed's tree also has its built-in cartridge zip replaced by an init-voice cartridge"
  echo "(recipes/dexed.sh), because its original DX7 banks have no clear authorship or licence."
  echo "On request, for three years from the date of this pack's release, we will provide the same"
  echo "source on a physical medium for no more than the cost of performing the distribution:"
  echo "open an issue at $release_repo."
  echo
  echo "| Instrument | Licence | Upstream | Commit | Patches |"
  echo "|---|---|---|---|---|"
  for id in $ids; do
    np=$( (compgen -G "$here/patches/$id/*.patch" || true) | wc -l | tr -d ' ')
    echo "| $(inst "$id" "['name']") | $(inst "$id" "['license']") | $(inst "$id" "['upstream']['repo']") | \`$(inst "$id" "['upstream']['commit']")\` | $np |"
  done
  echo
  echo "Built by packs/instruments/build.sh from $scripts_repo commit \`$scripts_commit\` for $platform."
} >"$stage/SOURCE-OFFER.md"

{
  echo "# Notices"
  echo
  echo "daw instruments pack $version for $platform. Three third-party synthesizers, each built from"
  echo "its official upstream source at a pinned commit as a separate VST3 plugin. daw hosts them"
  echo "out of process and does not link them."
  echo
  echo "These are **unmodified upstream builds**, with two exceptions. First, before building Dexed,"
  echo "\`recipes/dexed.sh\` replaces \`assets/builtin_pgm.zip\` (Dexed's built-in DX7 cartridges,"
  echo "compiled into the plugin) with a zip holding only \`Dexed_01.syx\`: 32 copies of Dexed's own"
  echo "INIT VOICE from its GPL source. The original banks have no per-voice authors or stated"
  echo "terms, so they are not distributed. Second, OB-Xf is patched for determinism:"
  echo "\`patches/obxf/01-seed-rng-from-rand.patch\` seeds its per-voice \"slop\" and LFO"
  echo "sample-and-hold RNGs from \`std::rand()\` instead of \`juce::Random\`'s default seed, which"
  echo "mixes in an object address and the clock. The amount and character of the variation are"
  echo "unchanged; a host that seeds \`rand()\` gets the same render every time. No other code is"
  echo "changed, and the patch ships in \`source/\` and the source archive."
  echo "On macOS, DISTRHO-Ports' meson build leaves Vitalium's library as"
  echo "\`Contents/MacOS/vitalium.dylib\` with no Info.plist, which hosts can't load, so"
  echo "\`recipes/vitalium.sh\` renames it to \`vitalium\`, adds a minimal Info.plist and ad-hoc signs"
  echo "the bundle (packaging only)."
  echo
  for id in $ids; do
    echo "## $(inst "$id" "['name']")"
    echo
    echo "- Licence: $(inst "$id" "['license']") (texts in \`licenses/$id/\`)"
    echo "- Upstream: $(inst "$id" "['upstream']['repo']")"
    echo "- Commit: \`$(inst "$id" "['upstream']['commit']")\` ($(inst "$id" "['upstream']['ref']"))"
    pd="$(inst "$id" "['upstream'].get('plugin_dir', '')")"
    [[ -z "$pd" ]] || echo "- Plugin: \`$pd\`"
    echo "- Build: \`recipes/$id.sh\` ($(sed -n '1p' "$here/recipes/$id.sh" | sed 's/^# *//'))"
    echo "- Presets: $(inst "$id" "['presets']['provenance']")"
    echo
  done
  echo "## Build"
  echo
  echo "\`packs/instruments/build.sh\` (in \`source/\`) fetches each commit with its submodules,"
  echo "checks the commit id, runs the recipe (CMake or meson, Release), and collects every"
  echo "LICENSE/COPYING file in the tree. Built by $scripts_repo commit \`$scripts_commit\`"
  echo "on $(uname -sm)${GITHUB_RUN_ID:+ (GitHub Actions run $GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID)}."
  echo
  echo "Complete corresponding source: \`$src_archive\` at $base_url$src_archive"
} >"$stage/NOTICES.md"

# --- preset index and admission (needs the daw CLI and the plugin host worker) ---------------
if [[ -z "$skip_index" ]]; then
  daw="${DAW_BIN:-$repo/target/release/daw}"
  if [[ ! -x "$daw" ]]; then
    log "build daw (cargo build --release -p daw-cli)"
    (cd "$repo" && cargo build --release -p daw-cli)
  fi
  worker="${DAW_HOST_BIN:-$repo/host/build/daw-host}"
  [[ -x "$worker" ]] || die "the plugin host worker is not built: cmake -S host -B host/build -G Ninja -DCMAKE_BUILD_TYPE=Release && cmake --build host/build (host/README.md)"
  sources=()
  for id in $ids; do sources+=(--source "$id=$B/src/$id"); done
  log "index presets and check determinism (tier A)"
  # A throwaway DAW_HOME: indexing must not depend on or touch the user's library.
  DAW_HOME="$B/home" DAW_HOST_BIN="$worker" "$daw" --json pack index --dir "$stage" \
    --manifest "$manifest" "${sources[@]}" --limit "$limit" --seed 7 $allow_c >"$B/index.json" \
    || { cat "$B/index.json" >&2; die "pack index failed (see above)"; }
  python3 - "$B/index.json" $ids <<'PY' || die "the pack is incomplete (see above)"
import json, sys
r = json.load(open(sys.argv[1]))["result"]
got = {i["id"]: i for i in r["content"]["instruments"]}
for i in got.values():
    print(f'{i["name"]:12} {i["version"]:10} tier {i["admission"]["tier"]}  presets {i["presets"]:5}  rejected {len(i["rejected_presets"])}')
missing = [x for x in sys.argv[2:] if x not in got]
if missing:
    sys.exit(f"not indexed: {', '.join(missing)}")
PY
else
  # No index here: the pack ships the licence-filtered patch files as they are, under
  # patch-files/<id>/<path in the upstream tree>, and `daw pack install` converts and checks
  # them on the user's machine (the same `pack index`, run by the installer).
  log "copy licence-filtered patch files (daw indexes them on install)"
  for id in $ids; do
    n=0
    while IFS= read -r f; do
      [[ -n "$f" ]] || continue
      mkdir -p "$stage/patch-files/$id/$(dirname "$f")"
      cp "$B/src/$id/$f" "$stage/patch-files/$id/$f"
      n=$((n + 1))
    done < <(patch_files "$id" kept)
    x="$(patch_files "$id" excluded | grep -c . || true)"
    echo "$id: $n patch files ship, $x excluded by the licence filter"
  done
fi

# --- package ---------------------------------------------------------------------------------
file="daw-instruments-$version-$platform.tar.gz"
log "package $file"
det_tar "$B/dist/$file" "$stage" .
echo "$(sha256 "$B/dist/$file")  $file" >"$B/dist/$file.sha256"
bytes=$(wc -c <"$B/dist/$file" | tr -d ' ')
python3 - "$B/dist" "$platform" "$file" "$(sha256 "$B/dist/$file")" "$bytes" <<'PY'
import json, sys
d, plat, f, sha, n = sys.argv[1:]
json.dump({plat: {"file": f, "sha256": sha, "bytes": int(n)}}, open(f"{d}/artifact-{plat}.json", "w"), indent=2)
PY

# The source tree as built: upstream trees (patched; Dexed's zip swapped), minus patch files the
# licence filter excludes (not part of any binary), plus sources the builds fetched themselves
# (CMake FetchContent/CPM under build/<id>/_deps/*-src). Staged on every run, with a per-file
# digest (source-digest-<platform>.txt) so builds on different platforms can be checked to come
# from the same source; the archive itself is skipped with --no-source-archive.
srcstage="$B/srcstage"
rm -rf "$srcstage"; mkdir -p "$srcstage/upstream"
for id in $ids; do
  (cd "$B/src" && tar --exclude .git -cf - "$id") | (cd "$srcstage/upstream" && tar -xf -)
  rm -f "$srcstage/upstream/$id/.daw-pin"
  while IFS= read -r f; do
    [[ -n "$f" ]] && rm -f "$srcstage/upstream/$id/$f"
  done < <(patch_files "$id" excluded)
  if [[ -d "$B/build/$id/_deps" ]]; then
    for d in "$B/build/$id/_deps/"*-src; do
      [[ -d "$d" ]] || continue
      mkdir -p "$srcstage/upstream/$id-fetched"
      (cd "$(dirname "$d")" && tar --exclude .git -cf - "$(basename "$d")") | (cd "$srcstage/upstream/$id-fetched" && tar -xf -)
    done
  fi
done
cp -R "$stage/source" "$srcstage/daw-pack-scripts"
cp "$stage/SOURCE-OFFER.md" "$stage/NOTICES.md" "$srcstage/"
python3 - "$srcstage/upstream" >"$B/dist/source-digest-$platform.txt" <<'PY'
import hashlib, os, sys
root = sys.argv[1]
out = []
for d, dirs, files in os.walk(root):
    for f in files:
        p = os.path.join(d, f)
        if os.path.islink(p):
            h = "link:" + os.readlink(p)
        else:
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        out.append((os.path.relpath(p, root), h))
for rel, h in sorted(out):
    print(f"{h}  {rel}")
PY
echo "source digest: $(sha256 "$B/dist/source-digest-$platform.txt") ($(wc -l <"$B/dist/source-digest-$platform.txt" | tr -d ' ') files)"
if [[ -n "$source_archive" ]]; then
  log "source archive $src_archive"
  det_tar "$B/dist/$src_archive" "$srcstage" .
  echo "$(sha256 "$B/dist/$src_archive")  $src_archive" >"$B/dist/$src_archive.sha256"
fi
log "done"
ls -l "$B/dist"
echo
echo "install:  daw pack install instruments --from $B/dist/$file"
echo "release:  upload dist/* and put artifact-$platform.json's sha256 and bytes into pack.json"
