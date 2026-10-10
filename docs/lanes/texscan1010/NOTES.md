# lane.texscan1010 -- create_texture()'s surface downloads at the NFS MW race start (#433, 0.5)

## 1. What the existing runs already say (no device time)

Read from perdrawon1010's fix-off run `1-1791644405-perdrawon1010-365120` (ref 4ad1154e55, perflog,
NFS MW `nfs-mw-quickrace`), the `txw[...]` and `txr[...]` lines inside the race windows:

| window | ct ms/frame | sdl ms/frame (calls/frame) | scan ms/frame (scans/frame) |
|---|---|---|---|
| heaviest | 19.40 | 8.94 (0.50) | 9.23 (443.7) |
| lighter | 6.95 | 2.92 | 3.10 |

- Every 60-frame window reads `txr dl30 ... scdl240 s2tc60` with `txdl[cube30]`.
- **There are two download sites in create_texture(), not one.**
  - The **range scan** (`scan`) makes about 4 downloads a frame and ends in one `SDC_RANGE` completion.
    This is the `[sdcall] range=fin60/dl240` the brief names.
  - The **SDL block** (`sdl`, the download of the surface at the texture's own address when s2t refuses
    it) costs as much again. Its only reason in these windows is `cube`, 30 per window, one every other
    frame. `[txdl794] why=cube surf 128x128 pitch512 swz1 color1 bpp4 | tex 128x128 levels1 cube1 fmt0x6
    lin0 bpp4` is a swizzled A8R8G8B8 128x128 cube map whose face 0 is a render target: the car's
    environment map.
  - The brief's `range` 4.4 ms/frame therefore misses the SDL half. Both are synchronous, and both go in
    this lane's table.
- `scans/frame` is 443.7 in the heavy window. The range cache (`tex_surf_range_cache`) is defeated on
  nearly every bind, because `surface_draw_gen` moves with every draw. Most of those scans download
  nothing, so the instrument times the scans that download separately from the ones that do not.

## 2. Step 1 instrument: `[tsc]` (texture.c, NV2A_PERF_LOG only)

Every surface that the SDL block or the range scan is about to download is classified against the texture's
layout:

| class | meaning |
|---|---|
| `base` | offset 0, not a cube; carries the s2t refusal reason (`levels dim cube pitch swz cvt bpp upl oth`) |
| `face` | a whole cube face whose shape is the texture's (dims, bpp, swizzled to match) |
| `facex` | a whole cube face that does not match |
| `mip` | starts at a mip level's offset |
| `sub` | starts anywhere else inside the texture |
| `part` | reaches outside the texture's range |

- The walk uses the scan's own three predicates (active, shelved, invalid lists). Its count is checked
  against the scan's real one (`miss`).
- Each distinct texture/surface pair is logged once when first seen (`[tsc] new #k ...`, tag hakuX), with
  both shapes and the offset.
- Each 60-flip window logs a `[tsc] f60 ...` line (tag hakuX-stall) with:
  - the downloads per class;
  - each pair's count;
  - the scan wall time with and without a download.

## 3. Census: what the downloads are (run `1-1791648919-texscan1010-2004607`)

Nova, ref 4784750c3c (perflog), `nfs-mw-quickrace`, 500 s. There are 307 `[tsc] f60` windows: 125 with
`face270`, one partial (`face81`), and the rest with no downloads (menus and loading). The race windows have
no other class: `base0 facex0 mip0 sub0 part0 miss0`.

All downloads are whole faces of **one texture**, the car's environment cube map:

- texture @352a080: len 393216, fmt 0x6 (SZ_A8R8G8B8), 128x128, levels 1, cube, no border;
- faces are 65536 bytes apart (`ROUND_UP(128*128*4, NV2A_CUBEMAP_FACE_ALIGNMENT)`).

Each face is its own render target: fmt 0x8 (A8R8G8B8), 128x128, swizzled, pitch 512, 65536 bytes. All six
are on the active list.

| # | surface | offset | face | site | downloads / 60 frames | why the direct path does not take it |
|---|---|---|---|---|---|---|
| 0 | @352a080 | +0 | 0 | SDL block | 30 | s2t refuses: `shape->cubemap` (check_surface_to_texture_compatiblity) |
| 1 | @353a080 | +65536 | 1 | range scan | 60 | s2t looks only at the texture's own address (`pgraph_vk_surface_get(texture_vram_offset)`) |
| 2 | @354a080 | +131072 | 2 | range scan | 60 | same |
| 3 | @355a080 | +196608 | 3 | range scan | 60 | same |
| 4 | @356a080 | +262144 | 4 | range scan | 30 | same |
| 5 | @357a080 | +327680 | 5 | range scan | 30 | same |

