# lane cloud-286 -- #286 3D primitive smoothing residual

**Summary.** Smoothing emulation can reach at most 165,144 of the 605,744
structural px in the 120 `-ls`/`-ps` captures. Of the rest, **349,608 px sit
on pixels our AA-surface path changed where silicon's changed nothing.**
Silicon's `AA_CENTER_CORNER_2` path is bit-transparent: 0 px moved over 48
captures where the flag has no geometric effect. Ours moves 517,872 px on
those same captures. The remaining 69,192 px are wrong in the same place with
smoothing off, and belong to #38 (|d|=2) and #13 (lines). The falsifier did
not fire: 0 px. **Recommendation:** no smoothing lane. Open a new lane for
the AA-surface sample position (net ~242k px, mechanism named below).

## Data, dated

| set | where | date |
|---|---|---|
| goldens (G) | `/home/justin/goldens/results/3D_primitive` | abaire commit `6e159f1532`, dated 2026-08-11; files cloned 2026-09-10 |
| console (K) | `hardware/runs/2026-09-19-calib/full/out/run1` | V1.1 silicon, captures pulled 2026-09-20 07:31 UTC |
| ours (O) | `dispatch/results/0-a-now-8e683b3a26-002-3D_primitive/captures1` | ref `8e683b3a26`, apk `423469eb5d42`, Thor, captured 2026-09-25 20:27 UTC |

Ours is the live requeue of the issue's run A (`void-z-a-now-2b04d4d422-002`,
voided 09-25 for sync validation). Both score the 120 captures identically:
2,710,548 differing, 2,104,804 one-step, **605,744 structural**, 0 exact,
52 `white-content` holding 367,248. The issue's figures reproduce to the
pixel.

Master has moved past `8e683b3a26` in `hw/` twice: #263 (fixed-function
lighting) and #269 (swizzled-surface staging on the CPU paths). Neither is
plausibly on this path: the test draws unlit vertex colour into a linear
(`LU_IMAGE`) surface. That is a judgement, not a measurement.

## 1. The ceiling, re-derived: 165,144 px (the 175,704 is not reproduced)

`struct(G_X, G_P)` is the silicon difference between a smoothed capture X and
its unsmoothed twin P, with some channel moving by more than 1:

| cut | px over 120 |
|---|---:|
| structural (>1), below the label band (y >= 64) | **165,144** (41,286 per submission path) |
| any difference, below the band | 166,384 |
| >2, below the band | 165,016 |
| structural, label band only (the name gains `-ls`/`-ps`) | 25,440 |
| console `struct(K_X, K_P)`, below the band | **165,144**, every row equal to the golden figure |

No cut gives 175,704 (= 43,926 x 4). The 09-12 number was one submission path
scaled by 4, using a different edge/threshold definition over the 09-12
captures. The ceiling is a property of silicon alone, so it is 165,144 on
this definition, and silicon agrees with itself. The console differs from the
goldens on one capture only, `LineLoop-inlinearrays-ls` (4,546 px, all inside
the smoothing footprint, max delta 100). The other three paths of that test
match exactly, so this is one silicon-to-silicon event on a smoothed line
(1.0 goldens vs a 1.1 console, or run-to-run). It does not touch anything
outside the footprint.

## 2. Classes (`decompose286.py`, `tables286.py`, `aapath286.py`)

The footprint is `struct(G_X, G_P)` below the band, dilated by one pixel.
That is the region where silicon's smoothing changes the image, and no
smoothing emulation can move a pixel outside it. Every wrong pixel
(`struct(O_X, G_X)`) lands in exactly one class. None fell in the label band.

