# lane.pmc188 -- #188: NV_PMC_ENABLE reads 0, silicon reads 0x01110000

Status: done. One hunk in `pmc_read`, plus a committed selftest.
PR #198.

## The brief

`hw/xbox/nv2a/pmc.c:pmc_read` had no `case NV_PMC_ENABLE` (0x200); the read
fell to `default: r = 0`. Two independent read-only sweeps on real NV2A
silicon, with a reboot between them and 1,024/1,024 dwords reproducible, read
`0x01110000` there. Scope was the read only.

## What changed

One case in `pmc_read` returning the bare constant `0x01110000`, with the
provenance and the two non-claims in the comment beside it.

`nv2a_regs.h` is **not** in the diff after all, though the brief listed it:
`NV_PMC_ENABLE` is already `#define`d at `nv2a_regs.h:72` as `0x00000200`, so
there was nothing to add. The case reuses it. No new bit-field macros were
invented -- see below for why that is the whole point.

`pmc_write` is byte-for-byte untouched. Not asserted from reading the diff
alone: `sha256` of `sed -n '/^void pmc_write/,$p'` over the function is
`20150c04ab69...` on `HEAD~` and identical on this branch, and the single diff
hunk's header names `uint64_t pmc_read`.

## What is NOT claimed, and why the constant is bare

`nv2a_regs.h` puts `_PFIFO` at bit 8 and `_PGRAPH` at bit 12. The measured
value sets bits 16, 20 and 24. Those two statements do not reconcile, and #188
is explicit that they are not meant to yet: the header positions are the
generic NVIDIA ones and may simply not be NV2A's, and a *different*
bit-position claim from this same sweep has already been retracted as an endian
artefact. Settling it needs an envytools cross-reference that this lane was not
asked for and did not do.

So: no field decomposition, no `SET_MASK`, no new macros. A bare constant is
the honest shape -- it says "silicon reads this" and nothing about why.

The write side is untouched for a blunter reason. Writing 0 to this register
**halted the physical console** in the sweep that found it -- no ICMP
afterwards, ARP `FAILED`, power cycle required. Modelling a write means
modelling a halt on a guess about which bit gates which engine, which is
exactly the guess above. Writes stay a silent no-op via `pmc_write`'s
`default`.

**A note for whoever does take the write side.** The read now returns a
non-zero value, which is a change in what a guest sees before it decides to
write anything. A guest that reads `PMC_ENABLE`, clears a bit and writes back
now computes its write from `0x01110000` rather than from `0`. The write is
still discarded, so nothing happens either way today -- but the day the write
path becomes live, the value being written will already have been shaped by
this commit. That is an argument for landing the read first, not against it;
it just means the write lane cannot treat the two as independent.

## The falsifier

`docs/testing/pmc_enable_selftest.sh` + `.c`. It extracts `pmc_read` from
`pmc.c` **by anchor on every run** and compiles it against stubs, following
`audio_starve_selftest.sh` and `glerr_report_selftest.sh`. A worktree cannot
build the native side, and a pasted copy of the function drifts from the
original silently and then certifies code that is no longer in the tree.

The register constants are not restated in the test: it `#include`s the real
`nv2a_regs.h`, so "0x200 reads 0x01110000" is asserted about the offset the
header actually defines.

Red then green, on this tree:

```
before:  FAIL NV_PMC_ENABLE   addr=0x200 got=0x00000000 want=0x01110000
         8 checks, 1 failures      exit 1
after:   ok   NV_PMC_ENABLE   addr=0x200 -> 0x01110000
         8 checks, 0 failures      exit 0
```

Seven of the eight checks are controls and were green in both runs -- the red
run failed on one line, for the stated reason, not because it could not build.

### The guards were checked against mutants, not assumed

A check nobody has seen fail is decoration, and an exit code is a coarse
discriminator -- a script that exits non-zero on everything "catches"
everything. Seven mutants, each in its own temp tree (never by swapping the
real path, which leaves the old code in the worktree):

| mutant | expected | got | failed on |
|---|---|---|---|
| M0 unmutated tree | exit 0 | exit 0 | -- (this is the one that makes the rest mean something) |
| M1 `pmc_write` gains a `case NV_PMC_ENABLE` | exit 1 | exit 1 | `REFUSED: pmc_write has a case for NV_PMC_ENABLE` |
| M2 `pmc_write` uses `0x01110000` | exit 1 | exit 1 | `REFUSED: the measured read-back constant appears in pmc_write` |
| M3 the read reverted to 0 | exit 1 | exit 1 | `NV_PMC_ENABLE got=0x00000000` |
| M4 the case widened to `+4` | exit 1 | exit 1 | `unmodelled 0x204 got=0x01110000` |
| M5 constant lands on `BOOT_0`'s arm | exit 1 | exit 1 | `NV_PMC_BOOT_0 got=0x01110000` |
| M6 `pmc_read` renamed | exit **2** | exit 2 | `anchors not found in pmc.c` |
| M7 trace logs 0 instead of `r` | exit 1 | exit 1 | `value is right but the trace is wrong` |

Each went red on its own line, not all on one reason. M6 is the one that
matters most for the long run: a silent mis-extract compiles to nothing and
passes, so the anchor failure is a distinct exit code with its own message.

M1 and M2 are anchored on the **code** -- a `case` label and the constant --
not on prose, because a comment in `pmc_write` mentioning `NV_PMC_ENABLE` is
legitimate and in fact likely, and a grep for the words would go red against a
correct file.

### What the selftest is not: it is not wired to anything

It runs when someone runs it. `jobs-selftest.yml` is scoped to
`docs/testing/jobs/**` -- the host job scripts -- and is not a runner for
emulator-code checks; `audio_starve_selftest.sh` and
`glerr_report_selftest.sh` are unwired in exactly the same way, and are each
cited in an audit that ran them by hand. I did not wire this one in:
`.github/workflows/` and `docs/testing/jobs/` are outside this lane's files,
and adding a call to another job's tick makes every existing fixture for that
job drive this code, which is a bigger change than the one #188 asked for.

Stated rather than left implicit, because a gate nobody invokes is not a gate.
If someone wants these three to run per-PR, that is its own small piece of
work and it should cover all three, not just this one.

## What the next lane should not repeat

- **Do not re-derive the bit layout from this one value.** Three bits set at
  16/20/24 is exactly the sort of pattern that invites a story. #188 says the
  header positions are unconfirmed *and* that a sibling bit-position claim from
  the same sweep was already retracted as an endian artefact. The
  cross-reference is the work; the arithmetic is not.
- **Do not queue a device arm for this.** There is no golden that can see it. A
  PMC register read never reaches a framebuffer, so an A/B on captures would
  come back "no change" and that verdict would be vacuous rather than
  informative. That is why `Prediction: none` here, and it is also the reason
  #188 notes no golden could ever have found this.
- **Do not reach for the write side without the envytools reference.** The
  cost of getting it wrong was already paid once, in a full console lockup.
- The extraction anchors are `^uint64_t pmc_read(` and `^void pmc_write(`, and
  the test assumes the second follows the first. Reordering the file is fine;
  the test will tell you it happened rather than quietly testing an empty
  string.
