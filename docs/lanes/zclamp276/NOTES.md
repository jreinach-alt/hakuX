# lane zclamp276 -- #276 ZMinMaxControl NEARFAR

Base: master @ 8af1bbb18e. Run measured: `1790359589-xbox-full6743-dry2-2802408`
(apk a7b9d28e6b84, nova, 2026-09-25; all 32 ZMinMaxControl rows `status ok`, full
coverage of the suite). Goldens: `/home/justin/goldens/results/ZMinMaxControl`.

## Mechanism (derived from the source and the goldens; the issue's guess was wrong)

`vk/draw.c:2294` (`depthClampEnable`) is **not** it. The defect is that
`NV097_SET_ZMIN_MAX_CONTROL`'s **CULL_NEAR_FAR_EN** bit (bit 0) is dropped:
`pgraph.c` `DEF_METHOD(NV097, SET_ZMIN_MAX_CONTROL)` stores only ZCLAMP_EN
(bits 4-7) and ignores bits 0 and 8; nothing in pgraph.c / glsl / vk reads a
near/far cull.

What the test does (`z_min_max_control_tests.cpp`): 2 (z/w-buffer) x 2
(NEARFAR) x 2 (ZCLAMP/ZCULL) x 2 (IgnW) x {Ctrl, CtrlFixed} = 32 captures;
CLIP_MIN/MAX = 10/100 in both buffer modes; six 5x8 blocks of 16 px quads,
quad `i` spans z `[i*150/41, i*150/41 + 0.75*150/41]` left to right in the four
"Z=Inc" blocks, z 8..120 in the two "Z=N->F" blocks; w varies per block.

What silicon does (`zmm_quads.py`, per-quad ink fraction, golden vs ours):

| capture family | golden, each Z=Inc block | ours |
|---|---|---|
| `*_NEARFAR_ZCLAMP*` (8) | quads 0,1 and 28-39 **absent**, whole; 2-27 drawn | all 40 drawn (clamped) |
| `*_WBuf_NEARFAR_ZCULL*` (4) | W=10 block: 0,1 and 28-39 absent (other blocks already w-clipped) | W=10 all 40 drawn |
| `*_ZCLAMP*` without NEARFAR | all 40 drawn | same (exact up to 1 step) |
| z-buffered `*_NEARFAR_ZCULL*` | per-pixel clip, 24 kept + 1 partial | same (exact up to 1 step) |

Quad 1 (z 3.66..6.40) goes, quad 2 (7.32..10.06) stays; quad 27 (98.8..101.5)
stays, quad 28 (102.4..105.2) goes. Culling is **whole-primitive** (no partial
quads, fraction 0.00 or 1.00), identical in all four Z=Inc blocks whatever w is
(1, 0.01..0.0001, 0..150, 10), and identical in the w-buffered captures.

**The rule:** with CULL_NEAR_FAR_EN set, a primitive whose vertices ALL have
screen-space z < CLIP_MIN, or ALL have z > CLIP_MAX, is rejected -- independent
of ZCLAMP_EN and of w-buffering (the test is on z, not w). Under ZCLAMP_EN_CULL
on a z-buffer the per-pixel clip already discards every pixel of such a
primitive, which is why the z-buffered NEARFAR_ZCULL captures already match and
the w-buffered ones do not (their per-pixel clip is on w). ZCLAMP=CLAMP makes
it visible everywhere.

