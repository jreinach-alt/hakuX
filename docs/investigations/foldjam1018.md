# foldjam1018: why the fold path jammed for 12+ hours on 2026-10-18, and what stops it recurring

Owner order, 2026-10-18 ~20:40 PDT: "dispatch a lane to fix what went awry with our process so this
doesn't bite us again." The owner does not care about the selftest or the process itself -- only that this
failure mode (three silent causes stacked, four asks to get two ready lanes folded) cannot recur. No
GitHub issue; this doc is the record. No gameplay, no device, no emulator code -- scope is the fold/dispatch
tooling only.

## 0. Where the files actually live (checked, not guessed)

- `offline_fold.py`, `foldqueue.sh`, `foldqueue.tried`, `foldqueue.log`: `/home/justin/hakux-work/offline-git/`,
  outside the git repo. My sandbox **can** write there directly -- no patches-under-`docs/lanes/` fallback was
  needed.
- `driver_tick.py`, `driver_selftest.py`: `/home/justin/hakux-work/host-tools/`, also outside the repo.
  `git ls-tree` against every ref confirms **there is no repo-tracked copy of `driver_tick.py` anywhere** --
  only scattered lane-scoped `docs/lanes/*/host-tools/` directories unrelated to this file. The brief's "the
  repo copies are what you change, then say which live copy must be synced" does not apply: there is one
  copy, the live one, and it was edited directly. No sync step exists or is needed.
- Backups: every live file edited here was copied to `<name>.bak-20261018-foldjam1018` before any edit.

All three causes below were re-verified from `foldqueue.log` and `journal.jsonl` in this session, not assumed
from the brief.

## 1. Master went red for ~20h with no alarm -- and the suspected mechanism was wrong

