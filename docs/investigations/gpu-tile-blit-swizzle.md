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

## Measured on device: the swizzle, then the regression it caused

A/B on the Nova, 97 captures per arm, `progress_log_proof` true on both, same
disc, only the swizzle commit differing (baseline `b5ed87489c`, fix
`d42a8d79bc`):

```
compared 97   better 1   worse 1   same 95

  Image_blit::BlitBeyondWidth              284,628 ->      0   (-284,628)
  Texture_Framebuffer_Blit::FBToZetaAsTex   14,383 -> 34,382   (+19,999)
```

`BlitBeyondWidth` went to **0, bit-identical**, as predicted — the layout above
is right, on hardware, to the byte.

The regression is the read path this note had already flagged as the thing to
watch, and it corrects one claim made here earlier. "pbkit registers the
framebuffer's tile with flags zero" is true of the **colour** tile only.
`Texture_Framebuffer_Blit::FBToZetaAsTex` blits the framebuffer over
`pb_depth_stencil_buffer()`, and the **depth** tile *is* registered valid. The
test then samples that buffer as a texture (`NV097_SET_TEXTURE_OFFSET`), and a
texture fetch in this emulator is linear. Write swizzled, read linear, +19,999
pixels.

So the earlier statement should have been: no other blit in the *Image blit*
suite finds a valid tile. The sibling suite does, which is why it was in the
regression set.

## The gate, and that it is a restriction rather than a mechanism

The swizzle now applies only to a blit the tile **actually clipped**
(`clipped_dest_size < dest_size`), not to every blit landing in a valid tile.

This is not a claim about hardware. Hardware remaps every write into a tiled
region whether or not it also clips one. It is a claim about *our* consistency:
the remap is invisible while the tile is valid, because every consumer goes
through it and it cancels, and we model tiling nowhere else — so swizzling a
write whose reader is one of our linear paths corrupts it. A blit that overruns
its tile is the one configuration hardware evidence covers and the only one in
the corpus where the guest drops the tile and reads the bytes back afterwards,
which is when the remap stops cancelling.

The gate separates the two captures by arithmetic alone, which is why it was
chosen over a surface-cache test that cannot be checked without running:

| blit | `dest_size` | after tile clip | path |
|---|---:|---:|---|
| `BlitBeyondWidth` #1, 1024x512 into pitch 2560 | 1,312,256 | 1,228,800 | **swizzled** |
| `BlitBeyondWidth` #3, 640x480 out, tile dropped | 1,228,800 | 1,228,800 | linear |
| `FBToZetaAsTex`, 640x480 over zeta | 1,228,800 | 1,228,800 | linear |
| `FBToTexture`, same blit into texture memory | — | — | linear (untiled) |

Only the first blit needs the swizzle, and it is the only one that gets it. The
gate is strictly more restrictive than the measured arm — it can only move a
blit from swizzled to linear — so no capture that was unchanged in the A/B can
move. Replayed through the gate, `BlitBeyondWidth` still reproduces its golden
at 0 differing pixels outside the text overlay.

A surface-cache gate ("destination is not a tracked surface") was the other
candidate and was rejected: it depends on whether a binding happens to exist at
`target_buffer`, a fresh `MmAllocateContiguousMemoryEx` allocation, and a stale
binding left at that address by an earlier test would silently veto the swizzle
and put `BlitBeyondWidth` back to 284,628 with nothing in the code to say why.

`FBToZetaAsTex` differed by **14,383 pixels before any of this work**, for an
unrelated reason. Returning it to 14,383 is the bar; that residual is not
attributable to the tile swizzle in either direction.

## The mechanism-level fix, which is not in blit.c

The gate closes the regression but leaves the model heuristic. The correct fix
is neither the blit write nor the texture read: it is to keep storing tiled
memory **linearly** — so that everything cancels, exactly as hardware does
while a tile is valid — and to permute the covered range **when a tile is
created or torn down**, which is the only moment the remap becomes observable.

Applied to the two captures:

- `FBToZetaAsTex`: the depth tile stays valid throughout, memory stays linear,
  the texture fetch is linear. Correct, with no gate.
- `BlitBeyondWidth`: step 5 reassigns tile 0, so at that instant the 1,228,800
  bytes it covered are permuted into their physical order; the following blit
  reads them linearly and sees the swizzle. Correct, with no gate.

It also removes the standing hazard for real titles, which set their tiles up
properly and would otherwise depend on the clip gate never firing on them.

That work belongs with the tile registers in `pfb.c`, with the permutation
moved next to `nv_clip_gpu_tile_blit` in `nv2a.c` and exported through
`nv2a_int.h` — three files this change does not own, so it is not attempted
here. Two things to settle when it is: the inverse permutation on tile
*creation*, since pre-existing bytes are reinterpreted rather than moved; and
what to do about a surface whose contents are still live in a `VkImage` and not
yet downloaded when the tile is torn down.

Still deliberately not done: a blit that *reads* out of a live tile is not
un-swizzled. No capture exercises it, and the design above removes the need for
it entirely.
