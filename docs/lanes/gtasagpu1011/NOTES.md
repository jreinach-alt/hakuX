# gtasagpu1011 -- GTA San Andreas: hard-edged sky polygons, no shadow under CJ

Lane notes. Brief: `/home/justin/hakux-work/briefs/gtasagpu1011.md`. Base: master @ 6d8947bb47.

## 0. The frames, read at full size

The six frames named in the brief, read at 1280x960:

| run | frame | clock | what is there |
|---|---|---|---|
| 3377194 (fastpaths OFF) | f00066 | 10:03 | the whole sky is white, with a flat pale-khaki rectangle over the upper left, its lower edge a straight slope. No shadow under CJ, who is running on a sunlit road |
| 3377194 | f00102 | 13:26 | a black triangle in the sky right of the tree, one edge carrying a thin cyan line |
| 3377243 (fastpaths ON) | f00089 | 12:05 | two parallel pale bands run from the top left of the sky down to the hill. The pavement in front of CJ is a quad of radially streaked texture with straight edges |
| 3377243 | f00107 | 13:47 | a black band, about 30 px wide, runs from the top of the frame down and to the right, from behind the palms to the hill |

CJ has no shadow in any of these frames, and in none of the sunny frames on the contact sheets either.
Neither do the other peds.

**A third symptom, from lane.local's later A/B** (frames every 30 s; read here at full size).
At the A-frame church, 60-90 s after the mark, two runs show the same frame:

- `1-1791733228-lane.local-3377455` f00012 (09:45);
- `1-1791733231-lane.local-3377611` f00010 (08:44).

In both, the sky is blown out yellow-white. The trees, the church roof and the distant buildings
are smeared into streaks, mostly along one axis, as if each pixel were drawn on top of copies
of its neighbours. The near geometry (fence, hedge, CJ) is mostly intact. Two other passes of
the same spot look normal (3377329 f00010, 3377515 f00012). In those, the sky is clean blue
and there is still no shadow under CJ.

This looks like a full-screen post pass over the frame that read the wrong image: a stale
one, one at the wrong scale, or the target it is writing to. It also fits the owner's "sky
going from blue to white" and this lane's 3377194 f00066, where the whole sky is white. So the
working split is two defects:

1. **(a) post pass:** the white or streaked sky. Intermittent.
2. **(b) shadow:** missing in every still.

The hard-edged polygons (bands, wedges) are not assigned to either yet. This is a reading of
four stills, not a finding. The dump decides it.

The bands are long, straight-edged and diagonal, and they end on the ground. A screen-space
sky polygon would not end on the ground. GTA SA projects pole and entity shadows onto the
ground as polygons (CShadows), and the real-time ped shadow is one of them. So one candidate is
that the bands and the missing shadow are the same draws: shadow polygons with wrong vertices
or wrong texture contents. This is a hypothesis to test, not a finding.

## 1. Step 1 predictions (written before queueing)

Each run: `gta-sa` route, 600 s, `--frames-every 5`, ref 6d8947bb47 (master), Nova, one switch
changed from the app default. Read by eye: CJ's shadow in sunny post-mark frames (in-game 07:00-19:00).

| switch | P(shadow back) | why |
|---|---|---|
| `HAKUX_SURFGPU=0` | 0.25 | the ped shadow is render-to-texture; SURFGPU changes how a pending download of a rendered surface reaches a later texture upload (surface.c:532) |
| `HAKUX_GPL=0` | 0.10 | the uber vertex stage serves a pipeline miss only until the specialised pipeline swaps in, but the shadow is missing in every frame of a 600 s run |

Sky bands: too rare per run (about 2 per 72 frames) for one run to decide, so step 1 reads them
only as a side note.

Brief addendum 1 (09:40): a still is 1 displayed frame in about 150. A run with a shadow in its
stills names the subsystem. A run without one is **inconclusive**, not a negative: the shadow
may show for a few frames at a time. The P values above are for "shadow in the stills".

