# lane.soakvideo1011

## Resume (attempt 2, 2026-10-11 ~11:xx PDT)

Per Addendum 2: attempt 1 ended at 10:52 PDT, before Step 2, because its selftest run was launched with
`run_in_background` -- a headless session ends the instant its turn ends, which kills every background
process with it, so the selftest never finished and no result was ever read back. (Same root cause as the
`hub-lanes.md` memory on background jobs dying with the session, and the brief's own "never end a turn while
a job of yours is still running" rule, which that run violated.) `git status`/`git log` here show the three
Step 1 + Addendum 1 commits are already in place and `origin/master` is already an ancestor of HEAD (the
fastpaths1010 fold that attempt 1 needed is already merged in), so Step 0's merge is not needed again. No PR.md
exists yet; PR #928 (draft, local forge) is already open from a prior push. Continuing from Addendum 2's
numbered steps: foreground `bash -n` + full selftest, then Step 2.

**`bash -n`**: `dispatcher.sh`, `request.sh` clean; `python3 -m py_compile hitch_report.py` clean.

**Full selftest, foreground, sharded** (`SELFTEST_SHARD=k/4`, the same split CI uses,
`--check-shards 4` confirms the 135 fragments are covered exactly once). Each shard run as its own
foreground Bash call; the harness's own per-call timeout (~9 min) auto-moved the long-running shell to a
tracked background task partway through every shard (this host is far slower than the CI estimate -- shard
0 alone took 23m55s real, not the ~5-9 min implied by "18-25 min across 4 CI shards, host 2x slower"), and
each time I kept polling the *script's own PID* (`while kill -0 <pid>; do sleep 5; done`) in the same turn,
never ending the turn while it ran, per the brief and the "headless session" rule. One real hazard hit
along the way: an earlier `nohup ... &` attempt for shard 1 was reported to me as blocked on a permission
prompt, but it had in fact already started running detached and untracked (confirmed via `/proc/<pid>/cmdline`
and `/proc/<pid>/environ`) -- a duplicate, unmonitored shard-1 run alongside the one the harness was
tracking. Killed the orphan by explicit PID (never `pkill -f`/`pgrep -f`, which would match this very
session's own command line -- `pgrep -af` on this host matched the `claude -p ...` process running this
session, confirming the blind spot). Separately, the first (tracked) shard-1 run's piped
`... | tail -100` reported `[exited with code 0]` but the final `selftest: N passed, M failed` summary line
was simply absent from the captured output -- `$?` after a pipe without `pipefail` is `tail`'s exit status,
not `selftest.sh`'s, so that "0" proved nothing (cf. `exit-code-is-a-coarse-discriminator`). Re-ran shard 1
writing straight to a log file with `set -o pipefail` and an explicit trailing `RC=$?` instead of piping
through `tail`, and only trusted the `RC=0` plus the literal summary line after that.

| shard | fragments | checks passed | failed | result |
|---|---|---|---|---|
| 0/4 | 13 | 284 | 0 | RC=0 (via `time ... \| tail -80`, summary line present) |
| 1/4 | 43 | 1023 | 0 | RC=0 (via `set -o pipefail` + logfile; first attempt's tail-piped run discarded, no trustworthy summary) |
| 2/4 | 40 | 1097 | 0 | RC=0 (logfile + pipefail) |
| 3/4 | 39 | 962 | 0 | RC=0 (logfile + pipefail) |

135/135 fragments, 3366/3366 checks passed, 0 failed. Addendum 2's selftest step is done.

## Addendum 3 (relayed by lane.local, cross-session message, 2026-10-11 ~12:2x PDT): route crops travel
with the request

Arrived mid-session, while shard 2/4 of the Addendum-2 selftest run was still executing. Read in full from
`/home/justin/hakux-work/briefs/soakvideo1011.md`. Ordered work: finish Addendum 2's selftest (done above),
then this, then re-run `bash -n` + the whole selftest again, then `State: ready`. Implementation notes below
as they're written.

**The bug, confirmed from the code before touching anything.** `request.sh`'s own "AND AS THE RUN WILL SEE
IT" check (copies `$ROUTE_PATH` to a scratch `$RCHK/route.txt` and runs `route.sh --check` against it, since
the dispatched run plays a *copy* of the route text, not the file at `$ROUTE_PATH`) never populated
`$RCHK/refs/<stem>/`, so any route naming a `waitfor`/`press-until` crop failed that check and was refused at
queue time -- every such route, `castlevania-cod.first-run` included, confirmed directly by running `request.sh
--route castlevania-cod.first-run` before any fix: refused with "no reference crop".

**The fix, three pieces, no device write added.**
- `request.sh` (around the existing route block, ~L1196-1314): after its own `route.sh --check "$ROUTE_PATH"`
  passes (proving every named crop exists on disk), a python heredoc re-reads the route's `waitfor
  <name>`/`press-until <btn> <name>` lines the same way route.sh's grammar does (first word dispatch, `#` to
  end of line stripped first), base64-encodes each crop from `refs/<stem>/<name>.png`, and writes `{"refs":
  {...}}` or `{"refuse": "..."}` to a **temp file** (`ROUTE_REFS_FILE`, `mktemp`, removed by an `EXIT` trap) --
  never through a shell variable or another process's argv/env, since an aggregate of base64'd crops could
  approach Linux's ~128 KiB single `MAX_ARG_STRLEN` string, where the route file's own existence check does
  not have to. A cap (`ROUTE_REFS_CAP=2000000` bytes total) refuses a route whose crops are unreasonably large
  rather than silently truncating. The existing check-copy step then decodes `ROUTE_REFS_FILE`'s entries into
  `$RCHK/refs/route.txt/` *before* calling `route.sh --check` on the copy, so the check passes exactly when
  the dispatched run would see the same crops -- and the final request-JSON heredoc adds a `"route_refs"`
  field read from the same temp file.
