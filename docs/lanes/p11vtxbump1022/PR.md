# p11vtxbump1022: a vertex upload that would rewrite an earlier draw's bytes goes to a fresh staging offset, not a finish (#433)

State: draft

Lane: p11vtxbump1022            Issue: #433 (0.5)
Base: master @ b944110629
Files: docs/lanes/p11vtxbump1022/PR.md, hw/xbox/nv2a/pgraph/vk/{vertex.c,draw.c,renderer.h,buffer.c}
Prediction: GTA III in the car, perflog build, `HAKUX_VTXHZ_BUMP=1` against `=0` (`HAKUX_VTX_HAZARD` at its
  default, on): the `vtx_hazard` line's finishes fall to ~0 (110-155 per 10 s at `=0`) while its bumps are > 0;
  `fin_vtx` falls by 1.5 to 2 ms/flip (1.48 / 1.60 ms/flip in captures/fpsnext1019/runs/sys1-Base1 and sys1-Base2;
  PLAN.md's 2.05 from g3-dwcost.md); buffer-space finishes and `fin_buf` do not rise (10 / 9 per 2940 flips,
  0.17 / 0.14 ms/flip at `=0`).
  Falsified when the `vtx_hazard` finishes count is unchanged at `=1`, or when buffer-space finishes rise by about
  the count the hazard finishes fall
Needs device: yes. The A/B above on the Nova, then GTA SA with `=1`: the sky polygons and CJ's shadow as the
  gtasagpu1011 fix left them
Needs NDK: yes
Selftest: 99-dipwin-counters -- the one fragment that reads a touched file (vk/draw.c's perflog finish counters,
  beside the hunk in `pgraph_vk_finish()`). No fragment compiles vertex.c, buffer.c or renderer.h; cc_wt.py does

## Step 0: already tried

Sources: `git log -i -E --grep='vtxhz|VTX_HAZARD|vtxstale|vertex RAM|private copy'` on master, `git log --
hw/xbox/nv2a/pgraph/vk/vertex.c`, and a grep of `docs/lanes/*/` for `vtx_hazard`, `option (D)`, `private copy`
and `fresh offset`.

