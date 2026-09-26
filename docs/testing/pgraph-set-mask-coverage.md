# Which PGRAPH bits a method handler can ever write (static, #200)

This is the static half of #200. The measured half is
[`pgraph-per-test-emulator-vs-hardware.md`](pgraph-per-test-emulator-vs-hardware.md)
(PR #201), which found the emulator moving 24 PGRAPH registers, all declared,
against the console's 336. That doc asks which registers move. This one asks
which bits the source *can* move from a pushbuffer method at all.

Reproduce from the repository root, no device and no build:

    python3 docs/testing/pgraph_set_mask_coverage.py --md        # the table
    python3 docs/testing/pgraph_set_mask_coverage.py --sites     # plus every write site

Read at master `9a4cce6570` (2026-09-25).

## What is counted

For each PGRAPH register `nv2a_regs.h` defines:

- **declared**: the OR of the field masks the header lists under it.
- **method-written**: the OR of every mask a method-driven path in
  `pgraph/pgraph.c` stores a value into. That covers `PG_SET_MASK` in any
  `DEF_METHOD` or in `pgraph_method()`, every `method_fast[]` entry
  (`MF_MASKED`/`MF_XLAT` through `mask_lut[]`, `MF_DIRECT`/`MF_TEX` as whole
  words), and every `pgraph_reg_w()` that stores a whole word, which covers
  all 32 bits.
- Instances the handlers reach as `X0 + slot * 4` (TEXFMT0..3, TEXPALETTE0..3,
  TEXCTL0_0..3, ...) are folded onto `X0`. The fold is keyed on that source
  pattern, not on address, because `CONTROL_1` sits at `CONTROL_0 + 4` and is
  a different register.

`pgraph_init()`'s two reset-time `PG_SET_MASK`s, the `pgraph_read()` RDI
bookkeeping and the MMIO path are left out of "method-written" on purpose. See
the MMIO section below.

**What this cannot see.** It checks masks, not values. A covered mask can
still be written with a narrower range than the guest sent. The DIMENSIONALITY
truncation in `SET_TEXTURE_FORMAT` is that case: its mask counts as covered
here, but the guest's high two bits are dropped (the board's 2026-09-21 check,
`nv2a_issues.toml` issue.200 status_note, CORRECTED). So the holes below are a
lower bound on unreachable bit *states*. The script also has nothing to say
about registers the header does not define. It cannot list PR #201's 308
undeclared console-moved registers, only confirm that nothing in `pgraph.c`
writes them.

## Result

| | count |
|---|---|
| register families written by a method handler | **75** |
| stored as a whole word (no hole possible) | 55 |
| rebuilt field by field (masked writes only) | 20 |
| with at least one **declared** field no handler writes | **3 / 75** |
| with at least one bit of any kind no handler writes | **20 / 75** |
| unwritten bits, summed per family | 8 declared, 287 undeclared |
| declared-field registers no method writes at all | 11 (all MMIO control: INTR, INTR_EN, CTX_CONTROL, CTX_USER, FIFO, RDI_INDEX, CHANNEL_CTX_*, INCREMENT, DEBUG_3) |

**The brief's falsifier comes out small: 3 / 75 (4%).** The header's declared
fields are nearly all reachable, and "every header hole is a hole in the
reachable state" does not hold for declared bits. What does hold, with no
exceptions, is narrower:

> **Every one of the 20 registers a handler rebuilds field by field has
> unwritten bits, and in 15 of the 20 the written mask equals the declared
> mask exactly.** In those 15 registers the header's field list is the upper
> bound on reachable state. (The other five: `CSV1_A`, `CSV0_D` and
> `TRAPPED_ADDR` write less than they declare; `CSV1_B` and `SHADERCTL`
> declare nothing and are written through borrowed or literal masks.) The
> other 55 registers are stored whole and cannot have a hole.

So the #200 thesis holds in the form "undeclared bits of a register rebuilt
from named fields are unreachable". It does not hold as "undeclared bits are
unreachable". Most of the 55 whole-word registers have partial or empty field
lists (TEXADDRESS0 declares `01171717`, TEXFILTER0 `FF3FFFFF`, the combiners
nothing at all), and they are still written whole from the method parameter.

### The 20 field-rebuilt registers

