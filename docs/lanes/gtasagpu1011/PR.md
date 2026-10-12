gtasagpu1011: GTA San Andreas, hard-edged sky polygons and no shadow under CJ (#433, 0.5)
State: ready

Lane: gtasagpu1011      Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 6d8947bb47
Files: docs/lanes/gtasagpu1011/NOTES.md, docs/lanes/gtasagpu1011/PR.md, docs/lanes/gtasagpu1011/dispcmp.py, docs/lanes/gtasagpu1011/dispcmp_lib.py, docs/lanes/gtasagpu1011/fdread.py, docs/lanes/gtasagpu1011/fsz.py, docs/lanes/gtasagpu1011/gradwatch.py, docs/lanes/gtasagpu1011/litfail.py, docs/lanes/gtasagpu1011/scrread.py, docs/lanes/gtasagpu1011/sqscan.py, docs/lanes/gtasagpu1011/stillcmp.py, docs/testing/nv2a_index.json, docs/testing/predictions/gtasagpu1011-screen.json, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/vertex.c
Prediction: docs/testing/predictions/gtasagpu1011-screen.json @ 70a4f2feb46e81ef45e0035e898a015daac96ac562ce91fb107ef4c93041ef07 (the title screen, self-judged by scrread.py); the switch screens, frame dumps and proof soaks are read by hand, each run's prediction written in NOTES.md (sections 1, 2b-2f, step 3) before it was queued
Needs device: yes (Nova)    Needs NDK: yes

The sky defect is found and fixed behind `HAKUX_VTX_HAZARD=1`, which is off by default. Two proof soaks with the switch show no sky defect in 136 post-mark stills or 240 one-a-second video frames. The current build shows 5 in 67 stills and 7 in 120 video frames. The shadow has no renderer defect: it is drawn as the game asks and it is in the stills, but it is faint (11-24% darker than the ground). It measures the same with and without the switch. The cross-title screen is lane.local's, combined with lane.nfsaudio1011's switch.

## Step 1: switch discriminators

These are `gta-sa` soaks, 600 s, frames every 5 s, at 6d8947bb47.

| switch | run | CJ's shadow in sunny post-mark stills |
|---|---|---|
| `HAKUX_SURFGPU=0` | `1-1791735439-lane.gtasagpu1011-3545202` | by eye: no, 0 of 66. Measured (attempt 4): yes, 0.81-1.08 of the shadow in every alley still |
| `HAKUX_GPL=0` | `1-1791735439-lane.gtasagpu1011-3545543` | by eye: no, 0 of 71. Measured: yes, 0.89-1.07 |
| fastpaths six OFF (lane.local) | `1-1791733219-lane.local-3377194` | by eye: no. Measured: yes, 0.88-1.10 |

By eye, no switch brought the shadow back. Measured against a dump's mask (step 2, `stillcmp.py`), the shadow was there all along, in every run.

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

### Shadow: drawn as the game asks, present in the stills, faint

The chain, every frame (NOTES 2d):

- **n0-n4:** draw CJ into a 64x64 render target at 0x3513980.
- **n5:** inverts it.
- **n6-n8:** blur it into 0x3517a00 (32x32) through 0x34e7480.
- **n9:** multiplies it by a 32x32 gradient at 0x034e8500.
- **n10:** adds a black border strip, so the clamp reads black.
- **The projection:** puts it on the ground. Blend is 0*S + (1-SC)*D, depth LEQUAL, no z write, alpha test GT 0, diffuse 0x8c-0x8f.

Each step was checked against the dumps:

| run | case | finding |
|---|---|---|
| `651566` (schema 6) | the chain's targets | the silhouette and blur are right (outcome A, NOTES 2d) |
| `818197` (schema 7) | CJ running down the road, 24 consumers | 48% of lit pixels pass depth (the rest sit behind the truck or CJ's foot), 80% of those darken, the display images carry 0.99-1.43 of the shadow; offline float32 depth rebuild agrees with the ideal raster (NOTES 2e) |
| `2027680` (schema 7) | CJ standing in the alley, 24 consumers | 92% of lit pixels pass depth, 76% of those darken, the display images carry 1.01-1.03 of the shadow (NOTES 2e) |
| `2946023` (schema 8) | how the gradient is made | at the title's start, 32 LINES draws, colour `128 - 2y` on row y; the readback equals the colours exactly; n9 samples those texels, `tex0 * diffuse`, no scale dropped (NOTES 2f, G1) |

**The shadow is in the stills.** From the route's `cut1` to `cut3`, CJ stands still in the alley with the camera fixed, so 2027680's projection mask fits every run's stills from that window. `stillcmp.py` measures each still's luminance in the mask against a ring around it, on the pre (0) to post (1) scale:

| run | build / switch | share of the shadow in the alley stills |
|---|---|---|
| `2027680` | `HAKUX_VTX_HAZARD=1` | 0.86-1.17 (12 stills) |
| `1-1791733219-lane.local-3377194` | fastpaths six OFF | 0.88-1.10 (9) |
| `1-1791733219-lane.local-3377243` | fastpaths ON | 0.87-1.07 (9) |
| `3545202` | `HAKUX_SURFGPU=0` | 0.81-1.08 (9) |
| `3545543` | `HAKUX_GPL=0` | 0.89-1.07 (9) |
| `176610` | switch off | 0.88-1.11 (9) |

The same mask moved onto other ground reads within 0.02 of its own pre/post value in every still, so a still without the shadow would read near 0.

**It is faint because the game makes it faint.** The gradient fades it from 0.5 to 0.25 along its length, and the projection's diffuse is 0x8c-0x8f. The darkest pixel is 0.76 of the ground's colour on the road and 0.82 in the alley. Every one of those inputs is drawn as asked. "No shadow under CJ" was this shadow missed by eye at still scale.

The owner's "shadow dropping out" in play: the vertex hazard rewrote a shadow-chain draw (n10, the border strip) in 176610, and the fix removes that. Beyond that, the dumps show the game's own causes: occluders, a fading diffuse on other peds' shadows, and a 24% darkening that is lost on dark ground. The fix's video goes to the owner.

**Schema 6 (8e40300c6c)** adds an `rtt` token to `XEMU_FRAME_DUMP`. For each draw that binds or samples a colour target of 64x64 or smaller, it reads back:

- the target itself;
- the surface each stage samples;
- the texture copy each stage samples.

`fdread.py DUMP rb F OUTDIR` turns the readbacks into PNG sheets. Predictions A-D and the timing case are in NOTES 2d.

**Schema 7 (50a389ef2b)** extends `rtt` to the draw that projects the shadow. Before that draw is recorded, it reads the full colour target (`pre`) and its depth (`zpre`). After the draw, it reads the colour target again (`post`). `fdread.py DUMP cons` reports how many pixels the draw changed, where they are, and the depth under them. Predictions A1-A4 are in NOTES 2d.

**Schema 8 (e53b9fa918)** reads back the texture a small-target draw samples when it was never a render surface, logs an inline-array draw's raw vertex words, and adds `watchNN`: from startup, only draws into small targets, until NN are logged. n9 multiplies the shadow by exactly (129 - 2y)/255 per row (651566, 5269 texels, no mismatch). That factor comes from a 32x32 gradient made at the title's start, outside every earlier dump. 2946023 caught it being made (G1, NOTES 2f).

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
| `1-1791752181-lane.gtasagpu1011-2027680` | 50a389ef2b | the same, dump at `after160` (CJ standing in the alley) | scored: drawn, passes depth, reaches the display; A4, no defect (NOTES 2e) |
| `1-1791755383-lane.gtasagpu1011-2946023` | e53b9fa918 | schema 8 `watch600` dump from startup: how the 32x32 shadow gradient is made, and n9's texels and diffuse | scored: G1, the gradient is drawn exactly as asked (NOTES 2f) |
| `1-1791766181-lane.gtasagpu1011-1063190` | d50bf5c47c | step 3 proof 1: gta-sa 600 s, `HAKUX_VTX_HAZARD=1`, frames every 5, video 120 s | scored: S and H hold, C fails by the letter (NOTES, step 3 result) |
| `1-1791766181-lane.gtasagpu1011-1063583` | d50bf5c47c | step 3 proof 2, the same | scored: the same |
| `1-1791756360-lane.soakvideo1011-3149619` | b73d50a070 | soakvideo1011's gta-sa video soak, no switch: the current build for the side-by-side | read: 5 of 67 post-mark stills with the sky defect |

## Step 3: proof

The proof runs are two `gta-sa` soaks on the Nova at d50bf5c47c with `HAKUX_VTX_HAZARD=1`: 600 s, frames every 5 s, and 120 s of video from 30 s after the mark. Neither has a BugCheck. Predictions S, H and C were written before queueing (NOTES, step 3).

| run | sky polygons, post-mark stills | video at 1 frame/s (pointers only) | shadow share, alley stills (`stillcmp.py`) | `vtx_hazard` finishes per 10 s, gameplay |
|---|---|---|---|---|
| `1063190`, switch on | 0 of 67 | 0 of 120 | 0.77-1.11 (13) | 69-395, median 260 |
| `1063583`, switch on | 0 of 69 | 0 of 120 | 0.78-1.11 (14) | 126-437, median 314 |
| `3149619`, current build | 5 of 67 | 7 of 120, plus a magenta quad on the road | (not measured) | (switch off) |

- **S (sky, P 0.85): holds.** 0 of 136 pooled stills. The current build runs at about 4 per 144, so zero by chance is about 1-3%. The verdict rests on the stills alone.
- **Video column:** the brief assumed mp4 could not be decoded here and said not to score it. `ffmpeg` in `~/.local/bin` decodes it, so I sampled each mp4 at 1 frame/s by eye. This is not a score. It tells the owner where to look, in the table below. The owner's video check decides.
- **H (shadow, P 0.95): holds.** Every alley still is at 0.7 or more. By eye, on open sunny ground, the shadow is no easier to see in either arm. That fits a faint shadow, not a missing one. The video check is the owner's.
- **C (cost, P 0.8): fails by the letter.** 11 of 79 lines are outside 100-370, between 69 and 437. That is about one extra submit a frame, and up to 1.5. No frame-rate claim is made from these runs; the screen reads gfps.

### For the owner: stills and video

The results are in `/home/justin/hakux-work/dispatch/results/<run>/`, with stills at `frames/fNNNNN.png` and video at `video/v00001.mp4` and `video/v00002.mp4`. The pairs are matched by time after the route's mark.

| current build (3149619) | what is there | switch on (1063190) | switch on (1063583) |
|---|---|---|---|
| f00041, 07:55 | the alley: sky white, treetops and a crane smeared | f00041, clean sky | **f00040, 07:52: the same spot, clean blue sky** |
| f00070, 10:45 | a saturated blue rectangle over the upper right sky | f00070, clean | f00069, clean |
| f00076, 11:19 | sky blown out yellow-white with rays, a tree smeared | f00076, clean | f00075, clean |
| f00081, 11:48 | a pale white wedge from the top edge of the sky | f00081, clean | f00080, clean |
| f00107, 14:18 | sky white, trees smeared | f00107, clean | f00106, clean |

Video, seconds into each mp4 (within about 1 s):

| run | mp4 | where to look |
|---|---|---|
| `1-1791756360-lane.soakvideo1011-3149619` (current) | `video/v00001.mp4` | +33 s pale wedges from the top edge; +55 s a red wedge over the upper right sky |
| | `video/v00002.mp4` | +4 s sky blown out, trees smeared; +32 s a magenta quad on the road (a ground polygon); +46 s a pale rectangle in the sky |
| `1-1791766181-lane.gtasagpu1011-1063190` (switch on) | `video/v00001.mp4`, `video/v00002.mp4` | no sky defect at 1 frame/s. For the shadow: CJ runs on open, sunny road and sidewalk through most of both segments |
| `1-1791766181-lane.gtasagpu1011-1063583` (switch on) | `video/v00001.mp4`, `video/v00002.mp4` | no sky defect at 1 frame/s |

**Regression:** The cross-title screen runs combined with lane.nfsaudio1011's switch (lane.local); prediction `gtasagpu1011-screen.json`. `HAKUX_VTX_HAZARD` stays off by default in this PR.

Release note (none): frame-dump instrumentation and an opt-in switch (`HAKUX_VTX_HAZARD`, off by default).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
