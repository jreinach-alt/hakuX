# lane.blinx372e -- #372: Blinx demo zeta flip, small to big only

Base origin/master e5db66fa37 (PR #396 folded). One source file:
`hw/xbox/nv2a/pgraph/vk/surface.c`. PR #467. Predecessor: lane.blinx372d
(`docs/lanes/blinx372d/NOTES.md`, sec 1, 3 and 5).

| commit | what |
|---|---|
| eedeeb3a81 | The quadrant copy, its guard and the `[quad372]` counter (sec 1, 2). |
| d979c58234 | Merge of `lane/doa413b` (PR #440, not folded) as the brief asks. One conflict, at `pgraph_vk_surface_update`'s completion: #440's env-gated lazy completion is kept, and the arm runs after it. |
| c5dc70c577 | Row-fit guard: a binding whose row is wider than its pitch is declined (sec 2). |
| 489394939f | Review fixes: the watch is handed over at the flip with no unwatched moment, and the guard gets a hash with no blind bits (sec 1). |
| f03876f0df | Both predictions registered (sec 4). |

## 1. The CPU-write gap: closed by a hash, and counted

The brief's gap: the old path re-uploads the large binding P from VRAM on
the flip back, so a guest write to P's range while P sat on the shelf is
picked up. A GPU copy of the corner into P's kept image does not read VRAM.
It is only right if P's image still equals an upload of that memory outside
the corner. `vram_newer` covers downloads recorded over a shelved binding. It
does not cover a guest CPU write, a PGRAPH blit or anything else that writes
VRAM directly.

Two things came out of reading the code:

- **In the demo, the large binding does not shed its watch on the shelf.** It
  is evicted draw-dirty, and `shelve_surface` runs before its deferred
  download lands. `unregister_cpu_access_callback_if_clean` therefore keeps
  the watch, and nothing drops it when the download lands. So a guest store to
  P's range while it is shelved traps into `surface_access_callback`'s shelved
  loop. The "clean shelved binding sheds its watch" gap applies to bindings
  that were clean when shelved, and the demo's P is not one of them.
- **The watch sees only the guest's CPU,** so the guard does not rest on it.
  The guard hashes VRAM over P's range (`surface_watch_hash`, surfwatch382's
  hash) right after P's own eviction download lands. That is in the same
  `surface_update` that shelved P, before the small binding's upload reads the
  memory. The guard hashes the range again at the small-to-big flip. Any
  writer changes the hash, and the flip then takes the old path. This is
  "gate the result, not the input".

`[quad372] copies= arms= cpu_writes= vram_changed=` prints every 5 s beside
`[evict372]`. These counters are cumulative since boot:
- `arms`: P's download landed and was hashed.
- `cpu_writes`: shelf periods in which the watch saw a guest store to the
  armed P. Each one disarms the guard.
- `vram_changed`: flips where the hash differed. Each one takes the old path.

**The flip itself hands the watch over with no gap (489394939f).** Both
the watch insert and its removal are queued to the vCPU as safe work, in
FIFO order. The first version removed the shelf watches of P and X before
`surface_put` queued P's new insert. That left a moment in which nothing
watched the range. Master has the same moment at every unshelve. It
mattered more here, because after the copy VRAM's corner is *older* than
P's image until P's download: a guest read in that moment would get stale
depth, where the old path had already downloaded X. The partner now must
still hold its shelf watch. That watch and X's are detached
(`surface_watch_detach`) and their removal is queued after `surface_put`
(`surface_watch_retire`), so some watch is always up. Every watch runs
`surface_access_callback`, which finds P by range. An independent review
found this; its second finding is below.

**The guard hash is its own (`surface_quad_hash`).** surfwatch382's
`surface_watch_hash` multiplies without rotating. A multiply carries a
word's top bit only into the product's top bit, and the final shifts drop
that bit. So a change confined to bit 63 of some words (a D24S8 pixel's
depth MSB) hashes the same. The guard's hash rotates by 29 at each step and
combines the four lanes with rotations. surfwatch382's hash has the same
blind spot for its gap check. That is left alone here, because it is outside
this brief.

**Measurement (B, `1-1790483698-blinx372e-3616042`, window 135-265 s):**
`arms=1282 copies=1282 cpu_writes=0 vram_changed=0 lost_writes=0`. In the
demo the guard armed at every big-to-small flip, and every small-to-big flip
copied. No guest CPU store reached the shelved large binding's range, and its
memory hash never changed. The gap exists in the code but does not occur in
the demo. Its guard costs two hashes of 1.2 MB per frame (sec 3).

## 2. The hunk

`update_surface_part`, incompatible branch, after `surface_handoff_partner`
declines. `surface_quad_partner` accepts only when all of these hold:
- the held binding X and the target are linear D24S8 zeta with 4-byte guest
  pixels, at surface scale 1, with TCG;
- they have the same format, pitch and bpp, and X is smaller in width or
  height, never larger;
- **each row fits in its pitch** (c5dc70c577);
- X is draw-dirty with no pending upload or download, it is not the display
  pre-download surface, and `mem_dirty` is clear;
- the shelved partner (`get_shelved_surface`'s first match) is the armed
  binding at the same draw generation, clean, and not `vram_newer`;
- no other active binding, and no dirty shelved binding at another address,
  overlaps the range;
- the hash matches.

`surface_quad_record` flushes the queued draws, then records X -> TRANSFER_SRC
and P -> TRANSFER_DST, then `vkCmdCopyImage` of X's extent (depth and stencil
aspects) to P at offset (0,0), then puts X back and P into
DEPTH_STENCIL_ATTACHMENT_OPTIMAL. It uses the handoff's global barriers.

The bookkeeping is #396's handoff exactly. P gets `upload_pending = false`,
and after `surface_put` a `draw_generation++` and
`pgraph_vk_surface_watch_mark_dirty`, so it owes the download with its watch
live. X is shelved clean, with `vram_newer` set and its watch dropped. On the
next big-to-small flip P is evicted draw-dirty and downloaded (the one wait
left), which puts X's pixels and P's own into VRAM. X comes back off the
shelf stale and re-uploads, as before.

**Why rows must fit (found by the must-not-move search, sec 4).**
`3D_primitive`'s `-ls`/`-ps` tests bind the default zeta at 640x480 and
then, under AA x2, at 1280x480, at one address and pitch 2560. That is
small-to-big, same format and same pitch, so the first version accepted it.
But a 1280-pixel D24S8 row is 5120 bytes over a 2560 pitch, so P's rows
overlap in VRAM. P's download is then not invertible, and an upload of the
memory is not P's image even when the memory is unchanged. The old path's
P' has X's rows folded into its right half. The copy would have kept P's own
pixels there.

Big to small stays on the old path (blinx372d sec 5). The evicted large
binding would still owe three quarters of its area from the shelf, and the
watch does not answer a read of a shelved binding.

## 3. Price (offline; a bound, not a value)

It removes one of the two synchronous finishes per demo frame (the
small-to-big one), X's download memcpy, P's full 1.2 MB upload and unpack,
and their buffer copies. It adds one 320x240 D24S8 image copy on the GPU and
two CPU hashes of 1.2 MB per frame. The hash cost is an analytic 0.1 to
0.6 ms: 4 independent multiply chains over 32-byte strides, memory-bound. It
is not measured, because this session cannot run a compiled binary.

From blinx372c/d's soaks, A's waits are Sub 25.6 to 35.2 ms of Tot 56.6 to
71.1 ms. Removing one of the two waits takes off at most about half of Sub,
which gives Tot 44 to 55 ms: 18 to 23 fps by Tot, and about 15 to 19 fps by
gfps at the 0.83 gfps/Tot factor blinx372d saw. That is a ceiling. The
remaining big-to-small wait may absorb the GPU work the removed wait used to
drain (GPU 31 to 46 ms), and then B stays near A.

## 4. Arms

Both predictions were registered at 2026-09-27T04:34Z, after the last merge
and before any run. Both use A = 988e51328e (lane/doa413b's head: master's
`hw/` plus #440, lazy completion off) and B = 489394939f (this lane).
`git diff 988e51328e 489394939f -- hw/` is this hunk and nothing else. The 6
master commits A lacks do not touch `hw/`.

- `docs/testing/predictions/blinx372e-demo-ab.json`: the same-session Thor
  soak A/B, 240 s, perflog, frames every 30 s. It is judged by `abquad.py`
  over 135-265 s. Queued by this lane:
  - A `1790483694-blinx372e-3615063`
  - B `1790483698-blinx372e-3616042`
- `docs/testing/predictions/blinx372e-mnm.json`: must-not-move, byte identity
  over Surface_clip, 3D_primitive, Depth_buffer_fixed_function,
  Color_zeta_overlap, Surface_format, Texture_CPU_Update and
  Texture_render_update_in_place. The arms job queues it.

The must-not-move set is from a search of the nxdk sources
(`fold-pins/nxdk_pgraph_tests`, tests 6743b6a). Zeta at two sizes at one
address inside a test:
- `Surface_clip/rt_*` (seven tests) go small -> 640x480.
  `rt_x320y240_w320h240` is Blinx's exact 320x240 -> 640x480 pair. All 47
  Surface_clip rows are ok and exact on current code.
- `XemuBug420` and `DebugTextShouldClip` go large -> small.
- `3D_primitive/*-ls|-ps` go 640x480 -> 1280x480 under AA x2 at pitch 2560.
  These are the rows the row-fit guard declines. 52 of the 120 read
  white-content (unreadable) on current code.
- `Color_zeta_overlap/AdjacentWithClipOffset_*` go 128 -> 126 at pitch 512,
  in texture memory.

### Results (judged 2026-09-27)

**Demo A/B: FAIL as registered, on P3 only.** A `1790483694-blinx372e-3615063`
and B `1-1790483698-blinx372e-3616042` both ran on the Thor, judged by
`abquad.py` over 135-265 s.

| | A (988e51328e) | B (489394939f) |
|---|---|---|
| gfps | 11.87 | 12.06 |
| sd/frame | 1.90 | 0.975 |
| sd per flip | 0.989 | 0.502 |
| quad copies / small-to-big flips | - | 1282 / 1282 |
| Tot ms median | 61.6 | 64.9 |
| GPU ms median | 35.6 | 40.1 |
| Sub ms median | 28.6 | 31.8 |

M0, M1, P0, P1 and P2 pass. P3 fails: B/A = 1.016 (at least 1.10 was
registered), and B is at 12.06 fps (13.5 to 20 was registered). 1.016 is the
blinx372c no-change spread exactly.

The mechanism works: one of the two synchronous downloads per flip is gone,
on every flip. The frame did not get faster. Sub **rose** by 3.2 ms and GPU
by 4.5 ms. This is sec 3's named rival world. The remaining big-to-small
`pgraph_vk_finish` now waits for all the GPU work the removed wait used to
drain. So the frame is bound by GPU work behind one synchronous point, not
by the number of synchronous points. Taking out one wait of two does not
halve the waiting when the GPU queue is the long pole. The 1.2 MB CPU hashes
(sec 3) may account for part of the Tot rise. They are not separated here.

B's frames at 150-240 s show no depth corruption in the top-left quarter
(f00006 looked at by eye).

**Must-not-move: PASS, 309/309, but inert for the copy.** The arms job's
verdict is on PR #467 (base `1-1790483754-arms-blinx372e-base-3630491`, fix
`1-1790483755-arms-blinx372e-fix-3630543`). B's logcat ends
`[quad372] copies=0 arms=4 cpu_writes=0 vram_changed=0`. The guard armed 4
times and never copied, and `[evict372] handoffs=2` held in both arms. The
arm shows that the hunk leaves those 309 captures alone. It does **not** show
that the copy draws correctly, because no nxdk test took the copy.
`Surface_clip/rt_x320y240_w320h240` did not copy. Why it declined was not
read; a lane that takes this hunk further must find out first.

**Outcome.** Per the brief, the result is not re-fit and the PR is not marked
ready. The hunk removes half the synchronous downloads with no fps gain, and
only the demo's frames exercise its correctness. That does not justify landing
it. The branch stays open as the measured record. master was merged at the
end (#440 folded), and `hw/` in the diff is this hunk alone.

### Why attempt 1 did not finish

Attempt 1 ended correctly in `waiting:`, on the two Thor soaks (then about
five requests deep in the queue), the must-not-move arms verdict and CI.
handback resumed it once all three had landed. Nothing was lost.

### Waiting (2026-09-26 21:40 PDT, resolved 2026-09-27)

Waiting on the two soaks above (about five requests were ahead of them), on
the arms job's `[job.arms]` verdict for `blinx372e-mnm.json`, and on CI for
f03876f0df. On resume:
1. `python3 docs/lanes/blinx372e/abquad.py <A>/logcat.txt <B>/logcat.txt
   --window 135,265 --spec-a <A>/result.json --spec-b <B>/result.json
   --prediction docs/testing/predictions/blinx372e-demo-ab.json`. Look at
   B's frames at 150-240 s by eye for depth garbage in the top-left quarter.
2. Must-not-move: check B's `[quad372] copies=` > 0 (otherwise the arm is
   inert) and `[evict372] handoffs=` > 0, and read white-content rows as
   unreadable.
3. If #440 has folded by then, merge master (no rebase). If the merge
   changes `hw/`, re-register on the new refs and re-run. Then fill in sec
   1's measurement and mark the PR ready.

## Tools

- `abquad.py`: the A/B judge. It imports `blinx372d/abread.py`, which reads
  the stall line, time zero and gfps the way `blinx372c/stallread.py` does.
  It adds `[quad372]`, `lost_writes` and **sd per flip**. `sd/frame` counts
  per display frame, so a faster B would move it with the frame rate; sd per
  flip does not. `--selftest` passes. A dry run on blinx372d's B soak
  (`-2481219`, same path as master) reads 866 flips each way, all of the
  dirty evictions, and 1.02 sd per flip.

## Do not repeat

- Do not treat "same format, same pitch, smaller" as enough for a corner copy.
  An AA binding's row can be wider than its pitch (sec 2).
- Do not assume a shelved binding has no watch. One shelved draw-dirty keeps
  its watch until it is unshelved or freed.
- Do not judge this change on sd/frame. Use sd per flip (Tools).
- Do not remove a watch and then register its replacement when the range
  holds pixels newer than VRAM. Both are queued to the vCPU, so queue the
  insert first (sec 1).
- Do not expect fewer synchronous finishes to mean more fps on Blinx. Halving
  them (sd per flip 0.99 to 0.50) moved gfps 11.87 to 12.06, and Sub rose.
  The remaining wait absorbs the GPU work. The next lever is the GPU work
  per frame (GPU 36-40 ms), or removing the last wait entirely, not the
  wait count.
- Do not count the must-not-move arm as coverage for the copy: it made 0.
- Do not use `surface_watch_hash` as a guard on depth data. It cannot see
  bit 63 of some words (sec 1).
