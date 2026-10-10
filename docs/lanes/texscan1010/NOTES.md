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

## 6. Attempt 2: why attempt 1 did not finish

Attempt 1 stopped on purpose, in the waiting state the brief prescribes. It queued the 6 Nova runs of section 5,
pushed `WAITING` with them (8fa509de16, 16:51 UTC), and ended. The last run finished at 18:13 UTC. Nothing
failed. What was left was reading the runs, the verdict and PR.md, which is this attempt.

Attempt 2 merged origin/master (dff4de7bbe). Master's changes since the base touch `renderer.h` and `shaders.c`
only, nothing in this lane's files, so the measured build (e654516849) is still what the switch does on the head.

## 7. Pixel leg: the switch does nothing outside a cube

B (on) `1-1791650753-texscan1010-2542806`, A (off) `1-1791650757-texscan1010-2543971`, apk 67490eb10d09, 719
of 719 captures in both arms.

`ab_compare.py --expect texscan1010-pixels.json` FAIL, 1 of 719. 718 captures are the same. The one that moved:

| capture | A (off) px off golden | B (on) |
|---|---|---|
| Texture_border/2D_BorderTex_SZ | 17103 | 16268 |

It is device noise in this test, not the switch:

- **The switch cannot reach it.** A 2D border texture is refused at `texscan_shape_ok` (not a cube, has a
  border), so both arms run the same code. B's logcat has `[texscan] on` and no `[texscan] first copy`, as
  predicted: no test in these 29 suites rendered into a cube and sampled it.
- **B's value is this test's usual one.** 16268 is what most recent APKs read for this capture: 7ff91c72566a x3,
  893d6f55a111 x3, bd60ff410b34 x3, d5aa7a873b21 x4, and others. The same test has also read 20618, 9328 and
  1120 on those APKs. The off arm, 17103, is the outlier.

So this leg shows the switch inert where it does not fire. It does not exercise the copy. The copy's pixels
are the car's reflection at the NFS race start: the `s5-g11` route frames of off1 (`104240`, 68 mph) and on2
(`110056`, 59 mph) both show a moving car and a reflection of the same kind on its body. It is not black,
stale or garbage.

## 8. NFS leg: the downloads are gone, and the start is slower

Runs, apk 15d83b0da02e, perflog, 12 starts each:

| run | state | period ms | v2 / v3 / v4+ | range ms/frame | gfps | draws/frame |
|---|---|---|---|---|---|---|
| `1-1791650940-texscan1010-2621346` | off | 46.6 | 31.8 / 57.8 / 10.3 % | 4.03 | 22.7 | 1015 |
| `1-1791650940-texscan1010-2621780` | on | 49.4 | 27.3 / 52.3 / 18.8 % | 0.00 | 21.7 | 881 |
| `1-1791650941-texscan1010-2622254` | on | 48.9 | 26.7 / 53.2 / 17.8 % | 0.00 | 22.1 | 891 |
| `1-1791650942-texscan1010-2622720` | off | void | | | | |

**off2 is void.** Its boot inputs went one menu level too deep. At `s12-main_menu` the game was already in the
career main menu, and every start after that was the "You must create a new alias" dialog: 59 fps, 389
draws/frame, range 0. The route has no check that it reached the main menu.

texread.py's V leg passed it anyway. V checks starts, route finished, env and build, not what was on screen
(section 11). The registered judge over all 4 runs reads:

`legs: V=PASS R=PASS P=FAIL H=FAIL F=FAIL N=PASS` (period +25.6 ms, gfps -26.02; both are the void run)

Over the 3 valid runs, `python3 docs/lanes/texscan1010/texread.py <off1> <on1> <on2> --expect ...`:

| leg | predicted | measured | |
|---|---|---|---|
| R | range on <= 0.5, off >= 2.5 ms/frame | on 0.00, off 4.03 | PASS |
| P | period on - off in [-12, -2] ms | **+2.6** (off 46.6, on 49.2) | FAIL |
| H | v3+v4 down >= 10 points, v2 up >= 10 | v3+v4 **+2.9**, v2 **-4.8** | FAIL |
| F | matched-work gfps in [+1, +8] | **-1.40** over 90 rows (frame_ms +3.0) | FAIL |
| N | >= 30 pace lines per state | off 33, on 57 | PASS |

`txw` agrees with R: create_texture's own time goes from ct 8.96 ms/frame (sdl 3.87 + scan 4.02) to ct 1.04
(sdl 0.00, scan 0.01).

The route, per 60 frames on: bind 122.7, cp 273.0, keep 461.3, force 2.0, faf 48.8, cmpl 0.5, fb 0. It
never fell back. With it on, `[sdcall] range` still shows `fin 0 dl 23.7` per 60 frames at 0.00 ms. These are
scan downloads with no finish and no measurable cost.

**The sign does not depend on off2.** The on period, 48.9 and 49.4, is above every off reading of this start on
record: 46.6 here, 46.4 (census `1-1791648919-texscan1010-2004607`), 43.5 and 41.9 (perdrawon1010). No
replacement off run can make on - off negative, so none was queued.

**No MC2 pair.** Brief step 5 runs one "if NFS wins". It did not.

