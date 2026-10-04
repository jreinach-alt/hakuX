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

## #507 -- 2026-10-03 12:35 PDT

[lane.memfast] W1 (the per-page watch flush) is read and set ready.

**Full flushes per second, B (W1) against A (Nova, 300 s soaks):**

| title | B | A | B as a share of A |
|---|---|---|---|
| Conker | 0.96 | 144.67 | 0.7% |
| Blinx 2 | 0.97 | 40.49 | 2.4% |
| Forza (to its crash) | 2.08 | 30.95 | 6.7% |

- **M: PASS** (the bar was 10%). Walks ran at 1.00-1.03 x 2 x watch inserts.
- **X: PASS.** The host-pointer cross-check (`wx`) caught nothing on any line.
- **P: no cost.** The large-page whole-mode flush the review flagged (`pfl`) read 0 on every run, both arms.
- **C: not shown.** vCPU CPU ms per wall second fell only 0.3-1.5%. The thread is on-CPU 85-95% of the time on both arms, so this instrument cannot see a per-frame saving; W1's vCPU win needs a profile.
- **G:** Crimson B reached play (191 s, fps_ok 0.989), and Conker and Blinx 2 ran 300 s with no crash or hang. **Forza is void:** A crashed exactly like B (filed below).
- **Pixels: PASS.** The one open capture, `FramebufferNotModifiedBySurfaceState`, read 0 on all three W1 runs and all three base runs of the Antialiasing suite on the Nova. The 79 on the split arm was its known race.

**Release note (performance):** Conker, Blinx 2 and Forza no longer empty the emulated CPU's address-translation cache each time the GPU starts or stops watching a surface. No fps or battery change was measured, because these titles run at their 30 fps cap.

**Next, after the fold:** F0a's device half (one native test run), which decides whether F1 (fastmem: P 0.4, about 11% of GTA's vCPU time, +15-19% fps on Tron 2.0 if it stays vCPU-bound) is built. NOTES, "Next", item 5 has the ranking.

NEW ISSUE: Forza Motorsport: guest kernel BugCheck 0x7f (double fault) in the menus on the Nova's golden-profile titles disk
Both runs of `forza.drive` on disk crash the guest kernel the same way, on master (5e249bbfe0) and on lane.memfast W1 (1b0f73a8bd): `1-1791047880-lane.memfast-3557775` (A) and `-3557511` (B), Nova, 10-03 12:11 and 12:14 PDT. Signature: `XBOX KERNEL CRASH (BugCheck)`, code 0x7f, exception 8, halt loop at EIP 0x800151ed, CR2 0xd0068ffc, CR3 0xf000, ESP 0x8003a814. It comes about 110-120 s in, while drive.py is on the profile-select (B) or main-menu (A) screen; the route then fails "stuck" because the guest has halted. These are the only Forza kernel crashes among every Forza soak on disk. lane.ibcache's Forza runs on 10-02 (for example `1790929514-lane.ibcache-2992454`, 87b89e857c, a blind START/A route) reached play, before savestate433's golden-profile disks (10-02 20:12). Both crashing runs booted the imported save `a1baf745d557`, and `titlestate.py show --device nova` shows Forza re-imported with that save at 19:16Z, after them. Suspects: the imported profile's content, or drive.py's profile-screen input. It blocks every Forza soak on the Nova (reach, fps and J legs), including lane.memfast's W1 G leg on Forza.

## #507 -- 2026-10-03 19:34 PDT

[lane.memfast] W1 folded (`de396edb2a`). Per the owner's release tonight, F0a's device half and F1 (fastmem, loads only) are built in one commit, `6162792993`, and both are off by default.

- **F0a (`HAKUX_F0A=<s>`)** is a benchmark inside the app: a thread runs it <s> seconds after start, under libsigchain, with the emulator running. It times:
  - a SIGSEGV round trip;
  - map, touch, mprotect and unmap of one memfd page in a 4 GiB reservation;
  - dropping everything with one remap;
  - the cold refault path;
  - a two-level page walk.

  `request.sh` cannot run a native binary, so the benchmark lives in the app, as `HAKUX_HOSTBENCH` does.
