#!/usr/bin/env bash
# Run whole suites on this worktree's desktop build, four at a time, as
# build-linux/ring53runs/<prefix>-<suite dir>. Used to price the guards: run
# once on the ring build and once with the ring forced off, then pxprice.py.
#
#   docs/lanes/ring53impl/runsuites.sh <prefix> 'Suite one' 'Suite two' ...
set -u
P="${1:?prefix}"; shift
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
L="$HERE/../../../build-linux/ring53runs"
mkdir -p "$L"
n=0
for s in "$@"; do
    t="${P}-${s// /_}"
    python3 "$HERE/dc_run.py" "$t" "$s" > "$L/$t.txt" 2>&1 &
    n=$((n + 1))
    if [ $((n % 4)) -eq 0 ]; then wait; fi
done
wait
for s in "$@"; do
    t="${P}-${s// /_}"
    printf '%-40s %s\n' "$t" "$(grep -c '^  Completed' "$L/$t.txt") completed, $(grep RUN_EXIT "$L/$t.txt")"
done
