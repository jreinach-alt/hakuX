# lane.vtxarr262 -- #262: a vertex array over GPU-rendered memory is never re-fetched

Base: origin/master 2b04d4d422. Fix: `74ac01608d` (parent `342d21c43f`, notes only).
Prediction: `docs/testing/predictions/vtxarr262-surface-vertex-refetch.json`.

## The failing link, by reading (Vulkan)

The brief asked which of three links fails. Traced in source at 2b04d4d422:

1. **Is the surface downloaded before the second draw?** Not by the vertex path.
   The only surface download that path makes is `pgraph_vk_download_surfaces_in_range_if_dirty`,
   called at the top of `pgraph_vk_update_vertex_ram_buffer` (vk/vertex.c:50). That
   function is only reached from `sync_vertex_ram_buffer` when the range tests dirty.
2. **Does the range's DIRTY_MEMORY_NV2A bit get set? No. This is the failing link.**
   Every surface download in vk/surface.c marks `DIRTY_MEMORY_VGA` and
   `DIRTY_MEMORY_NV2A_TEX` (5 sites each) and never `DIRTY_MEMORY_NV2A`. The
   draw-side write hook in vk/draw.c (the `draw_dirty |= color` block) marks
   nothing either. The only vk writers of that bit are the two blit paths
   (blit.c:757, :924). gl/surface.c's download has the same shape (VGA and
   NV2A_TEX only).
3. **Is the sync skipped?** Yes, as a consequence of (2). Pass 1 copies because
   the pages were guest-dirty from when the test filled them. That copy
   test-and-clears the bits, and inside it the download brings back pass 1's red.
   Passes 2-4 find the bits clean. `all_uploaded && !dirty` takes the early exit
   (or `OPT_SYNC_RANGE_SKIP` skips the call, keyed on the same
   `has_dirty_vertex_pages`), so the vertex buffer keeps red.

The brief's premise "nothing in vk/*.c marks DIRTY_MEMORY_NV2A" is right for
surfaces, but blit.c does mark it.

The evidence is the source. No device log was taken; the arm's pass-2..4
colours are the discriminator (red x4 means link 2 is still open).

## Why the fix does not just set DIRTY_MEMORY_NV2A on a GPU write

`update_surface_part` (vk/surface.c:3405) test-and-clears DIRTY_MEMORY_NV2A over
the bound surface as "the guest overwrote this surface" and re-uploads from VRAM
when it is set. That scan is behind `!tcg_enabled()`, so it is dead on Android
(TCG) but live on a KVM/WHPX desktop build. There, marking the bit from a draw
would upload stale VRAM over the render. It would also mean editing
vk/surface.c, which belongs to lane.remote.

## The fix (vk/draw.c only)

The GPU side is tracked read-only in draw.c. `vertex_range_gpu_stale()` walks
`r->surfaces`, `shelved_surfaces` and `invalid_surfaces`. A vertex range is stale if
it overlaps a surface that is either:

- still `draw_dirty`: its data is only in the image, and the re-fetch's own
  `download_surfaces_in_range_if_dirty` downloads it before the memcpy; or
- carrying a `draw_generation` that moved since the range was last copied: it
  was downloaded by someone else (e.g. the flip), after the vertex copy.

The last-copied generation per surface sits in a 64-slot table keyed by the
binding pointer. A pointer is only compared, never dereferenced, and a miss
costs one extra copy. The staleness check feeds both `has_dirty_vertex_pages`
(so the early exit and `OPT_SYNC_RANGE_SKIP` both see it) and the per-range copy
decision. The overlapping surfaces are recorded after each copy.

It compiles cleanly (`-fsyntax-only` with the desktop build's flags; no new warnings).

Cost: one walk of the surface lists per sync range per draw. Downloads happen
only for ranges that overlap a draw_dirty surface, which is the bound the brief
asked for.

## GL

GL has the defect too, and worse. `gl/vertex.c` `update_memory_buffer` copies only
on DIRTY_MEMORY_NV2A and never calls `pgraph_gl_download_surfaces_in_range_if_dirty`
at all, and gl/surface.c's download does not set that bit. Not fixed here (out of
territory).

## The arm

- Suites: Blend surface, Clear, Attrib setter, Degenerate begin end, Inline
  array size mismatch, Overlapping draw modes, Surface as vertex array.
- `Surface_as_vertex_array` has no published golden, and the dispatcher scores
  against a single root. So the must-move leg is scored by hand: run
  `score_sweep.py --goldens ~/hakux-work/hardware/runs/2026-09-25-refs6743/console-run/console`
  over both arms' captures. A request key naming it would be refused by
  request.sh's golden gate. The machine legs are must_not_move over the other
  six suites, plus worse=0.

Next lane: do not try to set DIRTY_MEMORY_NV2A from a GPU write (see above).

## Status 2026-09-25 18:35Z: waiting on the arm

Arms queued: base `1790361025-vtxarr262-base-3284261`, fix `1790361025-vtxarr262-fix-3284294`
(resume: `docs/testing/ab_run.sh --resume <base>,<fix> --expect docs/testing/predictions/vtxarr262-surface-vertex-refetch.json`).
Preflight passes (`--allow-tracker`) at the head that carries the regenerated index.
On resume: check `scores1.tsv` for `unreadable` and `run1.log` for PARTIAL COVERAGE / UtilAcceptVsock.
Then hand-score Surface_as_vertex_array in both arms against the console root, and record it here.
