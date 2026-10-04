# lane.async794 OUTBOX: per-title control vs fix

Nova, perflog, decompose.py over the 2-s rows after the gameplay mark;
sdcallers.py for the per-caller waits. A = master 5e4196fefd, B = c825e4b24f.

| title | arm | run id | fps | ph_Fin ms | ph_Tot (render) ms | lockw ms | share >= 28.5 | download wait by caller |
|---|---|---|---|---|---|---|---|---|
| NBA Live 2005 | A | 1791128020-lane.async794-3209876 | 25.89 | 13.40 | 27.40 | 3.38 | 0.20 | reuse 1.00/fr, 11.18 ms |
| NBA Live 2005 | B | 1791128026-lane.async794-3210567 | 25.34 | 13.80 | 28.10 | 0.27 | 0.19 | surfupd 1.00/fr, 11.48 ms |
| Top Spin | A | 1791135713-lane.async794-3678571 | queued | | | | | |
| Top Spin | B | 1791135717-lane.async794-3678947 | queued | | | | | |

NBA Live 2005: **fix 1 refuted, wait moved** (X1 fires). The finish went from
`reuse` to `surfupd`, the rebinding's upload from VRAM. Fix 2's lock release
acts (lockw -3.1 ms) without moving NBA's fps. Counter-Strike, Midnight Club 3
and Burnout Revenge were not run: their pairs tested fix 1, which is refuted.
