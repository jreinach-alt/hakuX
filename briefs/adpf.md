# lane.adpf

Lane: adpf
Issue: #544
Base: origin/master
Files:
- hw/xbox/adpf.c (new), include/hw/xbox/adpf.h (new), hw/xbox/meson.build
- android/app/src/main/cpp/CMakeLists.txt
- hw/xbox/nv2a/pfifo.c, hw/xbox/nv2a/nv2a.c, hw/xbox/nv2a/nv2a_int.h
- accel/tcg/tcg-accel-ops-mttcg.c
- docs/lanes/adpf/NOTES.md (and anything under docs/lanes/adpf/)
- docs/testing/predictions/adpf-*.json

## Why (evidence)

The owner set the critical path on 2026-09-27 as sustained fps within the heat budget. Every fix is judged on
sustained fps AND energy per frame (J/frame, #523) at device defaults (#533, merged 2026-09-28 03:10Z), not in a
short MAX window.

The engineering review, `/home/justin/hakux-work/lanelocal-scratch/thermal-review.md`, orders the levers. Read its
table row 5 and section 3.2 first. Its step 4 is ADPF hint sessions, to follow the bounded idle halt (#525, PR #528,
folded 2026-09-28 01:40 PDT). Both preconditions now hold:
- #533 qualifies at defaults. ADPF can raise clocks above the defaults, but it cannot lower MAX's vendor floors.
- #525's halt exists. A spinning vCPU reports 100% busy and asks for maximum clocks.

The review's figures:
- **The potential:** -0.5 to -1 W against MAX, and it recovers what MAX bought on CPU-bound titles, *if* the QTI HAL
  honours hints. That is unverified; it is the first thing to find out.
- **The cores:** cpu0-2 are A510 at 2.0 GHz, cpu3-6 are A715/A710 at 2.8 GHz, and cpu7 is an X3 at 3.19 GHz.
- **The API:** only the API 33 subset exists. There is no `setThreads`, no power-efficiency flag and no GPU split.

Today the vCPU thread and the PFIFO thread already call a pin helper:
- `xemu_pin_to_big_cores_cpp("qemu_cpu_thread")` in `android/app/src/main/cpp/xemu_android.cpp:1080`;
- `xemu_pin_to_big_cores("pfifo_thread")` in `hw/xbox/nv2a/pfifo.c:2105`.

Both are the points where each thread exists, so that is where to register its tid. xemu_android.cpp is
lane.rendermode474's: read it, do not edit it.

## Build

1. **Pilot first (owner's pilot rule).** Before any code, write a probe that shows whether the HAL does anything:
   - Can `APerformanceHint_getManager` and `createSession` be reached through `dlsym` from libandroid.so?
   - What does `dumpsys performance_hint` show while a session exists?
   - Does a report of high actual work time move `scaling_cur_freq` on policy3/policy7 at device defaults?
   - This can be a tiny opt-in path in the new file, driven by an env var in a single short soak.
   - If the HAL ignores hints, stop there, write that in NOTES and on #544, and end the lane: that is a result.
2. **Register a prediction** (`docs/testing/predictions/adpf-*.json`) before the A/B arms. Its legs:
   - pixels: the pgraph suites are byte-identical, hints on vs off;
   - sessions: `dumpsys performance_hint` lists both sessions with the expected tids;
   - fps: sustained gfps (p10 and median over the window) at defaults is at least the hints-off arm's, minus noise;
   - energy: J/frame at defaults is not worse by more than noise, and the direction is named per title;
   - a falsifier naming the refuted world: hints that pin the X3 at maximum clocks (J/frame up with no fps gain),
     or a session whose tids are wrong or dead.
3. **The module** (`hw/xbox/adpf.c`, Android only; a no-op stub elsewhere so the desktop build is unchanged):
   - Load the API 33 symbols with `dlsym`, because `minSdk` is 29.
   - Keep two sessions: the vCPU, and PFIFO plus render.
   - Register a thread's tid when it starts. Create a session only once all of its threads exist, since there is
     no `setThreads`.
   - Target = the guest frame period.
   - Once per guest flip, report each session's `CLOCK_THREAD_CPUTIME_ID` delta since the previous flip. Never
     report the frame interval.
   - Log session state and the reported durations on the perflog, at least every 2 s.
4. **Default OFF** behind an opt-in (for example `HAKUX_ADPF=1`) until the legs pass. The PR may propose flipping
   the default, and the audit decides.
5. The idle halt is opt-in today (`HAKUX_IDLE_HALT=1`). Run both ADPF arms with it ON, and say so in the
   prediction. Frame pacing (#526, lane.pacing) may remove the limiter spin while you work. Record the master sha
   that each arm is built on.

## Proof

- **Pixel arm:** pgraph suites A/B on any handheld. Read scores1.tsv for `unreadable` rows (VOID) and run1.log for
  UtilAcceptVsock.
- **fps and energy arms:** A/B at DEVICE DEFAULTS (`PERF_REGIMEN=default`, #533), on ONE handheld per title, with
  both legs on the same device. Use a title that is on the Thor for Thor runs; the Nova is on a battery hold
  until about 18:30 PDT on 09-28. Use one CPU-bound title and one content-capped title (Crimson Skies paces
  itself to 30).
  - Soaks are long enough to show sustained behaviour: at least 10 minutes, read over the late window.
  - Read each run's `thermal.jsonl`, and report `net_w` and `j_per_frame` from title_verdict.py.
- Post the numbers on #544. Open a PR, and mark it ready when CI is green and the arms are read.

## Do not

- Do not edit board files, or any file not listed above.
- Do not hard-pin threads to one core. The thermal pause removes cpu3-7.
- Do not take a device hold. Use the dispatch queue (request.sh), and give critical-path requests the `1-` prefix.
- Do not copy titles between handhelds.
- Do not qualify at MAX: the MAX floors hide exactly what hints are for.
