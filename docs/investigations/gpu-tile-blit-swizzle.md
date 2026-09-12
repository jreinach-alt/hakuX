# The GPU tile address swizzle, and `Image_blit::BlitBeyondWidth` (#33)

`BlitBeyondWidth` has sat at **284,628 differing pixels, max channel delta
155** in every run since 2026-09-07, and it did not move when #7's overlap fix
landed nor when #47's clip rectangle landed. This note records the mechanism,
the layout solved out of the golden, the parts that are measured versus
assumed, and the mechanisms measured dead.

## The capture is current for this test

`res_imgblt` is dated 2026-09-12 03:42, the goldens 2026-09-09 20:34, and
#47's clip fix (`983617ebef`) landed later on the 12th — so the capture set
predates the clip fix and its seven `Clip_*` frames are stale. For
`BlitBeyondWidth` it is not stale: scoring the on-disk capture against the
golden reproduces **284,628 / max 155 / 2,136 off-by-one**, identical to
`docs/testing/sb/today/run-2026-09-12-image-blit-clip.tsv`, which was taken
*after* the clip fix. Same numbers also in the 09-07, 09-08 and 09-10 runs.
The test is untouched by both earlier fixes, and the capture is usable.

## What the test does

`ImageBlitTests::TestBlitPastWidth`:

1. Generates a 1024x512 RGB ramp in texture memory (`GenerateRGBTestPattern`).
2. Allocates a 640x480x4 target plus a 4096-byte guard, 0x4000-aligned, and
   registers it as **GPU tile 0** with pitch 2560 and size 1,228,800
   (`pb_assign_tile(0, ..., 2560, 0, 0, 1)` — note the trailing `1`).
3. Blits the **1024x512** source into it with dest pitch 2560 — a destination
   both narrower and shorter than the source. Hardware clips the write at the
   tile limit; a guard word proves it.
4. Blits 256x256 to an untiled address, showing that without a tile there is no
   overdraw protection.
5. Restores the framebuffer tile — with `pb_assign_tile(..., 0)`, flags zero,
   which the test comments as "intentionally incorrect to match pbkit".
6. Blits 640x480 from `target_buffer + 4096` to the backbuffer so there is
   something to photograph.

Its own on-screen text says what to expect: *"Displayed image is a tile offset
by 4096 bytes"*, *"Image is tile-swizzled"*, *"Final pixels will be
0xCCCCCCCC from guard"*.

## Root cause (measured)

The geometry and the clipping are already right. What differs is *where inside
the tile each byte lands*.

A GPU tile is a memory-controller remap: addresses inside a tiled region are
shuffled so that a rectangle of the surface is contiguous. Every consumer —
scanout, texture fetch, the CPU aperture — goes through the same remap, so the
shuffle cancels and treating tiled memory as linear (what we do everywhere)
gives the right answer. It stops cancelling here, because step 5 removes the
tile before step 6 reads the data back: the write is remapped and the read is
not.

Two things were measured, not argued:

- **Our renderer produces exactly the linear blit.** A linear model of steps
  3 and 6 reproduces our capture at **0 differing pixels** over the whole
  307,200-pixel frame except 21,218 pixels of on-screen text, which the model
  does not draw. Nothing else in our path is wrong.
- **The golden is the same bytes, permuted.** 284,958 of 307,200 golden pixels
  satisfy the ramp's `R + B == 255` invariant, i.e. they are ramp pixels in the
  wrong place. A 64-word signature match against the source pinned the
  permutation exactly (all 4,800 candidate logical blocks have unique
  signatures, so the matches are unambiguous).

### The layout

For a logical byte offset `off` within a tile of pitch `P` (a multiple of 256):

```
row  = off / P;        col  = off % P
band = row / 16        unit = (col / 256) ^ 1 ^ (band & 1)
group = (row % 16) / 4                      /* 4-row group inside the unit */
column = (col % 256) / 64                   /* 64-byte column inside it    */
line = row % 4
chunk = ((col % 64) / 16 + 4 - rot[group]) % 4,   rot = { 0, 2, 3, 1 }

phys = (band * (P/256) + unit) * 4096
     + group * 1024 + column * 256 + line * 64 + chunk * 16 + (col % 16)
```

