# lane.ghoul311 -- #311 Grabbed by the Ghoulies hands-off fps decay

Status: 2026-09-26 00:20 UTC (attempt 4). The since-when pair is judged (both
bad, section 6); the host's bisect driver owns the since-when (section 7);
waiting on lane.tcgchurn's counter arm and the next bisect rounds.
Diagnosis first; no source claimed.

**Read section 6 before section 1.** Section 1's model (the arming walk after
a page empties) was written from one soak and is refuted by the pair: the
re-arm count differs 7x between the two arms and the frame time is the same.

## 1. What the existing logs already say (no new device time)

Source: gamecheck soak `1790365974-gamecheck-732876` and control
`1790366421-gamecheck-890892` (Nova, apk `851650a27937`, ref `e48514f980`).
Both carry the `hakuX-perf` pacing line and both `hakuX-pages` lines. The
pages lines fire every 120 guest frames, so **window seconds / 120 is the mean
guest frame time** for that window, with no smoothing. Tool:
`docs/lanes/ghoul311/windows.py`.

### The guest CPU is the slow side

`Ri` (renderer idle, ms per frame) tracks `G` (game frame ms) almost
one-for-one: 30.7/33.8 at 6 s, 504/546 at 133 s. The renderer waits on the
guest. The vblank timer stays at 59.9 Hz, and `Vpf` (vblanks per flip) climbs
from 1.96 to 12.8.

### Per 120-frame window, soak 732876

| t (s) | ms/frame | ev/f | di/f | pr/f (arming walks) | (ms-33)/pr (ms) |
|---|---|---|---|---|---|
| 17.0 | 63.8 | 88 | 376 | 88 | 0.35 |
| 23.0 | 49.9 | 82 | 344 | 82 | 0.21 |
| 39.6 | 138.0 | 148 | 547 | 148 | 0.71 |
| 62.1 | 187.6 | 171 | 629 | 171 | 0.91 |
| 88.3 | 218.3 | 169 | 480 | 169 | 1.10 |
| 133.1 | 373.6 | 208 | 478 | 208 | 1.64 |
| 190.3 | 476.2 | 247 | 566 | 247 | 1.80 |
| 236.1 | 381.8 | 233 | 644 | 233 | 1.50 |

Control 890892: 33.4 ms/frame (the 30 fps cap) at 9-17 s with pr/f 70-85, so
**each arming walk costs < 5 us there**; then 40.8 ms at 22 s, 81 at 32 s, 131
at 48 s.

**The frame time rises 11x while re-arms per frame rise only 2.7x.** If the
excess frame time is charged to the arming walk (`tlb_protect_code`), each walk
gets ~300x more expensive between 17 s and 133 s and then plateaus at
1.5-1.8 ms. A count of events cannot explain the curve; a per-event cost that
grows can.

Controls on the same apk (`1790364698` RalliSport 2, `1790364700` Spikeout):
4-9 arming walks per frame, at 60 fps -- 20-50x fewer re-arms than Ghoulies.
Any per-re-arm cost is diluted there by that factor.

Things that do **not** grow per frame: `ai` ~0, `xx` = 0, `ix` = 0; the
inv_htable recycle hits are all depth 1 (`hd` = n/0/0/0/0) and hash ~36 bytes
per candidate, so the recycle cache is not the growing cost. Codegen (`cg/f`)
falls to 2-3 per frame: this is not translation-buffer churn in the #68 sense
(new code generated), it is the re-arming around recycled blocks.

### The mechanism the numbers point at

`tb_page_add` re-arms a page (`tlb_protect_code`) whenever its TB list was
empty; `pr` == `ev` in every window, so every invalidation empties its page
and the next execution re-arms it. `tlb_protect_code` ->
`physical_memory_test_and_clear_dirty` -> `tlb_reset_dirty` walks **every
entry of every MMU index's TLB** (`accel/tcg/cputlb.c:917-939`), so its cost is
proportional to the TLB's current size, not to the page.

