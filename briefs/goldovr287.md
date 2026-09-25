# #287 data half: commit the TexFmt_R6G5B5 override PNG and its README row

Lane: goldovr287           Issue: #287 (harness; Texture format / TexFmt_R6G5B5)
Base: origin/master @ b07ecc56fc (rebase to the tip first).
Files: docs/testing/golden_overrides/Texture_format/TexFmt_R6G5B5.png,
       docs/testing/golden_overrides/README.md, docs/lanes/goldovr287/**
       (list of paths is literal; golden_overrides/** was granted by the host, board wave 206.)
Needs device: no. Needs NDK: no. Desktop file work.

## Why
lane.goldencorr287's PR #300 (folded b07ecc56fc) proved #287: our TexFmt_R6G5B5 output is
byte-identical to console set K (0 px), and the golden differs from both by the same 134,902 px
(it comes from a suite build that prints `C: 0`; ours and three console runs print `C: 1`).
Its analysis is in docs/lanes/goldencorr287/NOTES.md (read section on the chosen mechanism and
falsify.sh). The data half was granted but did not land before the fold, and its branch is gone.

## Do
1. Copy console set K's TexFmt_R6G5B5 capture (under hardware/runs/2026-09-19-calib; find it via
   docs/lanes/goldencorr287/find_captures.py) byte-for-byte to
   docs/testing/golden_overrides/Texture_format/TexFmt_R6G5B5.png. Verify sha256 is
   07dedad9ac60aa7c36f2791bf877311f66779359912f239bb7815a704ea385f8; if it is not, stop and say so.
2. Write docs/testing/golden_overrides/README.md: one provenance row per override (suite, test,
   source run, sha256, why, the issue). Say it is inert until the scorer's ordered golden-root
   hook (lane.toolsmith defect 17) lands, and that the key is suite/test, not test name alone
   (Texture_render_target has same-named tests; see NOTES).
3. Run docs/lanes/goldencorr287/falsify.sh against the committed file if it still runs on master.

## Falsifier
The offline re-score in falsify.sh: with the override as the reference, ours vs reference is
0 px on TexFmt_R6G5B5; without it, 134,902. If it does not reproduce, report that instead.

## Done when
The PNG and README are in a ready PR touching only docs/testing/golden_overrides/** and
docs/lanes/goldovr287/**, NOTES.md states sha256 checked and falsify.sh's output. No arm
(no emulator change). Do NOT edit score_sweep.py, scoreboard.py or dispatcher.sh: not granted.