| class | what it is | px | of which \|d\|>2 | owner |
|---|---|---:|---:|---|
| **S** smoothing footprint | silicon's coverage fringe or seam, which we do not draw | 186,944 | 166,264 | smoothing emulation (#286/#36); see section 4 |
| **A** outside, our AA path moved the pixel | `O_X != O_P` where `G_X == G_P` | **349,608** | 26,732 | **none: new lane, section 3** |
| **U** outside, our AA path left it alone | the same pixel is wrong in the unsmoothed twin | 69,192 | 6,336 | #38 (\|d\|=2: 62,856); #13 (lines `-ps` \|d\|>2: 6,336) |
| total | | **605,744** | 199,332 | |

Two thirds of the "structural" residual (406,412 px) is exactly |d| = 2. It is
not a region defect: 238,560 of those px are pixels where ours(X) is within
1 of ours(P) and ours(P) is within 1 of golden. Two one-step floors stack
into a 2. "Structural = differing minus off-by-one" is too wide a bucket for
this suite.

### The 52 white-content captures first (367,248 px)

`white-content` means only that more than 8 white pixels mismatch below the
label band. Here those are the line `-ls` fringes and the fan and strip
seams crossing white-ish interiors. It is a symptom, not a class.

| (x4 paths) | wrong | S >2 | S =2 | A | A >2 | U | U >2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| LineLoop -ls | 18,192 | 18,184 | 8 | 0 | 0 | 0 | 0 |
| LineLoop -ls-ps | 18,192 | 18,184 | 8 | 0 | 0 | 0 | 0 |
| LineStrip -ls | 16,128 | 16,120 | 8 | 0 | 0 | 0 | 0 |
| LineStrip -ls-ps | 16,128 | 16,120 | 8 | 0 | 0 | 0 | 0 |
| Lines -ls | 9,328 | 9,328 | 0 | 0 | 0 | 0 | 0 |
| Lines -ls-ps | 9,328 | 9,328 | 0 | 0 | 0 | 0 | 0 |
| QuadStrip -ps | 44,584 | 7,184 | 1,504 | 23,732 | 0 | 12,164 | 0 |
| QuadStrip -ls-ps | 44,584 | 7,184 | 1,504 | 23,732 | 0 | 12,164 | 0 |
| Quads -ps | 7,612 | 6,720 | 36 | 488 | 0 | 368 | 0 |
| Quads -ls-ps | 7,612 | 6,720 | 36 | 488 | 0 | 368 | 0 |
| TriFan -ls | 55,608 | 0 | 0 | 47,784 | 2,912 | 7,824 | 0 |
| TriFan -ps | 59,976 | 6,376 | 4,240 | 41,944 | 1,824 | 7,416 | 0 |
| TriFan -ls-ps | 59,976 | 6,376 | 4,240 | 41,944 | 1,824 | 7,416 | 0 |
| **52 total** | **367,248** | **127,824** | **11,592** | **180,112** | **6,560** | **47,720** | **0** |

