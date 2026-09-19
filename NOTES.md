# lane.fleetreg — the board's sensor now asks systemd

## What was wrong

`fleet.py` is the board's only wake-up: `board.sh:51` greps its output for
`^FAIL` and starts a model tick on any hit. All four FAIL conditions were
computed from `$DISPATCH_DIR/fleet/<lane>.json`, a directory whose own docstring
said it was "written by the ORCHESTRATOR". `ORCHESTRATION-DESIGN.md` §4 deleted
that role and nothing took over; `grep -n fleet docs/testing/lane.sh` returned
nothing for the whole life of that file.

Reproduced at 2026-09-19T06:24Z before touching anything, against a live host
running **nine** `hakux-lane-*.service` units:

| | registry (old fleet.py) | systemd |
|---|---|---|
| running | 4: `blitsafe fold remote swizzle87` | 9: `armpin auditoutlet backlogstate boardgate fleetreg foldci glerr86 handback notespath` |
| overlap | — | **zero** |

Two of the four were not running at all and `swizzle87` had been folded and
merged. The sets are disjoint, so the sensor was not merely lagging — it was
describing a fleet that no longer existed. Six consecutive board ticks logged
`nothing actionable`, and would have logged it with the fleet idle too.

Re-run 40 minutes later without touching anything: `RUNNING` 8 → 4 as `blit84`,
`glerr86`, `armsskip`, `boardgate` and `notespath` ended, and `READY, NOT
FOLDED` 3 → 5 as two of them marked their PRs ready. The old sensor would have
printed the same frozen four both times. Every number in this file is a dated
snapshot, not a constant — that is the point of deriving them.

## What it reads now

