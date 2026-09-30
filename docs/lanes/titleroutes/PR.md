# titleroutes: session 38, re-queue the three benchmarks lost to the offline cutover (#397)

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 146b8887dbe47f92bd6cc41418579c02065fb8ed
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/PR.md, docs/lanes/titleroutes/OUTBOX.md
Prediction: none: no arm (route/notes bookkeeping; no code or golden changed)
Needs device: yes (queued, not held; see NOTES.md session 38)

Release note (none): lane bookkeeping only, no emulator code touched.

## What this session did

Session 37's three Nova routes (Midnight Club 3, 187: Ride or Die, Crash:
Wrath of Cortex) had already folded into master as PR #626
(`a3681ccb0b`). This session found their three queued benchmark requests
missing everywhere under `dispatch/` -- most likely lost to the
titles-disk mode-660 crash that lane.hddcrash fixed (folded as
`146b8887db`, also offline while GitHub was suspended), which killed
2-7 ms after boot on 10 of 11 titles.qcow2 runs between 09-28 00:00 and
09-29 20:05, overlapping when those three were queued. See NOTES.md
"Session 38" for the full account, including why I can't confirm the
exact cause (no surviving run.log).

Re-queued all three on the Nova at ref `146b8887db` (the fixed
dispatcher): `1-1790764527-titleroutes-2436824` (Midnight Club 3),
`1-1790764530-titleroutes-2437076` (187: Ride or Die),
`1-1790764531-titleroutes-2437119` (Crash: Wrath of Cortex).

Confirmed the Thor is out of service (`dispatch/hold/thor` =
`lanelocal-fanwait`, dead fan, owner 09-29) and left it alone. The Nova
was free at 35% battery, so this session queued rather than took an
interactive hold.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks pass.
- `targets.toml` parses with `tomllib` (checked inline; unchanged this
  session).

## Device proof

Not in this PR. The three re-queued requests above are the device proof;
their results go in NOTES.md and the #397 table (OUTBOX.md) once they
land.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
