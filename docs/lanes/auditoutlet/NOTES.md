# lane.auditoutlet — one dispatch path for audits and remediation

Base: `master` @ bdeab36f75, merged forward twice since. Files:
`docs/testing/jobs/cloud.sh`, `docs/testing/jobs/board.sh`,
`docs/testing/jobs/roles/board.md`,
`docs/testing/jobs/selftest.d/98-audit-outlet.sh`, this file.

## Why attempts 1 and 2 did not finish, and what changed underneath them

The fix itself was written and green on attempt 1 and has not been touched
since. Both later attempts were spent on the same path, `selftest.sh`:

- **Attempt 1** ended with the work pushed and `fold-ready` set. The fold at
  07:13:27Z reported `CONFLICT in: docs/testing/jobs/selftest.sh` — #131 and
  #135 had folded between the push and the tick, both appending to the same
  file.
- **Attempt 2** merged `origin/master` at 07:38Z, kept both blocks, and set
  `fold-ready` again. The fold at 07:55Z conflicted **on the same file a
  second time**: #136 had folded in between and replaced `selftest.sh`
  wholesale, splitting the checks into `selftest.d/` fragments. Nothing
  attempt 2 did was wrong; a merge that is correct at push time is stale by
  the next tick when nine lanes share one path and the fold moves master once
  per tick.

That is the defect #136 fixed, and this attempt is the first that can land,
because the block below now lives in a file no other lane touches.

**Attempt 3 (this one) is a move, not a rewrite.** The sixteen checks went
across verbatim into `docs/testing/jobs/selftest.d/98-audit-outlet.sh`; after
the move `docs/testing/jobs/selftest.sh` is byte-identical to `origin/master`
(`git diff origin/master -- docs/testing/jobs/selftest.sh` is empty), so this
lane no longer holds the contended path at all. 98 keeps the block's position
as the last one appended; it builds its own `gh` shim on its own `$AOPATH` and
depends on no other fragment, so the sort order is not load-bearing for it.

One other thing the merge carried that was not mine: `NOTES.md` at the
repository root is `lane.blit84`'s, folded by #129 before #131's per-lane
convention reached master. An earlier attempt's merge resolution moved it to
`docs/lanes/blit84/NOTES.md`. I put it back at the root, unchanged, so this
branch's diff against master is exactly this lane's five files. Whoever owns
`blit84` — or the next fold that touches it — should move it; a lane silently
relocating another lane's file is a collision the board's `Files:` line cannot
see.

The fix's own files (`board.sh`, `cloud.sh`, `roles/board.md`) merged clean
against `69bacdeea9`, `ae3712aae1` and `6b54c1f88b`; the dispatch line still
sits at `board.sh:67`, ahead of `say "nothing actionable"` at `:89`, which is
the ordering the check pins.

## The defect, restated

`needs-audit-1` and `needs-remediation` are terminal. Three independent
reasons, and all three had to go, because fixing any two leaves the outlet
still handing findings to nobody:

1. `cloud.sh` filtered the remediate pickup on the head prefix `lane/cloud-`,
   so no local lane's PR was ever visible to it.
2. The board only starts a model tick on a `fleet.py` or coverage `FAIL`;
   an unremediated audit is neither, so `roles/board.md`'s resume rule never
   fired.
3. `hakux-cloud.timer` is disabled by the owner, so the prefix-matching path
   has no trigger at all.

## Decision: `cloud.sh` stays, as the one dispatcher, on the lane trigger

Not retired, and not a thin caller of something new — the brief asked for one
answer and this is it. `cloud.sh` was already a lane launcher wearing another
name: a worktree from a named base, a brief, `systemd-run`, a headless
`claude -p` with the same allowlist. What made it a *second mechanism* was not
the file, it was three things that could each be switched off alone:

- its own cap (`CLOUD_MAX`),
- its own unit prefix (`hakux-cloud-*`), so no other count could see it,
- its own timer.

All three are gone. What remains is a script the lane trigger calls.

**The cap is one number, and it is lane.sh's.** `cloud.sh` no longer has a
`CLOUD_MAX`, and it does not carry its own `LANE_MAX` default either — it
reads lane.sh's out of `lane.sh`:

```sh
LANE_MAX=$(sed -n 's/^LANE_MAX=\([0-9][0-9]*\).*/\1/p' "$T/lane.sh" ...)
. models.env; [ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
```

A *repeated* default is a second cap: it agrees on the day it is written and
drifts the first time one of the two is edited. `$WORK/limits.env` overrides
both, sourced after, exactly as in `lane.sh`.

