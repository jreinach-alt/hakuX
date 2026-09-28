#!/usr/bin/env bash
#   gen/run_gen.sh <variant> <noopt|opt> <outdir> [--optimize-size]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
S="$(realpath -m "${OUT:-$REPO/.scratch}")"
VAR="$1"; GL="$2"; O="$3"; shift 3
[ -d "$S/vshinc" ] || python3 "$HERE/stage_vshinc.py" "$S/vshinc" >/dev/null
bash "$HERE/build_gen.sh" "$VAR" "$GL" >/dev/null
rm -rf "$O"
"$S/gen-$VAR-$GL/gen" "$O" "$S/vshinc" "$@"
