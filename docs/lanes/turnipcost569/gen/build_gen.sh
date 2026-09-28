#!/usr/bin/env bash
#
#   gen/build_gen.sh <variant> <glslang: noopt|opt>   -> $S/gen-<variant>-<glslang>/gen
#
# Carves hakuX's GLSL generators (carve_all.py), applies the variant's edit to
# the CARVED COPIES only (variants/<variant>.py; "base" edits nothing), and
# links them with glslang built as the device ships it (noopt) or with the
# SPIRV-Tools optimizer (opt). The repo's sources are never touched.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
S="$(realpath -m "${OUT:-$REPO/.scratch}")"
VAR="${1:?variant}"; GL="${2:?noopt|opt}"
B="$S/gen-$VAR-$GL"
GLSL="$REPO/hw/xbox/nv2a/pgraph/glsl"
rm -rf "$B"; mkdir -p "$B/src"

for f in vsh.c vsh-ff.c vsh-prog.c geom.c psh.c common.c; do
    python3 "$HERE/carve_all.py" "$GLSL/$f" -o "$B/src/$f" 2>/dev/null
done
if [ "$VAR" != base ]; then
    python3 "$HERE/variants/$VAR.py" "$B/src"
fi

# vk/glsl.c's resource limits, verbatim.
python3 - "$REPO/hw/xbox/nv2a/pgraph/vk/glsl.c" "$B/src/resource_limits.inc" <<'EOF'
import sys, re
t = open(sys.argv[1]).read()
i = t.index("static const glslang_resource_t")
j = t.index("} };", i) + 4
open(sys.argv[2], "w").write(t[i:j] + "\n")
EOF

GI="$S/glslang-$GL/install"
LIBS="-lglslang -lMachineIndependent -lGenericCodeGen -lSPIRV -lOSDependent"
[ "$GL" = opt ] && LIBS="$LIBS -lSPIRV-Tools-opt -lSPIRV-Tools"
INC="-I$REPO/docs/testing/psh_differ/shim -I$REPO/include -I$REPO -I$GLSL -I$B/src -I$GI/include"
CF="-std=gnu11 -O1 -g -w $(pkg-config --cflags glib-2.0)"
objs=()
for f in "$B"/src/*.c "$HERE/gen.c"; do
    o="$B/$(basename "${f%.c}").o"
    gcc $CF $INC -c -o "$o" "$f"
    objs+=("$o")
done
g++ -o "$B/gen" "${objs[@]}" -L"$GI/lib" $LIBS $(pkg-config --libs glib-2.0) -lm -lpthread
echo "GEN_OK $B/gen"
