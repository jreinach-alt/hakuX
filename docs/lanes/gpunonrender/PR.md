# gpunonrender: render-pass census (HAKUX_GPUXFR=1); avoidable loads and stores are under 0.4 ms a frame on NG Black and DOA3, and the GMEM scene passes' replay is the cost
State: ready

Lane: gpunonrender                Issue: #433
Base: master @ 0342eba317
Files: hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/texture.c, docs/lanes/gpunonrender/NOTES.md, docs/lanes/gpunonrender/PR.md, docs/lanes/gpunonrender/OUTBOX.md, docs/lanes/gpunonrender/rpcread.py, docs/lanes/gpunonrender/WAITING, docs/testing/nv2a_index.json
Prediction: none: no arm (two telemetry soaks read by hand against expected results and a decision rule written in NOTES.md before the runs)
Needs device: yes    Needs NDK: yes

Release note (none): telemetry only; the render-pass census runs under HAKUX_GPUXFR=1, which is off by default, and changes no rendering or timing.

## What this measures

With `HAKUX_GPUXFR=1`, each render pass that has an outer timestamp pair also
gets a census record: its attachments and their sizes, the load op chosen for
each, the first operation on each attachment in the pass (a clear covering the
whole binding, a partial clear, or a draw), the number of draws, and the fate
of its depth/stencil store (read later, or overwritten whole before any read).
At readback the record is filed with the pass's outer span and its in-pass
span. A pass whose in-pass span is under 0.8 of its outer span is read as GMEM:
Turnip writes an in-pass stamp into the draw stream that a GMEM pass replays
per tile, so only the last tile lands.

Two new perflog lines, `xemu-xfr XFR rpc` (every pass) and `xemu-xfr XFR rpc g`
(passes read as GMEM), give per command buffer, for each group, the passes,
their outer ms and the avoidable MiB:

| group | the pass |
|---|---|
| `lclr` | LOADs an attachment whose first operation is a whole-binding clear |
| `lunif` | LOADs an attachment that holds only a whole-binding clear |
| `zdead` | STOREs a depth/stencil attachment whose next use is a whole-binding clear or a full upload |
| `clronly` | has a clear and no draw |
| `any` | `lclr`, `lunif` or `zdead` |

Also: bytes loaded and stored, the in-pass span, draws, and depth stores read
later or still pending. Surface events come from the download, copy-to-texture,
bind-as-texture, upload and handoff paths (surface.c, texture.c) and from
`destroy_surface_image`. When the variable is unset, each hook returns at once.

## Results (Nova, perflog, `PERF_REGIMEN=default`)

| per frame | NG Black (187 s of play) | DOA3 fight (60 s) |
|---|---|---|
| render passes | 13.1 | 2.3 |
| clear-only passes | 3.0 | 1.0 |
| passes that LOAD a surface holding only a clear | 3.1, carrying 19.9 of 24.5 ms | 1.0, carrying 35.0 of 38.7 ms |
| avoidable MiB, every pass | 9.0 | 8.8 |
| bound on what removing it saves (0.043 ms per MiB, a measured 1 MiB copy) | **0.39 ms** | **0.38 ms** |
| outer span − in-pass span (GMEM binning and tiles before the last) | **11.7 ms** | **19.3 ms** |
| GPU frame (`xemu-gpu` Tot) | 24.6 ms | 38.5 ms |

Every clear that arrives with no pass open gets a pass of its own, and the scene
pass after it LOADs a surface that holds only the clear. Those loads are
avoidable, but at 640x480 each is one 1.2 MiB attachment, so the most a CLEAR
or DONT_CARE load/store change could save is under 0.4 ms a frame on both
titles. The GMEM scene passes spend 11.7 and 19.3 ms a frame outside their last
tile. On the DOA3 fight that is one pass of about 700 draws at in/out 0.50, the
pattern measured on Dead or Alive Ultimate, where sysmem rendering raised the
fight from 14-16 to 21 gfps.

Instrument checks: the census counts the same passes as the outer stamps (K1),
and its clear-only passes match the inline-clear misses to 0.03 a frame (K2) on
both titles. The GMEM/sysmem reading is right on the DOA3 fight (K3), but it
cannot classify a pass shorter than about 0.1 ms. On NG Black 2 of its 3
clear-only passes read as GMEM. The byte bound does not depend on the mode.

Details, the per-scene tables and a ranked render-mode recommendation are in
`docs/lanes/gpunonrender/NOTES.md`, "Render-pass census".

## Checks

| check | result |
|---|---|
| draw.c, surface.c, texture.c at f4ffe285e7, NDK clang line of the release build, with and without `NV2A_PERF_LOG`, `-Wall` | compile; no warnings beyond those on master |
| Android build, perflog, at f4ffe285e7 | built by the dispatcher, apk 281bf2515bb8; ran N0 and D1 on the Nova |

🤖 Generated with [Claude Code](https://claude.com/claude-code)
