# Bits `nv2a_regs.h` does not name are unreachable by the emulator

Root cause for all three register disagreements in
`emulator-vs-hardware-registers.md`. They are not three defects; they are one
mechanism.

## The mechanism

Method handlers do not store the guest's parameter. They **reconstruct** the
register from named fields. `DEF_METHOD(NV097, SET_TEXTURE_FORMAT)` in
`pgraph/pgraph.c:4058`:

```c
PG_SET_MASK(reg, NV_PGRAPH_TEXFMT0_CONTEXT_DMA,     dma_select);
PG_SET_MASK(reg, NV_PGRAPH_TEXFMT0_CUBEMAPENABLE,   cubemap);
PG_SET_MASK(reg, NV_PGRAPH_TEXFMT0_BORDER_SOURCE,   border_source);
PG_SET_MASK(reg, NV_PGRAPH_TEXFMT0_DIMENSIONALITY,  dimensionality);
PG_SET_MASK(reg, NV_PGRAPH_TEXFMT0_COLOR,           color_format);
PG_SET_MASK(reg, NV_PGRAPH_TEXFMT0_MIPMAP_LEVELS,   levels);
PG_SET_MASK(reg, NV_PGRAPH_TEXFMT0_BASE_SIZE_U/V/P, ...);
```

Nine `PG_SET_MASK` calls, one per declared field. **Any bit not covered by a
declared field is never written** and keeps whatever it held at init — zero.

So a bit missing from `nv2a_regs.h` is not merely undocumented. It is
**structurally unreachable**: no method handler can set it, because handlers
only address named masks.

## The three disagreements, explained

**`NV_PGRAPH_TEXFMT0` / `TEXFMT1`, bits 4–5.** Not covered by any declared
field — the register's `DIMENSIONALITY` is `0x000000C0`, bits 6–7 — so nothing
writes them.

There is a second, sharper discrepancy in the same handler. The **method**
declares a wider field than the **register**:

| | mask | bits |
|---|---|---|
| `NV097_SET_TEXTURE_FORMAT_DIMENSIONALITY` | `0x000000F0` | **4–7** |
| `NV_PGRAPH_TEXFMT0_DIMENSIONALITY` | `0x000000C0` | **6–7** |

The handler reads a 4-bit value out of the parameter and writes it into a
2-bit register field. Bits 4 and 5 are exactly the two that fall out — and
exactly the two where hardware and this emulator disagree. That is the leading
explanation rather than a proven one: the observed values (`hw ...B8` versus
`em ...88`) do not decompose trivially under the header's layout, which is
itself consistent with the header's `TEXFMT0` layout not matching silicon.

**`NV_PGRAPH_SURFACE`, bit 0.** The register declares exactly three fields —
`WRITE_3D` `0x00700000`, `READ_3D` `0x07000000`, `MODULO_3D` `0x70000000` — and
every writer in the tree is a `PG_SET_MASK` against one of them
(`pgraph.c:934, 2275, 2281, 2287, 2296`). **Nothing in this emulator can set
bit 0.** Hardware holds it set before and after; we hold it clear throughout,
which is what the measurement showed.

## Why this is bigger than three registers

The gap list records "no vocabulary" as a reason finding divergences is slow: a
suite moves 135 PGRAPH registers and `nv2a_regs.h` names 14. That was filed as
a *description* problem.

It is worse than that. An unnamed bit cannot be described **and cannot be
written**. Every hole in the header is a hole in the emulator's reachable state
space, and the two are the same hole by construction.

This makes the header's completeness a correctness property rather than a
documentation nicety, and it makes the hardware map in
`nv2a-mapping-programme.md` the thing that closes it: measuring which bits
silicon actually latches per method is precisely the input needed to widen the
masks.

## What it does not say

It does not say the three disagreements matter to any rendered output. The run
that produced them differs from its golden by 5,412 px at a **maximum delta of
1** — #38 territory. Whether an unwritten `TEXFMT0` bit contributes to that is
untested. The value here is that a pixel count gave "rounding, probably" and
this gives two named registers, four bit positions, and a mechanism.
