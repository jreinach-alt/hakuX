# Where this emulator differs from the console

Measured against the project's own Xbox (`xbox-console-provenance.md`,
calibrated 3,374/3,379 bit-identical). Cross-reference: #112.

Until this week the only reference was 5,608 published goldens. With the
console on the bench the question changes from *"do we match the goldens"* to
*"where do we differ from the hardware"*, and the two are not the same list.

## The headline: nothing is unimplemented

**Every declared NV097 method offset has a handler. All 219 of them.**

`hw/xbox/nv2a/pgraph/methods.h.inc` is the dispatch table: 209 entries across
`DEF_METHOD`, `DEF_METHOD_RANGE`, `DEF_METHOD_CASE_4` and
`DEF_METHOD_CASE_4_OFFSET`, expanding to **1,358 covered opcodes** against 220
declared method offsets. The single apparent gap,
`NV097_SET_SURFACE_FORMAT_TYPE`, is a bitfield mask inside
`NV097_SET_SURFACE_FORMAT`, consumed by `GET_MASK` — not a method.

This matters because it says where the gaps are **not**. There is no missing
feature list to work through. Every divergence below is a *behavioural*
difference in code that already exists, and behavioural differences are only
findable by comparison against hardware.

*(Arriving at that number took six attempts, each wrong differently — counting
indentation levels, counting `case NV097_*` labels in `pgraph.c` where 84 of
105 turned out to be operand-value dispatch, a naming-convention rule that
misfiled `SET_CULL_FACE_ENABLE`, and three passes that missed dispatch macro
forms or failed to evaluate `16*4` as a range count. Each was validated only at
the end, against features known to render correctly. Recorded because the
lesson generalises: a coverage number without a validator is a guess.)*

## A. Modelled nowhere — confirmed on silicon

| what | evidence | issue |
|---|---|---|
| `NV_PMC_ENABLE` (0x200) — **read landed, write still nowhere** | silicon reads `0x01110000` with the console idle; `pmc_read` has returned that constant since PR #198. `pmc_write` still drops it via `default:`, deliberately — writing 0 halted the console outright, and what each bit gates is unestablished | #188 |
| `NV_PMC_BOOT_1` (0x004) — the **MMIO endian switch** | not declared and not modelled. Hardware honours it: writing ones byte-swapped every subsequent access | #189 |
| PMC reads `0x160`, `0x204`–`0x2FC` — **read landed, what the region IS still untested** | silicon returns `1` at 0x160 and at all 63 dwords of 0x204–0x2FC; `pmc_read` has returned that since PR #211, for dword-aligned offsets only. Whether the run is 63 live registers, one aliased register or a fixed unimplemented-read pattern is **undetermined and not modelled** — separating them needs a write one dword from #188's register, which halted the console. `pmc_write` drops the whole region via `default:` | #190 |
| PVIDEO overlay composition | `d->vga.enable_overlay = true` is **commented out** in `pvideo.c`; `nv2a.c:1302` has `overlay_draw_line` commented out too | #110 |
| PVIDEO size/pitch limits | `pvideo_write`'s `default:` stores all 32 bits unmasked — no cap of any kind | #110 |

**Read the row, not the heading.** This table is where PMC briefs are written
from — #188 came out of it, and #189 and #190 are still open above — so a row
that has partly landed is annotated in place rather than deleted. Check `pmc.c`
before writing "the emulator answers nothing in this block" into a brief.

## B. Behaviour that provably differs from hardware

| what | measured | issue |
|---|---|---|
| Slope-scaled polygon offset under W buffering | identical geometry, 235,200 px: hardware collapses a **383,447-unit depth span to 15 units**, 72% of the quad on one value. We produce a smooth per-pixel gradient. This is *flattening*, not clamping — the values sit at 9.93M, far from the 24-bit ceiling | #31 |
| `Texture_format::TexFmt_R6G5B5` | **134,902 px** (43.9%) from the golden on our console, byte-identical across runs *and* disc compositions. **Reclassified** — `gap-list-b-resolved.md`: the emulator matches our console exactly, so the golden is the outlier | new |
| `Attrib_float::-NaNs_NaNs` | **60 px**, likewise deterministic across runs and discs. **Reclassified** — `gap-list-b-resolved.md`: the emulator is 14,637 px from our console, so the defect here is ours; the 60 px is the residual discussed below | new |

**Read the rows, not the heading**, for the last two. Both were first read as
this console disagreeing with a golden captured on 1.0 silicon — either a
V1.1-vs-1.0 difference or a golden from a different suite build.
`gap-list-b-resolved.md` has since run both against a desktop build of this
tree, and that two-way reading does not survive either row:

- `TexFmt_R6G5B5`: the emulator is **byte-identical to our console** and
  134,902 px from the golden. Two independent implementations agreeing against
  a reference is evidence about the reference, so the golden is the outlier and
  the dichotomy above is settled in favour of the suite-build half.