So: a 4096-byte unit is 256 bytes wide by 16 rows; a band is 16 rows holding
`P/256` units; vertically adjacent units swap halves of a unit pair (the XOR,
the usual bank-conflict trick); and within each 64-byte row fragment the four
16-byte chunks are rotated by an amount fixed by the 4-row group.

**Validation.** The map is a bijection on `[0, 1228800)` at pitch 2560
(verified exhaustively). Replaying the test through it — the emulator's own
`row_pixels`, `adjusted_height` and tile clip, then the actual 16-byte-chunked
copy loop that landed in `blit.c` — reproduces the golden at **0 differing
pixels** outside the text overlay. Inside the text overlay our capture already
equals the golden, so the predicted post-fix score is **0**.

### Measured vs assumed

Measured: the whole layout above, including the `rot` table and the XOR, at
pitch 2560, tile base 16KB-aligned, 4 bytes per pixel. `XOR 3` and `XOR 1`
alternatives for `rot[2]`/`rot[3]` were tested and excluded.

Assumed, and untestable from the corpus:

- That `NV_PFB_TILE_PITCH` holds the pitch in bytes. The code prefers it and
  falls back to the blit's own dest pitch if it is zero or not a multiple of
  256. In this test the two are both 2560, so the capture cannot distinguish
  them.
- The `^ 1` constant in the unit column. It may be a genuine constant, or a bit
  of the tile base address that happens to be set here. Only one test in the
  corpus registers a valid tile, so there is no second pitch or base to check
  it against.
- That the layout generalises to other pitches, bases, and pixel sizes.

## Mechanisms ruled out

- **The row-width clamp.** `row_pixels = MIN(MIN(source_pitch, dest_pitch) /
  bpp, width)` clamps a 1024-pixel row to 640, where hardware writes all 1024
  and overruns into the next row. This *looks* like the whole bug given the
  test's name, and it is not: each row's overrun is overwritten by the next
  row, and the last row's is clipped at the tile limit. Modelling the copy with
  width 1024 and with width 640 gives **byte-identical** results. The clamp is
  left alone.
- **Tile clipping being absent.** #33's earlier comment says the emulator reads
  `NV_PFB_TILE` "for the address-tiling map, not for clipping 2D engine
  writes". It is the other way round: `nv_clip_gpu_tile_blit` has clipped blits
  at tile limits since `24087af22a`, and it is the *address map* that is
  missing. The clip is provably already correct here — the golden's content is
  exactly 480 destination rows, which is what our clip produces.
- **Blit geometry.** Colour edges land on identical x positions in both
  frames — but that observation is degenerate, it holds for any permutation
  that preserves 16-pixel runs, so it should not be used as evidence either
  way. Compare regions.

## Why no other capture changes

The swizzle is taken only when a tile with the **VALID** flag covers the
destination. pbkit registers the framebuffer's tile with flags zero — that is
what the test's "intentionally incorrect to match pbkit" comment is about — so
no other blit in the suite finds a valid tile. Corroboration rather than proof:
if the framebuffer tile were valid, `nv_clip_gpu_tile_blit` would already be
clipping full-screen blits to the back buffer at that tile's limit, and the
`SRCCOPY`, `BLENDAND` and `Clip_*` captures would not be bit-exact today.

## The boundary, and what is deliberately not done

Only the blit **destination** is remapped. That is enough for this test and it
is the whole of what the corpus can validate, but it is not self-consistency:

- A blit that *reads* out of a live tile is not un-swizzled. No capture
  exercises it, and an unverified inverse is a second bug waiting; left for
  whoever has a test for it.
- 3D renders and scanout still treat tiled memory as linear. A title that
  blits into a tile it has registered as valid and then scans that out would
  now see a scrambled result, where before it saw a correct one. The complete
  fix is a remap at the memory controller, applied to every access — which is
  well outside `blit.c`. **This is the thing to watch in a game smoke test.**
  If it bites, the narrow options are to gate the swizzle on the destination
  not being a bound render surface, or to revert to linear and accept #33.
