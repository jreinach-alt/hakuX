# lane.dirtytlb (#548)

Who calls `tlb_reset_dirty` off the vCPU thread, per flip, and what each
caller costs. #461 pair 1 (Crimson, Thor, master `f131dd11`) read ~175 such
walks per flip at ~27 us each, 4.7 ms per flip, with the texture path at most
41% of them.

## What the code says, before any run

- `tlb_reset_dirty()` has one caller, `tlb_reset_dirty_range_all()`
  (system/physmem.c), whose only caller is `physical_memory_dirty_bits_cleared()`.
  So one door, and every caller can be tagged there.
- Render-thread callers on the Vulkan backend:
  - **vertex RAM sync**, `pgraph/vk/draw.c` (~6961): calls
    `physical_memory_dirty_bits_cleared()` directly, once per dirty merged
    range, per draw.
  - **`check_texture_dirty()`**, `pgraph/vk/texture.c` (~636):
    `memory_region_test_and_clear_dirty(..., DIRTY_MEMORY_NV2A_TEX)`, which
    walks only when a bit was set.
  - The **surface check** (`pgraph/vk/surface.c` ~4377) clears NV2A bits only
    under `!tcg_enabled()`, so it never walks. Of lane.remote's two
    candidates, only the vertex sync is live.
- **A tail-page gap, upstream's too.** `tlb_reset_dirty_range_all()` rounds
  `start` down to a page and passes the caller's `length` unchanged, and
  `tlb_reset_dirty_range_locked()` tests each entry's page start against
  `[start, start + length)`. A range that starts mid-page and ends in the next
  page within the same offset walks one page short: that page's writable TLB
  entry survives while its bits read clean, so guest stores through it set no
  dirty bit. Texture ranges are page-aligned by `check_texture_dirty()`, so
  the exposure is the unaligned vertex ranges (whose own bitmap loop also
  stops a page short). Counted as `tm` on physmem's sites; not changed.

## The counter (commits c911c012db .. 111c7fea74)

`[rdc]` on hakuX-perf, one line per 60+ flips, every field this window's:

    [rdc] f= dt= tid= tcpu= rdo= rdous= vtx=n/us/pg/h nv2a= tex= vga= code=
          mig= snap= oth= v= dra= dx= vr= tm= ovh=ns/n tk=

- `<site>=calls/us/pages/hits`. The us are the walk time `tlb_reset_dirty()`
  already took for rdous (a thread-local, no second clock read); hits are the
  entries the walk set `TLB_NOTDIRTY` on, i.e. whether the walk did anything.
- `tcpu`: the printing thread's CPU ms over the window. The render thread
  prints (its walks are what cross the window), so this is render-thread CPU
  per window; `-` when a different thread printed the previous line.
- `oth` must be 0 (an untagged door); `dx` must be 0 (a second outside caller).
- **Overhead, measured not argued**: one walk in 64 times the accounting
  between two clock reads (`ovh`), and each line reports the previous line's
  own cost (`tk`). `rdc_read.py` turns them into us per flip against rdous.
- Built: NDK clang type-check of physmem.c and cputlb.c from the shared
  tree's compile_commands (`typecheck.py`), no new warnings;
  `check_android_guards.py` ok. Desktop not built (AGENTS.md: unmeetable here).

## Predictions

- `dirtytlb-counter-pixels.json`: 12 suites through the vertex and texture
  paths, must not move, A master `9d777502fa`, B `111c7fea74`. Queued by the
  arms job.
- `dirtytlb-counter.json`: the soak legs (V, C1, C2, H, N1, N2, X, F, K1, K2),
  hand-queued (queue_counter.sh), B first then A, 240 s perflog; re-registered
  in attempt 2 on A `559ea2fc07`, B `9d33d2dac2`: Crimson on the Thor, Blinx on
  the Nova. Judge: `rdc_read.py --pair A B` (selftest: `--selftest`).

## The fix (not yet chosen)

