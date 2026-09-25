# #68: translation-cache churn: why the guest thread spends a third of its time maintaining the cache

Lane: tcgchurn            Issue: #68 (also #73)
Base: origin/master
Files: accel/tcg/cputlb.c, accel/tcg/tb-maint.c, accel/tcg/translate-all.c, accel/tcg/cpu-exec.c,
target/i386/helper.c, target/i386/tcg/**, docs/lanes/tcgchurn/**, docs/testing/predictions/tcgchurn-*.json
Needs device: yes, for counters and the arm (Nova now, Thor after the 0.5 sweeps). Needs NDK: yes.
Prediction: yes, before the arm.

## Why

The 1.0 target is commercial titles at ≥30 fps on our handhelds, and the emulated CPU is the
critical path. The 09-11 guest-thread profile of Crimson Skies' heavy flying
(`docs/testing/perf/run-2026-09-11-crimson-profile-guestthread.txt`; local, gitignored) has these
self-time shares:

| Symbol | Self |
|---|---|
| `tlb_reset_dirty` | 10.68% |
| `tcg_flush_jmp_cache` | 8.37% |
| `qht_lookup_custom` | 5.23% |
| `flush_idcache_range` | 3.90% |
| `helper_lookup_tb_ptr` | 3.87% |
| `tb_lookup_cmp` | 1.96% |
| `notdirty_write` | 1.36% |
| `tlb_set_page_full` | 1.14% |
| `tb_tc_cmp` | 1.12% |

That is roughly 35-40% of the thread doing no game work.
- **The ceiling:** removing all of it is at most ~1.6x on that thread (a bound, not a value).
- **What Crimson needs:** only about 1.25x to hold 30 fps in its heavy scenes (guest busy 41.5 ms of
  a 50.2 ms frame).

**History to read first:**
- #68 and #73's threads, and `docs/investigations/tcg-retranslation-measured.md`,
  `tcg-invalidation-three-arm.md` and `docs/testing/perf/tcg-counter-correction.md`.
- **#73's fix landed:** −85% invalidation visits.
- **#68's range test (`937848c9e7`) is held:** it took walks 2162 → 0 but raised visits 3,605x.
- **The profile predates #73's fix.** lane.perfbase is taking a fresh one at master now. Confirm the
  split against its numbers before you arm anything.

## The job

1. **Two questions, answered with counters before any fix.** Keep the counters cheap, and rate-limit
   your own `hakuX-tlb` log line to one per 2 s.
   - (a) **What triggers the full TLB flushes** that clear the jump cache? Count
     `tlb_flush_by_mmuidx_async_work` by cause: CR3 write (same value vs a new one),
     CR0/CR4 write, INVLPG, anything else. `cpu_x86_update_cr3` is at `target/i386/helper.c:177`.
   - (b) **What drives `tlb_reset_dirty`** (`accel/tcg/cputlb.c:917`)? Count calls from
     `tb_link_page`/`tlb_reset_dirty_range_all` against `notdirty_write`, and the TLB entries walked
     per call.
2. **Name the mechanism per trigger**, from the counts and the guest's own code: disassemble what the
   Xbox kernel or the title runs at the hot CR3/INVLPG sites. Then design a fix for each large
   trigger. Candidates to test, not assume:
   - (i) a same-value CR3 reload used as a TLB-flush idiom, and whether global pages (CR4.PGE +
     PTE.G) make a full flush unnecessary;
   - (ii) a reverse index, so the dirty reset walks only the entries that map the page, not the
     whole TLB;
   - (iii) #68's range test, with its visits regression fixed.
3. **A fix with a registered prediction:**
   - the target symbol's self share drops by a stated amount;
   - Crimson's heavy-flying frame time drops, or its fps windows at target rise, on the same device
     with the same input sequence (`run_perf.sh`, or lane.titlerun's route once folded);
   - **must-not-move:** the reference-title soaks show no new crash or hang, and the pgraph smoke
     suites are unchanged.

   Soak arms are hand-queued (`request.sh --title`, both arms on one device); `arms.sh` does not
   queue soak predictions.

## Correctness

The x86 MMU semantics are the contract: what a flush must invalidate, when self-modifying code must
be seen. Write the argument for each change in NOTES:
- what could go stale;
- why it cannot under your change;
- which guest behaviour would break it.

If a change relies on the guest never doing something, add a runtime check that falls back to the
old path.

## Do not

- **Touch `tcg/**`, `util/cacheflush.c` or `tools/bench/**`.** They are lane.perfarch's, which
  covers memory ordering, codegen and cache-maintenance ISA. Coordinate on #68.
- **Touch `pgraph/profile.c` or `perf/**`.** They are lane.perfbase's.
- **Hold a device** while another lane's request runs there, or for more than 60 minutes.
- **Trigger CI as a self-check.**

## Done when

- #68 carries the trigger counts and the mechanism per trigger.
- A fix PR with an arm verdict is marked ready, or NOTES state why each candidate was refuted.
