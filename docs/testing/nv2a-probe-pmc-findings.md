# What real NV2A silicon says about PMC

First results from the hardware probe (`tools/nv2a_probe/`), measured on the
console in [`xbox-console-provenance.md`](xbox-console-provenance.md) — a V1.1
board, GPU revision 163, MCP revision 212. Cross-reference: issue #112.

Two runs of the PMC block, 2026-09-20:

| run | what it did | registers |
|---|---|---|
| writable-bit sweep | read, write ones, write zeros, restore | 128 attempted |
| read sweep | read only, no writes at all | 1,024 |

## The probe is calibrated against a known answer

`NV_PMC_BOOT_0` reads **`0x02A000A3`** on silicon. `pmc.c` hardcodes exactly
that constant, and the low byte `0xA3` is 163 — the GPU revision the console's
own system-info screen reports. Three independent sources agree, which is what
makes the disagreements below worth reading.

## Disagreements with the tree

### `NV_PMC_ENABLE` (0x200) — the emulator models nothing at all

`nv2a_regs.h` declares it with `PFIFO` (bit 8) and `PGRAPH` (bit 12). `pmc.c`
has **neither a read case nor a write case**: it falls through to `default:`,
so reads return 0 and writes are dropped.

Silicon reads **`0x01110000`** — bits 16, 20 and 24, none of which the header
names. A guest that reads this register to check engine state sees `0` here and
`0x01110000` on hardware.

Writing `0` to it **stopped the console dead** — no ICMP afterwards, ARP
`FAILED`, power cycle required. So the register is live, it gates something the
machine cannot run without, and the emulator neither reports nor honours it.

### `NV_PMC_INTR_EN_0` (0x140) — declared bits and implemented bits disagree

| | |
|---|---|
| declared in `nv2a_regs.h` | `HARDWARE` (bit 0), `SOFTWARE` (bit 1) → `0x00000003` |
| measured writable on silicon | `0x03000000` — bits 24 and 25 |
| what `pmc.c` does | `enabled_interrupts = val`, latching all 32 bits |

Bits 0 and 1 did not latch; bits 24 and 25 did. Write `0xFFFFFFFF` and read
back: the emulator returns `0xFFFFFFFF`, silicon returns `0x03000000`.

### `NV_PMC_INTR_0` (0x100) — an undocumented writable bit

Measured writable mask `0x00000080`: **bit 7 latches**, and no field in
`nv2a_regs.h` names it.

The register's *declared* bits behave correctly and are **not** a finding. It
is write-1-to-clear (`pending_interrupts &= ~val`), and the sweep measures
latching, so declared status bits legitimately read back 0. Across the two runs
the register read `0x00000001` once and `0x01000000` (bit 24, the declared
`PCRTC` field) the other — a pending-interrupt register is volatile, and seeing
a declared bit appear as status is the expected behaviour rather than a defect.

### Registers the emulator returns 0 for, and silicon does not

`0x000160` reads a constant `0x00000001`. Undeclared, unmodelled.

`0x000204`–`0x0002FC` — 63 consecutive dwords immediately after `PMC_ENABLE` —
all read `0x00000001`. **This is reported as one region, not 63 findings.** A
solid contiguous run of a single value directly after a live register is the
signature of address aliasing or a fixed unimplemented-read pattern, not of 63
distinct registers each holding 1. Distinguishing the two needs a write, and
the region sits next to the register that already stopped the machine once, so
it has not been attempted.

The remaining 957 of 1,024 PMC dwords read `0` on silicon, which is what the
emulator returns for them too.

## What this cost, and what the limits are

**One full lockup.** A blind `0` into `NV_PMC_ENABLE` took the processor down
with the GPU, so the watchdog could not fire and a power cycle was the only way
back. In the same 128 registers `0x000004` latched `0x01000001` and would not
restore — the power cycle did return it to `0x00000000`, confirmed by the read
sweep. **Two of 128 written registers were irreversible in-session.**

The soft-reset recovery tier was never exercised. The probe did **not** recover
from this hang without help.

Consequently the write sweep now defaults to declared registers only, a
generated hazard list is refused inside the probe (engine-enable, reset,
pushbuffer cache and the three PLL coefficient registers), and a failed restore
stops the run. Applied to PMC those defaults would have written 2 registers
instead of 128 — and those 2 are where every disagreement above came from.

**What the method cannot see.** The ones/zeros sweep measures *latching*. It is
blind to write-1-to-clear semantics, to bits whose value is driven by hardware,
and to any register whose behaviour depends on ordering or on another
register's state. A zero writable mask means "did not latch", never "read
only".
