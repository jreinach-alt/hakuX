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
