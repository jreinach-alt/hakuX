# Per-test PGRAPH register diff: this emulator against this console

52 tests from two suites, run on the desktop build and on the project's Xbox
(`xbox-console-provenance.md`), with a register diff bracketed around **each
test** rather than around each suite. Cross-reference: #196, #200, #112.

## Result in one line

The emulator moved **24 distinct PGRAPH registers**, and **all 24 are declared
in `nv2a_regs.h`**. The console moved **336**, of which **308 are not declared
there**. Not one register outside the header's vocabulary moved on the emulator
in 54 diff blocks.

That is #200's claim — handlers rebuild registers field-by-field through
`PG_SET_MASK`, so a bit with no name is unreachable — measured rather than
inferred.

## The instrument, and what of this is reproducible

**Provenance.** The runs used a modified `nxdk_pgraph_tests`:

| | |
|---|---|
| tests tree base commit | `6743b6ab164e760e8b995e969c762d829af5d52e` ("Adds more fog tests.", 2026-09-20 17:53 -0700) |
| the modification | [`patches/nxdk_pgraph_tests-6743b6ab-per-test-pgraph-diff.patch`](patches/nxdk_pgraph_tests-6743b6ab-per-test-pgraph-diff.patch), committed here |
| emulator side | this repository at the commit this document landed on |
| console side | `xbox-console-provenance.md` |

`nv2a_index.json` carries `provenance.tests_commit` for exactly this reason:
a result that cannot name the tree it was measured against cannot be compared
with the next one. This document did not carry it, and the patch existed only
as uncommitted working-tree changes on one machine.

**What the patch is evidence of, precisely.** It was captured from that
working tree on 2026-09-21, the day after the runs. The files carry an mtime of
2026-09-21 06:40, which is later than the last build of that tree
(2026-09-20 18:24) and later than this document's first commit (18:13). So the
patch is the instrument *as it stands*, not a proof that the run's XBE was
built from exactly these bytes. Treat it as the thing to apply and re-measure
from, not as a warrant for the numbers below.

**The numbers below are not re-derivable from this repository.** The raw
per-side dumps were not preserved and the host-side script that attributed
`PGRAPH-DIFF <suite>::<test>` lines to tests was ad hoc and is gone: a search
of this box on 2026-09-21 found no file containing a `PGRAPH-DIFF` line
outside the tests tree's own source and binaries. A rerun -- one run per side,
which the Scope section already costs -- should apply the patch above, record
the resulting sha, and **commit the two dumps**, at which point the table stops
being a claim and becomes a check.

### What the patch changes

`nxdk_pgraph_tests` already had `enable_pgraph_region_diff`, but it captured at
suite `Initialize` and dumped at `Deinitialize`, so a difference could not be
attributed to a test. Three changes, in the tests tree, not in this repo:

- the capture/dump pair now brackets the test body, with a second
  `PGRAPHDiffToken` so the per-test capture does not overwrite the suite
  baseline;
- each dump is prefixed `PGRAPH-DIFF <suite>::<test>`, which is what lets a
  parser attribute register lines to a test;
- the dump is also streamed to an FTP collector on the host. Previously it
  reached only `Logger::Log()`, which writes to a file on the Xbox
  filesystem — readable over FTP from a real console, but not from an
  emulator whose `E:` is inside a qcow2, and the emulator half is the point.

A fourth change rides along and is not part of this measurement: `DumpDiff()`
also emits a four-register **PMC watch** (`BOOT_0` as a fixed-chip-ID canary,
`INTR_0`, `INTR_EN_0`, `ENABLE`). It is read-only -- nothing in the patch
writes MMIO -- and it exists for #188's question about `NV_PMC_ENABLE`'s bit
layout, not for this one.

The empirical blacklist in `DumpDiff()` stays commented out. It was derived on
one machine by intersecting two unrelated draws, and filtering inside the
instrument would hide exactly the divergence it exists to find. It is applied
on the host instead, where both sides are visible.

## What the diff can and cannot decide

A register that moved on **both** sides has a destination value on both, so the
two destinations can be compared. A register that moved on **one** side cannot
be judged: the other side may already have held the correct value, and
`DumpDiff` reports only what changed. Only the first class is called a
disagreement below. Of 191 comparable observations, 92 agreed.

