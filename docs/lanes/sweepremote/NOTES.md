# lane.sweepremote -- both sweeps called the remote lane dead

Brief only, no tracker issue. Harness defect found by dry-running the two new
sweeps through their own timer path before their first unattended fire.

## What was wrong

`lane.remote` is a cloud session on `claude/docs-tooling-agentic-coding-u152m1`.
It has **no local systemd unit by design** and, between PRs, no open PR either.
Both sweeps decided a lane was dead from exactly that absence.

- **`issue-sweep.sh`** called a territory claim stale when the lane had "no
  unit and no open PR", and handed the finding to the board to release. On the
  live board that was four of `lane.remote`'s claims (#158, #62, #60, #34).
  Releasing a live lane's territory is how two agents end up editing one file.
- **`pr-sweep.sh:189`** derived the lane name as
  `branch[5:] if branch.startswith("lane/") else ""`, so a `claude/*` head
  produced the **empty** lane name.

### One correction to the brief, measured rather than assumed

The brief says the empty lane name "feeds `emit("draft-strand", ...)` at :209
and `emit("regressed", ...)` at :241". It does not: **both** of those emits
are guarded on `and lane`, and the empty string is falsy. So for a head like
`claude/docs-tooling-agentic-coding-u152m1` the old sweep **under-reported** --
the PR fell out of two classes entirely and no actor, right or wrong, was ever
named for it. Nothing was misrouted to `handback.sh`.

The misroute is real for the **other** legal spelling. `remote = true` means
the conventional `lane/<row name>`, so the prefix strip yields a real lane
name, there is no `hakux-lane-<name>` unit (there is no host here to run one),
and the PR **is** emitted as a strand whose entire content is naming
`handback.sh` as its actor. `handback.sh` refuses it -- it asks
`remote_lane_of` first -- but a sweep that is correct only because another job
guards it is a sweep that is wrong and happens not to be paid for it.

Both shapes are in the fragment, and the `remote = true` one is what goes red
against master for the misroute claim. The `claude/*` one goes red for
under-reporting, which is what it actually did.

`jobs/remote-lane.sh` (lane.laneshape, folded 2026-09-19T23:59Z) already
answered both questions and neither sweep called it: `grep -c remote-lane
issue-sweep.sh` was **0**.

## What was measured, on the live board and not on a fixture

`bash docs/testing/jobs/issue-sweep.sh list` from this branch, against
origin/board at wave 127 and live GitHub, 2026-09-19:

| territory.toml | findings | `lane.remote`'s claims |
|---|---|---|
| the board as it stands | 11 | #158, #62, #60, #34 all reported stale |
| the same file, `remote = "claude/docs-tooling-agentic-coding-u152m1"` added to `[lane.remote]` | 7 | none reported |

Every other lane's finding is byte-identical between the two runs. The four
that drop out are exactly the four this lane is about, and the delta is the
one field.

## THE FIX IS INERT UNTIL THE BOARD WRITES ONE FIELD. Read this before closing anything

`[lane.remote]` on origin/board **does not carry a `remote` marker today**:

```
$ cd docs/testing && bash -c '. jobs/remote-lane.sh; echo "$(remote_source)"; remote_map'
board
            <- an empty map. Not a read failure: a board with no marked lanes.
```

So this branch changes the mechanism and not yet the outcome. The issue sweep
will keep reporting those four claims on its 07:41 and 19:41 fires until the
board adds, to `[lane.remote]`:

```toml
remote = "claude/docs-tooling-agentic-coding-u152m1"
```

A lane must not write that row (`roles/lane.md:79`, and the lane contract), so
it is asked for here and in the PR body rather than done. The second table row
above is what the sweep does the moment it exists -- that run is the evidence
the field is the only thing missing, not a prediction about it.

### Two actors on this host already disagree about whether that lane exists

`check_coverage.py` runs in **every lane's preflight and in every fold**. Run
from this branch, 2026-09-19, it says:

```
coverage ok (...); 2 lane(s) RUNNING (fold, remote)
  -- do not claim their files or advise folding them
```

It gets that from `$DISPATCH_DIR/fleet/remote.json` (`"state": "running"`,
`"worktree": "cloud"`, dispatched 2026-09-14). So at the same moment, on the
same host: the coverage gate tells every lane **not to claim `lane.remote`'s
files**, and the issue sweep tells the board those same claims are stale and
should be released.

