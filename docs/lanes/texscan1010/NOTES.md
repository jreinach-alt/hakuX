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
