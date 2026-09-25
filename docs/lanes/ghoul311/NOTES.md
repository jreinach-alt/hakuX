# lane.ghoul311 -- #311 Grabbed by the Ghoulies hands-off fps decay

Status: 2026-09-25 21:15 UTC, waiting on four Nova soaks (section 4).
Diagnosis first; no source claimed.

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

## 5. The fix hunk (named, not applied)

`docs/lanes/ghoul311/fix-keep-armed.diff.txt`: under XBOX, do not
`tlb_unprotect_code` when a page empties (`tb-maint.c:1812-1815`, the only
disarm site). The next `tb_page_add` then finds the code bit still clear and
the walk does not happen. It needs a grant on `accel/tcg/tb-maint.c`
(lane.tcgchurn's). Its arm is master vs master+hunk, predicted from the pair
above once the pair lands.

## What the next lane should not repeat

- `docs/testing/perf/profile_guest.sh` drives the device with adb directly;
  a lane cannot use it, and the dispatch soak path has no simpleperf hook.
  The pages windows (per 120 frames) are the profiler available to a lane.
- Do not read the pages `n=` per-page counts as per-window: they are
  cumulative (never reset), so difference them.
