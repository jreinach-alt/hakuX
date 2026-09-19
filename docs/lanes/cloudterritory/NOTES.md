# lane.cloudterritory -- the audit outlet writes its own territory row

## What was wrong

`jobs/cloud.sh` claims a unit -- label `claimed:cloud`, a `[job.cloud]`
comment, a brief, a worktree, `systemd-run` -- and wrote no `territory.toml`
row. `$WORK/logs/board/tick.log` carried seven `FAIL: 1 lane(s) are RUNNING
with no territory row` in one night, five of them naming a unit this script
started (`cloud-audit2-102`, `cloud-remediate-102`, `cloud-audit2-115`,
`cloud-remediate-115`, `cloud-remediate-128`). Every one of those woke a board
tick -- a model session against the account's shared window -- to write a row
the claim already had in hand.

The window is not the whole cost. `check_territory.py` cannot detect a
collision with a lane that is not in the file, so between `systemd-run` and
the next board tick the session was invisible to the one gate that exists to
stop two sessions writing one file.

## What it does now

`cloud.sh` writes the row where it already writes the label and the brief,
and `cloud.sh finish` removes it where it already drops the claim. Shape and
branch are the board's own (`issues` / `files` / `standing` / `note` on the
orphan `board` branch); the note says who wrote it and what removes it.

- **Before `systemd-run`, not after.** `fleet.py`'s own account lists "a row
  written and validated but COMMITTED AFTER DISPATCH" as one of three
  variants of this defect -- that lane spent its life against a table where
  its files sat in `[free]`. Pinned by a check on the call order in the
  script, because the dispatch and the push land in two different logs.
- **No worktree.** `hash-object` + a throwaway index + `commit-tree` + `push`.
  A `worktree add` is seconds of IO inside the window being closed, and a
  checkout is the one step that can leave a half-written file behind.
- **A row that cannot be written does not stop the dispatch.** The unit is
  still worth running; the failure is said on the PR and in the tick log, so
  the board-tick fallback is no longer the silent path.
- **`systemd-run` failing removes the row again.** The unit's tail is what
  removes it, so a unit that never started would leave a claim with no agent
  -- `fleet.py` prints that as `ghost` and sets no rc, so nothing would ever
  fail on one accumulating per audit.

## What it claims, and the one place I did not follow the brief

An audit claims `files = []`: it reads a diff and writes
`docs/audits/<pr>-pass{1,2}` on the PR's own branch. The brief says a
remediation "genuinely holds the PR's files and should say so", and it does --
but **narrowed to the paths no other row already names**, with every omission
written into the `note` beside the holder.

That narrowing is not tidiness. `check_territory.py` FAILs on a path claimed
by two lanes, and on a path claimed while `[free]` lists it; that FAIL makes
`preflight` red for **every lane on the repository**. A remediation's PR comes
from a lane, and that lane's row usually still holds exactly those files -- so
the unnarrowed version would have turned a quiet board red in the common case,
which is a new outage caused by a bookkeeping write. The collision it would
have reported is already visible through the row that holds the path; the
session's existence was the thing nothing could see, and the row now shows it.

Where the originating lane's row is gone (folded, retired), the remediation
does claim the files and gets real protection. Matching is exact string
equality, which is the rule `check_territory.py` itself uses -- so
`target/**` is not read here as covering `target/foo.c` either.

