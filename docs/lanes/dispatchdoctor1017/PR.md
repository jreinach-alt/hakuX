# dispatchdoctor1017: the dispatcher stages a missing title before it fails, and a Sonnet doctor diagnoses what stops a run

State: ready

Lane: dispatchdoctor1017            Issue: none (harness lane, owner's word 10-17)
Base: master @ 15f8524be1
Files: docs/lanes/dispatchdoctor1017/**, docs/testing/dispatcher.sh, docs/testing/devices.sh, docs/testing/request.sh, docs/testing/dispatch_doctor.sh, docs/testing/titles/titlestate.py, docs/testing/jobs/models.toml, docs/testing/jobs/allowed-tools.doctor, docs/testing/jobs/roles/dispatchdoctor.md, docs/testing/jobs/selftest.d/98-dispatch-doctor.sh
Prediction: none: no arm (harness change; the selftest fixtures decide it)
Needs device: no    Needs NDK: no

Release note (none): dispatcher harness; no emulator code.
Selftest: 40-arms-refusal 50-arms-requeue 51-dispatch-hardening 55-affinity-offpool 56-desktop-worker 57-vsh-disc 58-pull-verify 61-soakvideo1011 62-routerefs-soakvideo1011 76-pr-sweep 78-sweep-remote 79-stop-hook-hold 84-perf-regimen 85-savestate 86-build-stamp 86-fold-regressed 88-ownersign1012 89-title-verdict 89-usage-mode 90-fold-notes 92-arms-skip-told 94-arms-disc-narrow 94-arms-label-state 95-affinity 96-failgate 97-dispatch-deploy 97-dispatch-snapshot-drive 97-dispatch-snapshot-rename 97-release-prio 98-dispatch-doctor 98-dispatch-late-device 99-arms-confounded-pair 99-battery-admit 99-build-gate 99-display-covered 99-fan-mode 99-fg-unreadable 99-fleet-absent-device 99-fleet-battery-gate 99-folder-pref 99-handback-draft 99-hdd-split 99-hold-take 99-iso-roots 99-lane-model-file 99-pilot-gate 99-profile-gate 99-request-priority-flag 99-request-release-prio 99-restore-priority 99-title-state 99-usb-dialog 99-wake-after-gate -- every fragment that sources, runs, copies or lints a file this diff changes (dispatcher.sh, devices.sh, request.sh, dispatch_doctor.sh, titlestate.py, models.toml, allowed-tools.doctor), plus 50-arms-requeue (51's fixture) and 99-title-state; see "Selftest" below for what was left out and why. Run by the lane on 6c2a4b5fdd: 1599 passed, 0 failed.

## Section 1 -- the deterministic staging fast path (done)

A request whose title is sitting on a host D: staging root, but not on the
device, no longer ERRORs "title not on device" -- the single largest ERROR
class across the last ~5000 dispatch results (~45 of them). The dispatcher
now checks staging (and, failing that, a read-only console FTP mirror)
before giving up, pushes under a strict "never delete anything a queued
request still wants, never touch the floor or app data" room-making rule,
and only falls through to the original ERROR text if staging genuinely has
nothing either. See `docs/lanes/dispatchdoctor1017/NOTES.md` for the full
design.

## Section 1b -- auto-attach a recorded route when a soak names none (done)

A soak queued with no `--route`, or only the generic `survey`, now gets
this title's best recorded route attached automatically: a route this host
has proven reaches gameplay first, a `targets.toml`-configured one
otherwise, never a guess. Attaches at both queue time (`request.sh`) and
claim time (`dispatcher.sh`, for a request written before this existed),
reusing the exact same resolve/`--check`/crop-embed/profile-gate path a
user-typed `--route` takes. Suppressed whenever `--find-route`/
`--remake-profile`/`--path-broken` is also given -- each is itself a
deliberate statement about route/profile handling that an attach would
second-guess (a real regression this surfaced and fixed in
`99-profile-gate.sh`'s A3/A4/M9 legs). See NOTES.md's "Section 1b" heading.

## Section 1c -- profile-backup discovery/restore before launch (done)

Before a soak's first run on a title with no golden save, the dispatcher
now searches four places in order (the title's own unpromoted store save,
a reset's exported `saves/<TID>` tree, a staging-archive `saves/<TID>`
tree, the device's own `hdd.img.bak-auto`) and promotes the first hit to
that title's first golden, rather than launching blind. After push, the
claimed save (if any) is verified actually present on the pushed disk
before the soak proceeds; a mismatch refuses (`hdd.refused`) rather than
soaking a title with the wrong save loaded.

## Section 2 -- `dispatch_doctor.sh`, the Sonnet-model diagnosis step (done)

The owner's complaint named this directly: "The dispatcher should have
sonnet reasoning. It should troubleshoot and resolve launch failures. It
should not be just a script." `docs/testing/dispatch_doctor.sh` (new)
classifies a recoverable ERROR class, gates on owner-play/battery/a
hold-file (standing in for a Halo-priority window, since no dedicated
mechanism exists), caps at one doctor attempt per request plus an hourly
cap, builds a read-only evidence brief, and runs a headless Sonnet session
(`claude -p`, `jobs/roles/dispatchdoctor.md`, a narrow `jobs/allowed-
tools.doctor` with no raw adb/git/gh/rm) that may run at most one of
`push-iso`/`attach-route`/`restore-profile` before writing `retry` or
`give-up: <reason>` to `doctor.md`. `dispatcher.sh` gained one new
function, `maybe_run_doctor`, called at the 5 ERROR sites that are real
failures (never at the 3 deliberate safety-refusal sites); a `retry`
verdict requeues the same request id exactly the way the existing
WSL-interop one-shot requeue already does. Every session logs one
`logs/dispatch-doctor.tsv` row and one `doctor-lessons.md` line (by class,
not by request), so a fix that keeps getting billed to a model session
is visible as a candidate for promotion into Section 1's deterministic
path. See NOTES.md's "Section 2" heading for the full design, the three
real bugs the selftest caught, and a sed-extraction gotcha worth knowing
before anyone else edits the `title-not-on-device` ERROR site again.

At Section 2's commit (75b1d3475d), the full unscoped selftest (all 148
fragments) gave 3651 passed, 0 failed. The current head's results are
under "Selftest" below.

Two known, deliberate limitations: the Halo-priority gate is only a
generic hold-file check (nothing dedicated exists to integrate with), and
no live device was used for this section -- judged not worth the risk for
a harness-only change the fake-adb/fake-claude selftest fixtures already
cover end to end.

## Section 3 -- a miss says where it looked, what it found, what the doctor decided (done)

Every result dir now has an `inputs.txt` with one `disc:`, `route:` and
`profile:` line, written on every outcome, success or not. Each line says
which of the three inputs the dispatcher saw to and how, so a reader of
one result dir never needs `dispatcher.log`. Some examples:
- `disc: pushed <D: path> -> <device path> (2.0 KiB, sha checked)`
- `disc: NOT STAGED: no CAFE7779-* image under <roots>; console: the console did not answer (stage_xiso.py exit 3)`
- `route: attached '<name>' for <TID>, …; why: proven, a judged run on it reached gameplay`
- `route: none: no proven or recorded route for <TID> …; the generic survey does not reach gameplay for most titles`
- `profile: <TID> has no golden and no backup was found (looked: store, hdd-reset, archive, device-bak-auto); nothing restored, no profile created`
- `profile: device check: save <id> pulled back off <path> and verified`

The title-not-on-device ERROR now leads with what staging actually found
instead of always "none had it". Staging may have found the image and been
refused by the free-space floor, the console may have been down or paused,
or the title may have had no TitleID. The ERROR then gains the doctor's
decision: `doctor: retry (see doctor.md)`, `doctor: give-up: <reason>`, or
`doctor: give-up: not a class the doctor recognises`.

A recorded route whose crop is missing now refuses the claim, naming the
crop (`refused before the soak: … waitfor 'title_screen': no reference
crop <path>`). Before, it fell back to the survey. request.sh already
refused this at queue time.

A crashed route lookup now says so. Before, a `suggest-route` traceback
(a snapshot with no `targets.toml`, snaptargets1018's defect) read as
"no proven or recorded route". Now the route line says the lookup failed,
gives the error, and the request runs as queued.

Two latent faults are fixed:
- The doctor never ran from the dispatcher as Section 2 committed it.
  The script was at mode 644 behind an `[ -x ]` guard; the guard is now
  `[ -f ]`, since the script is run with `bash`.
- The 98 fixtures could reach the real console mirror. Every fixture env
  now points `STAGE_XISO`/`HAKUX_XISO_DIR` at fakes.

The hourly-report line ("dispatch doctor: N sessions, M fixed, K gave up")
lives in `host-tools/hourly_report.sh`, which belongs to lane.local, so it
is a request in `OUTBOX.md` with the block ready to paste. Details are
under "Section 3" in NOTES.md.

## Selftest

How the list was chosen: the diff changes `dispatcher.sh`, `devices.sh`,
`request.sh`, `dispatch_doctor.sh`, `titlestate.py`, `models.toml`,
`allowed-tools.doctor` and `roles/dispatchdoctor.md`. A grep of
`selftest.d/` for those names hit 63 fragments, and I read every hit.
- Kept: the 51 that source, run, copy or lint one of the changed files.
- Added: 50-arms-requeue, because 51-dispatch-hardening FAILs alone with
  "fixture not as 50 leaves it", and 99-title-state, which tests
  `titlestate.py` without naming it.
- Dropped: 11 fragments whose hit is only prose, or a different file such
  as `roles/board.md` or `roles/lane.md`: 77-issue-sweep, 97-board-release,
  98-audit-outlet, 98-lane-shape, 99-arms-refused-requeue,
  99-handback, 99-handback-idle, 99-handback-runs, 99-hitch-report,
  99-lane-no-background, 99-release-note-line.
- Also dropped: 66-status-titles. It runs `titlestate.py no-save`, and this
  lane's `titlestate.py` diff only adds five new subcommands (168
  insertions, 0 deletions). So nothing 66 calls changed.

The fragments that test this change directly are 98-dispatch-doctor (this
lane's), 99-iso-roots (it cuts the soak block out of `dispatcher.sh` and
matches the miss ERROR's suffix), 99-profile-gate (the claim-time route
attach, now fatal on refusal) and 97-dispatch-deploy (the snapshot
closure).

Full unscoped run on 6c2a4b5fdd (this lane merged with origin/master
4a504d9aaa): **3683 passed, 1 failed, all 149 fragments.** The one FAIL is
66-status-titles, "check --pages passes when every page agrees …": its
fixture README still carries a numbered Playable line, and master's
48a6db90c5 (compat1017b) made `title_registry.py check --pages` reject
that. It comes from master; this lane touches neither file.

The named set (the `Selftest:` line above, 53 fragments) was run in this
session on 6c2a4b5fdd, in the selftest's own order: **1599 passed, 0
failed, PARTIAL: 53 of 149.** That includes 51-dispatch-hardening's E/E2
legs, which pass with 50 ahead of them.

After that, one function changed: `ensure_route_attached` now says when
its route lookup crashed. The fragments that drive it were re-run on that
head: 13 fragments, 419 passed, 0 failed.

`preflight.sh --allow-tracker`: every gate is ok except `territory`, which
fails on four double claims in `origin/board:territory.toml`. The one
touching this lane is `docs/testing/dispatcher.sh`, which is also claimed
by snaptargets1018 (started 10-18 ~01:45 PDT to ship `targets.toml` in the
snapshot). A lane cannot clear that, and fold order resolves it.

## Deploy

lane.local deploys after the fold. A running dispatcher keeps the version
it started with, so none of this is live until it restarts. No live device
run was made. Done means #1-#4 are shown against the fake adb and claude
fixtures; the first real claims after the deploy are the live check.

## Still to come

Nothing in the brief's three sections. The hourly line waits on lane.local
(`OUTBOX.md`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
