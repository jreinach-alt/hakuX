#!/usr/bin/env bash
# Run every desktop capture set the pricing reads, in parallel, on this
# worktree's build: Specular, Specular_back, and the two console-run ISOs
# (ringweights, ringweights2). Tags are <prefix>spec, <prefix>back, <prefix>rw,
# <prefix>rw2 under build-linux/ring53runs/.
#
#   docs/lanes/ring53impl/runall.sh <prefix>
set -u
P="${1:?prefix}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$HERE/dc_run.py"
H=/home/justin/hakux-work/hardware/runs
L="$HERE/../../../build-linux/ring53runs"
mkdir -p "$L"
python3 "$R" "${P}spec" Specular > "$L/${P}spec.txt" 2>&1 &
python3 "$R" "${P}back" 'Specular back' > "$L/${P}back.txt" 2>&1 &
python3 "$R" "${P}rw" 'Ring weights' --iso "$H/2026-09-26-ringweights/ringweights.iso" > "$L/${P}rw.txt" 2>&1 &
python3 "$R" "${P}rw2" 'Ring weights' --iso "$H/2026-09-26-ringweights2/ringweights2.iso" > "$L/${P}rw2.txt" 2>&1 &
wait
grep -H "RUN_EXIT\|renderer\|FAILED" "$L/${P}"*.txt
