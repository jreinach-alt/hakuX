#!/usr/bin/env bash
# Build vshinfo.c against this tree's glsl/vsh.h (psh_differ's shim stands in for
# a configured QEMU build) and write vshlayout.json for keys_coverage.py.
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
R="$H/../../../.."
gcc -std=gnu11 -O0 -g -Wno-all \
    -I"$R/docs/testing/psh_differ/shim" -I"$R/include" -I"$R" \
    -I"$R/hw/xbox/nv2a/pgraph/glsl" -I"$R/docs/testing/psh_differ" \
    $(pkg-config --cflags glib-2.0) \
    -o "$H/build/vshinfo" "$H/vshinfo.c"
"$H/build/vshinfo" > "$H/vshlayout.json"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('vshlayout ok, VshState', d['size'])" "$H/vshlayout.json"
