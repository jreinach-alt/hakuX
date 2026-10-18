# vtxstale1018 notes

Issue #1049 (GTA III drops into the teens while driving), part of #433. Brief: `briefs/vtxstale1018.md`.
Source of the lever: `docs/lanes/gta3instr1018/FINDINGS.md` sections 2.2 and 4 (lever 2), on lane/gta3instr1018.

[lane.vtxstale1018] status: Step 0 committed; implementing.

## 0. Already tried

| what | who, where | result | bearing on this lane |
|---|---|---|---|
| One stale span per receiving slot (`vertex_ram_stale_min/max`), copied from the outgoing slot at rotation | 2dd232172c (2026-09-10, #39) | Fixed #39: with three slots, an upload reached two copies and the third read zeros (Texture render target 4-7/40 to 10/40, Stencil 14/16 to 16/16) | This is the code being replaced. The page form must keep its guarantee: an upload reaches every slot however many the ring has. Its suites (Texture render target, Stencil, Depth buffer fixed function) are the regression set. |
| Per-slot vertex-RAM copies, `uploaded_bitmap` copied cur -> next at rotation | 41be412ae0 (2026-03-18) | The ring as it stands | `uploaded_bitmap` is per slot, 1 bit per 4096-byte page, `r->bitmap_size` bits: the new stale bitmap uses the same geometry. |
| `[dipwin]` timing of the rotation copy | gta3instr1018 (run 1792340293-gta3instr1018-503029, ref 25915ae59e, PurpleVK) | `stale` 2.19 of `fen` 2.36 ms/flip on foot; 129 KB/flip uploaded becomes ~30 MB/flip copied (14-23 MB a rotation, 117-508x) | The before number. The copy is the cost, not a fence wait (`rotfen` 0.04). |
| `HAKUX_VTX_EXACT=1` | fpsbelow1012 (L4a, default off) | Narrows the guest-to-current-slot download/stale-test to the bytes a draw reads | Different stage (guest RAM into the current slot), not the slot-to-slot rotation copy. With it on, an upload can be byte-exact and unaligned: the page mark must round both ends. |
| `HAKUX_VTX_HAZARD=1` | gtasagpu1011 (default off) | Finishes the command buffer when an upload overwrites bytes an earlier draw in it reads | Can rotate inside `pgraph_vk_update_vertex_ram_buffer()` before the memcpy. The marks are made after the memcpy against the then-current slot, so a rotation there is covered. |
| Vertex redo, surface copies (R1/R2), full-path binds | gta3dip1018, fabledip1018, drawrec1010 | Copies to 0 leave the in-car 52 render passes; drawrec1010's stale `shader_bindings_changed` (`HAKUX_DRAWREC`) | Other levers. None touched the rotation copy. |

`git log -S vertex_ram_stale origin/master`: 2dd232172c only. Nobody has tried a page-granular stale copy.

## 1. Territory (board 50976c18eb, 2026-10-18 09:52 PDT)

| file | held by before | how taken |
|---|---|---|
| vk/vertex.c | lane.fps1015 (folded, ancestor of origin/master, no unit) | stale hold, released on its row |
| vk/buffer.c | lane.x1port1012 (folded, ancestor, no unit) | stale hold, released on its row |
| vk/renderer.h | nobody (fps1015 and x1port1012 both released it) | claimed |
| vk/draw.c | lane.gta3instr1018 (draft, no unit, only a device run outstanding) | GRANT; returns to gta3instr1018 when this lane folds. One overlapping hunk: its `[dipwin]` stale timer wraps the rotation copy. Whoever folds second merges master and resolves it. |
| vk/vtxstale.h (new), docs/testing/jobs/selftest.d/99-vtxstale-pages.sh (new) | nobody | claimed |

buffer.c is outside the brief's three files but holds the per-slot allocation and the `stale_min/max` init (buffer.c:481-485,
521-526, 553, 586); the bitmap cannot be allocated anywhere else.

## 2. Writers and readers of the per-slot copies and the stale span (read, origin/master be379c5b7e)

Writers of `frame_staging[i].vertex_ram.mapped`:
- vertex.c:222 `pgraph_vk_update_vertex_ram_buffer()`, the current slot only (`get_staging_buffer(BUFFER_VERTEX_RAM)`).
  Callers: `update_memory_buffer()` (draw-time sync), renderer.c:515 (whole VRAM at init, then slot 0 marked
  initialized), render_thread.c RCMD_FLUSH / pending flush (whole VRAM, render thread).
- draw.c:5851 rotation, whole-buffer copy into a slot never initialized.
- draw.c:5860 rotation, the stale span copy.
- render_thread.c:173-196 `process_vertex_ram_update` (RCMD_VERTEX_RAM_UPDATE) writes too, but nothing enqueues that
  command (only the enum at renderer.h:765 and its case). Dead.

Writers of `vertex_ram_stale_min/max`: vertex.c:232-243 (widen every other slot), draw.c:5866-5867 (reset at rotation),
buffer.c:483-484 (init). Readers: draw.c:5856-5859 only. `pgraph_vk_flush_all_frames()` (draw.c:5137) clears the
non-current slots' flush span and `uploaded_bitmap` but leaves the stale span: correct, those slots are still behind.

Readers of the copies: the vertex bindings (draw.c:8348, 10454) bind the current slot's buffer; `vtxhz_overwrites()`
reads the current slot. `flush_memory_buffer()` (draw.c:4044) flushes `vertex_ram_flush_min/max` at submit; the Nova's
per-frame VERTEX_RAM is coherent and cached (buffer.c:508 log), so that flush is a no-op there and the flush range can
stay a span (the copied runs' lowest to highest byte).

Pre-existing, not changed here: draw.c:5433-5436, a change of `g_xemu_submit_frames` sets `current_frame = 0` with no copy,
so slot 0 runs with whatever it held. Same with the span and with the bitmap.

## 3. Design

Invariant (the one 2dd232172c relies on): for every slot s other than the current one, `stale[s]` covers every page on
which s differs from the current slot.
- An upload writes the current slot and sets its pages in every other slot's bitmap: preserved.
- Rotating `next` in copies `stale[next]`'s pages from the current slot, so `next` equals the current slot everywhere, and
  clears `stale[next]`. The third slot's differences from the new current slot are the same as from the old one: preserved.
- A slot never initialized takes the whole-buffer copy and clears its bitmap.

Cost: the bitmap is `vram/4096` bits (32768 for 128 MB, 4 KB); a rotation scans it with `find_next_bit` /
`find_next_zero_bit` and copies each run.

## Stop rule

The same failure twice for one cause: stop and report.
