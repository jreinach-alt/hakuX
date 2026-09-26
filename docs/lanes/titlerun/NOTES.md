# lane.titlerun: the title ruler

PR #307. Brief: scripted play through the queue, and a verdict per run
(the owner's 1.0 ruler, 2026-09-25).

## What exists now

| piece | file | what it does |
|---|---|---|
| pad | `docs/testing/perf/pad.sh` | evdev input only; `SERIAL` required; pad node auto-detected and cached per serial |
| routes | `docs/testing/titles/route.sh`, `titles/routes/*.route` | a small route language, parsed in full before anything is sent |
| queue | `request.sh --route <name>`, `dispatcher.sh` | the route TEXT goes into the request; the worker writes `route.txt` and passes `ROUTE_FILE` |
| soak | `docs/testing/soak_title.sh` | plays the route beside the hold; liveness retries adb (host defect 19) |
| judge | `docs/testing/title_verdict.py` | writes `verdict.json` and a contact sheet per run |
| table | `docs/testing/titles/table.py` | latest verdict per (title, device, ref); `--judge` fills in missing verdicts |
| targets | `docs/testing/titles/targets.toml` | keyed on the CSV's canonical `title_id`; ISO per device, own target fps, route |
| proof | `docs/testing/jobs/selftest.d/89-title-verdict.sh` | 29 checks: six fixtures, four verdict mutants, the liveness path and a dropped logcat stream against a fake adb (two soak mutants), `request.sh --route` |

## Pad nodes (read-only `getevent -pl`, 2026-09-25)

| device | serial | node | name |
|---|---|---|---|
| Nova | ee317437 | `/dev/input/event7` | Retroid Pocket Controller |
| Thor | bdc158a5 | `/dev/input/event9` | Odin Controller |

Both pads differ from what `pad.sh` used to assume, in three ways:

- `getevent` names code 304 `BTN_GAMEPAD`, not `BTN_A` or `BTN_SOUTH`. A
  detector that matched only the brief's two names found no pad on either
  device. It now accepts all three names.
- The sticks run from -32767 to 32767, centred on 0. The old comment said
  "centre 128 on this pad", which is no longer true of either device.
- The right stick is on `ABS_Z`/`ABS_RZ`, not `ABS_RX`/`ABS_RY`. The
  triggers are on `ABS_BRAKE`/`ABS_GAS`.

So routes name logical axes (`LX LY RX RY LT RT HATX HATY`). `pad.sh`
resolves each one against the axes the pad actually lists, and `min|max|mid`
read the cached range. A route written this way is the same file on both
handhelds.

## Decisions the verdict makes, and why

- **Frame rate is measured by the clock, not taken from G.** `hakuX-perf` is
  printed once every 60 FLIP_STALLs (`g_nv2a_stats.frame_count` counts guest
  flips; `pgraph/profile.c`). So the time between two lines is exactly how
  long those 60 guest frames took, and 60/dt is that window's frame rate.
  - `G` is an exponential average (x0.8 + x0.2 per frame). It carries the
    past into every window.
  - `gfps` is the count over the last ~250 ms, a quarter-second sample of a
    two-second window.
  - Both are reported; neither is judged. The "judge by G" mutant passes a
    20 fps run whose G still reads 33.3 ms, and the `below` fixture catches
    it.
- **The share is weighted by time.** A 60-frame window at 10 fps lasts six
  times as long as one at 60 fps, so counting windows under-weights exactly
  the slow stretches. `fps_ok_window_share` (by count) is reported beside it.
- **Windows straddling the mark are not counted.** Only pairs of lines that
  are both after `mark gameplay` count.
- **Tolerance.** A window counts as at 30 fps from 28.5 fps up (`fps_tolerance
  = 0.95`). NTSC vblank is 59.94 Hz, so a title locked to half of it runs at
  29.97, and that is the bar met.
- **Hang.** No perf line for more than 10 s after the mark means fewer than
  60 flips in 10 s. That reads a sustained 6 fps or slower as a hang. Such a
  run fails on fps anyway, so the two criteria overlap and never contradict
  each other.
- **Audio, "no dropouts", made mechanical.** Short callbacks as a share of all
  callbacks, from the `starve:` lines stamped more than 10 s after the mark.
  - The default maximum is **0.1%** (`audio_starve_max_share` in
    `targets.toml`). That is a decision; set it to 0.0 for a literal zero.
  - No `starve:` line at all means the instrument said nothing
    (`audio_measured: false`), and that run fails. A ruler that cannot hear
    must not pass a title.
- **Crash.** A crash is any of:
  - an E or F line from `hakuX-crash` (the kernel BugCheck dump);
  - `libc:F` or `DEBUG:F`;
  - a real exit, i.e. `guest exited` in run.log.

  `hakuX-crash` W lines (`NULL FAULT RETRY`) are retries. They are counted in
  `crash_warnings` and not failed.
- **Duration.** A screening run needs 600 s after the mark, a confirmation
  run 1200 s. The level is inferred from the run's length, or forced with
  `--require`.
- **Generic route.**
  - It writes `mark play`, never `mark gameplay`, because it cannot know it
    got there. The verdict scores from `mark play` provisionally, with
    `reached_gameplay: null`, and cannot pass the run until a reviewer who
    has looked at `contact.png` reruns it with `--reviewed-gameplay yes`.
    That run records `gameplay_by: review`.
  - Frames come from the route's `mark`/`shot` steps: about 10 screencaps in
    10 minutes, not the once-a-second `--frames-every` that costs frame rate.
- **Pace.** `hakuX-pace` is read by key, in the format agreed with
  lane.perfbase (`docs/lanes/perfbase/NOTES.md`, `pgraph/profile.c`). The
  late flips are the sum of `vK` for K above the title's nominal VBLANKs a
  flip (2 at 30 fps, 1 at 60). `late_per_100` is late flips per 100 flips
  over the scored windows, and `worst_stall` is the largest `max`. A
  process's first window (`f=60`) is dropped, because its first VBLANK
  delta starts from zero. Pace is reported and not judged: the owner's bar
  is frames per second.
- **Ratings.**
  - `rating_candidate` is `Playable` at `surface_scale=1` and `Playable (2x)`
    at 2. The scale is read from the app's own `hakuX: surface_scale=N`
    line, not from the request.
  - `human_review` is written empty, and nothing fills it.
  - `below_own_target` flags a title whose own target is 60 that meets 30
    but not 60.

## Snapshot deploy: the first re-exec after this folds will miss two files

Host memory "a new snapshot file misses the first re-exec" applies directly
here.

- **What happens.** `SCRIPT_DEPS` and `snapshot_scripts` now both list
  `titles/route.sh` and `perf/pad.sh`, and the copy loop makes their
  subdirectories. But the re-exec after the fold is carried out by the OLD
  worker, whose copy loop has neither the new names nor the `mkdir`.
- **What it looks like.** `soak_title.sh` refuses to guess: it writes
  `ROUTE NOT PLAYED: ... missing from this snapshot` to run.log, and the
  verdict fails the run with that reason.
- **The fix.** After the fold, run
  `mkdir -p $DISPATCH_DIR/bin/{titles,perf}` and `cp` the two files from the
  serving tree. That is exactly what the new `snapshot_scripts` would do.

## What this does not do yet

- **Set `surface_scale` 2 for a queued run.** No queue path writes the pref
  today; `apply_env_pref` handles `env_vars` only. The verdict records the
  scale the app logged, so a 2x run is judged correctly once something sets
  it. That is a `request.sh`/`dispatcher.sh` change, which belongs to
  lane.toolsmith after this PR.
- **Run the verdict inside the dispatcher.** The worker writes the result;
  `titles/table.py --judge` (or `title_verdict.py <dir>`) judges it. Putting
  the verdict into the worker would touch lines that were not lent.
- **The Galleon, DOA3 and JSRF routes**: PR 2, on the Thor.

## Device budget (the owner's scale)

- **The target.** 1.0 needs 855 of xemu's 950 Playable+ titles, about 145
  validated per minor version.
- **Cost of one screening run.** Install and start take ~1 min, boot and
  menus to the mark take ~2-3 min, then 10 min of gameplay: **about 14
  device-minutes**. So 145 screenings are **about 34 device-hours**, not 24.
  The 10-minute figure leaves out boot.
- **Confirmations.** Only titles that pass screening get one, at about 24
  minutes each. If half pass, that is 72 × 24 min ≈ **29 device-hours**.
- **Total.** About **63 device-hours per minor version**.
- **What the queue can sustain.** On 2026-09-25 the Thor was carrying two
  100-suite sweeps and the Nova had ~15 lane requests waiting. If each
  handheld gives titles about 8 hours a day, 145 screenings plus
  confirmations take **about 4 days per minor version**. That leaves
  pgraph/arms work the other 16 hours a day. Running titles around the
  clock would halve it, at the cost of every arm queued meanwhile.
- **What can cut it.**
  - A screening that fails early stops early. A crash or a guest exit
    already ends the hold, and a missing gameplay mark could too, since the
    route knows when it gave up.
  - Screening at 5 minutes, confirming at 20, would cut the screening pass
    in half.
  - Generic-route runs cost a reviewer's look at a contact sheet, seconds
    per title.

## Why attempt 1 did not finish (recorded 2026-09-26, attempt 2)

- **The implementation commit was never pushed.** `2695e09853` sat only in
  the worktree, so PR #307's head stayed at `0239b7e1cd` (notes only). CI went
  green on that head, but on a head that carried none of the work.
- **The real run never started.** `scratch/realrun.sh` waits for a moment when
  the Nova has no hold and no running request. The Nova was busy with lane
  requests the whole time. The script's log was empty when the session ended,
  and no run directory was ever made.
- **The PR was left in draft** with no waiting comment, which is what the
  handback job found.

Attempt 2 merged `origin/master`. The conflict in `dispatcher.sh`'s
`snapshot_scripts` is resolved by keeping master's write-beside-and-rename
(dispatch defect 13). The temporary file is made in the target's own
directory, because `titles/route.sh` and `perf/pad.sh` live in
subdirectories.

**Attempt 2 did not finish either.** It wrote the paragraph above and
merged, but the session ended before it pushed. `origin/lane/titlerun` was
still `0239b7e1cd` when attempt 3 started, 118 commits behind the worktree.
Attempt 3 did these things, in this order:

1. Committed and merged `origin/master` again. The merge was clean.
2. **Pushed first** (`2df80d8b31`).
3. Changed the real-run script so it could get onto the Nova at all. The old
   script waited for a moment with no hold and nothing running, and the
   worker claims the next request as soon as one ends, so that moment never
   came. The new script:
   - waits until no priority (`0-0-*`) Nova request is queued;
   - places the hold while a request is still running, which the dispatcher
     honours after that request (`dispatcher.sh`, "a hold placed mid-run
     takes effect after the current request");
   - waits up to 30 min for the Nova to drain;
   - never touches the device until then.

   It runs detached (`setsid nohup`) and logs to `scratch/realrun.log` in
   this worktree.

**Attempt 3's first session did not finish either.** Its real run started
at 04:50Z. Two things went wrong:

- Every liveness probe read as an adb failure.
- The run was killed at 04:52Z, when the session's unit stopped. `setsid`
  does not leave the unit's cgroup.

The second session of attempt 3 (2026-09-26, 05:10-06:00Z) stayed in the
foreground and polled its runs until they finished.

## Real run (2026-09-26, Nova, three tries)

Each try found a defect that only a real device shows. Each one is fixed,
with a fixture in fragment 89:

| try | what happened | fix |
|---|---|---|
| 04:50Z | Every probe read as an adb failure. The Nova's toybox `ps` pads the `NAME` header to its column width, so `grep -x NAME` never matched and the guest never counted as appeared. | strip trailing blanks (`663d0c0900`); the fake adb now pads its rows, and it goes red without the strip |
| 05:13Z | The soak held the whole 783 s through 10 real `UtilAcceptVsock` failures, so the liveness fix works. But one vsock failure made `getevent` return nothing, so **no input was played**. Another ended the logcat stream at once, so `logcat.txt` had 0 lines and the verdict could only say "never booted". | `pad.sh detect` retries three times (`c4deb73085`). The soak respawns the logcat stream with `-T 1` and writes each gap to run.log (`39e3ae4d97`), with a fixture and a mutant. |
| 05:29Z | **PASS**, as below | the pace parser was rewritten afterwards (`26f1331765`) and the run re-judged |

The verdict of the 05:29Z run is in `docs/lanes/titlerun/realrun/`, with
`verdict.json`, `contact.png`, `run.log`, `route.txt`, `request.json` and
`result.json`. The run directory is
`$HAKUX_WORK/titlerun/runs/1790400553-titlerun-crimson`.

| field | value |
|---|---|
| title | Crimson Skies (4D530021), Nova, apk `a00704d02eb0`, surface scale 1 |
| route | `crimson-skies.route`; `mark gameplay` at 22:31:52 PDT |
| gameplay | 625.4 s scored (screening) |
| fps | 309 windows; 97.2% of gameplay time at or above 30 (97.4% of windows); median 29.99, min 26.06 |
| pace | 2.19 late flips per 100; worst stall 328 ms |
| audio | short callbacks 0.029% of calls (bar 0.1%) |
| crash / hang | none / none |
| adb | 6 failures, none read as an exit; 2 route steps (`press A`) lost to vsock failures |
| verdict | **PASS, Playable candidate, screening**; `gameplay_by: route` |

The contact sheet shows the plane in flight, with the HUD, from the
`gameplay` frame on.

**For the next lane:**

- The WSL `UtilAcceptVsock` failures come in bursts of several per minute
  while the host is loaded. Any single adb call in a soak can fail. A route
  step that fails is logged (`pad.sh press A failed (rc 1)`) and the route
  carries on. It does not retry, so a route should not hang its progress on
  one press. The Crimson route mashes A 12 times for that reason.
- A detached helper started from a lane session dies with the session's
  unit, `setsid` or not. Stay in the foreground and poll.

## Audit pass 1 remediation (2026-09-26)

- **M1, capture gaps.** A logcat restart now asks the ring for everything
  from the last captured stamp (`-T <stamp>`; pass 2 below), and writes a
  `# hakuX-capture: stream ended` line into logcat.txt. `title_verdict.py`
  reads an exact duplicate line once. A restart whose replay does not reprint
  the last line is a gap. A window that spans a gap is not scored, and a hang
  gap is measured with the capture gap subtracted. The verdict reports
  `capture_gaps_s` and `capture_lost_s`. Fixture `capgap` is the audit's
  falsifier (12 s once, 5 s eight times, one replayed restart). It passes,
  with no hang and fps share 1.0. Three mutants must be caught by it.
- **M2, the mark.** route.sh retries the mark write three times, 2 s apart.
  Output on a zero exit also counts as a failure. After the third failure it
  logs `mark <x>: logcat write FAILED`, and the verdict names that as the
  reason whether or not other marks reached logcat. Fixture `lostmark`
  covers it. A fake-adb check covers the retry: fail, then noisy, then ok is
  three writes and no FAILED.
- The LOWs are not changed here. L2 (`fps_tolerance = 0.95`) is a policy
  value for the owner.

## Audit pass 2 remediation (2026-09-26)

- **M1, the restart stamp.** `-T "'$last'"` became `-T "$last"`. `adb shell`
  joins its arguments unescaped, so route.sh's `"'mark x'"` is right, but
  `adb logcat` escapes each argument itself, and the inner quotes reached
  logcat's `-T` parser, which rejected them. Every restart after the first
  drop failed. The selftest's fake adb now parses `-T` the way logcat does
  and exits on a quoted stamp. The call check asserts the unquoted form, and
  a soak mutant that restores the quotes must be caught.
- **M1, a break that never closes.** `parse_logcat` also returns the open
  break, which is a break line with no line after it. If the capture has no
  `soak end`, the run is `capture_truncated`. The verdict names
  `capture: truncated` first, ahead of duration and reached_gameplay, and
  estimates `capture_truncated_s` from `soak start` plus the hold that
  run.log reports. That estimate is added to `capture_lost_s`. Fixture
  `truncated` is the audit's falsifier: the pass run, cut at 300 s, then 31
  breaks. It now fails as "capture: truncated ... about 462 s unseen", not
  on duration, and a mutant that ignores the open break must be caught.
