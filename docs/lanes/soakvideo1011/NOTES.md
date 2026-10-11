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

## Territory discipline

Nothing outside the brief's list was touched. `burst_capture.py` and `flicker_score.py` were read only.
