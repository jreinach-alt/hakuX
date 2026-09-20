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
  produced the **empty** lane name. That fed two classes: `draft-strand`,
  whose entire content is naming `handback.sh` as the actor that should resume
  the PR, and `regressed`, which was guarded on `and lane` and therefore never
  fired for such a head at all.

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

The refusal names the source it got and the one command that cures it
(`git fetch origin board`). An unswept tick costs three hours; the other
direction costs a released claim.

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
| a `claude/*` head with no row is still not a lane | it is neither `remote-draft` nor `draft-strand` |
| a missing `remote-lane.sh` refuses | a `jobs/` holding the sweep and `models.env` and nothing else |

`bash docs/testing/jobs/selftest.sh`: green, 943 checks before this branch and
978 after.

## Files

- `docs/testing/jobs/issue-sweep.sh`
- `docs/testing/jobs/pr-sweep.sh`
- `docs/testing/jobs/selftest.d/78-sweep-remote.sh` (new)
- `docs/testing/jobs/selftest.d/76-pr-sweep.sh` (fixture only: the scratch
  tree needs a `board_files.py` and a `territory.toml`, and `HAKUX_BOARD_REF=`)
- `docs/lanes/sweepremote/NOTES.md`

`remote-lane.sh` is `[lane.laneshape]`'s and is **sourced, not edited**.

## The territory rows, which are the board's and not mine

Two stale rows on origin/board @ wave 127, said here rather than edited
(`roles/lane.md:79`):

1. **`[lane.sweeps]` still claims `docs/testing/jobs/pr-sweep.sh` and
   `docs/testing/jobs/issue-sweep.sh`** -- the two files this PR changes --
   while PR #174 is MERGED and the unit is gone. It also claims
   `docs/testing/jobs/selftest.d/73-pr-sweep.sh` and `74-issue-sweep.sh`,
   which do not exist: they were renumbered to `76-` and `77-` at fold, so
   that row has been naming two absent paths since the fold that created them.
2. **`[lane.remote]` carries no `remote` marker**, which is the one field this
   whole branch waits on. See the section above.

Prediction: none -- this is harness code and touches no renderer path, so no
arm can see it.
