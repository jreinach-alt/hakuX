# lane.async794 OUTBOX: per-title control vs fix

Nova, perflog, decompose.py over the 2-s rows after the gameplay mark;
sdcallers.py for the per-caller waits. A = master 5e4196fefd, B = c825e4b24f.

| title | arm | run id | fps | ph_Fin ms | ph_Tot (render) ms | lockw ms | share >= 28.5 | download wait by caller |
|---|---|---|---|---|---|---|---|---|
| NBA Live 2005 | A | 1791128020-lane.async794-3209876 | 25.89 | 13.40 | 27.40 | 3.38 | 0.20 | reuse 1.00/fr, 11.18 ms |
| NBA Live 2005 | B | 1791128026-lane.async794-3210567 | 25.34 | 13.80 | 28.10 | 0.27 | 0.19 | surfupd 1.00/fr, 11.48 ms |
| Top Spin | A | 1791135713-lane.async794-3678571 | 36.58 (median 36.50) | 12.30 | 22.50 | 10.50 | 0.963 | txr dl 27/fr, all `cvt` |
| Top Spin | B | 1791135717-lane.async794-3678947 | 35.85 (median 35.82) | 12.60 | 23.30 | 0.40 | 0.963 | txr dl 27/fr, all `cvt` |

NBA Live 2005: **fix 1 refuted, wait moved** (X1 fires). The finish went from
`reuse` to `surfupd`, the rebinding's upload from VRAM. Fix 2's lock release
acts (lockw -3.1 ms) without moving NBA's fps. Counter-Strike, Midnight Club 3
and Burnout Revenge were not run: their pairs tested fix 1, which is refuted.

Top Spin: **fix 2 acts and moves no fps.** The vCPU's lock wait fell from
10.5 to 0.4 ms/frame (rd_unl 0 -> 308k). The freed time went to the guest's
timer idle (gidle 0.56 -> 15.67 ms), and the share stays 0.963 in both. The
prediction's legs all hold (P2 only because A already passes) and X1 does not
fire.

**Top Spin clears the bar on master with the fixed route** (`async794-topspin`,
no step-24 START): 36.5 fps median, 0.963 share over 640 s of a live match.
fps20786's 0.89 was a paused match. It is a Playable candidate now, pending
the 600-s held run, the frame review and the flicker check.

Fold form 2344ae1ee2: fix 1 stripped, fix 2 and the txdl instrument kept.
The golden arm on the first form passed byte-identical (266/266,
1791129309-arms-async794-fix-3307191). `async794-fix2-must-not-move.json` is
registered for the stripped ref.

Fold-form golden arm judged PASS (2026-10-04 14:45 PDT): 266 of 266 captures
same, no movers (1791146467-arms-async794-base-1273188 vs
1791146467-arms-async794-fix-1273227). PR.md is `State: ready`. No follow-up
device runs for fix 2: it claims no fps change, and the Counter-Strike, MC3 and
Burnout Revenge pairs only tested fix 1. The follow-ups that could move fps
need their own briefs: a GPU-side converting copy for the texture-bind `cvt`
class, and a GPU-side path for NBA's image -> VRAM -> image rebinding.

Fold gate (2026-10-05): the branch merges origin/master f3bd87638e, which
includes libfolders, so a build from the head boots on a migrated device. One
120 s Nova hold of 4D53000F is queued at the head commit that carries this
paragraph, and that run is the gate. Its run id and result (boot ok, no wizard,
void=no) are on #798 and not in a commit. offline_fold.py accepts only a run
built from the exact head (`head.startswith(ref)`), so committing the result
here would move the head and void the run it reports.
