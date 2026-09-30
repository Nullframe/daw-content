# Shared by the recipes: configure and build one CMake target, falling back to the default
# target when the named one does not exist (upstreams rename targets between releases; the
# bundle check in build.sh catches a build that produced nothing).
# generator and cmake_platform come from build.sh.
# shellcheck disable=SC2154
cmake_build() { # target [extra cmake -D flags...]
  local target="$1"; shift
  cmake -S "$SRC" -B "$OUT" ${generator[@]+"${generator[@]}"} -DCMAKE_BUILD_TYPE=Release \
    ${cmake_platform[@]+"${cmake_platform[@]}"} "$@"
  if ! cmake --build "$OUT" --config Release --parallel "$JOBS" --target "$target"; then
    echo "note: target $target failed or does not exist; building the default target" >&2
    cmake --build "$OUT" --config Release --parallel "$JOBS"
  fi
}
