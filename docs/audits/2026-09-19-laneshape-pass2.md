# Audit pass 2 — PR #163, `lane/laneshape`: a lane is a branch with an open PR, not a branch named `lane/*`

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #163, branch `lane/laneshape`, tip **`c61644cf8e`** ("laneshape:
remediate audit pass 1"), over the merge `8233fe866a` that brought
`origin/master` in. Pass 1's subject was `8b185a925f`.
**Date** 2026-09-19. **Records** `2026-09-19-laneshape-pass2.{md,json}`.
**Pass 1** `2026-09-19-laneshape-pass1.md` — 2 HIGH, 3 MEDIUM, 4 LOW.

**CLEAN. All five scenarios closed. 2 HIGH, 3 MEDIUM, 4 LOW addressed; no new
HIGH or MEDIUM; one LOW-grade note about one fixture leg, recorded and not
raised.**

Pass 2 verifies that each pass-1 scenario can no longer occur, not that a
commit exists. So every number below was measured here, in this session, from
this tip — including the ones the remediation states, because a count that is
the evidence has to be re-run rather than read.

## How this pass was measured, so it can be repeated

Three runs of `docs/testing/jobs/selftest.sh`, each with **this branch's**
`selftest.d/98-lane-shape.sh` and otherwise a different tree, in scratch
worktrees (the old code never entered the live tree):

| tree | fragment | result |
|---|---|---|
| this tip `c61644cf8e` | its own | **727 passed, 0 failed**, exit 0 |
| `origin/master@11ddd94a66` | copied in | **684 passed, 43 failed**; the 98 section is 61 checks, **43 FAIL / 18 ok** |
| pre-remediation tip `8b185a925f` | copied in | **572 passed, 16 failed**; all 16 in the 98 section |

The runner (`selftest.sh` itself) is byte-identical between this tip and
`8b185a925f`, checked with `diff -q`, so the third run differs from the first
only in the eight files the remediation touched.

`gh pr view 163`: `mergeStateStatus` **CLEAN**, not a draft, head
`c61644cf8e`, all three checks **SUCCESS** (`build`, `build`, `selftest`).

---

## Scenario 1 (H1) — CLOSED

> *with an open PR whose head branch does not exist on the fixture origin, an
> `arms.sh` tick still advances `refs/remotes/origin/master` and still collects
> a prediction pushed to master in that tick.*

`arms.sh:140-225` now does three separable things, and I checked each against
the code rather than against the commit message.

1. **The trunk and `lane/*` are fetched first, alone** (`:181`), in an
   invocation that contains no name that can be missing — `$TIP` always exists
   and a wildcard that matches nothing is not an error. This is the half that
   makes the outage impossible rather than merely narrower.
2. **PR heads are fetched as `+refs/pull/<n>/head`** (`:189`), which GitHub
   publishes for an open PR whether the head is a fork or a branch somebody has
   since deleted. The number is validated as a number before it enters a ref
   path (`:186`), which matters now that the number and not the branch name is
   what is interpolated.
3. **A failed batch retries one spec at a time** (`:195-206`), so an
   unfetchable pull ref costs its own PR head and not the other PRs'.

The destination is `refs/remotes/pr/<n>`, its own namespace. I checked that
this is inert to every other job: no reader outside `arms.sh` walks anything
but `refs/remotes/origin/…` (`fold.sh:231` iterates `refs/remotes/origin/lane/*`,
`cloud.sh:377` and `lane.sh:212` `rev-parse` a named `origin/<branch>`,
`bootstrap-board-branch.sh:15` names `origin/board`), so a fork PR whose head
is called `board` can no longer land on top of the ref every job reads the
board from.

**The scenario is fired in the fixture and closed.** `98-lane-shape.sh:129-217`
builds a real bare origin with two open PRs, #777 (head present, published at
`refs/pull/777/head`) and #778 (`vanished-head`, present nowhere on that origin
and with no pull ref either), pushes a prediction to master *after* the
consumer's last fetch, and asserts:

* the consumer is genuinely behind before the tick (`:202` — the control, and
  it is a real one: without it the next two legs are green for a fetch that did
  nothing);