`compat1017b` folded at 23:38 10-17 (head `48a6db90c5`, merge `c42d3b00a5`), changing
`docs/testing/title_registry.py`'s `check --pages` to require the numberless README Playable line.
`docs/lanes/titledb1014/fixture/pages_check_falsifier.py` (a different, already-merged lane's fixture) still
wrote the old numbered format, so `selftest.d/66-status-titles.sh` (shard 3) failed for every later fold
that ran the full suite. Fixed on master in `47bca331d6`, roughly 20h later.

**The brief's suspected mechanism was wrong, and the real one is worse.** The journal entry for compat1017b's
own fold (`journal.jsonl:243`) reads:

```
"checks": {"selftest": {"named": "none", "why": "none -- data plus a page check no selftest.d fragment
runs; title_registry_selftest.py (6 tests, run directly) covers the new README check."}}
```

This is **not** a named `Selftest:` subset that happened to omit fragment 66 -- it is an explicit
`Selftest: none -- <rationale>` claim, asserting that *no* `selftest.d` fragment exercises the change at
all. That claim was false: `selftest.d/66-status-titles.sh` line 58 reads
``# `title_registry.py check --pages` (#433 Part 4): every public/rendered ...`` -- it does exercise exactly
the function compat1017b changed. `offline_fold.py` had (before this fold) no check of a `Selftest: none`
claim against what the suite's own fragments say they cover; it simply trusted the lane's self-report and
skipped straight to merge.

A second wrinkle, found while reproducing this: fragment 66 mentions the changed file only by **basename**
(`title_registry.py` in a comment), not by its full repo-relative path
(`docs/testing/title_registry.py`). A naive "does this fragment's text contain the changed path" grep --
which is what a first version of the auto-widen fix here used -- would still have missed it. The fix below
matches on both the full path and the basename.

### Fix (part of item A, implemented and tested)

`offline_fold.py`'s `mentioning_fragments(fdir, changed, exclude=())` (new module-level helper): for every
`selftest.d/*.sh` fragment not already in `exclude`, checks whether its text contains any changed file's
full path *or* basename. Wired into both:

- The `Selftest: none -- ...` branch: before accepting the claim, run `mentioning_fragments` with no
  exclusions. If it finds fragments, **run them** (via `SELFTEST_ONLY`) instead of skipping, and fail the
  fold if they fail -- `checks["selftest"]` records `claimed: "none"` alongside the auto-widened list and
  result, so the journal keeps the discrepancy visible. Only an empty `auto` list falls through to the old
  "named: none" skip.
- The named-`Selftest:` subset branch: widens the named list with anything `mentioning_fragments` finds
  that the PR.md didn't already name (`exclude=names`), same as before but using the shared, basename-aware
  helper.

Verified: reconstructed compat1017b's exact changed-file set
(`docs/testing/title_registry.py`, `README.md`, `docs/lanes/compat1017b/PR.md`) against a copy of the real
`66-status-titles.sh` fragment text in an isolated fixture dir (`/tmp/foldjam-test/frag/`) --
`mentioning_fragments` returns `['66-status-titles']`, confirming this fix would have caught the actual
incident, run the fragment, and failed the fold at `compat1017b`'s own fold time instead of 20h and four
other lanes later. `python3 -m py_compile offline_fold.py` passes.

This is a grep, not an import graph or a coverage map -- it catches "the fragment names the file it
exercises in a comment or invocation," which is the common case and was sufficient here, but it is not a
proof of coverage. A fragment that exercises a changed file without ever writing its name anywhere in its
own text (e.g. only through a shared helper module) will still be missed.

### Fix (item A, remainder): background master-red alarm

Independent of the auto-widen fix above (which only changes what a *fold* runs, and only catches changes
whose own diff touches the right file), a change elsewhere in the tree can still turn master red for a
reason unrelated to what any single fold's own files-changed list would surface -- the actual 20h window
happened because nothing ever re-ran the suite against master itself after folding.

`foldqueue.sh`'s existing FOLDED branch now backgrounds `master_health_check.sh <branch> <title>` via
`systemd-run --user --unit hakux-health-<epoch> --collect` (non-blocking, matching the established pattern
from `dispatcher_update_window.sh`). `master_health_check.sh` (new file,
`/home/justin/hakux-work/offline-git/master_health_check.sh`):

- Single-instance via `.health.lock`/`flock -n`: a burst of folds in a busy stretch backgrounds one check at
  a time, not a pile of parallel 4-shard suites; a check that's already running covers any fold that lands
  while it runs, since it fetches `origin/master` fresh at start.
- Fetches `origin/master`, builds a scratch worktree, runs the 4-shard selftest (or serial, if
  `--check-shards` refuses the split), and on failure extracts the failing fragment name via grep.
- Writes `offline-git/master-health.json`: `{checked, at, ok, fragment, culprit_branch, culprit_title,
  log}`, always overwritten with the latest run's verdict.

`driver_tick.py`'s new `master_red_status(health, checked_is_live)` (pure function, tested in
`driver_selftest.py`): returns the verdict only when `ok` is false **and** the checked sha is still live
(equal to current master, or an ancestor of it via `git merge-base --is-ancestor`) -- a stale red verdict
from a sha that a later fold's own health check has already superseded does not alarm twice, and a verdict
for a sha nobody has confirmed is still reachable from master does not alarm at all. `main()` wires this
into a new jam row: class `master-red`, id `master-red:<fragment>`, owner `external`, evidence naming the
fragment, timestamp, master sha, culprit branch/title, and log path.