What the counts would point to:
- vtx dominant and **hits well below calls**: the walks mostly re-arm nothing
  (the page was already NOTDIRTY because the guest has not written it since
  the last clear). Clear once per flip for the vertex client instead of per
  draw, in draw.c (lane.forza414's file: ask by board request).
- vtx dominant and **hits near pages**: each walk is needed; fewer, merged
  clears per flip is the only lever.
- A walk-skip inside physmem ("skip the walk if some other client's bit was
  already clean, since then no entry can be writable") looks exact but is
  not: a guest notdirty store on the vCPU can make the entry writable between
  the check and the clear. Not pursued.

## Runs

Attempt 1 queued four soaks at 2026-09-28 ~12:45Z (A 9d777502fa, B
111c7fea74). They never ran: withdrawn unclaimed at 14:55Z (queue/withdrawn/)
when attempt 2 added `vr`, and requeued (docs/lanes/dirtytlb/queue.log):

| request | title | device | arm |
|---|---|---|---|
| 1-1790606269-lane.dirtytlb-479803 | Crimson Skies | thor | B 9d33d2dac2 |
| 1-1790606269-lane.dirtytlb-479870 | Crimson Skies | thor | A 559ea2fc07 |
| 1-1790606270-lane.dirtytlb-479942 | Blinx | nova | B 9d33d2dac2 |
| 1-1790606270-lane.dirtytlb-480001 | Blinx | nova | A 559ea2fc07 |

A is master 559ea2fc07, which differs from the old A only in docs/ and jobs/.
The pixel arm is the arms job's (dirtytlb-counter-pixels.json, still on
9d777502fa / 111c7fea74, queued as arms-dirtytlb-base/fix); `vr` is a read of
a render-thread counter plus one static, so it moves no pixel, but that arm
covers the counter without it.

## Attempt 2 (2026-09-28 ~14:35Z)

Why attempt 1 did not finish: it did what it could and stopped on a correct
`waiting:`. Both handhelds were on battery holds, so its four soaks and the
pixel arm sat queued; handback resumed the lane with them still unclaimed.

What attempt 2 added: hostops' addendum (07:31 PDT) asks to price "one walk
per draw over the span of its dirty ranges" from the runs. `[rdc]` as queued
could not: vtx calls per flip against the Vsyn line's C (draws that reach the
sync) bounds walks per draw only loosely. So:

- **`vr`** (physmem.c): a vtx walk whose (flip, `vsync_working.calls`) equals
  the previous vtx walk's, i.e. a second or later walk inside one
  `pgraph_vk_sync_vertex_ram_buffer()` call. Only the render thread makes vtx
  walks, so a plain static key is enough. `tlb_reset_dirty()` scans every
  entry of every live mode whatever the length (cputlb.c ~1221), so the span
  lever saves exactly `vr` walks: `vr x vtx us/call` per flip, less whatever
  the wider span's extra NOTDIRTY entries cost the vCPU in slow-path stores.
- `rdc_read.py` reads `vr` (optional, so pre-vr lines still parse and read
  "unknown", not 0) and prints the price. Selftest covers both.
- Type-check as before: `typecheck.py <worktree>`, rc 0 on both files, the
  only warnings the pre-existing TARGET_PAGE_MASK shifts.

## The addendum's levers, to price from the runs

- **Span walk per draw** (safe as it stands): saves `vr` walks. It lives in
  draw.c (lane.forza414's): collect the dirty merged ranges of one sync, then
  one `physical_memory_dirty_bits_cleared(min_start, max_end - min_start)`
  after the loop, before the uploads are relied on. The bitmap test-and-clear
  stays per range, so no bit is lost; the span only re-arms more entries.
- **One walk per flip** needs a render-side pending bitmap (addendum); trades
  walks for repeat uploads. Only worth it if vtx calls per flip minus vr is
  still large.
- **VGA**: the addendum expects 3-5 walks per flip in `vga`; `[rdc]` reports
  them as their own site, not `oth`.

## Attempt 3 (2026-09-28 ~18:10Z)

Why attempt 2 did not finish: it also ended on a correct `waiting:` (the
four soaks and the pixel arm behind the battery holds). All five results
landed while no session was running, but no `[job.arms]` verdict was posted
on the PR, so handback's resume came as attempt 3 rather than as a
resolved wait. Nothing was lost; every result dir was DONE.

What attempt 3 found in them:

**Crimson B voided, requeued.** 479803 aborted before the route's first
input: both Thor displays read OFF at start, "not-foreground: unknown", 5
logcat lines. That is infrastructure, not the build (V: re-queued once).
Requeued as `1-1790619096-lane.dirtytlb-936387` (queue.log,
requeue_crimson_b.sh). Crimson A (479870, master) is valid: gfps 29,
Tq 1161, M 12028, j_per_frame 0.193 (title_verdict.py; 131 s of gameplay).

**Blinx pair (Nova, A 480001 / B 479942): read.** By `rdc_read.py --pair 480001 479942` and, for K1,
`docs/lanes/remote/pair461_read.py --pair` (outputs not committed: `*.txt`
is ignored; rerun them on the result dirs).

| per flip (B, 1620 flips in the window) | calls | us | pages | hits | us/call |
|---|---|---|---|---|---|
| vtx | 23.0 | 293 | 42.7 | 5.8 | 12.7 |
| tex | 0.2 | 3 | 19.6 | 6.0 | 20.8 |
| snap | 0.2 | 4 | 68.9 | 0.0 | 16.0 |
| rdo / rdous | 23.4 | 300 | | | |

- tcpu 49.2 ms per flip; gfps 10 in both arms; `vr` 0.0; `oth` 0, `dx` 0;
  vga 0 (no VGA walks at all on this scene).
- Legs: V, C1, C2, N1, N2, X, F, K1, K2 PASS. **H FAILS as registered**: the
  counter costs 129 ns per call, 3.6 us per flip, which is 1.21% of rdous
  (bar 1%). The 500 ns-per-call clause passes. The ratio fails because
  Blinx's walks are cheap (12.7 us, against Crimson's 27), so 129 ns is
  already 1% of one; in absolute terms it is 0.007% of the render thread's
  49 ms per flip.
