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

## Attempt 4 (2026-09-28 ~18:30Z)

Why attempt 3 did not finish: it ended on a correct `waiting:`, on Crimson B
(`936387`) and on the signed-suite arm. Handback resumed the lane when the
arms job posted its `[job.arms]` verdict on dirtytlb-counter-pixels.json
(FAIL 1 of 337, label `regressed`). That is the verdict attempt 3 had
already read by hand, so the resume carried nothing new about it. Crimson B
finished at 18:20Z, five minutes after the wait was posted. The signed-suite
arm was registered at 18:13Z, after the arms job's 18:10Z tick, so it was
not queued yet.

### Crimson pair (Thor, A 479870 master `559ea2fc07` / B 936387 `9d33d2dac2`)

`rdc_read.py --pair 479870 936387`, window 90 to 240 s, B over 4,140 flips:

| per flip (B) | calls | us | pages | hits | us/call |
|---|---|---|---|---|---|
| vtx | 126.3 | 3052 | 262.4 | 137.9 | 24.2 |
| tex | 50.1 | 1228 | 6626.7 | 74.3 | 24.5 |
| rdo / rdous | 176.4 | 4280 | | | |

- tcpu 21.58 ms per flip, so the walks are 19.8% of the render thread's CPU
  and the vertex sync's are 14.1%. `vr` 0, `tm` 0, `oth` 0, `dx` 0, vga 0.
- **Every leg passes**: V, C1, C2, H (216 ns per call, 38.8 us per flip,
  0.91% of rdous), N1 (vtx + tex 100%), N2, X, F (gfps 29 / 29), K1 (39
  cooling devices, every highest state equal), K2 (M 12028 / 12000).
- j_per_frame A 0.193 / B 0.190 (`jpf.py`; net 5.64 W / 5.51 W).
- **The brief's question, answered**: of 176 off-vCPU walks per flip the
  vertex sync makes 126 (72%) and `check_texture_dirty` 50 (28%). Nobody
  else makes any. lane.remote's offline bound for the vertex sync was 98 to
  165.
- Limits of this pair. B lost one A press of the intro mash to a WSL
  `UtilAcceptVsock` timeout (run.log line 14), so its gameplay frame is one
  tutorial prompt behind A's; both frames are the same flight over water and
  K2 agrees. B started at xo 60.0 C and A at 56.6 C; neither run has a
  thermal pause. A is master, so A has no tcpu: the counter's cost on the
  render thread is H's 38.8 us per flip, not a tcpu difference.

### The levers, priced from Crimson

- **Span walk per draw: nothing.** `vr` is 0 on both titles: a sync call
  that walks at all walks once.
- **One walk per flip with a pending bitmap: up to 3.0 ms per flip, not
  priced further.** It would remove 125 of the 126 vertex walks. But hits
  per walk are 1.09: nearly every walk re-arms an entry the guest had
  written through, so these walks do needed work and the repeat uploads it
  trades them for are real (2.08 pages, 8.3 KB, per upload today). The
  count it needs is the draws per flip that read a page dirtied earlier in
  the same flip. That count lives in draw.c, and `[rdc]` cannot see a draw
  that does not walk.
- **The walk itself: 2.7 to 2.9 ms per flip off the vCPU thread, and 2.5 to
  2.7 ms on it.** `walk_read.py` reads `[tlb68]` beside `[rdc]`:

| run | live entries | entries per walk | modes per walk | us per walk, off-vCPU | us per walk, vCPU |
|---|---|---|---|---|---|
| Crimson A 479870 | 1793 | 7204 | 22 | 21.11 | 14.19 |
| Crimson B 936387 | 2620 | 7992 | 22 | 24.25 | 16.44 |
| Blinx A 480001 | 606 | 5882 | 22 | 14.53 | 13.98 |
| Blinx B 479942 | 612 | 5881 | 22 | 12.83 | 13.04 |

  Every walk scans all 22 MMU modes. Two hold entries (`dm=0x60`); the other
  20 are empty 256-entry tables plus their victims, 5,280 entries, 67 to 75%
  of each Crimson walk and 90% of each Blinx walk. `HAKUX_TCG68_RD` (#68, PR
  #309) walks only the modes that can hold a live entry. It was audited
  exact (docs/audits/2026-09-25-tcgchurn-pass1.md) and turned off by default
  for #311's arms, and it never got an arm of its own.
- Why the time should follow the entries: the two Crimson runs have
  different table sizes and read 2.93 and 3.03 ns per entry off the vCPU
  thread (1.98 and 2.05 on it). That is two runs, not a fit; legs T and U
  test it.
- **The vCPU thread walks more than the render thread does**: 237 to 242
  walks per flip, every one of them code arming (`rdc` = `rd`), 3.4 to 4.0
  ms per flip, 10.6 to 12.1% of the vCPU thread's CPU. That answers
  lane.slowtier2's request for a split by thread (#548, 15:11Z): `[rdc]`'s
  `v` and `[tlb68]`'s `rd`, `rdc` and `rdus` already carry it.

### The fix: walk only the live modes, by default

In `accel/tcg/cputlb.c`, this lane's file, so no board request. It removes
no walk and clears every bit as before, so there is no upload trade. It
shortens every caller's walk on both threads.

- Branch `lane/dirtytlb-rd`, stacked on this one, with its own PR: the
  default flips there and nowhere else, so #549 stays the counter.
- `dirtytlb-rd.json`: the Crimson soak pair on the Thor, hand-queued, B
  first. Judge: `walk_read.py --pair A B`, K1 from pair461_read.py, J from
  jpf.py.
- `dirtytlb-rd-pixels.json`: 11 of the counter arm's 12 suites, one run per
  arm, queued by the arms job. `dirtytlb-rd-signed.json`: the twelfth, three
  runs per arm, because its capture moved in a one-run arm.
- Black and Midtown Madness 3 (lane.slowtier2's ask) wait for the Crimson
  pair: it is the pilot, and four more soaks would pass the 30 min gate.

### On `lane/dirtytlb-rd` (A `249ea8fd05`, B `052551bdd3`)

- The change is one line: `hakux_tlb68_rd_on()` reads 1 when
  `HAKUX_TCG68_RD` is unset, as `hakux_tlb68_jc_on()` does since #425.
  `HAKUX_TCG68_RD=0` restores the full walk.
- Why it is exact was argued in #68 and read again by PR #309's audit; read
  a third time here against the head: `c.dirty` is set under `c.lock` in
  `tlb_set_page_full()` before an entry is installed, and cleared only in
  `tlb_flush_by_mmuidx_async_work()` together with the flush of the same
  modes. The walk reads it under the same lock.
- Leg X is the device check of that argument: hits per walk and `sd` per
  flip must not drop. A faster walk that re-arms fewer entries is a walk
  that skipped work.
- Two refs, not one binary with `--env`: a second arm on the same APK keeps
  the first arm's shader cache, and a new APK clears it in both.
- Type-check (`typecheck.py`): no error, the same TARGET_PAGE_MASK shift
  warnings as before. `check_android_guards.py` ok. `walk_read.py
  --selftest` ok; its fixtures cover the switch not taking (W), a walk that
  stays wide (E), a walk that got faster by skipping (X), time that does not
  follow entries (T, U) and a render thread whose CPU does not move (C).
- `preflight.sh --allow-tracker` on `c137d97dfc`: every step ok except
  `territory`, which fails on two rows of `origin/board:territory.toml` that
  are not this lane's (draw.c claimed by pacing and shaderfb569, debug.h by
  shaderfb569 and remote). No file of this lane is in either row.

### What the next session should not repeat

- Do not look for the fix in draw.c first. The counts say the callers are
  doing needed work (hits per walk 1.09, `vr` 0); the waste is inside the
  walk, and `[tlb68]`'s `rdm` and `rdoe` had shown 22 modes per walk since
  #68. Read `fx=` on a `[tlb68]` line before pricing any TLB lever: it says
  which switches the run had on.
- Do not judge a walk lever by `rdous` per flip alone. The two rd0 Crimson
  runs differ by 20% in it (3584 and 4292) because their tables differ in
  size; us per entry is the figure that agrees.

## Attempt 4, resumed (2026-09-28 ~19:55Z)

Why the previous session did not finish: it ended on a correct `waiting:`,
on the signed-suite verdict for this PR and on the fix pair and its two
pixel arms for #575. Nothing of it had run when it ended (the Thor was on
lane.fanduty507's hold). The signed-suite verdict was posted at 19:29Z and
the fix pair finished at 19:55Z; handback resumed the lane then.

### The signed-suite arm: PASS, and it supersedes the one-capture FAIL

`dirtytlb-counter-signed.json` (`[job.arms]` on #549, 19:29Z; A
`01e62d8d1c` result `arms-dirtytlb-base-1288042`, B `0794c79011` result
`arms-dirtytlb-fix-1288213`; three runs per arm, 19 captures each, progress
log proof in all six):

- All 19 registered checks hold: 18 captures exact in both arms, no capture
  outside A's band, no `unreadable` row in the six scores files, no
  UtilAcceptVsock in the six run logs.
- `txt_A8R8G8B8_ADD` scores 168,960 px against the golden in all six runs,
  and **it varies inside arm A**, which is master with no counter: A's run
  1 differs from A's runs 2 and 3 in 512 px (two rows, x 64 to 319, y 118
  to 119, largest channel difference 191; sha256 `906cb7f2` against
  `5a303ebf`). B's three runs are all `5a303ebf`. Read here with PIL on the
  captures; the score cannot see it because those rows differ from the
  golden either way.
