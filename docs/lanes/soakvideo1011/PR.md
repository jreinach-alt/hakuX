# soakvideo1011-step2: device proof of the dispatcher's soak video capture (#433, 0.5)
State: ready

Lane: soakvideo1011            Issue: none (#433 umbrella)
Base: master @ 3f1eace130 (merged up from this branch's original base, the
lane/soakvideo1011 fold b73d50a070, after the device run below -- no
functional change for this PR; see "Merge note")
Files: docs/lanes/soakvideo1011/NOTES.md, docs/lanes/soakvideo1011/PR.md
Prediction: none: survey run, not an A/B arm (see below)
Needs device: yes (Nova, one soak)    Needs NDK: no

## What this is

Step 2 of lane.soakvideo1011's brief (#433): a device proof that the
dispatcher's new soak-video capture (`--video-seconds`/`--video-after`,
folded as `b73d50a070`) works on the Nova, end to end, including the
Addendum 1 fix that let `hitch_report.py`'s window read the dispatcher's own
`frames/` stills. `request.sh`, `dispatcher.sh` and `AGENTS.md` are released
to `lane.profilegate1011` (Addendum 4) and are not touched here; this PR is
the Step-2 proof only, on its own branch per Addendum 4 ("Step 2 changes go
on a new branch `lane/soakvideo1011-step2` from origin/master").

## The request

```
docs/testing/request.sh --who lane.soakvideo1011 --issue 433 \
  --purpose "Step 2 device proof: dispatcher-recorded video during a routed soak (#433)" \
  --title "54540082-Grand_Theft_Auto_San_Andreas.xiso.iso" --route gta-sa \
  --seconds 600 --frames-every 5 --video-seconds 120 --video-after 30 \
  --device nova \
  --no-expect "single device proof of Step 1's video capture path; not an A/B arm, and no prior gfps figure exists for this route+toggle to compare against (fastpaths1010's two gta-sa runs recorded surface-dropout frames, not a gfps reading)"
```

`--no-expect` rather than a registered prediction: this is one survey run of
new infrastructure, not an A/B arm with a comparison side (request.sh's own
`--no-expect "survey, not an A/B arm"` precedent). Queued at `--ref HEAD`,
which resolved to `b73d50a070` -- the same sha as `origin/master`, so the
Nova ran the just-folded code, no rebuild drift.

Queued as `1-1791756360-lane.soakvideo1011-3149619`. The Nova was running a
long backlog of other lanes' soaks (nfsdefault1011, profileconv1011,
lane.local, gtaroutes1011 x2, lane.gtasagpu1011 x2, snapshot1011,
nfsroute1011, plus two blocker-tier lane.local jobs that preempted
correctly) -- queued ~16:26 PDT, started running ~17:47 PDT, finished
~17:57 PDT. All of that is other lanes' normal traffic on the shared Nova;
nothing here touched a hold or the queue order.

## Result and the four legs

Result dir: `dispatch/results/1-1791756360-lane.soakvideo1011-3149619/`.

| leg | requirement | observed | pass |
|---|---|---|---|
| segment duration | two mp4s, 55-61 s each (`duration_s`) | `v00001.mp4` 60.026 s, `v00002.mp4` 60.014 s | yes |
| segment duration (ffprobe cross-check, owner-approved) | matches the box-reader figure | `v00001.mp4` 60.025422 s, `v00002.mp4` 60.013411 s | yes |
| nonzero samples | `samples` field present and > 0 | 3640 and 3640 | yes |
| segment gap | < 2 s between segment 1's end and segment 2's start (wall times) | `(1791766335.0) - (1791766274.0 + 60.026)` = 0.974 s | yes |
| device left clean | `adb -s ee317437 shell ls /sdcard/Download/` shows no `hakux_vid_*` | 20 unrelated files, no `hakux_vid_*` | yes |
| stills intact | `frames/` still has its captures | 108 stills + `frames/index.tsv` (the Addendum 1 fix) | yes |

`result.json`'s `video` dict:

```json
{
 "seconds": 120, "after": 30, "mark_wall": 1791766243.0,
 "segments": [
  {"file": "v00001.mp4", "start_wall": 1791766274.0, "bytes": 47368534, "duration_s": 60.026, "samples": 3640},
  {"file": "v00002.mp4", "start_wall": 1791766335.0, "bytes": 64590783, "duration_s": 60.014, "samples": 3640}
 ],
 "bytes": 111959317
}
```

`frames`: 108 stills every 5 s, 105,833,610 bytes. `seconds`: 600. 17,255
logcat lines. No `pulled` globs asked for.

The Addendum 1 fix is confirmed live end to end on a real run, not just the
fixture: `frames/index.tsv` exists (device-clock `HH:MM:SS` per still) and
`title_verdict.py`'s `static_window` reads `measured: true, n: 67, source:
"frames"` on a copy of this result -- the exact failure mode Addendum 1
fixed (`window unmeasured: 0 post-mark ... frames/ sample(s)`) does not
recur.

## gfps (measured figure, no claim beyond it)

Read with `title_verdict.py` on a scratch copy
(`docs/lanes/soakvideo1011/scratch/step2-1-1791756360-lane.soakvideo1011-3149619/`,
never the original result dir): `g_fps_mean_reported_not_judged: 29.7`
(target 30.0, 193 post-mark `hakuX-perf` windows, `fps_window_median`
29.93). This is the first gfps figure for GTA San Andreas's `gta-sa` route
on this harness -- `fastpaths1010`'s two prior runs on this route
(`1-1791733219-lane.local-3377194`/`...-3377243`, see its PR.md "GTA San
Andreas surface dropouts" section) recorded only the surface-dropout
stills, not a gfps reading, so there is no prior number to compare against.
This run also costs frame rate for both `--frames-every` and
`--video-seconds` (noted in `result.json`'s own fields for exactly this
reason), so it is not comparable to a clean soak's gfps either -- stated
plainly, not implied.

## mp4 paths

For the owner to watch (lanes cannot decode video here):

- `dispatch/results/1-1791756360-lane.soakvideo1011-3149619/video/v00001.mp4`
- `dispatch/results/1-1791756360-lane.soakvideo1011-3149619/video/v00002.mp4`

Release note (none): device-proof only, no emulator/harness code changed in
this PR.

## Merge note

This branch was cut from `origin/master` at `b73d50a070` per Addendum 4,
before the device run. By the time this PR was opened, `origin/master` had
moved 26 commits ahead (other lanes' folds); this branch merged up to
`3f1eace130` to stay current, per the session-start check. The only route
touched by that gap, `gta-sa.route`, changed by a header-comment re-head
(`state: first-run` -> `state: any`, `profileconv1011` #433) with no
functional lines touched -- the run below used the route as it stood at
`b73d50a070`, and nothing in the merge changes what that run proves.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
