#!/usr/bin/env bash
#   gen/run_lta3_check.sh [millions]  -- build and run lta3_check.c
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$(realpath -m "${OUT:-$HERE/../../../../.scratch}")"
gcc -O2 -fwrapv -o "$S/lta3_check" "$HERE/lta3_check.c"
"$S/lta3_check" "${1:-50}"
# the falsifier: a one-constant mutant of the new form must be caught
gcc -O2 -fwrapv -DMUTANT_BIAS=3 -o "$S/lta3_check_mutant" "$HERE/lta3_check.c"
if "$S/lta3_check_mutant" 1 > "$S/lta3_mutant.out"; then
    echo "FALSIFIER FAILED: the mutant passed"; exit 1
fi
echo "mutant caught: $(tail -1 "$S/lta3_mutant.out")"