- So the capture moves run to run on a build that has no counter, which is
  the prediction's claim. The 15,533 px move of the one-run arm is larger
  than the 512 seen here and was not reproduced in three runs of B.
- The PR label is `verified`: the arms job counts the FAIL as superseded.

So #549 is done: counter measured on both titles, overhead measured (H
passes on Crimson, fails its 1% ratio on Blinx at 3.6 us per flip), pixel
arm superseded by a PASS. It goes ready.

### What the next lane should not repeat

- Do not read a one-run pixel FAIL on `Texture_signed_component_tests` as
  the change's. `txt_A8R8G8B8_ADD` moved once under this lane's counter,
  once under tiecode282's unrelated change, and between two runs of one
  master build here. Register that suite with three runs per arm from the
  start, and compare its captures by pixel, not by score: the score read
  168,960 for two different images.
- H's bar is a ratio to `rdous`. With the fix of #575 the walks cost a
  fifth of what they did, so the same 180 to 216 ns per call reads 3.8% of
  rdous. The cost to watch is the absolute one (30 to 39 us per flip on
  Crimson).

### The fix pair, read: every registered leg passes (`dirtytlb-rd.json`)

Crimson, Thor, regimen max, 240 s, window 90 to 240 s, 4,320 flips in each
arm. A `1-1790620928-lane.dirtytlb-1387249` (`249ea8fd05`, rd0), B
`1-1790620928-lane.dirtytlb-1386630` (`052551bdd3`, rd1); B ran first.
Judges: `walk_read.py --pair`, `rdc_read.py --pair`, `pair461_read.py
--pair` (K1), `jpf.py` (J). Their outputs are `rd_*.txt` here, ignored by
git; rerun them on the result dirs.

| per flip | A (all 22 modes) | B (live modes) | |
|---|---|---|---|
| entries scanned per walk | 7,772 | 1,923 (live 1,834) | x0.25 |
| modes per walk | 22 | 2 | |
| us per walk, render thread | 21.70 | 4.83 | x0.22 |
| us per walk, vCPU thread | 15.03 | 2.41 | x0.16 |
| walks, render thread | 170.4 | 160.5 | |
| walks, vCPU thread | 236.4 | 242.7 | |
| walk ms, render thread | 3.70 | 0.77 | -2.92 |
| walk ms, vCPU thread | 3.55 | 0.58 | -2.97 |
| render-thread CPU ms (`tcpu`) | 19.79 | 16.44 | -3.35 |
| vCPU walk share of its CPU | 11.2% | 1.8% | |
| hits per vertex walk | 1.03 | 0.97 | |
| hits per vCPU walk | 1.00 | 1.00 | |
| `sd` (notdirty stores) | 473.3 | 469.1 | |
| gfps median | 29 | 29 | |
| flips taking 3+ VBLANKs | 4.3% | 0.8% | |
| net W / `j_per_frame` | 5.876 / 0.1995 | 5.888 / 0.1977 | x0.991 |

