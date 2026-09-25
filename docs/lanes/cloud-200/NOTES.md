# lane cloud-200 -- #200 static header-hole enumeration

Brief: enumerate every PG_SET_MASK write against nv2a_regs.h's declared masks
and report which bits no method handler can write. Analysis only; nv2a_regs.h
and pgraph.c were not edited.

## Did

- `docs/testing/pgraph_set_mask_coverage.py` parses the header's PGRAPH
  register and field defines and every write in `pgraph/pgraph.c`
  (PG_SET_MASK, method_fast[] via mask_lut[], whole-word pgraph_reg_w). It
  classifies each write site by its enclosing function (method / MMIO / other).
- `docs/testing/pgraph-set-mask-coverage.md` has the result, the table and
  the caveats.

## Result

- 75 register families written by a method; 55 are stored whole, 20 field by field.
- 3 / 75 have a declared field no handler writes (TRAPPED_ADDR.DHV,
  CSV0_D.FOG_MODE, CSV1_A.T{0,1}_{ENABLE,MODE,TEXTURE}). That is small and it
  narrows the thesis.
- 20 / 20 field-rebuilt registers have unwritten undeclared bits (287 bits in
  total). In 15 of them the written mask is exactly the declared mask.
- All three of PR #201's measured divergences fall inside the static holes.

## Do not repeat

- DIMENSIONALITY width mismatch: already refuted by the board (2026-09-21).
  This script counts masks, not value ranges, so it cannot see truncation.
- Do not fold registers by address alone. CONTROL_1..3 sit at CONTROL_0 + 4n
  and are distinct. The fold is keyed on `X0 + slot * 4` in the source.

## Next

A widened run with PR #201's per-test diff patch, dumps committed, checking
every console-moved bit against the "undeclared, never written" column. A bit
that moves outside a hole in a field-rebuilt register would mean the script
missed a write path. That run needs a device and the tests tree, not an arm.
