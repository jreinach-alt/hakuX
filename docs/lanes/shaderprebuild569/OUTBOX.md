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