| leg | | read |
|---|---|---|
| V | PASS | 75 `[tlb68]` and 72 `[rdc]` lines in each arm |
| W | PASS | A `fx=rd0`, B `fx=rd1` on every line |
| E | PASS | B 1,923 entries per walk against 1,834 live (+5%), x0.25 of A |
| X | PASS | hits per walk vtx 1.03 / 0.97, vCPU 1.00 / 1.00; sd 473.3 / 469.1 |
| T | PASS | x0.22 (bar 0.75) |
| U | PASS | x0.16 (bar 0.75) |
| C | PASS | -3.35 ms (bar -1.0) |
| F | PASS | 29 / 29 |
| J | PASS | x0.991 (bar 1.03) |
| K1 | PASS | 39 cooling devices, every highest state equal |
| K2 | PASS | M 11360 / 12001, x1.056 (bar 1.10) |

- Both run logs: no UtilAcceptVsock, 12 of 12 mash presses, no thermal
  pause. Both gameplay frames show the same tutorial prompt over the same
  water ("Objectives also show up on your map as yellow circles").
- What the pair does not show:
  - **No fps gain and no energy gain.** Crimson paces itself to 30 and held
    29 in both arms. Net power is the same to 0.2% and `j_per_frame` is
    0.9% lower, inside the 3% band two rd0 runs differ by. 5.9 ms of CPU per
    flip over two threads did not show in the battery at regimen max.
  - **C is not all the walk's.** The walks account for 2.92 of the 3.35 ms.
    B also made 6% fewer render-thread walks and hashed 12% less texture
    per flip (pair461's P2: mk 23,488 against 20,576 KiB), so the arms'
    scenes differ a little; K2 passes at 5.6%.
  - A started at xo 54.5 C and B at 48.5 C.
- The counter's cost is now a larger share of what it counts: 180 ns per
  call is 3.8% of B's rdous (leg H of `dirtytlb-counter.json`, bar 1%).
  That leg is not in `dirtytlb-rd.json`. In absolute terms it fell, 35.0 to
  29.5 us per flip.

### Black and Midtown Madness 3, priced offline from their rd0 runs

lane.slowtier2's readings (Thor, regimen max) carry `[tlb68]`, so
`walk_read.py RUN --window` prices them with no device time
(`price_black.txt`, `price_mm3.txt`):

| run | window | gfps | walks per flip, render / vCPU | us per walk, render / vCPU | walk ms per flip, render / vCPU | entries per walk | live |
|---|---|---|---|---|---|---|---|
| Black, titleroutes-3358750, `a593d8eb85` | 500 to 770 s | 7 | 235.7 / 41.3 | 72.7 / 86.8 | 17.15 / 3.59 | 9,456 | 4,176 |
| MM3, titleroutes-1032854, `6aaa8197c5` | 330 to 575 s | 2 | 20.1 / 111.5 | 85.6 / 82.8 | 1.72 / 9.23 | 9,456 | 4,176 |

- On both the live table is 4,096 entries, so the empty modes are 56% of
  the walk, not Crimson's 75%. If time follows entries the fix saves 9.6 ms
  per flip on Black's render thread and 2.0 on its vCPU (of a 134 ms
  frame), and 5.2 ms on MM3's vCPU (of 320 ms, 1.6%).
- A walk costs 7.7 to 9.2 ns per entry on these two, against 1.3 to 2.8 on
  Crimson's fix pair. Not explained. These titles walk a third as often per second
  (1,650 walks per second on Black's render thread, 4,900 on Crimson's), so
  the tables may be cold in the cache each time (inference). That is the
  reason to measure Black and not extrapolate Crimson's x0.22.
- **Black gets a pair (`dirtytlb-rd-black.json`), MM3 does not.** Black has
  the largest render-thread walk cost on record. MM3's price is 1.6% of its
  frame and its route takes 580 s; its bound is a blocked vCPU, which this
  fix does not address.