Not run end-to-end against the live `/home/justin/hakuX` repo (worktree-based git operations on the live
dispatcher tree are lane.local's job, not mine, under "never run git in a tree that is not your worktree");
verified via `bash -n`, `py_compile`, and an isolated unit test of the JSON-verdict-writing snippet with
synthetic args.

## 2. A selftest-failed head stayed blacklisted after master was fixed

`foldqueue.tried` keyed selftest failures by head sha alone (`echo "$head" >> $TRIED`), so once `47bca331d6`
fixed master, nothing re-tried the already-failed heads; `driver_tick.py`'s fold jam row kept saying
`fold-progress ... watching (not a jam while it progresses)` the entire time nothing was progressing.
lane.local had to hand-edit the blacklist (confirmed: no stale entries remain in the live `foldqueue.tried`
as of this session -- the incident's specific entries were already cleared by hand before I started; this
fix is forward-looking, not an unstick operation).

### Fix (item B, implemented and tested)

- `foldqueue.sh`: a selftest failure (matched by the existing `*"selftest failed (rc"*` case) is now keyed
  `$head@master:$master` instead of bare `$head`. A new skip-check, alongside the existing bare-head and
  `$head@$tb` (territory) checks, reads the last `$head@master:<sha>` line for this head and skips only if
  that sha still equals the current master -- once master advances, the head is no longer skipped and gets
  one more try. The inbox/log message for this case now says
  `(blacklisted until master moves past <sha>; one retry per master sha)`.
- `driver_tick.py`: new pure function `blacklist_status(head, master, territory_sha, tried_lines)` --
  returns `('plain', None)` for a bare-sha entry (never retried until the branch itself moves, unchanged
  behavior), `('territory', sha)` for a `head@territory-sha` entry still matching the current
  `territory.toml` sha, `('master', sha)` for a `head@master:sha` entry still matching current master, or
  `None` if the head isn't blacklisted under any of these or master/territory has since moved past the
  recorded sha. `blacklist_reason(lane_name, log_lines)` finds the most recent `FAILED lane/<name> @ ...`
  line in `foldqueue.log` and returns its reason text and timestamp for display.
- `main()`'s fold-jam section now checks `blacklist_status` for each lane before falling through to the old
  `fold_state`-based progress/silent/idle logic; a blacklisted head emits
  `blacklisted: <reason>, since <time> (retries when <condition>)` instead of `watching`, and skips the
  stale progress logic entirely (there is nothing to watch -- it is blacklisted, not running).

Verified: `driver_selftest.py` section "blacklist_status / blacklist_reason" -- 11 new cases (never-tried,
plain/territory/master-keyed each in both held and cleared states, re-blacklist at a second master sha,
missing head) all pass; `bash -n foldqueue.sh` and `python3 -m py_compile driver_tick.py` pass. A dedicated
bash snippet exercised the four `foldqueue.sh` skip-check scenarios (never-tried, blacklisted +
master-unchanged, master-advanced, re-blacklisted-at-new-master) directly against the shell logic.

## 3. A single-file territory refusal silently cost a full fold cycle, twice

`localdrive1018`'s fold was refused for one sibling file outside its territory row: `pathknow/learned.py`
(18:14 PDT) then `titles/route.sh` (20:14 PDT, a comment-only edit) -- both confirmed in `foldqueue.log:614`
and `:621`. Each refusal was visible only by reading `foldqueue.log` after the fact; the lane, still running,
was never told, and nothing re-checked until the next ~30-minute fold-queue tick.

### Status: partially implemented. `check_territory.py`'s exact-fix message is done and tested; the
ready-time check and fold-to-running-lane notification are spec only.

The brief marks `docs/testing/lane.sh` as sparsewt1017's ("spec/patch only" for me). `docs/testing/check_territory.py`
**does** exist in this repo (231 lines, granted in this lane's own territory row) -- my first pass at this
doc wrongly said it couldn't be found; it is the global board validator (wave monotonicity, no-two-lanes-
hold-one-file, and the FREE-but-claimed overlap check), not `offline_fold.py`'s own per-branch outside-files
check (which is a separate, smaller `fnmatch` loop inside `offline_fold.py`'s `main()`, ~line 100-108, and is
not item C's target).

1. **`check_territory.py`'s exact-fix message (done, tested).** Line 139's
   `"%s is listed FREE but claimed by %s"` now reads
   `"%s is listed FREE but claimed by %s -- release it from [free] in the same commit that adds it to
   [lane.%s]'s files"`. Verified with a new selftest fragment,
   `docs/testing/jobs/selftest.d/98-foldjam1018-territory.sh`: a synthetic `territory.toml` with a
   `[lane.widener]` row and a `[free]` entry naming the same file fails with the new message naming both
   the file and the fix; a clean row (no overlap) still passes with no fix text printed. Ran for real
   through `docs/testing/jobs/selftest.sh` (`SELFTEST_ONLY=98-foldjam1018-territory`), 5/5 checks pass; also
   reran `66-status-titles.sh` itself (22/22 pass) to confirm this edit caused no regression elsewhere in
   the suite.
2. **Ready-time territory check.** Spec only. `lane.sh`'s ready step (or whatever gate flips `State: draft`
   to `State: ready`) should run the exact same check `offline_fold.py`'s `main()` runs at merge time: read
   `origin/board:territory.toml`'s `[lane.<name>]` row, `git diff --stat` against the branch's merge-base
   with `origin/master`, and fnmatch every changed path against the row's `files` patterns the same way
   `offline_fold.py` does. Importing `offline_fold.py`'s check as a function (or factoring it out to a
   shared module both tools import) would keep the two from drifting apart -- two copies of the same fnmatch
   logic is exactly the kind of thing that silently diverges. Print the exact offending paths before flipping
   to ready, not after a fold refuses it. Not built: `lane.sh` is sparsewt1017's.