`issues` comes from the PR's closing references and from the `Issue: #n` the
lane contract puts in the body header -- **first two lines only**, so a number
mentioned in prose further down does not become a coverage claim
(`check_coverage.py` treats a lane's `issues` as coverage).

## The race: two jobs write this file now

There is no lock, and there is deliberately none.

The board regenerates `territory.toml` from open lane PRs on a tick and pushes
to `board`; `cloud.sh` now appends one row on a claim and pushes to the same
branch. The interleaving that matters is: cloud fetches, a board tick pushes,
cloud pushes. **That push is not a fast-forward, so git refuses it** -- the
default for a branch ref -- and the loop re-fetches and re-applies the row to
the tip that actually exists, three times before giving up. Nothing is ever
forced. A lost update here is a lane nothing can see, which is the defect
being closed; reintroducing it from the other side would be the worst possible
outcome of this change, so it is driven in the selftest by a real
`pre-receive` hook that moves the branch under the claim and rejects once.

Costs and residual risks, stated rather than assumed:

- **The claim gets one fetch, one push and one `gh pr view` slower** (~1-2s on
  the host). The race window it widens is *nothing*: the row is written before
  `systemd-run`, so the session-with-no-row window is now zero rather than
  up-to-one-board-tick. A concurrent board tick costs at most three retries.
- **The board can still drop the row on its next regeneration.** It rebuilds
  the file from open lane PRs, and a cloud unit is not always one. Nothing was
  lost relative to today (today there is no row at all), but if a board tick
  regenerates while a cloud unit runs, the row can vanish and the next tick
  reports it again. The durable fix is for the regeneration to preserve rows
  whose unit is active; that is the board's file, not this lane's.
- **`wave` is not bumped.** It records an allocation decision by the board and
  is monotone-checked; a bookkeeping row is not a new wave, and bumping it
  from two writers is how a monotone counter goes backwards.
- **Split-pair issues are not guarded.** `check_territory.py` refuses two
  lanes holding issues split from a common parent (its own `SPLIT` list). The
  issue path here claims `issues = ["<n>"]`, so it can in principle create
  that FAIL -- exactly as a board dispatch of the same issue would, and it is
  a true statement about a real double-assignment when it fires. Duplicating
  the `SPLIT` constant into `cloud.sh` to pre-empt it would be a second copy
  of a rule that drifts.

## A rejected push is not evidence of a race

The first version logged every failed push as "origin/board moved while this
row was being written". That is the usual cause and it is not the only one: an
expired credential, a protected branch and a failed unpack all arrive here as
`[remote rejected]`, and the message would have sent the next reader looking
for a board tick that never ran. `git`'s own text now goes into the tick log
verbatim (truncated to 200 characters, newlines flattened) and the
classification is left to whoever reads it. The retry is unchanged -- three
tries either way, because a credential failure costs two extra pushes and a
misdiagnosis costs a session.

## For the next lane

- Do not re-derive whether the row should be a `[retired.<name>]` entry
  instead of a deletion. The board writes `retired.*` for a lane whose work
  merged; a cloud unit ending is not a merge, and one block per audit is how
  this file grows without bound. It is deleted, and the tick log plus the
  `[job.cloud]` comments keep the trace.
- The `board` branch is written by plumbing here, never checked out. If you
  add a second field to the row, add it in the Python heredoc in `cloud.sh`
  and extend the "nothing else moved" assertions with it -- the validation is
  what makes a textual edit to a 90%-comments file safe, and it is the only
  thing standing between this and the three board-file breakages that came
  from slicing these files by hand.
- `71-cloud-territory.sh` builds real git repositories, not shims, because
  the property under test *is* git's refusal of a non-fast-forward push. It
  cleans up its worktree and the `cloud-remediate-102` attempt counter that
  `98-audit-outlet.sh` reads afterwards; keep that if you extend it.

## Falsification

`71-cloud-territory.sh` was run against the `cloud.sh` this replaces
(`origin/master`'s copy, in a symlink tree of `docs/testing` so the real file
was never swapped -- a falsification that leaves the old code in the tree has
cost a lane its whole session before):

    selftest: 11 passed, 15 failed      # against origin/master's cloud.sh
    selftest: 313 passed, 0 failed      # the full run against this branch

**The 11 that pass against the old file are not evidence of anything and are
not meant to be.** They are the damage-guards -- "the other lane's row is
untouched", "the board branch does not move", "master is not touched",
"finish removes the row" -- and every one of them is vacuously true when
nothing is written at all. Each of the 15 that fail asserts something
positive: that the row exists, that it names the PR's issue and files, that
the omissions are in the note, that a refusal is reported, that a lost race
is retried and the concurrent writer's row survives.

Two defects were found by running it rather than by reading it, both of which
would have shipped silently:

- `python3 - "$kind" <<'PY'` with the PR's JSON **piped in**: `python3 -`
  reads its program from stdin, so the heredoc replaced the pipe and every PR
  parsed as `{}`. The row was still written, with `issues = []` and
  `files = []`, and looked entirely plausible. The JSON goes in on argv now.
- The selftest's own concurrent-board-tick hook could not move the branch: a
  receive hook runs with the incoming objects quarantined and git refuses
  every ref update from inside it. The hook rejected the push, the branch did
  not move, the retry re-pushed the same commit and succeeded -- a green test
  of nothing. It unsets `GIT_QUARANTINE_PATH` now, and the two checks that
  were passing for that reason fail against the old code as they should.
