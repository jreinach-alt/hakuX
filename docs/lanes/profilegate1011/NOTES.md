# lane.profilegate1011 -- NOTES

## Attempt 1: why it did not finish

Attempt 1 wrote the bulk of `titlestate.py`'s profile gate (`admit()`,
`gate_report`, `title_routes`/`proven_route`/`known_path`, `title_saves`,
`readiness`, the `--save` disk-composition path, CLI wiring) and the R3
check in `pathfind.py`, plus a first slice of `titlestate_selftest.py`
covering the four `admit()` clauses and the transition file. It opened
PR #930 early, per protocol -- but every one of those changes stayed
**uncommitted** in the worktree. The PR body claimed files
(`docs/lanes/profilegate1011/**`, the selftest.d fixture, the
request.sh/dispatcher.sh patch) that were never written, and the branch
itself carried zero commits ahead of the base it was opened from. With an
empty diff against master, PR #930 was later closed as `MERGED` with a
merge commit (`b73d50a070`) that is just master's own tip -- none of
attempt 1's work landed. The uncommitted changes were still sitting in the
worktree when this attempt (2) started; nothing was lost, but nothing had
been delivered either.

Lesson applied this attempt: commit the in-progress work immediately
(checkpoint commit `c80bc65549`) before doing anything else, including
before merging origin/master, so a repeat of the same failure mode cannot
silently discard it again. Opened a fresh PR (#933) since #930 is closed.

## Addendum 3: the grant is in

`lane.local`'s board (`d09966237f`) released `request.sh`, `dispatcher.sh`
and `AGENTS.md` after `lane.soakvideo1011` folded (`b73d50a070`, 14:55
PDT). Merged `origin/master` into this branch (merge commit on top of
`c80bc65549`) -- clean, no conflicts: soakvideo1011's changes to
request.sh/dispatcher.sh/AGENTS.md (route_refs staging, video) don't touch
anything attempt 1 wrote in titlestate.py/pathfind.py.

## Evidence

`profilegate1011-inventory.py` and `profilegate1011-inventory.txt` (copied
from `/home/justin/hakux-work/briefs/`) are the brief's inventory of every
route, its state, its title's golden, and 3 days of runs -- the basis for
"The rule"/R1-R3 above.

## Rule actually implemented (Addenda 1 + 2, replacing the original "The rule")

`admit(title_id, route_name=None, route_text=None, device=None,
find_route=None, routes_dir=None, remake_profile=None, path_broken=None)`
in `docs/testing/titles/titlestate.py`. Refuses only:

- **R1** a `first-run` route on a title that already has a golden (either
  kind) -- override `--remake-profile "<why>"`.
- **R2** a `first-run` route with no `mark profile-saved` on a title with
  no golden -- way forward is the recipe (module docstring).
- **R3** a route-finding run (`--find-route`, or a `pathfind.py` session)
  on a title with a known path -- queued runs are blocked only by a
  *proven* route (one with `mark gameplay` AND a result whose
  `verdict.json` says `reached_gameplay`); `pathfind.py` sessions are
  blocked by that OR a `pathknow/paths/<TID>.json` success (Addendum 2:
  a route's own first proof soak still needs `--find-route` even though
  pathknow already succeeded once). Override `--path-broken <result id>`,
  checked against the known route/title.

Admitted unconditionally: `returning`/`any`/no-route on a title with a
profile (data-only counts under `any`/no-route, not `returning`),
`make-profile`, `--find-route` with no known path, a live
`profile-transition.toml` entry, and the two overrides above.

`--save <save_id>` (compose/plan/rebuild/prepare) swaps a specific stored
save in for a title's slot instead of its golden; refused when the save
isn't in the store, was rejected on the device, or (returning) has no
save directory.

## selftest.d/99-profile-gate.sh (`7d70b0eac6`)

Five sections. A: `request.sh` queue-time gating (R1/R2/R3, both
overrides, `--save`'s store check and its "needs a title" guard) driven
through the real script via fixture `DISPATCH_DIR`s. B:
`dispatcher.sh`'s `profile_gate_check()` called directly against a
hand-crafted `request.json` with no `request.sh` step at all, proving
nothing is grandfathered at claim; B6 drives the full Addendum-2
sequence (pathknow-only admits a queued find-route, a proven result then
refuses it, `--path-broken` naming that result admits again) at this
layer. C: the seven titlestate.py mutants (M1-M7), each a sed copy of the
real file compared against a shared `pgcases.py` fixture harness. D: M8,
a sed-delete of dispatcher.sh's claim-time call site, verified both
structurally (`declare -f serve_one` no longer names
`profile_gate_check`) and functionally (the untouched `profile_gate_check`
still refuses on its own). E: a non-mutant positive control that
`pathfind.py`'s own R3 check fires in `PATHFIND_DRY` mode (M4 is
titlestate.py's `admit()`, not pathfind.py -- see below).

Three bugs found while first running this file, all fixed before commit:

- **M1's fixture was accidentally untestable.** Its route text had no
  `mark profile-saved`, so disabling R1 (`if gg:`) just fell through to
  R2's refusal instead of admitting -- both real and mutant code produced
  `admit=False`, for different reasons, and the mutant passed unnoticed.
  Fixed by adding `mark profile-saved` to the route text, which also
  isolates M1 from M2: with it present, a disabled R1 now ADMITS
  (wrongly) rather than hiding behind R2.
- **`import-save --dir` pointed at a different path than the fixture
  wrote `save.json` to** (`$D/import-src/<tid>` on the CLI side vs.
  `$D/titlestate/import-src/<tid>` where the Python heredoc had written
  it, in both the A5/A6/A7 and B2/B3 blocks) -- `import-save` raised
  `FileNotFoundError` and both titles kept no golden, so every case that
  depended on one (A5, A6, B2, B3) was exercising the wrong state. Fixed
  by making the heredoc's `root` argument match the CLI's `--dir`.
- **The isolated mutant/real copies under `$PG/<name>/` have no
  `../../../tools/make_xbox_hdd.py` to find** -- `saves.py`'s module-level
  `_load_mkhdd()` only has a real target when `titlestate.py` sits in the
  actual repo tree, so every `pgcases.py` run crashed on import before
  printing a single case. Fixed with the documented override,
  `MAKE_XBOX_HDD=$REPO/tools/make_xbox_hdd.py`, set before `import
  titlestate` in the harness.

Two smaller test-logic bugs, also fixed: A6's helper call had a stray
literal `--` passed as if it were a `grep` flag (the helper is a bash
function, not `grep` itself, so it became the search pattern and the
real text/pattern arguments shifted); and the pathfind.py "nothing known"
dry-run check asserted `$? = 0`, but `--budget-min 0` always ends in exit
1 ("gave-up", no budget to attempt anything) whether or not the gate
would have blocked it -- the real discriminator is the gate's own
message, so that case now asserts the "already has a known path"
message is ABSENT rather than checking the exit code.

Also found and worked around, not a bug in the file itself: debugging
mutant copies by hand in a reused `/tmp` scratch directory can leave a
stray `titlestate.py` one level up from a mutant's own directory; Python's
`importlib.reload()` re-resolves the module's `sys.path` search at reload
time (after the module's own `saves.py` import has already pushed a new
entry), so a stray file one level up gets picked silently over the
intended mutant copy. `99-profile-gate.sh` itself never leaves such a
stray file (each mutant's own directory is the only thing under `$PG`
with that name), so this does not affect the committed file -- recorded
here only so a future debugging session with a dirty `/tmp` doesn't lose
time to the same confusion.

Ran standalone first (`SELFTEST_ONLY="99-profile-gate" bash
docs/testing/jobs/selftest.sh`) to find and fix the above without
spending the one full-suite run on it: 43 passed, 0 failed, once fixed.

## Readers audit

Grepped every `docs/testing` reader of `verdict.json`/`request.json`
(15 candidates, via `grep -rl "verdict.json\|reached_gameplay\|request.json"
docs/testing --include=*.py`, excluding titlestate.py/saves.py/selftest).
Confirmed via `grep -rl find_route docs/testing` that nothing outside
`titles/titlestate.py`/`titlestate_selftest.py` reads the new field yet.

Of the 15, only `title_verdict.py` independently judges a run (the others --
`titles/table.py`, `status_html.py`, `ab_compare.py`, `dispatch_gate.py`'s
Playable ledger reads -- all key off fields `title_verdict.py` already
computed into `verdict.json`: `pass`, `rating_candidate`, `void`). So voiding
a find-route run in `judge()`'s existing VOID block is the only patch
needed; nothing downstream needs its own change once that lands.
`title_verdict.py` is held by lane.failgate, so the exact patch (lines
491-500, reusing the existing `void` short-circuit) went to
`docs/lanes/profilegate1011/OUTBOX.md` under `FOR lane.failgate:` instead of
being applied here.

## Status at end of this session

See PR #933 body / `State:` line for current status; this file is kept
up to date as work proceeds in this session.

## Attempt 2: why it did not finish

Attempt 2 did the "After the grant" steps 1-4 (merge, admit()/gate_report/
readiness/saves in titlestate.py, the request.sh/dispatcher.sh wiring and
`profile_gate_check()` extraction, the full `99-profile-gate.sh` selftest
file with all 8 mutants, and the readers audit/OUTBOX.md patch) across six
commits, ending at `0b68bb2b82`. It ran out of turns at the cap before
pushing that last commit: the branch sat one commit ahead of
`origin/lane/profilegate1011`, and before stopping it had not yet run the
full `selftest.sh` suite once (only the standalone `99-profile-gate.sh`
run, noted above), had not written `PR.md`, and had not re-merged
`origin/master` (26 commits ahead by the time attempt 3 started). Nothing
was lost -- the work was committed, just not pushed or finished -- but per
Addendum 4 the unpushed commit had to be pushed first before continuing.

## Attempt 3

Starting from `0b68bb2b82` (6 commits ahead of the grant merge, 1 commit
ahead of `origin/lane/profilegate1011`). Pushed first, per Addendum 4.
Remaining before `State: ready`: the bare-8-hex-TitleID defect fix in
request.sh (Addendum 4), its selftest cases + mutant, merging
`origin/master` (26 commits behind), the one full `selftest.sh` run, and
`PR.md`.

Merged `origin/master` (26 commits: nfsdefault1011's fold, profileconv1011's
route conversions touching `amped2.route`/`gta-sa.route`, Android files) --
clean, no conflicts with anything this lane wrote.

Added `iso_for_tid(title_id, device=None)` to titlestate.py (targets.toml's
`iso.<device>`, else the newest `dispatch/results/*/request.json` resolving
to that title_id whose own `title` isn't itself another bare TitleID) and
its CLI (`iso-for-tid`), then the queue-time refusal in request.sh, right
before `tid_for_iso()` is first called on `--title` (so it fires before
`tid_for_iso`'s own 8-hex-head fallback can turn the bare TitleID into a
seemingly-valid title_id). Selftest: A8 (known replacement named), A9 (no
known name -- names `devices.sh`), A10 (a real file name is unaffected),
M9 (sed-drops the check; needs `--find-route` on the request to isolate it
from the unrelated finding below, since the title used for A8-A10 has no
golden and the plain admit() path refuses that regardless of the new check).

## Finding: admit()'s `any`/no-route branch may not match Addendum 1 -- NOT fixed here

While building M9's fixture I found that a title with NO golden and NO
route (or an `any` route) is REFUSED by the committed `admit()`
(titlestate.py ~1392-1402, "has no profile (no golden) and no
route-finding"), and A1's own existing test (committed in attempt 1/2,
`7d70b0eac6`) asserts that refusal as CORRECT. Addendum 1's own "Admitted"
list says the opposite in as many words: "`any`, and runs with no route,
whether or not the title has a golden." This looks like leftover logic
from the ORIGINAL "The rule" (before Addendum 1 replaced it -- that
original text's 3rd/4th bullets under "Everything else is refused" are
exactly this case) that Addendum 1's R1/R2/R3 rewrite never revisited for
this one branch, while NOTES.md's own "Rule actually implemented" summary
(above, "Admitted unconditionally: ... on a title with a profile") already
silently matches the stricter, pre-Addendum-1 reading rather than the
addendum's literal text -- so this is not a regression introduced this
session, it predates attempt 3.

Not fixed here: Addendum 4 scoped this session to the bare-TitleID defect
and the "After the grant" wrap-up, not a re-audit of admit()'s other
branches, and resolving it needs an owner/lane.local call on which reading
is intended (the owner's 10-11 12:3x clarification reads to me like the
addendum's literal text -- a plain boot screen "redoes nothing" regardless
of profile -- but that is a reading, not a measurement) before touching
code three attempts have already built and tested against the stricter
rule. Flagging it in the PR body for lane.local.

## The full selftest suite, run once (Addendum 4)

Merged origin/master first (clean, no conflicts, 34 commits ahead of
origin/lane after; `git merge --no-edit`), then ran all 137 fragments once,
sharded 0-3/4 (the suite's own comment: a single run takes 18-25 min on CI,
over this tool's 10-min-per-call cap, so each shard ran in the foreground
across several calls, polling the shard's PID with `kill -0` in a loop --
never left running across a turn boundary). Totals after the fixes below:
shard 0 (13/137 frags) 284/0, shard 1 (44/137) 971+1-then-fixed, shard 2
(39/137) 1079/0, shard 3 (41/137) 1091/0 -- ~3426 checks, 0 failed, every
fragment covered exactly once.

Three of the six fragments the merge brought in from origin/master (the
soakvideo1011-step2 fold) or already carried (`96-failgate.sh`,
`89-title-verdict.sh`, `97-dispatch-snapshot-drive.sh`) failed on first run,
all with the SAME root cause: a fixture queued a request with a
human-readable or fictitious `--title` ("Sonic Heroes.iso", "Crimson
Skies.iso", "RouteRefs Selftest.iso") or a real TitleID with no golden in
its isolated TITLESTATE_DIR, and no `--route`/`--find-route` -- harmless
before this lane's gate existed (an unidentified or profile-less title just
meant no golden to compose against), but `admit()` now runs unconditionally
for any `--title` and refuses exactly that. None of the six fragments were
testing profile semantics (video-option fit, route-crop transport, drive
snapshot resolution, pilot budget, failure-gate held/identified/released
logic) -- `--find-route "<reason>"` is the honest, minimal way past a check
they were never exercising, and is what each fix adds, with a comment
naming why. Fixed and reconfirmed (standalone fragment reruns, and shards
2-3 reran clean in full) in:
`61-soakvideo1011.sh`, `62-routerefs-soakvideo1011.sh`,
`89-title-verdict.sh`, `97-dispatch-snapshot-drive.sh`, `99-pilot-gate.sh`,
`96-failgate.sh`. This is the predictable fallout of a gate this lane made
unconditional landing in the same window as five other lanes' fixtures on
#433 that never anticipated it; lane.local should expect more of the same
from any fragment not yet merged against this branch.
