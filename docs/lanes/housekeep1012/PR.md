# housekeep1012: remove obsolete and conflicting agent instructions (#433, 0.5)

State: draft

Lane: housekeep1012          Issue: none (#433 umbrella)
Base: master @ 1ed3ac8f39
Files: AGENTS.md, docs/testing/jobs/roles/cloud.md, docs/testing/jobs/roles/lane.md, docs/testing/jobs/ops/escalate-role.md, docs/lanes/housekeep1012/PR.md
Prediction: none (instruction text only)
Needs device: no    Needs NDK: no

Harness housekeeping only: removed or minimally corrected instruction text
that no longer matches the harness it describes. No redesign, no new rules,
no reorganizing.

- `AGENTS.md:781` said debug builds are labelled "hakuX (debug)"; the
  gradle config (`android/app/build.gradle.kts`, debug buildType) sets
  `app_name` to "hakuX (test builds)". Corrected the label to match.
- `AGENTS.md:836-840`: the "LIFTED 2026-09-18. Both devices are online"
  banner is stale — the Ayn Thor's fan has since failed (owner 09-29) and
  the device is out of service; titles run on the Nova only
  (`docs/lanes/thorheat/NOTES.md`, the live `lanelocal-fanwait` device
  hold, and AGENTS.md's own line 1025 "the only Nova" contradict the
  banner). Added a one-line "superseded again" note ahead of the banner
  rather than deleting it, since the banner's own text argues two lines
  later that it still documents how a hold mechanism works.
- `docs/testing/jobs/roles/cloud.md:79-80` and
  `docs/testing/jobs/roles/lane.md:158-160` both claimed "CI is free on
  this public repository, runs on every PR" — conflicting with
  `AGENTS.md`'s current, dated "Non-negotiables" section ("CI is the
  forge's... They run on a ready PR... never on every push"), corroborated
  by `docs/testing/desktop-gate-warnings.md:4-6`. Corrected both to match
  the forge-CI policy.
- `docs/testing/jobs/ops/escalate-role.md:12` said "GitHub is down" as the
  reason to stay local; GitHub has been up since 2026-10-05
  (`AGENTS.md` lines ~37-68). Corrected the premise to "GitHub is up, but
  stay local," leaving the operative "never run `gh`" directive unchanged
  since nothing in scope lifted this role's local-only constraint.

Full candidate list, evidence, and items explicitly left for the owner are
in the lane report (not committed; see session output).

Release note: none

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
