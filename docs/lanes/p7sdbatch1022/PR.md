# p7sdbatch1022: HAKUX_SD_BATCH -- shelved overlap and expiry downloads stay in the deferred batch, and a full batch is flushed instead of finished (#433)

State: draft

Lane: p7sdbatch1022            Issue: #433 (0.5)
Base: master @ b944110629
Files: hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/draw.c, docs/lanes/p7sdbatch1022/PR.md
Prediction: Fable on the Nova, perflog build, same route in both arms, `HAKUX_SD_BATCH=1` against `0`:
  `[sdcall] tobuf` fin 18-37/60 -> ~0; `dlSrc[dirtyIf]` -> ~0; `sd_batched[ovl+exp]` > 0; about -9 ms/flip.
  Falsifier: `tobuf` fin unchanged, or `sd_sync_reason=overflow` the largest of the three.
Needs device: yes -- the Fable A/B below
Needs NDK: yes -- the perflog APK for the A/B; the touched C files are host-compiled under both NV2A_PERF_LOG values (Checks)
Selftest: 99-dipwin-counters 99-fpsdiag -- 99-dipwin-counters is the only fragment that reads hw/xbox/nv2a/pgraph/vk/draw.c (its dipwin_flip/opt_stats_log_and_reset rules); 99-fpsdiag synthesizes hakuX-stall lines for fpsdiag.py. No fragment reads surface.c or renderer.h.

## Mechanism

Two loops in `surface.c` still take a shelved binding's download inline:

- the shelved loop of `invalidate_overlapping_surfaces` (`dif[ovlSh]`);
- the shelved loop of `expire_old_surfaces` (`dif[expSh]`).

Each one calls `pgraph_vk_surface_download_if_dirty` (`dlSrc[dirtyIf]`). That completes the deferred batch and then makes a `download_surface_to_buffer` with a SURFACE_DOWN finish of its own (`[sdcall] tobuf`, `Finish:(sd)`). After that the binding is freed.

`expire_old_surfaces` also completes the whole batch with `SDC_EXPIRE` whenever anything expires. And when the batch is full (64 records, or staging), `download_surface_deferred` completes it (`SDC_DEFER_FULL`) before retrying, falling back to a synchronous download.

With `HAKUX_SD_BATCH=1`:

1. **Shelved downloads stay in the batch.** A draw-dirty shelved binding that an overlap or an expiry retires gets its download recorded with `download_surface_deferred`. It then moves to `invalid_surfaces` as `invalidate_surface` leaves an evicted binding (`sd_batch_retire_shelved`), instead of being downloaded inline and freed. A clean one is freed as before.
2. **Expiry no longer completes the batch.** Expired active bindings' downloads are left pending behind `invalidate_surface`, as #414 (94f002d309) already leaves eviction downloads.
3. **A full batch is flushed, not finished.** It is submitted with one `SURFACE_DOWN_FLUSH` and the record goes into the next batch (`sd_batch_record`). That finish is in the deferred list (`draw.c:5847-5852`), so the PFIFO thread waits for the submit, not for the GPU. The submitted batch is then held aside with its fence under HAKUX_SURFGPU (`complete_submitted_downloads`). Without SURFGPU it is waited for by the retry, which is a fence wait, not a finish. The render thread's finishes are synchronous, so there, and when the batch is already submitted, the default fallback runs, counted as `overflow`.
4. **The batch holds up to 128.** The arrays are sized for 128 (`MAX_DEFERRED_DOWNLOADS`). The cap is 64 when the switch is off and 128 when it is on (`deferred_downloads_cap()`).
5. **No duplicate records.** A range lookup's invalid-list branch can find a retired binding whose download is already pending. Recording it again would land the same bytes a second time, behind every download recorded since. So the record is skipped when the batch, the held one included, already holds a full download of that binding at its current generation into the same bytes (`deferred_downloads_hold_current`, the same test as the splice dedup).

The switch reads as off without TCG, because there is no CPU-access watch there to complete a pending download on demand. `surface_update_may_defer_downloads` and `surface_handoff_partner` use the same rule.

## Already tried

