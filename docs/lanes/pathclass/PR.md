# pathclass: a local GPU screen-state classifier for pathfind (#433)

State: ready

Lane: pathclass              Issue: #433 (0.5: 50 Playable)
Base: master @ c03e17b8a0 (merged in 2026-10-12; this checkout was found 147 commits behind at the start of attempt 3)
Files: docs/lanes/pathclass/PR.md, docs/lanes/pathclass/NOTES.md, docs/lanes/pathclass/OUTBOX.md, docs/lanes/pathclass/simpsons-hit-run.save.route, docs/testing/titles/pathclass.py, docs/testing/titles/pathclass_selftest.py, docs/testing/titles/classify.py, docs/testing/titles/drive.py, docs/testing/titles/drive-profiles/generic.toml, docs/testing/titles/pathknow/classifier/pool.py, docs/testing/titles/pathknow/classifier/label.py, docs/testing/titles/pathknow/classifier/embed.py, docs/testing/titles/pathknow/classifier/prompts.py, docs/testing/titles/pathknow/classifier/zeroshot_eval.py, docs/testing/titles/pathknow/classifier/ocr_eval.py, docs/testing/titles/pathknow/classifier/train.py, docs/testing/titles/pathknow/classifier/distill.py, docs/testing/titles/pathknow/classifier/jepa_probe.py, docs/testing/titles/pathknow/classifier/pick.py, docs/testing/titles/pathknow/classifier/head.npz, docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh, docs/testing/titles/targets.toml, docs/testing/titles/routes/gen-*.route
Prediction: none: no arm. Host-side test tooling + a drive-profile/classify.py wiring change; no device run yet.
Needs device: no    Needs NDK: no

Release note (none): host-side test tooling and a generic `drive` fallback profile; no emulator/renderer code touched.

Step 2 (reach the bar): rebuilt the label pool (5349 frames, 149 titles, 34 held-out), added 150 Haiku label
calls (1500 frames, at the cap) and tried 30 Sonnet adjudication calls (293 frames, at the cap, then
discarded -- see NOTES.md "why the Sonnet-adjudicated head was discarded"). Shipped head
(`pathknow/classifier/head.npz`, Haiku-only labels): **98/120 = 81.7%** (seen titles 52/60, held-out 46/60),
false "gameplay" on non-gameplay **4/103 = 3.9%**. Bar is >= 90% / <= 2%: **not met**, by 8.3 and 1.9 points.
All six brief-named false-pass cases (187 keyboard, Castlevania Name Entry, Super Monkey Ball Stage Select,
Sonic PAUSE, a KOF lost round, the Simpsons pause-over-play case) come out correctly not-gameplay. Warm
latency (OCR excluded, not used by the shipped head): median 21.6 ms, p90 28.5 ms, max 39.9 ms over the full
120-frame eval set -- well under the 50 ms bar.

Step 3 (generic fallback, since the bar was missed): added a confidence threshold instead of more labels, per
the brief's fallback instruction. `drive-profiles/generic.toml` sets `classifier_confidence = 0.85`; at that
threshold the head answers 39/120 frames and is right on all 39, with 0/36 false "gameplay". Wired
`classify.py`'s `classify_frame()` to ask pathclass when a profile says `classifier = "pathclass"` (one client
process per `drive` step), mapped pathclass's 17-state vocabulary onto classify.py's states
(`PATHCLASS_MAP`), and made `drive.py`'s `run()` turn a missing venv/GPU/serve process into `ROUTE FAIL drive
<profile>: pathclass unavailable (<why>)` -- never a blind press, never a model call. New
`pathclass_selftest.py` (venv-free: PIL + a stub client, no torch/GPU) covers the fail-closed path and the
recorded Simpsons run (reaches play, marks it, zero presses while playing), plus a mutant (`Driver.act`
patched to force START in `play`) that proves the no-START check actually fails when it should. All four
checks pass; `docs/testing/jobs/selftest.sh` run in full, result in NOTES.md.

Steps 4 (convert the four measurement routes) and 5 (a real Simpsons saved game) are DEFERRED per Addendum 1
(2026-10-11 23:15 PDT): the `WAITING` grant requests are withdrawn and the exploratory save route moved to
`docs/lanes/pathclass/simpsons-hit-run.save.route` (not committed under `routes/`, and not wired into any
route the dispatcher would run). Addendum 1's 6b is in this PR instead: `dispatcher.sh`'s `SCRIPT_DEPS` now
names `titles/pathclass.py` and `SNAPSHOT_GLOBS` now covers `titles/pathknow/classifier/head.npz`, so a
dispatched worker running a `drive generic` route actually has the classifier and its trained head --
without this, every queued run of the fallback would fail closed with `pathclass unavailable` for a reason
that is purely a snapshot omission, not a real unavailability. `97-dispatch-snapshot-drive.sh` extended with
a leg proving both ship, and two mutants (drop `pathclass.py` from `SCRIPT_DEPS`, drop `head.npz` from
`SNAPSHOT_GLOBS`) that must fail. Also found and fixed a second `SCRIPT_DEPS`-shaped gap:
`dispatcher.sh` names its snapshot contents in two places (the `SCRIPT_DEPS` variable and a literal loop
inside `snapshot_scripts()`) that must agree; `titles/pathclass.py` needed adding to both, not just the
one `97-dispatch-deploy.sh` first caught it on.

`docs/testing/jobs/selftest.sh` (the harness-wide gate) run in full twice: first run, 3380 passed / 1
failed (`99-lane-model-file.sh` caught a hardcoded model-id literal in `pathknow/classifier/label.py`,
carried over from attempt 2 -- fixed by reading it from `models.py` instead, like `drive.py` already does);
second run, **3381 passed, 0 failed, all 136 fragments**.

Step 6c (benchmark new titles on the classifier path) follows once this folds to master; see OUTBOX.md /
the PR comment for that wait.

**Step 6c, offline part (attempt 4, 2026-10-12):** the fold landed on `origin/master` as `a13a2f52db`
(Addendum 3). Ordered the 35 titles both `copied` (status.json) and present on the Nova gameplay-first,
excluded 4 held by `pm/owner-holds.tsv` (RalliSport exclude; Cel Damage/Arx Fatalis/Fantastic 4
below_bar+ALL+never), skipped Forza (already hand-tuned) and NFS Most Wanted (route held by
lane.nfsroute1011), and wrote `gen-<slug>.route` + a `targets.toml` row for the remaining 29 (full table in
NOTES.md). All 29 routes pass `route.sh --check`; none run yet. Device runs wait on both of Addendum 3's
dispatcher-tree gates against `/home/justin/hakuX` (still failing as of 03:58 PDT) and, per Addendum 2, on
the Nova itself (held by lane.local's overnight chain until Playable reaches 50).

This checkout was 147 commits behind `origin/master` at the start of attempt 3 (merged, not rebased, per
the lane rule against rewriting history after a prediction names refs -- there is no prediction here, but
the same merge-not-rebase habit applies). Merge was clean, no conflicts; `dispatcher.sh`'s two SCRIPT_DEPS
lists still both carried `titles/pathclass.py` afterward. `selftest.sh` run a third time in full against the
merged head: **3435 passed, 0 failed, all 137 fragments** (one more fragment than before the merge,
`99-profile-gate.sh`, from another lane's landed work).