3. **Fold-side notification, not just a log line.** `offline_fold.py`'s territory-refusal `sys.exit` already
   produces the exact message `foldqueue.sh` puts in its `FAILED` log line; `foldqueue.sh`'s catch-all
   already appends a note to `$INBOX` for a lane.local read. The missing piece is routing a copy of that
   same note somewhere the *running lane's own session* can read without a human relaying it -- e.g. a
   per-lane file under `docs/lanes/<name>/` the lane is expected to poll, or (lower-effort) a `WAITING:`-style
   comment posted to the lane's own PR by the fold tool itself at refusal time, the same channel
   `handback.sh` already reads. Not built: it needs a decision about which channel (PR comment vs. a polled
   file), which is dispatch-ownership territory, not mine to pick unilaterally.

## 4. Folds are serial (~30 min each); no owner-order fast path existed

lane.local merged `localdrive1018` by hand at 20:33 PDT (`foldqueue.log:622`,
`72af9cb92c ... directly on owner order (selftest skipped)`) because nothing let an owner-ordered fold skip
the ~30-minute suite in one command.

### Fix (item D, implemented and tested -- shipped first, per the brief's order)

`offline_fold.py <branch> --owner-order "<reason>"`:

- Requires a non-empty reason string (`sys.exit` otherwise).
- Skips the harness selftest/route checks entirely, but runs `py_compile`/`bash -n` on every changed `.py`/
  `.sh` file as a syntax smoke test, failing the fold on any syntax error.
- Leaves the device-run requirement for emulator code (`code` list) untouched -- an owner order waives the
  suite, not the no-untested-emulator-code rule.
- Records `checks["selftest"] = {"skipped": owner_order}` in the journal, and appends
  `Owner order: <reason>` to the fold commit message.

This matches, and formalizes, the hand-built journal entry lane.local already wrote for the real incident
(`journal.jsonl`'s `localdrive1018` entry: `{"skipped": "owner order 2026-10-18 ~20:35 PDT: push the fold
through, no selftest", "syntax": "py_compile + bash -n ok"}` -- written before this fix existed, by hand,
in the same shape this flag now produces in one command).

Verified: argv-parsing (reason required, `--dry-run` combinable), the syntax-check loop (both a clean and a
deliberately-broken `.py`/`.sh` fixture), and the journal/commit-message templating were each unit-tested in
isolation against `/tmp/foldjam-test/` fixtures. `python3 -m py_compile offline_fold.py` passes.

## 5. (Secondary) Nova held by two stacked holds with unclear visibility

Not scoped as code for this lane -- `hold.sh` is holdcap1018's and `battery_admit.py` is toolsmith's. Spec
only (item E):

- The dispatcher's `HELD by hold/nova` line, and `hold.sh who`, should list **every** hold currently on the
  device, not just the most recently placed one: each entry should show its tag, the reason string it was
  taken with, who/what placed it, and the exact command that lifts it (e.g. `hold.sh release nova
  lane.lanelocal-offline`). The 10-18 incident had a `lanelocal-offline` hold placed *after* a battery hold
  was lifted, and the dispatcher's HELD line showed only one of the two -- whoever read it next had to guess
  which command to run and against which tag.
