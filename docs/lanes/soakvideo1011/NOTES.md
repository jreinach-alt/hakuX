# lane.soakvideo1011

## Step 0 (read)

Read `start_frame_capture`/`stop_frame_capture` (dispatcher.sh ~L289-326) and the soak branch that calls
them (~L1461-1603, `frames_every` from the request, the `frames=` dict in result.json). Read
`request.sh`'s `--frames-every` (option at L171, default at L111, validation ~L910-950, request-JSON
field ~L1258) and `burst_capture.py`'s `rec()` (screenrecord to `/sdcard/Download/`, pull, delete).

Route marks: `titles/route.sh`'s `log()` writes `ROUTE HH:MM:SS.mmm <msg>` to stdout, which
`soak_title.sh` (and the dispatcher's `>>"$rdir/run.log"`) capture, and `mark <label>` writes
`mark <label>` through it (`drive_step`/the route grammar) -- so the dispatcher can watch `run.log` for a
line containing ` mark ` without touching logcat.

## Design decisions

- **Stopping `screenrecord` early uses `adb shell pkill -2 screenrecord`, not a signal sent to the local
  `adb` process.** The brief's rule is explicit: no device write except the temporary `hakux_vid_*.mp4`
  files, which rules out a remote PID marker file. `adb shell screenrecord ...` run non-interactively (no
  pty) does not reliably forward a locally-delivered SIGINT to the remote process -- that forwarding needs
  an allocated pty (interactive `adb shell`, Ctrl-C) or a second command that signals the remote process
  directly. `pkill -2 screenrecord` is the second: a plain command, no new device file, and it is the
  documented way to stop `screenrecord` early so it finalizes its `moov` atom rather than leaving a
  truncated container. Verified locally that GNU `timeout` forwards an externally-delivered SIGINT to its
  child (so the segment's own `timeout $((this+30))` wrapper is not in the way); the remote stop is a
  separate, independent `adb shell` call issued by `stop_soak_video`, not a signal to that wrapper.
- **A `.stop` marker file under `$rdir/video/`** (host-side, not on the device) lets the background loop's
  three wait points (mark-wait, after-wait, between segments) notice an external stop within ~1s without
  needing a signal of their own; `stop_soak_video` sets it, sends the remote `pkill`, then `wait`s on the
  loop's PID so by the time it returns `video/meta.json` is already written.
- **`duration_s`/`samples` are read from the mp4 in the existing soak result.json builder (dispatcher.sh's
  python heredoc after `soak_title.sh` returns), not in the bash capture loop.** The bash loop writes
  `video/meta.json` with `file`/`start_wall`/`bytes` per segment (and `skipped`/`mark_wall` when relevant);
  the python block that already builds `frames={}` reads it back, parses each segment's `moov`/`mvhd`
  (timescale, duration) and `trak/mdia/minf/stbl/stsz` (sample_count) with a small stdlib box walker, and
  writes the merged `video` dict into `result.json`. No ffmpeg/ffprobe exists on this host and none is
  installed, per the brief.

## Addendum 1 (lane.local 2026-10-11 09:55 PDT, board 3f54e5d3d7): `hitch_report.py`'s window never read the
dispatcher's own stills

**The defect, confirmed from first principles.** `window_frames()` takes its post-mark samples from
`route-frames/` or `frames/` via `_frame_time()`, which reads a frame's time from its *name* with
`FRAME_NAME = ^(\d\d)(\d\d)(\d\d)-`. The dispatcher's own `start_frame_capture` names its stills
`frames/f00001.png`, `f00002.png`, ... -- sequential, no time in the name at all -- so `FRAME_NAME` can never
match one, and `window_frames()` always read 0 post-mark `frames/` samples regardless of when they were
actually taken. Every `--frames-every` soak whose route takes no `route-frames/` shots after `mark` therefore
failed screening as `window unmeasured: 0 post-mark route-frame(s) and 0 post-mark frames/ sample(s), need 3
of one`, no matter how good the run actually was. Reproduced directly against the real result named in the
addendum, `dispatch/results/1-1791733228-lane.local-3377455` (GTA San Andreas, 29 `frames/` stills, mark
`09:26:13.399`, fps_ok 0.948): its committed `verdict.json` reads exactly this failure, under `pass_kind:
screening`.

**Which clock the new timestamps use, and why.** `titles/route.sh`'s `flush_disk()` has an explicit comment
that "the host and device clocks differ"; its `mark_logcat()` writes the mark via `adb shell log -t
hakuX-route`, timestamped by the DEVICE, which is what `hitch_report.main` reads for `mark_t`. The host clock
on this machine has its own problem besides merely differing: since 2026-10-10 04:22 PDT it steps backward
roughly every 31 s (see the memory `host-clock-steps-back.md`), so a host timestamp on a still taken near a
step is not even monotonic with its neighbors. Both new timestamp sources in this lane -- `frames/index.tsv`'s
per-still reading and `start_soak_video`'s per-segment `start_wall` -- read `adb shell date` (the device
clock) instead of the host's `date`, so a still, a video segment, and the `hakuX-route` mark line all land on
the one clock the verdict already trusts. `route.sh`'s OWN `route-frames/` filenames
(`$(date '+%H%M%S')-$name.png`) and its `run.log` lines (`ROUTE $(date '+%H:%M:%S.%3N') ...`) still use the
HOST clock -- a pre-existing mismatch between the mark (device) and `route-frames/` names (host) that this
lane did not touch, since Addendum 1 named only `frames/` in scope. It is a latent, separate correctness gap:
flagged here for whichever lane next touches `route.sh`, not fixed by this one.

**The fix.** `frames/index.tsv`, a sidecar of `name<TAB>HH:MM:SS` lines (one `adb shell date +%H:%M:%S` call
per still, device clock, 1-second resolution -- matching the one pre-existing precedent for reading the
device's clock in this codebase, `flush_disk()`'s `adb shell date +%s`; there is no millisecond precedent
anywhere to match instead). `hitch_report._frame_index()` reads it into `{basename: "HH:MM:SS"}`;
`_frame_time()` now tries the index first and only falls back to the `FRAME_NAME` regex when a name is not in
it, so `route-frames/`'s existing `HHMMSS-name.png` convention still works unchanged. `_post_mark()` and
`window_frames()` needed no changes at all -- the fix is fully inside `_frame_time`/`_frame_index`. The
`fNNNNN.png` names themselves are untouched, since readers and briefs cite them.

For the `video` dict, `mark_wall` and each segment's `start_wall` switched from host `date +%s.%3N` to a new
`_device_epoch()` helper (`adb shell date +%s`, device clock, plain Unix-epoch integer -- `float()` parses an
integer string fine, so every downstream consumer of these fields needed no change). `_device_epoch()` retries
three times before giving up, per the house rule that a single adb flake must not read as "the mark never
came" (`device-run-flakes.md`): `start_soak_video` now tracks `mark_seen` separately from `mark_wall` so a
seen-mark-but-unreadable-clock failure is never reported with the same reason string as a mark that truly
never came.

**Proof (copy of 3377455, scratchpad, never the original).** `docs/lanes/soakvideo1011/scratch/3377455` is a
`cp -r` of the real result dir; `frames/index.tsv` there is *reconstructed* from the 29 stills' own file
mtimes (the only clock reading available for a run that predates this fix -- there is no real device-clock
sidecar for a historical run). Converted to local time they match the addendum's own account exactly:
`f00008.png` 09:26:01 (pre-mark, mark is 09:26:13.399), `f00009.png` 09:26:32 through `f00029.png` 09:36:47 --
21 stills strictly after the mark and before `soak end` (09:36:55.822).

| | before (pre-fix `hitch_report.py`, `git show HEAD:...`) | after (this branch) |
|---|---|---|
| `static_window` | `measured: False`, `n: 0`, `source: None` | `measured: True`, `n: 21`, `source: "frames"`, `frozen_frac: 0.0099` |
| `title_verdict.py --require screening` first failure | `window unmeasured: 0 post-mark route-frame(s) and 0 post-mark frames/ sample(s), need 3 of one (a scored window the verdict cannot read is not Playable)` | none -- `VERDICT ... PASS Playable` |

Reproduced by running `title_verdict.py` twice against the one scratch copy: once via a `before_lib/` copy of
`title_verdict.py`/`thermal_state.py`/the pre-fix `hitch_report.py` (so `import hitch_report` resolves to the
old file), once via this branch's own `docs/testing/title_verdict.py` after dropping the reconstructed
`index.tsv` into the copy's `frames/`. Exact commands and output are in PR.md.

**What this can flip, stated plainly.** Only `--frames-every` soaks whose scored window was previously
*unmeasured* for lack of post-mark samples -- not every screening failure, and not a run that genuinely never
took a post-mark still (still 0 samples, still unmeasured, with or without this fix). The addendum names 6
such verdicts on 10-10/10-11; 3377455 is one of them and is shown above to flip from FAIL to PASS.

**Selftest.** `docs/testing/jobs/selftest.d/99-hitch-report.sh` gained a new section, built from 3377455's own
real names/mark/mtimes (not hand-written `HHMMSS-` names, per the addendum): `window_frames()` measures 4
post-mark `frames/` stills with `index.tsv` present, is unmeasured with no `index.tsv` (the pre-fix shape),
and a mutant that disables just the index lookup in `_frame_time` (reverting the fix without touching the
real file) reproduces the same unmeasured result on the identical fixture.

## Territory discipline

Nothing outside the brief's list was touched. `burst_capture.py` and `flicker_score.py` were read only.