**The fleet row is not the fix and must not become one.** It is a record of a
dispatch, written once in September and never refuted -- exactly the "file
that records what was true once" that `lane_live`'s own docstring says
liveness must never come from. It is cited here only as the contradiction:
whichever oracle is right, two actors on one host must not answer "does this
lane exist" in opposite directions, and the `remote` marker is what makes them
agree.

## How the two sweeps judge a remote lane now

A lane a `remote` row names is **not dead for want of a unit**; there is no
host here to run one. What this host can see of it:

- an open PR on **its own branch** -- not on `lane/<name>`, which is not its
  branch and never will be. This was the sharpest of the new checks: the old
  predicate and the new one differ only here when the tip is old.
- that branch's tip, fetched and read with `git log -1 --format=%ct`. A lane
  that has pushed is unambiguously working. `ISSUE_SWEEP_REMOTE_QUIET_SECS`,
  three days, set beside `AVAIL_SECS` and **above** the `limits.env` source so
  the owner's file can raise it.
- a tip that **cannot be read at all** is "cannot tell", not "dead": the
  branch may be on a fork or on no remote this host can reach. The report says
  `(tip unreadable here)` rather than going quiet about it.

**Its comments are the other signal the brief named and they are deliberately
not implemented.** There is no cheap query for "has lane.X commented anywhere
recently" -- it is a search across every open issue and PR, per lane, twice a
day -- and the answer is strictly weaker than the branch tip: a session can
comment without having done anything and cannot push without having. If the
tip ever stops being enough, the thing to add is the search; the paragraph
above `remote_rows` in `issue-sweep.sh` is what to re-read first.

## The constraint that mattered most, and why it disables the whole tick

`remote_authoritative` is rc 0 **only** for a board read. `board_files.load()`
falls back to the fold-lagged in-tree `territory.toml` and **returns it
successfully**, and that copy reaches a tree only when some later fold carries
it over -- so it is precisely the copy missing a `remote` marker the board has
just written. Through `remote_readable` that state is indistinguishable from a
clean read, and acting on it reproduces this entire defect with no symptom.

So a map that is not the board's refuses the **whole tick**, not just the one
class. Two reasons, and the second is the load-bearing one:

1. Both sweeps take outward actions keyed on which lane a head belongs to --
   `pr-sweep` runs `cloud.sh finish` and comments on PRs unattended every
   three hours; `issue-sweep` hands rows to the board. "I do not know whose
   branch this is" is not a state in which to do any of that.
2. Every class in `issue-sweep` compares live GitHub against the board's
   files, so on a fold-lagged board it reports rows the board fixed hours ago
   in **every** class at once. Its own header already said so four paragraphs
   above the code; this enforces it.

The refusal names the source it got and **both** ways out. `git fetch origin
board` is the ordinary one. The second matters because a gate that can refuse
forever must name every exit: on a host that has no `board` branch **at all**,
the fetch cures nothing -- the ref does not exist -- and that host would be
refused on every tick, twice a day, for a fault it cannot fix with the command
it was given. `HAKUX_BOARD_REF=` is the second exit, and `remote-lane.sh`
already honours it as a deliberate choice rather than a fallback. Both strings
are checked.

An unswept tick costs three hours; the other direction costs a released claim.

**A gate that refuses everything is the same defect with its sign flipped, so
the host was checked rather than assumed.** The timers do not run this
worktree: `run-trunk.sh` execs the job from `$WORK/jobs-wt`, a detached
worktree sharing `$REPO`'s ref store. Measured there, 2026-09-19:

```
$ cd /home/justin/hakux-work/jobs-wt/docs/testing
$ . jobs/remote-lane.sh; remote_source; remote_authoritative && echo yes
board
yes
```

So both sweeps pass the new gate on the host as it stands, and `pr-sweep`'s
new `git fetch origin board` is what keeps that true on a checkout that has
not fetched the ref yet.

### The fetch that makes the cure reachable

`pr-sweep.sh` never fetched `board` at all, so on a host whose `$REPO` lacked
that ref the new gate would have refused every tick forever. It fetches it
now -- **as a second, separate `git fetch`**. `git fetch origin master board`
exits 128 and updates **nothing** when either name matches no remote ref, so
folding them into one command would make a host with no `board` branch lose
the trunk fetch too, and with it the stale-red class. `issue-sweep.sh` had
them folded together already; it is split for the same reason.

## What the next lane should not repeat

- **Do not judge a remote lane by `lane/<name>`.** Two of the three obvious
  liveness facts are about the wrong branch, and the third is about the wrong
  host. Ask `remote_branch_of` and use what it returns.