**And one count, not just one number.** The unit is now `hakux-lane-$name`
(e.g. `hakux-lane-cloud-audit1-102`). That is not cosmetic: `lane.sh` counts
`systemctl --user list-units 'hakux-lane-*'` before every start, so an audit
session now occupies a lane slot *in lane.sh's own arithmetic*, with no edit
to `lane.sh` at all (it is not this lane's file). Had I instead made
`cloud.sh` count both globs, the number would have been shared and the count
would not: `lane.sh` would still have started `LANE_MAX` lanes on top of
however many audits were running.

**The trigger is the one that already starts lanes.** `board.sh` runs
`cloud.sh` at the top of every tick, *before* the `nothing actionable` exit.
That placement is the whole point: the two gates report on the fleet and on
the tracker, neither counts an unremediated audit, and a quiet fleet is
exactly the tick when an audit is waiting and there is a window to spend it
in. It is script-first — no model decides anything, because the label *is*
the decision. `hakux-cloud.timer` stays disabled; nothing here re-enables it.

`roles/cloud.md` is untouched, as the brief asked. Its numbered pickup order
is a fallback for a session started with no brief; every dispatched session
gets its unit named in the brief `cloud.sh` writes. Its rule 1 still says a
local lane's remediation is the board's to resume — that line is now stale
but harmless (the session is told which unit it holds), and the file is not
this lane's to edit. Worth one line from whoever next owns it.

## Clearing the state label, which is the other half of the outlet

The brief: "a label that is never cleared makes the same PR eligible
forever." The task text already told the session to remove `needs-audit-1`,
and the session is the one thing here that can forget. So the unit's tail is
now `cloud.sh finish <kind> <num>` instead of a bare `gh-label.sh rm`, and it
decides by what the session left behind:

- a successor state is on the PR (`needs-audit-2`, `needs-remediation`,
  `fold-ready`) → the label it was claimed under is stale. Remove it, clear
  the attempt counter.
- no successor → the unit did **not** finish. **Leave** the label, so the
  next tick claims it again, and say so on the PR.

Leaving it is what makes a retry possible, so it needs a bound, or the
outlet spends a window every 20 minutes on a PR that cannot be finished.
That bound is `$WORK/attempts/cloud-<kind>-<num>` with `LANE_MAX_ATTEMPTS`
and `LANE_ESCALATE_AFTER` from `models.env` — a lane's policy, unchanged,
including the escalation to `MODEL_LANE_ESCALATED` after three. Past the
limit the PR is labelled `blocked:needs-owner`, and `pr_by_label` skips that
label, so the outlet *moves on to the next unit* rather than stalling on this
one. The refusal runs before any git or worktree work: it costs nothing.

## What I checked, and what the checks would have missed

Sixteen checks, written as an append to `selftest.sh` and now carried
unchanged in `selftest.d/98-audit-outlet.sh`. Against `origin/master`'s
`cloud.sh` and `board.sh`, **14 of the 16 fail**. The two that pass are paired guards — "a session that set no
successor does *not* get the label cleared" and "no session is started for a
refused PR" are both true of code that does nothing at all — and each sits
beside a discriminating partner asserting on the *output words* (the PR
comment, the `blocked:needs-owner` POST), because an exit code or an absence
goes green for free.

Two things worth recording:

- **The head-branch filter lives in a `--jq` expression, which a shim does
  not run.** A shim that just returns a row would have passed against the
  old file and measured nothing. The shim emulates exactly the property
  under test: a query whose command line contains
  `startswith("lane/cloud-")` returns nothing for `#102`. That is a real
  discriminator — the old file's jq string is expanded before `gh` is
  called, so the prefix genuinely is on the command line.
- **The ordering check caught itself.** "`cloud.sh` is dispatched before the
  `nothing actionable` exit" first failed against the *correct* file,
  because the comment I wrote three lines above the dispatch contained the
  words `nothing actionable` and `grep -n | head -1` found that instead.
  The check now anchors on the `say "nothing actionable"` call. A pattern
  matched against prose that describes the mechanism is not matched against
  the mechanism.

The selftest's existing `cloud.sh` checks (detached worktree, `HEAD:<branch>`
push, "no claim path exits without saying why") all still pass — the detached
worktree contract from PR #125 is kept verbatim.

## What I did not do, and what the next lane should not repeat

- **`lane.sh` is untouched** and was never in this lane's files. The unit
  rename is what makes that work; do not "tidy" it back to `hakux-cloud-*`
  without moving the count somewhere both scripts read.
- **`install-host.sh:28` still enables `hakux-cloud.timer`.** Not this
  lane's file, so I left it. It is now the only thing that could resurrect
  the second trigger, and it takes one word to fix. A double trigger is not
  *harmful* — the claim label and the cap make a second firing find nothing
  — but it is a mechanism nobody is watching, which is how this defect
  happened. Worth a one-line follow-up.
- **`status.sh:95` lists running units with the glob `hakux-cloud-*`**, which
  now matches nothing; the sessions appear under "Lanes running" instead.
  Not this lane's file. No information is lost, but the "Cloud-class
  sessions" heading will say nothing is running while one is. Same one-line
  follow-up.
- I did **not** add a second cap, a second timer, or a second label reader.
  If a future brief asks for "just a small separate job for X", that is the
  shape this lane deleted.

## Cost

The `jobs/selftest.sh` gate takes about ten minutes on this host, not
seconds: `arms.sh` runs eight times and each run does
`git fetch origin master '+refs/heads/lane/*:...'` against the network, with
140 worktrees and every lane branch on the remote. That is pre-existing and
nothing to do with this change, but budget for it — I burned two full runs
before noticing and iterated on the new block through a throwaway harness
that extracted the block from `selftest.sh` (never a copy of it) and ran it
alone. Someone should make `arms.sh`'s fetch skippable under selftest; the
gate being slow is the gate being skipped.
