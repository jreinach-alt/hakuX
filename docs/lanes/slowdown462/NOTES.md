# lane.slowdown462 -- per-title frame-time attribution (#462)

Five slow titles, one protocol, one device (Nova ee317437, MAX). Measure and
attribute only; fixes go to the per-title lanes.

## The build and the instruments (same for every title)

- **Soaks:** ref `e5db66fa37` (master when this lane started), `--perflog`,
  survey route, 420 s, Nova, release priority (`HAKUX_RELEASE_PRIO=1`), MAX
  regimen (soak_title.sh's default; `perf_regimen.json` in each result).
- **Profiles:** `capture_profile.sh` (this dir), a held Nova session per title,
  APK `builds/a593d8eb85.apk` (not perflog). a593d8eb85 and e5db66fa37 build
  the same emulator: `git diff --stat a593d8eb85 e5db66fa37 -- ':!docs'` is
  empty. Asked of the host in `dispatch/board-requests/slowdown462.md`.
- **Window:** from the route's `mark play` + 30 s to 10 s before `soak end`.
  The survey route writes `mark play`, not `mark gameplay`; that the window is
  gameplay is checked from the route's `play` shots.
- **Readers:** `titleread.py <result-id>` runs, over that one window, the
  readers earlier lanes validated: aufire412's `splitread.py` (phase, cpu,
  work, stall medians), aufire412b's `pace.py` and `vbl.py` (VBLANKs per flip,
  VBLANK rate, clamps), tbchurn424's `churn.py` (#424 churn). Checked on
  `1790470425-aufire412b-4161655` (AUF, 53a9b91df3 perflog, MAX): it
  reproduces aufire412b's mission numbers (15.0 fps, Vpf 3.82, vCPU 86%).
- `waitres.py`: bounded wait on result ids, printing queue position and holds.

## What is already known, and what it does not answer

| title | prior evidence | open |
|---|---|---|
| DOA1U | doa413 (dc38b745b8, default regimen): fight 14-15 fps, `Surf` 33-52 of 55-67 ms, GPU 31-44 ms. doa413b's lazy-surface cut refuted (14.9 off vs 13.6 on) and ships default-off (PR #440, must-not-move PASS). | which part of `surface_update`: `xemu-surf` is not in the dispatcher's LOGCAT_SPEC |
| AUF | aufire412b: vCPU 54% in `cpu_exec_loop` (37% at one barrier), 26% guest JIT; renderer `Surf` 26.5, Draw 16.7, GPU 29.3 ms (1790470425, MAX) | the return causes (retreason425 in queue) |
| Blinx | blinx372d/c: attract demo, Sub 25-35 ms of 57-71 (synchronous zeta downloads); gameplay not read | gameplay split |
| Blinx 2 | nothing | everything |
| Forza | forza414 (Thor): race `Sub` 26-37 of 43-63 ms, ~5.5 uncoalesced `sd_complete_def` finishes/frame | Nova numbers; which caller |

## Log

- 2026-09-26 21:04 PDT: pilot queued, DOA1U, `1-1790481863-slowdown462-3154279`,
  behind three titlebench soaks. Nova at 36%, on a 500 mA port.
