## #787 -- 2026-10-03 17:15 PDT

[lane.flushstall787] Step 1 done (instrument), steps 2 queued. **Is it the flush? From the code: a TLB flush
discards no translated block in this tree** (it clears the TLB and the jump cache; blocks are found by physical
address), so "re-translation after the flush" has no mechanism. What a flush really costs the vCPU afterwards is
TLB refills, which run inside TB execution where no counter could see them. Commit 1fe520a709 adds `[tcg787]`
(per `[tlb68]` window: tb_gen_code calls/us/max, generations, blocks discarded, tb_flush count, flush-worker us,
TLB refill count/faults/us) and `[tpc787]` (where TB time goes, by entry pc, duration-weighted).

Runs already on disk, read without device time (NOTES.md section 2):

| | Kabuki 698 ms stall (1791054199-lanelocal-1518681) | Tron stalls (1-1791057797-lanelocal-2547673) |
|---|---|---|
| blocks generated in the stall's 120-frame line | 79 (20-861 over 9 burst stalls) | 15,785-48,572 (7 of 8 stalls) |
| `[rr425]` loop time between TBs (holds tb_gen_code) | 46 + 18 ms | 0.75-5.1 s |
| code-cache flush (tb_flush) trace | none | one, at the 1,762 ms stall |

So the prior is split: **Kabuki's stall is guest-side or TLB refill, not translation; Tron's looks like
re-translation, but from a code-cache flush or code loading, not from a TLB flush.** Two measurement runs on the
same build settle both, predictions registered first:

- Kabuki, the brief's run: `1-1791072687-lane.flushstall787-1209260` (840 s, perflog, GPL=3, Nova),
  `predictions/flushstall787-kabuki.json` @ 08f17e8e: tb_gen_code < 100 ms and the whole flush fallout < 250 ms
  in every burst stall.
- Tron: `1-1791072697-lane.flushstall787-1209966` (750 s, perflog, Nova), `predictions/flushstall787-tron.json`
  @ fc9d4b5e: tb_gen_code >= 400 ms in at least one stall, trigger named by tbf/disc.

## #787 -- 2026-10-03 19:30 PDT

[lane.flushstall787] Steps 2 and 4 done. **Is it the flush? No, in Kabuki or Tron.** Both runs ran on the
branch's perflog build (Nova, apk 66ded35425cd); validity holds in both.

Kabuki `1-1791072687-lane.flushstall787-1209260` (the brief's run, `predictions/flushstall787-kabuki.json`):
**G PASS, F PASS**. Over the 8 stalls >= 400 ms that overlap a `[tlb68]` burst (401-705 ms):

| per stall | min | max |
|---|---:|---:|
| tb_gen_code time (gus) | 5.7 ms | 41.7 ms |
| TLB refill time (tfus) | 8.0 ms | 34.6 ms |
| everything a flush can cost (gus + tfus + flush workers) | 17.5 ms | 83.4 ms |

What the guest runs instead (`[tpc787]`): in quiet windows the title's wait loop at 000a8330 holds 91-98% of TB
time. In every burst-stall window, other guest code takes 0.4-1.3 s of the 2-s window: title x87 routines at
000bb4d2/000bb8fc/000bb9e6 and 000b8fff, and the kernel's memory manager (80014386, INVLPG at 8001fb35, 12-25k
INVLPGs). The stall is the title's own work at a transition, run at TCG speed, and the flush burst is a symptom of
it. One stall (736 ms, no burst) is the guest idle and waiting on the timer. One TCG cost that is not the flush:
000b8fff's TB spans two pages and is never chained, so 1.4-3.8M dispatches per window cost 175-372 ms of loop
time in 2-3 of the 9 stalls.

Tron `1-1791072697-lane.flushstall787-1209966` (`predictions/flushstall787-tron.json`): G holds as worded
(474 ms of tb_gen_code over the 1,732 ms stall), but only as a sum over a 12-s span; per 2-s window it peaks at
189 ms. T is refuted on its trigger: no tb_flush (tbf=0), and generations exceed discards 5-7x, so this is
first-time translation of newly loaded code. F holds: the TLB flush's fallout is 11-117 ms per stall. The stall
windows spend 1.2-1.35 s of 2 s in guest kernel code (80014386, 80027beb-80027c5d) right after the code load.

Per the brief's step 4, no fix. Ranked next steps (NOTES.md 5.3): vCPU execution speed (the only lever on the
whole stall); chaining into two-page TBs (0.2-0.35 s in 2-3 Kabuki stalls); #68 page-range invalidation last
(<= 42 ms here).

## #787 -- 2026-10-04 00:45 PDT

[lane.flushstall787] lane.local's 20:2x items 1-3.

