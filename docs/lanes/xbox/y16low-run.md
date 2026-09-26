# #10: does a Y16 bump texel's low byte feed an offset?

**Status: PRE-REGISTERED.** This file, its scorer and the tests patch were
committed and pushed before the emulator dry run and before the console run.

## Why

PR #350 found that #10's own control (`BumpEnvLum_Y16`) is blind, so the rival
PR #187 had called "the only rival with the right magnitude" is not refuted.
That rival: **the bump offset reads the low byte of the filtered 16-bit
value.**
- **How it produces the seam.** Across #10's seam, a byte-replicated pair such
  as 0x5252 and 0x5353 filters to a low byte that sweeps about 200 values
  (0x52 → 0xFF → 0x00 → 0x53), which is the sweep #10 measured.
- **#283's byte order is a variant of it.** Silicon hands a Y16 colour texel
  to the combiner as separate bytes, which would let one offset take the high
  byte and the other the low byte.

The discriminating cut is to change the low bytes and leave the high bytes
alone. The test framework's converter always byte-replicates (Y8 × 257), so
the variants patch the uploaded texels in texture memory.

## What runs

- **The XBE:** nxdk_pgraph_tests `6743b6a` plus
  [`y16lowbyte.patch`](y16lowbyte.patch) (tests branch
  `hakux/bump-y16-lowbyte` `bbb46b6`). sha256 `97d4c61b608b…`, ISO
  `b197a175ef91…`.
- **The variants:** after the normal upload, the patch rewrites the Y16 bump
  texels in texture memory. Each is `BumpMap_Y16`'s unchanged draw at
  m11 = 0.5, where the seam band samples the checkerboard (PR #350):
  - `_patchSame` sets each low byte to its own high byte, which is inert on
    byte-replicated data;
  - `_lo00` sets every low byte to 0x00;
  - `_lo80` sets every low byte to 0x80;
  - `_zero` sets both bytes to 0x00.
- **The console config:** `Alpha func::AlphaFuncAlways_Disabled` first (PR
  #348's rule), then `BumpMap_Y16`, `BumpMap_Y8` and the four variants.
  Shutdown-on-completion off, networking off, progress log on.
- **The dry run:** an emulator dry run of the same selection comes first.

## Legs

Scored by [`y16low_score.py`](y16low_score.py). It was mutation-tested before
this commit on five synthetic cases, including a stale texture (every variant
equal to `BumpMap_Y16`), which Z voids, and a non-inert patch, which C0 voids.

| leg | must hold, or decides | the world in which it fails |
|---|---|---|
| **C1** | `BumpMap_Y16` and `BumpMap_Y8` equal their goldens | The build or the rig moved |
| **C0** | `_patchSame` equals this run's `BumpMap_Y16` | The patch path changes the draw by itself, and nothing below can be attributed |
| **Z** | `_zero` differs from `BumpMap_Y16` by ≥ 10,000 px | The GPU never saw the patched texels (a stale texture cache, say), so every variant would falsely read as unchanged |
| **S** | `BumpMap_Y8`'s seam band has no single-colour rows | The image cannot show a flip (PR #350's lesson) |
| **M** | `_lo00` against `BumpMap_Y8`, scored only if C1, C0, Z and S hold: **HIGH** if ≤ 2,000 px; **LOW** if ≥ 10,000 px; **X** otherwise | — |

**The world each M outcome rules out:**
- **HIGH** rules out every model in which a low byte feeds an offset,
  including #283's split. #10's seam sweep would then need another cause
  inside the full 16-bit value.
- **LOW** rules out every model in which both offsets come from the high byte
  or the full value. Where `_lo00` differs (the whole quad or only the band),
  and how `_lo80` differs from it, say which offset reads the low byte.

**Recorded, not predicted:** `_lo80`, and where each variant's differences
fall.

**hakuX (the dry run):** C0 and Z must hold. Its M is predicted HIGH: it
converts the full value, and 0x5200/65535 is within 0.2% of 82/255.

**Void:** a run without "Testing completed normally", or a failed C1, C0, Z
or S.
