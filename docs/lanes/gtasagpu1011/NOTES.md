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

## Attempt 2 (resumed 2026-10-11 11:30 PDT)

**Why attempt 1 did not finish.** It ended on the 300-turn cap at 11:08 PDT with two schema-5
dumps (`1-1791742113-lane.gtasagpu1011-176610`, switch off, and `...-177443`, switch on) queued
and not yet run, and no `waiting:` note. Nothing was left to read them. The lesson for the next
session: write NOTES and a waiting note before queueing the last run of a session, not after.

### 2c scored: the switch-off and switch-on dumps

Both at a6ee1c58fe, `XEMU_FRAME_DUMP=30,after250,cap512,vtx64`, the gta-sa route, 320 s.

- off: `1-1791742113-lane.gtasagpu1011-176610`, `pulled/framedump_1791742961.jsonl`, 29
  images (f005 not pulled). In-game 08:30, CJ running past a house, so the sky is partly behind
  the eave and the tree.
- on: `1-1791742114-lane.gtasagpu1011-177443`, `pulled/framedump_1791743353.jsonl`, 30
  images, logcat `env: HAKUX_VTX_HAZARD=1`. In-game 08:36, CJ running along an alley wall.

The two views differ, so the old sky-top box (180,0)-(480,20) does not read sky in either
(the eave and the wall cover it). The measure used here instead counts pixels in the top 160
rows, HUD box excluded: "white" is r > 200, g > 200 and b <= r + 10 (the ramp's
yellow-white, which no morning sky pixel has); "blue" is b > 200 and b - r > 50. Counts are in
hundreds of pixels, white/blue; `r` marks an `img_sync -1` image. `fdread.py DUMP vhaz 12f336cc`
gives the sky draw n11's state.

| dump | sky draw n11 hit by a later upload in its command buffer | frames with white pixels |
|---|---|---|
| 3571105 (33ceb415ca, schema 4, no switch) | not recorded (schema 4) | 23 of 30 |
| 176610, off | 15 of 30: f2, f5-f8, f12-f16, f18, f24, f26, f27, f29 | f8 (7/4), f15 (8/11), f16 (21/13), f18 (15/12), f26 (7/13), and their `r` repeats f9, f17, f19, f27 |
| 177443, on | 0 of 30 | 0 of 30 (blue 45-403 in every frame) |

**Prediction 1 (off): holds in its first half, not its second.**

- Every frame with white sky pixels is a hit frame, or an `r` repeat of one.
- No clean frame shows white: f0, f4, f10, f20, f22 and f28 are clean and imaged, with blue
  between 52 and 368 and zero white.
- But 7 hit frames show a blue sky (f2, f6, f12, f13, f14, f24, f29). So a hit is necessary for
  the white sky in this dump, not sufficient. That fits a hit that rewrites only part of the
  band: n11 draws 10 triangles all round the camera, and the rewritten bytes can be vertices of
  triangles that are off screen. The dump does not log the rewritten bytes, only their span, so
  this is not shown.

**Prediction 2 (on): holds.**

- Every image has blue sky and none has a white pixel.
- logcat has 22 `vtx_hazard` lines, 2806 finishes by 11:30:26.
- 29 of 30 frames carry a `vup` with `"hzf":1`.

The view differs from the off dump (the alley wall covers most of the sky after f15), so the
image half rests on f0-f15, where 268-403 hundred blue pixels are visible. The run's own
stills agree: 22 sunny post-mark stills (f00041-f00062, 07:52-09:51), all with a blue sky and
no hard-edged polygon in it. Per addendum 1 that is a floor on the defect, not proof it is gone.

**Prediction 3 (cost): holds.** In gameplay the switch finishes 100-370 times per 10 s, about 1
a frame at 25-30 fps, and the dump's `hzf` records say 1 a frame (2 in f17). So the cost is
one extra submit a frame. Option (D), a private copy for the rewritten range, is not needed
for cost.

