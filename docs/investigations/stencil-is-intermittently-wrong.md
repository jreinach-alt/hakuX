# Stencil is intermittently *wrong*, not intermittently *measured*

Eight runs of the same 4-suite disc on the Thor — four per binary, two binaries
differing only in `target/i386/tcg/fpu_helper.c`. 16 Stencil captures each,
128 observations, compared **byte for byte** and against the goldens.

## The correction this makes to #79

#79 was filed as `disposition = "harness"`: nine of sixteen captures varying
between runs, therefore an untrustworthy observable. That was right about the
variance and **wrong about the kind of thing it is**.

> **For every one of the nine unstable captures, the majority image is the
> golden-exact one, and the outliers are wrong.**

The emulator renders these correctly most of the time and incorrectly some of
the time. That is a **defect**, intermittently expressed — not a measurement
artifact. The disposition is now `defect`.

| capture | exact in | wrong in |
|---|---|---|
| `Stencil_REPLACE_DT` | A1 A2 A3 A4 B2 B4 | B1 (40,000) B3 (5,100) |
| `Stencil_REPLACE_ST` | A1 A2 A3 A4 B1 B2 B4 | B3 (5,050) |
| `Stencil_REPLACE_ST_DT` | A1 A2 A3 A4 B1 B3 B4 | B2 (30,000) |
| `Stencil_REPLACE_ST_ZB` | A1 A2 A3 A4 B1 B2 B4 | B3 (5,050) |
| `Stencil_ZERO` | A2 A3 A4 B1 B2 B3 B4 | A1 (5,000) |
| `Stencil_ZERO_ST` | A2 A3 A4 B1 B3 B4 | A1, B2 (30,000) |
| `Stencil_ZERO_ST_DT` | A3 A4 B1 B2 B3 | A1, A2, B4 (30,000) |
| `Stencil_ZERO_ST_DT_ZB` | A3 A4 B1 B2 B3 B4 | A1, A2 (30,000) |
| `Stencil_ZERO_ST_ZB` | A2 A3 A4 B1 B2 B3 B4 | A1 (30,000) |

11 wrong observations in 128 — about **8.6% of Stencil captures per run**,
scattered across both binaries. The other seven captures are byte-identical in
all eight runs and match their goldens.

## The failures are not noise-shaped

Nothing is dithered, speckled or partial. **Every deviation is a single whole
region changing from exactly one colour to exactly one other colour**, and
every region is the same quad or a concentric part of it:

```
capture                  run  px      bbox                    change
Stencil_REPLACE_DT       B1   40,000  x220..419 y140..339  (255,0,0) -> (0,255,0)
Stencil_REPLACE_DT       B3    5,100  x220..419 y140..339  (255,0,0) -> (0,0,0)
Stencil_REPLACE_ST       B3    5,050  x270..369 y190..289  (0,255,0) -> (255,0,0)
Stencil_REPLACE_ST_DT    B2   30,000  x220..419 y140..339  (255,0,0) -> (0,0,0)
Stencil_REPLACE_ST_ZB    B3    5,050  x270..369 y190..289  (255,255,1) -> (255,255,0)
Stencil_ZERO             A1    5,000  x220..417 y140..189  (255,0,0) -> (0,0,0)
Stencil_ZERO_ST          A1   30,000  x220..419 y140..339  (255,0,0) -> (0,255,0)
Stencil_ZERO_ST          B2   30,000  x220..419 y140..339  (255,0,0) -> (0,0,0)
Stencil_ZERO_ST_DT       A1   30,000  x220..419 y140..339  (255,0,0) -> (0,255,0)
Stencil_ZERO_ST_DT       B4   30,000  x220..419 y140..339  (255,0,0) -> (0,0,0)
Stencil_ZERO_ST_DT_ZB    A1   30,000  x220..419 y140..339  (255,255,255) -> (255,255,0)
Stencil_ZERO_ST_ZB       A1   30,000  x220..419 y140..339  (255,255,255) -> (255,255,0)
```

Three things follow directly:

