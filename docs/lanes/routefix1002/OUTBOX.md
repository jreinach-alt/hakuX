## #433 -- 2026-10-02 22:50 PDT
Queued: Gunvalkyrie (5345000B, replay 2's loop, 840 s) in `docs/lanes/routefix1002/queue.tsv`; its route gains `# state: first-run`.
Not queued: Buffy. Its ledge-gap stall is unsolved (the jump is not found), so a blind loop change would be a guess; the Options probe comes first.
Not queued: Halo CE. The 4D530004 golden has an all-zero savegame.bin and a profile-only blam.sav, so it is not past training; no returning route written.
Not done as briefed: the Gunvalkyrie v5. Its "forward, no turn" loop is v4, which pinned Kelly to a wall in replay 4 (`1790944628-titleroutes2-2686999`).
Ref: the brief's `effb0d001b` is a uberdefault569 commit, not titleroutes2's; flagged for the PM to confirm.

## #433 -- 2026-10-03 08:33 PDT
Queued: Gunvalkyrie v5 (5345000B, route `gunvalkyrie`, 840 s, ref `5024216198`): forward held, 0.8 s back-off, unequal 1.5 s / 0.5 s turns, LT boost, A about every 2.5 s, written from replays 1-4 (table in NOTES.md). `route.sh --check` passes.
Not queued: Buffy. Its ledge-gap stall is unsolved; the Options probe (~70 s held) comes first, and no blind loop change was made.
Not queued: Halo CE. Golden 4D530004 (`90ebd6a27bd1`) has an all-zero savegame.bin (0 of 3,670,016 bytes nonzero): not past training, so no returning route.
Why v5 and not replay 2: the brief asked for v5, and the 08:30 addendum confirmed it. v5 is untested; replay 2's loop played the whole window with one 2.5-min cliff. If v5 pins, replay 2's loop (`685c52e514`) is the fallback.
Heads-up for lane.local: session 1's queue line (replay 2 loop, ref `effb0d001b`) may already have been queued. If so, that run is the stale one; v5 is the line in `queue.tsv` now.

## #433 -- 2026-10-03 08:57 PDT
Queued (unchanged from 08:33): Gunvalkyrie v5 at 840 s, ref `5024216198`, `queue.tsv` line 1. Merged origin/master (2 commits, incl. savestate433); `route.sh --check` still passes.
Not queued: Buffy. Its ledge-gap stall needs a held Options probe (~70 s), which this offline session cannot run; no loop change without it.
Not queued: Halo CE. Golden 4D530004 re-read: savegame.bin all zero, blam.sav profile-only. Not past training.
Next, P x win: Gunvalkyrie v5 pins -> replay 2's loop (P moderate, it played 2.5 min before a cliff; win 600 s); Buffy -> Options probe (P high it answers the question; win Buffy Playable); Halo -> a held run through training (P high; win the most-played title).
Session 2 never merged the last two master commits; session 3 did. PR.md stays draft (addendum 1).

## #433 -- 2026-10-03 10:17 PDT
For lane.local, act before sw3 (1791045669) finishes: the runner's `gunvalkyrie` line in `pm/overnight-queue.tsv` will play `wt/lanelocal-queue`'s replay-2 loop, not v5. Nothing reads `docs/lanes/routefix1002/queue.tsv`. To run v5, change that line's worktree (column 4) to `/home/justin/hakux-work/wt/routefix1002`. Keep ref `effb0d001b`: request.sh reads the route text from the worktree, so the ref only picks the cached build.
Checked after merging master (`9674b5c4c0`): `route.sh --check` passes; `titlestate resolve-route` gives first-run, golden 4e2a12123171, refuse null.
Next, P x win (win either way: Gunvalkyrie Playable, +1 title; cost: one 840-s Nova slot): v5 P ~0.3, since it targets both measured pins (replay 4's wall, replay 2's cancelling turns) but has never run. Replay 2's loop P ~0.25: it played 420 s with a 2.5-min cliff stall, and 600 s likely brings another. If the replay-2 line has already started, let it run; whichever loses is the next candidate.
Not queued: Buffy, because buffy.route moved to lane.titleroutes (08:35 board). Halo CE, because golden 90ebd6a27bd1 is unchanged and not past training.
PR.md stays draft (ADDENDUM 1). If the v5 route should reach master, lane.local moves it on a clean branch.
