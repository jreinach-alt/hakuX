# lane cloud-188 (#188): NV_PMC_ENABLE storage over its ten implemented bits

Cloud-class lane, 2026-09-25, base `f2e8ef8ba8` (after PR #211's fold). PR #236.

## What changed

- `hw/xbox/nv2a/pmc.c`: `pmc_read` returns `d->pmc.enable`; `pmc_write` gains
  a `case NV_PMC_ENABLE:` that stores `val & 0x13111113` and does nothing else;
  new `pmc_reset()` sets `0x01110000`. The comment on the write arm is the one
  place the measurement, the "gate nothing" rule and the 16/20/24 choice are
  written down, and the read arm points at it.
- `hw/xbox/nv2a/nv2a_int.h`: `pmc.enable` field, `pmc_reset` prototype.
- `hw/xbox/nv2a/nv2a.c` (not on the board brief's file list; free in
  territory.toml since wave 123, no open PR claims it): `nv2a_reset()` calls
  `pmc_reset()`, and the register is saved in a `nv2a/pmc-enable` VMState
  subsection. It is a subsection, not a new field in the main list, so a
  savestate from before this change still loads; `nv2a_pre_load()` calls
  `pmc_reset()` first, so such a state loads with the reset value.
- The selftest (`docs/testing/pmc_enable_selftest.{sh,c}`) now extracts
  `pmc_write` and `pmc_reset` too and runs them: 38 checks.

## The model's choices

1. **Mask `0x13111113`** = the one under-load read (#203). It is n = 1 with no
   artifact in the tree; the findings doc says so in its Provenance section.
2. **Gate nothing.** No engine reset, no halt on 0, and nothing else reads
   `pmc.enable`. The selftest enforces this three ways: the whole stub state
   is byte-compared across every write to the register with live interrupt
   state seeded; `nv2a_update_irq` must not be called; and any other call
   (for example `pgraph_reset`) has no stub, so it fails to compile.
3. **Bits 16/20/24 are storage**, not hardwired to 1. That is a choice, since
   no read has been taken after a write that clears them. The falsifier is in
   the pmc.c comment: write `0x13101113` on silicon (only bit 20 cleared) and
   read it back. The selftest line `0x1000: 16/20/24 = storage` asserts the
   choice, and mutant U5 (hardwired) turns it red.
4. **A write replaces the whole word whatever `size` is.** INTR_EN_0 already
   works this way. A sub-dword write has not been measured.

## Measured (desktop selftest; no device, no arm)

`bash docs/testing/pmc_enable_selftest.sh`: 38 checks, 0 failures.

`python3 docs/lanes/cloud-188/mutants.py`: 14 mutants, 0 unexpected.

| id | mutant | red on |
|---|---|---|
| U0 | none | green, 38/0 |
| U1, U1b, U1c | unmasked; mask minus bit 1; mask plus bit 2 | `FAIL pb_init all-ones` |
| U2 | constant read (the pre-#188 model) | `FAIL pb_init all-ones` |
| U3 | write dropped | `FAIL pb_init all-ones` |
| U4 | reset 0 | `FAIL NV_PMC_ENABLE reset` |
| U5 | 16/20/24 hardwired | `FAIL 0x1000: 16/20/24 = storage` |
| U6 | write calls `nv2a_update_irq` | `had a side effect` |
| U7 | write ANDs into `enabled_interrupts` | `other state CHANGED` |
| U8 | `pgraph_reset` on a write of 0 | does not compile |
| U9 | a write arm in #190's region | `REFUSED` |
| U10 | the arm spelled `case 0x200:` | green (control) |
| U11 | `pmc_reset` renamed | anchors, exit 2 |

**U7 was green on the first draft.** Interrupt state was seeded non-zero for
only one write, and `enabled_interrupts &= 0x13111113` leaves `0x1` unchanged.
The fix seeds that state for the whole write sequence. Don't go back to
seeding it only at the end.

## Older suites this change supersedes

- `docs/lanes/pmc188/mutants.py`: 9 of its 14 rows now disagree, as they
  should. M1-M2b asserted that `pmc_write` had **no** arm for 0x200 and never
  mentioned `0x01110000`. That was the invariant until this lane, and those
  guards have been removed from the .sh on purpose. M3's anchor
  (`r = 0x01110000;`) is gone, so M3 runs unmutated. M0/L1/L2 wait for
  "16 checks". U0-U11 above replace it.
- `docs/lanes/cloud190/mutants.py`: it can't start, because N8's anchor is the
  old constant read. A scratch copy with only N8's anchor and the check count
  updated ran 22/24 as expected. The two that differ are expected: PRE (the
  base pmc.c has no `pmc_reset`, so exit 2 instead of 1), and K1, the
  documented "spanning range" hole (`case 0x100 ... 0x400:`). gcc now catches
  K1 as a duplicate of the 0x200 arm. #190's region guard in the .sh excludes
  0x200 itself and is otherwise unchanged.

Neither file is edited here. They belong to folded lanes, and each records
what its guard was at its own fold.

## Not done, and why

- **No arm, no prediction.** No golden can see a PMC register read (the
  reasoning PR #198 recorded).
- **No desktop or Android build.** The desktop build can't run on this host
  (AGENTS.md). `nv2a.c` and the in-tree `pmc.c` were not compiled here, so the
  VMState subsection is checked by reading only. It follows `hcd-ohci.c`'s
  form in this tree, with `.needed` omitted, which `vmstate_section_needed`
  treats as always sent. `check_android_guards.py` passes.
- **Bit 28 / PVIDEO** is #110's, as the brief says.
