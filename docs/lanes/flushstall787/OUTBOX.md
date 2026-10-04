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