1. **Red ↔ green is a pass/fail indicator flipping.** These tests paint the
   region one colour when the stencil comparison passes and another when it
   fails. A whole region swapping between them means the **comparison's result
   changed**, not that some pixels were shaded differently.

2. **The `_ZB` case reads the stencil value itself and it is off by one.**
   In the `_ZB` packing, z24 is `A<<16 | R<<8 | G` and the **stencil byte is
   B**. `Stencil_REPLACE_ST_ZB` goes `(255,255,1) -> (255,255,0)`: depth
   identical, stencil **1 in the correct image and 0 in the wrong one**. That
   is a direct read of the stencil buffer holding a different value, over
   5,050 px, with nothing else on the pixel changed.

3. **The affected area is quantised, not ragged.** 40,000 px is the whole
   200×200 quad; 30,000 is 200×150, exactly three quarters of it; 5,050 and
   5,100 are the 100×100 inner square plus a one- or two-row band; 5,000 is a
   198×50 strip. Region boundaries, not pixel scatter.

## What this is consistent with, and what is not established

Consistent with **the stencil buffer's contents at test time depending on
work that is not ordered against the draw that reads it** — a clear, or a
previous test's writes, landing or not landing before the comparison. The
whole-region granularity and the literal off-by-one stencil value both fit;
speckle would not.

Adjacent, and possibly the same family: the remote lane measured
`Surface_pitch::Swizzle` varying by up to 2,341 px between runs while scoring
14,848 every time, because four arms share one texture buffer and
`Pushbuffer::End()` does not wait for the GPU, so the guest rewrites the buffer
while a draw is queued. Both renderers read `d->vram_ptr + texture_vram_offset`
at draw time.

**Not established:**

- The site. No code has been read for this; the mechanism above is a shape the
  evidence fits, not a diagnosis.
- Any run-order rule. A1 carries five of the eleven and A3/A4 carry none, which
  invites a cold-start story — but B3 carries three and is a second run, so
  there is no clean first-run pattern and I am not claiming one.
- Device or renderer scope. Thor only, Vulkan only. The Nova is held.
- Whether it reaches titles. Every observation here is the test disc.

## What it has already cost

- **#75** was filed as a live ~100,652 px Stencil regression, with a suspect
  commit named and a bisect lane spawned. It was noise of exactly this kind,
  closed as a duplicate after 13 runs. `sweep_diff.py` came out of that; the
  mechanism did not.
- A `must_not_move = ["Stencil/*"]` control on the #67 arm failed on six
  captures and I first read it as the fix reaching further than argued — a
  wrong conclusion in the flattering direction.
- The #67 v2 arm, which passed 121 of 122 checks, was taken to FAIL by a
  global `worse = 0` leg that a single wrong Stencil capture broke.

## Consequence for everyone else

No Stencil number from a single run means anything, and `Stencil/*` must not
be used as a `must_not_move` control until this is fixed. A Stencil claim needs
**four runs minimum**, and should be made on the *majority* image with the
outlier count reported alongside.

---

## RESOLVED to a mechanism, 2026-09-14

The "Not established" list above named the site as unknown and offered a shape
for the mechanism. Both are now settled, and the shape was wrong in its second
half: **no clear is lost and no zeta surface races.** The stencil buffer's
contents differ because the *vertex array the draw reads* is rewritten by the
guest while PGRAPH is still behind — [#44's guest↔pgraph
skew](guest-pgraph-skew.md), on vertex data instead of texture data.

The wrongly drawn regions are TRIANGLES, halves of the `DefineBiTri` quads,
including one whose shared `ul` vertex carries `x` from the 100x100 quad and
`y` from the 200x200 one. Measured: with `XEMU_OPT_FIFO_SKEW_BOUND` at 1 the
flake goes from **7 wrong (run, capture) observations of 64 to 0 of 64** over
four runs per arm, with `held(n)/kicks = 1.0000` proving the bound in force.

See [`stencil-is-the-guest-pgraph-skew.md`](stencil-is-the-guest-pgraph-skew.md).
The operational rule in this document is unchanged while the bound is off by
default: no Stencil number from a single run means anything, and `Stencil/*`
must not be a `must_not_move` control.