| Date | Commit / doc | What it did | Bears on P11 |
|---|---|---|---|
| 03-18 | 41be412ae0 | Render thread with one vertex RAM staging copy per submit frame; dropped upstream's finish on a re-uploaded page | The copies keep command buffers apart, not the draws in one. This is the gap the hazard finish closes |
| 09-10 | 2dd232172c | An upload reaches every frame of the ring (stale range on the receiving frame, #39) | The stale-range rule a fresh-offset copy must still feed |
| 10-11 | a6ee1c58fe, 328425904c, 6177c5b698, fold 597df4af82 (gtasagpu1011) | HAKUX_VTX_HAZARD: finish before an upload that changes bytes an earlier draw in the command buffer reads. Fixes GTA SA's sky polygons and CJ's shadow | The behaviour this change must keep. NOTES.md:335-336 names "option (D): give the rewritten range a private copy instead of a submit"; NOTES.md:392 says it was "not needed for cost". It was never built or refuted. P11 is option (D) |
| 10-11 | ccb2749973, fold 00fde8afb3 (defaulton1011) | HAKUX_VTX_HAZARD on by default | Default stays on; P11 changes what a hazard does, not whether it is detected |
| 10-12 | 67e3fcf745 (fpsbelow1012) | HAKUX_VTX_EXACT: sync only the draw's own bytes (off by default) | Orthogonal: it changes which bytes are uploaded, not where. The upload path's `vtx_exact_downloaded` handshake is kept ahead of the new code |
| 10-13 | d4d292c9ca (0.5.1 A7), 223f216d7c (#939) | Staging flushed before its copy; staging memory properties logged | A fresh-offset copy must be flushed too on a non-coherent heap (the Nova's is coherent, memprops 0xf) |
| 10-17 | ee677157bf (gta3drive1017) | The always-on `vtx_hazard` count line | The line this change extends; `gtasagpu1011/scrread.py` parses its prefix |
| 10-18 | ecd7396c72, 2173daadf2 (vtxstale1018) | Bring a frame's vertex RAM current by page, not by span (#1049) | Restaged as P6 (below); touches the same stale bookkeeping |
| 10-19 | d670bdc5b5 (fpsnext1019) | Scored vtxstale1018 (C2) on GTA III's driving scene: "third strike on CPU-savings-absorbed-by-GPU-wait" | A CPU saving that only moves the wait does not show in fps; P11 removes submits, not CPU time |
| 10-22 | 1585bed984 (p6vtxstale1022) | P6 staged on master b944110629 | Not merged; composition below |

Coordinator check: `git log --oneline 72af9cb92c..b944110629 -- vk/vertex.c vk/draw.c` is empty, so master still
finishes on a hazard. Newest figures: captures/fpsnext1019/runs/sys1-Base1 and sys1-Base2 (GTA III, 10-19, apk
326bfebadb-perflog): in-car `fin_vtx` 1.48 / 1.60 ms/flip, `fin_buf` 0.17 / 0.14, 110-155 hazard finishes per
10 s, and 1103 / 978 vertex finishes against 10 / 9 buffer-space finishes over 2940 flips.

Nothing in the table built a per-frame copy at a fresh offset, so there is no earlier result to repeat or avoid.

## 1. Mechanism

Today, with HAKUX_VTX_HAZARD on (the default), `pgraph_vk_bind_vertex_attributes()` notes the guest bytes each
draw's vertex-RAM attributes read, and `pgraph_vk_vtxhz_commit()` folds them into `vtxhz_read` for the open
command buffer. An upload into the frame's vertex RAM copy whose bytes differ from the copy inside one of those
ranges (`vtxhz_overwrites()`, byte exact) first calls `pgraph_vk_finish(VK_FINISH_REASON_VERTEX_BUFFER_DIRTY)`:
the recorded draws are submitted and waited, and only then is the copy rewritten. That is GTA III's `fin_vtx`.

With `HAKUX_VTXHZ_BUMP=N`, each frame's `frame_staging[f].vertex_ram` (already one per submit frame,
host-visible, persistently mapped, VERTEX_BUFFER usage) is allocated N MB longer (`1` = 8 MB; N > 1 = N MB, at
most 256). When the same test fires, the upload is copied to the next free offset past vertex RAM's bytes
instead, 256-aligned plus the guest address's low 8 bits (so attribute alignment and
`remap_unaligned_attributes`' view of it stay the guest's), and an entry `{guest lo, guest hi, offset}` is
appended. The identity copy is not written, so every draw already recorded reads what it was recorded against.
Draws set up after the upload bind the entry: offset `entry.off - entry.lo + identity offset`.

The entries belong to one rotation of one frame and are append-only. An upload that overlaps an entry bumps too,
whether or not the hazard test fires, so the newest entry holding a byte is that byte's newest copy and, outside
the entries, the identity copy is. Lookups scan newest first.

The entries are folded back (`vtxhz_bump_resolve()`) on the first touch after `frame_rotations` moves, or at an
upload when the draw and reorder queues are empty and no command buffer is open: oldest first, each entry's bytes
are copied into the current frame's identity copy, its flush range widened, and the other frames marked stale
for them, as an upload to the identity copy would; then the set is emptied and the region reused from 0.

Out of room, entries overlapping the upload are trimmed (so none answers for bytes the identity copy is about to
take), `no room` is counted, and the upload takes today's path: the hazard test and, if it fires, today's finish.
PLAN.md has the NEED_BUFFER_SPACE finish here. That finish is unconditional, so it would finish on every
out-of-room upload, also those the hazard test lets through; today's path is never worse than master, and its
finishes stay under `vtx`, so the falsifier's buffer-space count reads only what the change causes.

`HAKUX_VTXHZ_BUMP=0` or unset (the default) runs none of this: `vtxhz_bump_cap` is 0, the buffer is its old size,
`bump` stays -1 so the finish's condition is today's, and every draw.c hook is behind `vtxhz_bump_n` (always 0)
or `vtxhz_bump_cap`. The `=0` arm differs from master only in the text of the `vtx_hazard` line (fields appended
after the prefix scrread.py reads) and one increment per NEED_BUFFER_SPACE finish. With HAKUX_VTX_HAZARD=0 the
switch is inert and its init line says so: without the read ranges there is no test to decide a bump.

