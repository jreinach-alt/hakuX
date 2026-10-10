# lane.placement1010 -- pin by role: the PFIFO thread on the prime core while the vCPU halts instead of spinning (#433, 0.5)

Opus (engineering, per the 10-10 model table; Sonnet when usage is Low). Issue: none (dispatched directly by lane.local,
#433 umbrella; step 4 of docs/lanes/nfs30plan1010/PLAN.md). Nova only.

**Dispatch condition.** Only if lane.nfs30plan1010's probe passes: requests `1-1791652213-nfs30plan1010-2992539` and
`1-1791652214-nfs30plan1010-2992731` (`HAKUX_IDLE_HALT=1`, plain build, route `nfs-mw-quickrace`) against
nfsframe1010's `1-1791649039`/`1-1791649724`, prediction `docs/testing/predictions/nfs30plan1010-idlehalt.json`:
B's pooled countdown pace <= 0.92 x A's with the vCPU on-CPU share down >= 25 points. If F fails in both B runs,
placement is not a lever for this scene and this brief is not dispatched (nfs30plan1010's NOTES will say so).

## Why
- At the NFS race start the vCPU thread holds the X3 prime core 88% of wall time (PMU, nfs30plan1010 NOTES 5.5),
  37.6 of its 66.6 ms/frame on CPU being the guest's idle loop spinning (`HAKUX_IDLE_HALT` off by default).
  The PFIFO thread paces the frame (`cls pgraph` 78-83%) with 30-38 ms on CPU per frame; which core it ran on was
  not recorded. If it runs on an A715 while the X3 spins, its on-CPU time is ~1.2x what the X3 would take:
  ~4-5 ms/frame cold, the margin between a 2- and a 3-VBLANK frame after steps 1-3.
- The probe measures exactly that: halt the vCPU, see whether the PFIFO thread's frame shortens. The probe's switch
  is an instrument; the fix is placement, because idle-halt as a default is already decided (lane.idlehaltdefault,
  09-29: opt-in; fps within 1.3% on the titles it ran, J/frame 0.68-0.73x).
- The corpus: lane.vcpuprime428 pinned the vCPU to the prime core and lost 21.5% because the scheduler ejected it
  to the little cores (its NOTES: next use `uclamp.min` or a big+prime mask). `XEMU_OPT_THREAD_AFFINITY` in
  android/app/src/main/cpp/xemu_android.cpp is dead code. Placement must be by role, with a mask that cannot be
  ejected to a little core.

## The job
1. **Instrument first: where do the threads run?** `HAKUX_PLACE_TRACE=1`, default off: per 60 frames, for the
   PFIFO, vCPU, render and main-loop threads, the CPU-id histogram (sched_getcpu sampled at frame boundaries or
   read from `/proc/self/task/<tid>/stat`). One table in NOTES.md for the race start, plain build, with and without
   `HAKUX_IDLE_HALT=1`. This confirms or refutes the "PFIFO on an A715" premise before any pin.
2. **Build pin-by-role behind `HAKUX_PLACE=1`, default off:** PFIFO -> prime core (X3); vCPU -> big+prime mask with
   `uclamp.min` raised (not a bare prime pin: vcpuprime428); render thread -> a big core; main loop and audio
   unpinned. Core ids read from the device's topology at start (`/sys/devices/system/cpu/cpu*/cpu_capacity`), not
   hard-coded. A title-table entry, not a global default, for idle-halt on NFS if the probe says the X3 must be
   free for the pin to pay (`kTitle*` tables, xemu_android.cpp:796-810 is the pattern).
3. **Register the prediction first**, docs/testing/predictions/placement1010-*.json: NFS race start, 2x2: PLACE on/off
   x IDLE_HALT on/off, plain build, 2 runs per cell at most (batch them; 12 starts per run). Predict the countdown
   period and the v2/v3/v4 histogram per cell; PLACE on + HALT on <= 0.92 x both off; PLACE on + HALT off tells
   whether the pin alone can take the X3 from a spinning vCPU (expected: no). Also J/frame from the power record,
   since a halt is a power change (sustain507: -0.58 W on the Nova).
4. **Pixel check:** none needed (placement does not touch pixels); say so in PR.md.
5. **PR.md:** `State: ready`; the placement table and the 2x2; `Needs device: yes (Nova, used)`;
   `Release note (performance): ...` or `none`; default-on recommendation per title, with the thermal record
   (a pinned PFIFO thread on the X3 is a heat choice; thermal507's gate applies).

## Rules
- Territory: android/app/src/main/cpp/xemu_android.cpp (thread affinity and the title table only), util/qemu-thread-posix.c
  (a named-thread affinity hook), hw/xbox/nv2a/pfifo.c (thread start only), docs/lanes/placement1010/**,
  docs/testing/predictions/placement1010-*.json. Ask for any other file by name on the board.
- No clock, governor or performance-mode remedy. A pinned clock is allowed only as an instrument to prove who paces,
  and the arm says so. Placement is not a clock, but a `uclamp.min` raise is a scheduler hint: state its value and
  keep it to the vCPU.
- Titles run on the Nova only. Use pad.sh for input (RT is the gas), never `adb shell input keyevent`.
- Perf claims come from this lane's runs only; cite the run id for every figure.
- A measured scene needs a moving player: confirm it from the `s*-g11.png` frames, not the HUD clock.
- No `gh`. Never `pkill -f` or `pgrep -f`.
- This is a headless session, and it ends when the turn ends. Never end a turn "waiting for a background task". With
  runs pending, commit and push `docs/lanes/placement1010/WAITING`, one `run <request-id>` line each; lanewaker
  resumes you when they are DONE.
