# Galleon's flashing deck texture

Observed 2026-09-11 on a Retroid Pocket Nova, Turnip T30, build `d191c1877c`.
Reported as a long-standing defect and visible in third-party video of this
emulator, so it is not a regression from recent work.

The scene was driven by hand while a capture script took 40 consecutive frames
and injected no input. Evidence in `images/`: `galleon-deck-normal.png` (frame
38), `galleon-deck-flash.png` (frame 39), and the crops in `leftdeck.png` and
`trio.png`.

## What it is

Intermittent, roughly one frame in forty in this scene, and stronger on the
left of the deck than the right. On a flashing frame the deck is brighter and
**loses its smooth mid-distance blend for a hard high-frequency stipple.**

Left-deck crop, same region, consecutive frames:

| frame | mean luminance | local contrast (std) |
|---|---|---|
| 38 | 92.2 | 24.2 |
| **39 (flash)** | **112.9** | **29.4** |
| 40 | 90.1 | 24.2 |

## Why the numbers matter more than the appearance

The first guess from a thumbnail was that a detail or dirt layer drops out,
leaving a lighter base wood. **The contrast figure rules that out.** Losing a
modulating layer would raise the mean and *lower* local contrast, because the
surface would flatten. Here the mean rises by 21 and the contrast rises too,
and the crop shows an aliased crosshatch appearing rather than detail
disappearing.

Brighter, sharper and aliased at mid distance is the signature of **sampling a
level of the mip chain that is too detailed for the distance**: no
minification averaging, so the texture both aliases and reads lighter. The two
candidate causes are mip level selection, and a texture being re-created or
re-uploaded without its full mip chain so only the top level exists until it is
rebuilt.

The second is the more interesting one here, because it would explain the
intermittency directly: a texture re-uploaded on the frame the guest touched it
would flash for exactly as long as it took to repopulate. This emulator polls
the dirty bitmap before every draw and re-binds on any hit, which gives such a
re-upload plenty of opportunities.

It is **not** lighting. A lighting or vertex-colour change brightens without
introducing high-frequency detail.

## Scene diagnostics during the capture

| | |
|---|---|
| guest frame rate | 14 fps, 71-75 ms |
| VBLANKs per flip | 4.3 |
| renderer idle | 46-49 ms of the frame |
| dirty-bitmap queries | ~1,200 per frame |
| slow stores into code pages | ~38,000 per 120 frames, one page taking 25,000 |

Worth recording that Galleon leans on the retranslation loop far harder than
Fuzion Frenzy did, roughly five times the slow-store rate, which is consistent
with it running at 14 fps.

## Revised: it is the stride, not the mip level

The mip reading above is **wrong**, and two pieces of evidence killed it.

First, the report from someone watching it live: the glitched patch cycles
through several different patterns and lighting, then sweeps across to the
right of the screen before the cycle restarts. A mip level cannot do that. A
wrong level gives one consistently wrong appearance, not a sequence.

Second, cropping the same deck patch out of all 40 frames and tiling them
(`images/galleon-deck-cycle.png`) shows what the sequence is: **fine diagonal
hatching, coarse diagonal hatching the other way, smooth plain wood, and a
strong crosshatch weave, in rotation.** The pattern's *direction* changes
between frames.

That direction change is the diagnostic part. Mip selection cannot rotate a
pattern. Reinterpreting the same texture memory with the wrong row stride can,
and does: a stride mismatch shears the image diagonally, and the shear angle
is set by how far wrong the stride is. A stride that differs frame to frame
gives a rotating set of shear angles, and content that walks sideways, which is
exactly the reported sweep to the right.

So the working diagnosis is **the deck texture being sampled with an incorrect
and varying row stride or tiling interpretation.** The candidates, in the order
worth checking:

1. Swizzled versus linear confusion. The NV2A stores most textures swizzled,
   and un-swizzling with the wrong assumption produces precisely this kind of
   diagonal shear.
2. Pitch read from the wrong register, or from a surface's pitch rather than
   the texture's.
3. A colour surface sampled as a texture where the two disagree about pitch.
   Related to, but distinct from, the channel-order case the desktop lane
   fixed in `a8f2454a`; that one swaps colours, this one shears geometry.

Recording the churn honestly: this defect has now had three readings from me.
A dropped detail layer, from thumbnails. A wrong mip level, from luminance and
contrast. And now a stride mismatch, from the pattern rotating. Each revision
came from evidence the previous one could not explain, and the first two were
stated too confidently for what they rested on.

