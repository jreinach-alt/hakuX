# nightlynotes1009: list offline folds, and publish nothing when nothing changed (#433, 0.5)

State: ready

Lane: nightlynotes1009          Issue: none (#433 umbrella)
Base: master @ f2c6b9c5d6
Files: docs/lanes/nightlynotes1009/NOTES.md, docs/lanes/nightlynotes1009/OUTBOX.md, docs/lanes/nightlynotes1009/PR.md, docs/testing/jobs/selftest.d/86-nightly-notes.sh, docs/testing/nightly_build.sh
Prediction: none: notes-mode / selftest change, no device arm
Needs device: no    Needs NDK: no
Release note: none. This PR changes no emulator code (nightly build/release tooling and its selftest only).

The 10/6 through 10/9 nightlies all showed the identical body, "No player-facing changes in this build.",
because every one of those nights' changes was an `offline_fold.py` merge (`fold: lane/<lane> (offline) --
<title>`), which `flush_change()` fell through to the unmatched-subject branch on: the whole subject
contains the word "lane", so `$INTERNAL_RE` counted it process regardless of what it actually changed.

1. `flush_change()` now matches `fold: lane/<lane> (offline) -- <title>` the same way it already matches
   `fold: PR #N ... -- title`: the title is cleaned of its lane prefix and `(#NNN)` tail, and its release
   note comes from `docs/lanes/<lane>/PR.md`'s own `Release note:` line at the fold commit
   (`lane_body_line()`), never from a PR lookup against the `(#433)` umbrella number. `$INTERNAL_RE` still
   applies to the cleaned title afterward, so a telemetry/analysis/audit lane is still internal -- just for
   the right reason now, read from what the lane's own author said it does.
2. A window whose notes list nothing no longer publishes. `build` mode still builds and writes the notes
   (so the APK is on disk if wanted), logs `not published: no player-facing change since <BASE_TAG>`, and
   exits 9 -- a documented, distinct code -- before `gh release create`/upload and before the tag push.
   `notes` mode prints `would publish` / `would not publish: <reason>` so the same decision is visible
   without a build.
3. After a successful publish, the script tags `$TAG` at the built sha (create-only, never `-f`) and pushes
   it to origin, with a non-fatal `WARNING` on failure -- so tomorrow's base-tag search does not depend on
   anything outside this script running.
4. `86-nightly-notes.sh` gained fixtures for: an offline fold with a `PR.md` note, one without, one
   touching only `docs/`, a bogus `(#433)` PR lookup that must never fire, and a window whose only change
   is internal (must not publish, must exit 9, must still build). Fragment alone: 66/66. Chain shard
   (`86-nightly-notes 87-nightly-trunk`): 108/108.
5. Evidence for lane.local, run with the fixed script against the five windows the brief named
   (nightly-2026-10-05..06, 06..07, 07..the 10-08 sha, 07..the 10-09 sha, 07..master): all five genuinely
   have no player-facing change, confirmed from each folded change's own `Release note:` line against its
   diff, not just from the mechanism's say-so. Full bodies, logs and the per-change check are in `NOTES.md`.
   The 10-06 and 10-07 GitHub release bodies were already the right *text*; the bug was in how the old code
   reached it (and would have hidden a real change the same way), not in those two nights' content.

**Outside this lane's territory** (see `OUTBOX.md`): `docs/testing/systemd/hakux-nightly.service` only
whitelists exit 75 as non-failure. The new exit 9 would otherwise be read as a failed unit by
`status.sh`'s `systemctl --user list-units --state=failed` scan -- a false alarm for a deliberate no-op.
Asking lane.local to add `9` to its `SuccessExitStatus=75` line. `run-nightly.sh` was read and needs no
change: it already propagates any exit code other than 75 unchanged.
