# surfgpu1009: a GPU-side route for the reuse/surfupd rebind (NBA Live 05/06/07)

#433 umbrella, 0.5. Dispatched directly by lane.local, so there is no issue.
Nova only. Switch: `HAKUX_SURFGPU=1`, off by default.

## 0. Baselines (already measured, re-read here, mark-restricted)

Sources: `docs/lanes/near30/decompose.py` and
`docs/lanes/surfdl1008/postmark_sdsurvey.py`, run on the existing results.
No thermal pause in any run. Nothing was re-run.

| title | run | gfps | ph_GPU | ph_Fin | ph_Tot | reuse ms/fr | surfupd ms/fr | record ms/fr |
|---|---|---|---|---|---|---|---|---|
| NBA Live 2005 | `1-1791525926-fpstelemetry1008-4089047` | 25.49 | 9.80 | 13.40 | 28.50 | 11.49 (fin 1.00/fr) | -- | 0.01 |
| NBA Live 06 | `1-1791525334-surfdl1008-4042714` | 20.10 | 19.60 | 22.20 | 43.30 | 20.48 (fin 1.00/fr) | -- | 0.01 |
| NBA Live 07 | `1-1791525340-surfdl1008-4043345` | 22.17 | 21.30 | 13.80 | 36.60 | 10.70 (fin 0.50/fr) | 8.74 (fence 0.50/fr) | 0.01 |

The raw `[sdcall]` lines (60 flips each) show which kind of wait each one is:

- NBA 06: `reuse=fin60/fence0/pre0/dl120`, `record=pre30/dl120`, `su_upl=0`,
  `clrskip=60`. `[surf413]`: `realupl=60 uplKB=72000`, so one 1200 KB upload
  per flip.
- NBA 07: `surfupd=fin0/fence30/pre0/dl30`, `reuse=fin30/dl60`,
  `record=pre30/dl180`, `su_upl=0`, `clrskip=120`. `[surf413]`: `realupl=0`.
  `xemu-work Fin:` shows only `Sd1 Fl1`.
- `[evict372]`:
  - NBA 05 and 06 rebind their zeta binding between `Z f130 ln p2560 640x480
    b4` and `256x256`;
  - NBA 07 between `Z f124 ln p640 320x240 b2` and `256x256`.
  - All of these are at one address and all are `m08` (smaller). f130 is
    `VK_FORMAT_D32_SFLOAT_S8_UINT`, f124 is `D16_UNORM`.

Instrument note: `ph_Fin` times `pgraph_vk_finish` only. A completion that
waits a submitted batch's fence (`wait_frame_fence`) is timed in the calling
phase, which is Surf for `surfupd` and `record`. That is why NBA 07's surfupd
8.74 ms is not inside its ph_Fin. `[sdcall]` times every completion of every
kind, so it is the counter for "did the wait go, or move".

## 1. Why each path needs a CPU-visible completed download today

### The NBA 05/06 frame, from the code

One guest frame, as the counters above and the code read together:

1. **big -> small.** The 640x480 zeta binding Z_big is evicted while dirty.
   `download_surface_deferred` records its download D1 into the open command
   buffer, unsubmitted (`deferred_downloads_frame = -1`). Z_big is shelved
   with its VkImage, still `draw_dirty`, so `shelve_surface` keeps its
   CPU-access watch.
   - D1's record calls `surface_vram_written`, which marks the shelved Z_small
     (same address) `vram_newer`.
   - Z_small comes off the shelf stale (`upload_pending`). A covering clear
     then drops that upload (`surface_drop_covered_upload`, `clrskip`).
     Nothing in this half reads VRAM, so `surface_update_may_defer_downloads`
     returns true and D1 stays pending.
2. **small -> big.** Z_small is evicted dirty, and its download D2 is
   recorded. Same address, same pitch, 256 rows of 1024 bytes: D2 overwrites
   the top-left 256x256 of D1's bytes. D2's record marks the shelved Z_big
   `vram_newer`.
   - `get_shelved_surface` returns Z_big's struct, which D1 still names. The
     reuse site (`update_surface_part`, `deferred_downloads_reference`)
     completes the batch with `download_surface_complete_deferred(SDC_REUSE)`.
   - That is a `SURFACE_DOWN` finish: submit, then wait for the GPU to go
     idle. It is 1.00 fin per flip, 11.5 ms on 05 and 20.5 ms on 06, the
     whole GPU frame so far.
   - Then `*surface = target`. Z_big is `vram_newer`, so it uploads 1200 KB
     from VRAM: `realupl=60`. VRAM over Z_big now holds D1 with D2 laid over
     it.

