# lane.stalecheck -- a PR red from a defect on master stays red forever

Harness defect, brief only, no tracker issue.

## The state, as found

`selftest.d/86-fold-regressed.sh` was broken on master for most of
2026-09-19. `selftest` is a required check, so every open PR that ran against
the broken tree carried `selftest:FAILURE`. PR #167 fixed it (`bb4b78689e`,
push run success 19:47:52Z) and master was healthy again, but #152, #153,
#155 and #163 still read FAILURE from runs that started at 17:14:32Z and
18:59:47Z. **GitHub does not re-run a pull request's checks when the base
branch moves.**

Nothing in the harness could reach them, and this was checked in the code
rather than assumed:

| job | why it did not act |
|---|---|
| `fold.sh` | gates on the head's CI being green; refuses correctly on the data it has |
| `handback.sh` | fires only on `needs-rebase`; these were `MERGEABLE`, no conflict |
| `board.sh` | picks up only PRs carrying no pipeline label (`board.sh:98`); these were labelled |

So the PR sat `fold-ready`, refused every tick, forever.

## What I built

**Detection, in `fold.sh`.** When the CI gate reads `RED`, the job now reads
the rollup a second time for *per-check* rows -- name, conclusion, start time
-- and compares every FAILING check's start against the commit time of
`origin/master`'s current head. All of them before it => the verdict is about
a base that has moved.

Conservative in every direction that matters: **any** failing check that
started after the trunk head makes the red live; a start time that is missing
or unparseable makes it live; a rollup with no failing entry in it at all
makes it live. The gate can only ever *add* an actor, never fold something.

**The action: a base merge, through `handback.sh`.** The PR loses
`fold-ready`, gains `needs-rebase`, and gets a cause file naming the failing
run and its timestamp. `handback.sh` resumes the lane with a brief that says,
first, *the red is not yours* -- with the run's own date to check.

**No re-run path, deliberately.** The brief had already measured it: #152's
`selftest` was re-run at 20:37:16Z, 50 minutes after the fix folded, and came
back red with the same ten checks, because the workflows check out the PR's
own head rather than `refs/pull/N/merge`. I confirmed the premise independently
before building on it -- `FR_LANE_SHA` (the fix) is on master and on none of
the four branches. A re-run therefore cannot refresh this verdict; only
bringing master into the branch can. **This also discharges the brief's CI
budget constraint outright: this change triggers no workflow run of its own.**
The one run it causes is the one the lane's own `git push` triggers, which is
a run the PR needed anyway.

## The two decisions worth arguing with

**1. `needs-rebase`, not a new label.** A new label would have to be added to
`ensure-labels.sh`, to `board.sh`'s state-label set (`board.sh:98`) and to
`fleet.py`'s (`fleet.py:176`) -- or a PR carrying only it would read as
*unlabelled* to the board and be handed `needs-audit-1` on top of work that
was already audited. Those are three files belonging to three other lanes
(`windowbudget`, `toolsmith`, and `ensure-labels.sh` unclaimed). The existing
label's own description is already the action -- "bring master into the lane
branch" -- and that is exactly and entirely what a stale red needs.

What *does* differ is what the lane must be told, so the cause file carries
`action=resume_stale_ci` and `handback.sh` overrides the row's action from
it, **against a whitelist** (the value comes out of a file and becomes the
command word of an invocation; an unknown value falls back to the row's own
action and says so in the log). A lane sent to resolve a conflict that does
not exist spends its session hunting for a defect of its own that is not
there -- which is the failure this whole change is about, one level down.

**2. Mergeability is not checked, although the brief's stated condition
includes it.** All four PRs that prompted this were `MERGEABLE`, but this gate
runs *before* the merge attempt, so a PR that is both stale-red and
conflicting never reaches `fold.sh`'s conflict path either and has no actor
for the same reason. The answer to both is the same base merge. Gating on
`MERGEABLE` would have left half the jam in place and paid a `gh` call for
the privilege.

## The lane that has exited

This is the case that actually bit: all four stranded lanes had **inactive**
units, so there was no session to resume. `handback.sh` already handles that
-- `systemctl is-active` false is not a skip, it is the normal path, and
`lane.sh resume` starts a fresh session in the existing worktree. Every check
in the new fragment runs against a `systemctl` shim that answers `is-active`
**false**, so that path is what is tested, not an incidental.

