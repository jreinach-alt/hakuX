# lane.displayguard (#494)

## What changed

| where | what |
|---|---|
| `docs/testing/devices.sh` `display_clear <serial>` | after the wake: `dumpsys power` must read `mWakefulness=Awake` (three reads, 1 s apart, when it reads something else), and `dumpsys window windows` must have no window block on `mDisplayId=0`, `fillxfill`, `mHasSurface=true`, `mViewVisibility=0x0`, of type BOOT_PROGRESS / SYSTEM_OVERLAY / APPLICATION_OVERLAY / SYSTEM_ALERT, whose package is not hakuX or systemui. The rule is `harness_health.py`'s `covered:` check, ported to awk. Prints `display-clear:` (0), `display-covered:` (1) or `display-unknown:` (2). |
| `docs/testing/soak_title.sh` | calls it after `KEYCODE_WAKEUP`, before audio is armed, the perf mode is set, logcat is started or `am start` runs. On covered: the line goes to run.log, the EXIT trap is cleared (no `KEYCODE_SLEEP` under the owner's app), the lease is removed, exit 4. On unknown: logged, and the run goes on. After the hold: when every route frame is under 12,288 B, it logs `display-black: all N route frames under 12288 B (largest X B)`. |
| `docs/testing/title_verdict.py` | new `void` field. It is set from a `display-covered:` or `display-black:` line in run.log, or from the route frames themselves when all are under 12,288 B, so a run.log from before this change is judged the same way. A void run has no fps windows (every fps field is null), `void: ...` is its first failure, and it does not pass. |
| `docs/testing/jobs/selftest.d/99-display-covered.sh` | the fixtures and legs listed below |

`title_verdict.py` is not on the brief's Files list. It had to be touched: the
dispatcher ignores the soak's exit code (`dispatcher.sh` ~767 runs the soak,
then always writes `result.json` and `DONE`), so the verdict is the only
reader that can void the run. No open PR claimed the file.

## What happens to a refused request

`dispatcher.sh` runs `soak_title.sh`, ignores its exit code, writes `result.json`
(0 log lines, 0 frames) and `DONE`, and moves the request into the result dir.
The request is consumed and not requeued. `title_verdict.py` then reads
`display-covered:` in run.log and writes `void: display-covered: ...` as the
first failure, with `pass: false` and every fps field null. Before this change
the same run would have failed as `booted: ...`, which is wrong about the
cause. The black runs of 09-27 would have been judged on their flips.

## Measured

- Selftest fragment, standalone: 10 of 10 pass under gawk (the host's awk),
  mawk and busybox awk.
- Mutants, each run against a scratch copy of `docs/testing`:
  - the overlay-type condition removed (in the fragment): the clear leg goes
    red, because the owner's Lime3DS `BASE_APPLICATION` window reads as a cover;
  - the soak's refusal removed: the covered leg goes red (rc 0, `am start` reached);
  - the verdict's run.log void removed: 2 legs go red;
  - the frames-on-disk void removed: 1 leg goes red;
  - the fps windows kept on a void run: 2 legs go red (`fps_ok_share` 1.0 on a black run).
- Neighbouring fragments that drive `soak_title.sh` / `title_verdict.py`:
  84-perf-regimen 21/21, 89-title-verdict 36/36, 99-iso-roots 10/10, the same
  as on master. The existing fake adbs answer `dumpsys` with nothing, which
  reads as `display-unknown`, and the run goes on. My first draft put the
  refusal flag inside `release()` and split the `perf_leave` +
  `KEYCODE_SLEEP` pair that 84's mutant anchors on. The refusal now clears the
  EXIT trap itself instead, and `release()` is unchanged.
- The same rule on the live handhelds: `host-tools/.health-state.json`
  (2026-09-27, ~19:05 UTC) holds `covered:thor` and no `covered:nova`. So the
  Python original flags the real 09-27 block and does not flag a clean Nova.

## Not done: the real-device pilot

The brief asks for a 60 s soak on a clean handheld. It could not run from this
branch:

- The dispatcher runs `soak_title.sh` and `devices.sh` from `$DISPATCH_DIR/bin`,
  a snapshot of the MASTER checkout (`snapshot_scripts`). A queued request runs
  master's soak, not this branch's. The only other way to run the soak
  would be to drive the device directly, which a lane may not do.
- Both handhelds were held all session: the Nova by the owner (charging) and
  the Thor by hostops-display (this very overlay).

So the pilot happens on the first title soak after the fold. Every soak's run.log
now carries one `display-*` line near the top. The first soak on a handheld
with a clean display must show `display-clear: <serial> Awake, no foreign
overlay on display 0 (N windows read)` and then run as before. If it shows
`display-unknown`, the awk port does not parse the real text (the run still
goes on). If it shows `display-covered` on a device whose display-0 screencap
is not black, the port disagrees with harness_health and is refusing good runs.
Revert the call in `soak_title.sh` first; the verdict change can stay.

## Follow-ups (not this lane's files)

- **pgraph path**: `run_disc.sh` (lane.toolsmith's) has no display check.
  A covered display there would presumably give black captures, scored as
  wrong pixels rather than void. Calling `display_clear "$SERIAL"` there
  before `am start` would close that gap. That file is lane.toolsmith's, so
  this lane did not edit it.
- **Unknown proceeds.** When adb cannot answer, the soak runs, and only a soak
  with a route has the black-frame backstop. A soak with no route and an
  unreadable window list on a covered display is still unguarded.
- Other fps readers that parse `gfps` straight from logcat (`perf/summarise.py`,
  `vblank_*`, `pace_check.py`) do not read `void`. Only `title_verdict.py`
  (and through it `status_html.py` / `titles/table.py`) does.

## Do not repeat

- Do not put anything between `perf_leave` and the `KEYCODE_SLEEP` line in
  `release()`: 84-perf-regimen's mutant anchors on that pair.
- The black threshold is on file size, not pixels. A 1920x1080 all-black PNG
  is 10,899 B. A title whose every route frame is a near-black loading screen
  also reads as black. In that case the route saw nothing either, so void is
  still right.