- A battery override currently needs a systemd service drop-in plus a lift-waiter script; the brief asks for
  one command instead. Concretely: `battery_admit.py --override <reason>` (or a `touch`-based override file
  with the reason as its content, if that's cheaper against the existing polling loop) that `battery_admit.py`
  itself checks on every poll and clears when told to, replacing the drop-in-plus-waiter two-step with a
  single invocation and a single matching release command.

This is written here as the proposed change, not implemented -- per the brief, ownership of `hold.sh` and
`battery_admit.py` belongs to other lanes.

## 6. (Found by this lane's own fold, 2026-10-19) The widening in item A can select a fragment without the
sibling it depends on for function definitions

This lane's own fold of commit `aa99e3acc4` failed `selftest failed (rc 1)` three times (00:11, then again at
two later master shas, per hostops's 06:13 PDT resume) on a bug in the item-A widening this lane itself shipped
-- not a regression in the PR's actual diff.

**Root cause (verified against the real fragments, not assumed).** Item A's `Selftest: 98-foldjam1018
98-foldjam1018-territory 66-status-titles` names an explicit subset. `mentioning_fragments()` then widens it
with every *other* fragment whose text mentions a changed file -- correctly, since this PR changes
`docs/testing/check_territory.py` and `51-dispatch-hardening.sh` names `check_territory.py` 5 times (it drives
the real script). So `51-dispatch-hardening.sh` gets pulled in. But `51-dispatch-hardening.sh` calls
`clear_markers`/`finish_queue` (lines 270, 275, 284, 294, 301, 327, 333, 345) without defining them -- both are
only defined in `50-arms-requeue.sh` (lines 58-59), and a *full* selftest run only works because bash sources
every fragment, in file order, in one shell, before 51 runs: by the time 51 calls `clear_markers`, 50 has
already defined it, purely from load order, not from any explicit dependency declaration. A `SELFTEST_ONLY`
run that selects 51 without 50 never sources 50, so both calls fail as a bare, non-fatal `set -u` error --
`clear_markers: command not found` -- not a fatal one (`set -e` is not in play for a function call that's
merely absent), so it corrupts fixture state silently and cascades into unrelated-looking `FAIL`s and, in one
reproduction here, a genuine hang in the next fragment section waiting on state `clear_markers` never cleared.
**Reproduced directly**: `SELFTEST_ONLY="51-dispatch-hardening" bash docs/testing/jobs/selftest.sh` run against
this tree prints exactly `FAIL E: fixture not as 50 leaves it (two clean results, an empty queue)` followed by
`.../51-dispatch-hardening.sh: line 294: clear_markers: command not found` and then hangs in section E2 instead
of failing fast.

This is a gap in item A's own widening rule, not a one-off: widening-by-file-mention finds fragments that
*reference* a changed path, but had no notion of a fragment *depending on another fragment for its function
definitions* -- a partial/widened run can always pick a fragment whose helpers only exist because of file-order
sourcing in the full suite, for any pair of fragments with this shape, not just 50/51.

### Fix (implemented and tested)

Rather than inventing a second notion of "these fragments share state," reuse the one this project already
curates for exactly this reason: `selftest.sh`'s own `SHARD_CHAINS` array, whose header already says
"fragments share state on purpose... A CHAIN below is a set that must land in one shard" -- `50-arms-requeue
51-dispatch-hardening ...` is already one of its three listed chains. The shard splitter already honors chains;
the `SELFTEST_ONLY` path in `offline_fold.py` simply never consulted the same list, so the two selectors had
silently drifted apart.

`offline_fold.py` (outside the repo) gains two new functions:

- `shard_chains(testing_dir)`: regex-parses `SHARD_CHAINS=( ... )` straight out of the live
  `docs/testing/jobs/selftest.sh` text (no bash invocation, no new repo-file dependency -- the same
  "read the fragment/script text" style `mentioning_fragments` already uses) and returns each chain as a
  `set` of fragment basenames.
- `close_chains(names, chains)`: given the already-selected fragment names, unions in the full membership of
  any chain that overlaps them, returning `(closed, added)` so the fold log can say exactly what was pulled in
  and why.

Both selftest-fragment-selection branches (the `Selftest: none` auto-widen, and the named-subset widen) now
call `close_chains` on their final fragment set before building `SELFTEST_ONLY`, and log
`"widening with N fragment(s) from the same SHARD_CHAINS group (a selected fragment calls a function only
defined there): ..."` when it adds anything. Verified: `close_chains(["51-dispatch-hardening"], shard_chains(...))`
against the real `selftest.sh` returns the full 13-fragment chain including `50-arms-requeue`; an unrelated
fragment (`75-fold-exact`) widens to nothing.

**Defense in depth, for a dependency SHARD_CHAINS hasn't caught up to yet.** `close_chains` only fixes gaps
already captured in `SHARD_CHAINS`; a *new* undefined-function dependency between two fragments neither chain
lists would still fail, just as before. So a partial run's failure is no longer just "selftest failed (rc N)":
new `fold_fail_message(rc, log, run)` greps the log for the `<name>: command not found` shape bash produces for
exactly this failure mode and, when found, names the undefined command(s) and points at `SHARD_CHAINS` as the
fix -- turning a silent fixture-corruption cascade into a loud, specific message the next person does not have
to re-derive. Verified against both a log containing the real `clear_markers: command not found` line (message
names it and points at `SHARD_CHAINS`) and an ordinary failure log with no such line (message is the plain
"selftest failed" with no false claim of a chain gap).