The six fastpaths switches are already ruled out by lane.local's OFF run (3377194).
`HAKUX_PREBUILD` is on by default but only queues pipeline builds; it draws nothing.

Queued at 6d8947bb47: `1-1791735439-lane.gtasagpu1011-3545202` (`HAKUX_SURFGPU=0`) and
`1-1791735439-lane.gtasagpu1011-3545543` (`HAKUX_GPL=0`).

### Step 1 results

Both runs were read on full-frame contact sheets of every post-mark still, plus the named
frames at 1280x960.

| switch | run id | env took | post-mark stills | shadow under CJ | (a) post pass | other |
|---|---|---|---|---|---|---|
| `HAKUX_SURFGPU=0` | `1-1791735439-lane.gtasagpu1011-3545202` | no `[surfgpu] on` line | f00042-f00107 (mark 10:11:10) | no, in all 66 | f00063 (09:46, at the church: sky blown out, streaks); f00088 (12:16: sky white below a thin blue strip, trees fringed yellow and smeared upward) | static shadows (houses, trees) render; other peds have no shadow either |
| `HAKUX_GPL=0` | `1-1791735439-lane.gtasagpu1011-3545543` | `[gpl569] requested=0 mode=0` | f00042-f00112 (mark 10:21:49) | no, in all 71 | f00074 (10:54: whole frame streaked, sky white, see right); f00107 (13:59: everything smeared in rays from the centre of the frame, tinted yellow, sky white); f00044, f00049, f00102, f00111, f00112 (sky blown out, milder) | f00074: a flat cyan quad on the pavement under the truck, with straight edges; cyan patches on the distant buildings |

So neither switch brings the shadow into the stills (inconclusive, per addendum 1). Symptom
(a) is present with either switch off, so neither SURFGPU's download path nor the
uber-pipeline is needed for it.

The smear in 3545543 f00107 is radial: streaks run outward from near the centre of the frame
in all directions, like a zoom blur. One pass of a bloom filter does not do that. A pass
that each frame adds a slightly scaled copy of the **previous** finished frame does, because
the copies compound. That would happen if the post pass's source (meant to be a copy of the
current frame before the effect) is instead the previous frame's output. To be tested in the
dump.

The cyan quad in f00074 is the colour of the sky. It reads as a ground polygon that was not
drawn, so the cleared sky shows through: a "poly surface dropout" in the owner's words.

**Desktop lavapipe: not run.** The GTA San Andreas disc is not under `/mnt/d/hakux-staging`
(searched 5 levels deep for `54540082` and `andreas`). And the desktop harness
(`docs/testing/desktop-runs.md`) runs the pgraph test disc, which needs no input. This route
needs START, twelve A presses and the stick before CJ is on foot, and the desktop path has
no input injection. Building one is out of scope here.

## 2. Frame dump

The live dump (schema 3) recorded each draw's colour surface and texture bindings, and
nothing else. Blend, depth, stencil, colour mask and the depth target were only in the
serialising diag capture, and GTA San Andreas cannot run under that capture. Schema 4
(33ceb415ca, `vk/renderer.c`) adds:

- per draw, raw (decode key: `nv2a_diag_log_draw_call`):
  - `rs`: CONTROL_0..3, BLEND, BLENDCOLOR, SETUPRASTER, SHADERCLIPMODE, ZCLIPMIN/MAX and CSV0_D;
  - `clip`, `aa`, `zf`;
  - `zeta`: the depth target's address, size and format;
- per enabled texture stage: `srf`, the surface at the stage's address if any (size, format,
  swizzle, dirty and pending flags), and `s2t`, whether the stage bound that surface's image
  directly;
- once per shader hash, a `{"t":"shader"}` record: the combiner registers and the VS,
  GS and FS GLSL.

Queued: `1-1791735798-lane.gtasagpu1011-3571105`, at 33ceb415ca, with
`XEMU_FRAME_DUMP=30,after250,cap512`. That is 30 frames from 250 s, about 55 s into gameplay
at an in-game time near 09:00, so sunny.

