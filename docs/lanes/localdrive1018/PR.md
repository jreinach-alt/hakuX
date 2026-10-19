# drive: local tools only, act-observe instead of wait-and-fail, learn what to press

State: ready

Lane: localdrive1018            Issue: #433 (0.5)
Base: master @ 63827dc908
Files: docs/testing/titles/drive.py, docs/testing/titles/pathclass.py,
docs/testing/titles/pathclass_selftest.py, docs/testing/titles/drive-profiles/generic.toml,
docs/testing/titles/drive-profiles/gta3.toml, docs/testing/titles/drive-profiles/gta3/,
docs/testing/titles/pathknow/learned.py, docs/testing/titles/route.sh,
docs/testing/titles/routes/gta3-drive.route, docs/lanes/localdrive1018/**
Release note (none): offline test-harness/tooling under docs/testing/titles/, not emulator code; nothing
a player sees.
Prediction: none: analysis-only so far (no arm registered; the one device run this session made was a
survey on the EXISTING proven gta-3.route, not an A/B against a golden)
Needs device: no further device time requested by this lane; one survey soak already run and folded in
(see below) -- the GTA III proof run quoted in "Owner" above is lane.local's, by hand, on the Thor
Needs NDK: no

Owner (2026-10-18 ~13:50 PDT): the classifier was supposed to run on local tools with no API calls; it
doesn't, drive.py falls back to Haiku 4.5 on any `unknown` screen and fails the route when no key is set
(8 of 10 gen-* routes voided overnight 10-18 this way, memory `gen-routes-die-without-a-model-key`).
Fix: remove the key path entirely, replace idle-on-unknown with an act-observe ladder, add a learned
table so repeated screens get smarter, and fix GTA III's opening cutscene being scored `gameplay` at
0.716 as the proof.

## Done (A+B+C, this lane)

- **A** -- `ask_model()`, `MODEL`, the `models` import, `model_calls_max`, `unknown_before_model`, the
  model-call cache, and every `ANTHROPIC_API_KEY` reference are gone from `drive.py`. No API key path,
  no `claude -p`, no network call, anywhere in this loop.
- **B** -- an `unknown` screen is never idle-waited to `Fail` any more. `act()`'s unknown branch now:
  resolves whatever press is still pending from the last capture (`advanced`/`regressed` in `enter()`
  on leaving `unknown`, `changed`/`none` in `act()` via frame motion or pathclass-embedding cosine if
  motion didn't run), gives one free capture before pressing anything on a *fresh* entry into `unknown`
  (`explore_fresh`), then presses the learned table's best non-vetoed answer for this screen or the next
  untried rung of `EXPLORE_LADDER` (wrapping forever). The route's own wall-clock budget in `run()` is
  the only thing that can end a run stuck here; the branch itself never raises `Fail`.
  - The `explore_fresh` grace period exists because the AvP Extinction selftest fixture regressed
    without it: a one-frame low-confidence blip (`publisher_logo` at 0.395, between `intro_video` and
    `title`) got an exploratory press, which pushed `last_press_t` late enough that the real `title`
    screen one capture later fell inside `menu_gap_s` and missed its START press entirely (the real
    recorded run has no 11th frame to recover on). Justified by the fixture's own data: 2 of its 3
    `unknown` frames resolve for free one capture later with no input at all.
- **C** -- `pathclass.py`'s `classify_image()` now stashes its pooled, L2-normalized embedding
  (`self._last_embedding`), and `classify()` attaches it (rounded 4dp) to the answer dict -- zero other
  plumbing changes, `Client`/`serve()` already pass the dict through verbatim. `pathknow/learned.py` is
  a new module: one JSONL record per explore-press outcome
  (`{title, key, embedding, button, outcome, t, run}`), two files per record (`<title>.jsonl` and
  `_global.jsonl`), matched by embedding cosine (`SIM_BAR=0.90`, explicitly untuned -- Part D's job) or
  exact `key` when either side has no embedding, grouped by button, `regressed` outcomes veto that
  button for that screen forever, otherwise the highest-ranked (`advanced` > `changed` > `none`)
  untried, non-vetoed button wins.
- Three new `pathclass_selftest.py` mutants, all passing: a button that `advanced` a screen is
  suggested first next time; a button that ever `regressed` a screen is never suggested again even as
  the only record for it; an `unknown` screen that never resolves across a full 8-rung ladder wrap ends
  on the route's wall-clock budget (`result="window-done", rc=0`), never `Fail`.
- Found and fixed before anything was committed: `learned.py`'s `DIR`/`GLOBAL_PATH` are fixed, real
  repo-tree paths with no test isolation -- every existing selftest scenario that reaches `unknown`
  already wrote real JSONL records to `pathknow/learned/` on disk, polluting the same file a live
  `--profile generic` run reads and making test order non-reproducible (one debug run suggested a
  stale-record button first). Fixed by monkeypatching `learned.DIR`/`learned.GLOBAL_PATH` to a
  `tempfile.mkdtemp()` path at the top of `pathclass_selftest.py`'s `main()`; verified by running the
  selftest twice and diffing byte-identical output. The polluted, untracked, never-committed directory
  this produced while debugging was moved aside with `mv` (`/tmp/claude-1000/localdrive1018-cleanup/
  learned-polluted-by-testing`), not deleted, and contains no fabricated bootstrap outcomes.
- `pathclass_selftest.py` and `classify_selftest.py`: 0 failures, re-run repeatedly through every edit.

Full writeup, the Already-tried table, and the open questions: `docs/lanes/localdrive1018/NOTES.md`.

## Done (D, partial, this session)

- `drive-profiles/gta3.toml`, built and verified against 9 real hand-captured Thor frames
  (`docs/lanes/localdrive1018/gta3-frames-1018/`, labelled): a `letterbox-top` crop fixes the named
  bug (opening cutscene scored `gameplay` 0.716) via a geometry signal (the cinematic top bar,
  present only during cutscene, 143-144px vs 0px, threshold 8.0, >10x margin) that runs before
  pathclass and so never reaches it; a `hud-heart` crop (the health icon, fixed-position, bright in
  live play / dark in `play_dim_unresponsive` / absent in cutscene, threshold 15.0, >20x/>2x margin)
  bypasses pathclass's `after_title` gap, which otherwise can never confirm `play` for this title at
  all (GTA III's boot flow has no title/menu screen for pathclass's own temporal rule to key off).
  Verified via `classify.py table` across all 9 frames: cutscene frames never reach pathclass;
  `play_dim_unresponsive` frames never read `play` (the brief's one hard requirement for that state).
  Full table, the measurement tables behind both thresholds, and an honest reading of what this does
  and does not prove (including a real open question about one frame's measured motion) are in
  `NOTES.md`, "Part D, what's buildable offline."
- **Re-validated on a second, independent dataset this session**: dispatched 300 s on the existing,
  already-proven `gta-3.route` (nova, 87 continuous frames every 3 s, `1-1792377549-localdrive1018-
  3572782`) and ran `classify.py table --profile gta3.toml` over all 87 -- the real `classify_frame`
  pipeline, not a hand script. `letterbox-top` scored exact `0.0` on every one of the run's 7
  `cutscene` frames, matching the 9-still claim on a different device and a different boot run.
  `hud-heart` stayed under threshold on all 40 `play` frames with zero false `play` calls on the
  other 46 frames, but the real margin is narrower in motion than at rest -- scores ranged 1.9-12.9
  within the play cluster (vs. the clean <6 band the 9 stills showed), still safely under the 15.0
  threshold but worth carrying forward honestly rather than re-quoting the wider number. Also added
  `routes/gta3-drive.route` ("Stage 1", one step, honestly scoped: only this step has run against a
  live device) and fixed `route.sh`'s stale `drive`-step doc, which still described the pre-Part-B
  "fails on an unnamed screen" behavior. Full numbers: `NOTES.md`, "Continuation" entry.

## Not done

- **D, the rest** (car-entry detection, the pause-menu Save-row crop, the drive loop itself, a
  GTA III `classifier_confidence` floor sweep, a `play_dim_unresponsive` state of its own, a true
  held-out false-gameplay number) -- now blocked on something more specific than "no device", found
  this session: the dispatcher refuses to run a `drive` profile that is not on `master` ("A 'drive'
  profile must be in the serving snapshot ... or on the serving tree's master"), so this lane's own
  `gta3-drive.route`/`gta3.toml` cannot be dispatched until this PR merges. The one route that CAN
  be dispatched today (the existing, proven `gta-3.route`) never presses Y or opens the pause menu,
  so it cannot produce a car-entry or Save-row frame no matter how many times it is re-run. See
  `WAITING` for the full state. GTA III is also still not in `pathknow/eval/eval_set.tsv`'s held-out
  set, so the <=2% figure the brief asks for still has no blind number behind it -- the closest
  available evidence is this session's 0/46 false-`play` count on the one real run captured so far.
- **E, for Part D**: did not wire the gta3 frames into `classify_selftest.py`'s `CASES`/`FOREIGN`
  tables -- that harness wants a continuous dispatch-run capture, not 9 non-continuous hand-picked
  stills, and forcing them in risked fitting the test to the frames rather than to the behavior (see
  NOTES.md). `pathclass_selftest.py`/`classify_selftest.py` re-ran unchanged, 0 failures each.
- **E**: `docs/testing/jobs/selftest.sh` is out of scope for this diff -- `git diff --stat
  origin/master...HEAD` touches only `docs/testing/titles/**` and `docs/lanes/localdrive1018/**`,
  nothing under `docs/testing/jobs/` (that file's own scope, by its module doc: "nothing under
  jobs/ is pushed until this passes"; CI already covers it for diffs that do). Re-ran
  `pathclass_selftest.py` and `classify_selftest.py` fresh this session instead (0 failures each,
  unchanged from the Part B/C run) -- that is the selftest this PR's Done-means names ("`State:
  ready` as soon as A+B+C pass the selftest"). See `NOTES.md`, "Resume 2026-10-18 ~17:02 PDT",
  for why the prior draft of this PR claimed the heavier run instead and never finished it.