**Falsifier** (the one the hostops addendum asked for): `SELFTEST_ONLY="51-dispatch-hardening"
bash docs/testing/jobs/selftest.sh` alone, run directly against this tree -- reproduces the bug exactly as
described above (confirms the defect is real, not a theory) and is mirrored, since `offline_fold.py` cannot be
imported from a bash fragment, as new checks in `docs/testing/jobs/selftest.d/98-foldjam1018.sh`: `(a)` the
real `SHARD_CHAINS` array still chains 50 with 51 (so this test doesn't go stale silently if that chain is ever
split), `(b)` closing over `51-dispatch-hardening` alone pulls in `50-arms-requeue`, `(c)` closing over an
unchained fragment adds nothing, `(d)`/`(e)` the "command not found" log-scan correctly names `clear_markers`
from a synthetic log with the real error shape, and names nothing from an ordinary failure log. Ran for real
through `docs/testing/jobs/selftest.sh` (`SELFTEST_ONLY=98-foldjam1018`): 13/13 pass.

**Cost tradeoff, named rather than hidden.** The 50/51 chain has 13 members (`SHARD_SECS` puts their combined
serial time above 10 minutes); any future PR whose own `Selftest:` widening touches *any one* member now pays
the whole chain, not just that one fragment. That is the correct trade against a silent hang/corruption, but it
means a small, targeted `Selftest:` subset can occasionally balloon back toward a near-full run if it brushes
this particular chain -- worth knowing, not a reason to skip the fix.

## Summary: what shipped, what didn't

| Item | Status | Where |
|---|---|---|
| D: owner-order fold path | Shipped, tested | `offline-git/offline_fold.py` |
| B: master-keyed blacklist + jam-row wording | Shipped, tested (unit + real `docs/testing/jobs/selftest.sh` run) | `offline-git/foldqueue.sh`, `host-tools/driver_tick.py`, repo fragment `98-foldjam1018.sh` |
| A: Selftest-claim auto-widen (both `none` and named-subset forms) | Shipped, tested (unit + real selftest run) | `offline-git/offline_fold.py`, repo fragment `98-foldjam1018.sh` |
| A: widened fragment set closed over SHARD_CHAINS + loud "command not found" diagnosis (found by this lane's own fold, section 6) | Shipped, tested (unit + the real failure reproduced and fixed) | `offline-git/offline_fold.py`, repo fragment `98-foldjam1018.sh` |
| A: background master-red health check + alarm | Shipped, tested (syntax + isolated unit tests only, not run live) | `offline-git/master_health_check.sh`, `offline-git/foldqueue.sh`, `host-tools/driver_tick.py` |
| C: `check_territory.py` FREE-widen exact-fix message | Shipped, tested (real selftest run) | `docs/testing/check_territory.py`, repo fragment `98-foldjam1018-territory.sh` |
| C: territory-at-ready check, fold-to-running-lane notification | Not implemented -- spec above; `lane.sh` is sparsewt1017's, and the notification channel is a dispatch-ownership decision | this doc, section 3 |
| E: hold visibility, one-command battery override | Spec only, by design (not my files) | this doc, section 5 |

The two new repo-tracked selftest fragments (`docs/testing/jobs/selftest.d/98-foldjam1018.sh`,
`98-foldjam1018-territory.sh`) ran for real through `docs/testing/jobs/selftest.sh`
(`SELFTEST_ONLY="66-status-titles 98-foldjam1018 98-foldjam1018-territory"`): 35 checks, 0 failed. Everything
living outside the repo (`offline-git/offline_fold.py`, `offline-git/foldqueue.sh`,
`offline-git/master_health_check.sh`, `host-tools/driver_tick.py`) was verified by `py_compile`/`bash -n`
plus isolated unit tests against synthetic fixtures (including a reconstruction of the actual compat1017b
scenario for the auto-widen fix) -- none were run end-to-end against the live `/home/justin/hakuX` repo or
the live fold queue, consistent with "never run git in a tree that is not your worktree" and with staying
off production infrastructure I don't operate. The two new selftest fragments mirror those external tools'
key logic inline rather than importing them (documented in each fragment's header, with the exact risk: if
the live script's key format or match rule changes, the fragment goes stale silently). While building the
fold-queue fragment I found a real bug in my own first draft of its fixture -- using non-hex placeholder
master shas (`m1`/`m2`) made the hex-anchored skip-check's grep never match, so every "should be skipped"
case passed by accident, for the wrong reason (always falling through to "retry"). Fixed by using hex-shaped
fixture shas; left in the fragment's comment as a warning against repeating it.
`driver_selftest.py`'s one pre-existing failure ("a verified name missing from the listing is reported") was
confirmed unrelated to this work by reproducing it identically against the pre-edit backup.
