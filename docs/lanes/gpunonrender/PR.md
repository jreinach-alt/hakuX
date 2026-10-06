Lane: gpunonrender                Issue: #433
Base: master @ c3a0c70ace
Files: hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/reports.c, docs/lanes/gpunonrender/NOTES.md, docs/lanes/gpunonrender/PR.md, docs/lanes/gpunonrender/OUTBOX.md, docs/lanes/gpunonrender/WAITING, docs/lanes/gpunonrender/stepsdump.py, docs/lanes/gpunonrender/qstate.py, docs/lanes/gpunonrender/abread.py, docs/lanes/gpunonrender/rls.py, docs/lanes/gpunonrender/routes/gnr-spiderman2.route, docs/lanes/gpunonrender/routes/gnr-mc2.route, docs/lanes/gpunonrender/routes/gnr-toejam.route
Prediction: none: no arm (A/B soaks read by hand against expected results written in NOTES.md before each run)
Needs device: yes    Needs NDK: yes

Release note (none): telemetry and opt-in switches; HAKUX_GPUXFR, HAKUX_GPUTS_INRP, HAKUX_SURFSPLICE and HAKUX_STALLFIN are off by default and change no rendering or timing. The GPU timestamp stats now count each command buffer once (perflog numbers only).

## What this measures

The command buffer's non-render GPU time (`gpu_nonrender_ms`, the span of the
command buffer minus its timestamped render passes) was measured as one number.
This change splits it by operation. Each top-level non-render scope that
records into the frame command buffer is bracketed by a timestamp pair:

| category | scope | file |
|---|---|---|
| `surf_up` | `pgraph_vk_upload_surface_data` | surface.c |
| `tex_up` | `upload_texture_image` | texture.c |
| `s2t` | `copy_surface_to_texture`, `copy_zeta_surface_to_texture` | texture.c |
| `download` | `download_surface_record_deferred`, `download_surface_to_buffer` | surface.c |
| `handoff` | `surface_handoff_record` | surface.c |
| `barrier` | `create_surface_image`, `bind_surface_as_texture`, `bind_zeta_surface_as_texture` | surface.c, texture.c |
| `other` | anything else in the command buffer, and any bracket not measured | - |

Each bracket is a timestamp pair in a query pool of its own. The pool is read
in the existing per-frame readback, after the frame fence, so no GPU sync is
added. The existing `gpu_nonrender_ns` is unchanged.

Per 60-frame window the perflog build logs two `xemu-xfr` lines: the median,
mean and 90th percentile of ms per frame for each category, the operations per
frame, the residual against `gpu_nonrender_ms`, and the four largest call sites
(`category@line`), with the count of brackets that were not measured.

`HAKUX_GPUXFR=1` turns it on. `HAKUX_GPUXFR_CTRL=N` additionally records N
bracketed 1 MiB buffer copies at the top of every frame, as a control whose cost
is known in advance.

The `xemu-xfr` lines are logged under the `xemu-gpu` tag: the perflog logcat
filter keeps only the tags it lists, and `xemu-xfr` is not one of them. The
line starts with `xemu-xfr`, so it can still be grepped.

## Limits, stated in advance

- A bracket opened inside another is folded into the outer one.
- A scope recorded on the auxiliary command buffer (the frame-end staging syncs
  and any single-time path) is not part of `gpu_nonrender_ms` and is not
  bracketed; those brackets are counted in `dropped`.
- Begin and end are `TOP_OF_PIPE` and `BOTTOM_OF_PIPE` stamps, as the render-pass
  brackets already are. A stamp can be written before earlier unfinished work
  completes, so a category can read a little early or late. The control arm is
  what shows how far that goes.
- When the variable is unset, each bracket is one call that returns at once.

## HAKUX_SURFSPLICE (off by default)

When a surface binding is about to upload from VRAM bytes that a pending
surface download has not written yet, `pgraph_vk_surface_update` used to
complete the downloads with a finish and a wait for the GPU, then upload the
bytes it had just downloaded. With `HAKUX_SURFSPLICE=1` the upload copies those
bytes from the download's staging rows into its own staging on the GPU, in the
order the downloads were recorded. Both staging buffers hold guest VRAM bytes,
so the result is what VRAM holds once the downloads complete; the downloads stay
pending and complete where other readers already complete them. Swizzled
downloads, downloads a finish already submitted, and uploads the CPU unswizzles
complete as before. `[sdcall]` (perflog) gains `spl=def/up/dl/kB/cmpl`.

## Render-pass spans on a tiling GPU

The render-pass stamps behind `gpu_nonrender_ms` are written inside the render
pass. Turnip records such a stamp into the pass's draw stream. A GMEM pass
replays that stream once per tile, and the last tile's value is the one that
lands (tu_query_pool.cc, `tu_CmdWriteTimestamp2`). In a GMEM pass, the
"render" span is therefore the last tile's draws. The binning pass, the other
tiles and the tile loads and stores are counted as non-render.