## Stride is ruled out. It is the coordinate side.

Measured 2026-09-11 on the live scene, build `865d829fe2`, logging each
texture stage's format, dimensions, level count, pitch and swizzled flag
whenever any of them changes. 22,493 transitions over about 45 seconds of
deck gameplay.

| | |
|---|---|
| distinct texture addresses | 115 |
| **addresses whose geometry ever changed** | **0** |
| pitch values seen | 0 (swizzled), 512 and 2560 (the 93 linear ones) |
| swizzled vs linear | 22,400 vs 93, never flipping for one address |
| stages in use | 0, 1 and 2, so this is multi-textured |

**Not one of the 115 textures ever changed its format, size, level count,
pitch or swizzled flag.** So the memory is not being reinterpreted at a
varying stride, and the shear cannot be coming from the texture side. The
stride reading is dead, on the same criterion this document set for it before
the measurement: if all five are stable across a flash, the cause is the
coordinate side.

That fits the reported behaviour at least as well. A wrong texture matrix
shears and rotates the sampled pattern, and a matrix left over from a
different material would give a rotating set of wrong appearances as materials
cycle -- "a few different patterns and lighting" -- with content walking
sideways. Three active stages means a detail or light-map stage with its own
generated coordinates is a candidate for carrying stale state.

So the next measurement is the texture matrix and coordinate generation mode
per stage, logged on change in the same way. Worth noting that the texture
matrix data is one of the fields an audit of the threaded-draw snapshot flagged
as uncaptured, which is at least a hint that this state is handled less
carefully than the rest.

### A note on the instrumentation itself

Logging every transition produced about 500 lines a second, which flooded the
logcat ring and **evicted the frame-pacing lines from the same capture** -- 1
survived where a dozen were expected. The geometry answer was unaffected
because it only needed the transitions, but a measurement that destroys the
other measurements in the same window is a bad trade. The next version should
emit a per-frame summary rather than a line per bind.

## Matrix-enable and texgen modes are stable too

Measured 2026-09-11 on the town save, build carrying the per-frame coordinate
summary. 50 frames captured, 431 frames of coordinate state logged, no input
injected.

**The artifact is present in this capture** -- the ground cycles through
smooth dirt, grass and a hatched crosshatch across the 50 frames
(`images/galleon-town-cycle.png`), so a stable reading here is a real negative
and not an absence of the defect.

Every one of the 431 frames reported the **identical** set of five
combinations:

| stage | texture matrix | texgen s,t,r,q |
|---|---|---|
| 0 | off | 0,0,0,0 |
| 0 | on | 0,0,0,0 |
| 1 | on | 0,0,0,0 |
| 2 | on | 1,1,1,0 |
| 3 | on | 1,1,1,0 |

Not one frame differed. So the matrix-enable flags and the texgen modes are
not what is cycling.

### What is now ruled out, and what is not

Ruled out by measurement: texture format, dimensions, level count, pitch and
the swizzled flag (115 textures, 22,493 binds, zero changes); and the
texture-matrix enable and texgen mode per stage (431 frames, zero changes).

**Not** ruled out, and the two candidates left:

1. **The matrix contents.** Only the enable bit was logged, never the values.
   Stages 2 and 3 use generated coordinates *through* a matrix, which is
   exactly the arrangement where a stale or wrong matrix produces a sheared,
   cycling result while every flag stays put.
2. **Per-draw attribution.** The per-frame summary merges every draw in the
   frame, so it cannot say whether the *ground* draw specifically received the
   right stages. A stable frame-level set is consistent with one draw getting
   the wrong one. This is a limitation of the measurement, not a finding.

So the next measurement is the matrix values for stages 2 and 3, logged on
change, and ideally attributed to the draw rather than the frame.

## The strongest lead: stage 1's tiling scale takes three values

Logged the texture matrix *contents* per stage, on change, with the frame and
bind index. 17,683 changes over 104 frames while the artifact was on screen.

| stage | distinct matrices | changes | max in one frame | row 0 |
|---|---|---|---|---|
| 0 | 630 | 1,995 | 19 | `1 -0 0 0` — per-object, identity-like |
| **1** | **3** | **14,431** | **138** | **`8 0 0 0`, `16 0 0 0`, `50 0 0 0`** |
| 2 | 3 | 627 | 6 | `0 0 0.0005 -0.5` — projection-like |
| 3 | 3 | 630 | 6 | `0 0 0.002 -0` — projection-like |

