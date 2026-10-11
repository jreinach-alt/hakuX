# frametrace: the PFIFO thread's GPU waits named per title (draw.c:4386 under pfifo.lock on Simpsons; draw.c:4319 behind the render thread's fence on Forza and Nightfire); Vulkan waits by call site; G1 + G5
State: ready

Lane: frametrace            Issue: #433
Base: master @ c3625aad90 (the fold of this lane's first PR)
Files: accel/tcg/cpu-exec.c, hw/xbox/nv2a/pgraph/pgraph.c, hw/xbox/nv2a/pgraph/profile.c, hw/xbox/nv2a/pgraph/profile.h, docs/lanes/frametrace/NOTES.md, docs/lanes/frametrace/OUTBOX.md, docs/lanes/frametrace/PR.md, docs/lanes/frametrace/build_local.sh, docs/lanes/frametrace/ft_selftest.c, docs/lanes/frametrace/ftread.py, docs/lanes/frametrace/selftest.py, docs/lanes/frametrace/chain.py, docs/lanes/frametrace/idlejoin.py, docs/lanes/frametrace/rtjoin.py, docs/lanes/frametrace/captures/1-1791264140-lane.frametrace-1709247/frames.csv.gz, docs/lanes/frametrace/captures/1-1791264140-lane.frametrace-1709247/ft.log.gz, docs/lanes/frametrace/captures/1-1791264140-lane.frametrace-1709247/meta.md, docs/lanes/frametrace/captures/1-1791264148-lane.frametrace-1709509/frames.csv.gz, docs/lanes/frametrace/captures/1-1791264148-lane.frametrace-1709509/ft.log.gz, docs/lanes/frametrace/captures/1-1791264148-lane.frametrace-1709509/meta.md, docs/lanes/frametrace/captures/1-1791264150-lane.frametrace-1709628/frames.csv.gz, docs/lanes/frametrace/captures/1-1791264150-lane.frametrace-1709628/ft.log.gz, docs/lanes/frametrace/captures/1-1791264150-lane.frametrace-1709628/meta.md
Prediction: none: telemetry, off by default; judged by the selftest and the overhead test already passed (NOTES section 5)
Needs device: no (the three Nova captures are read)    Needs NDK: yes

**Result (NOTES section 11).** Three Nova captures at f2763fe4c0, frames
checked, read by call site (`fw=`, addr2line against the built APK):

| title | the PFIFO thread blocks at | waiting for | ms/frame | consequence |
|---|---|---|---|---|
| Simpsons | `vk/draw.c:4386`, frame-slot fence, STALLED finish under pfifo.lock | the GPU, 8 times a frame | 8.06 (+0.93 `reports.c:259`) | the vCPU's DMA_PUT waits 7.90 ms/frame behind it; guest 16.2 + 7.9 + 0.4 = P 24.4 |
| Forza | `vk/draw.c:4319`, `qemu_event_wait`, non-deferred SURFACE_DOWN finish | the render thread's fence wait (`render_thread.c:157`): the GPU. Caller `surfupd` (surface.c:5169), `cpuw0` | 12.2 (+3.1 `surface.c:1266`) | the PFIFO thread sets the pace in 57% of late frames; 27.0 fps against 30 |
| Nightfire (play) | `vk/draw.c:4319`, same | `render_thread.c:157` | 7.4 | 64% of late frames are guest work |

`rtjoin.py` (new) shows that `draw.c:4319` is the unhooked wait: per second,
the PFIFO's unbooked time tracks the render thread's fence wait (corr
0.97-1.00, slope 1.0-1.24). The GPU ran at 615 MHz and was busy 24-49% of the
frame in every title. The waits are serial round trips, not GPU throughput.
Ranked fix targets (code lanes'): Forza's `surfupd` round trip; Simpsons'
GPU wait under pfifo.lock.

Reader changes: `ftread.py --until` (end a window where the frames stop
showing play); `chain.py`/`idlejoin.py` follow `read_logs`' sixth value;
`chain.py`'s port check accepts the period-late rule. Raw frame blocks of
the three captures are in `captures/`.

### Session 5 (the instrument at this head)

The owner's question: which processor waits on which, and where in our
code. From the code, joined with the counters every capture already has,
the PFIFO thread's unhooked blocked time (Simpsons 7.4 ms a frame, Forza
14.6) is **`vkWaitForFences(frame_fences[next_frame])` at
`hw/xbox/nv2a/pgraph/vk/draw.c:4386`**: the frame-slot rotation at the end of
every PFIFO-thread finish. Three slots rotate per finish, not per guest
frame, and Simpsons makes 8.8 finishes a frame, so the PFIFO thread can run
at most a quarter of a frame ahead of the GPU. Most of those finishes are the
STALLED finish (`vk/reports.c:335`), which the PFIFO loop calls with
`pfifo.lock` held (`pfifo.c:2163`). That is what the guest's DMA_PUT store
waits behind (Simpsons' 6.3 ms a frame). NOTES section 10 has the evidence,
two other GPU waits on the same paths (`reports.c:259`, `renderer.c:2824`)
and the result that would refute the naming.

To measure it rather than infer it, without editing draw.c (another lane's
row), the instrument now interposes volk's Vulkan entry points when
`HAKUX_FRAMETRACE=1`:

| | |
|---|---|
| interposer | `vkWaitForFences`, `vkQueueSubmit`, `vkGetQueryPoolResults` (WAIT_BIT), `vkQueueWaitIdle`, `vkDeviceWaitIdle`: booked as a fence or submit wait on the calling thread and by call site, then the driver's entry is called unchanged. Unset: nothing is swapped |
| context | `pgraph.c` tags the PFIFO loop's `process_pending_reports` (pfifo.lock held) and `process_pending`; PFIFO waits by context in `pc=` and CSV `p_c_*` |
| call sites | summary `fw=`: top eight `<row>.<ctx>.<reason>#<slot>:<ms/frame>/<calls/frame>`; each slot named once with its `.so` offset for addr2line |
| G1, G5 | applied as granted. G5 is hooked in the release variant of `pgraph_mmio_lock` too; hooks.diff reached only the perf-log twin |
| selftest | 43 checks, 21 mutants, all caught |

Captured and read (Nova, ref f2763fe4c0): Simpsons `1-1791264140-lane.frametrace-1709247`,
Forza `1-1791264148-lane.frametrace-1709509`, Nightfire
`1-1791264150-lane.frametrace-1709628`.

Checks: NDK clang type-check of profile.c, pgraph.c, cpu-exec.c, cpus.c
(Release line, re-pointed): clean apart from warnings that were there
before. Local `assembleDebug` of f2763fe4c0: BUILD SUCCESSFUL. Preflight: all branch gates pass; `coverage` fails on #838-#846, the board's. Desktop build: not run
(this host cannot build desktop; AGENTS.md).

Release note (none): opt-in telemetry, off unless HAKUX_FRAMETRACE=1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
