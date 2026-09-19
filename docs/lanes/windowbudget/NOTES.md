# lane.windowbudget -- the pipeline contracted on a session count, which is not the constraint

PR #155. Branch `lane/windowbudget`, based on master `6ca12eb803`.
No issue: a harness defect, dispatched directly. No prediction: no pixels.

## What was built

`docs/testing/jobs/window.sh` is new and is the only place any of this is
decided. Four scripts source it.

1. **A lane's exit is mapped like every other job's.** `lane.sh`'s unit now
   ends `fleet-end <name> <rc> <log>; exit $?`, and `fleet-end` decides the
   code: a refusal by the account's window is **75 (EX_TEMPFAIL)** and the
   attempt is **refunded**. `run-claude-job.sh` keeps its own check, now
   calling the shared function, and records the hit.
2. **`board.sh` holds a reserve.** Two rules, below. It defers lane dispatch
   by taking the `capacity` trigger away in the gate itself -- not by telling
   the model not to dispatch, because a tick that wakes every twenty minutes
   to be told there is work it may not start is the expensive half of the
   thing being deferred. The audit outlet's claim (`cloud.sh`) is deferred
   with it: §9.1 reserves the last fifth from "lanes and audits", and an audit
   session is a lane session.
3. **It says so.** The board's tick log, the board session's brief, and a new
   **Window budget** section at the top of `status.sh`'s page. No `FAIL` line,
   so no gate reads a deferral as breakage and wakes a tick to investigate it,
   and no lane is charged an attempt for it.

## The two rules, and why neither is a calendar

    cooldown        a session was refused (recorded in $WORK/window/limits.tsv)
                    -> defer until the reset the run named, or re-probe in 30 min
    weekly reserve  the week is >= 80% elapsed AND
                      a declared WEEK_SPEND_BUDGET is >= 80% spent, or
                      this fleet was refused >= 2 times INSIDE the reserve
                    -> defer until the week rolls

Time alone is not a rule here. §9.1 says the board "checks the day **and** the
run index", and a calendar that stops dispatch every Saturday afternoon would
be a throttle, not a brake on a measured constraint -- it would bind hardest
on exactly the weeks with a real backlog, which is the criticism the brief
makes of `LANE_MAX` standing in as the budget. `LANE_MAX` is untouched; it
stays the runaway backstop its comment says it is.

Both arms **fail open**: no declaration and no refusals means the fleet
dispatches, all week. An unknown window that halts dispatch is an outage with
a tidy explanation.

### Why the weekly arm counts refusals in the reserve, not in the week

A refusal is first-hand evidence that *a* window closed, and **nothing here
can tell which one**: the five-hour window and the weekly window are refused
with the same message. Counting Tuesday's refusals as evidence that Sunday's
*weekly* budget is gone reads a bound as a value -- Tuesday's five-hour window
has reset thirty times since. Refusals inside the reserve's own stretch need
no such inference: whichever window they belong to, they were refusals in the
stretch the reserve is meant to protect. The week's total is reported on the
status page and never armed on.

## The week's start is a declaration, not a measurement

**This is the number most likely to be wrong, and it is the one the brief
warned about.** The account's weekly window resets on an anchor that is not
visible from this host -- there is no API here that answers "when did my week
start". So:

- `WEEK_ANCHOR` (default `Mon`) and `WEEK_ANCHOR_HOUR` (default `0`, UTC) are
  in `$WORK/limits.env`, and the status page and the tick log both print the
  week start they used, so a wrong anchor is visible rather than silent.
- Under the default, the reserve stretch opens **Saturday 14:24Z** and closes
  Monday 00:00Z. On the day this was written (Sat 2026-09-19, 79% elapsed at
  13:30Z) the board begins printing its `NOTE: this is the last fifth` line
  within the hour.
- **Being wrong by a day or two costs a shifted reserve window, not a stopped
  fleet**, precisely because the time test alone defers nothing. That is the
  main reason the rule needs two conditions rather than one.

If the owner learns the real anchor (the CLI prints a reset time when it
refuses a session, and `window.sh` records it in `limits.tsv` column 3), set
`WEEK_ANCHOR`/`WEEK_ANCHOR_HOUR` to match. Nothing else needs to change.

## What can be observed from here, and what cannot

Written out because a zero from a blind instrument reads exactly like a zero
from a healthy one.

**Observable**

- Every session this fleet started: `logs/<job>/index.tsv`, one line per run
  with turns, seconds and the run's own `total_cost_usd`.
- The moment a session was refused, from its JSON log -- and sometimes the
  reset epoch the CLI appends to its message.

**Not observable, at all**

- The account's remaining five-hour or weekly balance. There is no API here.
- Which window a refusal belongs to (see above).
- The account's weekly anchor (see above).
- **The owner's own interactive sessions.** They come out of the same pool
  (§9.1 says so) and appear in no `index.tsv` on this host. Every spend figure
  here is therefore a **lower bound on the account's spend**, never the value.
  A `WEEK_SPEND_BUDGET` calibrated from these numbers is a budget for the
  *fleet's share*, and should be set well under whatever the account can take.

`total_cost_usd` is a **proxy for token spend, not money**: on a Max account
there is no per-token charge. It is used because it is the only per-run
quantity in the index that scales with what the window actually meters; a run
count does not (runs in the measured corpus vary 6x in turns).

## Numbers measured on the host, 2026-09-19

The run corpus, `$WORK/logs/{board,lane,cloud}` (85 JSON logs):