- **Interior fill / wrong colour:** none at |d|>2 outside the footprint.
  Everything in U here is |d|=2 Gouraud floor (#38).
- **Missing primitive / texture / depth:** none. There is no depth signature:
  U is empty of |d|>2 and A's |d|>2 is all on golden edges.
- **The line `-ls` captures are pure smoothing**: 99.9% in S.
- **The filled white-content captures are mostly A**: our AA path.

### Then the other 68 (238,496 px)

| (x4 paths) | wrong | S >2 | S =2 | A | A >2 | U | U >2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lines / LineStrip / LineLoop -ps | 8,352 | 0 | 0 | 1,704 | 1,560 | 6,648 | 6,336 |
| Points -ls / -ps / -ls-ps | 84 | 0 | 0 | 84 | 84 | 0 | 0 |
| Polygon -ls | 9,664 | 0 | 0 | 9,664 | 548 | 0 | 0 |
| Polygon -ps, -ls-ps | 30,632 | 13,216 | 2,576 | 14,840 | 0 | 0 | 0 |
| QuadStrip -ls | 38,788 | 0 | 0 | 26,088 | 1,172 | 12,700 | 0 |
| Quads -ls | 1,816 | 0 | 0 | 1,416 | 920 | 400 | 0 |
| TriStrip -ls | 36,880 | 0 | 0 | 36,304 | 5,560 | 576 | 0 |
| TriStrip -ps, -ls-ps | 84,384 | 14,056 | 4,848 | 64,456 | 9,472 | 1,024 | 0 |
| Triangles -ls | 6,096 | 0 | 0 | 6,044 | 720 | 52 | 0 |
| Triangles -ps, -ls-ps | 21,800 | 11,168 | 1,664 | 8,896 | 136 | 72 | 0 |
| **68 total** | **238,496** | **38,440** | **9,088** | **169,496** | **20,172** | **21,472** | **6,336** |

- The only |d|>2 defect with smoothing off is on lines with `-ps`: 6,336 px,
  wrong in the same place in the unsmoothed twin. This is plain line
  rasterisation, #13.
- Points: 7 dropped points x 4 paths = 84 px, all A. This is the 09-15
  `aa-drops-seven-points` finding, and the mechanism below explains it.

Full per-capture rows are in `decompose286.tsv`.

## 3. Class A: our AA-surface path is not transparent, silicon's is

`aapath286.py` isolates the AA path. It uses the 48 captures where the flag
has no geometric effect: `LINESMOOTH` on a filled primitive, `POLYSMOOTH` on
a line, either on points. The test still switches to the AA surface for them
(`three_d_primitive_tests.cpp:936`).

| | px moved below the band |
|---|---:|
| silicon, `G_X` vs `G_P`, any channel, any amount | **0** |
| ours, `O_X` vs `O_P` | **517,872** |
| wrong on these 48, `struct(O_X, G_X)` | 157,288 (twins: 67,808) |
| ... on pixels our AA path moved | 129,088 |

Silicon renders into the double-pitch AA surface and resolves it, and the
result is **byte-identical** to drawing without it. Ours is not.

**The first place our path differs.** The guest resolves (`:1023-1059`) by
drawing a 640-wide quad over the 1280-wide `LU_IMAGE` texture, with
texcoords `0..1280`. The stage uses the default `SetFilter(0)`, which is
`MIN_BOX_LOD0` (point sampling; `pbkitplusplus/src/texture_stage.h:175`). So
output pixel x samples u = 2x+1, which is exactly on the boundary between
texels 2x and 2x+1: a **texel tie**.

- **Silicon:** the result is transparent, so the texel silicon picks must hold
  exactly the value a non-AA draw puts at the pixel centre. That matches the
  mode's name: `CENTER_CORNER_2` has one sample at the pixel centre and one at
  the corner.
- **Ours:** `pgraph_apply_anti_aliasing_factor` (`hw/xbox/nv2a/pgraph/pgraph.h:572`)
  models `CENTER_CORNER_2` as `width *= 2` and nothing else: a grid of
  independent half-width pixels. Their centres land at guest x+0.25 and
  x+0.75, and neither is the pixel centre. Whichever texel our resolve picks,
  it was shaded a quarter pixel off. That gives, in order of size:
  - a ±1 shift along every colour gradient: 322,876 px of A at |d|=2;
  - edges moving by a sample: 26,732 px of A at |d|>2, all on golden edges;
  - a 1-px point landing in only one half-column, so it vanishes when the
    resolve picks the other: the 7 dropped points, decided by horizontal
    position alone, as 09-15 measured.

**What a fix would recover.** With a transparent AA path, ours(X) outside the
footprint equals ours(P). The error left there is ours(P)'s own: 176,464 px
against 418,752 now, so **~242,288 px net**. That is an estimate. It assumes
`G_X == G_P` outside the footprint, which holds to within 1.

| primitive (all flags, x4) | outside now | if transparent | net |
|---|---:|---:|---:|
| TriFan | 154,328 | 51,500 | 102,828 |
| TriStrip | 102,360 | 37,080 | 65,280 |
| QuadStrip | 110,580 | 55,944 | 54,636 |
| Polygon | 24,504 | 0 | 24,504 |
| Triangles | 15,064 | 884 | 14,180 |
| Points | 84 | 0 | 84 |
| Lines, LineStrip, LineLoop | 8,352 | 9,712 | -1,360 |
| Quads | 3,528 | 21,344 | **-17,816** |

Quads gets worse. Our shifted AA sampling happens to cancel part of Quads'
own plain-arm error, and a correct fix gives that back.

This is not in #274. `Antialiasing_tests`' residual is texture content over
CPU-written memory, and there "what varies with AA mode we already get right"
(`line-polygon-smoothing.md` section 4). The tie our resolve breaks at
u = 2x+1 is #282's rule (nearest-sample ties), and a fix has to get both
halves right: the sample position (A) and which texel the tie selects
(#282).

## 4. What only smoothing emulation could touch

| | px |
|---|---:|
| footprint, \|d\|>2 | 166,264 |
| footprint, \|d\|=2 | 20,680 |
| **silicon's own ceiling** | **165,144** |

We get 165,032 of silicon's 165,144 footprint px wrong: essentially all of
it, because we draw no coverage at all. Line smoothing (-ls on lines) is
87,392 px of the ceiling and polygon smoothing is 77,752. The blockers in
`line-polygon-smoothing.md` section 3 still stand:

- lines need `VK_EXT_line_rasterization` `smoothLines`, and its six feature
  booleans have never been measured on the Adreno;
- polygons have no Vulkan analog short of MSAA;
- both need a synthesised blend state.

**Recommendation.**

- **Smoothing: no lane now.** 165k px across 120 synthetic captures, games
  "low", and the first step is still a one-capture device probe of
  `VkPhysicalDeviceLineRasterizationFeaturesEXT`. If anyone wants to move
  this, that probe is the lane, not an implementation. Keep #286 as the
  holder of the 165,144 ceiling, with its figure corrected from 175,704.
- **AA surface sample position: a new lane, named `aasample`.** Net ~242k
  here (40% of this residual, 1.5x the whole smoothing ceiling). It touches
  `pgraph.h` (`pgraph_apply_anti_aliasing_factor`) and the Vulkan
  viewport/scissor consumers in `vk/draw.c`. Any game that renders to a
  `CENTER_CORNER_2` surface carries the same quarter-pixel shift.
  - Its falsifier leg: on the 48 no-op captures, `O_X == O_P` byte-exact,
    as silicon's are.
  - Its must-not-move leg: the 40 plain captures.
  - The Points leg: all 12 points present in every AA capture.
  - The lane should read the texel-tie rule from #282 before it chooses which
    half-column to put at the pixel centre.
- **U** needs no new owner: #38 owns the |d|=2 Gouraud floor (its table
  already lists `3D_primitive`'s filled primitives), and #13 owns the 6,336
  px of line rasterisation.

## Falsifier (stated and committed in `c818884db9` before it was run)

Claim: the part of the 605,744 outside silicon's own footprint is not
smoothing. The console run is independent silicon. For each X, take
`struct(K_X, K_P)`, the pixels where the console's smoothing changed its own
image, and intersect it with our wrong pixels that the golden footprint put
outside smoothing.

A hit would have been more than ~4,200 px (1%), or anywhere near 175,704. No
hit is near 0.

**Result: 0 px, and 0 with the console mask dilated by one pixel.** The
console's smoothing never reaches a pixel we called not-smoothing. The
console's smoothing footprint equals the golden footprint on every one of
the 120 rows (165,144 both ways).

## Do not repeat

- Do not treat `white-content` as a defect class in this suite. It flags line
  fringes and seams on white interiors.
- Do not read "structural" (differing minus off-by-one) as a region defect
  here: 406,412 of 605,744 px are exactly |d|=2.
- The 175,704 ceiling is not reproducible: use 165,144.
- The four submission paths replicate exactly for filled primitives, and
  within a few px for line `-ls`. Measure one and multiply by 4.