- `dispatcher.sh`: a new `write_route_refs <rdir> <req>` function (right after `stop_soak_video`, before
  `env_pref_marker`), called once right after the existing `route.txt` write in the soak-execution flow.
  Validates every name against `^[A-Za-z0-9._-]+\.png$` *before writing anything* (refusing the whole call,
  stdout + exit 1, on the first bad name) so no `/` or `..` can escape `<rdir>/refs/route.txt/`; a refusal
  writes `$rdir/ERROR`, logs, calls `restore_hdd_pref`, and returns -- the same shape as the existing
  `titles_disk_prepare` trc=3 refusal a few lines above it in the same function. Written as a function (not
  inlined) specifically so a selftest could call it directly without sourcing the whole worker loop.
- Refusal message at the bottom of request.sh's check reworded: it used to say a crop "must sit next to the
  route" (true before this fix, false after); now it says a missing/unreadable crop next to `$ROUTE_PATH`
  itself is the only way to still see this refusal, since the crop travels from there.

**Necessary territory exception: `docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh`.** Not on this
lane's `*-soakvideo1011.sh` glob, but its "crops" leg (~L164-173, lane.snapdrive) asserted the OLD, buggy
behavior as the *expected* one: `rq_sd` against a route with a `waitfor` crop, no snapshot bin/ and no serving
tree, asserting the output contains `"would not run in the dispatched soak"*"no reference crop"` -- i.e. it
pinned down the exact bug Addendum 3 removes. After this fix the crop travels, the check passes, and the
request queues; left unedited, this leg would go from `ok` to `FAIL` on every run from here on, for a reason
that has nothing to do with lane.snapdrive's own work. Confirmed required (not optional) by running the
unmodified fragment against the fixed scripts first: it failed exactly as predicted. Fixed the one case block
and its stale comment to assert "queued" (matching Addendum 3) and point at `62-routerefs-soakvideo1011.sh`
for the refusal-reproducing mutant; verified the corrected fragment passes in isolation
(`SELFTEST_ONLY=97-dispatch-snapshot-drive.sh`, 18/18). Per the brief's "if you need another file, stop and
write the file and the reason in NOTES.md" -- this is that file and that reason.

**Selftest: `docs/testing/jobs/selftest.d/62-routerefs-soakvideo1011.sh`.** Builds a real, throwaway route
(`zzz-routerefs-selftest.route`, `# state: first-run`, one `waitfor probe-crop 5 10,10,20,20 10` line) and its
crop (256 random bytes -- route.sh/write_route_refs only move and compare bytes, never decode an image)
directly under `titles/routes/` + `titles/routes/refs/`, since `titlestate.py resolve-route` (what
`request.sh --route` resolves names through) has no `--routes-dir` override: a route under `$T` would never
resolve by name at all. Removed at the very end (and defensively at the very start, in case a previous
aborted run left it) regardless of which checks below it failed, since `selftest.sh` has no `set -e` and
`bad()` only increments a counter. Legs: (1) `route.sh --check` passes the route as committed; (2) the queued
request's `route_refs["probe-crop.png"]` base64-decodes to the crop's exact sha256; (3) `write_route_refs`,
called directly by sourcing `dispatcher.sh` the way `97-dispatch-snapshot-drive.sh`'s `sd_env` and this lane's
own `61-soakvideo1011.sh`'s `sv_env` do, writes the crop byte-identical (`cmp -s`) at
`refs/route.txt/probe-crop.png`; (4) `route.sh --check` on the played `route.txt` (crop materialized) passes;
(5) `write_route_refs` refuses a `../escape.png` name, exit 1, before writing anything under the output dir at
all; (6) the mutant -- a python-sliced copy of `request.sh` with the `mkdir -p "$RCHK/refs/route.txt"` +
materializing-python-block removed, run through the same `rr_rq` helper, reproduces today's exact refusal
("no reference crop"). The mutant copy has to live inside `$TESTING` itself (not `$T`): `request.sh` resolves
its own repo root (`--ref HEAD`), `titles/route.sh`, and drive profiles relative to its own `$(dirname "$0")`,
so a copy run from anywhere else fails first on `git rev-parse` finding no repo at `../..` -- the wrong
failure, for the wrong reason, before ever reaching the route_refs logic the mutant is meant to test (hit this
exact false negative on the first attempt, diagnosed via the "cannot resolve --ref HEAD" message, fixed by
relocating the mutant copy). All 10 checks pass in isolation (`SELFTEST_ONLY=62-routerefs-soakvideo1011.sh`).

**Commit**: `soakvideo1011: route crops travel with the request (Addendum 3, #433)`, covering `request.sh`,
`dispatcher.sh`, the new `62-routerefs-soakvideo1011.sh`, and the `97-dispatch-snapshot-drive.sh` exception
above, in one commit (they are one change: the fix and the fragments that prove it and keep proving it).

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

Nothing outside the brief's list was touched, with one documented exception: Addendum 3 required editing
`docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh` (lane.snapdrive's file, not on this lane's
`*-soakvideo1011.sh` glob) because that fragment pinned down the exact bug Addendum 3 removes as its expected
behavior -- see the Addendum 3 section above for the full reasoning and the before/after proof. `burst_capture.py`
and `flicker_score.py` were read only.