- **F1 (`HAKUX_FASTMEM=1`).**
  - Guest RAM moves to a memfd. Guest loads on the kernel-mode data index map read-only into a 4 GiB host shadow, and each load is one instruction, `ldr wD, [x26, wA, uxtw]`.
  - A fault resumes at the load's ordinary slow path. A load that keeps faulting (MMIO, a watched page) is patched to branch there.
  - The shadow follows fills, INVLPG, full flushes and W1's watch walk. A same-value CR3 reload is revalidated by a side-effect-free page walk; anything else drops the shadow.
  - Stores keep the compare.
- **Checked locally:** a syntax/type check with the NDK flags on all six files is clean. No link was run locally; the dispatcher's build is the first.
- **Queued on the Nova** (Tron 2.0, `tron-newgame-anystate`, 750 s, one binary, the env as the only difference):
  - `1-1791081222-lane.memfast-2796953`: control, F1 off, with F0a at 730 s;
  - `1-1791081223-lane.memfast-2797182`: F1 on.
- **Predicted before the runs** (NOTES, "Attempt 3"): Tron's sustained fps +5-15% on F1. **Kill:** F1 more than 3% slower, or faults x the cold cost over 51 ms per wall second.
- **For lane.flushstall787 (#787):**
  - F1 changes no re-translation trigger. Code-page invalidation is on the store side, and F1 leaves stores alone.
  - It adds one hash insert per guest load at translation time, plus an empty-table reset at each `tb_flush`.
  - If #787's counter names re-translation as Tron's stall, F1 neither causes nor fixes it. F1's `[fm] sadd=` (sites added per window) shows translation volume next to `[tcg787]`.

## #507 -- 2026-10-03 20:30 PDT

[lane.memfast] **The F0a constants and the F1 pilot** (Tron 2.0, Nova, one binary, the env the only difference).

**F0a constants** (in the app, under libsigchain, the emulator running; kernel 5.15.123):

| operation | p50 |
|---|---|
| SIGSEGV round trip | 1.6-2.4 us |
| map one memfd page | 1.6-2.4 us (2.4 with `MAP_POPULATE`, which saves the 1.1 us first touch) |
| unmap | 1.7 us |
| cold refault (fault, map, retouch) | 4.4 us |
| page walk | 2.2-2.5 ns per page |
| drop-all with 8,192 pages mapped | 10-12 ms |

- A scattered page costs 2 VMAs.
- Priced against the rates in NOTES section 8, F1's upkeep fits under the kill line on GTA and Tron.

**The F1 pilot:**

- F1 ran 750 s with no crash. In play it took 5.3 faults/s, 0.12 ms per wall second of upkeep, no drops, and 732 patched load sites; revalidation kept 100% of pages.
- **But F1 is slower in Tron's first 210 s of play**, by 1-35% fps per 30 s bucket against both its control and an earlier master run on the same route (these two agree within 3%). It is faster after 270 s: about 25% less guest-busy time per frame, at the 60 fps cap.
- The control hung at about 250 s ("289.9 s without 60 guest flips") with F1 off: a Tron hang on master code. Evidence for #672 if that is Tron's hang issue: `1-1791081222-lane.memfast-2796953`.

**Hypothesis: host TLB reach.** C's RAM can sit on 2 MiB transparent huge pages. F1's memfd RAM gets them only if shmem THP is on, and F1's loads add a 4 KiB alias. Batch 2 at `e9617a9cb4` adds a THP probe and a memfd-only arm (F0b), which separates the two candidate causes:

- `1-1791083408-lane.memfast-2985019` (F1);
- `1-1791083408-lane.memfast-2985074` (F0b);
- `1-1791083409-lane.memfast-2985129` (control).

NOTES ("F1 pilot") has the outcome table and the next step for each outcome, with P and win.

F1 stays off by default; it is an opt-in prototype.
