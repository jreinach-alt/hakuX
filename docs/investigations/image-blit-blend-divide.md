# `Image_blit`'s one-step error is a scale error, not a rounding mode

Lane `lane.blit38`, 2026-09-14. Files `hw/xbox/nv2a/pgraph/vk/blit.c`,
`hw/xbox/nv2a/pgraph/pgraph.c`. Fix `24a75d6e3c`, prediction `a41068feca`.

**Settled with zero device time.** Everything here came from goldens and
capture sets already on disk plus one cross-compile. The device runs queued
afterwards are confirmation, not derivation.

## What was on the board

`docs/investigations/depth-buffer-is-four-defects.md:150-176` recorded that the
corpus-wide one-step colour error is *not* a single rounding mode — conditioning
on differing pixels manufactured a false one-sidedness, and unconditioned the
`Depth_buffer` cells split +0.03. But one row survived that correction:
`Image_blit` at **−0.70** over 515,562 one-step pixels, 85% ours-low, in "a
suite nobody has looked at".

## The signal is stronger than the record said

That `score_cv_blit` set predates both #33's tile-swizzle fix and the blit clip
fix, so its one-step population was diluted by `BlitBeyondWidth`'s structural
residual and seven broken clip captures. Re-measured at `c866527e03`
(`z-repeat-c866527e03-036-Image_blit`, three runs at two refs, all
bit-identical at 168,245 px):

| | channels |
|---|---:|
| ours +1 | **0** |
| ours −1 | **234,506** |
| \|delta\| > 1 | **0** |
| alpha differing | **0** |

Not −0.70. **−1.00, no exceptions.** A defect with no counterexamples at all is
a much easier thing to model than one with 15% of them, and the 15% was an
artefact of two other defects that had since been fixed.

**So: re-date a directional figure before you model it.** The bias was measured
on a capture set that two later commits had invalidated, and the residue those
commits left behind was the only thing making the signal look noisy.

## The mechanism

`perform_blit`'s BLEND_AND path forms `V = src*beta + dst*(0x7f80 - beta)` and
must divide by `max_beta_mult`, which is `0x7f80` = 32640. Two paths, two
defects, same direction:

- **NEON (aarch64, so: the device).** It substituted `>> 15` for the divide,
  with a comment claiming "Error is < 1 LSB for typical values". 32768 is 0.39%
  larger than 32640, so the result can only ever land *low*.
- **Scalar (the width tail, and the whole path on desktop).** `(a + b) / max`
  truncates. Silicon rounds to nearest.

Neither is a rounding *mode* difference. A mode difference is roughly
symmetric, which is exactly what the corpus-wide population turned out to be.
This is a scale error, and a scale error has a sign.

## How the hardware model was derived rather than fitted

The suite hands you its own inputs, which is why this needed no device:

- the four **beta==0** captures (`0x00000000`, `0x007FFFFF`, and the two
  negative ones, all masking to zero) leave the destination untouched, and are
  bit-exact — so they *are* the blit's destination image;
- the three **SRCCOPY** captures are a `memmove` and are bit-exact — so they
  are the blit's source image.

With `src` and `dst` in hand every BLEND_AND golden is predictable offline. Over
the blit rect (y 75-303, x 80-383):

| model | vs golden (hardware) | vs our own captures |
|---|---:|---:|
| `(V) / 0x7f80` truncating | 173,410 | 175,561 |
| `(V + 0x3fc0) / 0x7f80` round | **1,830** | 112,389 |
| `(V + 0x3fc0) >> 15` (shipped) | 112,389 | **1,830** |

**The two 1,830s are the same 1,830 channels**, 100% overlapping, confined to
rows 75-90 — the guest's own per-test label text, which differs between tests
and so is the one thing my reconstructed `src` gets wrong. That identity is the
control: if either model were wrong the two residuals would differ. Replicated
independently on the other surface format (`Z8R8G8B8`, using its own beta==0
and SRCCOPY captures) with the two columns agreeing to the digit in all six
cells.

