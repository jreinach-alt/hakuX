# p6vtxstale1022: bring a frame slot's vertex RAM current by page, not by span, on current master (#1049, #433)

State: draft

Lane: p6vtxstale1022          Issue: #1049 #433 (0.5)
Base: master @ b944110629
Files: docs/lanes/p6vtxstale1022/PR.md, docs/lanes/vtxstale1018/{PR,NOTES,FINDINGS}.md,
hw/xbox/nv2a/pgraph/vk/{vertex.c,draw.c,renderer.h,buffer.c,vtxstale.h},
docs/testing/jobs/selftest.d/99-vtxstale-pages.sh
Prediction: on Fable, `[dipwin]` stale ms/flip falls from ~5 to under 0.2 and PFIFO `tcpu` falls by about the same.
  Falsified when `STALE_B`/flip does not fall, or a pixel diff exceeds the A-vs-A floor
Needs device: yes, at its turn (below)
Needs NDK: yes
Selftest: 99-vtxstale-pages

fps30 PLAN.md item P6. It is staged now so that when its turn comes it costs one rebase, one build and one A-B-A.

## What this branch is

The four commits of lane/vtxstale1018 (be379c5b7e f3bd1ea198 2173daadf2 4507b8f2fa), cherry-picked onto master
b944110629. lane/vtxstale1018 and lane/fpsnext1019 are never folded; this branch is the only way the change
reaches master.

There was one conflict, in `pgraph_vk_finish()`'s rotation block (draw.c). Since vtxstale1018 branched, master
added the `[dipwin]` timing around the old span memcpy. The resolution keeps the page-bitmap copy and moves the
timing onto it, the same way lane/fpsnext1019's merge 326bfebadb did:

```c
                    bitmap_clear(next_fs->vertex_ram_stale, 0,
                                 r->bitmap_size);
                } else {
                    size_t lo, hi;
#if NV2A_PERF_LOG
                    DW_T0(dw_s0);
#endif
                    size_t copied = vtxstale_copy(
                        next_fs->vertex_ram.mapped, cur_fs->vertex_ram.mapped,
                        next_fs->vertex_ram.buffer_size,
                        next_fs->vertex_ram_stale, r->bitmap_size, &lo, &hi);
#if NV2A_PERF_LOG
                    DW_T1(stale, dw_s0);
                    DW_ADD(STALE_B, copied);
#endif
                    if (copied) {
                        next_fs->vertex_ram_flush_min = lo;
                        next_fs->vertex_ram_flush_max = hi;
                    }
                }
```

If a later rebase conflicts in the same block, this is still the resolution. No other file conflicted, and no
`vertex_ram_stale_min/max` reference is left anywhere.

Checked 2026-10-22 on this tree:

- draw.c, vertex.c and buffer.c pass `-fsyntax-only -DNV2A_PERF_LOG=1` with the desktop compile flags.
- `SELFTEST_ONLY=99-vtxstale-pages`: 14 passed, 0 failed. That covers 3014 rotations with 0 missed bytes (118.5 MB
  copied by page against 891.6 MB by span), and all six mutants caught.

## What is already measured (do not repeat)

- **Correctness.** The selftest above. It cuts the marking loop and the rotation block out of the tree as they
  stand, so it tests the resolved code, not a copy of it.
- **GTA III, driving, before P1** (lane/fpsnext1019 NOTES, "Attempt 8", same code via 326bfebadb).
  - Mechanism confirmed: `stale` fell from 3.60-3.88 to 0.05 ms/flip.
  - fps falsified: total ms/flip went from S mean 47.4 to C mean 50.9, and `rotfen`/`fin_stalled` rose
    +5.2 to +7.3. The frame was GPU-bound, so the saved CPU time went into the fence wait.
  - Pixels: S1-vs-C2 0.2, the S1-vs-S2 floor; C1 1.2, at the floor + 1.0 bound.
  - Stability: passed.
- vtxstale1018's own on-foot after-run (1792342997-vtxstale1018-1009067) was withdrawn and never ran.

**There is no switch.** PLAN.md P6 names `HAKUX_VTX_STALE`, but it does not exist; the change replaces the span
copy outright. Every A/B is two refs: A = master, B = this branch rebased onto that master.

## When it goes, and how it is judged

1. **Its turn is PLAN.md 3.2 step 4:** after P1, P5+P2 and P3/P4/P7, folded or falsified.
   - On GTA III/SA it is measured only after P1 is in for that title. Before P1 it is absorbed, as shown above.
   - Fable is its first title. Fable's PFIFO CPU is already at the bar (`tcpu` 27.6-31.5 ms) and the copy there
     is 24-51 MB/flip, about 5 ms.
2. **Rebase** onto the master of that day, then rerun the syntax check and the named selftest.
3. **Push** the branch to origin (`offline-git/hakuX.git`), so the dispatcher can build the B ref.
4. **Queue** Fable, `gen-fable`, 900 s, `--perflog`, Nova, as A1 (master) / B (branch) / A2 (master).
5. **Fold rule.** Fold by hand (`offline_fold.py`, then `dispatcher_update_window.sh`) when all of these hold:
   - `STALE_B`/flip falls.
   - The pixel diff is within the A1-vs-A2 floor + 1.0.
   - There is no `DEVICE_LOST`/`FATAL`.
   - ms/flip is not worse than A by more than the A1-vs-A2 spread.

   If ms/flip is worse by more than that spread, do not fold: that is the lost-overlap cost fpsnext1019 saw, and it
   goes to `rotfen` analysis, not into master.
6. GTA III, after P1 is in for it: one owner-driven in-car capture on the folded build. Read whether `rotfen`
   still absorbs the saving now that the frame is balanced.
