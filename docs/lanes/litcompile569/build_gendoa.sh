#!/usr/bin/env bash
#
#   build_gendoa.sh <tree> <outbin>
#
# Builds gendoa.c against the GLSL generators of <tree> (a checkout, or a
# `git archive` of hw/xbox/nv2a, include, ui and docs/testing/psh_differ),
# carved with lane.turnipcost569's gen/carve_all.py and linked with its
# device-configured glslang ($S/glslang-noopt, as gen/build_gen.sh does).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
S="$(realpath -m "${OUT:-$REPO/.scratch/tc}")"
T="$(realpath "${1:?tree}")"; BIN="$(realpath -m "${2:?outbin}")"
B="$BIN.d"
GLSL="$T/hw/xbox/nv2a/pgraph/glsl"
rm -rf "$B"; mkdir -p "$B/src"
for f in vsh.c vsh-ff.c vsh-prog.c geom.c psh.c common.c; do
    python3 "$REPO/docs/lanes/turnipcost569/gen/carve_all.py" "$GLSL/$f" -o "$B/src/$f" 2>/dev/null
done
python3 - "$T/hw/xbox/nv2a/pgraph/vk/glsl.c" "$B/src/resource_limits.inc" <<'EOF'
import sys
t = open(sys.argv[1]).read()
i = t.index("static const glslang_resource_t")
j = t.index("} };", i) + 4
open(sys.argv[2], "w").write(t[i:j] + "\n")
EOF
GI="$S/glslang-noopt/install"
LIBS="-lglslang -lMachineIndependent -lGenericCodeGen -lSPIRV -lOSDependent"
# XXH3 (util/fast-hash.c's) from Mesa's bundled xxhash: qemu/xxhash.h has none.
mkdir -p "$B/xxh"; cp "$S/mesa/src/util/xxhash.h" "$B/xxh/"
INC="-I$T/docs/testing/psh_differ/shim -I$T/include -I$T -I$GLSL -I$B/src -I$GI/include -I$B/xxh"
CF="-std=gnu11 -O1 -g -w $(pkg-config --cflags glib-2.0)"
objs=()
for f in "$B"/src/*.c "$HERE/gendoa.c"; do
    o="$B/$(basename "${f%.c}").o"
    gcc $CF $INC -c -o "$o" "$f"
    objs+=("$o")
done
g++ -o "$BIN" "${objs[@]}" -L"$GI/lib" $LIBS $(pkg-config --libs glib-2.0) -lm -lpthread
echo "GENDOA_OK $BIN"