**Stage 1 is a detail texture whose coordinate scale is only ever 8, 16 or 50,
and it flips between them up to 138 times in a single frame.** A detail texture
tiled 8, 16 or 50 times across a surface produces hatching at three different
densities, which is what the ground cycles through. Nothing else measured so
far has that shape.

This is a lead and not yet a finding. Three tiling densities alternating is
also exactly what a scene with three kinds of ground material legitimately
looks like. The open question is whether the *ground* draw receives the scale
that belongs to it, and that needs per-draw attribution against a frame where
the artifact is visible.

## Why this is the last thing to chase through logcat

Two of these measurements have now destroyed the evidence sitting beside them.
The per-bind geometry logger ran at 500 lines a second and evicted the
frame-pacing lines; this matrix logger ran at 17,683 lines and evicted the
startup lines, which is where the answer to "did the Vulkan validation layer
load" would have been. So **the validation-layer and synchronization-hazard
test is inconclusive, not negative** -- zero reported hazards with zero
validation lines of any kind means the layer never spoke, and the layer binary
ships in the package but was not found extracted on the device.

The right channel was already in the tree. `nv2a_dbg_trigger_diag_frames`
writes a per-draw JSON session to a file, with deduplicated shader sources and
frame-to-frame fingerprint diffs, and a file cannot be evicted by its own
volume. It already recorded blend, depth, stencil, cull, write masks, both
surfaces, the combiner constants and every texture stage's format, size,
levels, pitch, wrap modes and border colour; it now also records the
matrix-enable bit, the four texgen modes and all sixteen matrix values per
stage.

One capture therefore holds every hypothesis this investigation has raised and
every one it has eliminated. The remaining questions -- whether the ground
draw gets the wrong tiling scale, whether a texture is re-uploaded on the
flashing frame, whether the stage set differs for that draw -- are all
answerable from a capture already taken, offline, without another build or
another device trip.

## Found it: the detail scale and the detail texture go out of step

Four diagnostic captures, ten frames each, driven by hand from the Debug
Capture button. 303 draws, 299 with textures. The per-draw record now carries
each stage's matrix, so this was answerable offline with no further builds --
which is the whole argument for capturing everything at once.

**Stage 1 is a detail texture, and its matrix scale is paired with the texture
size to hold the detail density constant.** Across the captures, scale 8 is
always used with a 256-wide texture and scale 16 with a 128-wide one. Both
give 2048 detail texels across the surface:

| scale x texture width | draws |
|---|---|
| 2048 | **166** |
| **1024** | **1** |

**One draw in 167 breaks the invariant**: session 4122, frame 4122, draw 92,
`TRIANGLES` count 162, shader `0xbf6ac861...` -- **scale 8 with a 128-wide
texture**, half the intended density.

And the capture saved that draw's framebuffer, so the artifact is visible in
the act. Differencing the framebuffer after draw 91 against after draw 92
isolates exactly the geometry it drew: a stone wall, which comes out
**markedly brighter and with visibly coarser stone blocks** than the
correctly-drawn wall beside it (`images/galleon-outlier-draw.png`). Brighter
and coarser is what half the detail density looks like, and it is what was
reported from the outside as "more brightly lit and out of place".

### The mechanism

Scale 8 belongs with a 256-wide texture. On the failing draw the matrix held
the scale for the 256 texture while the 128 texture was bound. So the
**texture binding advanced and the matrix did not**: the two are maintained in
different dirty-tracking domains -- the texture through
`texture_state_gen`/`texture_vram_gen` in the renderer, the matrix through the
vertex shader constant file -- and a draw consuming both saw them out of step.

That also explains every earlier negative result. Each field was individually
stable, which is why logging them one at a time found nothing: **the defect is
not in any single field's value but in the relationship between two of them.**
An invariant across fields was needed, and only a capture holding all of them
at once could express it.

### RETRACTED: the draw-queue mechanism cannot explain this

Asked to confirm the diagnosis rather than act on it, and it does not survive.
Three independent problems, plus one with the evidence I presented.

**1. The mechanism is dead.** `nv2a_diag_log_draw_call` is called immediately
after `vkCmdDrawIndexed` and `end_draw` on the `inline_elements` path
(`draw.c:6050`). Draw 92 is `TRIANGLES`/`inline_elements`, so it went through
**immediate submission and never entered the merge queue.** The queue's
blindness to transform constants -- the whole code-level story below -- cannot
account for it. That finding about the queue may still be a real latent bug,
but it is not this one.

