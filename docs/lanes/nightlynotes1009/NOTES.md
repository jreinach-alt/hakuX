# lane.nightlynotes1009

## Why attempt 2 resumed

Attempt 1 left `State: ready`, pushed, with items 1-5 done and the five owner-evidence bodies in place
(below). It did not act on lane.local's addendum (2026-10-09 18:35 PDT), posted after c61abb39ce: a
real defect in that commit, found by lane.local's own review, with its own repro and fix shape. This
attempt's whole job is that one fix, its test, and nothing else. See "Addendum fix" below.

While here, this attempt also merged `origin/master` (the lane was 1 commit behind at resume, per the
session banner): lane.local had, in the meantime, independently added `SuccessExitStatus=75 9` to
`docs/testing/systemd/hakux-nightly.service` (`2b9846b729`) -- exactly the OUTBOX item 1 this lane asked
for in attempt 1 ("Nothing else changes: lane.local adds `SuccessExitStatus=75 9` to hakux-nightly.service
itself (OUTBOX item 1, accepted)"). OUTBOX item 1 is now done upstream; nothing further to ask for there.

## Addendum fix (lane.local, 2026-10-09 18:35 PDT): the exact-match "none" test

**Defect, as found.** `nightly_build.sh`'s classification loop (then line 406) read
`[ "${text,,}" = none ] && cat=none` -- an exact match. A `Release note:` line whose text is `none.
<prose>` or `none (<prose>)` (no `(category)` right after "Release note", so `norm_cat` returns "" for
cat and the whole tail becomes `text`) fell through: `cat` stayed empty, `guess_cat` ran on the full
`none. ...` string, and the change was LISTED under a guessed category (usually Other) instead of
dropped. A window whose only player-visible-looking change was one of these said "would publish"
instead of "would not publish". `none.` is the second most common `Release note:` shape on master's
`docs/lanes/*/PR.md` (this very PR's own PR.md from attempt 1 uses it), so this was not a rare shape --
any ordinary lane that touches `android/` or `hw/` and writes "none. because X" hit it.

**Fix.** One line, `docs/testing/nightly_build.sh`:
```
-    [ "${text,,}" = none ] && cat=none
+    [[ ${text,,} =~ ^none([^a-z]|$) ]] && cat=none
```
This one line is shared by both lookup paths (`lane_body_line()` for an offline fold's own `PR.md`, and
`map_line`/`body_line` for a numbered PR) -- `r` from either path feeds the same `text`/`cat` extraction
above it, so fixing it once fixes both, exactly as the addendum said it would ("body_line uses the same
regex shape, so the PR path has the same hole"). `Release note (none): ...` is untouched (that already
short-circuits via `norm_cat`'s own `none|skip` case on the parenthesised category, regardless of what
follows the colon), and a real note that merely contains the word "none" later in the sentence (e.g.
"performance is fine, none of this regressed") still does not match `^none(...)`, so it is still listed.

## Selftest for the fix

Added to `86-nightly-notes.sh`'s existing offline-fold fixture tree (`FIX4`): two more lanes,
`offlinenonedot` (`Release note: none. This PR changes no emulator code.`) and `offlinenoneparen`
(`Release note: none (analysis only; no emulator code changed)`), both touching an `hw/` path (so
`lane_body_line` is actually consulted -- the brief's "an EMU_RE path" requirement; a `docs/`-only fold
is already internal for an unrelated reason and would not exercise this code path at all). Checked:
neither fold's "nothing a player would see" text appears anywhere in the body, and the log's counts
updated correctly (4 emulator, 2 lines, 2 left out, 4 internal -- up from 2/2/0/2: 2 more EMU-touching
folds, both dropped as none, so +2 to both emulator and left-out, and +2 to internal, same as before).

Added a second, separate fixture tree (`FIX6`, "offline-nonedot-only") whose *only* change is one
`none.`-noted EMU-path fold: notes mode lists nothing and says `would not publish: no player-facing
change` -- the brief's "a window containing only those does not publish" requirement. Build mode's exit
9 for this shape was already covered by the pre-existing docs-only "nothing published" fixture (same
`PUBLISH_WHY` gate, reached here through the regex fix rather than through `$INTERNAL_RE`), so this new
tree only needs to show `notes` mode's side of it, per the addendum ("exit 9 in build mode is already
covered; notes mode `would not publish`").

**Falsification**, inline rather than a full legacy-script copy (the predicate itself is one line, so a
whole second `nightly_build.sh` copy would test nothing a direct check doesn't): the replaced exact-match
test (`[ "${text,,}" = none ]`) run directly against both prose forms FAILS to recognise either as
`none` -- reproducing the defect lane.local found -- while it still correctly catches a bare `none`
(not vacuous), and the new regex catches both prose forms while still leaving alone a real note that
merely mentions "none" later in a sentence.

**Counts.** Fragment alone (`SELFTEST_ONLY="86-nightly-notes"`): **76 passed, 0 failed** (up from 66/0 in
attempt 1 -- 10 new checks: 2 "not listed", 1 updated log-count check, 2 for the publish-gate fixture, and
5 for the falsification). Chain shard (`SELFTEST_ONLY="86-nightly-notes 87-nightly-trunk"`): **118 passed,
0 failed** (up from 108/0), re-run again after merging `origin/master` in (below) to confirm the merge
changed nothing this fragment depends on.

## Addendum 2 fix (relayed from lane.local via a cross-session message, verified against
`/home/justin/hakux-work/briefs/nightlynotes1009.md` at 18:32 PDT before acting on it): branch/lane-dir
mismatch, and "lane." leaking into `$INTERNAL_RE`

**Defect, as found.** A retry or split branch (e.g. `forzadecay414-fix`, `uberspike569-gpl`) does not
share its name with the lane directory its `PR.md` actually lives under (`docs/lanes/forzadecay414/`,
`docs/lanes/uberspike569/`) -- the title instead carries a `lane.<name>: ...` token naming the original.
Two independent things then went wrong on this shape:
- `lane_body_line` was called with the branch name, so `docs/lanes/<branch>/PR.md` never existed, and the
  fold's own `Release note:` line (e.g. forzadecay414's "Forza Motorsport no longer slows down over a
  race", under `performance`) was silently never read.
- `offline_clean_title` only stripped a literal `<branch>: ` prefix, so the fallback title (used whenever
  there is no note, and also exercised here while chasing the dir) kept its `lane.<name>: ` token, and
  `$INTERNAL_RE`'s `\blanes?\b` matched "lane" in it (the regex word boundary falls at the `.`, not at the
  end of "lanes"), so the change read as process commentary and was dropped or number-only even when a
  real note existed elsewhere in the same `PR.md`.

Confirmed against real history, not just the addendum's example: `uberspike569-gpl`, `memfast` (title
qualifier `W1`), and `vcpusleep` (title qualifier `(#507)`) are the same shape already on master.
`vcpusleep`'s and `shaderprebuild569`'s own `Release note:` text also confirmed the third requirement
below is real and not hypothetical: both start lowercase ("what the vCPU sleeps on...", "a game you have
played before no longer freezes the first time a scene loads.") because an offline lane's own prose was
never written with this file's list format in mind.

**Fix**, `docs/testing/nightly_build.sh`:
- `resolve_lane_dir(branch, sha, title)`: try `docs/lanes/<branch>/PR.md` at `sha` first (the common
  case, unchanged); then the title's `lane.<name>` token, if the title has one; then `<branch>` with a
  trailing `-<word>` segment stripped, one at a time, until one exists or none do (falls back to
  `branch`, same failure as before, if nothing matches). `flush_change`'s offline-fold case now calls this
  to produce `lane`, instead of using the branch directly.
- `offline_clean_title(branch, lane, title)` (was 2-arg: `branch, title`) now also strips a leading
  `lane.<lane>[ qualifier]: ` prefix (qualifier: `(#NNN)`, a bare word like `W1`, or `attempt N`) after
  the existing branch-prefix strip, using the *resolved* `lane`, not the branch -- so the token never
  reaches `$INTERNAL_RE` regardless of which of the three lookups above found the directory.
- Listed lines start with a capital letter, but **only for the lane path** (`[ -n "$lane" ]`): a numbered
  PR's note/title and a bare direct-commit subject are left exactly as their author wrote them, same as
  before this PR. Only an offline lane's own freeform `PR.md` prose is capitalised. This scoping was not
  in the addendum's own wording ("Capitalise the first letter of each listed line") but is required to
  avoid touching `87-nightly-trunk.sh` (out of this lane's territory), whose own fixture asserts an exact
  lowercase direct-commit subject (`'target/i386: trunk commit 5, landed today'`); capitalising
  universally broke that check with no way to fix it without leaving territory. The real motivating
  example for this requirement (`shaderprebuild569`, confirmed above) is itself lane-sourced, so scoping
  to the lane path loses nothing the addendum actually needed.

## Selftest for Addendum 2

Added a new fixture tree (`FIX7`, "offline-branch-mismatch") with two branches: `lane/foo-fix` (title
`lane.foo: x (#1)`, `docs/lanes/foo/PR.md` carrying `Release note (performance): a game you have played
before no longer freezes at its loading screen`) and `lane/bar-fix` (title `lane.bar: y (#2)`,
`docs/lanes/bar/PR.md` carrying `Release note (none): telemetry only, off by default`). Checked: the
`foo` note is found via the title's `lane.foo` token (the branch-named directory never exists) and
listed, capitalised, under Performance; neither `lane.foo` nor `foo-fix` survives into the body anywhere;
the `bar` mismatch with a `(none)` note lists nothing for it.

**Falsification**, against the replaced code directly: the old lookup
(`docs/lanes/<branch>/PR.md` = `docs/lanes/foo-fix/PR.md`) does not exist, while
`docs/lanes/foo/PR.md` (the new fallback) does; the old title-cleaning (strip only the literal branch
prefix, `foo-fix: `) leaves `lane.foo: x` in the text, which `$INTERNAL_RE`'s `\blanes?\b` matches (not
vacuous: the new cleaning's output, "A game you have played before...", does not match it).

Fixing the universal capitalization down to the lane-only path also meant reverting four assertion
strings in `86-nightly-notes.sh` that an earlier, broader version of this fix had capitalised by mistake
(all four are non-lane: `notes_name_the_buried_fix()`'s direct-commit subject, and three `fold_pr`
fixtures -- PR #203, #208, #172) back to the lowercase text their authors actually wrote, so they match
what the scoped fix now produces for the non-lane path. The two genuinely lane-sourced capitalised checks
(`offlinebare`'s "A vertex buffer no longer drops its last row", and FIX7's "A game you have played
before...") were never touched.

**Counts.** Fragment alone (`SELFTEST_ONLY="86-nightly-notes"`): **85 passed, 0 failed**. Chain shard
(`SELFTEST_ONLY="86-nightly-notes 87-nightly-trunk"`): **127 passed, 0 failed**, with zero edits to
`87-nightly-trunk.sh` -- the one check that shape would otherwise have broken
(`"the day's five trunk commits are in the notes"`, an exact-case direct-commit match) stayed green
because capitalisation never applies outside the lane path.

## Why attempt 1 did not finish the first time

Resumed into a worktree that already had the brief's two core edits sitting uncommitted
(`docs/testing/nightly_build.sh`, `docs/testing/jobs/selftest.d/86-nightly-notes.sh`) and no
`docs/lanes/nightlynotes1009/` directory, no commit, no PR. The code itself -- offline-fold parsing
(item 1), the publish gate (item 2), the tag push (item 3), and the five selftest fixtures (item 4) --
was already written and, on inspection, correct and complete. What was missing was everything after
that: actually running the selftest fragment and its shard, gathering the five owner-evidence bodies
(item 5), and writing `NOTES.md`/`PR.md`/`OUTBOX.md`. The most likely cause is the session ending
(context or turn limit) right after the implementation step, before any verification or write-up ran.
This attempt verified the existing diff rather than redoing it, then completed items 4 and 5.

## What the diff does (items 1-3, as found)

- `flush_change()` gained a case for `fold: lane/<lane> (offline) -- <title>` subjects, parallel to the
  existing `fold: PR #N` case. `offline_clean_title()` strips a leading `<lane>[ attempt N]: ` and a
  trailing ` (#NNN)` from `<title>`. The per-change record now also carries the lane name and the fold
  commit's `%H` (added to the `git log --format` alongside `%s`).
- The release-note lookup branches on whether a lane name was captured: `lane_body_line()` reads
  `docs/lanes/<lane>/PR.md` at the fold commit with the same `Release[ -]notes?(\(cat\))?:` regex
  `body_line()` already used for PR bodies, instead of calling `map_line`/`body_line` with the `(#433)`
  umbrella number (which is never a real PR and is never looked up as one).
- A window whose notes list nothing (`N_LISTED -eq 0`, which also covers the `TOTAL -eq 0` "no commits"
  case) sets `PUBLISH_WHY`. `notes` mode prints `would publish` / `would not publish: <reason>` after the
  body. `build` mode logs `not published: <reason>` and exits 9 before `gh release create`, after the
  build and the log are written as usual.
- On an actual `gh release create` success, the script now tags `$TAG` at `$SHA_NOW` if it does not
  already exist, and pushes it (`git push origin "refs/tags/$TAG"`, never `-f`), with a non-fatal
  `WARNING` on failure.

## Selftest

Fragment alone (`SELFTEST_ONLY="86-nightly-notes"`): **66 passed, 0 failed**.
Chain shard (`SELFTEST_ONLY="86-nightly-notes 87-nightly-trunk"`, the pair `SHARD_CHAINS` keeps together):
**108 passed, 0 failed**.

New fixtures (all passed): an offline fold with a `PR.md` release note (listed with that note, under
Rendering fixes); an offline fold with no `PR.md` (listed with its cleaned title, category guessed); an
offline fold touching only `docs/` (internal, counted, not listed); a bogus `(#433)`-numbered map row and
PR-body file that never leak into the output (the tail is never looked up as a PR); and a window whose
only change is an offline fold touching only `docs/` -- `notes` mode prints `would not publish:
no player-facing change`, and `build` mode exits 9, still builds and logs, and never calls `gh release`.

## Evidence for the owner (item 5)

All five windows were run with the FIXED script (this branch's `nightly_build.sh`), `notes` mode,
`NIGHTLY_PR_BODIES=/nonexistent` (so no `gh api` call is possible), against disposable clones of this
worktree (`git clone . <tmp>`, `origin` removed afterward so the script's own
`git fetch -q origin 'refs/tags/nightly-*...'` can't silently repopulate a tag I needed to remove to
reproduce a historical window -- see "method" below). Nothing was pushed or published; no real tag or
branch was touched.

**Method, for repeatability.** The repo tags `nightly-YYYY-MM-DD` only after a night publishes (now, per
item 3, by this same script). To see what the notes *would have said for* a past night, HEAD must be that
night's commit while the base-tag search skips that night's own tag (the real run never has it yet, since
the tag the script creates is for *this* run, after the fact). Windows 1 and 2 below needed that tag
deleted locally (then restored, to free the next window's base) before running; windows 3-5 needed nothing
special since 10-08 and 10-09 were withdrawn and were never tagged.

- **Window 1, nightly-2026-10-05..nightly-2026-10-06** (HEAD `c3a0c70ace`, base tag `d32c35d3ce`):
  ```
  Automated nightly. built from `c3a0c70ace` on `master`.

  No player-facing changes in this build.

  Plus internal test-harness work.

  Installs alongside an official hakuX build and upgrades a previous fork build in place.
  Launching from ES-DE needs the two files in `docs/es-de/`.

  _Notes updated 2026-10-10 00:04 UTC._
  ```
  Log: `5 commit(s) since nightly-2026-10-05 (d32c35d3ce): 3 emulator change(s), 0 line(s), 3 left out, 5 internal`.
  **Right.** The window's two first-parent folds that touch `hw/`-style paths (`frametrace` x2) and the other
  three folds (`dashretro`, `hitchcause`, `belowbar1005`) each carry an explicit `Release note (none): ...` in
  their own `PR.md` (telemetry off by default, status page, instrumentation only, analysis only). There
  really is nothing player-facing in this window; the old code reached "no changes" for the wrong reason
  (it counted everything as process because the subject contains the word "lane"), but the right-shaped
  answer was already correct here by coincidence of what landed.

- **Window 2, nightly-2026-10-06..nightly-2026-10-07** (HEAD `c6298a383d`, base tag `c3a0c70ace`):
  ```
  Automated nightly. built from `c6298a383d` on `master`.

  No player-facing changes in this build.

  Plus internal test-harness work.

  Installs alongside an official hakuX build and upgrades a previous fork build in place.
  Launching from ES-DE needs the two files in `docs/es-de/`.

  _Notes updated 2026-10-10 00:05 UTC._
  ```
  Log: `6 commit(s) since nightly-2026-10-06 (c3a0c70ace): 2 emulator change(s), 0 line(s), 2 left out, 6 internal`.
  **Right.** Of the 6 first-parent folds (`gpunonrender` x3, `dispatchgate1006` x2, `waitread1006`), only the
  two `gpunonrender` commits that touch `hw/` carry `Release note (none): telemetry only ... / ... off by
  default ... perflog numbers only`. The other four touch no emulator path at all. No player-facing change,
  correctly.

- **Window 3, nightly-2026-10-07..1d3b6d0148 (the 10-08 sha, `nightly/2026-10-08.log`'s `head=`)**:
  ```
  Automated nightly. built from `1d3b6d0148` on `master`.

  No player-facing changes in this build.

  Plus internal test-harness work.

  Installs alongside an official hakuX build and upgrades a previous fork build in place.
  Launching from ES-DE needs the two files in `docs/es-de/`.

  _Notes updated 2026-10-10 00:05 UTC._
  ```
  Log: `2 commit(s) since nightly-2026-10-07 (c6298a383d): 0 emulator change(s), 0 line(s), 0 left out, 2 internal`.
  **Right**, and it matches the brief's own description of this night: the only two folds
  (`harnessfix1006`, `stuckdetect1007`) touch no `hw/`/`target/`/`accel/`/`android/`/`tcg/`/`ui/`/`audio/`
  path at all -- "its APK equals 10-07's apart from the manifest." This window correctly exits 9 rather than
  publish a second no-op release under a fresh date.

- **Window 4, nightly-2026-10-07..5810476b58 (the 10-09 sha, `nightly/2026-10-09.log`'s `head=`)**:
  ```
  Automated nightly. built from `5810476b58` on `master`.

  No player-facing changes in this build.

  Plus internal test-harness work.

  Installs alongside an official hakuX build and upgrades a previous fork build in place.
  Launching from ES-DE needs the two files in `docs/es-de/`.

  _Notes updated 2026-10-10 00:05 UTC._
  ```
  Log: `5 commit(s) since nightly-2026-10-07 (c6298a383d): 1 emulator change(s), 0 line(s), 1 left out, 5 internal`.
  **Right.** Of the 5 folds (`fpstelemetry1008`, `surfdl1008`, `selfdeps`, `stuckdetect1007`,
  `harnessfix1006`), only `selfdeps` touches an emulator-gated path (`android/`, build tooling), and its own
  `PR.md` says `Release note (none): build and release tooling only; no player-visible behaviour.` Matches
  the brief's description -- "build-input plumbing only."

- **Window 5, nightly-2026-10-07..master** (HEAD `f2c6b9c5d6`, this lane's base):
  ```
  Automated nightly. built from `f2c6b9c5d6` on `master`.

  No player-facing changes in this build.

  Plus internal test-harness work.

  Installs alongside an official hakuX build and upgrades a previous fork build in place.
  Launching from ES-DE needs the two files in `docs/es-de/`.

  _Notes updated 2026-10-10 00:06 UTC._
  ```
  Log: `10 commit(s) since nightly-2026-10-07 (c6298a383d): 2 emulator change(s), 0 line(s), 2 left out, 10 internal`.
  **Right.** Of the 10 folds, only `profileddefault1008` and `selfdeps` touch an emulator-gated path, and
  both carry `Release note (none): ...` (`profileddefault1008`: the compiled default stays bandwidth,
  nothing changes unless a fleet A/B flips it; `selfdeps`: build/release tooling only). Still nothing
  player-facing as of the current tip.

**Bottom line for lane.local**: all five windows genuinely have no player-facing change, start to finish,
by the authors' own `Release note:` lines. The 10-06 and 10-07 GitHub releases' bodies ("No player-facing
changes in this build.") were the right text, reached by a bug that would just as easily have hidden a
real change (and, per the brief, did cause 10-08 and 10-09 to be withdrawn only because the mechanism gave
no reason to trust the "no changes" text it printed). Nothing here says those two releases need different
*content*; the fix is to the method that produced it, and to the publish gate so a night like 10-08/10-09
is taken down automatically instead of by hand.

## Outside this lane's territory

See `OUTBOX.md`: `docs/testing/systemd/hakux-nightly.service` line 26 needed `9` added to
`SuccessExitStatus=75`, or the new exit-9 no-op would be read by `status.sh`'s failed-unit scan as a
false alarm every night the gate holds. Not edited here (not in this lane's territory). **Done upstream**
as of this attempt's merge: lane.local's `2b9846b729` (`hakux-nightly.service: exit 9 (nothing to
publish) is not a failure (#433)`) set `SuccessExitStatus=75 9`, now on this branch via the
`origin/master` merge below. `run-nightly.sh` and `docs/lanes/nightlynotes/release_notes.tsv` were read
and need no change (also in OUTBOX, for the record).

## State: ready
