gtasagpu1011: GTA San Andreas, hard-edged sky polygons and no shadow under CJ (#433, 0.5)
State: draft

Lane: gtasagpu1011      Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 6d8947bb47
Files: docs/lanes/gtasagpu1011/NOTES.md, docs/lanes/gtasagpu1011/PR.md, docs/lanes/gtasagpu1011/WAITING, docs/lanes/gtasagpu1011/dispcmp.py, docs/lanes/gtasagpu1011/fdread.py, docs/lanes/gtasagpu1011/fsz.py, docs/lanes/gtasagpu1011/litfail.py, docs/lanes/gtasagpu1011/sqscan.py, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/vertex.c
Prediction: none: switch screens and frame dumps, read by hand; each run's prediction is written in NOTES.md (sections 1, 2b, 2c, 2d) before it was queued
Needs device: yes (Nova)    Needs NDK: yes

Work in progress. The sky defect is found and fixed behind `HAKUX_VTX_HAZARD=1`, which is off by default. The shadow is still under investigation.

## Step 1: switch discriminators

These are `gta-sa` soaks, 600 s, frames every 5 s, at 6d8947bb47.

| switch | run | CJ's shadow in sunny post-mark stills |
|---|---|---|
| `HAKUX_SURFGPU=0` | `1-1791735439-lane.gtasagpu1011-3545202` | no, 0 of 66 (inconclusive per addendum 1) |
| `HAKUX_GPL=0` | `1-1791735439-lane.gtasagpu1011-3545543` | no, 0 of 71 (inconclusive) |
| fastpaths six OFF (lane.local) | `1-1791733219-lane.local-3377194` | no (inconclusive) |

No switch brought the shadow back. Step 2 decides.

## Step 2: findings

### Sky: vertex RAM is rewritten inside one command buffer

Commit 41be412ae0 replaced upstream's `VK_FINISH_REASON_VERTEX_BUFFER_DIRTY` finish with per-frame vertex RAM copies. Those copies separate command buffers. They do not separate draws within one command buffer.

GTA SA's sky band (`CClouds::RenderSkyPolys`, draw n11, 30 inline indices) is drawn through RenderWare's one immediate-mode temp buffer. Later draws in the same command buffer re-upload those bytes before submit, so the sky draw runs with their vertices.

The fix is `HAKUX_VTX_HAZARD=1` (a6ee1c58fe, `vk/vertex.c`). It finishes before any upload that changes bytes an earlier draw in the same command buffer reads. The check is byte-exact and the finish is deferred.

| dump (schema 5, gta-sa, `after250`) | n11 hit by a later upload in its command buffer | frames with white sky pixels |
|---|---|---|
| `1-1791742113-lane.gtasagpu1011-176610`, switch off | 15 of 30 | 5 frames (plus their repeats), each a hit frame |
| `1-1791742114-lane.gtasagpu1011-177443`, `HAKUX_VTX_HAZARD=1` | 0 of 30 | 0 of 30 |

- **Cost (measured):** 100-370 finishes per 10 s in gameplay, about 1 extra submit a frame.
- **Stills (177443):** 22 sunny post-mark stills, f00041-f00062, all with a blue sky. Per addendum 1, that is a floor, not proof.

### Shadow: every draw is present; the output never lands

These are frame 4 of dump 177443 (NOTES 2d).

- **n0-n4:** draw CJ into a 64x64 render target at 0x3513980.
- **n5:** inverts it.
- **n6-n10:** blur it into 0x3517a00 (32x32) through 0x34e7480, then add the border strip.
- **n522:** projects 0x3517a00 onto the ground. Blend is 0*S + (1-SC)*D, depth LEQUAL, no z write, alpha test GT 0.

Ruled out by reading the dump and the code:

- the vertex RAM hazard (no n5xx is hit);
- pad alpha (dualSrcBlend gives alpha ONE);
- a VRAM read path;
- `draw_time` bookkeeping;
- the projection geometry. The UV centre maps on screen at (373,510), but the centre triangle has two negative-w vertices, so it goes to the host clipper.

Still open after 651566 (schema 6, below), which showed the texture is right:

1. the projection's pixels fail the depth test;
2. its raster is lost before depth (the clipper, or the fragment shader's depth rebuild and `clipRange` discard);
3. it is drawn, and a later draw covers it.

The projection draws whole ground collision triangles with UVs far outside [0,1]. Only the UV [0,1] square shows shadow, because the clamp border is black. In 844241 that square was off screen in all 60 dumped consumers, so that run decides nothing. In 176610 it is fully in frame round CJ's legs (f14-f18), and the display image shows no shadow there.

**818197 (schema 7, CJ running down the road): no defect in 24 frames** (NOTES 2e).

| reading | pooled over 24 consumers |
|---|---|
| lit pixels (UV square, texel above 8) | 231,059 |
| passing LEQUAL against `zpre` | 111,918 (48.4%) |
| failing ones within 1024 units of the depth under them | at most 7 a frame; the rest sit behind the pickup truck or CJ's foot |
| passing ones the draw changed (all darker) | 89,282 (79.8%) |
| fragment shader's depth rebuild (float32, offline) against the ideal raster | 0 `clipRange` discards, within 972 units, LEQUAL sets equal to 9 px |
| paired display images carrying the darkening | 19 of 22 wholly, 3 at half or more |

The shadow is faint by the numbers it is given. The blurred silhouette peaks at 247. n9 then multiplies it by a 32x32 gradient texture, which falls from 0.48 to 0.28 down the rows, leaving a peak of 108. The projection's diffuse is 0x8c-0x8f. The darkest result is 1 - (108/255)(0x8e/255) = 0.76 of the ground's colour, which is what is measured. The game does not lower that diffuse in the alley (176610 f14-f18: 0x8c-0x8d).

That leaves two readings:

1. The alley case fails in a way the road case does not. `2027680` dumps it.
2. A shadow at most 22% darker vanishes on darker ground. The gradient texture was made before any dump window, so its values cannot be checked against hardware here.

**Schema 6 (8e40300c6c)** adds an `rtt` token to `XEMU_FRAME_DUMP`. For each draw that binds or samples a colour target of 64x64 or smaller, it reads back:

- the target itself;
- the surface each stage samples;
- the texture copy each stage samples.

`fdread.py DUMP rb F OUTDIR` turns the readbacks into PNG sheets. Predictions A-D and the timing case are in NOTES 2d.

**Schema 7 (50a389ef2b)** extends `rtt` to the draw that projects the shadow. Before that draw is recorded, it reads the full colour target (`pre`) and its depth (`zpre`). After the draw, it reads the colour target again (`post`). `fdread.py DUMP cons` reports how many pixels the draw changed, where they are, and the depth under them. Predictions A1-A4 are in NOTES 2d.

## Runs

| run | build | what | state |
|---|---|---|---|
| `1-1791735798-lane.gtasagpu1011-3571105` | 33ceb415ca | schema 4 dump | scored (NOTES 2a) |
| `1-1791741002-lane.gtasagpu1011-54100` | a6ee1c58fe | `HAKUX_MEASURE_NO_GEOM=1` dump | scored: the GS wedge path is refuted (2b) |
| `1-1791742113-lane.gtasagpu1011-176610` | a6ee1c58fe | schema 5 dump, switch off | scored (2c) |
| `1-1791742114-lane.gtasagpu1011-177443` | a6ee1c58fe | schema 5 dump, `HAKUX_VTX_HAZARD=1` | scored (2c) |
| `1-1791744746-lane.gtasagpu1011-651566` | 8e40300c6c | schema 6 `rtt` dump, `HAKUX_VTX_HAZARD=1`, 320 s | scored: the shadow texture is right (outcome A, NOTES 2d) |
| `1-1791748627-lane.gtasagpu1011-844241` | 50a389ef2b | schema 7 `rtt` dump, `HAKUX_VTX_HAZARD=1`, 320 s | scored: the shadow's UV square is off screen in all 60 consumers; A1-A4 undecided (NOTES 2d) |
| `1-1791745550-lane.gtasagpu1011-818197` | 50a389ef2b | schema 7 `rtt` dump, `HAKUX_VTX_HAZARD=1`, 320 s (valid per lane.local, 14:04 PDT) | scored: drawn, passes depth where nothing stands in front, reaches the display; A4 by the letter (NOTES 2e) |
| `1-1791752181-lane.gtasagpu1011-2027680` | 50a389ef2b | the same, dump at `after160` (CJ standing in the alley) | queued on the Nova |

## Step 3

Not started. It waits on the shadow cause. Video capture is not live: `request.sh` in `/home/justin/hakuX` (6d8947bb47) has no `--video-seconds`.

Release note (none): frame-dump instrumentation and an opt-in switch (`HAKUX_VTX_HAZARD`, off by default).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