**The shadow is not this.** In the off dump the hit draws are n10-n15 (the shadow chain's border
strip, the sky, the three LINES draws and the sun) and three others (n326, n382, n619). The
stored-shadow draws (n5xx) are never hit. With the switch on, CJ has no shadow in any of the 22
sunny post-mark stills (f00044 at 08:03, CJ running on the road beside a parked car, read at
full size: the car has a shadow, CJ has none). So the sky and the shadow are two defects. The
shadow is next (2d).

### 2d. The shadow: what the schema-5 dumps show, and the next discriminator

Read from the on dump (177443), frame 4, with `fdread.py DUMP draws 4 0 11` and the
`v`/`cm` words. Frame 0 has the same chain (the projected draw is n554 there).

**The chain.** Every frame starts with it:

| draw | target | what it does |
|---|---|---|
| n0-n4 | 0x3513980, 64x64, fmt 4 (X8R8G8B8_Z8R8G8B8), swizzled, no zeta | CJ's meshes (shader 60cf0c75), blend SA*S + (1-SA)*D, alpha test GT 0 |
| n5 | 0x3513980 | a quad, blend (1-DC)*S + 0*D: inverts the target |
| n6 | 0x3517a00, 32x32 | samples 0x3513980 (SZ_X8R8G8B8, copy path: `s2t:0`, the surface `dirty`) |
| n7 | 0x34e7480, 32x32 | samples 0x3517a00 |
| n8 | 0x3517a00 | samples 0x34e7480 |
| n9 | 0x3517a00 | blend 0*S + SC*D with the static texture 0x034e8500: a falloff mask |
| n10 | 0x3517a00 | an 8-index LINE_STRIP: the border, so the clamp reads black |

**The projected shadow, n522.**

- Shader 7f12c419cf0057eb, 9 indices, TRIANGLES.
- Blend 0*S + (1-SC)*D: it darkens the frame by the texture.
- Depth test on, LEQUAL, no depth write. Alpha test GT 0.
- t0 is 0x03517a00, SZ_X8R8G8B8 32x32, clamp, through the copy path (`s2t:0`).
- Diffuse 0x8f8f8f8f.

All of it is drawn, every frame, in both dumps. The car shadows are stencil volumes and do show.

**Ruled out by reading:**

- **The vertex RAM hazard.** No n5xx draw is ever hit (2c).
- **The pad-alpha override.** The Nova has dualSrcBlend (logcat), so `surface_sampled_pad_alpha`
  (vk/texture.c) returns IDENTITY. SZ_X8R8G8B8's own map then gives alpha ONE, and the alpha
  test cannot be what removes the shadow on the texture's account.
- **A VRAM read of the texture.** The stage takes `copy_surface_to_texture`, a GPU copy of the
  surface image, recorded in order in the main command buffer
  (`pgraph_vk_begin_nondraw_commands` returns `r->command_buffer` since OPT_SURF_TO_TEX_INLINE).
- **`draw_time` bookkeeping.** draw.c sets the target's `draw_time` on every path (the reorder
  path, `post_draw` and `mark_clear_drawn`), so the copy is not skipped as up to date.
- **The geometry.** Recomputed from n522's `v` and `cm` words, the quad lands under CJ. The
  texture centre maps to screen (373,510), below the 640x480 frame. So part of the shadow
  should show near CJ's feet (y 390-430 in `on_f004.png`) and part falls off screen. The centre
  triangle has two vertices with w < 0. The geometry shader's wedge path handles exactly one
  negative w, so that triangle goes to the host clipper.

**Still open.** The dumps cannot tell these apart, because the shadow's texture is never seen:

1. **The texture is empty.** The silhouette is not in 0x3517a00 when n522 samples it. Either
   n0-n4 draw nothing into 0x3513980, or a step from n5 to n10 loses it.
2. **The texture is right, and n522's pixels are lost.** The depth test against the ground
   fails, or the host clipper drops the two-negative-w triangle and the other triangles fall
   off screen.
3. **A timing hazard.** The copy reads the surface before the chain's draws land. Nothing in
   the source shows one. It is included because a finish between draws would hide it.

**Schema 6 (`rtt` token) decides between them.**