## 2. How recorded draws reference staging, and why the remap is complete

A draw reads vertex RAM through `vkCmdBindVertexBuffers` on the current frame's `vertex_ram` buffer at
`vertex_attribute_offsets[attr]`. The buffer and offset are fixed at record time and the bytes are read at
execute time; that is why rewriting the identity copy under an open command buffer is the hazard. There are two
places a draw takes those offsets: `bind_vertex_buffer()` (direct recording) and `snapshot_vertex_buffers()` (a
reorder-window entry, replayed later from its snapshot). Attributes that need conversion go to the inline buffer
from guest memory (`copy_remapped_attributes_to_inline_buffer()` reads `d->vram_ptr`), not from this copy, and
both remap sites leave `BUFFER_VERTEX_INLINE` alone. `RCMD_VERTEX_RAM_UPDATE` has no producer in the tree.

Both sites map a vertex-RAM attribute through `pgraph_vk_vtxhz_bump_offset()` while entries exist. It finds the
newest entry overlapping the attribute's read range (`vtxhz_attr_lo/hi`, set at the two `vtxhz_note_attr()`
calls in `pgraph_vk_bind_vertex_attributes()`); an entry that contains the range gives its offset, no overlap
gives the identity offset. Completeness is that a found entry always contains the range:

- The read range is inside the draw's sync range (`update_memory_buffer(start, n * stride)` beside each note),
  and the sync range is inside the merged range `sync_vertex_ram_buffer()` uploads.
- Before a draw binds, it either runs `sync_vertex_ram_buffer()` or takes the `OPT_SYNC_RANGE_SKIP` skip, which
  needs `!has_dirty_vertex_pages()`; the sync's own early exit needs the same. Both now count a sync range as
  dirty when an entry overlaps it without containing it (`pgraph_vk_vtxhz_bump_needs_copy()`), so the range is
  uploaded again; that upload overlaps an entry, so it bumps, and becomes the newest entry, containing the whole
  merged range.
- So the newest overlapping entry contains the sync range and with it the read range. If no entry overlaps, the
  identity copy is newest for those bytes.

The one way out is an element larger than its stride, where the read range passes the sync range; the lookup
then binds the identity copy and counts it as `partial` on the `vtx_hazard` line rather than silently.

