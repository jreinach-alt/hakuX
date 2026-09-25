# #262: a vertex array over memory the GPU just rendered into is never re-fetched (DynamicUpdateLoop, 96,000 px)

Lane: vtxarr262            Issue: #262 (component pgraph; #184's neighbour)
Base: origin/master 2b04d4d422
Files: hw/xbox/nv2a/pgraph/vk/draw.c, docs/testing/predictions/vtxarr262-*.json,
docs/lanes/vtxarr262/**
Needs device: yes (Thor arm). Needs NDK: no.

## The defect

`Surface as vertex array::DynamicUpdateLoop`: four passes each render a solid colour into
`surface_a_` and then draw a quad whose DIFFUSE array (UB_D3D) points at that memory. Silicon:
red, green, blue, yellow. hakuX 84a67b9cf8: red x4 = 3 quads x 32,000 = 96,000 px. The other
four tests of the suite already match (RenderScalePattern 18,136 px at delta 1 is #38's class,
not this). Oracle: the console captures at
`~/hakux-work/hardware/runs/2026-09-25-refs6743/console-run/console/`, used as an extra
`--goldens` root (layout in PR #261's docs/testing/xbox-refs6743-2026-09-25.md).

## Read first, then re-derive; the mechanism below is a CLAIM

The likely chain (vk/draw.c's own header comment, lines ~80-120, records it): the vertex sync
`sync_vertex_ram_buffer` (draw.c:6570) copies guest VRAM into the vertex buffer only for pages
whose DIRTY_MEMORY_NV2A bit is set, test-and-clearing as it goes, and "the only clearer is the
vertex sync". A GPU surface write reaches guest VRAM through the deferred/staged download in
vk/surface.c, and nothing in vk/*.c marks DIRTY_MEMORY_NV2A for that range (grep
`memory_region_set_client_dirty` in vk/: only blit.c does). So later renders are never seen by
the vertex fetch. Confirm each link before coding: (1) is the surface downloaded to
`d->vram_ptr` before the second draw at all, or is the vertex fetch reading stale memory
because the download is still deferred; (2) does the range's dirty bit get set; (3) is the
draw's `vertex_ram_buffer_syncs` entry skipped by the `all_uploaded && !dirty` early exit
(draw.c:6586-6598)? Name which link fails on DynamicUpdateLoop with a counter or log line.

## Territory

vk/draw.c is yours (released by lane.remote; #184 folded as PR #256). **vk/surface.c is
lane.remote's** (#109 Vulkan half): do NOT edit it. If the fix cannot be done from draw.c by
calling surface.c's existing entry points (flush deferred downloads overlapping a vertex
range, then mark the range dirty from draw.c), stop and post the exact one-line surface.c
change on #262; the board will arbitrate. Do not touch glsl/*.c, pgraph.c, vk/instance.c.
GL has the same shape (gl/vertex.c:67): note whether GL has the defect, do not fix it.

## The arm (register BEFORE building, after the last rebase)

- must_move: `Surface as vertex array::DynamicUpdateLoop` 96,000 -> 0 (against the console root).
- must_not_move: the other four Surface-as-vertex-array captures, and every suite whose draws
  use vertex RAM buffers over surfaces (`nv2a_index.py blast hw/xbox/nv2a/pgraph/vk/draw.c`).
  Flushing every deferred download per vertex sync costs frame time and could move
  timing-sensitive captures: bound the flush to ranges overlapping a live surface.
- The world in which it fails: DynamicUpdateLoop still reads red,red,red,red after the change.
Check `scores1.tsv` status for `unreadable` and `run1.log` for PARTIAL COVERAGE / UtilAcceptVsock
before believing a verdict.

## Done when

The failing link is named with evidence; either the fix folds green with the arm PASS, or
NOTES says which link needs a file you do not hold. PR ready (not draft), NOTES.md at
docs/lanes/vtxarr262/.