- **What it does.** A draw whose colour target is at most 64x64, or that samples a colour
  surface that small, finishes the command buffer after its record. It then reads back, as the
  GPU left them after this draw:
  - its colour target (`"k":"color"`);
  - each such stage's surface image (`"srf"`);
  - the texture copy the stage actually sampled (`"tex"`).
  
  Each is written raw, as `framedump_<id>_fFFF_nNNNN_<k><s>.bin`, and listed in the draw
  record's `"rb"`. `fdread.py DUMP rb F OUTDIR` prints each image's lit-texel count and writes
  PNGs and a sheet per frame.
- **What it does not see:** depth. If n522's own pixels are the question (outcome A below),
  the next instrument is a per-draw occlusion query or a depth readback.

**Predictions** (written before queueing). The run: the gta-sa route, 320 s,
`XEMU_FRAME_DUMP=30,after250,cap512,vtx64,rtt`, with `HAKUX_VTX_HAZARD=1` so the sky is clean.

A texture holds "a silhouette" when 2% to 80% of its texels differ from its most common texel
by more than 32 in any channel. A flat image does not, whatever its colour.

- **A. The texture is right (P = 0.5).** The `tex0` readback at n522 holds a silhouette in most
  frames that have one. Hypothesis 2 stands, and the defect is in n522's raster.
- **B. The copy is wrong (P = 0.15).** The `srf` readback at n522 holds a silhouette and the
  `tex` readback does not. The copy or the binding loses it (`copy_surface_to_texture`, or a
  stale node chosen for the stage).
- **C. CJ is never drawn into the target (P = 0.25).** The `color` readback after n4 has no
  silhouette. The cause is in n0-n4's state.
- **D. A chain step loses it (P = 0.1).** There is a silhouette after n4 and none at n10. The
  first readback without one names the step.
- **Separately, timing (P = 0.15).** The finishes `rtt` adds put CJ's shadow into the dump's
  display images, which no earlier dump showed (feet visible in f0-f15 of 177443). That points
  at hypothesis 3, whatever A-D say.

**Schema 7 (`rtt`, extended), built while 651566 waited.** Under outcome A, schema 6 still does
not show whether n522 writes a pixel, or the depth it is tested against. Schema 7 adds both at
the consumer draw itself, so a single run answers A's next question instead of a second
build-and-queue cycle.

- **What it does.** A "consumer" is a draw whose colour target is not small and which samples a
  colour surface of 64x64 or less. In 177443 these are exactly the projected shadows: n522 in f4,
  and n615 and n616 in f10, which has two. The 1024x512 effect draws (n552-n557) are not small.
  For the first `FDUMP_CONS_PER_FRAME` (2) consumers a frame, and `FDUMP_CONS_MAX` (24) a dump,
  `pgraph_vk_fdump_pre_draw` (called from `flush_draw_one_pass` in vk/draw.c, before anything of
  the draw is recorded) finishes and reads:
  - `"pre"`, the full colour target;
  - `"zpre"`, the depth aspect of the zeta surface. D24S8 (vkfmt 129) is in the low 24 bits of
    each 4 bytes, D32S8 (130) is a float, and D16 (124) is 2 bytes.
  The draw's own record then reads `"post"`, the colour target after the draw.
- **Cost.** At the Nova's `surface_scale` 1 (177443's session record), that is 3 x 1.2 MB a
  consumer, 88 MB at the cap, inside `cap512`.
- **Reading it.** `fdread.py DUMP cons [OUTDIR [X0 Y0 X1 Y1]]` prints, per consumer, how many
  pixels pre and post differ in (any channel by more than 2), their box, their mean change, and
  zpre's range over the image and over a given box. With OUTDIR it writes pre, post, diff and
  zpre PNGs. It was tested on a synthetic dump (a known 11x5 darkened box and a D24 ramp); the
  box, the mean and the depth values come back exactly.

**Predictions for the schema-7 run**, written before queueing. The run is the same route, 320 s,
`XEMU_FRAME_DUMP=30,after250,cap512,vtx64,rtt`, `HAKUX_VTX_HAZARD=1`. They are conditional on A
(the texture is right). Under C or D the consumer readbacks show nothing written, and the run's
schema-6 readbacks are a second sample of 651566's chain.