The game redraws faces 1-3 every frame and faces 0, 4 and 5 every other frame.

The bind path does not take any of them. It binds the surface's own image as the texture
(`tex_surface_direct`), so it exists only when s2t accepts, and s2t accepts only a single-level 2D surface at
the texture's address. A cube has to be one image with six layers, and no single surface image is that.

Cost inside the 125 race windows (ms per frame, from `txw[...]` and `[tsc]` on the same flip):

| | min | median | mean | max |
|---|---|---|---|---|
| create_texture (`ct`) | 4.27 | 8.22 | 8.25 | 19.89 |
| SDL block (`sdl`, face 0) | 1.74 | 3.41 | 3.53 | 9.19 |
| range scan (`scan`) | 1.97 | 3.71 | 3.76 | 9.43 |
| scans that download (`dlscan`) | 1.96 | 3.69 | 3.75 | 9.41 |
| scans that download nothing (`nodl`) | | | 0.04 | 0.06 |

- The SDL block and the scan are 7.3 of create_texture's 8.25 ms/frame.
- Each is a synchronous finish followed by a copy back from the GPU.
- `[sdcall] range=fin60/dl240` matches the scan alone, which is why the brief's 4.4 ms missed the SDL half.

## 4. Step 2: `HAKUX_TEXSCAN=1` (texture.c, surface.c; default off)

**Route.** When a cube texture of the census shape has drawn faces in its range, both downloads are skipped
and each drawn face is copied on the GPU, `vkCmdCopyImage` from the surface image into array layer `face` of
the texture image.

- **Census shape:** levels 1, 2D, swizzled, no border, scale 1, a format with no conversion, no I8, no
  compression, no `replace`.
- **Recording:** the copy goes into `r->command_buffer` in order, through `pgraph_vk_begin_nondraw_commands`,
  so it sits after every draw that rendered the face. Barriers: the texture goes SHADER_READ_ONLY ->
  TRANSFER_DST -> SHADER_READ_ONLY; each surface goes `image_layout` -> TRANSFER_SRC -> back.
- **The bytes are the same as off.** A color download of a swizzled surface is a raw copy of the host image
  (the store and the texture read cancel). Uploading a swizzled, non-converted format is an unswizzle of
  those bytes into the same linear layout. So layer `face` of the texture holds what the off route's upload
  would have put there.
- **The pad-alpha and x1a7 rules** need `surface_is_texture_source`, which is false for a cube. They do not
  apply on either route.

**Where the route says no** (`texscan_plan`), the existing downloads run unchanged:

- a shelved or invalid surface that is draw_dirty overlaps the range;
- a drawn surface is not one whole face: it is not at a face offset, it is a duplicate face, a zeta surface,
  of the wrong size, or s2t-incompatible with the face's 2D shape;
- the surface is `upload_pending`.

**VRAM stays coherent: deferred, not removed.**

- The faces stay `draw_dirty`. Every other reader still downloads them before reading: the CPU watch, other
  range scans, blits, eviction, savevm.
- A deferred download already pending in the range completes first, as the off route's scan would
  (`pgraph_vk_texscan_complete_range`, surface.c, SDC_RANGE).
- After the copy, every other texture binding over a copied face is marked possibly dirty
  (`pgraph_vk_mark_textures_possibly_dirty`). Off, the download and upload would have marked them through
  the dirty bits.

**Skipping work** (`texscan_memo`, 16 entries):

- **Unchanged face.** A face is not copied again when its source has not changed. The source is identified
  by the surface pointer, vram_addr, image, w, h, draw_time and draw_generation, plus `surface_list_gen`.
- **Re-upload.** When the texture is uploaded from VRAM (a miss, or a found node re-hashed dirty), every
  planned face is copied again.
- **Later draws this frame.** `dirty_check_frame = frame_time - 1` stops the per-frame dirty-check skip from
  hiding a face drawn later in the same frame.

**The #474 FAF is skipped and counted (`faf`).** The copy is recorded after the earlier draws' reads in the
same queue order, and the TRANSFER_DST barrier waits on FRAGMENT_SHADER reads, so overwriting the image
while the GPU still samples it is ordered by the spec.