CULL_IGNORE_W (bit 8) has **no visible effect** on any of the 32 goldens (every
IgnW capture's quad map equals its pair). Nothing in this test has w <= 0 at a
kept primitive, which is presumably where it acts; left unmodelled.

## Priced offline (`zmm_price.py`: paint rejected quads background, rescore)

| capture | before (differing / max) | after | residual |
|---|---|---|---|
| Ctrl_NEARFAR_ZCLAMP, _IgnW, Ctrl_WBuf_NEARFAR_ZCLAMP, _IgnW | 21,073 / 215 each | 6,737 / 1 | pure one-step |
| Ctrl_WBuf_NEARFAR_ZCULL, _IgnW | 6,968 / 215 | 3,384 / 1 | pure one-step (= Ctrl_WBuf_ZCULL) |
| CtrlFixed_WBuf_NEARFAR_ZCULL, _IgnW | 7,074 / 215 | 3,490 / 1 | pure one-step (= CtrlFixed_WBuf_ZCULL) |
| CtrlFixed_NEARFAR_ZCLAMP | 25,344 / 215 | 10,992 / 50 | 7,181 one-step + 3,803 sliver |
| CtrlFixed_NEARFAR_ZCLAMP_IgnW | 25,158 / 215 | 10,806 / 50 | 7,181 + 3,617 |
| CtrlFixed_WBuf_NEARFAR_ZCLAMP | 25,161 / 215 | 10,809 / 50 | 7,181 + 3,620 |
| CtrlFixed_WBuf_NEARFAR_ZCLAMP_IgnW | 25,054 / 215 | 10,702 / 50 | 7,181 + 3,513 |
| other 20 captures | unchanged | unchanged | -- |

The 12 go from 213,093 px differing, 143,673 of them beyond one step (the
issue's 129,337 + 14,336 exactly), to 69,420 all one-step once the sliver goes
(the issue's "69,420 one-step" exactly: the rule leaves precisely the pixels
that were already one step off). **The CtrlFixed "sliver"** is not a second
defect: quad 0 of the W=Inc block has w = 0 on its left vertices, which
`UnprojectPoint * w` collapses to the origin, so its triangles stretch to the
screen corner. The golden has no sliver because quad 0 is rejected. The offline
paint only covers the 16x16 body, so it leaves the sliver; the real rule
rejects the whole triangle **iff** the w=0 vertices' z is below CLIP_MIN. In
vsh-ff.c the degenerate vertex is `0 * compositeMat = 0`, w is lifted by
`clampAwayZeroInf`, so `vtxPos.z = 0 / w = 0 < 10` -- rejected. Predicted:
those four go to ~7,181 one-step (+ at most 8 px where the sliver crossed a
kept quad). That is the one leg the offline paint cannot settle; the arm does.

The one-step residual is shared with every non-NEARFAR sibling (Ctrl_ZCLAMP
7,678, CtrlFixed_ZCLAMP 7,810 ...): depth interpolation precision, not #276.

## The hunk (`nearfar_cull.diff`, applies cleanly to master @ 8af1bbb18e)

| file | holder | change |
|---|---|---|
| `hw/xbox/nv2a/nv2a_regs.h` | [free] | `NV_PGRAPH_ZCOMPRESSOCCLUDE_CULL_NEAR_FAR_EN (1<<0)`, `NV097_SET_ZMIN_MAX_CONTROL_CULL_NEAR_FAR_EN 0xF` |
| `hw/xbox/nv2a/pgraph/pgraph.c` `DEF_METHOD(NV097, SET_ZMIN_MAX_CONTROL)` | lane.vshsubneg255 (then the next #273 lane) | store bit 0 |
| `hw/xbox/nv2a/pgraph/glsl/psh.h` `PshState` | lane.texvol283 | `bool cull_near_far` |
| `hw/xbox/nv2a/pgraph/glsl/psh.c` state init (~:311) and the fragment `clip` block (just before `if (ps->state->depth_needed)`, ~:2558) | lane.wbufdepth24 (queue: texvol283, wbuf31sel) | read the bit; emit a discard when all three `vtxPos{0,1,2}.z` are < `clipRange.z` or all > `clipRange.w` |

The discard is emitted only when `cull_near_far && (!depth_clipping ||
z_perspective)`: where ZCLAMP_EN_CULL on a z-buffer already clips per pixel the
shader text is **unchanged**. `vtxPos0..2` are always written (vsh.c sets all
three to the vertex for points; geom.c for triangles and lines), and
`clipRange` is always declared, so the check needs no `depth_needed`.

The register bit position (0) mirrors the method's nibble the way ZCLAMP_EN
(bit 4) already does; no test reads the register back, so it is unverified and
harmless.

## Must-not-move, by construction

`test_suite.cpp:147` sets NEARFAR | ZCLAMP_CULL before **every** test, on a
z-buffer: the new branch is not emitted there. The only suites that w-buffer
or set ZCLAMP_EN_CLAMP (Depth clamp, W buffering, W param) write
ZMIN_MAX_CONTROL **without** NEARFAR (`depth_clamp_tests.cpp:84,150,216,244,273`,
`wbuf_tests.cpp:459`, `w_param_tests.cpp:502,619,753`). So corpus-wide the
branch is emitted in exactly the 12 target captures; every other capture runs a
byte-identical shader (only the cache key gains a byte). Leg to name for each
must-not-move suite: it would move only if the gate `(!depth_clipping ||
z_perspective)` were dropped (polygon offset could then differ on z-buffered
CULL draws).

## Arm (not registered yet -- no ref can carry it)

The hunk touches three held files, so no commit on this branch can carry it
without colliding. The board request is `dispatch/board-requests/zclamp276.md`.
When the files are granted: apply `nearfar_cull.diff`, merge master, register
`zclamp276-nearfar.json` with a_ref = the merge, b_ref = the patch commit:

- must_move (ZMinMaxControl/...): the 12 above to the "after" column (Ctrl*: exact
  figures; CtrlFixed_*NEARFAR_ZCLAMP*: <= 7,189, max_rgb <= 1).
- must_not_move: the other 20 ZMinMaxControl captures; Depth buffer, Depth
  buffer fixed function, W buffering, Depth clamp, W param, Clear.
- Check scores1.tsv `status` for `unreadable` and PARTIAL COVERAGE first.

## Do not repeat

- The grid origin in the captures is y 60/252, not the source's arithmetic 70;
  measure it (`zmm_quads.py` notes this) or every quad reads 0.36/0.71.
- Do not look at `depthClampEnable`: ZCLAMP (no NEARFAR) is already exact to
  one step on all 8 captures.