| register | addr | declared mask | method-written | declared, never written | undeclared, never written |
|---|---|---|---|---|---|
| `NSOURCE` | 0x0108 | `00000001` | `00000001` | -- | `FFFFFFFE` |
| `TRAPPED_ADDR` | 0x0704 | `11F71FFF` | `01F71FFF` | `DHV` | `EE08E000` |
| `SURFACE` | 0x0710 | `77700000` | `77700000` | -- | `888FFFFF` |
| `CSV0_D` | 0x0FB4 | `DFFCFFFF` | `DFDCFFFF` | `FOG_MODE` | `20030000` |
| `CSV0_C` | 0x0FB8 | `DFFFFF00` | `DFFFFF00` | -- | `200000FF` |
| `CSV1_B` | 0x0FBC | `00000000` | `FFF0FFF0` | -- (see note) | `000F000F` |
| `CSV1_A` | 0x0FC0 | `FFF7FFF7` | `FFF0FFF0` | `T0_ENABLE`, `T0_MODE`, `T0_TEXTURE`, `T1_ENABLE`, `T1_MODE`, `T1_TEXTURE` | `00080008` |
| `CHEOPS_OFFSET` | 0x0FC4 | `0000FFFF` | `0000FFFF` | -- | `FFFF0000` |
| `ANTIALIASING` | 0x1800 | `00000001` | `00000001` | -- | `FFFFFFFE` |
| `BLEND` | 0x1804 | `0001FFFF` | `0001FFFF` | -- | `FFFE0000` |
| `CONTROL_0` | 0x194C | `3FDF5FFF` | `3FDF5FFF` | -- | `C020A000` |
| `CONTROL_1` | 0x1950 | `FFFFFFF1` | `FFFFFFF1` | -- | `0000000E` |
| `CONTROL_2` | 0x1954 | `00000FFF` | `00000FFF` | -- | `FFFFF000` |
| `CONTROL_3` | 0x1958 | `00070381` | `00070381` | -- | `FFF8FC7E` |
| `SETUPRASTER` | 0x1990 | `B0E01FCF` | `B0E01FCF` | -- | `4F1FE030` |
| `SHADERCTL` | 0x1998 | `00000000` | `0FFFFFFF` | -- | `F0000000` |
| `SHADOWCTL` | 0x19A4 | `00000007` | `00000007` | -- | `FFFFFFF8` |
| `TEXFMT0` (x4) | 0x1A04 | `FFFF7FCE` | `FFFF7FCE` | -- | `00008031` |
| `TEXPALETTE0` (x4) | 0x1A34 | `FFFFFFCD` | `FFFFFFCD` | -- | `00000032` |
| `ZCOMPRESSOCCLUDE` | 0x1A84 | `00000010` | `00000010` | -- | `FFFFFFEF` |

`CSV1_B` has no fields of its own in the header. `SET_TEXGEN_*` writes it for
stages 2 and 3 through `CSV1_A`'s `T0_*`/`T1_*` masks, so its bits 0-2 and
16-18 are the same unwritten ENABLE/MODE/TEXTURE fields as `CSV1_A`'s.

`NSOURCE` and `TRAPPED_ADDR` are written only on the NOP-trap and bad-channel
paths, and `NSOURCE` only with a constant. They are not rendering state.

The three declared fields nothing writes are referenced nowhere else in
`hw/xbox/nv2a/`. `CSV0_D_FOG_MODE` appears only in a `FIXME` comment at
`pgraph.c:2639`. `TRAPPED_ADDR_DHV` and the six `CSV1_A_T{0,1}_{ENABLE,MODE,TEXTURE}`
appear nowhere outside the header.

The remaining 55 whole-word registers and the 11 MMIO-only ones are in the
script's full `--md` output.

## Agreement with the measured half

Every divergence PR #201 measured falls inside the static holes above. None
falls outside them:

| PR #201 observation | static row |
|---|---|
| `SURFACE` bit 0: console 1, emulator 0, 53 / 53 | bit 0 is in `888FFFFF` |
| `TEXFMT0` bits 4-5: console 3, emulator 0, 40 / 40 | bits 4, 5 are in `00008031` |
| `CSV1_A` bit 0 (`T0_ENABLE`) set on console only | declared, never written |

This is a consistency check and nothing more. The static table was built
knowing those three, and it would have listed them either way. The new
information is the rest of the table: 17 more field-rebuilt registers whose
undeclared bits are all pinned at their init value here.

## MMIO is not covered by this, and does not need to be

`pgraph_write()`'s `default:` case stores a guest CPU's MMIO word whole
(`pgraph.c:1020`), so a BAR0 write can reach every bit of every register. The
thesis is about the pushbuffer method path, which is what the test suite and
titles drive. A register written only by MMIO is reachable from the CPU and
only from the CPU.

## What would settle whether these holes matter

This static reading says which bits the emulator cannot set. It does not say
which of them silicon does set. That needs PR #201's instrument widened to
more suites: one run per side with the committed
`patches/nxdk_pgraph_tests-6743b6ab-per-test-pgraph-diff.patch`, dumps
committed, and each console-moved bit checked against the "undeclared, never
written" column. A console bit that moves inside a hole is a defect this table
predicts. A console bit that moves *outside* a hole in a field-rebuilt
register would refute this reading, because it would mean some write path was
missed. That run is a register diff, not a pixel comparison, so there is no
`ab_compare.py` prediction to register for it.