An entry's bytes are never written again, so an offset taken at record or snapshot time stays valid until the
region is reused. It is reused only from `vtxhz_bump_resolve()`: after a rotation (the reorder window is flushed
at the top of `pgraph_vk_finish()`, and the new current frame's previous submission was waited before it became
current; the next bumps go to that frame's region), or when both queues are empty and no command buffer is open
(the render thread's finish waited its fence). Resolve is lazy but always ahead of the frame's first bind: both
bind sites, `has_dirty_vertex_pages()` and the sync's merged loop call into it while entries exist. The fresh
copies are flushed with the identity copy's range in `flush_memory_buffer()` before the submit, from the entries'
own frame, with a HOST to VERTEX_INPUT barrier.

## 3. Why the gtasagpu1011 fix holds

The defect was GTA SA rewriting vertex bytes between draws of one command buffer: draws recorded before the
rewrite read the new bytes when they executed (the sky polygons, CJ's shadow). The finish fixed it by ordering:
the earlier draws ran before the bytes changed. The bump fixes it by place. The detection is unchanged: the same
`vtxhz_overwrites()` against the same identity copy, under the same empty-queue condition. When it fires, the
identity copy keeps the bytes the earlier draws read until they have executed (a waited fence, or nothing left
recorded), and the later draws bind a copy holding exactly the uploaded bytes. Each draw reads the bytes that were
current when it was recorded, which is the property the finish gave. Out of room, the path is today's finish. The
GTA SA check with `=1` on the device is the confirmation.

## 4. Composition with lane/p6vtxstale1022

Not based on it, nothing taken from it. `git merge-tree --write-tree --name-only` of this branch's tree (on
b944110629) and lane/p6vtxstale1022 (1585bed984): exit 0, no textual conflict. buffer.c's hunks are adjacent
(p6 drops the `vertex_ram_stale_min/max` initialisers at :487-488, this changes `.buffer_size` at :483) and merge
clean.

One semantic conflict, in one function: `vtxhz_mark_stale()` (vertex.c:265-279) writes `vertex_ram_stale_min/max`,
which p6 replaces with a page bitmap per frame (`vertex_ram_stale`, vk/vtxstale.h). The merge fails to compile
there, loudly:

```
vertex.c:273:25: error: 'FrameStagingState' has no member named 'vertex_ram_stale_min'; did you mean 'vertex_ram_stale'?
```

(and three more at :274, :276, :277). Whichever branch lands second takes the one-line edit, the loop body becoming
`vtxstale_mark(other->vertex_ram_stale, lo, hi - lo);`. With it, vertex.c, draw.c and buffer.c of the merged tree
compile with perflog 1 and 0, and p6's `99-vtxstale-pages` passes 14 / 0 on it.

p6's fragment cuts vertex.c's marking loop between `QEMU_BUILD_BUG_ON(TARGET_PAGE_SIZE != VTXSTALE_PAGE_SIZE);`
and the line `bitmap_set(get_uploaded_bitmap(r), start_bit, nbits);`, which must occur once. A bumped upload
marks its pages inside `vtxhz_bump_upload()`, from its own bounds, so the line stays single; with a second copy
in the bump's early return the fragment failed 8 of 14 checks on the merge.

The two compose in meaning: bump entries are guest ranges inside vertex RAM, so p6's page marks cover them; the
region past vertex RAM has no bits in the stale bitmap (`bitmap_size` counts vertex RAM's pages), so p6's
rotation copy never copies it; and resolve marks the other frames through the same call the upload path uses.

## 5. The change

- vk/vertex.c:91-123: the switch, `vtxhz_bump_env()`, read once; `HAKUX_VTXHZ_BUMP` beside `vtxhz_env()`.
- vk/vertex.c:134: `vtxhz_note_attr()`, the per-attribute read range, called at :705 (cached layout) and :833.
- vk/vertex.c:212: `vtxhz_log()`, the `vtx_hazard` line (Android, at most every 10 s):
  `vtx_hazard: F finishes, D since the last line; B bumps (K kB), R no room, P partial; S buffer-space finishes`.
- vk/vertex.c:238: `pgraph_vk_vtxhz_bump_init()`, sizes the region and logs
  `HAKUX_VTXHZ_BUMP=<raw> (<MB> MB a frame for an upload that would rewrite an earlier draw's vertices, instead of
  a finish)` plus ` (off)` or ` (inert: HAKUX_VTX_HAZARD=0)`.
- vk/vertex.c:265 `vtxhz_mark_stale()`, :286 `vtxhz_bump_resolve()`, :311 `vtxhz_bump_sync()`, :319
  `vtxhz_bump_find()`, :337 `vtxhz_bump_trim()`, :377 `vtxhz_bump_upload()` (1 bumped, 0 identity, -1 no room).
- vk/vertex.c:443 `pgraph_vk_vtxhz_bump_offset()`, :465 `pgraph_vk_vtxhz_bump_needs_copy()`, :477
  `pgraph_vk_vtxhz_bump_flush()`.
- vk/vertex.c:520-529: the hook in `pgraph_vk_update_vertex_ram_buffer()`; :533 the finish now also needs
  `bump < 0`, and logs through `vtxhz_log()`.
- vk/draw.c:4314-4318 `flush_memory_buffer()`: the fresh copies' flush and barrier.
- vk/draw.c:5689-5693 `pgraph_vk_finish()`: `vtxhz_buf_finishes++` on NEED_BUFFER_SPACE.
- vk/draw.c:8790-8794 `snapshot_vertex_buffers()` and :10939-10942 `bind_vertex_buffer()`: the remap.
- vk/draw.c:9139-9151 `has_dirty_vertex_pages()` and :10233-10235 `sync_vertex_ram_buffer()`'s merged loop: a
  range no one copy holds is dirty.
- vk/renderer.h:1436-1454: the entries, region bounds, attribute ranges and counters (`vtxhz_bumps`,
  `vtxhz_bump_bytes` printed as kB, `vtxhz_bump_full` as `no room`, `vtxhz_bump_partial`, `vtxhz_buf_finishes`);
  :1855-1860 the four prototypes.
- vk/buffer.c:444-446 and :483: the region's size, added to each frame's `vertex_ram` (0 when off).

The counters follow `vtxhz_finishes`: always counted, printed on the always-on `vtx_hazard` line, nothing under
`NV2A_PERF_LOG`; `fin_vtx` / `fin_buf` are the perflog build's existing finish timings.

## 6. Checks

cc_wt.py (desktop build flags, worktree headers), each touched C file with `-DNV2A_PERF_LOG=1` and `=0`:

```
vertex.c perflog=1 EXIT=0  perflog=0 EXIT=0   0 errors, 0 warnings in vertex.c
draw.c   perflog=1 EXIT=0  perflog=0 EXIT=0   0 errors, 16 warnings: master's 16 (:1434-1528, :5929, :7994 there)
buffer.c perflog=1 EXIT=0  perflog=0 EXIT=0   0 errors, 6 warnings: master's 6 (:28, :33, :57, :159, :366)
```

renderer.h is compiled by all three. The Android-only log calls do not build on the desktop, so vertex.c was
also compiled with `-D__ANDROID__`, `-Wformat=2` and a stub `android/log.h` that declares `__android_log_print`
with `format(printf, 3, 4)` (a `#warning` in the stub proves it was the one included): perflog 1 and 0 EXIT=0, no
vertex.c warnings, so both new format strings match their arguments.

Merge with lane/p6vtxstale1022, as in section 4: merge-tree exit 0; the merged vertex.c fails with the four
errors quoted; after the one-line edit, vertex.c, draw.c and buffer.c EXIT=0 with perflog 1 and 0, and
`SELFTEST_ONLY=99-vtxstale-pages` on the merged tree:

```
selftest: 14 passed, 0 failed, PARTIAL: 1 of 161 fragments
```

Selftest on this branch, `SELFTEST_ONLY` with the `Selftest:` line's fragment plus the seven that mention staging,
vertex RAM or the hazard line by name:

```
99-dipwin-counters 13 ok; 62-routerefs-soakvideo1011, 64-status-html, 90-fold-index, 98-dispatch-doctor,
99-dev-push-ro-disc, 99-dev-push-wslpath, 99-pilot-gate the rest
selftest: 212 passed, 0 failed, PARTIAL: 8 of 160 fragments
```

Not run: the full selftest, an NDK build, a desktop link, any device.

## 7. Risks

- Not built with the NDK, not run anywhere. The A/B is the first execution of the new path.
- Hazards are still unchecked while the draw or reorder queue holds draws, as on master: the test and the bump
  both need empty queues, except that an upload overlapping an entry always bumps.
- An element larger than its stride binds the identity copy for that attribute (`partial`); a non-zero `partial`
  on the device is a draw that can read old bytes.
- Overlap chains: once a range is bumped, every later upload touching it bumps until the next resolve, so `kB`
  can be well above the hazard bytes, and 8 MB can run out (`no room`, then today's finish). `=N` sizes it.
- Resolve copies each bumped byte a second time, into the identity copy, on the CPU.
- The first rotation onto a frame that was never initialised copies its whole buffer, now 8 MB longer at `=1`.
- The submit-frame-count change at the top of `pgraph_vk_finish()` resets `current_frame` and bumps
  `frame_rotations` while a command buffer can be open; the flush uses the entries' own frame, but a resolve into
  frame 0 while frame 0's command buffer is still open would rewrite bytes it reads. The path runs only when the
  frame count changes.
- Host memory: +8 MB per submit frame at `=1` (+24 MB with three frames). The entry array is never freed.
- Non-coherent memory: the flush of the fresh copies is untested (the Nova's staging is coherent, memprops 0xf).
- The `vtx_hazard` line's text changes in both arms; `scrread.py` reads only its `vtx_hazard: N finishes` prefix,
  which is kept. At `=1`, "0 finishes" is the expected reading and needs `bumps` > 0 beside it to mean anything.
- The falsifier's mechanism: without the hazard finishes a command buffer lives longer and can fill the index,
  inline or uniform staging, moving the finish to NEED_BUFFER_SPACE.
