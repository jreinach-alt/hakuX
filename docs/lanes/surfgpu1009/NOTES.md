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

### 7.1 NBA Live 2005 pilot: every scored leg PASS

`sg_judge.py --expect surfgpu1009-nba2005-soak.json --a ...381687 --b
...381463 --floor 1-1791525926-fpstelemetry1008-4089047`. Same apk
6257c859de70 in both arms. B ran first on a cleared shader cache, A kept it.
Neither arm had a thermal pause. `[surfgpu] on` appears in B only.

| post-mark | A (flag off) | B (HAKUX_SURFGPU=1) | rule |
|---|---|---|---|
| gfps | 25.25 | **43.00** | P4 gain >= 1.5: +17.75 |
| ph_Fin ms/frame | 12.80 | 2.80 | P3 drop >= 8.0: 10.00 |
| ph_Tot (render thread) | 29.10 | 12.90 | |
| ph_GPU | 9.80 | 14.00 | not scored, see below |
| F (frame period, ms) | 39.61 | 23.25 | |
| gbusy / gidle (guest, ms/frame) | 19.22 / 21.38 | 21.99 / 1.42 | |
| vcpu load % | 57.22 | 90.26 | |
| `reuse` wait ms/flip | 11.84 (fin 1.00/flip) | 0.00 | P0 >= 8.0, P1 <= 1.0 |
| `record` wait ms/flip | 0.01 | 0.21 (pre 1.00/flip) | the residual |
| all `[sdcall]` waits ms/flip | 11.85 | 0.22 | P2 ratio <= 0.5: 0.02 |
| `[surfgpu]` detach / nodisp per flip | - | 1.00 / 0.50 | P1 detach >= 0.9 |
| `spl=` up / dl / cmpl per flip | 0 / 0 / 0 | 1.00 / 2.00 / 0.00 | |

The n column is 143 (A) and 138 (B) decompose rows of 2 s each, and 116
(A) and 200 (B) post-mark `[sdcall]` windows. surfdl1008's
`postmark_sdsurvey.py` reads the same: A sd/flip 1.00 with `reuse`
11.84 ms/frame, B sd/flip 0.00 with `record` 0.21.

- **Moving player, from the hold frames.** Both arms are a live game after
  the mark, minutes apart.
  - B: clock 11:00 -> 10:25 -> 9:37, DET 4 -> 9 -> 14, players in new
    places each frame. The Pistons splash in two holds is the game's
    transition after a basket.
  - A: 10:55 -> 9:56, 3 -> 8.
  - The game clock is frame-locked. B advanced 83 game-seconds in 144 s
    of wall time, A 59 in 143.
- **The wait is gone, and the frame is now the guest's.** The render
  thread is at 12.9 ms of a 23.25 ms frame, and the guest idles 1.42 ms a
  frame (21.38 in A) at 90% vCPU load. NBA 05's next limiter is guest CPU
  work, about 22 ms/frame, not surface downloads.
- **ph_GPU +4.2 ms/frame is not attributed.** This instrument cannot split
  it: GPU clocks read the same range in both arms (401-615 MHz), and the
  splice adds about 1.46 MB/frame of buffer copies, which is well under a
  millisecond of bandwidth. It does not limit the frame (ph_Tot 12.9 < F
  23.25).
- **Pixels, route frames.** Regions B vs A are the same order as A vs the
  older flag-off run on every step (menus, cutscenes and gameplay differ by
  timing in both). The only static-screen difference (s02-s04, 0.2-0.3%,
  x 879-1071 y 85-110) is the title screen's pulsing PRESS START. The
  floor's s03 differs in the same strip. By eye, B's gameplay frames show
  the court reflection, shadows, crowd, scoreboard and HUD with no stale
  or garbled surface. Route frames cannot test a guest readback exactly;
  the disc golden below does.

Pilot verdict written to `pilots/surfgpu1009.ok`. Queued next, B first
in each pair:

| arm | request |
|---|---|
| golden B / A | `1-1791588861-surfgpu1009-610569` / `-610665` |
| NBA 06 B / A (460 s, nbalive06) | `1-1791588869-surfgpu1009-611883` / `-612026` |
| NBA 07 B / A (480 s, nbalive07) | `1-1791588870-surfgpu1009-612141` / `1-1791588871-surfgpu1009-612271` |

## 8. Resume, attempt 1 (2026-10-09 ~17:00 PDT)

**Why the previous session did not finish.** It queued the six requests
above at 16:34 PDT and ended without a `waiting:` line. None of the six had
started: the Nova was running `pmucounters`' Amped 2 pair
(`1-1791588183-pmucounters-521453` running at 16:59 PDT, `-521720` queued
ahead of these). Nothing in this lane failed. This session reads the six
results as they land.

### 8.1 The generalisation arm, read from the code before any device time

Brief step 6 names Spider-Man 2 or NHL 2K3. I ran surfdl1008's
`postmark_sdsurvey.py` on fpstelemetry1008's full runs (already on disk, not
re-run) and read the `[evict372]` pairs against the splice's gates
(`surfsplice_dl_ok`, `surfsplice_upload_layout`):

| title | run | post-mark waits | evict pairs (one address) | switch reaches it? |
|---|---|---|---|---|
| Spider-Man 2 | `1-1791538675-fpstelemetry1008-1143702` | `surfupd` fin 2.50/fr, 2.60 ms/fr; `record` 0.80; `range` 0.78 | Z f130 **sz** 256x256 -> 128x128 -> 64x64 -> 256x256 | **no** |
| NHL 2K3 | `1-1791540124-fpstelemetry1008-1240862` | `surfupd` fin 3.50/fr, 6.67 ms/fr (`why=stale`, no `reuse`); `record` 1.03 | Z f130 ln 640x612 <-> 640x480; 640x612 <-> Z f130 **sz** 256x512 | partly |

- **Spider-Man 2.** Every zeta binding in the chain is swizzled D32F_S8.
  `surfsplice_dl_ok` refuses a swizzled download, because its staging is
  unswizzled and the CPU swizzles at completion. `surfsplice_upload_layout`
  refuses a swizzled depth upload. Flag on, every `surfupd` there still
  completes at `SDC_SURF_UPDATE` (`spl_cmpl`). An arm would measure nothing,
  so none is queued.
- **NHL 2K3.**
  - The 640x480 <-> 640x612 linear half can splice.
  - Any upload overlapping the pending swizzled 256x512 download cannot. A
    fallback completes the whole batch, so the GPU time queued before it is
    still waited.
  - So the switch removes at most part of the 6.67 ms/frame. How much is set
    by the order of the four evictions in the frame, which no counter
    records.
- **What would reach both.** A splice for swizzled downloads and uploads.
  The download's staging is linear guest-format rows. The upload's VRAM
  bytes are swizzled, so a GPU swizzle (compute) would replace the CPU's.
  For square power-of-two nests like Spider-Man 2's, the smaller texture's
  swizzle is a prefix of the larger's.
  - It is a separate change with its own golden.
  - Win: NHL 2K3 about 6.7 ms/frame, Spider-Man 2 about 2.6. Both are
    smaller than NBA's.
  - It is the next lane's step if NBA 06/07 hold, not this lane's.
- NHL 2K3 is the only generalisation arm with a mechanism this switch
  touches. It is queued only after NBA 06/07 and the golden are read, with
  its own registered prediction.

## 9. Resume, attempt 2 (2026-10-09 ~19:55 PDT): the record residual, and why the previous session stopped mid-build

**Why attempt 2 did not finish.** Its session read the six results section 8
left pending (golden B/A, NBA 06 B/A, NBA 07 B/A), found a real pixel bug and
a real residual, fixed the first, built most of a fix for the second, and
ended without committing the second fix or writing this section. Reconstructed
from the working tree and dispatch results, in the order it must have
happened:

1. **Golden B/A** (`...610569`/`...610665`) moved exactly one capture:
   `Image_blit/Overlap_TR_Outside` 1 -> 16384 px. Root cause and fix: commit
   `c663a91697` (a record does not retire the generation under the splice, so
   an evicted surface whose download was left pending stayed draw_dirty and
   got recorded a second time, behind the subsurface's download; completion
   in record order put the backbuffer's clear over the gradient). A dedup
   check closes it. Prediction for the recheck registered as
   `surfgpu1009-golden2.json`, committed `50892613de`, pair queued
   (`...895207`/`...895356`) -- this is the "two results landed, unread" the
   lanewaker resume pointed at.
2. **NBA 06 B/A** (`...611883`/`...612026`): read now with `sg_judge.py`,
   every scored leg PASSes clean on the already-built `1e5b1af818`/dedup-fix
   combination that golden2 also uses: reuse 21.03 -> 0.00 ms/flip, all waits
   21.04 -> 2.19 ms/flip, ph_Fin -20.1 ms, gfps 20.26 -> 45.79 (registered
   min +3.0). No further work needed here.
3. **NBA 07 B/A** (`...612141`/`...612271`): read now with `sg_judge.py`,
   **FAILS P2** (`sdcall_wait_sum_ratio_max` 0.5, measured 0.66). `reuse` and
   `surfupd` both reach 0.00 ms/flip (every P1 leg passes, P0 confirms the
   baseline waits were real), but `record` rises to 12.68 ms/flip in B,
   where A had 0.01: the wait did not shrink, it moved caller. gfps still
   gains (21.71 -> 23.93, +2.22, just over the 2.0 min) because `record`'s
   12.68 ms is less than `reuse`+`surfupd`'s 19.65, but the sum-ratio leg is
   what section 6 flagged as the open question: *"A second download batch
   (removes a `record` residual). Whether it is needed is decided by this
   arm's `record` number, so it is not built first."* The arm says it is
   needed.

**The mechanism (`g_sg_held`, uncommitted in the working tree when this
session started, reviewed and finished here).** `record`'s wait is
`complete_submitted_downloads`: when a new download is recorded and an
earlier finish has already submitted a batch, one fence covers one batch, so
the new record used to wait the old batch out before starting its own
(`download_surface_complete_deferred(d, SDC_RECORD)`). NBA 07's flip
piggybacks the display download onto the flip stall (`surfupd`'s fix, part
(b) of section 4) often enough that the *next* frame's first record now hits
an already-submitted batch and pays for the GPU work the flip just handed
it -- the residual section 5 named and declined to build ("outside this
lane's territory... the next step if `record` takes most of the wait").

The fix: hold the submitted batch aside with its own fence
(`g_sg_held`, file-static in `surface.c`, not in `PGRAPHVkState` --
`renderer.h` is outside this lane's territory, as section 5 said, so the
static is the one-file version of the "next step") instead of waiting it at
record time, and let the new download start the next batch
(`r->deferred_downloads`) immediately. The held batch is always the older of
the two, so:

- it completes first wherever either does (`complete_staged`, used by both
  `pgraph_vk_complete_staged_downloads` and the new `surfgpu_complete_held_at`);
- every guest-visible completion path in section 2/3's list now checks it
  too: `deferred_downloads_overlap_range` (a trapped CPU access, a blit/vertex
  range), `surfsplice_upload_ok` (a rebind must not splice over bytes the
  held batch still owns), `deferred_downloads_pending` (replaces plain
  `num_deferred_downloads > 0` at each of those call sites, including
  `surface_access_callback`'s `wait_for_downloads` and
  `pgraph_vk_download_surfaces_in_range_if_dirty`), `deferred_downloads_reference`
  and `deferred_downloads_clear_surface` (a rebind of a surface the held
  batch still names detaches or NULLs it there too, not just in the current
  batch), and `surface_handoff_partner` (a display pre-download the held
  batch is keeping is not handed off);
- on its own, with no current batch forcing it, it completes at the frame
  slot rotation that its fence belongs to (`pgraph_vk_surfgpu_slot_retired`,
  called from `vk/draw.c`'s `pgraph_vk_finish` right after that slot's fence
  is known waited -- outside the `frame_resources_in_use` test, because
  `pgraph_vk_flush_all_frames` can wait a slot's fence without going through
  the normal per-frame cleanup that would have completed it) -- this is the
  bound on the residual section 5 left unmeasured ("bounded by ph_GPU minus
  the CPU time from flip to first eviction"), now paid at a point this
  session did not have to guess about.
- the staging buffer is linear and the held batch's rows are behind the
  current batch's offset until the held batch frees them, so a new download
  that would overlap them wraps to the front instead (`surfgpu_staging_fits`,
  `g_sg_wrap`) rather than reusing live bytes.
- `download_surface_record_deferred`'s dedup check (part 1 above) now also
  checks the held batch, since a surface the held batch already downloaded at
  its current generation must not be recorded a second time either -- the
  same bug golden2 is rechecking, one batch earlier.

Two submitted batches are never both held: `surfgpu_hold_submitted` completes
whatever is already held (waiting its fence) before holding the new one, so
there is one `g_sg_held` slot, not a queue. This keeps the design to the one
extra batch section 6 asked for, not an unbounded pipeline.

**What this does not change.** Still behind `HAKUX_SURFGPU=1`, still default
off (`surfgpu_hold_submitted`'s own gate is `tcg_enabled() && surfgpu_enabled()`,
the same switch). Telemetry gains `[surfgpu] hold= hwait= hrot= wrap=` on top
of the existing `detach=`/`nodisp=`/`dedup=`, so a B run with none of the four
set to 0 is evidence the held-batch paths were reached, same as `detach=` was
for part (a).

**Plan from here, in the order that decides something first:**
1. Build (already running in the background this session started) --
   compiles or it doesn't, decided before any device time is spent.
2. One NBA 07 pilot pair on the new ref (2 requests, under the already-valid
   `pilots/surfgpu1009.ok` window): does `record` fall and does P2 clear.
3. One golden pair on the same ref, since this mechanism touches the same
   completion-ordering class of bug golden2 just caught once already, and a
   second `g_sg_held`-shaped one is exactly the kind of bug a per-60-frame
   telemetry counter can miss (golden2's own `dedup=` sum was 0 across the
   kept logcat even though the per-capture pixel count is the thing that
   actually confirmed the fix -- see golden2's read below). The per-capture
   pixel table is the decision; the counter is corroboration only, not proof
   by itself.
4. If both hold, NHL 2K3 (section 8.1) is still the only generalisation
   candidate with a mechanism this switch reaches, and is unaffected by
   this section's change (its wait is `surfupd`/`why=stale`, not `record`).

### 9.1 golden2 read: dedup fix confirmed by the pixel table, not by the counter

`ab_compare.py --a ...895356 --b ...895207 --expect surfgpu1009-golden2.json
--allow-same-binary`: **PASS**, worse=0, 266/266 same, byte-identical hash on
every shared capture. The specific capture golden1 broke is back to golden1 A's
value exactly: `Image_blit/Overlap_TR_Outside` B 1 px (was 16384), A 1 px, at
the same registered pixel (176,180).

The prediction's own text named a second, falsifiable check: B's `[surfgpu]`
line should carry `dedup= > 0` summed over the run, "the skip fired". It did
not -- `grep '\[surfgpu\]' ...895207/logcat1.txt` sums to `dedup=0` across all
3 printed windows (`detach=1 nodisp=0` on the first, matching golden1 B's own
first window exactly). Only 3 `[surfgpu]` windows are in the kept logcat
against 266 captures, so the dedup hit -- if it happened -- is very likely in
a window the retained log cut, not evidence the fix is a no-op: the decisive
evidence is the per-capture score, which moved from broken to matching. Say
what the instrument cannot see: this run's `[surfgpu]` counters cannot confirm
*why* the capture is fixed, only the capture itself can, and it says the fix
works. A future read of this dedup path should keep the full logcat or grep
the un-truncated device log, not the harness's retained tail, if the counter
itself needs confirming.