* `refs/remotes/origin/master` equals the pushed sha after the tick (`:205`);
* `master:docs/testing/predictions/trunk.json` is in `collect()`'s output
  (`:207`);
* the tick says `PR head unavailable … refs/pull/778/head` rather than going
  quiet (`:211`);
* `refs/remotes/pr/777` exists (`:216`).

Against `8b185a925f` — the tip that had the defect — **`:205`, `:207`, `:211`
and `:216` all fail**, and against master they pass for a different and correct
reason (master fetches no PR heads at all, so H1 was a defect this branch
introduced and master is the wrong falsifier for it). That distinction is
stated in `NOTES.md:437-446` and it is right.

## Scenario 2 (H2) — CLOSED

> *with `origin/board` unreadable and a working-tree `territory.toml` carrying
> no `remote` row for it, `fold.sh --apply` does not delete the marked branch
> and `lane.sh resume` still exits 76.*

`remote-lane.sh` now has three outcomes and a predicate per question
(`:89-160`). The python block prints `src=board|worktree` on line one and the
shell treats a missing or unrecognised source line as `unreadable`; the
distinction is drawn from `board_files.source("territory.toml")` itself, not
guessed. `remote_authoritative` is rc 0 **only** for `board`;
`remote_readable` is kept, documented as "not a permission", and used only to
report.

The two callers whose question is an **absence** ask the right one:
`fold.sh:168` refuses to prune and `lane.sh:101` exits 76, both naming the
source they got and the one command that cures it. `handback.sh:278` reads a
**positive** (`remote_lane_of`), which the stale copy answers truthfully — so
the defence in depth is now two different questions rather than one asked
twice, which is what pass 1's H2 broke. `prune_branch`'s new refusal is still
placed after the `lane/?*` case and can still only `return 1`, so the delete
set cannot widen.

`HAKUX_BOARD_REF=` (a host that switched the board branch off on purpose) reads
as `board`, so the refusal does not fire for a fault that does not exist — I
checked that this is a configuration read and not an accident: `board_files.py:23,28`
makes the empty ref disable the `git show` entirely.

**The scenario is fired against the real reader, not a shortcut.** The legs at
`:373-378` (`lane.sh`) and `:430-435` (`fold.sh`) set `HAKUX_BOARD_REF=refs/nosuch`
and set **no** `HAKUX_TERRITORY`, so `board_files.load` runs for real, fails its
`git show`, and falls back to the in-tree `territory.toml` — which names no
`lane/third` and no lane `alpha` as remote. `lane.sh resume alpha` exits **76**
saying `came back \`worktree\` rather than origin/board`, creates no worktree;
`fold.sh prune --apply` leaves `refs/heads/lane/third` on the fixture origin and
says which source it got. Against `8b185a925f` **both `fold.sh` legs and all
four `lane.sh` legs fail**, along with the three `remote_source`/`remote_authoritative`
legs and the live-board agreement legs — eleven of the sixteen.

I also ran the default path here, on this checkout: `remote_source` →
`board`, `remote_authoritative` → rc 0, and the map is empty (no territory row
carries `remote` yet — that is the board request in the PR body, and the
change is correctly inert until it lands).

I checked the load-bearing claim in `fold.sh`'s comment — that the host path
gets an authoritative read because `board.sh` fetches the board ref before
re-execing these jobs — against `board.sh` itself: `git -C "$WT" fetch -q
origin board` at **`board.sh:186`**. The comment cites `:161`, which is the
line it was at before master moved; the fetch is there, so this is a stale
line number in a comment and nothing more.

## Scenario 3 (M1) — CLOSED

`mergeStateStatus` is **CLEAN**. The merge `8233fe866a` resolved `lane.sh`:
master had moved `. "$JOBS/window.sh"` onto the line this branch sources
`remote-lane.sh`, and **both survive** — `window.sh` at `lane.sh:56`,
`remote-lane.sh` at `:62` with the non-bare guard that turns a missing file
into `exit 76` rather than an undefined `refuse_if_remote`. Master's
`window_limit_hit`/`window_note_limit` are still called at `:292-293`, so the
resolution did not drop the other side's feature.

