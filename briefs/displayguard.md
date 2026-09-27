# Lane: displayguard

- **Lane:** lane.displayguard
- **Issue:** #494
- **Base:** origin/master
- **Files:**
  - docs/testing/soak_title.sh
  - docs/testing/devices.sh
  - docs/testing/jobs/selftest.d/99-display-covered.sh
  - docs/lanes/displayguard/NOTES.md

## Why (evidence)

On 2026-09-27 Lime3DS was started on the Thor (bdc158a5) at 11:06:02 PDT. From then until at least 11:51, `com.odin.dualscreen.assistant` held a full-screen window on display 0 above hakuX. `dumpsys window windows` showed `primaryScreenTopLayout`, `ty=BOOT_PROGRESS`, `fillxfill`, `mHasSurface=true`, `mViewVisibility=0x0`.

What the runs produced in that window:
- Every hakuX frame on the Thor is a 10,899 B all-black 1920x1080 PNG. This covers titleroutes `1-1790527983-titleroutes-2100312` (7 of 7 route frames), gta482's held session (9 of 9 frames plus 3 screencaps) and `0-0-x-1790533127-gta482-3508140`.
- GTA stopped flipping: no `gfps` line for 105 s.

The device read `mWakefulness=Awake` with no keyguard. `soak_title.sh` sends `KEYCODE_WAKEUP` (line ~224) and verifies nothing, so these runs looked like measurements.

## Build

1. In `devices.sh`, add a function, e.g. `display_clear <serial>`. It prints the reason and returns non-zero when either of these holds:
   - `mWakefulness` is not Awake after the wake;
   - `dumpsys window windows` shows a visible (`mViewVisibility=0x0`), `mHasSurface=true`, `fillxfill` window on `mDisplayId=0` of type BOOT_PROGRESS / SYSTEM_OVERLAY / APPLICATION_OVERLAY / SYSTEM_ALERT whose package is not hakuX (`com.jreinach.hakux*`) or systemui.

   The host-side reference implementation is the `covered:` check in `/home/justin/hakux-work/host-tools/harness_health.py` (read it; do not import it).
2. In `soak_title.sh`, call it after the wake and before `am start`. On failure, write the status `display-covered` where the result reader sees it, then exit non-zero. It must not produce frames that are scored, and a verdict must never read the run as an fps measurement. Check what `title_verdict.py` and the dispatcher do with a non-zero soak exit. The request must end as a failed or void result, not loop forever in the queue.
3. Add a black-frame guard: when every route frame a soak wrote is under 12 KB, the soak's log records `display-black` and the run's verdict is void.
4. Add the selftest fragment `99-display-covered.sh`. Feed it a fixture `dumpsys window windows` text (with the 09-27 overlay block, and a clean one) through the function with adb stubbed. Assert the output words, not only the exit code.

## Proof

- The selftest passes, and a mutant (the overlay type check removed) fails it.
- One real pilot: a 60 s title soak on whichever handheld is free, with a clean display. It must run normally, so the guard does not refuse a good run.
- The device must not be held for more than 10 minutes, and must be at or above 30% battery.

## Do not

- Force-stop, uninstall or touch any non-hakuX app on a device. The overlay's app belongs to the owner.
- Edit `run_disc.sh`: it is lane.toolsmith's. Name the pgraph path as a follow-up in NOTES instead.
- Edit board files.