### The Black pair (registered, then queued)

- A `68cfc51e10` (`lane/dirtytlb`'s head: the counter, master merged, rd0),
  B this branch's head at registration (the same tree with rd1). Both
  carry master `503b901ee4`, so neither is the APK of the Crimson pair.
- Route `black.returning`, 760 s, Thor, B first. The window is 500 to 760 s
  after the first hakuX-perf line: the route's `mark gameplay` comes at
  about +489 s.
- Two things can void it, and each is read before any leg:
  - **The route is timed presses recorded on `a593d8eb85`.** lane.slowtier2's
    Otogi pilot never left the title screen on a newer build. Read
    `route-frames/*gameplay.png` in each arm first.
  - **A 760 s run at regimen max can reach the thermal pause (#507).** K1
    and the run log's THERMAL line say whether it did. E, X, T and U are
    read either way; C, F and J only on a pair with no pause in the window.

## Waiting (2026-09-28 ~20:40Z, attempt 4 resumed)

All outside this session.

| what | id | resolves |
|---|---|---|
| fix, 11 suites, A | `1-1790621866-arms-dirtytlb-base-1593889` (running at 19:56Z) | the `[job.arms]` verdict on `dirtytlb-rd-pixels.json`, PR #575 |
| fix, 11 suites, B | `1-1790621867-arms-dirtytlb-fix-1593943` | the same |
| fix, signed suite x3 | `1-1790621868-arms-dirtytlb-base-1594519`, `1-1790621869-arms-dirtytlb-fix-1594555` | the `[job.arms]` verdict on `dirtytlb-rd-signed.json`, PR #575 |
| Black pair | in `queue.log`, under `rd-black` | `dirtytlb-rd-black.json` |

Then:
- #575 goes ready when both pixel verdicts are PASS. The Black pair adds a
  second title to its release note; it does not gate the PR, because the
  Crimson pair passed as registered and the switch's exactness is the
  pixel arms' and leg X's to show.
- Read the Black pair with `--window 500,760` on all three judges, frames
  and THERMAL line first.
- If a pixel arm fails on `txt_A8R8G8B8_ADD` alone, compare the six
  captures by pixel before reading it as the fix's: it varied inside arm A
  of the counter's signed arm.

## Waiting (2026-09-28 ~18:50Z, attempt 4)

All outside this session. Both handhelds are on holds (the Nova on battery,
the Thor on lane.fanduty507's), so nothing of this lane's has run yet.

| what | id | resolves |
|---|---|---|
| fix pair B, Crimson, Thor | `1-1790620928-lane.dirtytlb-1386630` | `dirtytlb-rd.json` |
| fix pair A, Crimson, Thor | `1-1790620928-lane.dirtytlb-1387249` | `dirtytlb-rd.json` |
| counter, signed suite x3 | `1-1790620563-arms-dirtytlb-base-1288042`, `-fix-1288213` | the `[job.arms]` verdict on `dirtytlb-counter-signed.json`, PR #549 |
| fix, 11 suites | not queued yet (next arms tick) | the `[job.arms]` verdict on `dirtytlb-rd-pixels.json`, PR #575 |
| fix, signed suite x3 | not queued yet (next arms tick) | the `[job.arms]` verdict on `dirtytlb-rd-signed.json`, PR #575 |

Then:
- `walk_read.py --pair 1387249 1386630`, `pair461_read.py --pair` for K1,
  `jpf.py` for J. Read run.log for UtilAcceptVsock and the gameplay frame
  of each arm first: 936387 lost a press to it.
- #549 goes ready when the signed-suite verdict supersedes the one-capture
  FAIL. If that arm is refuted (A's three runs agree and B's three all
  differ), the counter does not land as it stands, and #575 carries it, so
  #575 waits on the same verdict.
- #575 goes ready when its pair and both pixel arms are read. Put the
  measured figure in its `Release note` line then.
- Then Black and Midtown Madness 3 on the Thor, both refs, for
  lane.slowtier2: write `pilots/lane.dirtytlb.ok` from the Crimson pair
  first.

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
