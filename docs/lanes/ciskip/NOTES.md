# lane.ciskip

Two harness defects, each of which cost several PRs on 2026-09-18/19. Both are
small; the interesting part of each is the half that is easy to get wrong.

## 1. The retired skip-ci marker is in no role file

#101, #123, #129 and #139 each stalled on a head commit whose message carried
the marker. GitHub then creates **no workflow run at all** -- not a skipped
one -- so `statusCheckRollup` comes back empty, `fold.sh`'s `ci_green` maps
that to `NONE`, and the fold correctly refuses to fold a head nothing built.
Each of the four needed a person to push an empty commit.

`AGENTS.md` retired the marker on 2026-09-18 (CI is free on this public
repository), and `fold.sh` already explains all of this in the comment it
posts when it sees `NONE`. But a lane's system prompt is its **role file**,
and `grep -c "skip ci"` was 0 in both `roles/lane.md` and `roles/cloud.md`:
the lanes were copying the habit out of the repository's own history, and the
only thing telling them not to was a comment they see after they have already
done it.

Added to the `Never` section of both. Two things had to be in the wording:

- it is not a hint to CI, it is the absence of CI, and the fold cannot fold a
  head with no run; and
- **do not quote the marker either**, not even to explain the rule. GitHub
  matches it anywhere in the message, body included, so the empty commit
  pushed to restore a missing run suppressed that very run on 2026-09-18.
  That second half is why both files name the marker in prose and neither
  writes the literal string -- a role file that spelled it out would be
  quoted into a commit message by the next lane that copied the rule.

## 2. A board-level gate failure poisoned an innocent PR's head

`fold.sh` wrote `$F/failed/$pr-$head` on **any** preflight failure, and that
marker is permanent: the head is never tried again. But preflight's `coverage`
and `territory` gates read the board -- both go through `board_files.py`,
which loads from `origin/board` -- and not the PR's diff at all. When the
board opened `decision-needed` #138 the coverage gate went red for every fold,
and #123, #124 and #130 were each written off on a head that was complete,
green and innocent. The board fixed its own row one tick later and the gate
went green: the failure was transient by construction, and only the marker
outlived it. The three folded when a person deleted the markers by hand.

Now: a failure in **only** those gates is logged and retried next tick; any
other failed gate, alone or alongside them, still earns the marker.

**How the gate is identified.** The brief said not to parse prose if an exit
code or a flag would do. Neither would: `preflight.sh` exits 0/1/2 for the
whole run, and it is not this lane's file to give it a per-gate code. What it
does have is a machine-readable **column** -- `step()` pads the gate name to
28 characters and `bad()` prints `FAILED` and nothing else on the line. So the
detection anchors on a line that *begins* with the gate name and *ends* with
FAILED, which also excludes each gate's own indented output, where the word
appears often. `selftest.d/91-fold-transient.sh` asserts that shape against
the real `preflight.sh`, so a rename or a reformat there fails the selftest
instead of silently turning a board gate into a tree gate.

**Three things the next lane should not have to rediscover:**

- `board files` is **not** one of the board's gates, despite the name. It is a
  gate about what this checkout edited, which is exactly the thing a lane can
  cause. There is a check for that specific wrong answer.
- A log that names no failed gate at all (preflight died early, `exit 2` on a
  bad argument, the run was cut off) is classified as the **tree's**, not as
  transient. An unreadable failure must not become an infinitely retried one.
- `board_files.load()` *prefers* `origin/board` but *falls back* to the
  working-tree copy, so while that transition lasts a PR that edits the two
  board files genuinely can fail these gates by itself -- and `--allow-tracker`
  has stopped asking by the time the fold runs preflight. So the fold also
  checks `origin/master...origin/<branch>` for those two paths, and a PR that
  touches them gets the marker as before.

A permanently-parked PR with no trace off the host is the #102 failure over
again, so a board gate still red after `BOARD_GATE_STUCK_SECS` (default 7200,
four ticks) is reported on the PR -- once per head -- and the comment says
plainly that the head is *not* marked failed and that the lane need not push
anything. That mirrors the ledger `ci_report` already keeps for `PENDING`.

## Testing

`docs/testing/jobs/selftest.d/91-fold-transient.sh`, 29 checks, self-contained:
its own `gh` shim, its own git repository (a bare origin, a master, an innocent
lane branch and one that edits `territory.toml`) and its own `$HAKUX_WORK`. It
drives the **real** `fold.sh` through a real merge in a real worktree; the tree
it merges into carries a stand-in `preflight.sh` that prints the real one's
gate column and fails whichever gates the fixture names. Building psh_differ
and reaching `origin/board` for every scenario would have made this untestable,
and the column is the whole interface -- which is why the last four checks
assert that interface against the real file.

`fold.sh preflight-verdict <log>` exists for the same reason `resolve-notes`
does: it is the decision without the merge, so the cases a fixture would make
expensive (an empty log, a mixed failure, `board files`) are cheap.

**Falsified against the file it replaces**, not by reasoning: `origin/master`'s
`fold.sh` placed in a symlink tree (never at the real path) and the fragment
run against it -- 17 of the 29 checks fail, and not all for one reason. The
e2e ones fail because the old file writes the marker; the verdict ones fail
because the mode does not exist. The controls stay green against the old file,
which is what makes them controls: a real tree-gate failure still writes the
marker, a mixed failure still does, a board-file-editing PR still does, and
nothing folds. Runner kept at `/tmp/ciskip-falsify.sh` (not committed --
it hardcodes this worktree's path).

## Not done here

`AGENTS.md` mentions the marker twice and is correct; it is not this lane's
file and needed no change. Nothing under `hw/`, `target/`, `accel/`,
`android/` was touched. No prediction: harness script, no pixels claimed.
