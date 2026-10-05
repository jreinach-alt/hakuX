# lane.frametrace OUTBOX

## 2026-10-05 (session 1): GRANT REQUEST, hook lines outside the row

**The patch is ready: `docs/lanes/frametrace/hooks.diff`** (8 files, +83 -4,
`git apply --check` clean on 606bbf1ee1, every file type-checked with the
NDK Release compile line). On the grant I apply it as one commit.

The instrument's core is in the row (`profile.c`, new `profile.h`,
`system/cpus.c`). From there it reads, per frame: the flip, the present
(`nv2a_profile_increment`), the vCPU's, PFIFO thread's and main loop's
schedstat (on-CPU / run-queue / blocked), the vCPU's BQL waits (with the
holder) and halts, the DMA_PUT pfifo.lock wait (`lock_wait_ns`, already
always on), the PFIFO idle (`renderer_idle_acc_ns`), GPU ns from
`gpu_ts_readback`, and GPU MHz from sysfs.

What it cannot see from the row, and the hooks that would give it. Each is
a call into `profile.h` behind one predictable branch on a global
(`hakux_ft_on`), so a build with the variable unset runs the code it runs
today. No behaviour change at any site.

| # | file : lines (at d32c35d3ce) | hook | what it adds | without it |
|---|---|---|---|---|
| G1 | `accel/tcg/cpu-exec.c` : 1255 (`rrw_sti`, where `rrw_idle = true`) and 1276 (`rrw_wake`, where `rrw_idle = false`) | `hakux_ft_gidle_begin()` / `hakux_ft_gidle_end()` | guest idle per frame (the kernel idle loop, spun or halted) | **the vCPU's on-CPU time cannot be split into guest work and the idle loop's spin.** Forza idles 20 ms/frame on-CPU (vcpu60 1.2); without G1 it reads as guest-vCPU-run (pinned by the selftest) |
| G2 | `hw/xbox/nv2a/pgraph/vk/render_thread.c` : 198-206, 150-165 | `hakux_ft_thread(HAKUX_FT_RENDER)` at thread start; waits around `vkQueueSubmit` and the two `vkWaitForFences` | the render thread's row and its submit and fence time | no render-thread row; no submit time |
| G3 | `hw/xbox/nv2a/pgraph/vk/draw.c` : 1731, 3786, 3978-4030, 4211, 4221, 4319, 4386 | waits around each: `vkQueueSubmit` (submit), `vkWaitForFences` and the `finish_event` wait (fence), `wait_frame_submitted` (render thread) | the PFIFO thread's blocked time by reason, which is what a vCPU lock wait's holder split reads | **a vCPU lock wait's holder reads RUN when it sat in a fence**: the split has no PFIFO spans to intersect |
| G4 | `hw/xbox/nv2a/user.c` : 92-95 | `HAKUX_FT_W_PFIFO_LOCK` wait beside the existing `lock_wait_ns` | the DMA_PUT wait with its holder split | the wait is in the frame as a total with no holder: unattr |
| G5 | `hw/xbox/nv2a/pgraph/pgraph.c` : 958-968 (`pgraph_mmio_lock`) | `HAKUX_FT_W_PGRAPH_LOCK` wait | vCPU pgraph.lock waits with the holder split | blocked, unnamed: unattr |
| G6 | `hw/xbox/nv2a/nv2a.c` : 931, 1158 | `hakux_ft_vblank()` beside `vblank_fired++` | the VBLANK's own timestamp | slack is read from the present (the guest ISR's INCREMENT write), which includes ISR latency |
| G7 | `hw/xbox/nv2a/pfifo.c` : 2187-2229 (idle park) | `HAKUX_FT_W_IDLE` wait from the park to `cbl_leave()` | the PFIFO thread's idle as a span, for the holder split | idle total only (always on) |
| G8 | `hw/xbox/nv2a/pgraph/vk/surface.c` : 70, 79, 1266, 2079, 2560 | `HAKUX_FT_W_DOWNLOAD` around the four download/flush event waits; fence around `wait_frame_fence` | a guest access that waits for a surface download (vcpusleep's never-measured prior) | blocked, unnamed |

G1 and G3 are the ones the attribution needs most; G2, G4 and G5 make the
holder split possible on the real lock sites; G6-G8 sharpen it.

Until the grant this lane builds, tests and captures the in-row instrument.

### Selftest wiring (outside the row)

`docs/lanes/frametrace/selftest-fragment.sh` is the proposed
`docs/testing/jobs/selftest.d/90-frametrace.sh`: one `check` running
`python3 docs/lanes/frametrace/selftest.py` (~7 s, a C compiler with
pthreads, no device). Please copy it in.

### Device

- Queued, Thor, Forza (the Thor's copy), the pilot pair (2 x 480 s):
  `1-1791216352-lane.frametrace-2340761` (HAKUX_FRAMETRACE=1) and
  `1-1791216356-lane.frametrace-2340965` (unset), ref 606bbf1ee1, route
  `forza-frametrace` (lane.gpuclock's `drive forza 400 mark`). Criteria:
  NOTES section 2.
- **Simpsons needs a host capture under a pathfind hold** (as vcpusleep's
  simp1): the request follows once the pilot's frame records are read.

### 09:15 PDT: the Thor pilot, and what is queued now

- **Thor fault, not the instrument:** both pilot runs died before the race
  (B, instrument on, at 42 s in the intro; A, instrument OFF, at 25 s with
  `not-foreground: com.magneticchen.daijishou` in front). Same family as
  lane.gpuclock's 08:51 aborts (Lime3DS in front). I have not re-queued on
  the Thor. Whoever owns the Thor's focus/second-screen state: two lanes
  have hit it this morning.
- B's frame CSV (761 frames) shows the record works on the device: all
  rows filled, the GPU clock readable by the app (615 MHz from kgsl
  `gpuclk`, an open question for lane.gpuclock), builder cost 17-19 us/frame.
- The [hakuX-ft*] lines were dropped by LOGCAT_SPEC; fixed at 0bb89cd1f5
  (they now go out on `hakuX-lane`, which the spec keeps).
- Queued on the Nova (behind pathfind's hold and the four requests ahead):
  `1-1791216614-lane.frametrace-2373212` Nightfire, on;
  `1-1791216620-lane.frametrace-2374008` Tron (vcpuwait433's
  tron-newgame-anystate), on; `1-1791216621-lane.frametrace-2374160`
  Nightfire, off (the overhead pair's A; queued last so the Nova is left
  without the env). 24 min of device time in all.

### HOST CAPTURE REQUEST: Simpsons free roam under a pathfind hold

`docs/lanes/frametrace/capture_simpsons_frametrace.sh simpft1` (lane.local
runs it; a lane does not touch the device). It is
`capture_simpsons_gpuclock.sh` without the performance_mode switching, with
`env_vars=HAKUX_FRAMETRACE=1` set and read back before the session and
cleared (read back) on every exit, a second logcat that keeps `hakuX-lane`,
and the frame CSV pulled at the end. APK: `dispatch/builds/0bb89cd1f5.apk`
(the dispatcher builds it for the Nova requests above). HOLD_S 300, about
10 min of device time. Out: `perf/2026-10-05-frametrace/simpft1/`.

### Spend

Session 1 (Opus): reading, design, instrument, selftest, hook patch, pilot
queued. No device minutes used yet.
