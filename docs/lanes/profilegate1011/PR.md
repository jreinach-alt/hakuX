# profilegate1011: the profile gate -- a title run needs the title's profile, unless it is finding a route (#433)

State: ready

Lane: profilegate1011      Issue: none (harness defect, dispatched directly by lane.local, #433 umbrella)
Base: master @ 4c9132fa17
Files: AGENTS.md, docs/lanes/profilegate1011/NOTES.md, docs/lanes/profilegate1011/OUTBOX.md, docs/lanes/profilegate1011/PR.md, docs/lanes/profilegate1011/profilegate1011-inventory.py, docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/61-soakvideo1011.sh, docs/testing/jobs/selftest.d/62-routerefs-soakvideo1011.sh, docs/testing/jobs/selftest.d/89-title-verdict.sh, docs/testing/jobs/selftest.d/96-failgate.sh, docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh, docs/testing/jobs/selftest.d/99-pilot-gate.sh, docs/testing/jobs/selftest.d/99-profile-gate.sh, docs/testing/request.sh, docs/testing/titles/pathfind.py, docs/testing/titles/profile-transition.toml, docs/testing/titles/titlestate.py, docs/testing/titles/titlestate_selftest.py
Prediction: none: no arm -- a scheduler/gate change, not a rendering or perf one
Needs device: no    Needs NDK: no

## What changed

The profile gate (`admit()`, `docs/testing/titles/titlestate.py`), wired into
`request.sh`'s queue-time checks and `pathfind.py`'s dry-mode sessions, per
the owner's rule (10-11) and Addenda 1-3: a title run is refused when it
would redo work already kept --

- **R1**: a first-run route remaking a profile the title already has
  (override: `--remake-profile "<why>"`).
- **R2**: a first-run route that keeps no profile of its own (no `mark
  profile-saved`), on a title with none already -- or (unchanged from before
  Addendum 1, see Finding below) an `any`/no-route run with no profile and no
  route-finding.
- **R3**: finding a route blind on a title that already has a proven one
  (override: `--path-broken <result id>`).
- **Both**: `--find-route "<why>"` admits a run whose purpose is finding or
  re-proving a route, never scored as a verdict (title_verdict.py side still
  needs the OUTBOX.md patch below to void it explicitly).
- `profile-transition.toml` grandfathers routes not yet converted to the new
  scheme.

This session (attempt 3, Addendum 4) added one defect fix and finished the
wrap-up:

- **Bare-TitleID defect** (`request.sh`, `titlestate.py`'s new
  `iso_for_tid()`): `--title 5454000F` passed queue-time checks (`tid_for_iso`
  takes the 8-hex head of any name, and a bare TitleID is its own head) and
  failed mid-claim with "title not on device". Refused at queue time now,
  naming the on-device file name when `targets.toml` or a past request knows
  one, or `devices.sh` when neither does. Selftest cases A8-A10 and mutant M9
  in `99-profile-gate.sh`.
- Merged `origin/master` twice (clean both times) and ran the full selftest
  suite once (sharded 0-3/4, ~3426 checks, 137/137 fragments, 0 failed after
  fixes -- see NOTES.md). Six fragments from five other lanes on #433 (not
  previously tested against this gate) queued a fictitious or profile-less
  title with no `--find-route`; fixed each with `--find-route` and a comment
  naming why, never by weakening the gate.

## Finding, not fixed here (flagging for lane.local)

`admit()`'s `any`/no-route branch (titlestate.py ~1392-1402) refuses a title
with no golden and no route at all ("has no profile (no golden) and no
route-finding"). Addendum 1's own "Admitted" list says the opposite: `any`
and no-route runs admit "whether or not the title has a golden". This
predates attempt 3 (A1's own existing test already asserts the refusal as
correct) and is not something this session's Addendum-4 scope covers --
resolving it needs an owner/lane.local call on which reading is intended
before touching logic three attempts have already built and tested against.
Full writeup in NOTES.md.

## Still open (not this lane's file to touch)

`docs/lanes/profilegate1011/OUTBOX.md` carries a patch for
`title_verdict.py` (held by lane.failgate): void a `find_route` run's
verdict explicitly, so a find-route soak that happens to clear the fps bar
is not written up as a normal Playable pass. Not applied by this lane.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