- `-NaNs_NaNs`: the emulator is **14,637 px** from our console and 14,697 px
  from the golden, while our console is 60 px from the golden. The large,
  actionable defect is the emulator's. The 60 px is the residual, and it is
  what the explanations below are about.

Both still reproduce exactly and neither is noise; what they are evidence
*about* has moved.

**A third explanation for the 60 px, which this list omitted.** The tests tree
says so itself, at `src/tests/attribute_float_tests.cpp:55-57`: *"It appears
that the handling of the signaling NaN is nondeterministic. Sometimes it is
converted to quiet NaN. As pgraph operates on integers and does a conversion
from float back to int, it may be better to fall back into setting raw values
without doing the float conversions."* If the first half is right, the golden
froze one of two outcomes and the 60 px is neither a silicon revision nor a
suite build. Note where the comment's own last sentence points: at the
**submission path** — what the XBE puts in the pushbuffer after a float-to-int
conversion — not at the GPU.

**None of the three needs a second console to make progress**, and two are
readable offline:

- **A different suite build** is settled by the goldens' provenance and by
  building the suite, not by more silicon. The goldens are
  `abaire/nxdk_pgraph_tests_golden_results` @ `6e159f15`
  (`xbox-calibration-2026-09-20.md`); the comparison is that commit's
  `-NaNs_NaNs.png` against one built from the XBE we ran.
- **The conversion path** is readable from the XBE we already have, with the
  same disassembly #74 used to classify all 61 FIST/FISTP sites in the .text of
  this exact XBE (`nv2a_issues.toml`, #74's `blocker_tested` — extracted from
  `nxdk_pgraph_tests_xiso.iso`, which is the calibration disc). If the value
  the test submits is fixed by a conversion in the XBE, the nondeterminism is
  about that code and not about silicon at all.
- **A V1.1-vs-1.0 difference** is the only one that would need another console,
  and it is the last worth buying: a 60 px residual on a capture where our own
  emulator is 14,637 px out.

"Deterministic across runs and discs" was measured on this console and does not
by itself rule the nondeterminism out — a console can be deterministic in
itself and still disagree with another. It is not neutral either: the literal
reading of that TODO is run-to-run variation, and this capture is recorded
byte-identical across runs and across disc compositions
(`xbox-calibration-2026-09-20.md`). The emulator side is deterministic too,
across five binaries
(`../investigations/attrib-float-is-nantoone-and-the-colour-floor.md`, which
quotes the same TODO). So if the nondeterminism is real, it resolves somewhere
stable per machine rather than per run.

Until one of the two offline checks is done, `-NaNs_NaNs` should not be quoted
as a settled hardware disagreement — and per `gap-list-b-resolved.md` it should
not be quoted as a hardware defect at all.

## C. Measurement hazards — things that will mislead a future comparison

| what | measured |
|---|---|
| `Color_zeta_overlap::ZetaIntoColor` | **nondeterministic on silicon**: 20,141 px differ between two identical-disc runs. #88/#91 take absolute pixel targets from this capture's golden histogram |
| `Color_zeta_overlap::ColorIntoZeta_ZB` | nondeterministic, 3,182 px run to run |
| `3D_primitive::LineLoop-inlinearrays-ls` | stable within a disc, **4,546 px different between disc compositions** — contamination, the clearest case of why whole-suite captures are marked non-solo |
| `Color_zeta_overlap::Swap` / `Swap_ZB` | byte-stable across every hardware run — safe to quote exactly |

## D. Why finding more of B is currently slow

- **No vocabulary.** A single suite moved 135 PGRAPH registers; `nv2a_regs.h`
  names **14**. The other 121 are not defects — `pgraph.c` models methods, not
  registers — but there is no name to describe a divergence with.
- **47% of a raw register diff is noise**, and the blacklist that identifies it
  (63 registers, all 63 confirmed present in a real delta) is **commented out**
  in `DumpDiff()`.
- **The capture point is wrong for attribution.** `Capture()` is at suite
  `Initialize` and `DumpDiff()` at `Deinitialize`. Every test draws its
  parameter label after its own geometry, so the diff records residual state
  after the label draw. Measured: two tests differing only in blend equation
  (`FUNC_ADD` vs `V_MIN`) produce **identical `NV_PGRAPH_BLEND`**, and the only
  five registers that differ are `CLEARRECT` aliases tracking the test *name's*
  length.

## What would extend list B fastest

Nothing in A needs hardware — it is all readable from the tree. List B is where
the console earns its keep, and the cheapest next step needs no console at all:
**run the same suites under a desktop build with `enable_pgraph_region_diff`
and diff against the hardware register dumps already captured.** That converts
pixel differences into named state differences, and it is the only item here
that has not been attempted.
