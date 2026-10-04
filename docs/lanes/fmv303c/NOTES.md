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

Attempt 3 did not finish for the same reason: it ended parked, by policy,
with nothing registered. Nothing failed. On 2026-10-04 the owner lifted the
park (brief addendum 3): the green is on a Playable title's pre-game screens
(Spikeout) and also on Star Wars III (#719). Attempt 4 merged origin/master
(1964 commits; one conflict in `pgraph_vk_prerecord_display_download`, where
master removed the early `display_predownload_pending` return; resolved by
keeping the `wbc` counter call first and master's body unchanged:
cf328d86f7). Master's new deferred-download batch completes through
`pgraph_vk_complete_staged_downloads()`, which the probe already covers. No
other copy into VRAM exists in `vk/`. Attempt 4 re-ran the judge's fixtures
(same four verdicts), registered
`docs/testing/predictions/fmv303c-wb-probe.json` on cf328d86f7 (86f8cace9d),
and queued both Thor runs.

Attempt 4 did not finish because both Thor runs were refused before start.
A foreign overlay covered the Thor's display (below). The session ended
waiting on `time 2026-10-04T13:40` to re-queue. Brief addendum 4 then said
two things. First, the owner left the overlay there from their own
bottom-screen test, and the lane must not ask for it to be cleared. Second,
the green was seen on the **USA** disc. The Europe disc named in the first
registration was wrong.

Attempt 5 (13:45 PDT, 2026-10-04) re-registered the prediction before any
run, on the same ref cf328d86f7, with the USA disc. It also added one M0
rule to `wb_judge.py`. The probe logs every landing only inside
0x3000000..0x3400000, and the USA build may place the FMV buffers
elsewhere. That case would read as a false EXONERATED, so the judge now
VOIDs a run where more than 10% of lit tinted frames show a buffer outside
the region. In the fmv303b control, 1 of 3100 lit tinted frames does
(0x3628000). That is why the rule is not "any". New fixture `outside` (the
control with its buffers moved to 0x1xxxxxx) gives VOID; the other four
fixtures give the same verdicts as before. Then it queued both runs again.

Attempt 5 did not finish because the USA pair was refused by the same
display cover (rows below). It parked on `WAITING: owner`. At 14:4x PDT
lane.local cleared the cover. The cause was the SYSTEM key
`dual_screen_display_mode=2`; hostops had reset only the global key.
lane.local set the system key to 0. Attempt 6 (14:38 PDT) deleted WAITING
and queued the same two runs unchanged: ref cf328d86f7, prediction sha
6b933f61..., USA disc.

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
| 1791142591-lane.fmv303c-697274 (L1) | 3ecdda7c45e7 | - | - | - | VOID: refused, display-covered |
| 1791142595-lane.fmv303c-698913 (L2) | 3ecdda7c45e7 | - | - | - | VOID: refused, display-covered |
| 1791146938-lane.fmv303c-1371607 (L1, USA disc) | 3ecdda7c45e7 | - | - | - | VOID: refused, display-covered (13:49 PDT) |
| 1791146942-lane.fmv303c-1372235 (L2, USA disc) | 3ecdda7c45e7 | - | - | - | VOID: refused, display-covered (13:50 PDT) |
| 1791149862-lane.fmv303c-2094485 (L1, USA disc) | | | | | queued 14:38 PDT, cover cleared |
| 1791149866-lane.fmv303c-2096647 (L2, USA disc) | | | | | queued 14:38 PDT, cover cleared |

The first two rows were registered on the Europe disc, which was the wrong
disc, and are superseded. The USA pair was refused by the same guard
(`display-covered: ... primaryScreenTopLayout (com.odin.dualscreen.assistant,
BOOT_PROGRESS)`). Nothing was started, and no logcat or frames were
produced. The guard (`soak_title.sh` / `devices.sh display_clear`) has no
override that a request can pass. Brief addendum 4 says the overlay is the
owner's own and the lane must not ask for it to be cleared. So attempt 5
parks with `WAITING: owner`, and lane.local takes the question to the owner.
The question: either clear the overlay on the idle Thor, or let the guard
accept it when the soak draws on the top screen. Once either happens, the
same two requests can be queued again unchanged: same ref, same prediction
(sha 6b933f61...). A void whose named cause is the device state, not
performance, allows a retest.

Both refusals (2026-10-04 12:3x PDT) come from one device state, with a
named cause that is neither a performance nor a code problem. run.log says
`display-covered: a foreign full-screen overlay covers display 0 on
bdc158a5: primaryScreenTopLayout (com.odin.dualscreen.assistant,
BOOT_PROGRESS)` and `soak refused ... nothing was started`. The runs logged
0 logcat lines and one all-black 10,899 B frame. This is the 09-27 cover:
`harness_health.py`'s `covered:` check names `dual_screen_display_mode=2` as
the root cause, and hostops' fix is `device_reality.sh --fix`. The owner
hand-tested Spikeout on the Thor earlier today, which plausibly left the mode
set. The lane does not touch the device. It re-queues the same two runs (same
ref, same prediction) once the cover is cleared. The requeue is allowed
because the void cause is named and is not a performance miss.

Both runs: ref cf328d86f7, Thor (hard pin), Spikeout, 150 s, frames every 2 s,
`HAKUX_FMV303_PROBE=1`, hands-off. Prediction: EXONERATED, P about 0.65 (a
write-back lands whole surfaces, all four bytes; the green is one zeroed
chroma component).

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
