# lane.frametrace OUTBOX

## 2026-10-05 (session 1): GRANT REQUEST, hook lines outside the row

The instrument's core is in the row (`profile.c`, new `profile.h`,
`system/cpus.c`). From there it reads, per frame: the flip, the present
(`nv2a_profile_increment`), the vCPU's and the PFIFO thread's schedstat
(on-CPU / run-queue / blocked), the vCPU's BQL waits and halts with the BQL
holder, the DMA_PUT pfifo.lock wait (`lock_wait_ns`, already always on), the
PFIFO idle (`renderer_idle_acc_ns`), GPU ns from `gpu_ts_readback`, and GPU
MHz from sysfs.

What it cannot see from the row, and the one-line hooks that would give it.
Each is a call into `profile.h` behind one predictable branch on a global
(`hakux_ft_on`), so a build with the variable unset runs the same code it
does today. No behaviour change at any site.

| # | file : lines | hook | what it adds | without it |
|---|---|---|---|---|
| G1 | `accel/tcg/cpu-exec.c` : 1261-1283 (`rrw_wake`) | `hakux_ft_guest_idle(now - rrw_t)` after `rrw_idle = false;` | guest idle ns per frame (the kernel idle loop, spun or halted) | **the vCPU's on-CPU time cannot be split into guest work and guest idle spin.** Forza idles 20 ms/frame on-CPU (vcpu60 1.2); without G1 it reads as guest-vCPU-run |
| G2 | `hw/xbox/nv2a/pgraph/vk/render_thread.c` : 198-204, 150-165 | `hakux_ft_thread(HAKUX_FT_RENDER)` at thread start; spans around `vkQueueSubmit` (151) and the two `vkWaitForFences` (157, 163) | render thread row (on-CPU / blocked) and its submit and fence ns | no render-thread row; no submit time |
| G3 | `hw/xbox/nv2a/pgraph/vk/draw.c` : 4211, 4221, 4289, 4319, 4381, 4386, 1731, 3786 | span begin/end around each wait: `vkQueueSubmit` (submit), `vkWaitForFences` (fence), `wait_frame_submitted` and the `finish_event` wait (render thread) | the PFIFO thread's blocked time by reason, and its state while it holds pfifo.lock | PFIFO blocked time is one unsplit number; **the holder of a vCPU lock wait cannot be classed as GPU or CPU** |
| G4 | `hw/xbox/nv2a/user.c` : 92-95 | `hakux_ft_wait_end(HAKUX_FT_W_PFIFO_LOCK, ...)` beside the existing `lock_wait_ns` | the DMA_PUT wait as spans with the holder's state (begin and end) | totals only, no holder |
| G5 | `hw/xbox/nv2a/pgraph/pgraph.c` : 960-972 (`pgraph_mmio_lock`) | the same, `HAKUX_FT_W_PGRAPH_LOCK` | vCPU pgraph.lock waits | folded into "blocked, unnamed" |
| G6 | `hw/xbox/nv2a/nv2a.c` : 931, 1158 | `hakux_ft_vblank()` beside `vblank_fired++` | the vblank's own timestamp (slack to the deadline) | slack is read from the present (the guest ISR's INCREMENT write), which includes ISR latency |
| G7 | `hw/xbox/nv2a/pfifo.c` : 2187-2232 (idle park) | span `HAKUX_FT_W_IDLE` from `idle_t0` to after `cbl_leave()` | the PFIFO thread's idle as a state, for the holder test | idle total only (already always on) |

G1, G3 and G2 are the ones the attribution needs; G4-G7 sharpen it. The
patch for all seven is `docs/lanes/frametrace/hooks.diff` (when it lands on
this branch), ready to apply once granted.

Until then this lane builds, tests and captures the in-row instrument. I am
not waiting on the grant to work.

Spend so far: session 1, reading and design only.