- **A1. Depth rejects the shadow (P = 0.35 given A).** n522 changes no pixel. zpre over the
  shadow's screen box (around (373,430) and down, from the 2d geometry) is below the depth the
  projected quad computes there, so LEQUAL fails. The next step is the depth n522 computes:
  `calc_triz` in the fragment shader against the FF epilogue's `z/clipRange.y`.
- **A2. The raster is lost before depth (P = 0.35 given A).** n522 changes no pixel, and zpre
  over the box is at or beyond the quad's depth (LEQUAL would pass). The host clipper or the
  two-negative-w triangle drops the coverage. The next step is the clipper path in vk/geom.c
  for a triangle with two vertices behind the eye.
- **A3. The shadow is drawn, and a later draw covers it (P = 0.2 given A).** n522 darkens a box
  near CJ's feet (mean change negative), and the frame's display image has no shadow. The next
  step is to find the first later draw that writes over the box.
- **A4. Something else (P = 0.1).** For example, n522 changes pixels outside the expected box.

#### 2d result: 651566 (schema 6) -- the texture is right (outcome A)

`1-1791744746-lane.gtasagpu1011-651566`, build 8e40300c6c (apk d94a1d8f54fa), 30 dumped frames.
Read with `fdread.py DUMP rb 4 OUT` and by eye on the sheet.

| step | readback | what it holds |
|---|---|---|
| n0-n4 | `color` 0x3513980 64x64 | CJ's meshes, dark, on white (lit 4000 -> 3716 of 4096 texels as they are added) |
| n5 | `color` | inverted: a bright silhouette on black, 500 of 4096 texels |
| n6-n8 | `tex`, `srf`, `color` | the blur passes; `tex` equals `srf` at every step |
| n9-n10 | `color` 0x3517a00 32x32 | the masked silhouette: 144 of 1024 texels, peak 94-109 of 255 |
| n590 (the projection in f4) | `tex0`, `srf0` | the same 144-texel silhouette |

All 30 frames have the same chain and one projection draw (shader 7f12c419, 24 indices this
run). So **predictions B, C and D are refuted, and A holds**: the projection samples the right
texture, and the shadow is lost in its raster, its depth test, or a later write.

**Where the shadow should land.** `fdread.py DUMP cover F N` works out the projection's coverage
from its `v` and `cm` words. It takes a pixel as covered when the ray through it meets the
triangle at w > 0. Two-negative-w triangles therefore come out right, as a host clipper would cut
them.
- **651566:** every frame's projection covers 45k-118k pixels, and 333-1423 of them sample a
  texel above 8. In f8, f12 and f29 that region is at y 336-380, on the wall top and the hedge
  beside CJ's waist. There the hedge or CJ is in front of it, so these frames cannot show a
  missing shadow by eye. Inside the region the display image is darker than beside it on the same
  quad (f6-f29: 26 vs 48, 13 vs 23, 13 vs 22 mean luminance). The surfaces differ, so that is
  not evidence either way.
- **177443 f4 (the schema-5 run):** the texture's [0,1] square lands on open dirt from CJ's feet
  to the bottom edge (x 198-519, y 399-479). The silhouette's body (u 0.5, v 0.25 in either
  orientation) maps to (343,448). `on_f004.png` shows plain dirt there. That frame is the
  clearest case of the shadow's pixels being lost.

**What is left inside A** is what the schema-7 run separates: A1 depth, A2 raster, A3 a later
write.

## Attempt 3 (resumed 2026-10-11 ~13:00 PDT)

