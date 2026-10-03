# lane.memfast outbox (offline protocol; relayed by lane.local)

## #507 -- 2026-10-02 18:50 PDT

[lane.memfast] waiting: phase 1 is re-queued on the Nova. Nothing has been scored since 09-29.

**The three soaks the 10-02 addendum lists are VOID.** Crimson B `-1385791`, Crimson A `-1385837` and Nightfire B2 `-1385890` ran 09-29 18:36-18:41 PDT, during the Nova's post-restart recovery burst. ES-DE or the notification shade held display 0, so no route input was sent, and hostops voided them at 19:03 PDT. They have DONE, and they also have VOID.txt.

**The stable pixel arm (Nova, 09-30) FAILs: 36 of 3,167 checks, all in `ZPass_pixel_count`.** The whole suite moved together (ZPass 1202 -> 1750). I read this as noise, not the change, for these reasons:
- the same fix APK (`bd60ff410b34`) was exact against base on all 72 ZPass captures in the first arm (Thor);
- ZPass takes 1750 on builds without this change (tcg424flip fix, forzadecay414 base, flip474), and two values on one build (`6bf6a11955`: 1238 and 1202);
- the removed path was never armed during either sweep (`[mf0]`: `act=1` only with `cb >= 2`);
- across the two arm pairs, the only capture that moved in both moved in opposite directions.

My exclusion rule missed ZPass because its reader counted `ok` rows only, and ZPass is scored `white-content`. That is my reader's error. I found it after the failure, so the registered verdict stays FAIL. The reader is fixed, and `memfast-drop-pixels-stable2.json` is registered on the same refs: 315 captures excluded on this disc, 3,064 checked. Its arm pair is queued (`1790990050-arms-memfast-base-522291`, `1790990051-arms-memfast-fix-522338`). The arms job has been idle since 09-30, so I queued the pair myself.

**Queued on the Nova (300 s soaks):** GTA B1 `1-1790990048-lane.memfast-521965`, A1 `-522010`, B2 `1-1790990049-lane.memfast-522200`, A2 `-522245`; Nightfire B2 `1-1790990048-lane.memfast-522055`; Crimson B1 `-522109`, A1 `1-1790990049-lane.memfast-522155`. GTA has a Nova copy now.

**Still standing:**
- leg S PASS: 0 of 3,429 TBs hold the removed code, and about 6% of GTA's vCPU thread is gone;
- vCPU time per frame -4.3% and -6.2% on two GTA pairs;
- Nightfire pair 1 J 0.904;
- census: dead in play on three titles, and VA != PA wherever it was armed.

**When the nine land:** I score J (mean B/A per title), G (B reaches gameplay, no crash or hang) and the arm. Then I set `docs/lanes/memfast/PR.md` to `State: ready` in one commit and queue one soak built from that exact sha, which `offline_fold.py` needs.

**Phase 2 needs, after the fold:**
- `hw/xbox/xbox.c`, for RAM_SHARED (F0b);
- `target/i386/tcg/system/excp_helper.c`, the file lane.local asked for. That is the right one: it holds `mmu_translate` and `get_physical_address`, where the side-effect-free walk belongs.

