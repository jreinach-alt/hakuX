# lane.nightlynotes1009

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

See `OUTBOX.md`: `docs/testing/systemd/hakux-nightly.service` line 26 needs `9` added to
`SuccessExitStatus=75`, or the new exit-9 no-op is read by `status.sh`'s failed-unit scan as a false
alarm every night the gate holds. Not edited here (not in this lane's territory). `run-nightly.sh` and
`docs/lanes/nightlynotes/release_notes.tsv` were read and need no change (also in OUTBOX, for the record).

## State: ready
