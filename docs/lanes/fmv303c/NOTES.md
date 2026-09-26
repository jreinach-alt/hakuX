# lane.fmv303c -- #303 Spikeout FMV green: the surface write-back probe

Continues lane.fmv303b (docs/lanes/fmv303b/NOTES.md s4, s5). What is settled
there is not re-measured here: the green (Cr=0) is already in the CPU-written
A8R8G8B8 guest buffers at 0x307d000 / 0x3163000; display, upload, PVIDEO and
Tier1 are exonerated.

## Why attempt 1 did not finish

It was stopped by hostops at about 13:4x PDT on 2026-09-26 under the 0.5
release policy (#433: the device is pointed at 0.5 issues, and #303 is not
one). The probe commit was pushed and CI went green on it; the PR was
labelled `blocked:after-0.5`. The judge (`wb_judge.py`) was written and
tested against fixtures but not committed, and no prediction was registered,
so nothing was queued. Attempt 2 (handback resume) found 0.5 still open,
merged master, committed the judge and these notes, and did not register the
arm: committing a prediction queues it on the device, which the park forbids.
Attempt 2 did finish, as blocked (PR comment `[lane.fmv303c] blocked:`); the
handback job resumed it on the quiet clock at 23:55Z. Attempt 3 found #433
still open and the `blocked:after-0.5` label still on #439; master (110
commits ahead, #396 folded) merges clean against this branch, so the merge is
left to the arm step, where it has to precede registration anyway.

## What the branch carries

1. `hw/xbox/nv2a/pgraph/vk/surface.c`, probe hunk only (b86f91641b), gated on
   `HAKUX_FMV303_PROBE=1`. It logs
   `[fmv303] wb addr= len= color= fmt= ft= n= in= path= surf= WxH` at the
   synchronous copy in `download_surface_to_buffer()` (`sync`, `sync-part`)
   and at each staged copy in `pgraph_vk_complete_staged_downloads()`
   (`staged`, `staged-part`); `ft` is `pg->frame_time`, the guest flip count.
   Every landing in 0x3000000..0x3400000 is logged; landings elsewhere up to a
   cap of 20000 lines. One `[fmv303] wbc ft= n= in=` line per flip stall
   (`pgraph_vk_prerecord_display_download`) carries cumulative counts, so a
   zero is an observed zero and a line logd dropped shows as a gap.
   Unset, the only code that runs is `fmv303_wb_on()`, which reads the env
   once. CI green on b86f91641b.
2. `wb_judge.py`: joins the `wb`/`wbc` lines to the fmv303b `tex0 tint` lines
   by flip count. Validity per run (else VOID): probe on, `wbc` present, last
   `wbc` n > 0, >= 100 lit tinted frames, no in-region `wb` line dropped.
   Verdict pooled over two valid runs: EXONERATED (no in-region landing),
   HIT (P(join | tinted) - P(join | clean) >= 0.5 for NEAR, a region landing
   within 2 flips, or SINCE, a landing on the displayed buffer since it was
   last shown), else UNORDERED.

   Fixture check (synthetic `wb` lines injected into the fmv303b soak logcat
   `0-0-y-1790433000-1790433159-fmv303b-2432336`, 3100 tinted / 274 clean
   lit frames):

   | fixture | in-region landings | NEAR t / c | SINCE t / c | verdict |
   |---|---|---|---|---|
   | none | 0 | 0.000 / 0.000 | 0.000 / 0.000 | EXONERATED |
   | onbuf (on shown buffer before tinted only) | 3100 | 1.000 / 0.978 | 1.000 / 0.000 | HIT |
   | otherbuf (on the other buffer) | 3100 | 1.000 / 0.978 | 0.839 / 0.555 | UNORDERED |
   | all (every frame) | 3498 | 1.000 / 1.000 | 1.000 / 1.000 | UNORDERED |

   NEAR alone cannot separate states here: clean frames come singly between
   tinted runs, so a 2-flip window nearly always reaches a tinted neighbour
   (0.978 on clean). SINCE is the join that discriminates.

## Per-run table

| run id | apk_sha | lit tinted | wbc n | in-region | verdict |
|---|---|---|---|---|---|
| (not run: parked under the 0.5 policy) | | | | | |

## Next, after 0.5 ships

1. Merge master (and `origin/lane/blinx372d` if #396 has not folded; it also
   touches surface.c). Register `docs/testing/predictions/fmv303c-wb-probe.json`
   with `ab_compare.py --register` on the post-merge refs, two Thor runs,
   hands-off, `HAKUX_FMV303_PROBE=1`; must-not-move: pgraph suites and
   Surface_* rows with the variable unset.
2. HIT: name the surface binding whose write-back lands on the shown buffer
   and why it is still dirty; fix it in a second surface.c hunk, registered
   before measuring. EXONERATED (with `wbc` showing write-backs elsewhere):
   probe the APU and IDE DMA landing sites, then fmv303b NOTES s5 step 2b.

Do not repeat: the Tier1 on/off A/B (settled, 0.688 vs 0.680).