- **Do not use `remote_readable` for a decision.** It answers "did something
  parse". Both sweeps discuss it in their headers to say why they do not call
  it, so a grep for the name matches the prose that forbids it --
  `78-sweep-remote.sh` therefore greps for a *call*, on a comment-stripped
  file, in both directions.
- **`len(out) <= 2` was a sentinel that could not survive a new header line.**
  `issue-sweep`'s "Nothing stuck" verdict was gated on the output being
  exactly the two header lines; adding the remote-lanes line would have
  silently removed the quiet verdict from every clean run. It counts `### `
  headings now, which is what `n_find` counts in bash, so the two agree by
  construction instead of by being edited together.
- **A fixture for either sweep now needs a whole `docs/testing`, not a
  `jobs/`.** Both source `remote-lane.sh`, which finds `board_files.py` at
  `dirname $J`. Without a `board_files.py` and a `territory.toml` beside the
  jobs dir the map reads `unreadable` and the tick refuses for a fault the
  fixture invented. `76-pr-sweep.sh` needed exactly that plus
  `HAKUX_BOARD_REF=` and nothing else; `77-issue-sweep.sh` already had it.

## The checks, and the mutants they are measured against

All new checks are in `docs/testing/jobs/selftest.d/78-sweep-remote.sh` -- a
fragment of its own, not an append to 76 or 77, for the reason `selftest.sh`'s
own header gives: one file per lane cannot collide at fold time.

The branch tips are **real**. The fixture is a bare origin with a branch
committed a minute ago and one committed a month ago, read by the sweep with
the same `git log -1 --format=%ct` it runs on the host, and a leg asserts the
two tips really are a month apart before anything depends on it.

Every exemption runs as a pair, because "a live remote lane is not reported"
is satisfied by a sweep that reports nothing at all -- which is this defect
wearing the face of its fix:

| the claim | how it is falsified in the same run |
|---|---|
| a live remote lane's claim is not stale | delete `remote = ...` from that one row: it is reported again, by name, in the old words |
| a stale remote lane's claim still is | the month-old tip is reported, and says it is remote |
| an open PR keeps the claim | the PR is on `claude/stale-u1`; the same fixture with the PR on `lane/stalecloud` reports it |
| an unreadable tip is not a dead tip | a dead **local** lane rides in the same fixture and is still reported |
| an unreadable map acts on nothing | the same fixture with the board readable IS a finding, run immediately before |
| a fold-lagged map acts on nothing | `HAKUX_BOARD_REF=refs/nosuch`, which succeeds through `remote_readable` and must not through `remote_authoritative` |
| a remote draft never reaches handback | the stub records being called **at all**; an ordinary `lane/*` draft in the next case still calls it |
| a `remote = true` lane on `lane/<name>` is not a strand | the discriminating shape: this is the one master DOES misroute |
| a `claude/*` head with no row is still not a lane | it is neither `remote-draft` nor `draft-strand` |
| a missing `remote-lane.sh` refuses | a `jobs/` holding the sweep and `models.env` and nothing else |

### The falsification run, and the taxonomy of what survives it

The fragment was run against **master's** `issue-sweep.sh` and `pr-sweep.sh`
(`git archive origin/master docs/testing` into a scratch tree; master already
has `remote-lane.sh`, so every job there is the old one and only the sweeps
differ). Driven by a standalone harness rather than master's `selftest.sh`,
because that harness needs `$REPO` to be a real git repo two levels above
`docs/testing` and an extracted tree is not one; the fragment's whole contract
is `$T`, `$HERE`, `$TESTING`, `check/ok/bad` and shims it builds itself.

**65 checks: 40 fail against master, 25 pass.** The 25 are:

- **5** fixture integrity and stub safety (the two tips really are a month
  apart; each stub is a real file and not a symlink into the repository).
- **8** must-not-move legs about **local** lanes -- the dead local lane is
  still reported, in the old words; an ordinary `lane/*` draft still reaches
  `handback.sh` and is still called a strand.
- **2** positive controls that must pass under both, and exist so the mutant
  beside them cannot be satisfied by a sweep that has simply stopped working.
- **10** negative halves of a pair, true under both codes **for different
  reasons**. The sharpest: "a remote lane's draft never reaches `handback.sh`"
  passes against master too -- because master emits no class at all for a
  `claude/*` head, not because it routes it anywhere correct. That is exactly
  why the `remote = true` shape was added; it is the leg that separates
  "silent for the right reason" from "silent for the wrong one".

40 + 25 = 65. If those three numbers stop reconciling, this paragraph is the
thing to re-measure, not to repair by arithmetic.