**Why attempt 2 did not finish.** It ended on the turn cap (301 turns) at 11:30 PDT, right
after queueing the schema-7 run `1-1791745550-lane.gtasagpu1011-818197`, again with no
`waiting:` note: the lesson written at the top of attempt 2 was not applied. That run came back
void: hakuX lost the foreground to `com.android.settings` for 90 s or more (12:40-12:41 PDT), so
the route's input went to Settings. hostops re-queued it unchanged as
`1-1791748627-lane.gtasagpu1011-844241` (ref 50a389ef2b). 818197 is not scored or used anywhere
in these notes. (Superseded at 14:04 PDT: lane.local's addendum 5 says neither run is void, the
"void" message was wrong, and 818197's dump is valid data. It is scored in 2e.)

This session writes a `waiting:` note before it queues anything, and keeps the turn count low
while it waits.

### 2d result: 844241 (schema 7) -- the shadow is off screen in every dumped frame; A1-A4 undecided

`1-1791748627-lane.gtasagpu1011-844241`, build 50a389ef2b, 30 dumped frames, 2 consumers a frame
(60 draws, all shader 7f12c419, all with `pre`, `zpre` and `post`).

**What the projection draws are.** They are not a quad. Each one draws whole ground collision
triangles, with texture coordinates far outside [0,1]. Only the [0,1] square of UV space can show
shadow; everywhere else the clamp reads the black border that n10 draws, and `(1-SC)*D` leaves
the frame as it was. So "the draw changed no pixel" means something only for the pixels inside
the square.

**Where the square was.** For each consumer, the affine map from UV to world XY was solved from
its flat triangle (z spread under 0.05), and a 41x41 grid over the square was projected with the
draw's `cm` words. In all 60 consumers, **0 of 1681** grid points land in front of the eye and
inside 640x480: the square's centre is next to the camera, and half of it is behind the eye. The
stills at the dump's time (f00049-f00050) show why: CJ is in a dark spot with his feet out of
frame. The consumers' zero changed pixels are what a working renderer would also show. **This
run cannot decide A1-A4**, and is not evidence for any of them.

**Why the dump missed.** Every `after250` dump fires 42-45 s after the route's `mark`, and the
route is random-walking by then (`repeat forever`), so where CJ stands is chance. Six runs'
route stamps give arm-to-`cut1` 140-142 s, `cut2` about 163 s, `cut3` about 186 s, `moved` about
200 s and `mark` 205.1-207.9 s. From `cut1` to `cut3` CJ stands still in the Jefferson alley
with the camera behind him and his feet in frame, the same picture in the four runs checked (game
clock 06:44-07:35).

**The defect is in a dump already.** In 176610 (schema 5, no `pre`/`zpre`/`post`) the square is on
screen in f0-f10 (1312-1353 of 1681 points) and wholly in frame in f14-f18 (f14 n602: box
50,305-590,443), round CJ's legs on sunlit grass, and the frame's display image has no shadow
there. So the next run only has to put a schema-7 dump on such a frame.

**Alpha, rechecked.** `tex0` and `srf0` hold alpha 0 (X8R8G8B8's pad byte), with 214 texels above
8 in RGB. On the Nova (`vk dualSrcBlend: enabled (maxFragmentDualSrcAttachments=1, #59)` in
logcat), `surface_sampled_pad_alpha` returns IDENTITY, the copy path's view keeps
SZ_X8R8G8B8's {ID, ID, ID, ONE} swizzle (vk/constants.h:225), and the sampled alpha is 1. With
diffuse alpha 0x8c, `alpha GT 0` passes. The alpha test is not the cause.

**Next run: the same request, dump at `after160`.** That lands the dump about 20 s after `cut1`
and 26 s before `cut3`, with CJ standing in the alley. Everything else is 844241's request
(ref 50a389ef2b, 320 s, frames every 5, `HAKUX_VTX_HAZARD=1`, `--pull 'framedump_*'`). Queued as
`1-1791752181-lane.gtasagpu1011-2027680` at 13:58 PDT, behind about 3 h of Nova work.

**Predictions** (written before queueing). A consumer *qualifies* when the square scan puts at
least 400 of 1681 points on screen and `fdread.py DUMP cover` finds at least 200 covered pixels
that sample a texel above 8 ("lit"). The readings are over the lit pixels of qualifying
consumers, pooled.

- **Q. No consumer qualifies (P = 0.15).** The alley picture differs, or the game does not draw
  the projection before `mark`. The run decides nothing; the next run uses 176610's timing with
  `after250` and accepts the chance.
- Given at least one qualifies:
  - **A1. Depth rejects it (P = 0.35).** Under 10% of lit pixels pass LEQUAL against `zpre`
    (cover's `draw z - zpre` median above 0), and pre/post change under 5% of them.
  - **A2. The raster is lost before depth (P = 0.35).** At least 50% of lit pixels pass LEQUAL,
    and pre/post change under 5% of the passing ones. This includes the fragment shader's own
    depth disagreeing with cover's (cover models ideal rasterization; the shader rebuilds depth
    from `vtxPos0..2` and discards outside `clipRange`), so the next step is to run that shader
    arithmetic offline on the dumped vertices.
  - **A3. Drawn, then covered (P = 0.2).** At least 50% of the lit, passing pixels change in
    pre/post (darker), and the frame's display image at those pixels does not show the darkening.
  - **A4. Something else (P = 0.1).** A reading between these, or changes outside the coverage.

**Read after queueing: 844241's depth over the whole coverage.** The depth test does not depend
on the texture, so 844241's `zpre` says where the projection passes LEQUAL even though its lit
square was off screen. `fdread.py DUMP cover` on all 60 consumers:

| frames | covered px | pass LEQUAL | draw z - zpre, median |
|---|---|---|---|
| f0-f2 | 12k-21k | 4-44% | +0.14 to +0.20 (something near the camera in front) |
| f3-f5 | 10k-21k | 0-24% | +0.24 to +0.45 |
| f6-f10 | 4.5k-17k | 80-94% | -0.0038 to -0.0050 |
| f11 | 1151 | 42% | +0.020 |
| f12-f29 | 0 | - | - |

In f6-f10 the projection lies about 0.005 (normalised) in front of the ground under it, and
passes the depth test over most of its coverage. Its covering triangles there have two
negative-w vertices (the host clipper) and one (the geometry shader's wedge). So where nothing
stands in front, the projection is not behind the ground by construction. That makes A1 less
likely than the 0.35 written above; the predictions stand as written, and the run scores them.

### 2e result: 818197 (schema 7) -- the shadow is drawn, passes depth, and reaches the display

`1-1791745550-lane.gtasagpu1011-818197`, build 50a389ef2b, `HAKUX_VTX_HAZARD=1`, 30 dumped
frames, one consumer a frame, `pre`/`zpre`/`post` on the first 24 (FDUMP_CONS_MAX). Addendum 5
reinstated it after the predictions above were written for 2027680, and its frames are a
different case from the one they target: CJ running down the road beside a pickup truck (game
clock 08:33-08:35), not standing in the alley. They are scored here as written, then read for
what they show.

**Every consumer qualifies.** The square is on screen in all 30 (`sqscan.py`), and the 24 with
readbacks have 5.5k-11.6k lit covered pixels each.

| frames | lit px | lit and passing LEQUAL (texel-weighted) | changed px (all darker, all inside the coverage) | changed / lit passing |
|---|---|---|---|---|
| f0-f2 | 9.0k-10.4k | 15-32% | 1250-2599 | 78-82% |
| f3-f13 | 9.7k-11.6k | 12-58% | 1106-4819 | 69-89% |
| f14 | 9.9k | 41% | 3118 | 75% |
| f15-f23 | 5.5k-10.6k | 84-100% | 4448-8183 | 77-84% |

(Changed pixels are any channel moved by more than 2; the rest of the lit, passing pixels sample
texels too dim to move an 8-bit channel.)

**Where it fails depth, something stands in front.** Of the lit pixels that fail LEQUAL, at most
7 a frame are within 1024 units (of 2^24) behind the depth under them, and at most 140 are
1024-16384 units behind. All the others (276-9996 a frame where the truck is in shot) are more than
16384 units behind. That is an occluder, not a precision band. `litfail.py`'s per-pixel
map puts them under the pickup truck's body in f0-f14 (f6 checked by eye), and on CJ's foot in
f16.
Where the road is open, the shadow passes.

**The fragment shader agrees with the ideal raster.** `fsz.py` runs the projection's VS and FS
arithmetic in float32 (per-vertex RTZ `z/w`, the 1/16 screen rounding, the kahan barycentrics and
the compensated depth rebuild) over f0, f6, f16, f19 and f22. It finds:

- 0 `clipRange` discards in 520k covered pixels;
- FS depth within 972 units of the ideal depth;
- LEQUAL-passing sets that agree with the ideal raster's to within 9 pixels a frame.

A2's sub-mechanism is not present in this run.

**The darkening reaches the display image.** The frame image is the surface at `pcrtc.start` when
the frame ends. Paired against each consumer's `post` (whole-frame mean absolute error), it is
usually the previous frame's render (double buffering), and sometimes the frame's own. For each
image and its matching render, the shadow mask is the render's pre/post change. The ratio of
mean luminance in the mask to a ring 4-12 px around it is computed for `pre`, `post` and the image
(`dispcmp.py`). An image at the `post` ratio carries the whole shadow; one at the `pre` ratio
carries none.

| image | render | share of the shadow in the image |
|---|---|---|
| f1, f2, f4-f13 | f0-f12 (one behind) | 0.99-1.43 |
| f14, f15 | f14 | 0.52 |
| f16 | f16 | 0.65 |
| f18-f24 | f18-f23 | 0.98-1.01 |
| f0 | none dumped (its render is f-1) | - |
| f3, f17 | no image (`img_sync` -2) | - |

19 of the 22 paired images carry the whole shadow, and the other three carry half or more.
In f16 (pre, post and the image side by side), the image has CJ and the camera about 10 px from
where `post` has them, so the mask is offset rather than missing. f14 was not examined. None of
the 22 paired images carries the pre-draw picture.

**Score as written** (pooled over the 24 qualifying consumers, as the rule says): 231,059 lit
pixels, 111,918 passing LEQUAL (48.4%), 89,282 of those changed (79.8%).

- Q fails: all 24 qualify.
- A1 fails: 48.4% pass, not under 10%.
- A2 fails both clauses: under 50% pass, and 79.8% of the passing pixels change, not under 5%.
- A3 fails its display clause: the image carries the darkening.

That leaves **A4**, by the letter. What it means is that **there is no defect in this run's 24 frames**. The
projection is drawn, passes depth wherever nothing stands in front, darkens the road, and that
darkening is what the display shows.

**But the shadow is faint, by the numbers the game feeds it.** The strongest darkening in any
frame is post/pre 0.76-0.79, and the median is 0.85-0.89. The chain explains that end to end
(651566 f4, re-read):

| draw | what it does | peak value after it |
|---|---|---|
| n0-n4 | CJ into the 64x64 at 0x3513980 (white clear, CJ dark) | 255 background |
| n5 | invert, `(1-DC)*S` | 253 (CJ) |
| n6 | resample 64 to 32 into 0x3517a00 | 253 |
| n7, n8 | blur passes through 0x34e7480 | 247 |
| n9 | quad, shader faa9d5fc (`tex0 * diffuse`), blend `0*S + SC*D`, samples a 32x32 X8R8G8B8 texture at 0x034e8500 that is not a render surface | 108 |
| n10 | the black border LINE_STRIP | 108 |

n9's per-row factor (n9 / n8 where n8 is lit) falls linearly from 0.48 at row 3 to 0.28 at row
29, about 0.0078 a row. That reads as a gradient the game multiplies the shadow by, fading it
along its length. The texture has no render surface in the dump, so it was made before the dump
window, and the per-frame chain only samples it. The projection then multiplies by its diffuse,
0x8c-0x8f:
1 - (108/255)(0x8e/255) = 0.76, the darkest pixel measured. Each link checks against its
neighbour, so nothing in the per-frame chain is dimming the shadow beyond what its inputs say.
The dump cannot say whether the gradient texture's values (about 129 down to 69, if n9's
diffuse is white) match what the Xbox would hold. The texture predates every dump window, and
n9's vertex colours are not recorded (n9 is `inline_array`).

**The game does not dim CJ's shadow in the alley.** The projection's diffuse is 0x8c-0x8d in
176610 f0-f29, including the alley frames f14-f18 where the display showed no shadow, and
0x8d-0x8f in 818197 and in 844241's CJ consumer. 844241's second consumer samples another
shadow texture (0x34e6400; by its address, another ped's). Its vertex colour fades
0x8e -> 0x28 over the 30 frames, a fade the game asks for, and it is not CJ.

Scripts, in this directory, each reading a dump through `fdread.py`: `sqscan.py` (the square's
on-screen points), `litfail.py` (lit pixels failing LEQUAL, by depth deficit), `fsz.py` (the
float32 VS/FS depth rebuild) and `dispcmp.py` (shadow share in the display image).

**What this leaves.** In the road case, the renderer does what the draws ask. Two readings remain
for "the shadow dropping out":

1. a case this run does not contain, such as CJ standing in the alley (176610 f14-f18, and
   2027680's target);
2. a shadow faint enough (13-22% darker at best) that it vanishes into darker or busier ground.
   That would be the gradient's or the intensity's absolute value, which no dump here can check
   against hardware.

2027680 separates them. If its alley consumers pass and change their lit pixels like 818197's,
reading 2 stands, and the question becomes the gradient texture made at start.

### 2f: the gradient n9 multiplies by, and how it was made (schema 8)

**n9's multiplier, re-read on 651566.** Over every texel where n8 (the blurred silhouette) is above
40, 5269 texels in 30 frames, n9's output is exactly `round(n8 * (129 - 2y) / 255)`, where y is
the row. There are zero mismatches, and the multiplier does not depend on the column. The
alternative, texels `255 - 4y` with diffuse 0x81, misses 1227 of them by one. So the factor
n9 applies is 129/255 at row 0, falling by 2/255 a row. That is tex0 times diffuse, and the
combiner has no scale, so it is either texels `129 - 2y` with a white diffuse or another product
with the same value. Either way the per-frame chain does what its inputs say. The open question
is whether the 32x32 texture at 0x034e8500 holds on the Nova what it would hold on an Xbox.

**Why no dump so far can say.** The texture has no render surface in any dump, so it was made
before every dump window (at the title's start, by the look of it: it is the same in every
frame of four runs). If the game makes it by drawing into it, those draws ran on the emulator,
and a wrong draw there would halve every shadow for the whole session and leave the per-frame
chain looking faithful, which is what is measured.

**Schema 8** (this commit) adds three things to `XEMU_FRAME_DUMP`:

- with `rtt`, a draw into a small target also reads back the texture image of each stage that
  has no surface (n9's gradient, `"k":"tex"`);
- with `vtxNN`, an inline_array draw logs its raw vertex words and layout (`"ia"`), so n9's
  diffuse and any line draw's colours are on record;
- `watchNN`, armed at startup, logs only draws into small targets, from the first flip, until NN
  are logged. That covers the title's start, where the gradient is made, and the first frames of
  the shadow chain.

`gradwatch.py DUMP [ADDR]` prints each logged draw, its decoded vertices and its readbacks as
per-row channel means.

**The run.** gta-sa route, 320 s, `XEMU_FRAME_DUMP=watch600,cap512,vtx64,rtt`,
`HAKUX_VTX_HAZARD=1`, `--pull 'framedump_*'`. About 7 min of device time.

**Predictions** (written before queueing):

- **G0. No logged draw targets 0x034e8500 before the first draw that samples it (P = 0.35).** The
  game writes the gradient from the CPU, or makes it before the first flip. Then the texels are
  the game's own. n9's `"tex"` readback and `"ia"` diffuse say which product gives 129 - 2y, and
  the gradient is ruled out as a defect.
- **G1. Draws into a 32x32 target at 0x034e8500 make it, and the readback after the last one
  matches their vertex colours row by row, within 2 (P = 0.45).** The emulator renders the
  gradient as asked; the gradient is ruled out.
- **G2. Draws make it, and some row of the readback differs from the colour drawn on that row by
  more than 2 (P = 0.20).** For example, half the value, a row off, or a row never written. That
  is a renderer defect, and it would dim every ped shadow. Its draw state names the code path.

In every case, n9's own `"tex"` readback must show the same rows as the multiplier above (129 - 2y
if the diffuse is white). If it does not, the readback or the fit is wrong, and the run decides
nothing until that is explained.
