# dispatchdoctor1017: the dispatcher stages a missing title before it fails, and a Sonnet doctor diagnoses what stops a run

State: draft

Lane: dispatchdoctor1017            Issue: none (harness lane, owner's word 10-17)
Base: master @ 15f8524be1
Files: docs/lanes/dispatchdoctor1017/**, docs/testing/dispatcher.sh, docs/testing/devices.sh, docs/testing/request.sh, docs/testing/dispatch_doctor.sh, docs/testing/titles/titlestate.py, docs/testing/jobs/models.toml, docs/testing/jobs/allowed-tools.doctor, docs/testing/jobs/roles/dispatchdoctor.md, docs/testing/jobs/selftest.d/98-dispatch-doctor.sh
Prediction: none: no arm (harness change; the selftest fixtures decide it)
Needs device: no    Needs NDK: no

Release note (none): dispatcher harness; no emulator code.

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

Full, un-scoped selftest run (no `SELFTEST_ONLY`, all 148 fragments):
**3651 passed, 0 failed.**

Two known, deliberate limitations: the Halo-priority gate is only a
generic hold-file check (nothing dedicated exists to integrate with), and
no live device was used for this section -- judged not worth the risk for
a harness-only change the fake-adb/fake-claude selftest fixtures already
cover end to end.

## Still to come

Section 3 (richer ERROR text beyond what 1/1b/2 add, an hourly-report
line via an OUTBOX request to lane.local). Staying in draft until that
lands or a blocker is written up.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
