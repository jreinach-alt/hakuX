# pilotgate: no device batch over 30 minutes without a reviewed pilot

Owner rule, 2026-09-26. Prompted by titleplay's pass 1 (#397): 29 soaks of
420 s queued at once, a route that reached clean gameplay in 7 of 15 titles,
and nobody looked at the first two runs before the other 27 ran.

## What landed

- `docs/testing/request.sh`: the gate sits after the request record is
  written to its dotfile and read back, and before the rename into `queue/`.
  It reads the new record (the one the dispatcher will read) and sums it with
  every `queue/*.req` and `running/*.req` of the same requester. Over 1800 s
  it refuses (exit 2, temp removed) unless `$D/pilots/<requester>.ok` has an
  mtime under 24 h. The refusal names the rule, the per-part estimate, why the
  pilot file does not admit it, and the way out.
- Rule text: `AGENTS.md` ("Working with a device", top) and
  `docs/testing/jobs/roles/lane.md` ("Pilot first").
- `docs/testing/jobs/selftest.d/99-pilot-gate.sh`: legs A (over, no pilot:
  refused, running/ counted), B (25 h old pilot: refused), C (another
  requester under budget while `pg` is over: admitted, per-requester scope),
  D (exactly 1800 s: admitted), E (fresh pilot: admitted).

## The estimate lives in two places

`request.sh` (the `PYPILOT` block) and `host-tools/harness_health.py`
(`[device-budget]`, host-only, not in this repo). Same formula:
`(seconds + 90) * runs` if `seconds > 0`, else 180 flat (not times runs).
Same globs (`queue/*.req` + `running/*.req`, so the idle `z-` tier counts),
same `requester or "?"` key, same `> 30*60` and `mtime < 24 h`. Change both or
neither.

Measured side effect worth knowing: `request.sh` writes `"seconds": 60` on
EVERY request (the `--seconds` default), suite runs included, so a suite
request counts (60+90) x runs, not 180. The 180 s branch is only reached by
records written elsewhere (`queue_full_sweep.sh` writes `"seconds": 0`). An arms pair at runs 3 is
2 x 450 s = 15 min, under the limit; the gate will not bite the arms job in
normal use, and if it does, arms.sh already posts a request.sh refusal on the
lane's PR as `[job.arms] REFUSED`.

## Writers of queue/ that do not go through request.sh (exempt)

| writer | why exempt |
|---|---|
| `dispatcher.sh` (requeue when the device is absent, requeue after an adb interop loss, orphan recovery at start) | puts back a request that was already admitted: net zero device time |
| `desktop_channel.sh` orphan recovery | same |
| `queue_full_sweep.sh` | idle `z-` tier, pre-empted by every epoch request, so it cannot make anyone wait longer than one run; it is the host's corpus survey, not a lane batch. `[device-budget]` still sees it after the fact, as requester `full-sweep` |
| `host-tools/park_requests.sh --restore` | the host restoring a batch it parked; the remedy, not a new decision |

`arms.sh`, `ab_run.sh`, `ab_bisect.sh` and `sweep_queue.sh` all enqueue
through `request.sh` and are gated.

## Falsification (measured on this branch)

Each named failure world applied as a mutant to `request.sh`, fragment run
alone (10 checks):

| mutant | checks failing |
|---|---|
| none | 0 |
| no gate | 6 |
| counts queue/ only | 4 |
| pilot age ignored | 3 |
| sums all requesters | 3 |
| `>=` instead of `>` | 1 |
| pilot file ignored | 3 |

The `>=` mutant first PASSED: the admission check matched `*"queued "*`, and
the refusal's own prose says "queued or running". Admissions are now judged on
the anchored `^queued <id>$` line. Do not loosen it back.

## For the next lane

- Do not change the 30 min threshold (owner's). The 24 h / 90 s / 180 s are
  the host's; change them in both homes with a reason.
- Writing `pilots/<requester>.ok` from a lane: use python3; the lane sandbox
  blocks Write/cp into the dispatch dir.
