#!/bin/bash
# The five Nova runs of 2026-09-27 (NOTES section 15): gfps, gaps, crashes.
cd "$(dirname "$0")"
DOA="0-0-x-1790527182-flip474-1639694 0-0-x-1790527188-flip474-1640231 0-0-x-1790527190-flip474-1640480"
for r in $DOA; do
  python3 lockread.py --from 151 --to 288 "$r"
done
python3 lockread.py --from 299 --to 420 0-0-x-1790530526-flip474-2801414
python3 lockread.py --from 255 --to 411 0-0-x-1790530526-flip474-2807172
for r in $DOA; do
  python3 crashcheck.py "$r"
  python3 tailcheck.py "$r"
done
