#!/bin/bash
# Build rewrite_edges.c against a prim_rewrite.c and run it.
#   rewrite_edges.sh [PRIM_REWRITE_C]   (default: the worktree's own)
# Headers always come from the enclosing worktree, so an older
# prim_rewrite.c (git show REF:hw/.../prim_rewrite.c > f) can be diffed
# against the current one.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
src=${1:-$root/hw/xbox/nv2a/pgraph/prim_rewrite.c}
tmp=$(mktemp -d "$here/.build.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/qemu"
printf '#include <assert.h>\n#include <stdbool.h>\n#include <stdint.h>\n#include <glib.h>\n' \
    > "$tmp/qemu/osdep.h"
cp "$src" "$tmp/prim_rewrite.c"
# shellcheck disable=SC2046
gcc -Wall -Wextra -Werror -Wno-unused-parameter -std=gnu11 \
    -I"$tmp" -I"$root/hw/xbox/nv2a/pgraph" -I"$root/include" -I"$root" \
    $(pkg-config --cflags glib-2.0) \
    "$here/rewrite_edges.c" "$tmp/prim_rewrite.c" \
    $(pkg-config --libs glib-2.0) -o "$tmp/rewrite_edges"
"$tmp/rewrite_edges"
