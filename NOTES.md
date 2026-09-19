# lane.blit83b — #83 second pass, analysis only

## Job

The first pass (`lane.blit83`, issue comment 5737707468) settled everything a
reader could settle and left one thing it could not: **which** pixels differ on a
**device** capture at a ref carrying `dca3c94b98`. Every "which pixels" datum in
that comment was desktop-measured at `b9d845d316`, which does not carry
`dca3c94b98`, so the existing comparison confounded the commit with
desktop-vs-device.

Falsifier, pre-stated in the brief: if the differing pixels on the device capture
fall **inside** the 1×1 blit rect, "not the blit" is refuted and #83 goes back to
`vk/blit.c`.

## What I read, and its provenance

Capture sets — the judged 2026-09-18 pair, both arms, under
`/home/justin/hakux-work/dispatch/results/`:

| | arm A | arm B |
|---|---|---|
| result dir | `1789758697-lane.arms-blit38A-2228233` | `1789758704-lane.arms-blit38B-2230198` |
| ref | `71c7bd1d7d` | `24a75d6e3c` |
| `apk_sha` on every scored row | `7064ef90460a` | `dc3dc7c38b55` |
| device | thor, serial `bdc158a5` | thor, serial `bdc158a5` |
| captures written | 2026-09-18 12:12–12:21 | 2026-09-18 12:23–12:32 |
| runs | 5, all `progress_log_proof: true` | 5, all `progress_log_proof: true` |
| suite total | 168,245 px, 17/41 exact | 8 px, 33/41 exact |

Binding checked rather than assumed: `sha256(builds/71c7bd1d7d.apk)` =
`7064ef90460a…` and `sha256(builds/24a75d6e3c.apk)` = `dc3dc7c38b55…`, which are
the `apk_sha` values the scorer stamped on each row. Two distinct binaries, not
one column repeated.

Goldens — `/home/justin/goldens/results/Image_blit`, 42 PNGs, every one mtime
**2026-09-09 20:34**. Nine days *older* than the run, so the "golden newer than
the run" hazard does not apply here.

Dating the commit against the capture:

```
dca3c94b98  2026-09-12 20:03:12 -0700  nv2a/vsh: quantise the vertex colour to its byte before the interpolator
git merge-base --is-ancestor dca3c94b98 71c7bd1d7d  -> 0   IS an ancestor
git merge-base --is-ancestor dca3c94b98 24a75d6e3c  -> 0   IS an ancestor
git merge-base --is-ancestor dca3c94b98 b9d845d316  -> 1   NOT an ancestor (the desktop set)
```

Capture postdates the commit by six days, on both arms.

## Result

`docs/testing/blit_residual_anatomy.py <captures> /home/justin/goldens/results/Image_blit`
on arm B `captures1`:

- 8 differing px over 41 captures, 33 byte-exact. All eight `Overlap_*` read
  `differing = 1`, `max|d| = 1`.
- **0 of 8 blitted destination pixels differ.** All eight are
  `ours=(255,255,0,255) golden=(255,255,0,255) delta=(0,0,0,0)`.
- Decomposition: `big_quad=1  small_quad=0  ELSEWHERE=0` in every one of the eight.

The coordinate, which is the whole point and which the anatomy script does not
print — the single differing pixel is at **(176,180)** in all eight captures,
B channel only, ours 227 / golden 228, delta −1. Identical in all 5 runs of
arm B **and** all 5 runs of arm A: 80 capture-golden pairs, one answer.

That is the refutation a copy mechanism cannot survive. The blit destination
varies across the eight — (63,64) (64,64) (191,64) (192,64) (63,191) (64,191)
(191,191) (192,191) — and the differing pixel does not move with it. Offsets from
the blit dest run from (−16,−11) to (+113,+116).

Neighbourhood of (176,180) on row y=180: a smooth interpolated ramp, R falling
39→24, B rising 222→231. Golden steps B 227→228 at x=176; ours steps at x=177.
One quantisation boundary displaced by one pixel, 1 of 7,301 B-channel horizontal
step edges inside the 128×128 quad; 16,383 of 16,384 quad B pixels are exact.

The x=64 R-channel tie that the desktop anatomy named (127.5 on a 255→0 ramp,
hardware 128, ours 127) is **closed** on device at this ref: ours=128,
golden=128 in all eight.

## Falsifier verdict

**Negative for the blit — the "not the blit" conclusion is NOT refuted.** The
differing pixel falls outside the 1×1 blit rect in 8 of 8 captures, on device, at
a ref carrying `dca3c94b98`, reproduced over ten runs of two distinct binaries.

## De-confound, stated with what remains

The desktop-vs-device confound the first pass could not remove is removed:

| host | ref | carries `dca3c94b98` | per `Overlap_*` |
|---|---|---|---|
| Nova / Adreno, 2026-09-10 | `ccad2844d4` | no (verified non-ancestor) | 1,573 |
| Thor, 2026-09-18 | `71c7bd1d7d` | yes | 1 |
| Thor, 2026-09-18 | `24a75d6e3c` | yes | 1 |

Both sides are device/Vulkan, so ~1,573 → 1 is not desktop-vs-device. **What it
still is**: a Nova→Thor device change, and a 09-10→09-18 commit window that also
contains #33's swizzle fix and the clip fix. I am not attributing the drop to
`dca3c94b98` on this evidence, and #83 does not need the attribution — that is
#38 mechanism 1's business. What #83 needed was the coordinate, and the
coordinate does not depend on which commit closed the other ~1,572.

## Side finding: the control leg's inertness is now visible, not just argued

Arm A and arm B produce the byte-identical pixel — (176,180), 227 vs 228 — in all
ten runs. The BLEND_AND divide moved the suite 168,245 → 8 and did not move one
bit of the eight. That is what the first pass predicted by reading the branch
structure, now seen. It does not upgrade the leg: a leg that could not move is
still not a measurement of #83's claim.

## Recommendation

**CLOSE #83.** Not a defect in `vk/blit.c`. The surviving pixel is interpolated
vertex colour and it already has an open owner: **#38**, `fixed-part`, "One-step
colour differences from hardware across many suites (rounding, interpolation,
blending)", whose mechanism 1 is exactly this (`colorPrecision` in
`glsl/vsh.c` plus `dca3c94b98`). No re-file, no new issue, no file grant.

Board request written to `$DISPATCH_DIR/board-requests/lane.blit83b.md`.
