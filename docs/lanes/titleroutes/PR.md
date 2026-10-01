# titleroutes: session 50 -- the Thor's 90 C CPU stop voids every title screen; lane blocked on the threshold

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ dc9529a408 (origin/master merged in session 50; session 49's PR folded there)
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md
Prediction: none: no arm (lane notes only; the one device run was a route screen, not an A/B arm)
Needs device: yes, queued requests only (Thor cold-slot runner, 300 s); no held session

## What changed

Notes only. No routes and no targets.toml changes this session.

**All six of session 49's Thor requests voided on `thor_coldconfirm.sh`'s cpu-1-9 >= 90 C stop,
64-169 s in.** None reached its mark, so none says anything about its route.

**A cold start does not prevent the stop, and neither does a lower regimen.** Hostops' 04:11 fix makes
`coldslot.sh` require cpu-1-9 <= 55 C at the start. It would have admitted the two Castlevania runs that
started at 41.4-41.8 C, and both voided at ~80 s. This session's one pilot ran Gauntlet at
`--env PERF_REGIMEN=default` (`1790853287-titleroutes-569824`). On the Thor that is perf_mode 0, the same
as REST. It started at 39.5 C, read 81 C at +39 s, and was stopped at ~74 s. Before the stop existed,
Castlevania held 94-95 C for four minutes and played 284 s to gameplay. Sonic Heroes' void was a
one-sample trip: it was stopped 4 s into its route while every logged sample read about 51 C. Every Thor
route marks later than the ~75 s the die takes to reach 90 C (the shortest, Gauntlet, marks at ~145 s),
so no screen can reach its mark under this stop.

| run | regimen | cpu-1-9 at start | +38 s | +69 s | stopped |
|---|---|---|---|---|---|
| Castlevania `3234529` | max | 41.8 C | 76.3 | 84.5 | ~80 s |
| Castlevania `3951103` | max | 41.4 C | 77.4 | 86.8 | ~80 s |
| Gauntlet `569824` | default | 39.5 C | 81.0 | 86.0 | ~74 s |
| Sonic Heroes `3954488` | max | 51.6 C | 51.6 | 51.2 | 4 s into its route |
| Castlevania survey `2238193`, before the stop existed | max | 52.0 C | 95.0 | 94.6 | none; held 94-95 C for 4 min, played to gameplay |

The six re-queues the 04:11 addendum asked for are withheld: they would void the same way. The lane is
blocked on a host-tools decision: raise the stop, require consecutive reads, or screen on the Nova until
the fan is replaced. That decision is in `dispatch/board-requests/titleroutes.md` and OUTBOX #397. NOTES.md
session 50 also has a cold-start state for a successor: confirmed and nominated routes, routes waiting on
a clean replay, voided surveys, and the re-queue order and command.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks passed.
- `targets.toml` parses (tomllib, 80 titles; unchanged).
- No harness files changed, so `docs/testing/jobs/selftest.sh` does not apply.

Release note (none): lane notes only; no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
