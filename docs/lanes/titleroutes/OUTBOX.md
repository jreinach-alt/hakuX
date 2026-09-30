## #397 -- 2026-09-30 (session 38)

[lane.titleroutes] Session 37's three Nova routes (Midnight Club 3, 187: Ride or Die, Crash: Wrath of Cortex) already folded as PR #626. Their three queued benchmark requests, though, are missing everywhere under `dispatch/` -- most likely lost to the titles-disk mode-660 crash lane.hddcrash just fixed (folded offline as `146b8887db`), which killed 10 of 11 titles.qcow2 boots between 09-28 00:00 and 09-29 20:05, overlapping when I queued them. Re-queued all three on the Nova at the fixed ref: `1-1790764527-titleroutes-2436824` (Midnight Club 3, 460 s), `1-1790764530-titleroutes-2437076` (187: Ride or Die, 370 s), `1-1790764531-titleroutes-2437119` (Crash: Wrath of Cortex, 400 s).

The Thor is out of service (`lanelocal-fanwait`: dead fan, owner 09-29 approved a warranty replacement) -- no Thor work this session. The Nova was free at 35% battery; queued rather than held.

[lane.titleroutes] waiting: the three re-queued Nova benchmark requests above (`1-1790764527-titleroutes-2436824`, `1-1790764530-titleroutes-2437076`, `1-1790764531-titleroutes-2437119`). Once they land, their fps table goes here and in NOTES.md, and the next batch (Black Stone's walk investigation, Burnout Revenge's profile loop) continues on the Nova. Thor work resumes when `lanelocal-fanwait` lifts.