**Instrument.** `[tsc] ... ts[bind cp keep force faf cmpl fb]` per 60 frames (perflog builds only):

| counter | meaning |
|---|---|
| `bind` | binds the route took |
| `cp` | faces copied |
| `keep` | faces skipped because unchanged |
| `force` | full re-copies after an upload |
| `faf` | FAFs that would have been needed |
| `cmpl` | deferred downloads completed |
| `fb` | refusals that fell back to the downloads |

A `[texscan] on` line is logged once per process, and `[texscan] first copy ...` once per process.

**Prediction for the switch, from the census.** With the switch on, the 7.3 ms/frame of SDL plus scan should
drop to the cost of recording 1-6 copies (well under 0.5 ms). The vblank histogram is the deciding measure
(section 5).

## 5. Arms (queued 2026-10-10 ~17:05 UTC, Nova)

Both legs are env A/Bs on one ref, e654516849. Arms.sh skips a prediction whose `a_ref == b_ref`, so the lane
queues them itself with `--expect`.

The head moved twice after the queue, to 9acb2fcffb (no NV097 constant in new code). Neither move changes
what the switch does:

- the I8 test was redundant: `pgraph_texture_format_is_converted()` already refuses I8;
- the census instrument now reads a compressed texture's offsets past its base as `sub`.

**Pixel leg**: `docs/testing/predictions/texscan1010-pixels.json`.

- 29 suites (every golden suite with texture, surface, cube or render in its name; 721 goldens).
- RenderTextureLoop is skipped, as the arms job does.
- Release build. B (on) runs first, then A (off).
- Predicted:
  - every capture is the same between arms or inside the band;
  - B's logcat has no `[texscan] first copy` line. No suite renders into a cube's faces, so this leg shows
    the switch inert where it does not fire. It does not exercise the copy.

| arm | request |
|---|---|
| B, HAKUX_TEXSCAN=1 | 1-1791650753-texscan1010-2542806 |
| A, no env | 1-1791650757-texscan1010-2543971 |

**NFS leg**: `docs/testing/predictions/texscan1010-nfs.json`, read by `texread.py`.

- Perflog build, 500 s each, route `docs/lanes/texscan1010/nfs-mw-quickrace.route`.
- Queued as `--route ../../../lanes/texscan1010/nfs-mw-quickrace`. The prediction's `route` field says
  `nfs-mw-quickrace`.
- Order off, on, on, off, so neither state always inherits a warm shader cache.

| arm | request |
|---|---|
| off | 1-1791650940-texscan1010-2621346 |
| on | 1-1791650940-texscan1010-2621780 |
| on | 1-1791650941-texscan1010-2622254 |
| off | 1-1791650942-texscan1010-2622720 |

Off baseline, read with texread.py over the same windows (12 starts per run):

| run | build | period ms (fps) | v2 / v3 / v4+ | range ms/frame | sdl + scan ms/frame |
|---|---|---|---|---|---|
| census 2004607 | 4784750c3c perflog | 46.4 (21.5) | 32.1 / 57.6 / 10.1 % | 4.05 | 3.93 + 4.09 |
| perdrawon1010 365120 | 72fe2eabc46e | 43.5 (23.0) | 42.7 / 51.5 / 4.8 % | 3.89 | 3.75 + 3.90 |
| perdrawon1010 726861 | 72fe2eabc46e | 41.9 (23.9) | 48.3 / 48.1 / 2.1 % | 3.95 | 3.79 + 3.96 |

Predicted on - off, pooled over 2 runs per state:

| leg | predicted | point estimate |
|---|---|---|
| R | range on <= 0.5, off >= 2.5 ms/frame | |
| P | period in [-12, -2] ms | -5 ms |
| H | v3+v4 share down >= 10 points, v2 share up >= 10 points | |
| F | matched-work gfps in [+1, +8] | +2.5 |
| V | the route copied faces in every on run, never in an off run | |

The start still does not hold 30 fps.

What refutes the prediction:

- **R passes and P/H fail:** the waits were hidden behind GPU-bound time. The switch then has no fps value at
  the start, and stays off.
- **R fails on:** something else downloads in the starts once the cube stops. ts[fb] and [tsc] cls name it.

**Pixels in game:** the car's reflection is the copied cube. The route frames at each mark are checked by
eye, on vs off.

**Not repeatable from here:** a later lane should not re-measure the off baseline. The three runs above are
on disk.
