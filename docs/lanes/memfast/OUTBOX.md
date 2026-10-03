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
