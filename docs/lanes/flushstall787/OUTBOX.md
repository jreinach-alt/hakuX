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
