# vtxstale1018 findings (#1049)

## 1. What changed

Each of the NUM_SUBMIT_FRAMES frame slots holds its own copy of guest vertex RAM, and only the current slot receives
uploads. A slot coming back into use was brought current at rotation (`pgraph_vk_finish()`) by one copy from the
lowest to the highest byte uploaded while it was out of use (`vertex_ram_stale_min/max`, 2dd232172c, #39).

Now each slot has a page bitmap (`vertex_ram_stale`, 1 bit per 4096-byte page, `r->bitmap_size` bits, the geometry of
`uploaded_bitmap`). `pgraph_vk_update_vertex_ram_buffer()` sets the pages of each upload in every other slot's bitmap;
the rotation copies each set run from the outgoing slot and clears it (`vk/vtxstale.h`). A slot rotated in for the
first time still takes the whole-buffer copy, and its bitmap is cleared. The flush range stays one span, over the
copied runs (the Nova's per-frame vertex RAM is coherent, so that flush is a no-op there).

The invariant is the one #39 needed: every slot other than the current one has its bitmap covering every page on
which it differs from the current slot. An upload keeps it (marks every other slot); a rotation keeps it (the incoming
slot becomes equal to the current one and is cleared; the third slot's differences are unchanged).

There is no switch. The old rule gives the same bytes in every slot and copies more, so there is nothing to select it for.

## 2. Test (selftest fragment 99-vtxstale-pages)

The fragment compiles vertex.c's mark loop and draw.c's rotation block, cut from the source, against `vtxstale.h` in
a host harness: 3 slots, 101 pages, an independent model of each slot's differing pages, a byte comparison of the
incoming slot at every rotation and an exact count of the bytes copied.

| | result |
|---|---|
| rotations (directed cases + 3000 random, active slots 2 and 3 alternating) | 3014 |
| rotations where the incoming slot differed from the current slot | 0 |
| rotations that copied other than exactly the stale pages | 0 |
| bytes copied, random part: by page / by the old span over the same writes | 118,468,608 / 891,623,514 |

Directed cases: one page, a write across two pages, the buffer's last bytes, an exact page, an empty write, writes far
apart, a write across a bitmap word, a rotation with nothing stale, a slot never made current until the ring grows.
Six mutants fail it (last page from the size alone; a copy that stops before the last page; no clear; the old span;
marks on the next slot only; no clear after the first whole copy).

## 3. Device: GTA III on foot (`gta-3` route, Nova, perflog `[dipwin]`)

Before: 1792340293-gta3instr1018-503029 (ref 25915ae59e, PurpleVK, 172 windows): `fen` 2.36 ms/flip, `stale` 2.19,
`rotfen` 0.04, about 30 MB/flip copied, 33.39 ms/flip (the on-foot 30 fps cap).

After: request 1792342997-vtxstale1018-1009067 (ref 54c0b3ee95 = this change on the before run's instrumented build).
Pending.

The parked in-car scene, where `Fen:` is 7.1 ms of a 37 ms frame, cannot be reached by a dispatched run: the route
grammar has no verb to load a save state. The on-foot number is the one shown here; this change makes no claim about
frame rate while driving.