**2. The invariant may be fitted rather than found.** 2048 rests on exactly two
observed pairings, 8 with 256 and 16 with 128. Draw 92 is also structurally
unique in the capture: the only large indexed-triangle draw with a stage-1
matrix, where every other large one is a strip. A third legitimate pairing for
a differently-submitted object cannot be excluded from 167 draws.

**3. Frequency mismatch.** One violation across the seven captured frames that
contain draws, against an artifact reported as cycling continuously. A cause
should fire at roughly the rate of its effect.

**4. My visual evidence did not show what I said it showed.** The before/after
comparison put the framebuffer before draw 92 against the one after it. Draw 92
painted a *different object* into that region, so the comparison shows two
different walls, not one wall drawn wrongly. It never supported "draw 92
rendered incorrectly", and presenting it that way was wrong.

### What would actually settle it

The common flaw in every measurement so far, including the good ones, is that
they all read **emulator state**. If the defect is ours it is a divergence
between emulator state and what reached the GPU, and no amount of state
logging can see that divergence.

1. **Rule the driver in or out first.** Galleon captured across Turnip T30, T26
   and the Qualcomm driver, frames compared. If the artifact moves with the
   driver, every emulator-state measurement has been looking at the wrong
   layer. The swap harness exists and this needs no code change. The one
   earlier attempt at the validation layer failed silently and proved nothing.
2. **Then log what the GPU received, not what the state said** -- the image
   view actually bound per stage and the matrix actually in the pushed uniform
   buffer at submission. A disagreement between that and the state file is the
   bug directly, with no invariant and no assumption about the game's intent.
3. **Fix the frequency first.** Count artifact frames per hundred before
   believing any candidate, and require the candidate to fire at a comparable
   rate.

What stands regardless: the capture now records every per-draw field at once,
and `check_diag_invariants.py` exists. Both are useful whatever the cause turns
out to be.

### The queue finding, kept because it is probably a real bug elsewhere

The draw queue merges consecutive draws and decides whether their uniforms
changed with a single comparison (`draw.c`, `check_draw_mergeable` and the
enqueue path):

```c
bool uniforms_changed = (q->count > 0 && pg->any_reg_gen != q->any_reg_gen);
```

**The texture matrix is not a register.** It is written by
`SET_TRANSFORM_CONSTANT` (`pgraph.c:3130`), which lands in `pg->vsh_constants`
and sets `vsh_constants_dirty[]` and `vsh_constants_any_dirty` -- and does
**not** bump `any_reg_gen`. The draw queue never reads
`vsh_constants_any_dirty` at all.

So a transform-constant change between two mergeable draws is **invisible to
the queue**: both draws are merged and both render with the uniform values
captured for the first one, including its texture matrix.

That predicts exactly the signature measured, down to which side was wrong.
`texture_state_gen` *is* in the mergeability test, so the texture is always
right; the constant file is not, so the matrix is inherited from the previous
draw. The failing draw kept its correct 128-wide texture and took the
preceding material's scale of 8. It also explains the rarity: it only bites
when the guest changes a transform constant and no register between two draws
the queue would otherwise merge.

### The acceptance test, written before the fix

`docs/testing/check_diag_invariants.py` checks the pairing over any capture
and exits non-zero on a violation. Baseline over the four sessions:

```
167 stage-1 draws checked, 1 violating the pairing
  frame 4122 draw 92: scale 8.0 with a 128-wide texture = 1024, expected 2048
```

So "did the fix work" is a script over a capture rather than a person watching
for a flash, which is what made this defect so expensive to chase in the first
place.

### Still to establish

The shape of the fix, and its cost. Making the queue aware of the constant
file is the obvious move -- a constants generation counter captured on enqueue
and compared in `check_draw_mergeable`, or bumping `any_reg_gen` on a
transform-constant write. The second is a one-liner and the blunter of the
two: every constant write would then break a merge, and this title writes
constants constantly, so it could cost a large share of the merging the queue
exists to do. The first is narrower but needs a new counter threaded through
the queue and the snapshot.

Which to take is a measurement, not a judgement: land the blunt version first,
check the invariant passes, then read the merge rate off the existing
`OPT_STAT` counters to see what it cost. If the cost is real, the narrow
version earns its complexity; if it is not, the one-liner is the fix.

## Next measurement, not yet done

