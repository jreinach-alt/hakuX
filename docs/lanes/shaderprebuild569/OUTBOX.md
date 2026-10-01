# lane.shaderprebuild569 outbox (offline; relayed by lane.local)

## #569 -- 2026-09-30 12:50 PDT

[lane.shaderprebuild569] waiting: on the Nova, for the DOA two-launch pair of P3 (the pipeline pre-build). They are `1790791301-shaderprebuild569-118449` (L1) and `1790791306-shaderprebuild569-118725` (L2), both at 54865a3521 and queued behind five release-priority Nova requests. The PR is `docs/lanes/shaderprebuild569/PR.md` on `lane/shaderprebuild569` (`State: draft`).

**Item 5, read before building anything: in sync mode, the default, the pipeline cache is saved during play and works on the next launch.** The plan's grep for "Saved pipeline cache" finds nothing because that log line is compiled out on Android. The `[shd413]` line's `W=` field, the save count, climbs in all 224 soak and arm logcats since 09-28. A later launch on the same apk loads the file. Arctic Thunder on the Nova spent 4,661 ms in 43 pipeline creates cold, and 1-2 ms on the same 43 in each of the next three launches.

What does lose the warm state:
- async mode, which never saved during play;
- the last 30 s of a session;
- a driver update, which wiped every cache;
- any update that changes the shader generators. The SPIR-V changes, so every driver cache entry misses.

Turnip also never sets the creation-feedback cache-hit bit (`dfbh=0` everywhere), so a hit shows only as time.

**Built (54865a3521):**
- three compile workers, with pipeline jobs first;
- each monolithic pipeline a title creates is recorded per title, keyed by default.xbe's title id read from the disc;
- at the next launch those pipelines are rebuilt on the workers into the Vulkan pipeline cache in the background, behind any draw-path work;
- the cache is saved from a worker when the app pauses, after a load, at most every 30 s, and after a pre-build;
- a driver update now keeps the SPIR-V and key files.

**Proof:** each launch runs with the pipeline cache file removed at start. Launch 2's recorded pipelines can then only be warm if the pre-build made them warm, which is the plan's W4 falsifier. Legs: W4 known-pipeline create <= 0.10 x cold; W1 whole run <= 0.25 x; W1b first fight load <= 0.25 x; W2 pre-build done before `mark booted`; W3 boot gfps >= 0.90 x. The judge is `docs/lanes/shaderprebuild569/pbjudge.py`. Kabuki follows once DOA is read, because it needs the pilot verdict.

## #569 -- 2026-09-30 17:35 PDT

[lane.shaderprebuild569] waiting: on the Nova, for the Kabuki two-launch pair of P3 at 262e30e6de. They are `1790814605-shaderprebuild569-748505` (L1) and `1790814611-shaderprebuild569-750364` (L2), queued behind two Nova requests. 262e30e6de merges master after lane/uberspike569-gpl folded.

**DOA's pair has run. The pre-build works; one load leg failed because the route reached a different fight.** Both launches ran with the pipeline cache file removed. Launch 2 rebuilt launch 1's 640 recorded pipelines on three workers in 57 s, finishing 9 s before the intro ended, with no change in intro fps (59 vs 59).

| leg | launch 2 vs launch 1 | verdict |
|---|---|---|
| W4: create time of a recorded pipeline with no cache file | 32 us vs 171 ms per pipeline | PASS |
| W1: total pipeline-create time in the run | 12.6 s vs 108.9 s | PASS |
| W1b: the first fight load | 3.16 s vs 2.74 s | FAIL |
| W2: pre-build done before the intro ends | 9 s before | PASS |
| W3: intro fps | 59 vs 59 | PASS |

W1b failed because the two launches loaded different fights. DOA's route presses START/A blind, and the frames show launch 1 fought Zack and then Helena, while launch 2 fought Bass. Every one of launch 2's 131 creates after that point was a pipeline launch 1 never made. No pipeline that had been recorded was slow at any point. Kabuki's route is fixed, so it gives the like-for-like reading.