The one sub-case that was still silent: a lane whose *worktree or brief is
gone* cannot be resumed at all. It was told so in a PR comment and nothing
else -- and nothing polls a comment. It now also gets `blocked:needs-owner`,
the same label the attempts-exhausted path sets, so it appears in
`status.sh`'s roll-up. That is "say plainly it needs an owner", made visible
to something other than a human eye.

## Proof

`selftest.d/87-fold-stale-ci.sh`, 43 checks, drives the real `fold.sh` and the
real `handback.sh` against its own shims and its own `HAKUX_WORK`. The two
halves **share** that `HAKUX_WORK`: the cause file the fold half writes is the
one the handback half reads, so the join is what is tested, not two fixtures
agreeing with each other.

Both mutants the brief asks for, translated to the no-re-run design:

- stale red -> handed back exactly once per `(PR, trunk head)` pair; the trunk
  moving is a new pair and is said once more; **no merge worktree is ever
  created**, so the gate still holds.
- the fresh verdict is also red (run postdates the trunk head) -> reported as
  an ordinary live red, not handed back, no cause written.

Checks that can actually go red, i.e. the ones I wrote against my own likely
mistakes:

- **a stale failure alongside a live one is a live red.** The test is over
  *every* failing check. A build that looked at only the newest, or at "the
  one that matters", waves a genuinely broken PR through to a lane as "not
  yours".
- **a rollup gh calls RED with nothing failing in it.** An impossible row, and
  it is the check: `newest` starts at 0, which is before every trunk head
  there has ever been, so the empty case reads STALE unless it is refused
  explicitly. Every row in that fixture is plausible on its own.
- **`date -u -d ""` is not an error.** It is midnight today, at exit 0. An
  entry with no `startedAt` would have been compared as "started today" --
  which is *before* the trunk head on every evening this job runs, i.e. it
  would read STALE. Refused by hand, with its own check.
- **the `--jq` the shim bypasses.** `gh` runs it internally, so a typo in it
  is invisible to every behavioural check. The query is a single-line
  variable (`CHECK_ROWS_JQ`) that the fragment pulls out of `fold.sh` and runs
  through real `jq` against a canned rollup carrying an in-flight `CheckRun`
  (`conclusion: ""`), a completed FAILURE, and a legacy `StatusContext`.
  That is where the `//`-does-not-catch-`""` trap is reachable, and the check
  asserts the in-flight one reads `PENDING`.
- **the default survives the override.** A conflict cause under the same label
  still gets the conflict brief; a dispatch that swallowed the row's own
  action would pass every stale check above and silently retitle every real
  rebase.
- **an `action=` the cause file invents is refused**, named in the log, and
  the row's own action runs instead.

### The mutants, run

A check that cannot go red tests nothing, so each was run against a build with
the thing it names removed. Every mutant was applied to the real file, run,
and reverted with `git checkout --`, with `git status` confirmed clean after
each (everything was committed first, so the revert is exact and checkable).

| mutant | what was removed | reds |
|---|---|---|
| M1 | the "no failing check in the rollup" guard | `a rollup with NO failing check in it is never judged stale` |
| M3 | newest-failing → first-failing | `a stale failure ALONGSIDE a live one is still a live red` |
| M7 | the once-per-(PR, trunk head) ledger | 3 reds: the second tick, the new pair, and the second tick at the new pair |
| M4 | the `action=` override in `handback.sh` | 5 reds across the brief and the PR comment |
| M5 | the `action=` whitelist | `an action the cause file invents is refused` + the fallback |
| M6 | `blocked:needs-owner` on the gone-lane path | `its PR is labelled blocked:needs-owner` |
| M8 | the comparison inverted (`-lt` → `-ge`) | 19, including `it is not handed back`, which no other mutant could move |

M8 exists because of that last row. `it is not handed back` was green under
every mutant above -- correctly, and therefore without evidence. A check no
mutant can move is a check that has not been shown to check anything, so it
got one of its own.