Log the texture matrix and the coordinate generation mode for each active
stage, on change, and as a per-frame summary rather than a line per bind. If a
stage's matrix or texgen mode differs between a clean frame and a flashing one
for the same material, that is the defect. Three stages are active, so include
which stage.

## The fourth retraction holds, and it holds for a better reason

Measured 2026-09-13, entirely offline, from the four diagnostic sessions in
`~/hakux-work/diag/` and the frame mosaics already in `images/`. No device
time: Galleon lives only on the Nova and the Nova was held. All four
objections above were re-examined. Two are confirmed, one is confirmed and
generalised, one is **downgraded** -- and the document's central quantity, the
artifact's rate, turns out to have been measuring the wrong event.

### The rate was never measured, and the frame it was measured on is the wrong frame

`docs/testing/galleon_flash_rate.py` counts flashing frames from frames on
disk. It separates two things that mean luminance and local contrast cannot:

| | |
|---|---|
| a **brightness** excursion | the surface reads lighter, at large scale |
| a **stipple** excursion | a hard high-frequency hatch appears, with a direction |

Over `images/galleon-deck-cycle.png`, the 40-frame left-deck mosaic this
document is built on, **they are not the same frames.**

| | mean lum | HF energy | d1/d2 |
|---|---|---|---|
| set median | 87.4 | 4.65 | ~1.07 |
| **frame 38** (this doc's flash) | **110.2** | **4.94** | 1.14 |
| frame 4 | 96.0 | **8.96** | 0.75 |
| frame 8 | 89.0 | **7.86** | 0.50 |
| frame 13 | 94.6 | **6.80** | 0.73 |
| frame 32 | 91.8 | **8.25** | 0.92 |
| frame 14 | 92.1 | 6.11 | **1.68** |

Frame 38 is the brightest frame in the set and its high-frequency energy is
**dead average**. The frame the whole document calls "the flash", and from
which the 92.2 -> 112.9 / 24.2 -> 29.4 table is taken, is not the hatched one.
Its std of 22.7 is the highest in the set and that is large-scale contrast, not
stipple; std cannot tell the two apart and HF energy can. Looking at the tiles
side by side agrees with the numbers: 4, 8 and 32 are visibly hatched and 38 is
a bright, comparatively smooth plank.

So the rates are:

    deck, left-deck crop      stipple  4 / 40 = 10.0 per 100   (12.5 at k=2)
                              bright   1 / 40 =  2.5 per 100
    town, ground crop         stipple  7 / 50 = 14.0 per 100
                              bright   0 / 50 =  0.0 per 100

**Two independent scenes agree on roughly 10-14 stipple frames per hundred,
four to six times the "one frame in forty" recorded above.** And the direction
reversal is now a measurement rather than a report: the deck's four strong
frames all hatch on the anti-diagonal (d1/d2 0.50-0.92) and frame 14 hatches on
the main diagonal (1.68); the town set carries both directions above the bar.

A note on the town capture, because it changes what an earlier negative means.
Over the **whole** mosaic tile the town frames look static -- per-tile mean
spans 55.2-59.1 and the largest consecutive-frame difference is 3.6 grey
levels against the deck's 22.1. The artifact is there, but it occupies a small
part of the tile, and only a region-restricted measurement finds it. Any
future null from a whole-frame statistic on this defect should be assumed to be
that effect until the region is named.

### Objection 2 is CONFIRMED: 2048 is fitted, and the corpus refutes it

Stage 0 carries `matrix_enable = false` with row 0 `[1, ...]` on all 167
stage-1 draws, so stage-0 coordinates are the mesh's own UVs. `stage0_width`
base texels and `scale * stage1_width` detail texels therefore span the same
UV unit, and their ratio is detail texels per base texel:

| rule | value | draws |
|---|---|---|
| `scale * stage1_width` | 2048 | 166 |
| | **1024** | **1** |
| `scale * stage1_width / stage0_width` | **8.000** | **167** |

**Draw 92 is the only draw in the corpus whose stage-0 texture is 128 wide**
rather than 256 -- 166 of 167 use a 256x256 BC1 base. It is therefore the only
observation capable of separating the two rules, and it separates them against
2048. The second rule has no exception at all, and it is the more natural
reading of a *detail* texture: density fixed relative to the base map, which is
what "detail" means. 2048 is that rule specialised to the base texture the
other 166 draws happen to carry.

`check_diag_invariants.py` now gates on the rule with no exception and reports
the fitted one as an observation, because a gate must not fail on the single
draw that distinguishes them. Baseline: **167 checked, 0 violating.**

And the visual claim pointed at the wrong stage anyway. "Visibly coarser stone
blocks" is the **base** texture's block size; stage 0 is 128 wide on that draw
and 256 elsewhere, which is a legitimate property of the material -- 41 draws
in the corpus bind a 128x128 BC1 at stage 0. Stage 1 at scale 8 over a 128
texture puts 1024 detail texels across a UV unit, far finer than block scale,
so it cannot make blocks coarser whatever value it holds.

### Objection 1 is CONFIRMED and generalises to the whole corpus

The line references above are stale -- `draw.c:6050` is the *clear* log, not
the draw log, and `SET_TEXTURE_MATRIX` is nowhere near `pgraph.c:3130`. Cite
the symbol rather than the line here; `vk/draw.c` moved by 53 lines between
`b958a64146` and `5c52049f66` alone. The conclusion survives three times over,
and each reason covers **every draw in every capture** rather than draw 92:

1. **`g_xemu_draw_merge` is `false` by default**, in three places: the static
   in `vk/draw.c` (`static bool g_xemu_draw_merge = false`), the Kotlin
   default in `SettingsActivity.kt`, and the
   `GetPrefBool(..., "draw_merge", false)` in `xemu_android.cpp`. The queue
   is an opt-in setting. Unless it was on for Galleon on that device, no draw
   in any capture went through the queue. `draw.c:4520` says the same about
   both switches in a different context ("Both switches are off by default").
2. **A merged draw is never logged.** `nv2a_diag_log_draw_call` is called from
   inside `pgraph_vk_flush_draw`, and the enqueue path reaches `post_draw` by
   `goto`, skipping it. So appearing in the JSON *means* the draw was submitted
   on its own. No logged draw can be a merge victim, by construction.
3. **A capture cannot merge anything anyway.** The per-draw surface dump in
   `nv2a_diag_log_draw_call` calls
   `pgraph_vk_finish(pg, VK_FINISH_REASON_SURFACE_DOWN)` before downloading,
   and `pgraph_vk_finish` flushes the queue and sets
   `draw_queue.active = false`. Every draw during a capture therefore starts
   with an inactive queue.

Point 3 is the one worth keeping, because it is not about this candidate. **A
diagnostic capture runs the renderer fully serialised, with a submit-and-wait
after every draw.** Any defect whose mechanism is merging, deferred
submission, a stale binding or a missing barrier is *suppressed while
capturing*. So the claim above that "one capture therefore holds every
hypothesis this investigation has raised" is false: it holds every
**state-value** hypothesis and is blind to the whole submission-ordering class.
That is the same shape as the validation-layer test -- an instrument that
cannot see the mechanism reporting nothing.

### Objection 4 is CONFIRMED, with the numbers

Draw 92's footprint is the set of pixels differing between the framebuffers
before and after it: **102,967 px, 16.8% of the 1280x480 surface**, one solid
wall-shaped region, bbox x[161..684] y[0..244].

    mean luminance inside that footprint, BEFORE draw 92    35.2
    mean luminance inside that footprint, AFTER  draw 92   111.0

The region was near-black. The "before" image contains no wall at all, so the
comparison shows an object appearing, and could not have shown a wall drawn
wrongly under any circumstances. Two neighbouring framebuffers are also
byte-identical to it in both directions (`d90 == d91`, `d92 == d93`), so a
single-draw before/after on this data has less resolution than it appears to.

### Objection 3 is DOWNGRADED

With the rate measured, the frequency argument weakens rather than holds. The
four sessions contain **four guest frames**, not seven: the ten "frames" per
session are capture ticks sharing one or two `frame_number` values, and only
frame 4122 (191 draws, split across two records) looks complete. One anomalous
draw in four frames is 25%, against a measured artifact rate of 10-14% -- those
are compatible, not mismatched. Objection 3 no longer refutes anything. It is
objection 2 that kills the candidate.

And there is a prior question objection 3 skipped: **nothing establishes that
the artifact was on screen during any of the four sessions.** The town capture
earned that check explicitly and passed it; these did not. Nine of roughly 300
per-draw framebuffers survive on disk, all from one frame of one session, so
the rate tool cannot be run over them and no final frame exists to inspect.
Combined with the serialisation in point 3 above -- a capture submits and waits
after every draw, which is not how the artifact was observed -- the corpus
should be treated as an unverified sample until a capture is scored for the
artifact with the frames retained. That is a cheap fix to the capture, not a
cheap fix to the corpus already taken.

### The queue bug is real, and it is still not this

Verified read-only. `SET_TEXTURE_MATRIX` in `pgraph.c` writes
`pg->vsh_constants[NV_IGRAPH_XF_XFCTX_T0MAT + tex*8 + entry/4]` and sets
`vsh_constants_dirty[row]` and `vsh_constants_any_dirty`. It never calls
`pgraph_reg_w`, so it never reaches the `pg->any_reg_gen++` inside
`pgraph_reg_w`, and `check_draw_mergeable`'s `uniforms_changed` compares only
`any_reg_gen`. Nothing in the mergeability set (`shader_state_gen`,
`pipeline_state_gen`, `texture_state_gen`, `vertex_attr_gen`,
`texture_vram_gen`, `primitive_mode`, the dynamic registers) moves on a
texture-matrix write either. **So a transform-constant change between two
otherwise-mergeable draws is invisible to the queue.** Latent, because
`draw_merge` defaults off; a real bug if it is ever defaulted on, and it should
be fixed before that happens rather than after.

One correction to the hint that motivated this line of enquiry: the
threaded-draw snapshot **does** capture the texture matrix.
`pgraph_vk_snapshot_state` in `vk/render_thread.c` copies `vsh_constants`,
`vsh_constants_dirty`, `vsh_constants_any_dirty` and
`texture_matrix_enable`. Whatever audit flagged that field as uncaptured is
stale.

### What is now the cheapest thing that settles it

The driver A/B, unchanged in priority and cheaper than it looked -- with one
correction about the harness. **`driver_ab.sh` cannot be used for Galleon**: it
enumerates a suite's goldens and boots one test disc per test. The reusable
pieces are `~/hakux-work/drv/swap_driver.sh` (three arms, `t30` / `t26` /
`stock`, payloads present on disk for T30 and T26, and it restores T30 on
exit) plus a title soak, which is workload-agnostic.

What was missing was not the swap but the **observable**, because Galleon
cannot be driven identically twice and frames will not compare between arms.
It now exists: the rate above is a per-run figure over tens of frames with a
median/MAD bar computed inside each run, so each arm scores itself and the
comparison is between rates rather than between images.

The registration this supports, with absolutes rather than falls:

    V0 (validity)  arm T30 shows >= 3 stipple frames per 40 in the named
                   region, or the pair is void -- the instrument must be
                   pointing at something before a zero means anything
    A1             arm T26 and arm stock each report their stipple rate; the
                   claim under test is that all three arms land in 5-20 per
                   100, i.e. the artifact does NOT move with the driver
    A2             the brightness class stays at 0-3 per 100 in every arm,
                   and never coincides with a stipple frame

A1 failing -- one driver at zero, or one far above the others -- is the result
that redirects the entire investigation, and it is the only leg here that any
amount of emulator-state logging could not have produced.

Second, and only if the driver is ruled out: log what the GPU received. Note
that the diag file cannot answer this as built. It reads the matrix from
`pg->vsh_constants`, which is the same array the uniform update reads, so the
two agree by construction and a divergence between state and the pushed buffer
is exactly what this instrument cannot see. That measurement needs a read-back
of the descriptor's bound image view and of the uniform buffer contents at
submission, which is a source change and a new territory grant.

## The driver A/B was attempted on the Thor, and V0 failed. Here is what stopped it

Run 2026-09-14 by `lane.galleon77`, ref `c866527e03`, Thor `bdc158a5`.

### The blocker this issue carried was false, and the real one is different

`#77` and this document both recorded the A/B as blocked on device
availability -- "Galleon lives only on the Nova, which is held". That is not
true. `docs/testing/devices.sh titles thor` lists `Galleon (USA).xiso.iso` at
`/storage/388C-68F7/ROMS/xbox`, and `swap_driver.sh` opens
`S=${SERIAL:-ee317437}`, so the Nova serial is a DEFAULT and not a
requirement. The A/B was run on the Thor with `SERIAL=bdc158a5`.

**The real obstacle is the workload, and nothing in the issue had named it.**
The A/B needs the stipple rate on a view of the deck or the town ground. The
founding capture got one by being *driven by hand* to the scene and then
holding still. A soak cannot do that: reaching gameplay needs input, and
injecting input terminates the emulator. So what an unattended Galleon soak
actually renders is the **attract demo** -- Galleon boots to its title screen
and plays a scripted loop of gameplay footage, watermarked `Demo`, cutting
between cliffs, caves, sky, a lit courtyard and `Loading...` cards, with a
static `Please press the START button to begin` title card between passes.

That matters because `galleon_flash_rate.py` sets its outlier bar from the
median and MAD of the frames it is handed, which assumes ONE scene with a
parked camera. Over a loop that cuts between scenes the MAD is set by the
cuts, and the artifact has to clear a bar the cuts raised.

### V0 failed on two corrections to the instrument, not on one reading

Registered gate: a T30 arm must show >= 3 stipple frames per 40 (>= 7.5 per
100) or the pair is void. Measured over 115 sampled frames, 94 of them lit:

    STIPPLE   2 / 94  =  2.1 per 100        against a 7.5 gate
    HF energy median 0.614   MAD 0.153   bar 1.295
    median frame-to-frame motion in the band   8.97 grey levels

against this document's own baseline of **10.0-14.0 per 100** with HF median
4.65 and hatched frames at 6.80-8.96. V0 **FAILS**.

Two instrument errors were found and corrected before believing that, because
a rate this far below the baseline is first a suspicion about the instrument:

**The screencap is an UPSCALE, and HF measured on it is the compositor's.**
The guest renders 640x480 and the display shows it at 1440x1080 -- exactly
2.25x. A 3x3 neighbourhood on the 1920-wide capture spans well under half a
guest pixel, so the statistic is computed across a smooth interpolation ramp
and reads low whatever the guest drew. Resampling to 640x480 before measuring
raised HF median **0.256 -> 0.614** and the capture maximum **0.687 -> 1.937**
on the identical frames. Most of the apparent "the artifact is not here" was
this, and any future screen-based measurement on this device must resample
first.

**A modal dialog is dimming every frame by a measured 0.40.** A persistent
`Use USB for` chooser (`com.odin.settings`) sits over the display, occludes
the central 61% x 44%, and dims everything behind it. The factor is not
estimated: the emulator's own `FPS:` overlay reads **exactly 102** in every
frame of every capture while the navigation bar, which is drawn above the
scrim, reads **255** -- and 255 x 0.40 = 102. It survives `am force-stop
com.odin.settings` (the package respawns and re-shows it) and it is tied to
the USB connection state, so clearing it needs a human to press CANCEL. It
cannot manufacture a difference between arms, because it is identical in all
of them -- but it costs 60% of the signal and hides the middle of the screen,
and it is the first thing to remove before any negative here is believed.

After both corrections the whole capture still tops out at HF 1.94 -- about
1.5 after correcting for the scrim -- against a baseline whose *unhatched*
median is 4.65. The demo simply does not put the stippling surface on screen
at the scale the founding capture did.

### What did come out of it: "cannot be driven identically twice" is false for the demo

This document's argument for a per-arm rate was that "Galleon cannot be driven
identically twice and frames will not compare between arms". That is true of
hand-driven gameplay and **false of the attract demo**, which is scripted and
repeats. Matching the survey's first loop against its second by a descriptor
built only from the display the dialog does not cover -- the dialog is
pixel-identical everywhere and an instrument that matched on it would pair
everything with everything and report beautiful agreement -- gives 10 mutually
nearest scene pairs agreeing on HF to **+0.3% median, p90 +3.3%**.

So a much stronger observable than the rate exists on this workload: *same
scene, different driver, compare the ground texture*, with a within-run floor
of a few per cent. It is the instrument the A/B should use if it is run
unattended again. What it still cannot do is put the deck on screen.

### What would actually unblock the measurement

In increasing order of cost:

1. **Press CANCEL on the Thor's `Use USB for` dialog.** One human action,
   recovers 60% of the signal and the middle of the screen, and every
   screen-based measurement on this device is degraded until it happens.
2. **Drive Galleon to the deck once and leave it parked**, then soak. This is
   the measurement the issue actually specified, and it needs either a human
   or a sanctioned input path -- the evdev route in AGENTS.md's device table
   exists precisely because `input keyevent` terminates the emulator.
3. **A marker-file-armed frame dump**, the way `apu.c` arms the PCM capture.
   There is no unattended frame capture today: `nv2a_dbg_trigger_diag_frames`
   is reachable only from a JNI method bound to the Debug Capture button,
   there is no intent extra and no marker file, and `LauncherActivity` reads
   only `rom_path`. It would also have to dump WITHOUT the per-draw
   `pgraph_vk_finish` a diag capture does, or it inherits that capture's
   blindness to merging and barriers.
