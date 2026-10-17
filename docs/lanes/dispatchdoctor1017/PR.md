# dispatchdoctor1017: the dispatcher stages a missing title before it fails, and a Sonnet doctor diagnoses what stops a run

State: draft

Lane: dispatchdoctor1017            Issue: none (harness lane, owner's word 10-17)
Base: master @ 15f8524be1
Files: docs/lanes/dispatchdoctor1017/**, docs/testing/dispatcher.sh, docs/testing/devices.sh, docs/testing/request.sh, docs/testing/dispatch_doctor.sh, docs/testing/titles/titlestate.py, docs/testing/jobs/models.toml, docs/testing/jobs/allowed-tools.doctor, docs/testing/jobs/selftest.d/98-dispatch-doctor.sh
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

Full, un-scoped selftest run (no `SELFTEST_ONLY`, all 147 fragments):
**3580 passed, 0 failed.**

## Still to come

Section 1c (profile-backup discovery/promotion before launch), Section 2
(`dispatch_doctor.sh`, a Sonnet-model headless diagnosis step), Section 3
(richer ERROR text beyond what 1/1b add, hourly-report line). Staying in
draft until those land or a blocker is written up.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