The TLB is dynamically sized (`tlb_mmu_resize_locked`, cputlb.c:204): at each
full flush it doubles when the window's max use exceeds 70%, up to
`1 << CPU_TLB_DYN_MAX_BITS` = 2^20 entries per index on i386. It only shrinks
at a flush after a 100 ms window under 30%. A title that loads a large
working set (the title screen building, 20-50 s) grows it, and a guest that
rarely does a full flush (a single address space) never lets it shrink.
Also, `n_used_entries` can drift upward: a same-page refill takes the
`tlb_hit_page_anyprot` branch (cputlb.c:1134), skips the decrement and still
increments at 1186, so use can read high without more pages in use.

This is the candidate. It is **not measured yet**: nothing in the build
reports the TLB size. See section 3.

## 2. Pre-registered for the reproduction soaks (written before queueing)

Current master (`a7f7c8bda9` + notes), Ghoulies, 240 s, frames every 2 s,
hands-off. From the existing counters only:

- window nearest 20 s: ms/frame 33-70, pr/f 65-100, (ms-33)/pr <= 0.4 ms
- window nearest 120 s: ms/frame >= 200, pr/f 140-260, (ms-33)/pr >= 0.9 ms
- refuted if ms/frame >= 200 at 120 s with (ms-33)/pr flat (within 2x of its
  20 s value): then the per-event cost is not what grows.
- not reproduced if ms/frame < 70 at 120 s on both runs.

## 3. The counter that would decide it (named, not applied)

`accel/tcg/cputlb.c` is lane.tcgchurn's and `profile.c` lane.perfbase's, so
the instrument is named here for the board to grant:

- `hakux_tlb_walk_entries += n` inside `tlb_reset_dirty`'s mmu_idx loop
  (sum of `tlb_n_entries(fast) + CPU_VTLB_SIZE` over every call);
- `hakux_tlb_resizes` and the current max `tlb_n_entries` over mmu indices,
  set in `tlb_mmu_resize_locked` when `new_size != old_size`;
- printed as `tw=` / `tn=` / `rs=` at the end of the `inval` line.

Prediction for that counter, per arming walk (`tw/pr`):

- ~20 s window: <= 4.2k entries (8 indices x 512 + vtlb)
- ~120 s window: >= 64k entries, i.e. >= 15x the 20 s value, with
  ms/frame - 33 ~= pr/f x tw/pr x k at a single k across all windows.
- **Refuted** if `tw/pr` stays within 2x of its 20 s value while the frame
  time collapses.

## 4. Since when: the pair around 2af6def68a (registered, queued)

No `v0.3.1` tag exists (v0.3.2, v0.3.3-j1 and v0.4.0-j1 do). v0.4.0-j1
(2026-09-10) has no `hakuX-perf` or `hakuX-pages` line at all, so its fps
could only be read off captured frames. The better bound is in the code:
`2af6def68a` (2026-09-14, "unstranding #73's blocks") changed when a page
empties. Before it, tier-1 promotion left CF_INVALID blocks stranded on page
lists for the life of the buffer, so a page carrying one never emptied and was
never re-armed. In the gamecheck soak, the tier-1 `consume` lines put
promotions on all four hot store pages: 0x549458 -> 54940c, 0x184725/0x18478f
-> 184278, 0x183a54 -> 183ac0, and 0x1c5a15 -> 1c5518. After 2af6def68a, every
invalidation empties the page and pays the arming walk (`pr == ev`).

Prediction `docs/testing/predictions/ghoul311-sincewhen.json`
(sha256 `05acabbe548622279bc6de55f03f8c6fcb3a2ab312f0f5a9788bf230972f4216`,
committed in 18e5dda13a before either arm was queued). a_ref `797129aea7`,
b_ref `2af6def68a`:

- A: pr/f at 120 s <= 25, ms/frame at 120 s <= 100
- B: pr/f at 120 s >= 120, ms/frame at 120 s >= 200, (ms-33)/pr >= 0.9 ms
- both arms <= 70 ms/frame at 20 s
- refutes the model: A at pr/f <= 25 still >= 200 ms/frame with ai/visited
  <= 0.5
- a second growth, not a refutation: A collapses with ai/visited > 0.5 (the
  pre-fix page-list clog grows instead)

