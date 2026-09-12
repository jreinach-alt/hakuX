# What the full-corpus sweep says about the unclassified backlog

Measured 2026-09-12 from the idle-priority scoreboard sweep, binary
`fb4dfafc6d38`, one disc per suite, only rows whose own progress log shows the
tests completing. 32 of 102 suites at time of writing; regenerate with
`docs/testing/collect_sweep.sh`.

The point of this file is to turn `unclassified` tracker entries into ranked
work. Numbers are exact-captures and total differing pixels.

## Nearly solved — the cheapest things on the board

| suite | exact | differing px | read |
|---|---|---:|---|
| `Fog_inf_coord` | 0/6 | **18** | 3 px per capture. Not a rule failure; a boundary or one-step residue. |
| `Depth_Clamp` | 8/40 | **1,754** | 44 px per failing capture. |
| `Color_key` | 10/18 | **1,936** | 242 px per failing capture. |
| `2D_Lines` | 1/13 | **3,257** | 271 px per failing capture. |
| `Edge_flag` | 0/2 | 5,374 | And we drop `0x16bc` (glEdgeFlag) entirely -- see the unhandled-method inventory. |
| `Degenerate_begin_end` | 0/1 | 8,422 | One capture. |
| `Color_mask_blend` | 0/1 | 18,786 | One capture. |
| `Combiner` | 5/8 | 24,901 | |

A suite differing by tens of pixels is a different kind of problem from one
differing by millions, and the tracker did not distinguish them. `Fog_inf_coord`
at 18 px total is almost certainly finished by a rounding or edge-inclusion
decision, not by a mechanism.

## Large and fully covered

| suite | exact | differing px | issue |
|---|---|---:|---|
| `Blend_tests` | 0/105 | 4,356,145 | #50, #43. The stack-C region dominates. |
| `3D_primitive` | 4/160 | 3,866,664 | #36 (smoothing) territory. |
| `Fog_exceptional_value` | 12/96 | 3,664,740 | #8. |
| `Fog_gen` | 4/60 | 2,333,312 | #41 -- but 2,172,192 of its structural channels are ONE cell whose golden holds three colours in the whole frame. Real residue 14,568. Do not rank on the raw figure. |
| `Blend_surface` | 4/32 | 2,155,037 | #48. |
| `Bump_env_lum` | 0/42 | 1,951,411 | #10 |
| `Depth_buffer` | 34/144 | 1,569,874 | #16, #52 |
| `Attrib_carryover` | 0/96 | 1,254,627 | #12, and #19's missing-state class |
| `Depth_buffer_fixed_function` | 6/80 | 663,094 | #52 -- a distinct, larger defect than `Depth_buffer`; error maxes at 9 units not 1. |
| `Bump_map` | 0/40 | 435,201 | #10 |
| `Alpha_func` | 1/16 | 435,032 | no issue of its own |
| `Color_zeta_overlap` | 6/9 | 399,197 | #4 |
| `Clear` | 25/32 | 532,200 | |
| `Context_switch` | 0/1 | 173,760 | one capture, no issue of its own |
| `Fog_carryover` | 0/11 | 177,656 | #42 territory |

## Two suites with no issue at all

`Alpha_func` (1/16, 435,032 px) and `Context_switch` (0/1, 173,760 px) are not
named by any tracker entry. `Color_mask_blend` and `Degenerate_begin_end` are
single-capture suites failing outright and likewise unowned. Small enough to be
cheap, and currently invisible to any query that starts from the issue list.

## Caveat that applies to every figure here

These are TOTAL differing pixels, not structural. A suite can be large here and
almost entirely one-step, which is a rounding floor rather than a rule -- that
is what `classify_residuals.py` separates, and the `boundary-shift` class only
exists from `d0114a49`. Rank on structural pixels from the scoreboard, and
check `run-2026-09-12-golden-discrimination.tsv` before fitting anything: a
saturated golden bounds the hardware value rather than determining it.

## A crash was hiding a defect: High vertex count

`HighVtxCount-inlinebuffers` SIGSEGV'd in `pgraph_finish_inline_buffer_vertex`
and took its run down, which is why this suite had no measurement at all. The
cause was a bound check naming `NV2A_MAX_BATCH_LENGTH` (524,287) against a
32,768-vertex Android allocation -- a 16x overrun past a `g_malloc`, with the
`assert` inert because this is a release build. Fixed in `878507db2f` by
growing the buffers on demand from a single shared capacity.

Verified on device, prediction met exactly: **4 of 4 captures, progress-log
proof true, zero crashes in the logcat**, against 2 captures and a crash at
test 3 of 4 before.

And now that it runs, it fails: **0 of 4 exact, 581,620 differing px.** That is
a real accuracy defect which no measurement could previously see, and like
`Alpha_func`, `Context_switch`, `Color_mask_blend`, `Degenerate_begin_end` and
`Fog_inf_coord` it belongs to **no tracker entry**. Six unowned suites now.

Worth stating plainly because it justifies the sweep: this defect was invisible
not because nobody had looked, but because looking crashed.