| shape | count |
|---|---|
| `is_error: false`, `subtype: success` | 72 |
| `is_error: true`, `subtype: error_max_turns` | 14 |
| unparsable (session killed before writing) | 5 |
| **any field naming a rate or usage limit** | **0** |

So **the fleet has never been refused on this host**, and the detection could
not be tested against a real sample. That is why it accepts several fields
rather than one: a miss leaves today's behaviour (the run reads as a failure),
and no shape in the measured corpus is reported as a limit.

Spend, from the three `index.tsv` files, over 2026-09-18T23:37Z -> 13:17Z
(13.7 h, the whole life of the job harness):

| index | runs | sum `total_cost_usd` |
|---|---|---|
| lane | 46 | 299.3 |
| cloud | 14 | 89.5 |
| board | 25 | 43.9 |
| **total** | **85** | **432.7** |

Lanes are 69% of it, which is why §9.1's controls missing lanes mattered.
Seven days at that rate is ~5,300 units; that is the order of magnitude a
`WEEK_SPEND_BUDGET` would be set in. **I did not set one.** It is a
declaration about an account I cannot query, it belongs in the host's
`$WORK/limits.env` and not in a commit, and the evidence arm arms the reserve
without it. The board now says on every tick in the reserve stretch that the
budget arm is unarmed and what would arm it, so it cannot sit inert and
silent.

## The falsification runs

Both were run in `docs/testingX`, a symlink shadow of `docs/testing` whose
`jobs/selftest.d` holds only this fragment; the files under test were replaced
*inside the shadow* (`git show origin/master:...`), so no real path was ever
swapped and no other fragment ran against the wrong tree.

| shadow | result |
|---|---|
| my tree | 45 pass, 0 fail |
| all six files from `origin/master` | **32 fail**, 11 pass |
| `window.sh` mine, `lane.sh`/`board.sh`/`status.sh`/`run-claude-job.sh` from `origin/master` | **24 fail**, 19 pass |

The second run is the one worth keeping: with the helper present, the 8
detection checks go green and the reds are not one reason but three distinct
mechanisms -- `lane.sh`'s tail (8), `board.sh`'s gate and outlet (11),
`status.sh`'s page (5).

The 11 that stay green against the fully-old tree are the must-not-move legs:
master dispatches normally with the window open, mid-week, and after a stale
refusal, and it has no refund path to break.

**The first version of three checks passed against the old tree for the wrong
reason.** `! window_limit_hit x` is *true* when the function does not exist,
so "a healthy run is not a hit", "a missing log is not a hit" and -- worst --
"a capped run that merely mentions a rate limit is not one" were green against
a tree with no `window.sh` at all. They now go through `wl_not`, which refuses
unless `declare -F` finds the function first. A negative check has to prove
there is something there to be negative about.

## What is NOT covered

- **`cloud.sh`'s own unit tail.** An audit or cloud-lane session is started by
  `cloud.sh` and ends by calling `cloud.sh finish`, which does not consult the
  window: a cloud session refused by the account still spends an attempt in
  `$WORK/attempts/`. `cloud.sh` belongs to `lane.cloudterritory` this cycle
  and I did not touch it. The board-side deferral shrinks the exposure (no
  claim is made while the window is known closed) but does not close it. The
  fix is four lines: source `window.sh`, and in `finish`, `window_limit_hit`
  the log, `window_note_limit`, decrement the counter.
- **`handback.sh`** resumes a lane without consulting the window. Harmless for
  the counter now -- the refund is in `lane.sh`, where every resume path goes
  through -- but it will spend a session start into a closed window. Cheap,
  and a gate there would need the same helper; left deliberately.
- **No real limit log.** The field names (`terminal_reason`, `subtype`,
  `api_error_status`, the `Claude AI usage limit reached|<epoch>` message) are
  the shapes the CLI is known to use; none has been seen on this host. When
  the first real one lands, check it against `window_limit_probe` and add the
  fixture to the fragment.

## What the next lane should not repeat

- **Do not read tab-separated fields with `read`.** Tab is an IFS *whitespace*
  character, so a run of empty fields collapses and every later field shifts
  left. `window_check` printed `defer/until/why/facts` and the facts landed in
  `WINDOW_UNTIL`, which read as a deferral with no reason. It prints one field
  per line now.
- **Do not pass fixture output to a check in a shell variable.** `check ...
  bash -c 'grep ... <<< "$out"'` reads an *unexported* `$out` in the child --
  the empty string. Two checks failed for that and not for the tick. Write to
  a file, or pass it as an argument.
- **Do not `rm -rf` the board worktree between two tick fixtures.** git keeps
  the registration in the repo, the second `worktree add` fails, and `board.sh`
  exits at "cannot create" *before* reaching the thing under test -- which for
  a "did not happen" check is green for the wrong reason.
- The detection's real adversary is the model's own prose, not the JSON. Any
  future test of it belongs on fields.

## Dials (all in `$WORK/limits.env`, none in a commit)

    WINDOW_COOLDOWN_MIN=30     re-probe interval after a refusal with no named reset
    WEEK_ANCHOR=Mon            the declared start of the account's week
    WEEK_ANCHOR_HOUR=0         ... in UTC
    WEEK_RESERVE=0.2           §9.1's "last fifth"
    WEEK_SPEND_BUDGET=         unset: the budget arm is not armed (and says so)
    WEEK_LIMIT_HITS=2          refusals inside the reserve that arm it instead
