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

The six fastpaths switches are already ruled out by lane.local's OFF run (3377194).
`HAKUX_PREBUILD` is on by default but only queues pipeline builds; it draws nothing.