## Systematic divergences

| register | bits | observations | emulator | console |
|---|---|---|---|---|
| `NV_PGRAPH_SURFACE` (0x710) | bit 0 — **undeclared** | 53 / 53 | 0 throughout | 1 throughout |
| `NV_PGRAPH_TEXFMT0` (0x1A04) | bits 4–5 — **undeclared** | 40 / 40 | 0 throughout | 3 throughout |

Neither side ever toggles these within the workload: the console holds them set
in every `from` and every `to`, the emulator holds them clear in both. They are
not set at the wrong moment — they are not modelled at all.

`SET_TEXTURE_FORMAT` makes nine `PG_SET_MASK` calls covering bits 1, 2, 3, 6–7,
8–14, 16–19, 20–23, 24–27 and 28–31. Bits 0, 4 and 5 are written by nothing.
`NV_PGRAPH_SURFACE` is only ever touched through `READ_3D`, `WRITE_3D` and
`MODULO_3D`, which start at bit 20.

The console also maintains a copy of the 0x700 block at +0x1000 that moves in
lockstep; the emulator's copy is static. 764 of the hardware-only observations
are that mirror.

## Declared fields that no code path writes

Five registers declared in `nv2a_regs.h` moved on the console and never on the
emulator. Four are on the project's own utility blacklist. The fifth is not:

**`NV_PGRAPH_CSV1_A` (0xFC0)** — the console sets bit 0, `..._T0_ENABLE`, a
**declared** field. In this tree `CSV1_A` is written only by `SET_TEXGEN_S/T/R/Q`,
through the `T0_S`/`T0_T`/`T0_R`/`T0_Q` masks. `T0_ENABLE`, `T0_MODE` and
`T0_TEXTURE` are declared in the header and referenced **nowhere else in
`hw/xbox/nv2a/`** — neither read nor written.

No live rendering defect follows from that today, precisely because nothing
reads them. It is worth recording anyway: `CSV1_A` appears in the register list
`pgraph_glsl_check_shader_state_dirty()` walks (`shaders.c:99`) — a dirty
check, not a hash — and nothing reads `T0_ENABLE` into a `ShaderState`, so two
states differing only in that bit are indistinguishable here and are not on
silicon.

## Not a divergence

`NV_PGRAPH_TEXOFFSET0` (0x1A24) and `NV_PGRAPH_TEXPALETTE0` (0x1A34) disagree
with a constant xor of `0x0002F000` — a fixed 0x21000-byte offset between the
two destinations, with the low flag bits preserved. That is the guest
allocating the texture and its palette at different physical addresses under
the two BIOSes, not a modelling error. It is listed because it is the shape a
real finding would have, and it is not one.

`NV_PGRAPH_ZCLIPMAX` (0x1ABC) is the one register the emulator moved and the
console did not (0x4B7FFFFF → 0x477FFF00, 2²⁴−1 → 65535.0). The console may
already hold the destination value, so this needs an absolute read before it
can be called anything.

## Scope

Two suites, `Texture format` (40 tests) and `Attrib float` (12). **52 tests,
54 diff blocks:** the patch dumps one block per test *and* one
`SUITE-RESIDUAL <suite>` block per suite from `Deinitialize`, so 52 + 2 = 54.
The two are different things -- a residual is the net change across a whole
suite, measured against `Initialize` -- and the observation counts below
(`53 / 53`, `40 / 40`, 191 comparable, 764 mirror) are over blocks, without
this document recording which of the 54 each denominator drew from. That
cannot be recovered without the raw dumps; see the provenance note above.

The claim "nothing outside the header's vocabulary moves on the emulator" is a
claim about those 54 diff blocks, not about every method. Widening it costs one
run per side and no new tooling.

## Bycatch

`resources/sample-config.json` in the tests tree is stale: it lists 34 tests
for `Texture format` where the binary registers 40, and 11 for `Attrib float`
where it registers 12. A test list read from it silently omits real tests —
`TexFmt_R6G5B5`, the subject of `r6g5b5-golden-packing.md`, is one of them.

A suite-level `"skipped": false` sets that suite's per-test default to *run*,
overriding `skip_tests_by_default`. To run named tests only, omit the
suite-level key entirely and list the tests.