| section | old source | new source |
|---|---|---|
| RUNNING | `state == "running"` in the registry | `systemctl --user list-units 'hakux-lane-*' --state=active,activating` |
| REPORTED → **READY, NOT FOLDED** | `state == "reported"` | one `gh pr list`: open, `lane/*`, not a draft, carrying no pipeline label |
| WAITING ON THE ORCHESTRATOR → **BLOCKED** | registry `waiting_on` prose | the same `gh pr list`: the `blocked` label |
| LANE CLAIMED WITH NO RUNNING AGENT | territory rows minus registry | territory rows minus the systemd set |
| RUNNING WITH NO TERRITORY ROW | registry minus territory | the systemd set minus territory |
| DISPATCHABLE | suppressed by registry `running` lanes | suppressed by the systemd set (plus a running lane's own registry `issues`) |

Cost: two `systemctl` calls (`list-units` for names, then **one** keyed `show`
for all start times — not one per lane) and one extra `gh pr list`. Measured
end-to-end **1.8s** against the live host, against a 60s budget in `board.sh`.

`ActiveEnterTimestampMonotonic` and `/proc/uptime`, not `ActiveEnterTimestamp`:
the latter is local time with a timezone *abbreviation* (`PDT`) that `strptime
%Z` cannot be trusted to read, and `--timestamp=utc` needs systemd 247.

## The registry: kept, demoted, and it can no longer withhold work

`lane.sh` writes `$DISPATCH_DIR/fleet/<lane>.json` at `start` and `resume`, and
the unit's own command line calls `lane.sh fleet-end` after `summarise_run.py`,
which appends the final shape to `fleet/history.jsonl` and unlinks the entry.

It carries **no `state` field**. State is what went stale; state is now derived.
What it carries is what `lane.sh` knows first-hand: `asked` (the brief, 400
chars, whitespace collapsed), `issues`, `attempt`, `model`, `branch`,
`worktree`, `started_utc`. `fleet.py` ignores any entry whose lane has no active
unit, so an entry can never create a lane, revive one, or suppress a dispatch.

`resume` takes no issue argument and the entry is gone by then, so `start` also
writes `$WORK/briefs/<name>.issue` beside the brief for `resume` to read.

A missing entry costs the `asked` prose and the issue list — the lane still
appears in RUNNING, and its issue may show up as DISPATCHABLE, so the board
takes a second look at work already in hand. Over-claiming would *hide* work;
this errs the other way on purpose.

## The 37 stale entries: **ignored, and collectable on demand**

Not migrated (they have no `started_utc` and their `state` is the field being
abolished), not deleted by `fleet.py` (a read-only reporter the board runs on a
timer has no business mutating `$DISPATCH_DIR`). They are inert: `fleet.py`
never shows them as lanes and never lets them suppress anything. It prints one
line — `(37 registry entries for lanes with no active unit, ignored)` — so they
read as what they are rather than as current.

`lane.sh fleet-gc` deletes them, in one command, when somebody wants the disk
back. **It refuses if `systemctl --user` does not answer**: an unanswered query
would otherwise produce an empty active set, which reads as an idle fleet and
would delete the *live* lanes' entries. That is the same confusion as the one
being fixed, pointed the other way, and there is a selftest check for it.

## FAIL lines: which can fire now that could not, and vice versa

**Can fire now, could not before:**

- `RUNNING with no territory row`. Both sides of this cross-check used to be
  orchestrator-written, so after the role died it could fire for *nothing*. It
  fires for **eight lanes** on the first live run, and the collision it warns
  about is real and active: six of them are editing
  `docs/testing/jobs/selftest.sh` concurrently. The board clears it by writing
  the rows (`files = []` is a valid claim).
- `DISPATCHABLE`. Went from 0 to **9**, not because more work appeared but
  because the four lanes that were suppressing issues are not running.
- `READY and carry no pipeline label`. Three PRs (#129, #117, #115) sitting
  ready with no `needs-audit-*`; nothing else picks those up. The old
  `state == "reported"` FAIL had been unfireable since 09-18.
- `labelled blocked`. Unfireable since 09-14 as `waiting_on`.

**Can no longer fire:** nothing that could fire on 2026-09-19. All four old
conditions were already dead — that is the defect. In principle, if the
orchestrator role were restored and started writing `state`/`waiting_on` again,
those two derivations are gone for good.

**One more that can fire: `FAIL: FLEET-BLIND`.** I first wrote the blind path
to raise *no* FAIL — reasoning that a board tick cannot fix a broken user
manager, so waking a model session every twenty minutes would be pure cost.
That was wrong for this file specifically: `board.sh` keeps only `^FAIL` and
drops every other line, so a blindness announced any other way is announced to
nobody, which is precisely how this file reported calm for five days. It is
its own FAIL now, and `gh` blindness is deliberately *not*:

| condition | FAIL? | why |
|---|---|---|
| `gh` unreachable | no | transient, retried in twenty minutes, nothing a tick can do |
| `systemctl --user` unreachable **from a process whose job is to manage user units** | **yes** | a configuration defect; it does not self-heal and nobody finds out otherwise |

The derived FAILs stay suppressed under blindness either way — "I could not
ask" must never become "nothing is running". The selftest pins both halves:
exactly one FAIL, and it is the blindness.

**Net effect on board wake-ups:** the first tick after this lands will be
actionable rather than `nothing actionable`, and will stay actionable until the
board writes eight territory rows and labels three PRs. That is roughly two
ticks of real work, after which the gate goes quiet for the right reason.

## The checks, and what they measure against the file being replaced

25 checks appended to `jobs/selftest.sh`. To prove they measure something I ran
the same fixture set against `origin/master`'s `fleet.py` and `lane.sh`
(`bdeab36f75`), via a scratch runner that differs from the selftest block only
in which pair of scripts it points at. To redo it: `git show
origin/master:docs/testing/fleet.py > docs/testing/fleet.old.py` (and the same
for `lane.sh`), then run the block's `fleet_run`/`lane.sh` invocations against
those paths — they must sit **inside `docs/testing/`**, because `fleet.py`
imports `board_files` from its own directory and `lane.sh` derives `$JOBS` from
its own.

```
falsify[new]: 25 passed,  0 failed
falsify[old]:  5 passed, 20 failed
```

The five that pass against the old code are the negative controls — "a draft
lane PR is not reported as ready", "a `fold-ready` PR is not the board's item",
"a PR not on a `lane/` branch is nobody's lane", "fleet-gc keeps the live
entry", "an unowned issue is dispatchable". The old file passes those because it
never looks at PRs at all, so they discriminate nothing; they are there to stop
a future edit from over-reporting. Every check that asserts a *positive* fact
about provenance fails against the old code.

Two checks passed against the old code for the wrong reason on the first run —
`fleet-end removes the entry` (nothing had been created, so "absent" was free)
and `fleet-gc drops the entry` (the `cp` that set it up had failed silently).
Both are now stated so they cannot pass vacuously: `fleet-end` must leave a
`history.jsonl` *and* remove the entry, and the gc fixtures `mkdir -p` first.

## Limits, stated rather than discovered later

- **A `[lane.<n>] blocked:` comment with no `blocked` label is invisible here.**
  Reading comments is one `gh` call per PR and the budget is two calls total, so
  the *label* is the contract. If a lane only comments, the board never wakes.
  Worth a line in `roles/lane.md` — not my file; flagged for whoever owns it.
- A lane started by anything other than `lane.sh` has no registry entry, so its
  issue is not suppressed. Conservative, see above.
- A SIGKILLed unit skips `fleet-end` and leaves an entry. Harmless by
  construction, and precisely why `fleet.py` asks systemd rather than the
  directory who is running.
- The selftest exercises the real `lane.sh start` path against a throwaway
  `git init` origin, so the worktree, attempt counter and cap arithmetic all
  execute. What it does *not* exercise is systemd actually running the command
  line — the `systemd-run` shim logs it, and the check greps that log for the
  `fleet-end` call.

## Incidental, and it cost a few minutes

**`gh pr edit --body-file` fails on this host too**, not just `--add-label`:

```
$ gh pr edit 133 --body-file .pr-body.md
GraphQL: Projects (classic) is being deprecated ... (repository.pullRequest.projectCards)
```

`AGENTS.md` and `roles/board.md` document the breakage for `--add-label` only,
so the natural reading is that the rest of `gh pr edit` is fine. It is not —
the failing field is `projectCards`, which `gh pr edit` requests on *every*
invocation regardless of which flag you pass. The working call is
`gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>`, the same REST
route `gh-label.sh` already takes for labels. Worth widening the rule from "the
label flags" to "`gh pr edit`" wherever it is written down.

## For the next lane

- Do not reintroduce a `state` field. The whole defect is one word written by
  somebody who was later deleted.
- `lane_units()` returning `None` is **not** an empty fleet, and every caller in
  `fleet.py` distinguishes them. If you add a section that subtracts the running
  set, suppress it under `fleet_blind` or you rebuild the bug.
- `board.sh` greps `^FAIL`, so every FAIL string is a model session every
  twenty minutes. Each one now names the actor and the action that clears it;
  keep that up.
