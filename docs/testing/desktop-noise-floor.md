# The desktop lane's run-to-run noise floor is one capture wide

Measured 2026-09-13: **five runs of one unchanged binary** over the 236
captures of `iso_surf1` under `renderer = 'OPENGL'`.

**235 of 236 captures are bit-reproducible across all five runs.** Exactly
one is not:

| capture | run 1 | 2 | 3 | 4 | 5 | band |
|---|---:|---:|---:|---:|---:|---|
| `Surface_pitch::Swizzle` | 15,360 | 14,848 | 15,360 | 15,360 | 15,360 | **14,848–15,360, spread 512** |

Every other capture hashes identically run to run. So a delta of ±512 on
`Surface_pitch::Swizzle` alone is a coin flip and must be classed NOISE, not
better or worse; a delta anywhere else, of any size, is signal.

## Why this needed measuring

The capture moved in four consecutive arms on 2026-09-13 — the #70 clip
fix, two of #60's arms, and the `noperspective` probe — always by exactly
512 and always between those two values. Four unrelated changes producing
the same ±512 on one capture is not four findings, and taking it at face
value cost three misreported results before the re-run of one binary
settled it. `ab_compare.py`'s own docstring had warned about exactly this
("a delta inside the run-to-run band is a coin flip"), from the device
lane; it was not known that the desktop lane had a band at all, because
until #66 the OpenGL disc had never run to completion for anyone to
re-run.

## What it corrects

* **#70**: reported 9 captures better. It is **8 better**;
  `Surface_pitch::Swizzle` 15,360 → 14,848 was noise. The registered legs
  did not name it and are unaffected.
* **#72** (`noperspective` probe): reported 6 better and 1 worse, with one
  registered leg failed. It is **6 better, 0 worse**, and the leg holds.
* **#60**: reported 4 captures regressed. It is **3**. The two control arms
  that refuse the `A8R8G8B8` surface-to-texture row landed
  `Surface_pitch::Swizzle` at 12,224 and 10,176 — both far outside the
  band, so those findings and #71 stand, but their deltas carry a ±512
  uncertainty from the baseline.
* **The GL blit range download**: reported 8 better and 1 worse. It is
  **8 better, 0 worse**.

## The instability is in the run, not in that capture

Measured after the band was: a build instrumented to log every surface
create, hit, upload, download and overlap-eviction, run three times
unchanged. The three runs produced **376,336 / 372,485 / 375,927 events**,
diverging first at event 25,867 — where one run carries a block of extra
`UPLD ... pending=0 -> skip` and `DNLD` pairs the others do not.

So the **surface event stream is non-deterministic run to run**, and it is
non-deterministic even on runs whose captures all agree (all three scored
`Surface_pitch::Swizzle` at 15,360). The extra events are no-ops — repeated
update calls that find nothing dirty — so what varies is how many times the
guest gets round the loop, i.e. the interleaving of the CPU thread and the
pgraph thread. That is inherent to a free-running guest and is mostly
harmless.

It stops being harmless where the interleaving decides whether a real
download lands before a read. That is what `Surface_pitch::Swizzle` is
sensitive to: diffing two runs of one binary, 8,192 px differ across 80 rows
of 256 columns, and the differences are whole blocks — one run shows
`#FFFFFF` where the other shows `#7722FF`, the run with more real colour
scoring closer to the golden. Data that sometimes arrives and sometimes does
not, not a numeric race.

**The corollary matters for every A/B on this disc.** "235 of 236
bit-reproducible" is an observation over five runs, not a guarantee. The
mechanism that flips one capture is present in every run; what makes the
other 235 stable is that nothing they measure depends on the ordering, not
that the ordering is fixed. A capture that starts moving after a change to
the surface or texture paths should be re-run before it is believed, in
either direction.

## How to use it

