## #433 -- 2026-10-02 10:35 PDT

[lane.pathclass] **Interface for lane.pathfind (proposed; usable now on lane/pathclass).**
`docs/testing/titles/pathclass.py`, any python3 (it re-executes under `~/hakux-work/venvs/pathclass`):

- `python3 pathclass.py classify <frame> [--prev <frame>] [--context '{"menu_seen": true}'] [--no-ocr]`
- `python3 pathclass.py serve`: JSON lines. First line out is `{"ready": true, ...}`; then one answer per
  request line `{"frame": <path>, "prev": <path|null>, "context": {"menu_seen": <bool>}}`.
- In Python, from any interpreter: `from pathclass import Client, Unavailable`; `c = Client()` (starts one
  `serve`, models load once, ~15 s); `c.classify(frame, prev, {"menu_seen": False})`; `c.close()`.
  Inside the venv, `Classifier` is the same thing in-process.
- `python3 pathclass.py check`: exit 0 when usable.

Answer: `{state, confidence, top3, moving, diff, black, menu: [{text, box, highlighted, intent}], action: {do, why},
escalate, source, ms, ms_image}`. `escalate` is null when the local tiers decided, else the reason to ask the
language model: `low_confidence` (confidence < 0.6), `menu_no_match`, `menu_unread`, `save_load_prompt`,
`unknown`. `action.do` is the rule table's suggestion (START / A / wait / a direction / `verify` for a
gameplay candidate / `escalate`); pathfind keeps rule 5 (an input must visibly change the playfield) as the
only gameplay claim.

Fail open: no venv, no torch, no GPU or no weights -> ONE stderr line `pathclass: unavailable: <why>`, exit 3
(`serve` first prints `{"ready": false, "error": ...}`); `Client()` raises `Unavailable`. Fall back to the model.

Pass `context.menu_seen` (has this run shown a title screen or menu yet?): it is how an attract demo (gameplay
pixels before the first menu) becomes `intro_video`, and an intro after the menu becomes `cutscene`.

**First numbers** (pathknow's 120 eval frames, never trained on; half their titles held out of training):
image + OCR text rules 95/120 = **79.2%** (titles seen 56/62, held-out titles 39/58); gameplay said on a
non-gameplay frame 6/103 = 5.8% (3 of the 6 are attract demos that `menu_seen: false` turns into intro_video).
The five named false passes (187 keyboard, Castlevania Name Entry, SMB Stage Select, Sonic PAUSE, KOF lost
round) all come out not-gameplay. At confidence >= 0.6 it answers 68/120 frames, 94% right: use that bar.
Image tier 26 ms/frame warm on the RTX 2070; OCR adds a median 221 ms (p90 631) and only runs on menu-like or
gameplay-candidate frames. Below the 90% bar so far: work continues (more labels, distilled pathfind answers).

## #433 -- 2026-10-11 15:22 PDT

[lane.pathclass] **Restart: more labels (still below the bar), a confidence threshold, and the generic `drive`
fallback that actually calls this classifier.** The owner's trigger: a Simpsons Hit & Run run on the Nova
spent ~2 minutes in a blind START/A survey loop after it had already reached free roam
(`1-1791745785-nfsdefault1011-877404`, free roam at 12:49:50, looped until 12:51:44) -- this classifier,
stopped 10-02 at 79%, was never wired into anything that could have stopped that loop.

**Step 2.** Rebuilt the label pool (5349 frames, 149 titles, 34 held-out), added 150 Haiku label calls (1500
frames, the brief's cap) and tried 30 Sonnet adjudication calls (293 frames, also the cap). The Sonnet labels
raised raw accuracy (82.5% vs 81.7%) but raised false "gameplay" too (5.8% vs 3.9%) and broke one of the six
named false-pass cases (a KOF lost-round screen flips to a false gameplay pass) -- discarded in favor of the
Haiku-only head. Shipped: **98/120 = 81.7%** (seen 52/60, held-out 46/60), false gameplay **4/103 = 3.9%**.
Bar (90% / <=2%) **not met**, by 8.3 and 1.9 points. All six named cases (187 keyboard, Castlevania Name Entry,
SMB Stage Select, Sonic PAUSE, KOF lost round, and the Simpsons pause-over-play case) come out correctly
not-gameplay. Warm latency (OCR not used by this head): median 21.6 ms, p90 28.5 ms, max 39.9 ms -- well under
the 50 ms bar.

**Step 3**, per the brief's own fallback instruction (missed bar -> a confidence threshold, not more labels):
`drive-profiles/generic.toml` sets `classifier_confidence = 0.85`; at that threshold the head answers 39/120
frames and is right on all of them, 0/36 false gameplay. Wired `classify.py` to ask pathclass when a profile
says `classifier = "pathclass"` (one client process per `drive` step, not per capture), mapped pathclass's
states onto classify.py's, and made `drive.py` fail closed -- a missing venv/GPU/serve ends the route with
`ROUTE FAIL drive <profile>: pathclass unavailable (<why>)`, never a blind press or a model call. New
`pathclass_selftest.py` runs without the venv (PIL + a stub client) and proves, with a mutant, that the
no-START-in-play check is not vacuous.

Steps 4 (convert the four measurement routes) and 5 (a real Simpsons save) need routes other lanes hold --
requests in `docs/lanes/pathclass/WAITING`. Zero of 12 device runs used.

## #433 -- 2026-10-12 02:05 PDT

[lane.pathclass] **Attempt 3: Addendum 1 applied, steps 1-3 landed and ready, dispatcher fixed to actually
ship the classifier.** Attempt 2 left all of the above (the bar, the fallback, the selftest) uncommitted;
Addendum 1 (lane.local, 2026-10-11 23:15 PDT) arrived before any of it reached a commit, so it is applied
here rather than redone: steps 4-5 (route conversions, the Simpsons save) are deferred, the five `WAITING`
grant requests are withdrawn, and the exploratory save moved to `docs/lanes/pathclass/simpsons-hit-run.save.route`
(not under `routes/`, not wired into any route the dispatcher would run).

**Addendum 1's 6b**: `dispatcher.sh` snapshots a worker's files in two independent places -- the
`SCRIPT_DEPS` variable (feeds `src_hash`, checked by `97-dispatch-deploy.sh`'s closure checker) and a
separate literal copy-loop inside `snapshot_scripts()` -- and neither had `titles/pathclass.py`, nor did
`SNAPSHOT_GLOBS` have `titles/pathknow/classifier/head.npz`. Every queued `drive generic` run would have
failed closed with `pathclass unavailable`, not from real unavailability but from a snapshot omission. Fixed
both lists and `SNAPSHOT_GLOBS`; extended `97-dispatch-snapshot-drive.sh` with a leg proving both ship, two
mutants (drop `pathclass.py` from `SCRIPT_DEPS`, drop `head.npz` from `SNAPSHOT_GLOBS`) that must fail.

`docs/testing/jobs/selftest.sh` (the harness-wide gate, 136 fragments) run in full twice: first run, 3380
passed / 1 failed (`99-lane-model-file.sh` caught a hardcoded model-id literal in
`pathknow/classifier/label.py`, carried over uncommitted from attempt 2 -- fixed by reading it from
`models.py`, matching `drive.py`'s existing pattern); second run, **3381 passed, 0 failed, all 136
fragments**. `State: ready`.

Step 6c (benchmark new titles on the classifier path) follows once this folds to master -- see the PR
comment for that wait. This checkout was found 147 commits behind `origin/master` at the start of this
attempt; merging it in before pushing.