What to look for (GTA SA's real-time ped shadow, as reverse-engineered for the PC
version; the Xbox port is a hypothesis to check against the dump):

1. CJ's silhouette is drawn into a small render target, about 128x128.
2. The silhouette is blurred and inverted by full-raster quads that sample that target.
3. The result is projected onto ground polygons the CPU clipped, with blend
   ZERO / INV_SRC_COLOR.

If the target arrives in that last texture as zero, the multiply leaves the ground unchanged,
and the shadow is missing with every draw present. The dump separates:

- the surface→texture path: `srf`/`s2t` on the sampling draws;
- a draw sampling its own colour target (feedback; tile memory on Adreno);
- blend, depth or cull state on the projected draw.

### 2a. What dump 3571105 shows

`1-1791735798-lane.gtasagpu1011-3571105`, file `pulled/framedump_1791740003.jsonl`, 30 frames,
PPMs `framedump_1791740003_fNNN.ppm` (640x480). Read with `fdread.py` (this directory). The
display buffers alternate: 0x3d04000 on even frames, 0x3e30000 on odd ones.

**Only the sky changes.** Mean RGB of three regions in each even frame (same buffer):

| frame | sky (180,0)-(480,20) | road (250,400)-(400,470) | wall (0,150)-(60,300) |
|---|---|---|---|
| f00 | 213,203,154 (khaki) | ~60 | ~50 |
| f02 | 237,234,185 | ~60 | ~50 |
| f04 | **130,224,250 (blue)** | ~60 | ~50 |
| f06 | 237 | | |
| f08 | 247,246,223 | | |
| f10 | 251 | | |
| f12 | **128,225,250 (blue)** | | |
| f14 | 191,241,252 | | |
| f16 | 228 | | |
| f18 | 243 | | |
| f20, f22, f24 | khaki | | |
| f26 | 236 | | |
| f28 | 242 | | |

Over all 30 frames the road holds at 57-68, the wall at 42-56 and CJ at 50-73. A post pass
reading a stale whole frame would brighten those too, by the same factor of about 2.4. So
"the post pass read the wrong image" (section 0's defect (a)) is refuted as stated. What
brightens is the part of the sky that was not drawn this frame.

**The mechanism these numbers fit.** Nothing clears the colour buffer. Where the sky draw does
not cover the top of the screen, the pixels keep what the same buffer held two frames earlier.
GTA SA's post pass (radiosity and colour filter) then brightens them again each frame. Between
blue frames the sky goes khaki → 237 → 247 → 251, which fits x_n ≈ 116 + 0.59 · x_(n-2).
The flat khaki polygon with a straight sloped edge (3377194 f00066, dump f00) is that
uncovered region on its first frame: what is left of an earlier frame, seen through the hole
the sky triangle should have filled.

This covers all three of the owner's sky words: the white sky, the hard edges (the hole is
bounded by triangle edges) and "blue to white" (the brightening ramp). **The church symptom
(peer message 2) is most likely the same defect.** Uncovered pixels are post-processed again
every frame while the camera moves, so the old image smears along the direction of motion.
It is radial (3545543 f00107) when the camera moves forward. The cyan quad on the pavement
(3545543 f00074) is the same thing on the ground: a polygon that was not drawn.

**The sky draw.** In every frame it is draw n11:

- shader 12f336cc, `inline_elements`, 30 indices, TRIANGLES (10 triangles);
- no blend, no z test, mask RGBA, no texture;
- the same registers in every frame, good or bad.

Its vertex shader is fixed-function with skinning off: `oPos = position * compositeMat`, a 3D
transform. The geometry is a band of polygons around the camera (GTA SA's
`CClouds::RenderSkyPolys`), so some of its vertices are behind the camera and have w < 0.

The draw is a filled triangle list, so it gets the #223 geometry shader (`glsl/geom.c`,
`append_wedge`, 77bc07d5e2). Given exactly one negative-w vertex, that shader emits the
"external wedge" in place of the triangle. Given none, two or three, it passes the triangle
to the host clipper. Which path a sky triangle takes, and so whether it covers the top of
the screen, depends on the camera angle.

