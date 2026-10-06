# frametrace: the PFIFO thread's GPU wait named (draw.c:4386 under pfifo.lock); Vulkan waits measured by call site; G1 + G5
State: draft (waiting on three Nova captures)

Lane: frametrace            Issue: #433
Base: master @ c3625aad90 (the fold of this lane's first PR)
Files: accel/tcg/cpu-exec.c, hw/xbox/nv2a/pgraph/pgraph.c, hw/xbox/nv2a/pgraph/profile.c, hw/xbox/nv2a/pgraph/profile.h, docs/lanes/frametrace/NOTES.md, docs/lanes/frametrace/OUTBOX.md, docs/lanes/frametrace/PR.md, docs/lanes/frametrace/WAITING, docs/lanes/frametrace/build_local.sh, docs/lanes/frametrace/ft_selftest.c, docs/lanes/frametrace/selftest.py
Prediction: none: telemetry, off by default; judged by the selftest and the overhead test already passed (NOTES section 5)
Needs device: yes (three Nova captures queued)    Needs NDK: yes

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

Queued (Nova, ref f2763fe4c0): Simpsons `1-1791264140-lane.frametrace-1709247`,
Forza `1-1791264148-lane.frametrace-1709509`, Nightfire
`1-1791264150-lane.frametrace-1709628`.

Checks: NDK clang type-check of profile.c, pgraph.c, cpu-exec.c, cpus.c
(Release line, re-pointed): clean apart from warnings that were there
before. Local `assembleDebug`: see NOTES section 10. Desktop build: not run
(this host cannot build desktop; AGENTS.md).

Release note (none): opt-in telemetry, off unless HAKUX_FRAMETRACE=1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
