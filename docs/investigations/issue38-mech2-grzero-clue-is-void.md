# #38 mechanism 2: the `GRZero` half-and-half clue is void, and the parity is not per-triangle

Measured offline against the golden and the `z-tip-018-Context_switch` capture,
no device. Two checks, both cheap, both aimed at clues rather than at the rule.

## Where this starts

#38 mechanism 2 is measured and unimplemented: silicon holds a fragment colour
constant across the pixel pair `{2m, 2m+1}` and evaluates it at the pair's
right edge, `s = 2·floor(x/2) + 2`, 0 wrong of 512 on both `Alpha_func` bands.
What is **not** established is the *selection* rule -- which draws get the
paired granularity. The candidates on record, with what each survives:

| candidate | survives? |
|---|---|
| screen space, `w = 1` | no -- `High_vertex_count` is `w = 1` passthrough and unpaired |
| immediate-mode vertices rather than arrays | no alone -- `Shade_model` is immediate mode and unpaired |
| immediate mode **and** `w = 1` | not contradicted |
| one large primitive (>= 500 px) | not contradicted, not really tested |

Two clues were offered for narrowing it. Both are checked here and one of them
is not a clue.

## The residual's confinement to the upper half says nothing

The recorded observation is that `Context_switch/GRZero`'s residual is confined
to rows 48-239 -- the polygon's upper half -- and that its lower half is exact.
Reproduced: 70,444 differing px, **all** of them in rows 48-239, **zero** in
240-431, max channel error 2.

The lower half is exact because **nothing is drawn there**. Over the polygon's
x range the golden's lower half holds exactly **two** distinct colours, 0x33
and 0x44, which are `DrawCheckerboard`'s two tones; its whole per-row and
per-column spread is 17, the step between them.

`context_switch_tests.cpp` says why. `Test()` opens one
`PRIMITIVE_POLYGON`, submits four vertices spanning `top` to `midline`, then
writes `NV_PGRAPH_CTX_SWITCH1 = 0` **inside the Begin/End**, submits three more
vertices spanning `midline` to `bottom`, and restores the register. The
vertices submitted while the graphics class is zero never reach the
framebuffer -- the test prints "Bottom of screen is only drawn to with ctx
disabled" precisely to make that the subject.

So the lower half is **unmeasured, not unpaired**. That is the exact mirror of
this lane's own stated blind spot -- "a gradient steeper than ~4 bytes/px
leaves a row unmeasured, not unpaired" -- with a flat region in place of a
steep one, and it is the same trap as reading a flat pixel count as inertness.
The clue is void and carries no information about the selection rule.

## The parity is not per-triangle either

That left a sub-primitive reading worth one measurement: the four drawn
vertices are a `PRIMITIVE_POLYGON`, which `prim_rewrite.c` tessellates as a fan
from v0, so the drawn quad is two triangles split on the v0-v2 diagonal from
(64, 240) to (576, 48). If the pair granularity were a property of triangle
setup it could hold on one side and not the other, which would explain a
row-level split without any draw-level rule.

It holds on both. Counting every channel step in rows 48-239 and its x parity,
restricted to each side of that diagonal:

| | steps | on an even x | rows all-even |
|---|---:|---:|---:|
| golden, both triangles | 90,549 | **81.8%** | 55 of 192 |
| golden, v0-v1-v2 | 40,459 | **90.1%** | 55 of 192 |
| golden, v0-v2-v3 | 50,090 | **75.1%** | 59 of 191 |
| ours, both | 80,936 | 56.4% | **0** of 192 |
| ours, v0-v1-v2 | 42,858 | 55.9% | **0** of 192 |
| ours, v0-v2-v3 | 38,078 | 57.1% | **0** of 191 |

(81.8% against the 82.8% on record, and 55 all-even rows against 64: this
counts every channel step where the recorded figure counts transitions of
count <= 4, so the two are the same signature under slightly different
conditioning. The point is the split, which either conditioning gives.)

Both triangles are far above our ~56%, so the selector is **not** triangle
setup, and the candidate list above is unchanged.

## What `GRZero` is, for the candidate list

Worth stating plainly because it is what decides whether `GRZero` narrows
anything: its drawn part is **four screen-space vertices at `w = 1.0` with
per-vertex diffuse, submitted in immediate mode**. That is the *same* class as
`Alpha_func`'s band. `GRZero` is valuable for a different reason already on
record -- it shows the pair on RGB rather than only on alpha, and on a gradient
running in both axes -- but it is **not a second independent class**, so it
corroborates "immediate mode and `w = 1`" and cannot narrow it.

The narrowing has to come from the two negatives (`High_vertex_count`,
`Shade_model`) or from the four captures already specified on the issue: the
same screen-space quad with a shallow colour ramp, drawn immediate vs arrays
crossed with `w = 1` vs `w != 1`.

## Two notes for whoever takes this next

**The tooling is not on the integration branch.** `docs/testing/interpolator_phase.py`
and `docs/investigations/interpolator-sample-position.md`, which the issue
tells the reader to reproduce from, exist only on
`worktree-agent-a461720f7c39f5548` (`bf90a00c44`, `fe1fdae25f`). They are not
ancestors of `claude/es-de-launcher-disc-error-ojnl14`, so the census cannot be
re-run at the tip. Either fold them in or stop citing them.

**The fix is still one expression in `glsl/psh.c`.** Nothing in `glsl/vsh.c`,
`vsh-ff.c`, `vsh-prog.c` or `geom.c` can express a per-fragment sample rule; it
needs `gl_FragCoord.x` parity and a screen-space derivative. That is unchanged
and is why no fifth candidate is offered here.