**Two checks in the first draft of this fragment were vacuous, and the
falsification run is what found them.** They asserted that an unreadable board
map makes `issue-sweep` print no `### ` heading -- but they ran it in `run`
mode, whose stdout is only the one-line `say` summary, because the report goes
to a file. "No headings on stdout" is true of a run tick under any code: a
falsifier its own subject forces true. They are in `list` mode now, whose
stdout **is** the report, and the destructive half (unread findings left
alone, no report page written over the last one) is asserted separately
against a `run` tick.

`bash docs/testing/jobs/selftest.sh`: green, 943 checks before this branch and
1008 after.

## Files

- `docs/testing/jobs/issue-sweep.sh`
- `docs/testing/jobs/pr-sweep.sh`
- `docs/testing/jobs/selftest.d/78-sweep-remote.sh` (new)
- `docs/testing/jobs/selftest.d/76-pr-sweep.sh` (fixture only: the scratch
  tree needs a `board_files.py` and a `territory.toml`, and `HAKUX_BOARD_REF=`)
- `docs/lanes/sweepremote/NOTES.md`

`remote-lane.sh` is `[lane.laneshape]`'s and is **sourced, not edited**.

## The territory rows, which are the board's and not mine

**Resolved while this lane was working.** At wave 127 `[lane.sweeps]` still
held `pr-sweep.sh` and `issue-sweep.sh` (PR #174 MERGED, unit gone), and it
also named `selftest.d/73-pr-sweep.sh` and `74-issue-sweep.sh`, which do not
exist -- they were renumbered to `76-` and `77-` at fold, so that row had been
naming two absent paths since the fold that created them. At **wave 128** the
board released it and wrote `[lane.sweepremote]` holding both sweeps. Verified:

```
docs/testing/jobs/pr-sweep.sh                   -> ['sweepremote']
docs/testing/jobs/issue-sweep.sh                -> ['sweepremote']
docs/testing/jobs/selftest.d/78-sweep-remote.sh -> unclaimed
docs/testing/jobs/selftest.d/76-pr-sweep.sh     -> unclaimed
docs/lanes/sweepremote/NOTES.md                 -> unclaimed
```

No collision on any file in this PR, and `check_territory.py` is green.

**Still open, and it is the one this branch waits on: `[lane.remote]` carries
no `remote` marker at wave 128 either.** The board ticked at 2026-09-20T03:20Z
and wrote my row in the same wave without writing that field, so it is not a
matter of the board not having ticked yet. See the section above for the exact
line and the measurement that shows it is the only thing missing.

Prediction: none -- this is harness code and touches no renderer path, so no
arm can see it.

## Why attempt 1 stopped, and what the second session found changed

**It stopped waiting, correctly, in the one state the harness had no actor
for.** At 2026-09-20T03:50Z every item of `roles/lane.md`'s definition of done
was finished except the last: the branch was pushed, `preflight.sh` was green,
the PR body's `Files:` matched the diff, this file was written and the
prediction was declared `none`. What was left was CI on `03f5dc5a3d`, which
takes about ten minutes and which a session has no way to sleep through. So it
posted `[lane.sweepremote] waiting:` naming the sha and the signal, and ended
-- and `jobs/handback.sh` resumed it at 05:51Z with "CI GREEN on that sha".

That is the shape this lane should be read as: **nothing was unfinished, and
nothing here was re-measured on the resume.** The one gap was that a finished,
green PR was still a draft, which `board.sh`, `fleet.py` and `fold.sh` all
skip. The handback job exists for exactly that gap; without it this branch sits
green and invisible indefinitely. If you resume a lane of your own in this
state, the work to do is the *last* item and nothing else.

Re-checked at the top of attempt 2, because the whole outcome of this PR turns
on one of them:

| | attempt 1 (03:50Z) | attempt 2 (05:5xZ) |
|---|---|---|
| CI on `03f5dc5a3d` | pending | **GREEN** (build, build, selftest) |
| mergeable vs master | -- | `MERGEABLE` / `CLEAN`, 52 behind and no conflict |
| `preflight.sh` on this branch | passed | passed, territory and coverage both ok |
| `remote_source` / `remote_authoritative` | `board` / rc 0 | unchanged |
| `remote` marker on `[lane.remote]` | absent, wave 128 | **still absent, wave 129** (`updated_utc` 2026-09-20T03:40Z) and `remote_map` is still empty |

So the request in the PR body and in the comment above it is still the live
one, and it is still the board's to make, not this lane's. Nothing on the
branch changed on the resume but this section.