### `reuse`: struct identity, not data

A download's completion retires the binding it names:

- it sets `download_generation` to the generation the copy captured;
- it clears `draw_dirty` if no draw came since;
- it drops a clean shelved binding's watch.

After `*surface = target`, the struct is a different binding with
`draw_generation` restarted. A completion that came later would credit the
old binding's generation to the new one. With an equal draw count, it would
mark the new binding clean over VRAM that holds the old one's pixels
(`deferred_downloads_reference`'s comment). So the reuse completes first.

The data itself does not need to be in VRAM at that moment. What reads it is
the upload two steps later.

### The stale upload: it reads VRAM

`pgraph_vk_upload_surface_data` memcpys guest VRAM into its staging buffer,
and the GPU then converts that into the image. For f130 a compute pass
unpacks the guest Z24S8 into D32F_S8. The bytes it must read are D1
overlaid by D2. Those bytes exist on the GPU already, in the download
staging (`BUFFER_STAGING_DST`): the packed guest-format rows that each
completion would memcpy into VRAM.

### `surfupd`, two different things under one caller name

`pgraph_vk_surface_update` completes the pending downloads when
`surface_update_may_defer_downloads` says no.

1. **An uploading binding** (`upload_pending`). The upload reads VRAM, so the
   bytes have to land first. This is async794's fix-1 pilot on NBA 2005:
   detaching the reuse moved the wait here, `surfupd` 1.00 fin/frame,
   11.48 ms.
2. **A batch an earlier finish already submitted** (`frame >= 0`, not the
   flip's pre-download). It is completed here because it was believed cheap.
   The function's own comment says "cost a fence wait, not a finish, so they
   complete here as before". No correctness rule asks for it.
   - #474 already exempted the flip's pre-download from this rule.
   - Its readers are the trapped CPU access and an overlapping
     texture/vertex/blit range (`deferred_downloads_overlap_range`), the
     scanout's request, a new record (`complete_submitted_downloads`), the
     frame-slot rotation, and the next flip's pre-record. Each of them
     completes the batch first, and none of them is specific to the
     pre-download.

**NBA 07's surfupd is the second kind, not the rebind.** The counters:

- `su_upl=0` and `realupl=0`: no binding uploads, and both stale uploads are
  dropped by clears (`clrskip=120`).
- `surfupd=fence30`: a submitted batch, waited on every other flip, about
  17 ms each.
- The only finishes are `Sd` (the reuse) and `Fl` (the flip).

So the batch was submitted by the flip without a pre-download. On those
flips `pgraph_vk_prerecord_display_download` returned false before
recording, because the display surface was not found, not colour, or not
`draw_dirty`. The FLIP_STALL finish then submitted the pending download as a
plain batch, and the first surface_update after the flip waited for the GPU
to finish that frame. The brief's premise for 07 ("the `upload_pending`
rebind path gated by `surface_update_may_defer_downloads`") holds for 05/06
after a detach. It does not hold for 07's measured surfupd.

## 2. Which guest-visible behaviour depends on the completed download

- **A guest CPU read or write of the range.**
  - Under TCG, the evicted dirty binding's watch outlives its eviction
    (`unregister_cpu_access_callback_if_clean`).
  - Any access overlapping a pending download sets `wait_for_downloads` in
    `surface_access_callback`. The batch then completes before the access
    proceeds; with #474's lock release, `pgraph_lock_settled` keeps a write
    from landing under the staged copy.
  - This is the lazy completion at the point the guest reads, and it is kept
    unchanged.
  - After a reuse the old struct's watch is unregistered, but `surface_put`
    registers the new binding's watch over the same range. The match is
    exact on address, width, height and pitch, so the size is the same.
    D2's range stays under the shelved Z_small's watch (dirty, kept).
- **Emulator readers of guest memory.** Texture uploads, vertex fetch and
  blits go through `pgraph_vk_download_surfaces_in_range_if_dirty`, which
  completes any overlapping pending download first (`SDC_RANGE`). This is
  unchanged.
- **The scanout and the frame dump.** `render_display` uses the surface
  image. The frame dump calls `pgraph_vk_download_surface_complete_deferred`
  itself. Both are unchanged.
- **A later upload from guest RAM.** This is the stale upload above. It is
  the only reader that runs before the guest's next access. It is the one
  the GPU route replaces.

Without TCG there is no watch, so VRAM must be current when
surface_update returns. The switch does nothing there.

## 3. What a GPU-side route must preserve

1. **The bytes.** The rebound image must hold exactly what flag-off uploads:
   D1 laid under D2, in record order, after the guest-format round trip.
   - For f130 (NBA 05/06) that round trip quantizes depth to Z24.
   - A raw `vkCmdCopyImage` / blit from Z_big's or Z_small's VkImage keeps
     full D32F precision, so it is **not** bit-exact with flag-off.
   - It would also have to rebuild the top-left overlay from Z_small's
     image, a second copy of the region logic that already exists in
     staging space.
   - The byte-exact GPU route is the one HAKUX_SURFSPLICE built
     (lane.gpunonrender, 5eef1dacd9):
     - the upload memcpys current VRAM into its staging;
     - then, for each overlapping pending download in record order,
       `vkCmdCopyBuffer` copies that download's staging rows over it;
     - then the existing unpack/convert runs.
   - The image is then exactly what the CPU path makes, quantization
     included. For D16 (NBA 07) and plain colour, an image copy would also
     be exact. The splice covers both cases, so one route serves all three
     titles.
2. **Completion order and ownership.** The pending downloads stay pending
   and complete where they would have if no binding had uploaded: at the
   next trapped access, range reader, record, rotation or pre-record. A
   later download of the new binding is recorded behind them, so it lands
   last.
3. **Struct identity at reuse.** The pending entries must stop naming the
   reused struct before `*surface = target`.
   `deferred_downloads_clear_surface` does that. It is the path a struct
   freed with a pending download already takes (`invalidate_overlapping_surfaces`):
   the staged bytes still land in VRAM, and no binding is retired by them.
   The old binding's obligations are discharged by those bytes landing,
   which is what the CPU path's completion did. The new binding starts
   clean and stale (`upload_pending`) as before, and its image comes from
   the splice.
4. **The watch.** As in section 2. Nothing is unregistered that the CPU path
   kept.

### What still needs the CPU copy, kept lazily

The memcpy of the staged rows into guest VRAM still happens, at the
batch's completion. That covers a guest read, a guest write, a
texture/vertex/blit reader, the frame dump, and the next record or flip.
Nothing guest-visible can see VRAM before those bytes land, because every
path to it completes the batch first. The flag only removes the
**emulator's own** round trip, image -> VRAM -> image, and the wait the
PFIFO thread spent in its middle.

## 4. The design (HAKUX_SURFGPU=1)

All in `hw/xbox/nv2a/pgraph/vk/surface.c`. TCG only.

(a) **Reuse detach.**
- At the reuse site, a struct still named by a pending download, under the
  switch and with no handoff in this call, gets
  `deferred_downloads_clear_surface` instead of the `SDC_REUSE` completion.
- `shelf_stale` is kept, so the binding uploads as before.
- `surface_update_may_defer_downloads` and `g_surfsplice_armed` treat the
  switch like HAKUX_SURFSPLICE, so the upload splices instead of
  completing.
- Where the splice cannot cover the bytes, the upload path completes at
  `SDC_SURF_UPDATE` (`spl_cmpl`), so a fallback stays visible as `surfupd`.
  The cases are a submitted batch, a pre-download, or a swizzled download.

(b) **Flip batch without a display surface.**
- When `pgraph_vk_prerecord_display_download` cannot record the display
  surface but downloads recorded in this command buffer are pending
  (`num > 0`, `frame < 0`), the batch is marked as the flip's pre-download
  with no display surface (`display_predownload_surface = NULL`).
- The FLIP_STALL finish submits it either way. Marking it only makes the
  next surface_update leave it pending, as #474 does for the pre-download,
  instead of waiting on its fence.
- NULL is already a legal value: `deferred_downloads_clear_surface` sets it.
- The handoff test compares against it and does not match. The frame dump
  reads `display_predownload_frame_index`, which equals
  `deferred_downloads_frame` for a flip-submitted batch.

Counters: `[surfgpu] on` once, when the switch is read. Under NV2A_PERF_LOG
on Android, one `[surfgpu]` line per `[sdcall]` window: `detach=` reuse
completions skipped and `nodisp=` flip batches marked. `[sdcall]`'s format
is unchanged, so `reuse`, `surfupd` and `spl=` are read exactly as in the
baselines.

## 5. Where the wait can go instead (falsifiers)

- **`record`.** The flip's batch is completed by the next frame's first
  `download_surface_record_deferred` (`complete_submitted_downloads`), as in
  the baseline (`record=pre30`, 0.01 ms/frame).
  - Flag-off, the reuse finish handed the GPU most of the frame mid-frame
    (06's 20.5 ms reuse wait is about its whole 19.6 ms GPU).
  - Flag-on, the GPU gets the frame at the flip. If the next frame reaches
    its first eviction before the GPU has finished, `record` waits the
    remainder.
  - That residual is bounded by ph_GPU minus the CPU time from flip to first
    eviction, which is not measured. Avoiding it would take a second
    download batch (two lists, two fences). Its natural home is
    PGRAPHVkState in renderer.h, which is outside this lane's territory. A
    file-static in surface.c and draw.c would work, but it is a larger
    change. It is the next step if `record` takes most of the wait.
- **`surfupd` `spl_cmpl`.** The splice refuses the batch.
- **`range`.** A texture scan completes it, as on Forza (gpunonrender F1).
- **`defer_full`.** The staging or the 64 entries fill.

So the claim is on the **sum of all `[sdcall]` waits** and on gfps, not on
`reuse` alone. The CPU memcpy of 1200 KB per flip into the upload staging
stays (`upl` 0.24 ms/frame in 06's `[surf413]`).

## 6. Ranking (P x win)

- **Splice + detach + flip-batch mark** (built here). This is the GPU route
  the hardware offers for a byte-exact rebuild: buffer copies the GPU
  already has the data for, in the command buffer it is already recording.
  - P that `reuse` falls to ~0 on 05/06: 0.85. The gates were checked by
    reading against the counters: the batch is unsubmitted at the reuse
    (`fin`, not `fence`/`pre`), f130 linear, pitch 2560 >= 640*4.
  - P that gfps rises by >= 2 on 06: about 0.5. That depends on the `record`
    residual above.
  - Win if it holds: NBA 06's 20.5 ms/frame is 51% of its ph_Tot. 43.3 ms
    -> about 25 ms is the two-VBLANK side of 33.3 ms.
- **Image-to-image copy into the shelved Z_big plus no upload.** It saves the
  0.24 ms memcpy on top, but it is not bit-exact for f130 (section 3). Its
  win over the splice is under 1 ms, at a real risk to depth pixels. Not
  built.
- **A second download batch** (removes a `record` residual). Whether it is
  needed is decided by this arm's `record` number, so it is not built first.

## 7. Arms (one build, 1e5b1af818; env-only A/B on the Nova)

Predictions registered and committed (c49c78ddf2) before any run:
`surfgpu1009-nba2005-soak.json`, `-nba06-soak.json`, `-nba07-soak.json`
(named `expect` rules scored by `sg_judge.py`) and `-golden.json` (disc
suites, `ab_compare.py`, worse=0 over ten surface/texture suites).

Every arm is queued by hand: `arms.sh` skips title soaks and a_ref == b_ref
pairs. B (flag on) goes first and A (flag off) last, so the env left behind
is the shipped one. B starts on a cleared shader cache when the apk is new.
Its cold-cache compiles bias against the prediction.

Pilot (two requests, 2 x (500 + 90) s = 19.7 min, under the 30-min gate):

| arm | request | env |
|---|---|---|
| B NBA 05 | `1-1791586168-surfgpu1009-381463` | GPUXFR, FRAMETRACE, SURFGPU=1 |
| A NBA 05 | `1-1791586172-surfgpu1009-381687` | GPUXFR, FRAMETRACE |

`prequeue.py "NBA Live 2005"` printed only the exempt fps-bar BLOCK.
