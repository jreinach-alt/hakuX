# soakvideo1011: screen video during a routed soak, from the dispatcher; route crops now travel with the request (#433, 0.5)
State: ready

Lane: soakvideo1011            Issue: none (#433 umbrella) [board 3f54e5d3d7]
Base: master @ 6d8947bb47
Files: docs/testing/dispatcher.sh, docs/testing/request.sh, docs/testing/jobs/selftest.d/61-soakvideo1011.sh, docs/testing/jobs/selftest.d/62-routerefs-soakvideo1011.sh, docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh (necessary exception, see Addendum 3), docs/testing/jobs/selftest.d/99-hitch-report.sh, docs/testing/hitch_report.py, AGENTS.md (one paragraph), docs/lanes/soakvideo1011/NOTES.md, docs/lanes/soakvideo1011/PR.md, docs/testing/predictions/soakvideo1011-* (Step 2, not yet registered)
Prediction: none yet (Step 2, device proof, queued once this is live on master)
Needs device: yes (Step 2, Nova only)    Needs NDK: no

## What this is

Owner reported GTA San Andreas surface dropouts (hard-edged sky polygons, no
CJ shadow) visible while playing, caught in only ~2 of 72 soak stills. This
lane adds a screen-video capture to the dispatcher's soak path, the way
`--frames-every` adds stills, for the class of defect a still only catches by
luck.

## Step 1 (done)

- `docs/testing/dispatcher.sh`: `start_soak_video`/`stop_soak_video`, mirroring
  `start_frame_capture`/`stop_frame_capture`. Watches `run.log` for the route's
  `mark` line, waits `--video-after`, records `HAKUX_SOAK_VIDEO_SEG`-second
  segments via `screenrecord`, pulls each in the background while the next
  records, deletes the device file only once the pull's size matches. Stop is
  unconditional: `adb shell pkill -2 screenrecord` (a signal to the remote
  process, not the local adb client -- that needs a pty), pull the last
  segment, clear stray `hakux_vid_*.mp4`. `result.json` gets a `video` dict
  whether video ran or not (cost-comparability, same reason as `frames_every`).
  `duration_s`/`samples` read from the mp4 via a stdlib ISO-BMFF box reader
  (`mvhd`, `stsz`) -- no ffmpeg/ffprobe on this host, nothing installed.
- `docs/testing/request.sh`: `--video-seconds N` / `--video-after S`, soak-only,
  refused at queue time for a non-soak request, non-numeric input, N over
  `HAKUX_SOAK_VIDEO_CAP` (default 300), or `after+seconds` exceeding the soak's
  own `--seconds` even in the best case (mark at t=0).
- `AGENTS.md`: one paragraph documenting the flags, where files land, and that
  the mp4s are for a person to watch (no lane here decodes video).
- `docs/testing/jobs/selftest.d/61-soakvideo1011.sh`: `start_soak_video`/
  `stop_soak_video` against a fake adb dispatched on argv position -- segment
  chaining + pull-then-delete order, SIGINT early stop, no-mark-in-run.log vs.
  mark-seen-but-clock-unreadable, video off, and a hand-built-mp4 test of
  `_mp4_info()`'s own box reading. Plus `request.sh`'s six queue-time
  refusal/acceptance legs. 20/20 passing in isolation.

## Addendum 1 (lane.local 2026-10-11 09:55 PDT, board 3f54e5d3d7) -- done

`hitch_report.py`'s `window_frames()` took a still's time from its *name*
(`FRAME_NAME` regex), but the dispatcher's own `start_frame_capture` names
stills `frames/f00001.png`, ... -- no time in the name at all -- so a
dispatcher still was never once counted as post-mark. Every `--frames-every`
soak whose route takes no `route-frames/` shots after `mark` therefore failed
screening as "window unmeasured", regardless of how the run actually went.

**Fix**: `frames/index.tsv`, a `name<TAB>HH:MM:SS` sidecar read from the
DEVICE clock (`adb shell date`) -- the same clock the `hakuX-route` mark line
is on; the host clock on this machine steps backward periodically and cannot
be trusted to agree with it. `_frame_index()`/`_frame_time()` read it first,
falling back to the `FRAME_NAME` regex unchanged for `route-frames/`'s
existing convention. `mark_wall` and each video segment's `start_wall` move to
the same device clock via a new `_device_epoch()` helper.

**Proof**, against `1-1791733228-lane.local-3377455` (GTA San Andreas, 29
`frames/` stills, mark 09:26:13.399, fps_ok 0.948), run on a scratch copy with
a reconstructed `index.tsv` (stills' own mtimes, the only clock reading a
historical run left):

| | before (committed `hitch_report.py`) | after (this branch) |
|---|---|---|
| `static_window` | `measured: False`, `n: 0`, `source: None` | `measured: True`, `n: 21`, `source: "frames"`, `frozen_frac: 0.0099` |
| `title_verdict.py --require screening` | FAIL `window unmeasured: 0 post-mark route-frame(s) and 0 post-mark frames/ sample(s), need 3 of one` | PASS `Playable` |

What this can flip, stated plainly: only `--frames-every` soaks whose scored
window was previously *unmeasured* for lack of post-mark samples -- not every
screening failure, and not a run that genuinely never took a post-mark still.

**Selftest** (`99-hitch-report.sh`): fixture built from 3377455's own real
names/mark/mtimes, proving `window_frames()` measures with `index.tsv`
present, is unmeasured without it (the pre-fix shape), and a single-anchor
mutant reverting just the index lookup reproduces the same unmeasured result
on the identical fixture. 15/15 passing in isolation.

`route.sh`'s OWN `route-frames/` filenames and `run.log` lines still use the
HOST clock -- a pre-existing, separate mismatch against the mark (device
clock) that Addendum 1 did not name in scope. Flagged in NOTES.md for
whichever lane next touches `route.sh`; not fixed here.

## Addendum 3 (relayed by lane.local, cross-session, 2026-10-11) -- done: route crops travel with the request

**The bug.** `request.sh`'s own "AND AS THE RUN WILL SEE IT" check copies the
route to a scratch `route.txt` and runs `route.sh --check` against that copy,
since the dispatched run plays a copy of the route text, not the file at
`$ROUTE_PATH` -- but it never populated the copy's `refs/<stem>/`, so any
route naming a `waitfor`/`press-until` crop failed that check and was refused
at queue time. Every such route, `castlevania-cod.first-run` included, on
master today -- confirmed directly by running `request.sh --route
castlevania-cod.first-run` before any fix: refused with "no reference crop".
This blocked `lane.nfsroute1011`.

**The fix, three pieces, no device write added.**
- `request.sh`: after `route.sh --check "$ROUTE_PATH"` passes, reads the
  route's `waitfor <name>`/`press-until <btn> <name>` lines the way route.sh's
  own grammar does, base64-encodes each crop from `refs/<stem>/<name>.png`,
  and writes `{"refs": {...}}` (or a refusal) to a **temp file**
  (`ROUTE_REFS_FILE`, removed by an `EXIT` trap) -- never through a shell
  variable or another process's argv/env, since an aggregate of base64'd crops
  could approach Linux's ~128 KiB `MAX_ARG_STRLEN`. A cap
  (`ROUTE_REFS_CAP=2000000` bytes total) refuses rather than silently
  truncating an unreasonably large set. The check-copy step decodes
  `ROUTE_REFS_FILE`'s entries into the copy's `refs/route.txt/` *before*
  calling `route.sh --check` on it, so the check passes exactly when the
  dispatched run would; the final request JSON carries the same entries as
  `"route_refs"`.
- `dispatcher.sh`: new `write_route_refs <rdir> <req>` function, called right
  after the existing `route.txt` write in the soak-execution flow. Validates
  every name against `^[A-Za-z0-9._-]+\.png$` *before writing anything*,
  refusing the whole call (stdout + exit 1) on the first bad name so no `/` or
  `..` can escape `<rdir>/refs/route.txt/`; a refusal writes `$rdir/ERROR`,
  logs, calls `restore_hdd_pref`, and returns, the same shape as the existing
  `titles_disk_prepare` trc=3 refusal nearby. Written as a function so a
  selftest can call it directly without sourcing the whole worker loop.
- The refusal message reworded: it used to say a crop "must sit next to the
  route" (true before, false after); now a missing/unreadable crop next to
  `$ROUTE_PATH` itself is the only way to still see this refusal.

**Request shape.** A request naming a route with crops now carries:
```
{ ..., "route": "<name>", "route_refs": {"<crop-name>.png": "<base64>", ...}, ... }
```
absent or `{}` for a route with no `waitfor`/`press-until` lines.

**Necessary territory exception:** `docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh`
(lane.snapdrive's file, not on this lane's `*-soakvideo1011.sh` glob) had a
"crops" leg asserting the OLD, buggy behavior (refused) as expected. Left
unedited it goes from `ok` to `FAIL` on every run from here on, for a reason
that is this fix, not lane.snapdrive's work -- confirmed by running the
unmodified fragment against the fixed scripts first and watching it fail as
predicted. Fixed the one case block + comment to assert "queued"; verified
18/18 in isolation. Per the brief's own escape clause, documented in NOTES.md.

**Selftest result:** new `docs/testing/jobs/selftest.d/62-routerefs-soakvideo1011.sh`
builds a real, throwaway route+crop under `titles/routes/` (`resolve-route`
has no `--routes-dir` override, so a route under a sandboxed `$T` would never
resolve by name) and proves: the queued request carries the crop's exact
bytes (sha256 match); `write_route_refs` writes them byte-identical at
`refs/route.txt/<name>.png`; `route.sh --check` on the played `route.txt`
then passes; an escaping name (`../escape.png`) is refused before anything is
written; and a mutant with the check-copy staging block removed reproduces
today's exact refusal ("no reference crop"). 10/10 passing in isolation.

Full details, including the mutant-placement bug hit and fixed along the way
(a mutant copy of `request.sh` has to live inside `docs/testing/` itself, not
a scratch dir, since it resolves its own repo root/`titles/route.sh` relative
to its own path), are in `docs/lanes/soakvideo1011/NOTES.md`.

## Verification so far

- `bash -n` clean on `dispatcher.sh`, `request.sh`, and every touched
  `selftest.d/*.sh` fragment; `python3 -m py_compile hitch_report.py` clean.
- Each new/changed selftest fragment passes in isolation
  (`SELFTEST_ONLY=<fragment>`): `61-soakvideo1011.sh` 20/20,
  `62-routerefs-soakvideo1011.sh` 10/10, `97-dispatch-snapshot-drive.sh`
  18/18 (post-fix), `99-hitch-report.sh` 15/15.
- Full `jobs/selftest.sh`, all 4 shards, run in the foreground after the
  Addendum 3 commit landed:

  | shard | fragments | checks passed | failed |
  |---|---|---|---|
  | 0/4 | 13 | 284 | 0 |
  | 1/4 | 45 | 1104 | 0 |
  | 2/4 | 39 | 1068 | 0 |
  | 3/4 | 39 | 920 | 0 |

  **136/136 fragments, 3376/3376 checks passed, 0 failed.**

No device proof for Addendum 3 itself: `lane.nfsroute1011`'s first gated
route run after this folds is the proof that a crop-naming route now queues
and plays.

## Still open

- Step 2: device proof on the Nova (GTA San Andreas, `--route gta-sa`, 600s,
  `--frames-every 5`, `--video-seconds 120`, `--video-after 30`), queued once
  this is live on master -- gfps and both mp4 paths will be added here.
  (No existing gfps figure exists for GTA San Andreas from `fastpaths1010`'s
  two toggle-screen runs on this route, `1-1791733219-lane.local-3377194`/
  `...-3377243` -- that screen recorded only the surface-dropout frames, not
  a gfps reading -- so this run's gfps will be the first for this route, not
  a comparison against a prior number.)

Release note (none): test-harness/dispatcher infrastructure only, not
hw/target/accel/android/tcg/ui/audio -- this adds an opt-in capture path and
fixes an existing scorer and queueing check to use data/crops they already
have; nothing changes for a soak that does not ask for video or name a route
with no crops.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