With `HAKUX_GPUXFR=1`, every render pass also gets a stamp pair outside it
(before `vkCmdBeginRenderPass`, after `vkCmdEndRenderPass`). A third
`xemu-xfr` line, `XFR rp`, reports per command buffer:
- `in`: the in-pass render span.
- `out`: the outer render span.
- `nr_out`: the command buffer's span minus `out`.
- `res_out`: `nr_out` minus the bracketed categories.

`xemu-xfr` values are per command buffer. `xemu-gpu` values are per guest
frame.

`HAKUX_GPUTS_INRP=0` leaves out the in-pass stamp pair. Its end stamp is a
`BOTTOM_OF_PIPE` write, which Turnip precedes with a wait-for-idle, once in
every tile it is replayed in. With the variable set, `Rnd` reads 0. A run with
and without it measures what that pair costs the GPU.

## GPU stamps are read once per command buffer

A finish on the PFIFO thread that is not deferred hands the submit to the
render thread, waits for it, and reads the slot's timestamps back. The render
thread marks the slot submitted when it submits (render_thread.c), and nothing
cleared that mark, so frame rotation reached the same slot before it was
recorded again and read the same stamps a second time. Each such command buffer
was counted twice in the GPU phase stats (`xemu-gpu` Tot/Rnd/Xfr, the frametrace
record's `gpu`) and in `xemu-xfr`. On ToeJam & Earl III, which has one such
finish a frame, Tot read 48.5 ms per frame against a 38.4 ms frame.

A per-slot flag is now cleared when the slot's command buffer begins and set by
the first readback; a second readback of the same recording is skipped. Under
`HAKUX_GPUXFR=1` the `XFR rp` line counts the skipped readbacks and their summed
command-buffer span as `dup <n> <ms>`. Nothing that renders reads these stats.

## HAKUX_STALLFIN=reports (off by default)

When the pusher catches up with `DMA_PUT` while the command buffer holds draws,
the PFIFO loop submits it (a `STALLED` finish). That rotates the frame slot,
and the rotation waits for the command buffer two finishes back. The zpass
reports are the only guest-visible value written after a finish: semaphores
are written at the method, and surface bytes the CPU reads have their own
download finishes. With `HAKUX_STALLFIN=reports`, the caught-up submit happens
only when a report is queued. Otherwise the draws stay in the command buffer
until the flip or another finish submits them. The perflog log shows
`[stallfin] reports-only on` (hakuX-vk).

## Status

- The category instrument passed its control. 16 bracketed 1 MiB copies
  read 0.68 ms per command buffer in `ctrl`, `nr` rose by the same amount,
  and no other category moved.
- `HAKUX_SURFSPLICE` removes Forza's `surfupd` finishes (2.00 to 0.00 per
  frame), but it does not remove the wait. That moves to the texture bind's
  surface-range scan (`range` rises from 8.1 to 19.3 ms per frame).
- Spider-Man 2 carries a 6.0 ms per frame `surfupd` wait. Midnight Club II
  carries none; its 8.0 ms is in `range`.
- The unbracketed share of `gpu_nonrender_ms` is 34-83% on these titles.
- **NG Black, outer stamps:** of `gpu_nonrender_ms`'s 10.75 ms per frame,
  10.36 ms (96%) is render-pass work that the in-pass stamps miss. The time
  outside every render pass is 0.39 ms per frame: `download` 0.35, `s2t` 0.01,
  unbracketed 0.02. The GPU frame is 97% render passes, and no copy or upload
  category is large enough to move fps.
- Removing the in-pass stamp pair (`HAKUX_GPUTS_INRP=0`) changes the per-pass
  span by +0.5% and the GPU frame by +0.2 ms: no measurable cost.
- `HAKUX_SURFSPLICE=1` does not engage on Spider-Man 2. Every update with a
  binding uploading was refused by the splice's eligibility check, and the
  `surfupd` wait is unchanged (6.0 to 6.3 ms per frame).
- `HAKUX_STALLFIN=reports` on Simpsons cuts STALLED finishes from 5.36 to 1.05
  per frame, and fps falls from 30.3 to 25.8. The vCPU's wait for pfifo.lock
  grows 4.3 ms per frame, and the GPU frame grows 6.1 ms at the same clock.
  It stays off.
- **ToeJam & Earl III and DOA3, outer stamps:** the same result as NG Black.
  97% (ToeJam) and 96-98% (DOA3, fight and title screen) of
  `gpu_nonrender_ms` is render-pass work. The time outside every render pass is
  0.55 ms (ToeJam) and 0.26-0.34 ms (DOA3) per frame, and `download` is the
  largest part on both.
- On all three titles the GPU frame is inside render passes. The cost to look
  at next is per-pass load/store and GMEM binning, not uploads or copies.

Details and per-run tables are in `docs/lanes/gpunonrender/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
