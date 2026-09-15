# `Blend_surface` is already substantially fixed — on the peer's branch, in my lane's files

`Blend_surface` was this cycle's target: 114,378 channels per capture over 32
captures, the largest row resolving into `gl/surface.c`. Before baselining it I
looked for runs already on disk, per the rule that saved an emulator run on
`Texture_anisotropy`. That search found the answer, and it is not a measurement
of the suite — it is a coordination finding.

Reproduced by
`docs/testing/blend_surface_peer_gap.py <pgraph_run_root> <goldens_root>`.

## My standing gate note was wrong, and it has been steering me

My hourly check-in has said, for days:

> Peer head `ee926dbb`, unmoved 28+ hours. **Touches only `AGENTS.md` +
> `nv2a_issues.toml`, so no build gate required.**

That is true of the peer's *most recent* commits and **false of the branch**.
From the merge base `8c5218af` (2026-09-13 23:19Z), the peer branch carries
**fifteen commits that touch `hw/xbox/nv2a/pgraph/gl/*.c` — this lane's files**
— none of which are in my branch:

```
09ff005c  Merge the remote lane's #62/#66/#70/#71 GL fixes and its #51 correction
013181df  nv2a/gl: an R5G6B5 surface aborted, and its scalar tail disagreed with itself
1a10176e  Revert "nv2a: put a wide line's centre where the hardware puts it" -- measured worse
69102110  nv2a: put a wide line's centre where the hardware puts it, half a pixel along x
082bc0ac  nv2a/gl: read the drawn format, not the creation-time shape
a105a51a  nv2a/gl: a reused surface binding now refreshes its guest format
c234c1cc  nv2a/gl: the 565 green tail disagreed with its own NEON body
fe1cde49  nv2a/gl: a converted texture buffer is four bytes per pixel on every platform
f0095555  nv2a: expand 5- and 6-bit texels by replication, and stop claiming native packed formats
ab4a8293  nv2a: the signed blend equations ignore both factors, so program ONE/ONE
b6a35b34  nv2a: rasterise the NV04 solid line, so 2D_Lines draws
c6dd6fcd  nv2a: take the blend unit's surface format from the register, not the binding
be423575  docs: #36 smoothing is coverage in eighths, and 4.5% of the suite it is filed on
f4e029b1  nv2a/gl: repair the braces my #48 conflict resolution dropped
2f23dd9c  nv2a: read destination alpha as one on an alpha-less colour surface
```

Meanwhile `09ff005c` is the peer **merging my** GL fixes into their branch. The
flow has been one-directional and I did not notice, because my own note told me
the branch was documentation.

## The suite I was about to investigate is already mostly fixed

| line | binary | total | byte-exact |
|---|---|---:|---:|
| this lane (GL) | `66fdd6d7` ×3 runs | 3,660,115 | 3 / 32 |
| this lane (Vulkan) | `66fdd6d7` ×3 runs | 3,660,115 | 3 / 32 |
| this lane | `d7dfe146` (corpus) | 3,660,115 | 3 / 32 |
| **peer** | **`1a879e56`** ×2 runs | **2,361,485** | **6 / 32** |
| peer | `a105a51a` ×2 runs | 2,361,485 | 6 / 32 |
| peer | `082bc0ac` ×2 runs | 2,441,374 | 6 / 32 |
| peer | `082bc0ac` ×2 runs | 2,386,061 | 6 / 32 |

**A gap of 1,298,630 channels and three byte-exact captures.** And it lands
exactly where I had predicted the defect would be — the surface formats whose
top bit is forced:

| capture | this lane | peer | delta |
|---|---:|---:|---:|
| `1-DstAlpha_X_ZRGB8` | 294,912 | **0** | −294,912 |
| `DstAlpha_X_ORGB8` | 344,064 | 196,608 | −147,456 |
| `1-DstAlpha_X_ORGB8` | 344,064 | 196,608 | −147,456 |
| `X_ZRGB8_Add_SrcA_DstA` | 108,645 | **2** | −108,643 |
| `X_ORGB8_Add_SrcA_DstA` | 108,645 | **2** | −108,643 |
| `DstAlpha_X_Z1RGB5` | 98,304 | **0** | −98,304 |
| `1-DstAlpha_ARGB8` | 98,304 | 98,304 | 0 |
| `1-DstAlpha_R5G6B5` | 0 | 0 | 0 |

The `ARGB8` and `R5G6B5` captures — the formats with a **real** alpha channel —
do not move at all. Every capture that moves is an `X`/`Z`/`O` format. The
peer's `2f23dd9c` is titled *"read destination alpha as one on an alpha-less
colour surface"*, and `c6dd6fcd` *"take the blend unit's surface format from the
register, not the binding"*. Both touch **`gl/draw.c` and `vk/draw.c`
together**.

Nine of the ten candidate commits are ancestors of `1a879e56`, where the
improvement is already present, so the run data cannot isolate which one does
what — and does not need to.

## GL and Vulkan are byte-identical here, and that is why

On this lane's line, `Blend_surface` is **32 of 32 captures byte-identical
between the GL and Vulkan backends** at the same commit `66fdd6d7` — not
matching totals, the same images. That is the signature of a defect upstream of
both backends, and it is consistent with the peer having fixed `gl/draw.c` and
`vk/draw.c` symmetrically in each commit.

## Two things the peer's work says about my own parked findings

- **`ab4a8293` "the signed blend equations ignore both factors, so program
  ONE/ONE"**, with `docs/investigations/signed-blend-is-half-expressible.md`.
  I localised `Blend_tests` to `SADD`+`SREVSUB` (91.3%) and **parked it** as
  *"semantics unreadable from this corpus; three instruments failed, do not
  build a fourth"*. That was the right call about my corpus and the wrong
  conclusion about the problem: it was readable, from the register definition
  rather than from the pixels.
- **`69102110` and its revert `1a10176e`** ("put a wide line's centre where the
  hardware puts it, half a pixel along x" — *measured worse*). That is adjacent
  to my `Line_width` axis-offset result and to the AA-lines lead I left
  uncharacterised; the revert is a recorded negative I did not have.

## `082bc0ac` regresses this suite, and goes bistable

Parentage is linear and clean: `1a879e56` → `a105a51a` → `082bc0ac`.

- `a105a51a` moves `Blend_surface` **not at all** (2,361,485 → 2,361,485).
- `082bc0ac` makes it **worse**: 2,361,485 → 2,441,374 / 2,386,061.
- Those are **two different totals across four runs of the same commit** — the
  same bistable-not-noisy pattern as `Window_clip`, stable within a session and
  different between sessions.

So the last commit of that trio costs 24,576–79,889 channels on this suite and
introduces run-to-run variability. Flagging it rather than acting on it: it is
the peer's commit on the peer's branch.

## What I did not do

**I did not merge, cherry-pick, or port any of it.** These are another lane's
commits on another lane's branch, and pulling fifteen commits — several touching
files I hold — across is a coordination decision, not a measurement. It is
raised on PR #45 for the owner to decide.

What this does settle for my own planning: **`Blend_surface` should not be
investigated from scratch from this lane.** Re-deriving `2f23dd9c` would be
work already done, and the remaining 2.36M there is a different and smaller
question than the 3.66M I was about to open.

**The rule: check what the other lane has already landed in YOUR files before
starting a suite.** I resolve where a fix would live before baselining; I had
not been asking whether someone else already put it there. A stale one-line
summary in my own standing notes hid fifteen commits for two days.
