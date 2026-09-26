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

## Attempt 2 (resumed 2026-09-25 20:32Z)

**Why attempt 1 did not finish:** it ended correctly, waiting on the device arm, with
the PR in draft. The handback job resumed it once CI went green on `1c1c666bad`.

**What the first pair measured.** Both arms finished on the Nova (apks `851650a27937`
and `cf2d5d9d29d4`), 72 captures each, 0 `unreadable`, no PARTIAL COVERAGE or
UtilAcceptVsock in `run1.log`. `ab_compare.py --expect` returns **PASS, 73/73 machine
legs**, and all 72 captures are byte-identical between the arms. So the must_not_move
set held.

**The must-move leg was not measured.** Neither arm contains any `Surface_as_vertex_array`
capture. The suite is not on the stock dispatcher disc. The progress log runs the
other six suites and ends "Testing completed normally" without mentioning it. The
refs6743 dry run captured the suite only because it passed
`--base-iso .../2026-09-25-refs6743/refs6743.iso` (the pristine 6743b6a XBE).
Next lane: **a suite without a published golden is probably not on the stock disc
either.** Give request.sh that suite's `--base-iso`, and check the progress log for
the suite name before you trust an arm.

**Re-queued, the must-move leg only** (Thor, refs6743 disc, `--no-expect` naming the
registered prediction, which already says this leg is hand-scored):
base `1790368380-vtxarr262-base-iso-1676913` (342d21c43f), fix
`1790368384-vtxarr262-fix-iso-1679009` (74ac01608d). On resume:
`score_sweep.py --goldens ~/hakux-work/hardware/runs/2026-09-25-refs6743/console-run/console`
over both runs' `captures1`. Expect base DynamicUpdateLoop 96,000 and fix 0. The other
four should stay as they are (RenderScalePattern 18,136 at delta 1). Check that
`Surface_as_vertex_array::*` files exist in both before scoring.

## Attempt 2, second resume (2026-09-25 22:40Z)

**Why the previous session did not finish:** it ended correctly, waiting on the
refs6743-disc arm pair, with the PR in draft. After that, master moved 109 commits
ahead and `docs/testing/nv2a_index.json` conflicted. GitHub builds the merge commit,
so `0247449198` got no CI run at all. That was the "CI: NONE" the handback reported.

**Done this session.** Merged `origin/master` @ 90a8dc1c1a. This was a merge, not a
rebase, so the prediction's refs are still ancestors. The only conflict was the
generated index. I took master's copy and rebuilt it with `nv2a_index.py build` over
`fold-pins/` (tests_commit 6743b6a, which matches provenance). `check` passes.

**Still waiting.** The pair `1790368380-vtxarr262-base-iso-1676913` /
`1790368384-vtxarr262-fix-iso-1679009` is still in `dispatch/queue`. The dispatcher
is not jammed: a 100-suite `0-a-now-*`/`0-b-*` priority sweep is running ahead of it,
finishing a suite every 1-2 minutes. The PR stays draft until the must-move leg
(DynamicUpdateLoop 96,000 -> 0) is hand-scored. That leg is the only evidence the fix
does anything, and the machine legs only show it is inert elsewhere.

## Attempt 2, third resume (2026-09-26 02:10Z): the must-move leg, measured

**Why the previous session did not finish:** it ended correctly, still waiting on
the refs6743-disc pair, which was queued behind a 100-suite priority sweep. Both
runs have finished since then. Master moved again and `nv2a_index.json` conflicted
a second time.

**Result.** Both runs are in `dispatch/results/`, with apks `851650a27937` (base,
342d21c43f) and `cf2d5d9d29d4` (fix, 74ac01608d). Each has all 5
`Surface_as_vertex_array::*` captures, no `unreadable`, and no PARTIAL COVERAGE or
UtilAcceptVsock in `run1.log`. Their `ERROR` file ("produced 0 captures") and
"no golden to compare: 5" come from the stock goldens root having no copy of this
suite. They are not missing captures. Hand-scored with
`docs/lanes/vtxarr262/score_console.py` against the console root:

| test | base px (maxd) | fix px (maxd) | base vs fix |
|---|---|---|---|
| DynamicUpdateLoop | 96,000 (255) | **0** | differ |
| LinearDiffuseArray | 0 | 0 | identical |
| MultiStream | 0 | 0 | identical |
| RenderScalePattern | 18,136 (1) | 18,136 (1) | identical |
| SwizzledDiffuseArray | 0 | 0 | identical |

Colours in DynamicUpdateLoop: the base arm has red over 128,000 px (four red quads).
The fix arm has red, green, blue and yellow at 32,000 px each, which matches the
console histogram exactly. So the must-move leg PASSES. The first pair's machine
legs had already passed 73/73 byte-identical.

Merged `origin/master` again, with the same index resolution as before: master's
copy, rebuilt over `fold-pins/` (6743b6a). `check --tests --support` matches.