The two negations in the fragment (`it is not handed back`, and the NONE
check's second clause) are now functions rather than `bash -c '! grep ...
"$VAR"'`. Both were in fact safe -- `SC_LOG` and `SC_COMMENTS` are exported --
but `85-fold-ci.sh`'s header records a mutant that caught exactly that shape
when the variable was not, and "safe because of an export three screens up" is
not a property worth depending on.

**M5 is why the fixture's invalid action is inert.** The obvious value to
write there is `rm -rf /`, and under M5 -- which is the mutant this very check
demands -- that string becomes the command word of a real invocation in
whoever's checkout runs the self-test. A name that is merely not a function
proves the same thing and cannot do anything. I wrote the dangerous one first
and changed it when I worked out what its own mutant would do.

### One bug the checks did not catch, and one the shell hid

`bash -n` caught an unterminated string: inside `"${cause:+... \`$TIP\`'s
head}"`, the apostrophe opens a single quote that runs to EOF. Bash is happy
with the same apostrophe in an ordinary double-quoted string; inside a
`${var:+word}` it is not. Reworded rather than escaped.

And `grep -c` prints `0` **and exits 1** when nothing matches, so
`grep -c ... || echo 0` appends a second zero and the comparison reads
`"0\n0"`. The fragment's comment-count helper had it; `85-fold-ci.sh`'s has
the same shape and gets away with it only because it never compares against
zero.

## Territory, stated rather than edited

Both files I changed are held by other rows on `origin/board`, and
`roles/lane.md:79` says the board writes those rows, not me. So, for the
board:

- `docs/testing/jobs/fold.sh` -- `[lane.branchprune]`. **Stale row**: its PR
  #137 is MERGED and its unit is gone. My change is the CI gate in the
  candidate loop; `prune_branch` is untouched.
- `docs/testing/jobs/handback.sh` -- `[lane.draftstrand]`, PR #153, OPEN and
  `fold-ready`. **Not folded when I started.** #153 also touches `fold.sh`
  (the `cands` early-exit, ~line 300) and `handback.sh` (a second, non-label
  cause). #163 (`lane.laneshape`) touches both files too.
- `docs/testing/jobs/selftest.d/87-fold-stale-ci.sh` -- a new file, held by
  nobody.

Separability, checked against the two open diffs rather than assumed:

| PR | `fold.sh` region | `handback.sh` region | overlap with mine |
|---|---|---|---|
| #153 | the `cands` early exit (~300) | header, `HANDBACK_ROWS` area, a strand pickup | header prose; adjacent, not the same hunk |
| #163 | `prune_branch` (~144) | `lane_name()` (~119) | none |
| mine | after `ci_green` (~310) and the RED arm of the candidate loop | the cause read and the action dispatch (~222), a new action function | -- |

If any of the three folds first, the rest should merge with at most a header
conflict. Mine is additive in both files.

## Attempt 2: why attempt 1 did not finish, and the merge

**Attempt 1 finished its work.** It was not cut off and it was not wrong: the
PR was open, non-draft, `fold-ready`, audited by the board (the `[job.board]`
diff-scope comment at 21:33:28Z), and green. What ended it was the trunk
moving underneath it -- `fold.sh` tried to fold `lane/stalecheck` at
`06cd5bfb30` on 2026-09-20 00:30:55Z, hit a conflict in `handback.sh`, and
handed the PR back on `needs-rebase`. So attempt 2's whole task was the base
merge, which is exactly the path this PR builds an actor for, one cause over.

The two PRs my separability table called out as unfolded **both folded** in
between, and both landed in `handback.sh`:

| PR | landed as | what it changed under me |
|---|---|---|
| #153 `lane.draftstrand` | `5eeea45328`, `eb61bf0fb7`, `033d927723` | the draft-strand cause: `resume_strand()`, the `$extra`/`quiet=`/`arm=` cause parse, the `$said` phrasing, the attempt-counter restore |
| #163 `lane.laneshape` | `8f43845b25`, `c61644cf8e` | `lane_name()`, the lane set derived from the board |

Six conflict regions, all in `handback.sh`; `fold.sh` auto-merged (#163 touched
`prune_branch`, mine is the CI gate -- the table's prediction of "no overlap"
held). Every region was **both sides kept**, because the two changes are two
causes sharing one job, not two takes on one cause:

1. header prose -- both sections, mine then theirs.
2. `resume_stale_ci()` and `resume_strand()` had been interleaved into one
   broken function by the merge driver (both open with `cat <<EOF\n\n---\n`,
   which is what it matched on). Split back into two whole functions.
3. the cause parse -- theirs is a `case "$label"` with a `draft-strand-*` arm;
   mine read `detail=`/`files=` and the whitelisted `action=`. Mine moved
   **inside the `*)` arm**, which is where it belongs: a strand has no cause
   file at all, so the override can only ever come from a label cause.
4. the gone-worktree path -- kept my `blocked:needs-owner` label, but took
   their `$said` for the comment's opening clause, since `$said` is the thing
   that knows how to phrase a strand as well as a label.
5. the dispatch -- kept their `attempts_before=` capture, but the invocation
   stays `"$act"`, not `"$action"`.

### The resolution was checked by mutant, not by the green

`selftest.sh`: **798 passed, 0 failed**, with both fragments running -- mine
(`87`, the two sections at "a red about a base that has moved" and "the stale
red's lane is told it is not its defect") and theirs (`99-handback-draft`).

But a green suite after a merge is weak evidence: region 5 is the exact line
M4 was built to move, and a resolution that dropped `$act` would still be
green on every check that does not need the override. So M4 was re-run on the
merged file. Two shapes, deliberately:

| M4 variant | what it removes | reds |
|---|---|---|
| dispatch only (`"$act"` -> `"$action"`) | the brief the lane reads | 4 |
| the override assignment (`act="$a"` -> `:`) | the brief **and** the PR comment | 5 |

5 is what this file recorded before the merge, and the narrower variant giving
4 is the scope difference, not a lost check: the PR comment's own
`case "$act"` (the "its red is stale" clause, vs "conflicting in") survives a
dispatch-only mutant and is the fifth red. Both halves of the override are
still live. Reverted with `git checkout --` after each, tree confirmed clean.

Diff against the new master is still exactly the four files, so the merge
pulled nothing of anyone else's into this PR's surface.

## What the next lane should not repeat

- **Do not build a re-run.** It was measured twice, once by the brief's author
  and once here. The workflows check out the PR's own head; a re-run replays
  the same broken tree, spends CI minutes, and comes back red identically.
- **Do not add a label for this.** Check `board.sh:98` and `fleet.py:176`
  first: a PR whose only label is outside those sets reads as *unlabelled* to
  the board, which will then label it `needs-audit-1`. The cost of a new state
  is three files across three lanes, and the action here was already the
  meaning of an existing one.
- **Do not test a timestamp gate without a "cannot be read" case.** `date -d
  ""` succeeds. So does `date -d "@0"`. A gate whose failure mode is "silently
  compares against midnight" reads STALE on every evening tick.
- `handback.sh` resumes **one lane per tick**, so four stranded PRs take four
  ticks (~2h) to clear. That is by design and is not worth changing; it was
  ~forever before.
- **Do not read the trunk head from `FETCH_HEAD`.** `$REPO` is the shared
  checkout and several jobs fetch in it; `FETCH_HEAD` is one file they all
  overwrite. A gate whose entire job is comparing a timestamp must not read
  that timestamp from a file another process can replace between the fetch and
  the read. Explicit refspec, then read the tracking ref by name.
- **A merge driver will interleave two functions that open alike.** Both
  briefs here begin `cat <<EOF` / `---`, so git matched on that and produced
  one function with two headers and no closing brace -- and `bash -n` catches
  it, but only because the heredocs happened not to balance. After resolving a
  conflict in a file of same-shaped functions, check `grep -n '^[a-z_]*() {'`
  against `^}` before trusting the suite.
- **Re-run the mutant for any line the resolution touched.** A green suite
  after a merge only says nothing *else* broke; the check that proves a line
  is load-bearing is the mutant that moves it, and the merge is precisely when
  that line was last rewritten by something that did not understand it.
- The self-test now does a real `git fetch` per `fold.sh` tick that sees a RED
  head (`85`, `86`, `91` all do), because those fixtures do not set
  `FOLD_TIP_SHA`/`FOLD_TIP_EPOCH`. That is a few seconds, not a defect, but it
  is why the run got slower. A fragment that drives a red head and does not
  want the fetch should set both.
