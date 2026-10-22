# p4splice1022: an uploading surface_update whose bytes a pending download still owes is fed by a GPU image copy (#433)

State: draft

Lane: p4splice1022            Issue: #433 (0.5)
Base: master @ b944110629
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/p4splice1022/PR.md
Prediction: Fable, `HAKUX_SU_SPLICE=1` against `=0` (both arms `HAKUX_ZETA_D24=1`): `[sdcall] surfupd=fin..` falls
  from ~60/60 frames to ~0, `spl=../cp..` > 0, flip time -4.7 to -17.9 ms per flip.
  Falsifier: `surfupd` fin >= 60 per 60 frames on the `=1` arm with `cp0`, and `spl_fallback=` naming the clause
  that refused (partial / cpuw / fmt / src / sub).
Needs device: yes (A/B on the Nova, Fable)
Needs NDK: yes (the counters are on the Android perf-log build; the code path itself is not Android-only)

## Step 0: already tried

| Change / record | What it did | Result | What it means for P4 |
|---|---|---|---|
| 94f002d309 forza414 (#414) | defers the download batch to the next finish instead of draining it per surface_update | kept; the batch completes at the first update that cannot defer (surface.c:6236-6248) | P4 is the case #414 cannot defer: an upload reads the VRAM the batch still owes |
| #474 (flip474) | pre-download at the flip and the locked wait with `pg->lock` released | kept | the fallback path keeps that call unchanged |
| 5eef1dacd9 HAKUX_SURFSPLICE | splices the pending download's staging bytes into the upload's staging buffer | kept, opt-in; refuses swizzled and submitted batches | Fable's zeta is swizzled, so the buffer splice never fires there. P4 copies image to image instead, which does not depend on the VRAM layout as long as the texel mapping is a rectangle |
| 1e5b1af818 / c663a91697 / 7cde4fcf54 surfgpu1009 | GPU-side detach of the pending download (`HAKUX_SURFGPU`) | kept, opt-in; moves the wait to the frame fence (`surfupd=fin0/fence61`) | P4 removes the completion, not only the CPU copy |
| surfgpu1009 NOTES sec. 3, lines 281-284 | image-to-image copy of a D32_SFLOAT_S8 zeta | rejected: not bit-exact against the CPU pack/unpack, "real risk to depth pixels" | P4 refuses D32S8 (`spl_fallback fmt`) and copies D16 and D24S8 only, whose upload/download are bit copies |
| c825e4b24f / 2344ae1ee2 async794 fix 1 | skips the download wait at one site | refuted: the wait moved to `surfupd` | P4 targets `surfupd` itself |
| 7f01f7f157 / 6cd9507d07 / 14ed3ff573 doa413b | lazy completion of downloads | stripped | P4 does not make completion lazier; the batch still completes at its next forcing site |
| c01b3c8d6d forzasurf1010 | surface reuse rules for Forza | kept | no overlap |
| fpsdata1018 H2 | "skip the download" | not built | P4 does not skip the download; the bytes still reach VRAM for CPU readers |
| fpsnext1019 | clrskip/dl = 0.504 | skip falsified | same as above |
| bb7c3bcbc3 HAKUX_SWZKEEP | keeps swizzled surfaces | kept, opt-in | no overlap |
| 489ebfe8d7 | no #474 drain before the colour surface-to-texture copy | kept | precedent: a GPU copy that reads a surface needs no CPU completion |
| 01630977be p5swz1022 | P5, no code change | n/a | no overlap |
| 77fd9d4881 pfifowait1009 | PFIFO wait attribution | kept | counters only |
| 1666e81d7a | profiling fixes | kept | counters only |
| 1bc98b347a | skips downloads on lazy eviction | kept | no overlap |
| #372 handoff (surface.c:5333-5589 at base) | GPU pack/unpack between same-dimension partners | kept | precedent for a GPU write into the new binding's image in the nondraw CB |

Recorded reasons the wait must stay, and how P4 keeps each:

- Without TCG there is no write watch, and VRAM must be current (surface.c:6229-6230). P4 falls back with `cpuw`
  when `!tcg_enabled()`.
- A submitted batch costs a fence wait (#414). P4 falls back with `sub` when the batch is submitted, a display
  pre-download is pending, or a held SURFGPU batch overlaps.
- Coalescing is correct only when no CPU read or write comes between. P4 falls back with `cpuw` while a trapped
  access is in progress (`downloads_pending`), when the source has no watch, when the source's watch is suspended,
  or when the binding's watch is suspended (its re-arm would hash VRAM before the download lands, and the gap
  check in surface_watch_rearmed would read the landing as a guest write).
- A deferral past an uploading update re-records a still-dirty surface (dedup comment at surface.c:1184-1199,
  Overlap_TR_Outside). The dedup is on whenever `HAKUX_SU_SPLICE` is, and a surface's pending download completes
  before a synchronous download of it.

## Mechanism

Fable's zeta at 0x019b4000 is reshaped 128x128 -> 64x64 -> 32x32 at one address, swizzled. Each reshape evicts the
old binding, which records a deferred download of it, and creates a new binding with `upload_pending` (`why=inv`).
The upload reads VRAM the download still owes, so surface_update completes the whole batch: a finish and a CPU wait
(fpsdata1018 21:30:24: `surfupd=fin127/.../dl134/703.6ms su_upl=127 why=...inv127`).

The bytes that upload would read are the download's, and the download's are its source image's at the generation it
captured. With `HAKUX_SU_SPLICE=1` the update instead records one `vkCmdCopyImage` from the source image into the
new binding's image, in the same nondraw command buffer and after the download's own copy, and leaves the binding as
the upload leaves it (watch re-armed under `surface_watch_lock`, `upload_pending` cleared, `initialized`). The
download stays pending and completes at its next forcing site for the CPU readers it was recorded for.

Texel mapping:

- Swizzled, same address: texel (x, y) of a 2^a x 2^b surface sits at the same offset in a 2^A x 2^B surface when
  each of the new surface's swizzle masks is the low set bits of the old one's (a shrink). `su_swizzle_masks` is
  swizzle.c:52-74 at depth 1; growing reshapes are `partial`, masks that do not nest are `fmt`. The copy is the
  source's (0, 0)..(w, h) rectangle.
- Linear, one pitch: the binding is the rectangle at `x0 = (off % pitch) / bpp`, `y0 = off / pitch` of the source.

Bit-exactness: colour only when `host_bytes_per_pixel == bytes_per_pixel` (upload and download are raw copies);
D16; D24_UNORM_S8_UINT, whose pack/unpack is integer (surface-compute.c:28-67, `depth << 8 | stencil` and back),
copied as a depth region and a stencil region. D32_SFLOAT_S8_UINT goes through float and is refused (`fmt`); it is
the default zeta host format, so the A/B sets `HAKUX_ZETA_D24=1` on both arms.

## Source-image lifetime and content

The copy reads `dl->surface->image` in `r->command_buffer` (draw.c:6338 begin_nondraw_commands), after the download's
copy and before anything recorded later.

Alive until the copy executes:

- destroy_surface_image (surface.c:4429-4466) queues the VkImage on `deferred_surface_releases[current_frame]`,
  freed only after that slot's fence, so even a destroy after the copy is recorded leaves it valid for this CB. It
  NULLs `surface->image`, which the planner refuses (`src`).
- migrate_surface_image (surface.c:4398-4400) NULLs the image and sets UNDEFINED: refused (`src`).
- get_any_compatible_invalid_surface (4554-4556) and prune_invalid_surfaces (4575-4577) skip a struct a pending
  download references; prune frees only after deferred_downloads_clear_surface (4580), which NULLs `dl->surface`
  (1597-1616): refused (`src`).
- Shelf reuse of a referenced struct (5989-5996) completes the batch, or under HAKUX_SURFGPU detaches it
  (`dl->surface = NULL`): refused (`src`).
- expire_old_surfaces completes the batch when anything expires (4621-4623).

Unmodified between the download's copy and this one:

- `src->draw_generation == dl->draw_generation`: no draw or clear reached it (draw.c:10941/10950 and
  surface.c:6057 bump it).
- src is neither the colour nor the zeta binding, so this update's draws cannot reach it, and no queued draw
  exists (`reorder_window`/`draw_queue` empty; the download's own recording flushed both, surface.c:1276-1281).
- An upload into src needs `upload_pending`, which is refused; a trapped CPU write sets it only after the access
  callback has completed overlapping downloads (surface.c:3409), so the download would no longer be pending. The
  gap check sets it only for a surface that is not `draw_dirty`, and a surface with a pending download is.
- Width, height, pitch, swizzle, address and host format are compared with the download's.
- Writes recorded after the copy are ordered after it by the TRANSFER -> ALL_COMMANDS post-barrier.

Equivalence with complete-then-upload: the planner takes the last pending download over the binding's bytes
(completion writes in record order) and requires it to cover every texel the binding reads, so after completion
VRAM there holds exactly the source's texels at that generation, which is what the copy writes. The download's
later completion writes those same bytes through the host pointer with no trap; the binding's image already holds
them. Texture reads check deferred_downloads_overlap_range before using VRAM, as before.

## The change (hw/xbox/nv2a/pgraph/vk/surface.c)

- 597: `g_su_splice`, read once at init.
- 1200: the re-record dedup runs under `surfsplice_on() || g_su_splice` (a download left pending past an
  uploading update needs the same test as the buffer splice).
- 2840-2842: download_surface completes a surface's pending downloads first under the gate, so the generation
  skip sees the completion's credit and the synchronous copy does not overwrite later downloads.
- 1885-1887: `SUFB_*` fallback reasons. 1916-1921: `spl_cp`, `spl_nov`, `splfb[]` in g_sdcall.
  2031, 2046-2058: `[sdcall]` line gains `spl=.../cmpl../cp../nov..` and
  `spl_fallback=partial../cpuw../fmt../src../sub..` (appended; existing readers' regexes still match).
- 6282-6356: comment block, `SuPlan`, `su_pow2`, `su_swizzle_masks`, `su_low_set_bits`.
- 6358-6517: `su_plan_binding`: range, held-batch overlap (`sub`), last overlapping download, `partial`, source
  checks (`src`), watch checks under `surface_watch_lock` (`cpuw`), format (`fmt`), linear and swizzled mapping.
- 6525-6634: `su_splice_copy`: explicit image barriers into TRANSFER_SRC/DST (GENERAL kept for colour already in
  GENERAL), `vkCmdCopyImage` at 6597 with one region, or depth + stencil for D24S8, back to the source's layout and
  to the binding's default layout (GENERAL colour, DEPTH_STENCIL_ATTACHMENT_OPTIMAL zeta, as the upload leaves it).
- 6645-6694: `su_splice_try`: plans both bindings before recording anything; any fallback completes as before and
  counts `splfb[reason]` once; otherwise copies, applies the upload's bookkeeping, counts `cp` (or `nov` when no
  uploading binding had a pending download over it). No `surfupd` fin is counted on that path.
- 6802-6805: `if (!(g_su_splice && upload && su_splice_try(d)))` around the unchanged
  `download_surface_complete_deferred_at(d, SDC_SURF_UPDATE, qemu_thread_is_self(&d->pfifo.thread))`. With the
  gate at 0 the expression short-circuits to today's call; the dedup and the download_surface guard are also off.
- 7318-7321: `HAKUX_SU_SPLICE` read once in pgraph_vk_init_surfaces after the Z24S8 line; logs
  `nv2a: HAKUX_SU_SPLICE=0|1`.

## Checks

```
$ python3 -I tools-p/cc_wt.py wt/p4splice1022 .../vk/surface.c -DNV2A_PERF_LOG=1    -> exit 0
$ python3 -I tools-p/cc_wt.py wt/p4splice1022 .../vk/surface.c -DNV2A_PERF_LOG=0    -> exit 0
$ ... -DNV2A_PERF_LOG=1 -D__ANDROID__ (android/log.h declarations stub)              -> exit 0
$ ... -DNV2A_PERF_LOG=0 -D__ANDROID__ (same stub)                                    -> exit 0
```

Warnings in all four runs are the base's own (surface.c:1122 redundant declaration, 2129 unused `t0`, 2179 missing
prototype); none is on a changed line. The `__ANDROID__` runs compile the `g_sdcall` fields, the `SDCALL_DO`
bodies and the `[sdcall]` format string with -Wformat.

Selftest fragments matching `surface\.c|surface_update|may_defer|474|sdcall`: 65-status-objective,
71-cloud-territory, 86-nightly-notes, 99-fleet-suffixed-pr, 99-handback-branch, 99-handback-lane-line,
99-request-release-prio, 99-request-priority-flag. None anchors on surface.c code (they match path strings and
issue numbers).

```
$ SELFTEST_ONLY="<the eight>" timeout 900 bash docs/testing/jobs/selftest.sh
selftest: 218 passed, 0 failed, PARTIAL: 8 of 160 fragments
```

## Device A/B

Fable on the Nova, perf-log build, both arms `HAKUX_ZETA_D24=1`; arm A `HAKUX_SU_SPLICE=0`, arm B
`HAKUX_SU_SPLICE=1`. Confirm the init lines `nv2a: Z24S8 host format ...` and `nv2a: HAKUX_SU_SPLICE=N`. Read per
60-frame `[sdcall]` window: `surfupd=fin../fence../pre../dl../ms`, `su_upl=.. why=...inv..`,
`spl=def../up../dl../kB/cmpl../cp../nov..`, `spl_fallback=partial../cpuw../fmt../src../sub..`, and ms per flip.

## Risks

- D32S8 zeta (the default) is always `fmt`; the gain needs `HAKUX_ZETA_D24=1`, whose own depth quantisation is a
  separate question (rendering, not this copy).
- Growing swizzled reshapes are `partial`; a linear pitch change is `fmt`; a held HAKUX_SURFGPU batch over the range
  is `sub`; a suspended watch on the source or the binding is `cpuw`. Any of these, frequent on Fable, falsifies.
- The read range is conservative (`MAX(size, w*h*bpp, pitch*h)`), so an unrelated later download just past the
  texels can be taken as the last writer and refuse the copy (`partial`/`src`): a lost hit, not a wrong one.
- ALL_COMMANDS barriers around the copy may serialise more than needed on Turnip.
- expire_old_surfaces can still complete the batch in the same update when a surface expires (`expire` caller on
  the `[sdcall]` line).
- `why=inv` is not a precondition (UPW exists only in perf builds); the copy applies to any uploading binding the
  planner accepts.
- Untrapped writes to VRAM (DMA paths that bypass the watch) are a pre-existing hazard for every deferred download;
  the copy does not widen it, but it does keep the download pending across one more update.
- With the gate on, the download_surface pre-completion also applies to downloads #414 deferred past a
  non-uploading update; it completes only a batch that references the surface being synchronously downloaded.