| What | sha / where | Result | Bearing on this change |
|---|---|---|---|
| Defer active eviction, overlap and expiry downloads | 1666e81d7a (04-06) | dl 649 -> 0; the two shelved loops kept inline: "use inline path since images are destroyed here" (base `surface.c:4061`, `:4587`) | The only recorded reason for the inline path; see Image lifetime |
| Retire images behind the frame fence | 772b7d954e (09-10, #29), `destroy_surface_image` `surface.c:4582-4615` | A freed binding's VkImage is released once that slot's fence signals | Removes that reason |
| Skip eviction downloads ("lazy overlap") | 1bc98b347a (04-08) | Reversed: #7 Image blit Overlap_* (`surface.c:4226-4234`), Depth buffer fixed function 42/80 | Not re-implemented: every download is still taken, only later |
| Leave eviction downloads pending past surface_update | 94f002d309 (#414) | On master. Forza A/B P1 0.559 (fail), fps 1.005, baseline already at the 30 fps cap | The pattern this change copies for shelved bindings |
| Keep a pending download's struct out of reuse and prune | f65175f993 (#414 audit) | On master | The ownership rule this change reuses (`deferred_downloads_reference`) |
| #474: pgraph.lock released across download fence waits | ee830484bb, ef66174066, 16b7e14ec9; c825e4b24f fix 2 | On master (Top Spin vCPU lock wait 10.1 -> 0.4 ms/f) | Preserved; no new wait, no `release_lock` argument changed |
| async794 fix 1: per-submission completion, reuse detaches | c825e4b24f, stripped by 2344ae1ee2 | Refuted on NBA Live 2005: the finish moved from `reuse` (11.18 ms) to `surfupd` (11.48 ms) | Not re-implemented. The same risk applies here: a deferred download an upload reads is completed by `surfupd` (Risks) |
| doa413b lazy completion of submitted batches | 7f01f7f157 -> 6cd9507d07 -> 14ed3ff573 | Never fired (no submitted batch at surface_update); 14.9 vs 13.6 fps; stripped | Not re-implemented: this change defers unsubmitted records |
| Halo overlap census | 7a960726d8; `docs/lanes/halo1016/NOTES.md` 335-348 | Overlap eviction MISS on Halo: draw-dirty 0.00/f against Finish sd 49.28/f | `dif[ovlSh]` counts every shelved overlap, dirty or not; `sd_batched[ovl]` counts only the dirty ones |
| Fable eviction census (H2/H3), `[edl]` skip | `docs/lanes/fpsdata1018/NOTES.md` 506-507; `docs/lanes/fpsnext1019/NOTES.md` 949-978 | H3 dead; `[edl]` clrskip/dl 0.504, the skip was not built | About half of evicted bytes are read later: defer them, do not skip them |
| A range lookup completes the whole pending batch | `docs/lanes/fpsbelow1012/NOTES.md` 810-848 (rule from 59729d180a) | Any overlap completes everything pending | Deferral can move the finish to `range` (Risks; unmeasured) |

No record defers the two shelved loops, the SDC_EXPIRE completion, or the full-batch completion. `SURFACE_DOWN_FLUSH` had no caller on master.

## Every recorded reason a download must be synchronous or complete first

1. "Images are destroyed here" (base `surface.c:4061`, `:4587`). This is out of date since 772b7d954e; see Image lifetime.
2. `download_surface_deferred`: "The caller MUST ensure ... complete_deferred() is called before the surface is invalidated or freed" (`surface.c:2952-2956`). Invalidation keeps the image (`invalidate_surface`); freeing loses the watch and the struct. This change does not free a struct the batch names.
3. A range lookup "must complete now since the caller needs the data in VRAM" (`surface.c:1136-1155`). Unchanged.
4. "Without TCG there is no CPU-access watch, and VRAM has to be current when the update returns" (`surface.c:6402-6403`). The switch is off without TCG.
5. A binding that uploads from VRAM forces completion unless HAKUX_SURFSPLICE covers it (`surface_update_may_defer_downloads`, `surface.c:6414-6421`). Unchanged; P7 relies on it (P4 note below).
6. The reuse site completes with `SDC_REUSE` before handing back a pending struct (`surface.c:6167`). Unchanged.
7. A full batch or full staging falls back to a synchronous download (`download_surface_deferred`). With the switch on, a flush comes first.
8. #474: a wait on a deferred download releases pgraph.lock only on the PFIFO thread. The staged bytes are copied into VRAM only after the lock is retaken. The submitted batch completes before a record goes into a new command buffer (`complete_submitted_downloads`, `surface.c:1221-1238`). The access callback settles (`pgraph_lock_settled`, `surface.c:3542`), so a guest write cannot land before the staged copy. None of this changes.
9. AGENTS.md "A retained GPU copy of guest memory is a write-back obligation, and it needs a watch": anything that defers a copy into guest memory keeps watching it until the copy lands.
10. `docs/lanes/halo1016/NOTES.md` 274: coalescing "is only correct if the guest does not read the downloaded bytes on the CPU in between". The watch enforces this; see below.

## Synchronous readers: how each still gets its bytes

Every one below completes an overlapping pending download before it reads VRAM. Each tests `deferred_downloads_overlap_range`, which covers the held batch too, or completes the batch outright. None of them changed.

| Reader | Where | How the pending download completes first |
|---|---|---|
| CPU access (TCG watch) | `surface_access_callback`, `surface.c:3534-3675` | `wait_for_downloads = deferred_downloads_pending && deferred_downloads_overlap_range` (3552-3554). The access kicks the PFIFO thread and waits on `downloads_complete` (3667-3673). `process_pending_downloads` completes `SDC_PENDING` first (3200). Settled under #474 (3542) |
| Scanout | `pgraph_vk_wait_for_surface_download` (`renderer.c:4349`, `:4353`) | Same kick, `process_pending_downloads` |
| Texture / vertex / blit / draw range | `pgraph_vk_download_surfaces_in_range_if_dirty`: `texture.c:4149`, `vertex.c:175`, `draw.c:9002`, `blit.c:558`, `:560`, `:900` | Its invalid-list branch finds a retired binding (draw-dirty) and sets `found_overlap`. The record dedups. Then `SDC_RANGE` completes (`surface.c:1136-1155`) |
| Texture scan | `pgraph_vk_texscan_complete_range`, `texture.c:2343` | `deferred_downloads_overlap_range`, then `SDC_RANGE` (`surface.c:1174-1189`) |
| Inline per-surface reads | `pgraph_vk_surface_download_if_dirty`: `texture.c:4093`, `blit.c:530`, `:623`, `:911`, `renderer.c:4093-4116` (diagnostic) | On active bindings; unchanged and synchronous |
| A new binding uploading over the bytes | `pgraph_vk_surface_update`, `surface.c:6544-6560` | The overlap records are made in `update_surface_part` (6498-6518), before this check. An uploading binding forces `SDC_SURF_UPDATE`, unless the splice covers it; then `pgraph_vk_upload_surface_data` completes whatever it cannot splice (4862-4865, 4964-4967) |
| Reuse of a pending struct | `update_surface_part`, `SDC_REUSE`, `surface.c:6167` | Unchanged |
| Flip pre-record | `pgraph_vk_prerecord_display_download`, `SDC_PREREC`, `surface.c:3095` | Unchanged |
| Dirty sweep | `pgraph_vk_download_dirty_surfaces` | Unchanged; cap via `deferred_downloads_cap()` |
| Renderer completions | `renderer.c:630`, `:3098`, `:3915` | `pgraph_vk_download_surface_complete_deferred`, unchanged |
| Surface flush / finalize | `pgraph_vk_surface_flush` (`surface.c:7137`, `:7143`) | Downloads active bindings synchronously; see Risks for the kept invalid structs |

A CPU access to a range with a pending download completes it first. The retired binding keeps its watch while it is draw-dirty (`unregister_cpu_access_callback_if_clean`, `surface.c:4052-4057`), so the access traps. `wait_for_downloads` is computed from the batch itself, not from the binding (3552-3554). A write also clears `draw_dirty` on the overlapping shelved and invalid structs (3648-3663), and then waits for the same completion. The staged copy therefore lands before the guest's write, which wins. This is the ordering #414's eviction downloads already have.

## Image lifetime

- **The image.** `destroy_surface_image` (`surface.c:4582-4615`) appends the VkImage, its view, its allocation and its scratch to `deferred_surface_releases[current_frame]`, which drains after that slot's fence (772b7d954e, #29). The image a recorded copy reads therefore stays valid whatever happens to the struct. The struct this change keeps also keeps its image until `prune_invalid_surfaces` frees it, and that goes through the same retirement.
- **What freeing the struct loses.** It loses two things. `unregister_cpu_access_callback` drops the watch over the bytes the download will write. `deferred_downloads_clear_surface` NULLs the record's `surface`, so completion cannot retire the binding's generation or mark it clean.
- **The ownership rule.** `deferred_downloads_reference` (`surface.c:1696`, f65175f993) is the existing rule for a struct a pending download names. `get_any_compatible_invalid_surface` (4700-4718) and `prune_invalid_surfaces` (4720-4739) skip it. Reuse completes it first (`SDC_REUSE`).
- **How the retired binding is placed.** It goes on `invalid_surfaces`, under that rule, exactly as #414 places an evicted active binding. It is draw-dirty, so its watch stays. `shelved_dirty` is cleared. `invalidation_frame` is the current frame when a command buffer is open; this is conservative, since the image may have been drawn in it before it was shelved. `surface_list_gen` is bumped.
- **The keep test.** The binding is kept only if `deferred_downloads_reference` holds after the record. If the record fell back to a synchronous download, it is freed as before.

The ownership rule is therefore safe to reuse for shelved bindings, and no fallback to the inline path is needed.

## The change

- **`renderer.h:446-452`.** `MAX_DEFERRED_DOWNLOADS` goes from 64 to 128 (the arrays: `deferred_downloads[]`, `g_sg_held.dl[]`), and `DEFERRED_DOWNLOADS_DEFAULT_CAP` 64 is added.
- **`renderer.h:229-253`.** The perflog counters are added: `sd_batched_{ovl,exp,ev,flush,dup}` and `sd_sync_{access,overflow,other}`.
- **`surface.c:492-569`.** The switch (`g_sd_batch`, `sd_batch_on()` = switch and TCG), `deferred_downloads_cap()`, `deferred_downloads_hold_current()`, and the `sd_sync_reason` tag (`SDW_*`, perflog only).
- **Cap checks.** `download_surface_record_deferred`'s cap is `deferred_downloads_cap()` (`surface.c:1298`), as are the cap checks of `process_pending_downloads` (3217) and `pgraph_vk_download_dirty_surfaces` (3302).
- **Finish counts.** Every compiled SURFACE_DOWN finish in surface.c is counted by reason: `download_surface_complete_deferred_at` (2285), `download_surface_to_buffer` (2844), `process_pending_downloads` (3247), `download_dirty_surfaces` (3332).
- **`surface.c:2924-2950`, `sd_batch_record`.** Record; if that fails on the PFIFO thread with an unsubmitted batch, `SURFACE_DOWN_FLUSH` and record again.
- **`surface.c:2977-3011`, `download_surface_deferred`.** With the switch on: dedup, then `sd_batch_record`. The default path is the original call. The `SDC_DEFER_FULL` plus synchronous fallback is tagged `overflow`.
- **`surface.c:3013-3054`, `sd_batch_retire_shelved`.**
- **`surface.c:3183-3194`.** `pgraph_vk_process_pending_downloads` becomes a wrapper that tags `access`. The body, unchanged, is `process_pending_downloads`.
- **`surface.c:4244-4263`.** `invalidate_overlapping_surfaces`' shelved loop: retire under the switch, else the original inline path.
- **`surface.c:4753-4811`.** `expire_old_surfaces`: active bindings use `download_surface_deferred` under the switch; there is no `SDC_EXPIRE` under the switch; the shelved loop retires under the switch.
- **`surface.c:7073-7079`.** `HAKUX_SD_BATCH` is read once in `pgraph_vk_init_surfaces`, and one init line is logged: `nv2a: HAKUX_SD_BATCH=<0|1>, deferred download cap <64|128>[ (no TCG: off)]`.
- **`draw.c:999`, `:1033-1041`.** The hakuX-stall RPBreaks line gains ` sd_batched[ovl%d exp%d ev%d flush%d dup%d] sd_sync_reason=access%d/overflow%d/other%d` after `dif[...]`.

**Untouched:**

- `surface_update_may_defer_downloads`
- the tail of `pgraph_vk_surface_update`: its call of `expire_old_surfaces` is unchanged, and so is the function's caller
- every `wait_frame_fence` call and its `release_lock` argument
- the `if (false &&` row narrowing in `surface_access_callback` (`surface.c:3585`)
- the splice block

**With the switch at 0** every branch takes the original statement; the only differences are the cap expressions, which evaluate to 64, and the perflog-only tags.

**P4 (lane/p4splice1022).** P7 does not need `surface_update_may_defer_downloads` or the update's tail changed. It does rely on their current rule: an uploading binding completes, or splices, every pending download before it reads VRAM. That rule is what now completes the shelved overlap downloads that used to complete inline. A replacement rule in P4 must keep that property for downloads recorded during `update_surface_part`.

### Counters

- `Finish:(sd%d)` counts SURFACE_DOWN and SURFACE_DOWN_FLUSH as before (`draw.c:5683-5684`), so the flushes are in it.
- `dlSrc[dirtyIf]`, `dif[...]` and `[sdcall] tobuf` count at the same statements as before. Under the switch the shelved loops no longer reach `pgraph_vk_surface_download_if_dirty`, which is the predicted drop.
- `sd_batched[ovl]`: draw-dirty shelved bindings an overlap retired with the download pending.
- `sd_batched[exp]`: the same for expiry, plus expired active bindings whose download expiry no longer completes.
- `sd_batched[ev]`: `download_surface_deferred` records made after a flush, where the default path would have completed the batch.
- `sd_batched[flush]`: the flushes.
- `sd_batched[dup]`: skipped duplicate records.
- `sd_sync_reason`: the SURFACE_DOWN finishes issued from surface.c, split three ways:
  - `access`: under `pgraph_vk_process_pending_downloads`, a trapped CPU access or the scanout.
  - `overflow`: under the full-batch fallback.
  - `other`: everything else.
  Finishes issued from renderer.c and texture.c are not in it. It is one global tag shared by the PFIFO and render threads, so it is an attribution, not an exact count.

## Device A/B (not run)

- **Build.** One perflog APK from this branch (`NV2A_PERF_LOG=1`), the Fable route used for the 10-19 Fable windows, the same route in both arms.
- **Arms.** A: `--env HAKUX_SD_BATCH=0`. B: `--env HAKUX_SD_BATCH=1`.
- **Confirm the arm.** Check the `hakuX-stderr` init line in each arm: `nv2a: HAKUX_SD_BATCH=1, deferred download cap 128` on B, `=0 ... cap 64` on A.
- **Read per 60-frame window:**
  - `hakuX-stall`: `Finish:(sd)`, `dlSrc[dirtyIf]`, `dif[ovlSh expSh]`, `sd_batched[...]`, `sd_sync_reason=...`
  - `[sdcall]`: `tobuf=fin`, `expire=fin` (0 on B), `deffull=fin`, `range=fin/ms`, `surfupd=fin/ms`, `record=fence`
  - `[surfgpu]`: `hold/hwait/hrot`
  - `hakuX-pace`: ms
- **Where the completions move.** Watch `range` and `surfupd`. If B's `tobuf` drop reappears as `range` or `surfupd` fin at the same ms, the deferral moved the wait instead of removing it.

## Checks

```
$ python3 -I /home/justin/hakux-work/tools-p/cc_wt.py /home/justin/hakux-work/wt/p7sdbatch1022 <file> -DNV2A_PERF_LOG=1   (and =0)
surface.c 1 exit=0 warnings=3 errors=0
surface.c 0 exit=0 warnings=3 errors=0
draw.c 1 exit=0 warnings=16 errors=0
draw.c 0 exit=0 warnings=16 errors=0
```

Every warning is also present at the base:

- surface.c: the redundant redeclaration of `download_surface_complete_deferred` (base 238/1113), `t0` set but unused in `surfgpu_complete_held_at` (base 2104), and no prototype for `pgraph_vk_surfgpu_slot_retired`.
- draw.c: 14 `xemu_set/get_*` without prototypes, `cmd` shadowed in `pgraph_vk_finish`, unused `r` in `classify_draw_safe`.

renderer.h is compiled by both.

```
$ grep -l -E "surface\.c|SURFACE_DOWN|download|sdcall|474" docs/testing/jobs/selftest.d/*.sh
71-cloud-territory 65-status-objective 86-nightly-notes 99-handback-branch 99-request-priority-flag
99-fleet-suffixed-pr 99-handback-lane-line 99-request-release-prio
```

These eight match on paths, lane names and issue numbers; none reads the C code.

A wider search for the anchors this change moved found two more fragments: 99-dipwin-counters reads draw.c, and 99-fpsdiag synthesizes hakuX-stall lines. The anchors searched were `process_pending_downloads`, `download_surface_deferred`, `expire_old_surfaces`, `invalidate_overlapping_surfaces`, `MAX_DEFERRED_DOWNLOADS`, `SDC_EXPIRE`, `SDC_DEFER_FULL`, `dlSrc`, `ovlSh`, `hakuX-stall`, `opt_stats_log_and_reset`, `pgraph_vk_init_surfaces` and `deferred_downloads_reference`. No anchor moved under any fragment, and no check was changed.

```
$ SELFTEST_ONLY="71-cloud-territory 65-status-objective 86-nightly-notes 87-nightly-trunk 99-handback-branch \
    99-request-priority-flag 99-fleet-suffixed-pr 99-handback-lane-line 99-request-release-prio \
    99-dipwin-counters 99-fpsdiag" timeout 900 bash docs/testing/jobs/selftest.sh
selftest: 300 passed, 0 failed, PARTIAL: 11 of 160 fragments
```

87-nightly-trunk was run because it is in 86-nightly-notes' shard chain.

Stall-line readers: the in-tree parsers of the RPBreaks line match substrings, with no `$` anchor:

- `halo1016/censusread.py`, `halo1016/scratch/stallrows.py`
- `blinx372c/stallread.py`, `blinx372c/demobound.py`
- `aufire412/splitread.py`
- `gpunonrender/*`
- `doa413/tools/phase_table.py`

The appended tokens cannot be read as `sd\[`, `flu(\d+)` or `oth(\d+)`, because `sd_batched[`, `flush%d` and `other%d` do not fit those patterns.

## Risks

- **The wait may move, not vanish.** A range lookup completes the whole pending batch on any overlap, a clean active surface included (`surface.c:1136-1138`; fpsbelow1012 NOTES 810-848). An uploading binding completes it in `surfupd`. That is async794 fix 1's failure mode. The A/B reads `range` and `surfupd` for it.
- **Each flush adds a rotation.** It moves to the next frame slot and waits that slot's fence. Without SURFGPU, the retry's `complete_submitted_downloads` also waits the flushed batch's fence (a wait, not a finish).
- **`Finish:(sd)` includes the flushes.** A drop in `tobuf` with `sd` flat can be flushes; `sd_batched[flush]` says how many.
- **Kept structs outlive a flush.** They survive `prune_invalid_surfaces(0)` in `pgraph_vk_surface_flush` while the batch still names them. They are freed at the next prune after completion. #414's evicted structs already behave this way.
- **Expiry downloads stay pending past surface_update** until a reader, a new record behind a submitted batch, the rotation or the next flip's pre-record completes them. Staging holds them longer, so the batch can fill sooner (`overflow`, `flush`).
- **The sync-reason split is approximate.** `sd_sync_reason` is one global tag. A finish on one thread while the other is inside a tagged section is misattributed. `pgraph_vk_download_dirty_surfaces`' own fallback is counted as `other`, and renderer.c and texture.c finishes are not classified.
- **The watch can be suspended.** A retired binding's watch is suspended only if it is no longer draw-dirty, as for any invalid binding. The exposure is the same as the existing eviction path's.
- **TCG is read at init.** `tcg_enabled()` is read in `pgraph_vk_init_surfaces` for the log line and on every `sd_batch_on()` call; the result does not change at run time.
- **Memory.** The extra struct memory and the doubled `DeferredSurfaceDownload` arrays are small. Staging capacity, not the array, bounds a batch.
