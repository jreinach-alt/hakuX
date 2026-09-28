#!/usr/bin/env bash
#   gen/run_gen.sh <variant> <noopt|opt> [--no-opt-flag]  -> $S/out-<variant>-<gl>/
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
S="$(realpath -m "${OUT:-$REPO/.scratch}")"
VAR="$1"; GL="$2"; shift 2
[ -d "$S/vshinc" ] || python3 "$HERE/stage_vshinc.py" "$S/vshinc" >/dev/null
bash "$HERE/build_gen.sh" "$VAR" "$GL" >/dev/null
O="$S/out-$VAR-$GL${1:+-flag}"
rm -rf "$O"
"$S/gen-$VAR-$GL/gen" "$O" "$S/vshinc" "$@"
