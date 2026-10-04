## #672 -- 2026-10-04 14:05 PDT
hangwatch (lane.hangwatch) on the Tron 2.0 hang, from the logs on disk. Two classes, and the detector catches one.

- Run 1-1790990144-uberdefault569-532476 (ubershader default, Nova): one guest PC takes 0.98 of the returns, idle ~0,
  audio silent 716 s, frames static from t=30 s to the end. This is a hang the new rule trips about 2 min in
  (docs/testing/hangwatch.py, not yet wired: the hook waits on a grant for pathfind.py).
- Runs 1790971658-lanelocal-1220020 and 0-1790978946-tronhang672-3184149 (run 6): NOT caught. Busy with a call/ret
  loop in chained TBs; no single pinned PC (pinned 4 s and 2 s), audio silent 446 s and 226 s. Matches
  docs/lanes/tronhang672/NOTES.md. The detector needs a guest-progress signal (hakuX-pace flips or GPU submits) for
  this class; that is the next candidate, P about 0.5, and it can be measured from existing logs.

## #811 -- 2026-10-04 14:05 PDT
Whiteout (4B4E0001) claim, run docs/lanes/pathfind/runs/screen-whiteout/claim: 138 looks, 15 min, result gave-up on the
loading card. Frames are static (masked change 0.000 on every pair) from about t=146 s to t=898 s. No logcat was kept, so
the emulator's telemetry for this run is not on disk. The detection half is in docs/testing/hangwatch.py (selftested);
the hook waits on a grant for pathfind.py, then the supervised run goes through request.sh.
preflight's coverage gate fails on this row: it has no lane and no blocker. Suggested blocked_on, stated as the
measurement that would refute it: "Whiteout with logcat kept (hangwatch hook) either trips HANG near t=236 s with the
guest pinned and audio quiet, or shows the guest moving; the call/ret class is not covered by the current rule".

NEW ISSUE: pathfind's screening loop keeps no logcat, so a screening run has no emulator telemetry on disk
Evidence: runs/screen-whiteout/claim has no logcat; pathfind.py starts logcat only in hold_play (line 1352). The
Whiteout claim (4B4E0001) held the Nova 15 min on a static loading card with the rr425/audio tags unrecorded. The
hangwatch hook starts a screen-logcat.txt in run() to close this, in pathfind-hook.patch.

NEW ISSUE: steps.jsonl never records `changed`
Evidence: runs/screen-whiteout/claim/steps.jsonl has changed=null on all 138 rows. run() sets steps[-1]["changed"]
after write_step has already appended the line, so only the in-memory dict has it. The frames are the only record.

NEW ISSUE: the dispatch soak has no stop condition on a locked-up title
Evidence: 1-1790990144-uberdefault569-532476 (Tron 2.0, Nova, 720 s soak) ran its whole length with pinned+quiet+still
for about 690 s. The rule in docs/testing/hangwatch.py would have stopped it near 130 s. dispatcher.sh's fixed-length
soak is lane.toolsmith's territory; the hook is pathfind-side only so far.

NEW ISSUE: the hang gate in failure_intake.py cannot hold a screening claim
Evidence: gate(tid, route_file) matches on the route file's sha. A pathfind screening claim has no route file, so
rsha is '?' and no row is ever held by it. Found by reading host-tools/failure_intake.py; not tested on a live row.

## #811 -- 2026-10-04 14:48 PDT
hangwatch (lane.hangwatch), attempt 2. The hook is applied to pathfind.py (screening loop and hold loop), selftests green
(hangwatch 15/15, pathfind dry selftest all ok, fragment 96-failgate 12/0). NOT yet confirmed on a live device: request.sh
cannot run a pathfind claim, and a direct run is outside lane rules, so the supervised Whiteout run waits on an owner
decision (docs/lanes/hangwatch/WAITING). Until it returns HANG, the hook is not folded.