Class a move on `Surface_pitch::Swizzle` of **|2,200| or less** as NOISE
under OpenGL -- the 512 in the first table was five samples, and a later
three produced 2,200. Under Vulkan this capture was byte-stable over five
runs, so treat any move there as signal until it is re-measured. Do not
class a move on any other capture as noise without re-measuring: the band
is per capture and per renderer, and on this lane every other capture's
band is zero.

The right fix is to find out why that one capture is unstable, which is
worth doing -- a non-deterministic capture is a defect in its own right, and
this one is in `Surface_pitch`, a suite of one. Until then this file is the
band.

## The band is wider than 512, and it is GL-only

Re-measured 2026-09-13, later the same day, on the two-test disc
(`Surface_pitch::Swizzle` + `Pixel_shader::Passthru`) with an unmodified
binary:

| renderer | runs | scores | capture digests |
|---|---:|---|---|
| OpenGL | 3 | 15,360 / 14,848 / **13,160** | three distinct |
| Vulkan | 5 | 10,240 x5 | **one digest, `15845fa9e1e40032`** |

Two things change.

**The GL band is at least 13,160-15,360, spread 2,200** -- over four times
the 512 recorded above. The 512 in the table was five samples of a
distribution with a long tail, not the tail. Treat 512 as the *observed
minimum* move, not the maximum.

**Vulkan was byte-stable across five runs of the same disc** while GL was
three-way distinct across three. The hazard is the same in both renderers
(both read `d->vram_ptr + texture_vram_offset` when pgraph reaches the draw,
not when the guest submitted it), so this is not "Vulkan is correct" --
Vulkan scores 10,240, so it loses the same race, just *reproducibly*. It is
"the band is a property of the renderer's pacing, and must be measured per
renderer."

### What this corrects, again

The #71 filter-cache fix was reported with two arms at **12,224 and 10,176**
called "outside the band". Against a 2,200-wide band with a floor of 13,160:

* **10,176 is still outside** it, by 2,984.
* **12,224 is not safely outside** it any more -- 936 below the observed
  floor, well inside a 2,200 spread. That arm should not be cited as
  evidence on its own.

The fix itself is unaffected, because its evidence was never the scores: it
was **8 captures going byte-identical to the golden** and GL's bit-exact
count moving 102 -> 108 to match Vulkan's. Byte counts are not samples from
this distribution. But the two score arms were quoted as corroboration and
one of them no longer corroborates.

The general rule this keeps re-teaching: on this capture, compare bytes.
`docs/testing/sweep_agreement.py` exists for that and does not use scores.

## Answered: why this one capture is unstable

Measured since, and written up in
[`../investigations/gl-surface-to-texture-is-wrong.md`](../investigations/gl-surface-to-texture-is-wrong.md).

`Surface_pitch::Swizzle` draws four inner quads through **one** texture
buffer at `0272b000`, rewriting it from the CPU between draws.
`Pushbuffer::End()` does not wait for the GPU, so the guest overwrites that
buffer while the previous draw is still queued. pgraph reads texture memory
when it reaches the draw, not when the draw was submitted, so it sees
whichever version happens to be there. Instrumented, arm 2's read came back
with **three** distinct dwords -- arm 4's colour, black, and arm 1's colour
in one buffer, i.e. read mid-`swizzle_rect()` -- and two hashes of the same
pointer and length taken a few lines apart in one `pgraph_gl_bind_textures()`
call disagreed.

Three runs of one unchanged binary scored 12,800 each but produced three
byte-distinct captures, differing only in one result quad and only by
swapping arm 3's `#2222FF` for arm 4's `#7722FF`.

So the band in this file is not measurement slop: it is one CPU/GPU
memory-ordering hazard with a known mechanism. That does not change how to
use the band -- |512| or less on this capture is still NOISE, and the
instability is still real -- but it does mean the band will not shrink until
that hazard is addressed, and that a change to the surface or texture paths
cannot be credited or blamed for a move inside it.
