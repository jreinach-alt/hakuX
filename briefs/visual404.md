# lane.visual404 -- #404: flag rendering defects in scripted-play screenshots

Lane: visual404
Issue: #404
Base: origin/master
Files: docs/testing/titles/visual_score.py, docs/testing/jobs/selftest.d/99-visual-score.sh, docs/lanes/visual404/**, docs/testing/predictions/visual404-*.json

## Why (evidence)
The owner sequenced #404 to start after the first gameplay-FPS table was posted on #397 and the ops flow fix was in. Both have happened: the pass-1 table is #397 comment 5849041338 (12:09 PDT), and harness_health.py runs every ops tick. hostops unblocked the tracker row at 13:15 PDT on 2026-09-26, answering lane.local's board request in dispatch/board-requests/host.md. The frames are already on disk:
`/home/justin/hakux-work/dispatch/results/0-0-y-1790433159-titleplay-p1-*/route-frames/` holds 17 titles at about 38 PNGs each, 1920x1080. lane.titleplay's per-title verdicts in #397 say which frames are gameplay. Earlier `*-gamecheck-*` results in the same directory may hold other titles, such as MechAssault.

## Build (OFFLINE, no device time)
Read #404's body first: it has the owner's three layers and the positive-control rule.
1. `visual_score.py`: reference-free detectors per frame and per route:
   - large solid-colour blocks (HUD and overlays excluded by a stated rule);
   - pure-magenta or NaN colours;
   - black or blank frames;
   - frame-to-frame flicker.
   Output one row per frame, with a status tag, the detector hits and their areas.
2. Positive controls before any verdict:
   - Galleon's #77 stipple must be flagged. Galleon frames are in titleplay-p1-galleon.
   - Find a capture on disk that shows MechAssault's red box, and it must be flagged. If no capture shows it, say so. Do not queue a device run for it without a 2-request pilot; the pilot rule applies.
   - At least three titles that the pass-1 table calls clean must come back clean.
3. Contact-sheet rubric (layer 2): a per-title sheet of the gameplay frames, reviewed with vision, one line per title: player model, textures, large colour errors.
4. A selftest fragment covering the detectors on synthetic frames, with one positive and one negative per detector.

## Proof
Post a per-title table on #404: detector hits, the rubric line, and each positive control's result.
Open a PR with the tool and the NOTES, and mark it ready when the controls hold.

## Do not
- Do not edit board files (territory.toml, nv2a_issues.toml).
- Do not hold a device.
- Do not restore dispatch/parked/titleplay-p1-20260926: the owner stopped it.
- Do not end the session waiting on a background task. It dies with the session. Queue work, post a `waiting:` comment, and end.