Around n11:

- n12-n14: 65586dbf LINES, 28 indices each, SA/1-SA;
- n15: the sun, additive, t0 0x03459180;
- n16 onward: the world.

The post pass is draws n722-n728 in each frame. Its copy images and draw list are the same
in good frames and bad ones.

**Ruled out:**

- frame skip: off in logcat;
- a difference in the draw list between good and bad frames;
- SURFGPU and GPL (step 1).

**The shadow chain** (frame 4; the same in every frame):

1. n0-n5 draw CJ into 0x3513980 (64x64).
2. n6-n8 blur it into 0x3517a00 (32x32) via 0x34e7480.
3. n9 is 0*S + SC*D with t0 0x034e8500.
4. n10 is a LINE_STRIP border.
5. n687 is the projected shadow: one triangle, blend ZERO*S + (1-SC)*D, zLE, atest GT 0,
   t0 0x03517a00 X8R8G8B8 32x32, on the surface→texture copy path.

Every draw is there, so the shadow is lost in the contents (t0's texels, or v0.a against
the alpha test), not in a missing draw. The dump does not record either.

### 2b. Next measurements (predictions written before queueing)

1. **The same dump with the #223 geometry shader off for smooth filled triangles**
   (`HAKUX_MEASURE_NO_GEOM=1`, a measurement-only switch already in `geom.c`). The ref is
   33ceb415ca, same route, `after250`. The sky triangles then go to the host clipper.
   - Prediction: if the wedge path is what leaves the sky uncovered, all 30 frames show a
     blue sky top, with no khaki and no ramp. P = 0.45.
   - The other reading: the ramp persists. Then the GS is cleared, and the geometry itself
     (stale vertex data, or a position that the host clipper also drops) is next.
   - Dump 3571105 had 2 blue frames in 15 even ones, so 30 blue frames out of 30 is not
     chance.
2. **Schema 5:** each small draw's vertex inputs and the composite matrix, so the sky
   triangles' w and screen positions can be computed offline and set against the
   wedge model.

#### 2b result 1: the geometry shader is cleared

`1-1791741002-lane.gtasagpu1011-54100` (33ceb415ca, `HAKUX_MEASURE_NO_GEOM=1`, logcat
`env: HAKUX_MEASURE_NO_GEOM=1`), dump `framedump_1791741485`, 29 images. The switch reached
the sky draw: n11 (12f336cc) has no geometry shader in this dump, while the shadow-chain
draws still do. **The prediction failed.** The ramp is still there. Sky (180,0)-(480,20) mean
red per frame:

| frames | sky top |
|---|---|
| f001-f002, f007-f009, f021, f029 | 124-126 (blue) |
| f003-f004, f010-f011, f023 | 185-186 |
| f005-f006, f012-f013, f025 | 225 |
| f014-f015 | 241 |
| f016-f020, f022, f024, f026-f028 | 247-252 (white) |

This is the same ramp as 3571105 (each step is one rendered frame; the dump repeats an image
when `img_sync` is -1). CJ is running here (f001, f017), so it holds with a moving camera too.
f017 is a white sky with a hard diagonal edge on the right and ghosted treetops.
**The #223 wedge path is not the cause.** The sky triangles are dropped with the host
clipper too.

### 2c. Vertex RAM rewritten inside one command buffer (found in code, 41be412ae0)

The sky draw has the same registers in every frame, good or bad. CJ stands still in 3571105
and runs in 54100, and good and bad frames interleave either way. So what changes between
frames is the vertex data the draw reads.

How a draw reads vertex RAM:

1. `sync_vertex_ram_buffer` (`vk/draw.c`) copies dirty pages of guest RAM into
   `frame_staging[current_frame].vertex_ram` (`pgraph_vk_update_vertex_ram_buffer`,
   `vk/vertex.c`) at the offset of their VRAM address.
