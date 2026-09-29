#!/usr/bin/env bash
#   run_lt_check.sh [millions=50]  -- build and run lt_check.c, then every mutant
# Exit 0 iff the new forms match the old on every input AND every mutant is caught.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$(realpath -m "${OUT:-$HERE/../../../.scratch}")"
mkdir -p "$S"
gcc -O2 -fwrapv -o "$S/lt_check" "$HERE/lt_check.c"
"$S/lt_check" "${1:-50}"
fail=0
for n in 1 2 3 4 5 6 7 8 9 10; do
    gcc -O2 -fwrapv -DMUT=$n -o "$S/lt_check_mut$n" "$HERE/lt_check.c"
    if "$S/lt_check_mut$n" 1 > "$S/lt_mut$n.out"; then
        echo "FALSIFIER FAILED: mutant $n passed"; fail=1
    else
        echo "mutant $n caught: $(grep -v '  0 mismatches' "$S/lt_mut$n.out" | grep -v '^MISMATCH' | tr '\n' ';')"
    fi
done
exit $fail