Queued (Nova, 240 s, frames every 2 s):

| request | ref | role |
|---|---|---|
| `1790370153-ghoul311-3053340` | f94b6e0ad1 (master + notes) | reproduction 1 |
| `1790370157-ghoul311-3058825` | f94b6e0ad1 | reproduction 2 |
| `1790370309-ghoul311-3211642` | 797129aea7 | since-when A |
| `1790370311-ghoul311-3215191` | 2af6def68a | since-when B |

### Attempt 3 (resume, 22:50 UTC)

Why attempt 2 did not finish: it ended correctly in a wait -- all four soaks
were queued on the Nova, ~5 h behind, and nothing had run. It did not post the
`[lane.ghoul311] waiting:` comment, so the resume came from the host moving
the pair, not from a signal. Nothing is wrong with the pair or the prediction.

The host re-queued the pair on the Thor at top priority as
`0-0-1790370309-ghoul311-3211642` (A) and `0-0-1790370311-ghoul311-3215191`
(B). At 22:50 UTC both were still in `queue/`, behind a texvol283 arm and a
Lighting_normals run. **The pair is not a one-commit A/B:**
`797129aea7..2af6def68a` is 390 commits, and 2af6def68a is only the last.

Queued now, both `--device thor`, `#311 bisect` in the purpose, no
prediction (a bisect point is classed by the section-4 thresholds, not by a
new model):

| request | ref | answers |
|---|---|---|
| `1790376674-ghoul311-3613035` | 7df72a6c98 (= 2af6def68a^) | #73's unstrand vs the other 389 commits, if A is good and B is bad |
| `1790376677-ghoul311-3616328` | aeb4a096b6 (v0.4.0-j1) | does the 0.4 release have it? (not an ancestor of 2af6def68a; no pages line, so fps comes from frames) |

How to judge them: gfps at 90-240 s from `hakuX-perf`, >= 25 good and <= 5 bad,
plus the pages `pr/f` curve (`windows.py`). If A is good and B is bad, and
7df72a6c98 is good, then #73 is the commit and section 5's hunk is the fix. If
7df72a6c98 is bad, bisect `797129aea7..7df72a6c98`. If both A and B are bad,
bisect `e64e336d27..797129aea7`. If both are good, bisect `2af6def68a..master`.

Branch merged with origin/master (merge, not rebase; the prediction refs are
unchanged).

## 5. The fix hunk (named, not applied)