2. `bind_vertex_buffer` binds that staging buffer itself.
3. The GPU reads it when the command buffer runs, which is at the next finish (frame 4 of
   3571105: one submit for the whole frame).

So if the guest rewrites vertex memory that an earlier draw in the same command buffer
reads, and a later draw syncs it, the earlier draw runs with the later draw's vertices.

Upstream xemu guards this. `pgraph_vk_update_vertex_ram_buffer` finishes the command buffer
(`VK_FINISH_REASON_VERTEX_BUFFER_DIRTY`) before re-uploading a page uploaded since the last
finish. hakuX commit 41be412ae0 ("vk: add render command thread with per-frame vertex RAM
buffers") replaced that with "Per-frame buffer: no finish needed, each frame has its own
copy". The per-frame copies keep command buffers apart, not the draws within one. Nothing in
the tree passes `VERTEX_BUFFER_DIRTY` any more.

A guest that reuses one vertex buffer for several draws a frame, and waits only until the
GPU has fetched the previous draw, does exactly this. pgraph fetches on the guest's clock, so
the wait always passes at once. GTA SA draws the sky band and the stored shadows through
RenderWare's immediate-mode path: `CClouds::RenderSkyPolys` and `CShadows::RenderStoredShadows`
both transform into one temporary vertex buffer (`TempBufferVertices`) and draw it with
`RwIm3DRenderIndexedPrimitive`. The dump fits: the sky is n11 (`inline_elements`, 30 indices)
and the shadow is n527-n530 (`inline_elements`, 15-24 indices). Both are small indexed draws
from vertex RAM, near the start of the command buffer, with later immediate-mode draws after
them.

The hypothesis covers both defects with one cause. Whether a frame comes out good depends on
whether a later draw in the same command buffer rewrote the buffer before submit. That
explains the 1-in-7 blue frames.

**Built** (a6ee1c58fe):

- Schema 5 of the dump. Each draw record gets `rot` (its command buffer) and `vr` (each array
  attribute's VRAM byte range). A `vup` record is written for every staging upload that
  changes bytes, with the changed span `clo`-`chi`.
- `HAKUX_VTX_HAZARD=1`, default off. It finishes before an upload that changes bytes an
  earlier draw in the same command buffer reads.
  - It is byte-exact, so a ring of vertices appended draw by draw does not trigger it, as a
    shared page would under upstream's check.
  - The finish is deferred: the next upload goes to the next frame slot's copy, and the
    rotation waits that slot's fence.
  - It logs `vtx_hazard: N finishes` to logcat at most every 10 s.

**Predictions** (written before queueing; both dumps at a6ee1c58fe, `after250`, `vtx64`):

1. **Dump, switch off.**
   - In every imaged frame whose sky top is not blue (mean red > 150), a `vup` with the same
     `rot` as n11 and a larger `n` changes bytes inside n11's `vr`.
   - In the blue frames, none does, or there is a submit between them.
   - P = 0.65.
   - If no such `vup` exists in the bad frames, the hypothesis is refuted for the sky. The
     remaining candidates are then a position the host clipper drops and a torn read of
     guest RAM (#54's race).
2. **Dump, switch on.**
   - All imaged frames have a blue sky top (mean red < 150).
   - logcat shows `vtx_hazard` lines with N > 0.
   - `vup` records with `"hzf":1` appear.
   - P = 0.6. It is lower than prediction 1 because the fix stands down while merged or
     reordered draws are queued, and the dumps show both off for GTA SA.
   - Shadow: these 640x480 dump frames cut CJ off at the knees, so the shadow is judged in the
     step 3 soaks, not here.
3. **Cost.** The `vtx_hazard` rate is the number of extra submits a frame. Below 10 a frame
   it is close to the submits a frame already make (1-6, mean 2.4, over the 29 frame gaps of
   3571105, from the draw records' `submits`). Above 50 it needs option (D): give the
   rewritten range a private copy instead of a submit. P(≤ 10) = 0.5.
