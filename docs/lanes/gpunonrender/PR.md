Lane: gpunonrender                Issue: #433
Base: master @ 8522288a77 (merged c3a0c70ace)
Files: hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/texture.c, docs/lanes/gpunonrender/NOTES.md, docs/lanes/gpunonrender/PR.md, docs/lanes/gpunonrender/OUTBOX.md, docs/lanes/gpunonrender/WAITING, docs/lanes/gpunonrender/stepsdump.py, docs/lanes/gpunonrender/qstate.py, docs/lanes/gpunonrender/routes/gnr-spiderman2.route, docs/lanes/gpunonrender/routes/gnr-mc2.route
Prediction: none: no arm
Needs device: yes    Needs NDK: yes

Release note (none): telemetry and an opt-in switch; HAKUX_GPUXFR and HAKUX_SURFSPLICE are off by default and change no rendering or timing.

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
  Its cost is not yet measured; a timed arm with it unset is queued.

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

## Status

The instrument is built and committed. Two control arms on Nova (NG Black, same
route, same binary, 150 s each: `HAKUX_GPUXFR=1`, and the same with
`HAKUX_GPUXFR_CTRL=16`) were queued at 9609d0299f. The `xemu-gpu` lines of the
earlier pair already show the 16-copy control in the existing `Xfr` value
(0.40 to 1.10 ms per frame median); the `xemu-xfr` category reading is pending.
The per-title category tables, the ranking and the cost measurement follow in
`docs/lanes/gpunonrender/NOTES.md`.