## The fix, and how it was checked before the device saw it

`0x7f80 == 255 << 7`, and `floor(floor(x/128)/255) == floor(x/32640)`, so the
NEON helper shifts the 128 out first and divides the sub-2^16 remainder by 255
exactly with `(W * 0x8081) >> 23`.

That helper was compiled for aarch64 with NDK clang and the **real instructions
run under `qemu-aarch64`** over every one of the 2^24 `(src, dst, beta)`
triples:

    checked        : 16777216
    NEW mismatches : 0
    OLD differed   : 8388608  (low 8388608 / high 0)

So the old form is low-by-one on exactly half the domain and high on none —
which is the sign signature the suite shows — and the new one is exact
everywhere. A NEON intrinsic bug is otherwise invisible until the device run,
and `qemu-aarch64-static` plus the NDK compiler is already on this box.

## What this instrument cannot see

**No triple in the whole 2^24 domain produces an exact half-tie.** So this data
cannot distinguish round-half-up from round-half-even, and "round to nearest" is
all that is established. Anything later needing the tie-break rule must get it
elsewhere.

## Two things closed, one thing opened

**`ImgBlt_Clip_*` is fixed.** `issue-19-isolation-2026-09-12.md:42,64` records
six of six clip captures rendering the *unclipped* image. All seven now read
zero. Checked that the goldens can actually see a clip before believing that:
all 21 golden pairs differ, the tightest (`320_240_0_0` vs `320_240_1_1`) by
**81 px**. The suite discriminates and we agree with it.

**`BlitBeyondWidth` is zero**, confirming #33's swizzle fix holds at this ref.

**Eight pixels are left, and they are not this.** The eight
`Overlap_*_{Inside,Outside}` captures are 1 px each, all ours-low-by-one, on the
**SRCCOPY** path (`image_blit_tests.cpp:708`) — a `memmove`, with no arithmetic
to round. This fix provably cannot reach them and they are registered as a
must-not-move control. A boundary/inclusivity question, wanting its own row.

**And `hw/xbox/nv2a/pgraph/gl/blit.c:49` carries the same truncating divide**,
unfixed because it is not this lane's file. Raised in
`$DISPATCH_DIR/board-requests/blit38.md`.

## A negative worth keeping: `pgraph.c`'s beta mask is already right

The other half of this lane's territory is `NV012_SET_BETA`'s handling at
`pgraph.c:1943-1951`, which masks the parameter with `0x7f800000` and clamps a
negative value to zero — "only 8 fractional bits are actually implemented in
hardware", per its own comment. That comment was worth checking rather than
trusting, because if the extraction were wrong the blend would have been the
wrong *input*, not the wrong arithmetic, and the divide would have been a
plausible-looking fix for someone else's defect.

The suite checks it for free: it deliberately includes parameter pairs that
must collapse to the same beta. Comparing **golden against golden**, inside the
blit rect:

| pair | what it tests | differing px |
|---|---|---:|
| `0x00800000` / `0x00D00000` | both mask to byte 1 | **0** |
| `0x44400000` / `0x444FFFFF` | low 23 bits dropped | **0** |
| `0x7F800000` / `0x7FFFFFFF` | both mask to byte 255 | **0** |
| `0x00000000` / `0x007FFFFF` | both mask to byte 0 | **0** |
| `0x00000000` / `0x80000000` | bit 31 clamps to zero | **0** |
| `0x00000000` / `0x8FFFFFFF` | bit 31 clamps regardless of the rest | **0** |

Six of six. Silicon really does implement eight fractional bits and really does
clamp negatives, so the mask needs no change and **no edit was made to
`pgraph.c`**. Note this is a claim about the *goldens*, not about us: it is
hardware compared with hardware, so it holds whatever this emulator does.

Restricting to the blit rect matters — every one of those pairs differs by 6 to
314 px over the whole frame, and all of it is the guest printing the test's own
parameter string into the picture. Read whole-frame, four of the six pairs look
like real disagreements.
