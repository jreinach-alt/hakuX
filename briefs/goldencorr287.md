# #287: TexFmt_R6G5B5's golden is the outlier; correct or annotate it so 134,902 phantom px leave the score

Lane: goldencorr287        Issue: #287 (component harness; Texture format / TexFmt_R6G5B5)
Base: origin/master @ d709a8d1fa (rebase to the tip before you register anything).
Files: docs/lanes/goldencorr287/**, docs/testing/predictions/goldencorr287-*.json
       (the file that holds a golden or a golden override is NOT named here: find it first,
       then ask the board for it with a board-request naming the exact path; do not guess.)
Needs device: no. Needs NDK: no. Desktop reading of files on disk.

## The defect
Our TexFmt_R6G5B5 output is byte-identical to the console capture (gap list B,
docs/testing/nv2a-hardware-gap-list.md; console set K under hardware/runs/2026-09-19-calib), yet
the scoreboard counts 134,902 px against us because the golden is the outlier. score_sweep.py
already documents that this test "was chased for hours" as an emulator defect (line 22): read
that comment first, it is the history of this exact capture.

## Read first; the claim is the issue's, verify it
1. Re-derive "byte-identical to the console": compare our capture (a scored run, not a claim from
   the issue) to the K capture and to the golden. Region, not point samples. State the three
   pairwise diffs and a pixel count for each. If ours != console, STOP and report that on #287;
   the issue is then wrong and this is a renderer defect, not a data fix.
2. Find how the harness represents a golden and any existing correction/annotation mechanism
   (grep score_sweep.py, scoreboard.py, nv2a_index.json, docs/testing/*golden*). Prefer an
   existing mechanism to a new one. scoreboard.py is lane.sweepcover's and score_sweep.py is
   lane.toolsmith's: do not edit either; if the fix needs one, say which lines and ask.
3. Check other goldens for the same shape only to the extent one query answers it (goldens where
   console == ours != golden); list them on the issue, do not fix them here.

## Falsifier
If the golden were NOT the outlier, replacing it with the console capture would not move
R6G5B5 to exact, and other Texture format captures that match their goldens today would be
unaffected either way. Register both: R6G5B5 -> exact against the corrected reference; every
other Texture format capture unchanged.

## Done when
R6G5B5 scores exact (or is recorded as a known-bad golden by the harness's own mechanism, void and
not counted as a residual), no other row moves, the PR states which mechanism was used and why,
docs/lanes/goldencorr287/NOTES.md lists any sibling goldens found, and the issue is answered.
This is scoring/data work: no hw/ edit.