`docs/lanes/ghoul311/fix-keep-armed.diff.txt`: under XBOX, do not
`tlb_unprotect_code` when a page empties (`tb-maint.c:1812-1815`, the only
disarm site). The next `tb_page_add` then finds the code bit still clear and
the walk does not happen. It needs a grant on `accel/tcg/tb-maint.c`
(lane.tcgchurn's). Its arm is master vs master+hunk, predicted from the pair
above once the pair lands.

## 6. Attempt 4 (2026-09-25 23:47 UTC): the pair, judged -- both bad

Why attempt 3 did not finish: it ended in a wait, correctly (the
`[lane.ghoul311] waiting:` comment is on #316 at 22:51 UTC). The host resumed
it when both halves had `DONE`. Meanwhile the host withdrew my two bisect
soaks (`7df72a6c98`, `aeb4a096b6`) into `queue/withdrawn/` and took the bisect
mechanics over with `host-tools/bisect311.py` (section 7).

Tools added here: `gfps.py` (30 s gfps bins and a window median from the
`hakuX-perf` line), `pacing.py` (every pacing field over time), `ls_results.py`
(request state without `ls`).

### The two arms, Thor, 240 s, frames every 2 s

| arm | ref | apk | gfps by 30 s bin | median gfps 90-240 s |
|---|---|---|---|---|
| A | 797129aea7 (09-13, pre-unstrand) | d1496958c8f7 | 29 6 7 3 2 3 2 | 2.5 |
| B | 2af6def68a (09-14, #73 unstrand) | 4155a653abec | 29 5 5 4 1 2 2 2 | 2.0 |

Both bad. Against the registered legs (`ghoul311-sincewhen.json`):

| leg | predicted | A measured | B measured |
|---|---|---|---|
| A pr/f at 120 s | <= 25 | 29 | -- |
| A ms/frame at 120 s | <= 100 | 381 | -- |
| B pr/f at 120 s | >= 120 | -- | 218 |
| B ms/frame at 120 s | >= 200 | -- | 420 |
| B (ms-33)/pr | >= 0.9 ms | -- | 1.77 ms |
| both <= 70 ms/frame at 20 s | yes | 33.9 | 33.9 |

The A legs failed. The "refutes the model" leg (A at pr/f <= 25, still >= 200
ms/frame, ai/visited <= 0.5) does not fire by the letter: A's pr/f is 29 and
its ai/visited is 0.89. The "second growth" leg (A collapses with ai/visited
> 0.5) fires by the letter. **Neither reading survives the brief's
falsifier**, which is the one that matters: a counter that is flat while the
fps collapses is refuted.

| counter, per frame | A at 18 s | A at 120 s | B at 18 s | B at 134 s |
|---|---|---|---|---|
| ms/frame | 33.9 | 381 (11x) | 33.9 | 420 (12x) |
| pr (arming walks) | 14 | 29 (2x) | 76 | 218 (2.9x) |
| ev (invalidations) | 1614 | 2407 (1.5x) | 76 | 218 |
| ai/visited | 0.85 | 0.89 | -- | -- |
| cg (blocks generated) | 2.4 | 2.0 | 1.9 | 2.5 |
| Tq (texture dirty queries) | 427 | 652 | 428 | 691 |

Nothing the pages line counts grows with the frame time in either arm. And
across the arms: **the re-arm count differs 7x (29 vs 218 per frame) while
the frame-time curve is the same at every timestamp** (33.4 / 67.8 / 118.7 /
155.1 / 606.1 ms in A at 3 / 24 / 35 / 45 / 120 s; 33.4 / 69.3 / 116.1 /
177.7 / 653.5 ms in B at 3 / 24 / 36 / 46 / 134 s). The `Tq` values are
identical to the unit at the same second in both arms (22, 576, 670, ...,
348 at 3-20 s), so the guest's frame sequence is deterministic across the
390 commits and the collapse is not a count of anything the guest does more
of.

**Consequences.**

- The section-5 hunk (keep the page armed; tcgchurn's hunk (a),
  `HAKUX_TCG311_KEEP_ARMED`) is **predicted to fail its gfps leg**: it
  removes the walks that `pr` counts, and A already ran with 14-36 of them per
  frame and collapsed on the same curve as B with 76-218. Removing 29 walks a
  frame cannot recover 350 ms a frame unless each costs 12 ms, and then B
  would be at 2.6 s a frame, which it is not.
- What survives of the model is only its shape: a per-call cost that grows
  with a caller count that does not. The callee both entry points share is
  `tlb_reset_dirty_range_all` (system/physmem.c:1008), which
  `physical_memory_test_and_clear_dirty` calls whenever a query finds a
  dirty bit (physmem.c:1277), for every client. The second caller is the
  texture poll: `check_texture_dirty` (hw/xbox/nv2a/pgraph/vk/texture.c:534)
  issues `Tq` = 550-950 queries per frame, 3-20x more than the code re-arms,
  identical in both arms. Only the queries that find a bit walk, and nothing
  counts those.
- The TLB-size model is **not measured**, and lane.perfbase's Crimson profile
  (#68, 23:53 UTC) gives a reason it may be dead: no CR3, CR0/CR4 or INVLPG
  flush was sampled. The dynamic TLB resizes only at a flush
  (`tlb_flush_one_mmuidx_locked` -> `tlb_mmu_resize_locked`), so a guest that
  never flushes has a TLB that never grows, and then no walk grows either.

### Pre-registered for lane.tcgchurn's counter arm (709cfb13aa, queued)

Its `[tlb68]` line carries `tn` (current TLB entries) and `rs` (resizes):

- model alive: `tn` at 120 s >= 8x `tn` at 20 s and `rs` > 0; then hunk (b)
  (`HAKUX_TCG311_TLB_BOUND`, cap 2^13) recovers gfps >= 25 and hunk (a) does
  not.
- model dead: `rs` = 0, or `tn` within 2x, while gfps collapses. Then no
  counter we have names the growth, both hunks fail, and the only remaining
  instruments are the bisect (section 7) and a simpleperf guest-thread
  profile at 20 s vs 120 s, which only the host can take
  (`docs/testing/perf/profile_guest.sh` drives adb directly).

## 7. Since when: the host's bisect driver, and my reads of its probes

`host-tools/bisect311.py`, state in `hakux-work/bisect311/state.json`. Its
judge is the `hakuX-perf` median, but the **pacing line (33557e82ab) and the
pages line (9e2f61dac5) were both added on 09-11, after the whole window**, so
every probe in it runs 60 s with a frame every 10 s and is judged by the FPS
overlay in the frames. A good build's counter curve cannot be read from any
window probe; the confirmation pair on master (section 8) is where the
counters land.

| round | ref | date | read | verdict |
|---|---|---|---|---|
| bracket | e64e336d27 (0.3.1) | -- | host: 29 fps at 45, 130, 190 s | good |
| 1 | aeb4a096b6 (v0.4.0-j1) | 09-10 | host hand verdict | bad |
| 2 | 7d60ea3648 (probe commit 85e3550b0d) | 09-10 | FPS 6 at 60 s, comic page 1 blank | bad |
| 3 | 9094472fae | 09-08 | FPS 29 at 50 s and 60 s, comic on page 2 at 60 s | **good** (my read, 00:05 UTC) |

The comic's page is a second witness: at the same wall-clock second a good
build is further into it. Every bad run reads <= 7 by 35 s.

Window after round 3: `9094472fae..7d60ea3648`, 31 first-parent commits, no
TCG or i386 change among them (the only accel/tcg touches are a meson line
and a one-line mttcg build fix). The code-changing ones, first-parent order:
b831942974 (glsl bump border), 4f6990c81e (vk: signedness in the sampler),
2d0dadc0e0 + fcb43fc7e2 (net zero), 21cacb354a (vk: a retired surface
writing over memory the guest took back), f81d0fa448 (R6G5B5 decode),
f69f2fd8e1 (unimplemented surface formats), cd98400d03 (vk: bound surface
invalidated undirtied), 23a8962df2 + a33fa42bc3 (depth encoding and scale),
and the side branches of the merges 7283070f5c, ad5edf0897, 7d60ea3648.
Not picking among them; ~5 halvings left.

## 8. The confirmation A/B, prepared (register when the driver names the culprit)

Template: `docs/lanes/ghoul311/culprit-ab.json.template`. Two pairs, both
240 s hands-off on one device, `#311 bisect` in the purpose:

1. `culprit^` vs `culprit`, frames every 10 s (no pacing line in the
   window): overlay >= 25 at 50, 60, 90 and 120 s on `culprit^`, <= 8 from
   60 s on `culprit`. Repeated once.
2. `master` vs `master + revert(culprit)`, frames every 0: median gfps 90-240
   s <= 5 on master and >= 25 on the revert; and the pages/pacing counter the
   culprit implies, stated before the arm. Must-not-move: Spikeout and
   RalliSport 2 gfps, and the pgraph suites via `ab_compare` (a revert of a
   rendering fix moves pixels, and then the revert is the diagnosis, not the
   fix).

## What the next lane should not repeat

- Do not model from one arm. Section 1 charged the excess frame time to the
  re-arm walk because `pr` was the counter that rose; the second arm showed
  the same collapse at a seventh of the count.
- The bisect window (09-08..09-10) predates every counter line; do not queue
  a window probe expecting a `hakuX-pages` or `hakuX-perf` curve.

- `docs/testing/perf/profile_guest.sh` drives the device with adb directly;
  a lane cannot use it, and the dispatch soak path has no simpleperf hook.
  The pages windows (per 120 frames) are the profiler available to a lane.
- Do not read the pages `n=` per-page counts as per-window: they are
  cumulative (never reset), so difference them.
