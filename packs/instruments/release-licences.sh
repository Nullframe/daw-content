#!/usr/bin/env bash
# Release-side GPL source obligations for the instruments pack. Given the dist folder (the
# platform archives, the -src archive and pack.json's version), writes next to them, as release
# assets:
#
#   LICENSE-<id>.txt     each instrument's own GPL-3 text (its top-level LICENSE, or the
#                        GPL-3.0.txt build.sh adds for a tree without one, as DISTRHO-Ports)
#   licenses.tar.gz      every licence file collected from each upstream tree and its submodules
#   SOURCE-OFFER.md      where the corresponding source is and the written offer
#
# and then fails unless the release would carry, for every instrument in pack.json: its licence
# text, the -src archive holding its upstream tree (upstream/<id>/), our patches for it and the
# build scripts. The build and release jobs of .github/workflows/build-instruments.yml run it.
#
#   packs/instruments/release-licences.sh DIST_DIR
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
dist="${1:?usage: release-licences.sh DIST_DIR}"
die() { echo "release-licences: $*" >&2; exit 1; }

version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$here/pack.json")"
ids="$(python3 -c 'import json,sys; print(" ".join(i["id"] for i in json.load(open(sys.argv[1]))["instruments"]))' "$here/pack.json")"
src="$dist/daw-instruments-$version-src.tar.gz"
[[ -f "$src" ]] || die "no source archive $src: every release must carry the complete corresponding source"
bin="$(ls "$dist"/daw-instruments-"$version"-linux-x86_64.tar.gz "$dist"/daw-instruments-"$version"-*.tar.gz 2>/dev/null | grep -v -- '-src\.tar\.gz$' | head -n 1)"
[[ -n "$bin" ]] || die "no platform archive in $dist"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
tar -xzf "$bin" -C "$work" ./licenses ./NOTICES.md ./SOURCE-OFFER.md
for id in $ids; do
  d="$work/licenses/$id"
  [[ -d "$d" ]] || die "$id: no licenses/$id in $(basename "$bin")"
  # The instrument's own GPL-3 text: a top-level file in licenses/<id>/ (its LICENSE, or the
  # GPL-3.0.txt build.sh adds when the tree has none), never one from libs/.
  main=""
  while IFS= read -r f; do
    if grep -q 'Version 3, 29 June 2007' "$f"; then main="$f"; break; fi
  done < <(find "$d" -maxdepth 1 -type f -print0 | xargs -0 grep -lE '^[[:space:]]*GNU GENERAL PUBLIC LICENSE[[:space:]]*$' | sort || true)
  [[ -n "$main" ]] || die "$id: no GPL-3 text at the top of licenses/$id (build.sh adds licence-texts/GPL-3.0.txt when the tree has none)"
  cp "$main" "$dist/LICENSE-$id.txt"
  echo "LICENSE-$id.txt <- licenses/$id/${main#"$d"/}"
done
tar -C "$work" --sort=name --owner=0 --group=0 --numeric-owner --mtime='2000-01-01 00:00Z' \
  -cf - licenses | gzip -n >"$dist/licenses.tar.gz"
cp "$work/SOURCE-OFFER.md" "$dist/SOURCE-OFFER.md"
grep -q "daw-instruments-$version-src.tar.gz" "$work/NOTICES.md" || die "NOTICES.md doesn't say where the source is"

# The source archive: every upstream tree, our patches and the build scripts.
listing="$work/src.txt"
tar -tzf "$src" >"$listing"
for f in ./daw-pack-scripts/build.sh ./daw-pack-scripts/pack.json ./SOURCE-OFFER.md ./NOTICES.md; do
  grep -qxF "$f" "$listing" || die "$(basename "$src") has no $f"
done
for id in $ids; do
  grep -q "^\./upstream/$id/" "$listing" || die "$(basename "$src") has no upstream/$id/"
  grep -qxF "./daw-pack-scripts/recipes/$id.sh" "$listing" || die "$(basename "$src") has no recipes/$id.sh"
  if [[ -d "$here/patches/$id" ]]; then
    for p in "$here/patches/$id"/*.patch; do
      grep -qxF "./daw-pack-scripts/patches/$id/$(basename "$p")" "$listing" \
        || die "$(basename "$src") is missing our patch $id/$(basename "$p")"
    done
  fi
done
echo "release-licences: source and licences complete for $ids ($version)"