## 9. Why: the wait moved to the report fence

The phase rows, averaged over in-start rows. Phase fields are per-flip EMAs, so these are approximate. The
period in section 8 is the measure. `Fin rest` is Fin - Sub - Fen, which holds
`pgraph_vk_process_pending_reports_internal`.

| run | Draw | Fin | Sub | Fen | Fin rest | Idle (Fr / St) | Tot | GPU (R / X / MxG) |
|---|---|---|---|---|---|---|---|---|
| off1 | 12.7 | 12.0 | 6.4 | 1.0 | ~4.6 | 10.4 (9.8 / 0.6) | 36.5 | 9.4 (9.1 / 0.3 / 0.1) |
| on1 | 11.3 | 11.9 | 0.2 | 1.3 | ~10.4 | 14.1 (12.6 / 1.6) | 38.6 | 10.9 (8.2 / 2.7 / 2.3) |
| on2 | 11.5 | 12.2 | 0.2 | 1.3 | ~10.7 | 13.9 (12.5 / 1.4) | 38.8 | 11.1 (8.3 / 2.8 / 2.5) |
| census 2004607, off | 12.8 | 12.0 | 6.6 | 1.4 | ~4.0 | 10.4 | 36.6 | 9.4 (9.1 / 0.3 / 0.1) |

- **Fin does not move.** The 6.4 ms of synchronous wait inside `Sub` (the SURFACE_DOWN finishes) is gone, and
  the same time reappears in `Fin rest`. That is the #804 wait (reports.c:243-263). When queries are in flight,
  every finish waits on every submitted frame's fence, then `vkGetQueryPoolResults` with WAIT_BIT.
- **NFS has occlusion queries in every frame.** `hakuX-rpbrk` reads `qry120` per 60-frame line in all three
  runs, two query breaks per frame. So the pgraph thread waits for the whole frame's GPU work at the report
  either way. With the switch off, the mid-frame cube-face finishes submitted part of that work early, and the
  report fence found the GPU nearly done. With it on, nothing submits before the end-of-frame finish, and
  `xemu-work` QS goes from 3.1 to 1.2-1.4 submits per frame. The fence then waits for all of it.
  The downloads' wait was GPU execution the frame needs anyway, not the readback. That is the "waits hidden
  behind GPU-bound time" refutation section 5 wrote down.
- **The GPU does about 1.6 ms more per frame on** (R+X 9.4 -> 11.0), mostly in one inter-render-pass gap
  (MxG 0.1 -> 2.4). On Turnip a GMEM pass's binning, other tiles and loads/stores count as non-render
  (draw.c:3722-3730), and the switch changes how the frame is split into passes and command buffers (`Bar`
  939 -> 490, `Tr` 1236 -> 1916 per 60 frames, the latter the copy route's ~11 transitions per frame). So
  this gap is not shown to be the copies themselves. `HAKUX_GPUXFR=1` brackets each non-draw scope, which
  includes `texscan_apply`, and one on run with it would say. That matters only while the pgraph thread
  waits for the GPU, which is the case here.
- **The CPU side did improve.** create_texture dropped from 8.96 to 1.04 ms/frame. Draw is 1.2 ms lower and
  `TexU` (texture uploads) goes 1.0 -> 0 per frame: the cube is no longer re-hashed and re-uploaded. Fin
  rest and Idle absorbed all of it.

## 10. Verdict and recommendation

- **Prediction: R PASS, V PASS, N PASS; P, H, F FAIL, wrong sign.** The switch removes the downloads it was
  built to remove, and makes the NFS race start 2.6 ms per frame slower (21.5 -> 20.3 fps), with more frames
  at 4+ vblanks.
- **Keep it default-off. Not recommended default-on on its own.**
- **What it is for:** lane.reportasync1010 (`HAKUX_REPORT_ASYNC=1`) moves the report write to the render
  thread after the fence. That removes the wait this switch moved to. Its brief step 5 runs both switches on
  vs both off when this switch is on its base. That pair, not this lane's, decides whether HAKUX_TEXSCAN
  goes default-on. Folding this PR as-is (opt-in, inert when off, pixel-checked) is what lets that pair run.

## 11. For the next lane

- **Do not run HAKUX_TEXSCAN=1 alone again** to look for an NFS win. Any title with an occlusion query in the
  frame turns the removed download wait into a report-fence wait. Pair it with the async report.
- **Before blaming the copy for the GPU gap,** take one on run with `HAKUX_GPUXFR=1` (section 9).
- **Forza.** lane.forzasurf1010 measured the `range` caller at 5.77 -> 9.69 ms/flip with surfgpu on. Whether
  those are cube faces is not known. One perflog run there reads it from `[tsc] cls` and `ts[fb]`. If they
  are not cubes, this route refuses them (`fb`), and the census table in section 3 says which shape to build.
- **The route.** `nfs-mw-quickrace` needs a check that it is on the main menu before it steps into Quick
  Race. off2 went one level too deep and ran 12 starts of an alias dialog.
- **texread.py's V leg** checks starts, route, env and build, not the scene. A start window with draws/frame
  far below the others (389 vs ~900-1000) should void the run. That reader is in this lane, but its rules were
  registered before the runs, so it is not edited here.