`refuse_if_remote` is the first statement with a side effect in both call
sites: `start` (`:201`, ahead of the brief check, the worktree and the unit)
and `resume` (`:244`, ahead of everything). `selftest.sh` passes whole on the
resolved tree (727/0, measured here, not read).

## Scenario 4 (M2) — CLOSED

> *one number, measured at a named tip, in all three places, summing to 41.*

The check count changed from 41 to **61** in remediation, which is the number
the three places now carry, and all three agree:

| where | claim |
|---|---|
| fragment `:22-28` | 61 checks, 43 fail against `master@11ddd94a66`, 18 pass |
| `NOTES.md:406-407` | 61 checks, 43 fail, 18 pass |
| PR body | 61 checks, 43 fail, 18 pass |

**Re-measured here, not read.** `grep -c 'check "'` → **61**. The master run's
98 section is **43 FAIL / 18 ok = 61**. And the 18 that pass are the 18 the
NOTES enumerate — I matched them by name, one for one, against the four
categories it gives (6 must-not-move legs, 7 negative halves of a pair, the 2
`arms.sh state` legs, the 2 H1 trunk legs and their control): exact, no
leftovers on either side. The pre-remediation figure is checked too: **16 of 61
fail against `8b185a925f`**, and the sixteen are H1's four and H2's twelve and
nothing else, as the body says.

So the number is a measurement again and the taxonomy under it reconciles to
the file. Pass 1's failure mode — pass 2 getting a fourth number and being
unable to tell a tautology from a stale note — did not occur, because I got
each of the three numbers the documents claim.

## Scenario 5 (M3) — CLOSED

`NOTES.md:455` is now `## ~~Not mine: 86-fold-regressed.sh is red on master~~
-- SUPERSEDED 2026-09-19, FIXED`, struck through **at the heading**, with the
next line stating the section is history and nothing below it asks anybody for
anything. The two-commit diagnosis is kept, which is the right call. The PR
body's claim is withdrawn in place (body "**M3**"), in the past tense, naming
`bb4b78689e`, PR #167 and 19:47Z; the old headline assertion is gone from the
body — `grep` over the fetched body finds "holds up every fold" only inside the
withdrawal.

## The four LOWs

All four are addressed, which pass 2 does not require but does record.

* **L1/L2** — `fleet.py:610-620` reads `p["remote"]` and prints `elsewhere`
  rather than `finished` for a remote lane's ready PR. The field has a reader.
* **L3** — `fleet.py:588-593` now says "No FAIL **from this section**", and
  states that the PR can still raise one through `unfolded`/`waiting`, which it
  should.
* **L4** — the mislabelled check is split: `:271` "gives every row carrying
  `remote` a section of its own" asserts `REMOTE LANES (2)`, `:273` asserts the
  PR. A failure now names the right thing.

## One note, deliberately not a finding

`98-lane-shape.sh:209` — "and the other open PR's head is collected too, not
lost with the bad one" — passes against `8b185a925f` as well as against this
tip, so it does not discriminate for H1. The reason is the fixture's shape, not
the assertion: `$LSA/repo` is both the arms consumer and the pusher of
`claude/elsewhere-u1` (`:105-127`), and the push itself creates
`refs/remotes/origin/claude/elsewhere-u1` in that repo, so the leg is satisfied
whether or not the tick's fetch ran. It asserts something true and worth
asserting; it just is not the leg that proves the fetch happened. `:216`
(`refs/remotes/pr/777` exists) is, and it does fail against `8b185a925f`.

No severity: H1's scenario is closed by four legs that do discriminate, and a
leg that cannot fail costs nothing here beyond being counted among the 45.
Recorded so a later reader does not mistake it for evidence it is not.

## Verdict

**Clean.** Both HIGHs are closed by mechanism, not by assertion: H1's cannot
fire because the invocation that updates the trunk no longer contains a name
that can be missing, and H2's cannot fire because the two guards whose question
is an absence now ask a predicate the fold-lagged copy cannot answer. All three
MEDIUMs and all four LOWs are addressed. Removing `needs-audit-2`, adding
`fold-ready`.