**1. Perflog-only.** Every #787 hook now compiles only when `XBOX && NV2A_PERF_LOG` (`HAKUX_TCG787`), in
7b4ab7823e: the tb_gen_code wrapper (translate-all.c); the full-flush and INVLPG worker timers, the
tlb_fill_align wrapper (count + time) and the `[tcg787]` line (cputlb.c); `tpc787_pc`/`tpc787_book` on the
execution path, `tpc787_tick` and its reset (cpu-exec.c). Checked by symbol, not by reading: `ndk_check.py` builds
each object plain and perflog and counts `tcg787`/`tpc787` symbols with llvm-nm: **plain 0 / 0 / 0, perflog
4 / 20 / 4**. (Its earlier "plain" leg was not plain: the dispatcher's build tree is a perflog build and already
passes `-DNV2A_PERF_LOG=1`; it now strips that.) The plain build is the pre-#787 code path.

**2. Head run queued**: `1-1791098627-lane.flushstall787-847488`, Kabuki, route `kabuki-warriors`, 840 s,
`--perflog`, HAKUX_GPL=3, Nova, release tier, ref 0b8b63bef1 (the branch with origin/master 4991143fde merged).
No prediction (the answer was judged on 1fe520a709); what it must show: `[tcg787]` and `[tpc787]` on every
window and `fs_judge.py`'s validity V1-V5.

cputlb.c: origin/board retires `[lane.memfast]` (files released, cputlb.c granted to this row), and memfast's
own head (b41a8e4c2f, 00:08) closed its F1 PR with F1 rejected, so there is no memfast fold to wait for. WAITING
names only the run.

**3. Chaining two-page TBs, priced by title.** `fs_gs_scan.py` reads `[rr425]` gs (dispatches into a TB spanning
two pages, which `cpu_exec` never chains into) from every run on disk with `[rr425]`: 590 runs, 141,041
windows, 6 titles with any window at gs >= 1M.

| title (runs) | windows with gs >= 1M | loop gap there vs other windows |
|---|---:|---|
| Tony Hawk's Pro Skater 2x (8) | 504 of 1,321 (38%) | 1.0-1.6 s vs 25-32 ms per 2-s window |
| Kabuki Warriors (44) | 57 of 8,828 | 175-372 ms vs 19 ms (the stalls, 5.1) |
| MechAssault 2 (3) | 15 of 3,177 | 186-230 ms vs 48-158 ms |
| Top Spin (1), Crash WoC (3), Ninja Gaiden (2) | 6, 6, 2 | none measurable |
| every other title (THPS3 included) | 0 (max gs 0.15-0.87M) | -- |

So it touches more than one title, but one carries most of it: THPS2x spends half its vCPU loop time outside TBs
in 38% of its windows (~0.6-1 us per gs there, against ~95 ns in Kabuki, so it costs more than the
dispatch alone, probably the jump-cache lookup each time). THPS2x reads 59.8 fps median with 79% of windows at
its 60 target (targets.toml); Kabuki's stalls lose 0.2-0.35 s in 2-3 of 9 and stay over the 500-ms bar.

P x titles: P(a safe chain is buildable: unlink every jump into a two-page TB on any TLB flush or INVLPG, single
vCPU) ~0.5 x P(the gs cost is what holds THPS2x under 60 in those windows) ~0.4 = ~0.2 for one title's 60-fps
share, plus partial Kabuki stall relief at ~0.5; MechAssault 2 marginal. Expected: ~0.2 titles moved to target,
0 titles cleared on its own. Cheaper first step if wanted: one THPS2x perflog soak to see whether the hot
windows are gameplay and whether they are the sub-60 ones (decides the 0.4). Waiting for lane.local; no work started.

## #787 -- 2026-10-04 00:50 PDT

[lane.flushstall787] Head run done: `1-1791098627-lane.flushstall787-847488` (Kabuki, route `kabuki-warriors`,
840 s, perflog, HAKUX_GPL=3, Nova, ref 0b8b63bef1, the perflog-only hooks). `fs_judge.py`: `[tcg787]` prints on
421 of 421 `[tlb68]` windows (pl=1), V1-V5 hold (tb_gen_code moves: 4 heavy windows up to 167 ms vs 4.5 ms median
quiet; gc/pages calls 1.001). It repeats the answer judged on 1fe520a709:

| | measurement run (1fe520a709) | head run (0b8b63bef1) |
|---|---|---|
| stalls >= 400 ms with a flush burst | 8 (401-705 ms) | 8 (408-689 ms), plus 1 of 640 ms with none |
| worst span tb_gen_code (G) | 41.7 ms, PASS | 60.5 ms, PASS (< 100) |
| worst span flush cost (F) | 83.4 ms, PASS | 100.3 ms, PASS (< 250) |

Not the flush. The PR is ready to fold; WAITING is removed. Two-page TB chaining stays priced (00:45 entry) and
unstarted, waiting for lane.local.