- **What it says about the fix on this scene: nothing to win.** The walks
  are 0.3 ms of 49 ms render CPU per flip (0.6%), vtx makes 99% of them,
  and `vr` 0 means one walk per draw already: the span lever saves nothing.
  Only 25% of vtx walks re-arm any entry (5.8 hits in 23 calls).
- **Limit:** Blinx's `survey` route never marks gameplay (title_verdict:
  "no `mark gameplay`"), so there is no j_per_frame, and this is a
  hands-off scene at 10 gfps, not play. No route exists for Blinx or AUF
  (docs/testing/titles/routes/). The brief's #462 leg is measured on that
  scene only.

**The pixel arm (dirtytlb-counter-pixels.json): FAIL as registered, 1 of
337.** Read by hand with `ab_compare.py --a <base-88080> --b <fix-88112>
--expect` the prediction; no `[job.arms]`
comment had been posted. No `unreadable` rows, no UtilAcceptVsock in either
run1.log. 336 captures byte-identical. The one move:
`Texture_signed_component_tests/txt_A8R8G8B8_ADD`, A 168,960
`label-differs`, B 153,427 `white-content`. It is a visible move: B's upper
quads show the header's red gradient and blue stripes, a stale texture
sampled. The counter adds no walk and skips none (the diff wraps the same
`tlb_reset_dirty_range_all()` calls); what it adds on the render thread is
time. This capture moved 12,544 px under tiecode282's unrelated change and
varies run to run on lavapipe, but read byte-stable in lane.remote's six
handheld runs (#461). One run per arm cannot separate the two; so:

- **`dirtytlb-counter-signed.json`** (register_signed.sh): three runs per
  arm, that suite only, A master `01e62d8d1c`, B `0794c79011` (this branch
  with master merged; A..B is the counter and docs only). Refuted if A's
  three runs agree byte for byte and B's three all differ from them: the
  counter's timing reliably exposes a texture-upload race, and it does not
  land as it stands. Queued by the arms job on push.
- If it is refuted, the race is itself a finding: a stale texture under a
  timing change is what the tail-page gap above would produce if a texture
  range ever reached it unaligned. That is not the case for
  check_texture_dirty (page-aligned), so the next lane should look at the
  texture cache's own upload ordering before the TLB.

## Waiting (2026-09-28 ~18:30Z, attempt 3)

On: `1-1790619096-lane.dirtytlb-936387` (Crimson B, Thor), then
`rdc_read.py --pair 479870 936387` and pair461_read.py K1, which name the
dominant Crimson caller and price `vr`; and the arms job's verdict on
`dirtytlb-counter-signed.json`. The fix (dirtytlb-fix-*.json, draw.c by
board request) is chosen from Crimson, not Blinx: on Blinx there is no walk
cost worth removing.

## Waiting (2026-09-28 ~15:00Z)

On things outside this session: the four soaks above (both handhelds on
battery holds; the Nova lifts near 16:15Z), the arms job's `[job.arms]`
verdict on dirtytlb-counter-pixels.json, and CI on the head. Next session:
`rdc_read.py --pair A B` per title, K1 from thermal.jsonl, j_per_frame from
title_verdict.py; then choose between the levers above from vtx's calls, vr
and hits per flip, register dirtytlb-fix-*.json, and ask for draw.c by board
request.