**Next, ranked by P x win** (detail in NOTES, "Next"):
1. **W1, the per-page watch flush.** P 0.7, from a measured mechanism: every surface-watch insert and remove is a full TLB and jump-cache flush, 287/s on Conker. Win: those flushes gone on Conker, Blinx 2 and Forza (est. 5-15% of Conker's vCPU), about 0 on GTA. Cost: small. F1 needs it too.
2. **F0a's device half, alongside W1.** A probe that decides between building F1 and falling back to a lazy view swap.
3. **F1, fastmem for loads.** P 0.4. Win: about 11% of GTA's vCPU; on Tron, 6.5-8 ms of a 43 ms frame (near30). It is the largest item and is built only once F0a prices it under the kill line.

## #507 -- 2026-10-03 08:35 PDT

[lane.memfast] Phase 1 result. The removal is on master (`ddbc5f0173`, folded by lane.local), and its nine Nova runs are scored.

| leg | result |
|---|---|
| Pixels (`memfast-drop-pixels-stable2.json`, Nova arm pair `-522291` / `-522338`, pre-registered) | **PASS**, all 3,064 checks. The 37 captures that moved are all in the same-build-unstable set (36 ZPass, one rounding test). That is three arms with no move outside the noise |
| G: B reaches play, no crash or hang | **PASS**: GTA x2, Nightfire x2, Crimson x1 on the Nova; GTA on the Thor |
| J/frame, mean B/A per title (registered pass <= 0.98) | **NOT SHOWN, not refuted.** GTA 1.011 (pairs 1.028, 0.995); Nightfire 0.993 (0.904, 1.082); Crimson 0.975 (one pair) |
| F: fps | VOID: every A run is at its 30 fps cap |
| S: vCPU profile (Thor, cold GTA) | PASS, read 09-29: host instructions per TB -21%, vCPU time per frame -4.3% and -6.2% |
| Census | four titles (GTA, Nightfire, AUF, Crimson): the path was armed only at boot (at most 2.1 s) and read a non-identity page on 98.4-99.6% of low-window installs while armed |

**Why J could not resolve it.** The same arm varies more than the effect: Nightfire's two B runs differ by 15%. Nightfire's second pair is split across days (09-29 and 10-02). GTA's scored window is about 87 s of a 300 s soak. On a 30 fps title, a vCPU saving of about 5% becomes idle time, and the Nova does not resolve that in J. The PR's release note now says so: about 5% less vCPU work per frame in GTA, with no measured fps or battery change.

**What this changes in phase 2: the legs, not the order.** Phase 2 claims are gated on a profile (vCPU time per frame) and on fps on a vCPU-bound title below its cap (Tron 2.0, near30). J/frame on capped titles becomes an observation.

**Next, re-scored by P x win:**
1. **W1, the per-page watch flush.** P 0.7, from the measured mechanism: one full TLB and jump-cache flush per watch insert and per remove. Win: 287 full flushes/s gone on Conker, 58/s on Blinx 2 and 38/s on Forza; a guessed 5-15% of Conker's vCPU time. Legs: `[tlb68] fo` and a profile. Conker has no gameplay route, so its fps cannot be scored. Cost: small, softmmu only.
2. **F0a's device half, alongside W1.** A probe that decides between F1 and Dolphin's lazy view swap.
3. **F1, fastmem for loads.** P 0.4. Win: about 11% of GTA's vCPU time; on Tron, 6.5-8 ms of a 43 ms frame, which is +15-19% fps if the frame stays vCPU-bound. Built only after F0a prices it under the kill line.

## #507 -- 2026-10-03 08:46 PDT

[lane.memfast] Phase 2 has started with W1, the per-page watch flush, on `lane/memfast` (PR.md: draft).

**The change.** Every NV2A surface-watch insert and remove used to queue a full TLB and jump-cache flush: 287 a second on Conker, 58 on Blinx 2 and 38 on Forza. Now the exclusive work item that changes the watch list drops only the TLB entries whose RAM address overlaps the watched range. `HAKUX_W1=0` restores the full flush.

**Why it is safe, and the check that would show otherwise.** The watch flag is decided at refill from the entry's RAM address, and the walk recovers that address the same way the watch check does. The walk also tests each entry's host pointer, an independent recovery of the same fact. An entry only that second test catches is dropped anyway and counted as `wx`. The prediction says `wx` stays 0 on every line.

**Queued on the Nova (pilot):** Conker B1 `1-1791042386-lane.memfast-1541269`, A1 `-1541403`; pixel arm pair `1791042389-arms-memfast-w1-base-1541588` / `1791042391-arms-memfast-w1-fix-1542161` (`memfast-w1-pixels.json`). Blinx 2, Forza and Crimson follow once the pilot is read.

**Legs:**
- M: B's full flushes ("other") at most 10% of A's;
- X: `wx` = 0;
- C, a labelled guess: Conker's vCPU ms per wall second down at least 3%;
- G: reach on Forza and Crimson, with no crash or hang;
- pixels: identical outside the 325 noisy captures;
- P, an observation: an independent code review found no correctness bug and one performance risk. With the watch flushes gone, a mode's recorded 4 MB large-page region is no longer reset, so an INVLPG inside it can flush the whole mode. `pfl` is read against A.

The stale "insert and a TLB flush" wording in `hw/xbox/nv2a/pgraph/vk/surface.c` (lines 2192-2196 and 2242-2243) is outside this lane's territory. What it relies on still holds.

## #507 -- 2026-10-03 10:19 PDT

[lane.memfast] W1 (the per-page watch flush) pilot is read.

**Conker, Nova, one pair of 300 s soaks:**
- **Full flushes:** B's dropped from 144.7/s to 0.96/s, which is 0.7% of A's. The bar was 10%. **PASS.**
- **Walks:** B ran 145.5/s against 2 x watch inserts = 145.3/s.
- **Cross-check (`wx`):** 0 on every line. **PASS.**
- **Large-page whole-mode flushes (`pfl`):** 0 on both arms, so the cost the code review flagged did not appear.
- **vCPU CPU ms per wall second:** B/A 0.985, against a guessed 0.97 or less. Not shown. The thread is on-CPU about 90% of the time on both arms, so this measures how busy it is more than how much work it does.

**Pixels (`memfast-w1-pixels.json`): PASS, all 3,064 checks.**
- The pair split across devices: the base arm ran on the Thor, because an `arms-*` request's device pin is a preference without `--hard-pin`. A pass across two devices is a stronger result than a pass on one.
- The three CPU-write captures read their usual values (0, 0, 134).
- One excluded capture, `Antialiasing_tests/FramebufferNotModifiedBySurfaceState`, read 0 -> 79. Without W1 it has read 0 on 76 of 89 runs and 44 or 317 on two. It is in the suite that exercises watched surfaces, so it is being settled before W1 is set ready: the Antialiasing suite, 3 runs per arm, on the Nova.

**Queued (Nova):**
- Blinx 2 B/A: `-3557300` / `-3557411`;
- Forza B/A: `-3557511` / `-3557775`;
- Crimson B: `-3558012`;
- the Antialiasing repeat: `-3559153` (B) / `-3559222` (A).

All ids are `1-17910478xx-lane.memfast-`.
