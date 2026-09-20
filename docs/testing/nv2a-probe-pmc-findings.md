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

## WITHDRAWN: two "disagreements" that were an endian flip

**`NV_PMC_INTR_0` bit 7 and `NV_PMC_INTR_EN_0` bits 24-25 are not findings.**
They were reported as silicon disagreeing with `nv2a_regs.h`. They are the same
declared bits, read through a byte swap that the sweep itself caused.

`0x000004` is **`NV_PMC_BOOT_1`**, whose low bit is the MMIO endian switch on
NVIDIA parts of this generation. The write sweep wrote `0xFFFFFFFF` to it at
the second register it touched, and every access afterwards was byte-swapped.

The evidence is not an argument from plausibility:

| check | result |
|---|---|
| `0x000` BOOT_0, read *before* `0x004` is written | `02A000A3` in both runs — the control holds |
| the 126 offsets after `0x004`, write-run vs clean read-run | **124 identical, 2 byte-swap related, 0 unexplained** |
| `NV_PMC_INTR_0` writable `00000080` byte-swapped | `80000000` = `NV_PMC_INTR_0_SOFTWARE`, declared |
| `NV_PMC_INTR_EN_0` writable `03000000` byte-swapped | `00000003` = `HARDWARE|SOFTWARE`, the declared union exactly |

So silicon implements precisely the bits the header declares, in the positions
it declares them. The earlier claim that it implemented bits 24-25 "and none of
the two it does" was wrong, and it was wrong because the instrument had
silently changed underneath the measurement.

`0x000004` also did **not** "latch a value and refuse to restore". The restore
wrote the correct bits to a register that was by then addressed in the other
endianness. The power cycle did not repair a stuck register; it reset the
endian switch.

Two things follow that are worth more than the retracted findings.

**The tree does not model `NV_PMC_BOOT_1` at all.** `nv2a_regs.h` names
`BOOT_0`, `INTR_0`, `INTR_EN_0` and `ENABLE` in PMC, and nothing at `0x004`. So
this emulator has no model of the MMIO endian switch, and a guest that flips it
would diverge from hardware on every subsequent register access. Whether that
matters depends on whether any real title touches it, which is a separate
question from whether it is modelled.

**A name-based hazard list could never have caught this.** `BOOT_1` does not
contain `ENABLE`, `RESET`, `PLL` or anything else a pattern would match. It is
hazardous because of its *semantics* — a register whose write changes how every
later access is interpreted. See "classifying hazards by semantics" below.

## Disagreements that survive

### `NV_PMC_ENABLE` (0x200) — the emulator models nothing at all

`pmc.c` has **neither a read case nor a write case**: it falls through to
`default:`, so reads return 0 and writes are dropped. The clean read sweep —
no writes, therefore no endian flip, and `BOOT_0` verified correct in the same
run — reads **`0x01110000`**.

Writing `0` to it **stopped the console dead**: no ICMP, ARP `FAILED`, power
cycle required. The register is live, it gates something the machine cannot run
without, and the emulator neither reports nor honours it.

*Open, and deliberately not asserted:* the header declares `PFIFO` at bit 8 and
`PGRAPH` at bit 12, while the measured value has bits 16, 20 and 24 set. Those
header positions are the generic NVIDIA ones and may simply not be NV2A's. That
is a question for envytools, not something to conclude from one read — and
given the endian lesson above, a bit-position claim from this sweep has earned
some scepticism.

### `0x000160` reads `0x00000001` where the emulator returns 0

Undeclared and unmodelled. Value taken from the clean read sweep. (The write
sweep saw `0x01000000` here, which is the same value through the endian flip —
consistent, and another confirmation of the mechanism.)

### A 63-dword region after `PMC_ENABLE`

`0x000204`-`0x0002FC` all read `0x00000001` where the emulator returns 0.
**Reported as one region, not 63 findings**: a solid contiguous run of a single
value directly after a live register is the signature of address aliasing or a
fixed unimplemented-read pattern. Telling that apart needs a write next to the
register that already stopped the machine, so it has not been attempted.

The remaining 957 of 1,024 PMC dwords read `0` on silicon, as the emulator
returns for them too.

### `NV_PMC_INTR_0` is not a finding, and was nearly filed as two

Its declared bits read back 0 because it is write-1-to-clear and the sweep
measures latching — that false positive was caught and suppressed. Its
"undocumented bit 7" was the endian artefact above. The same register produced
two spurious findings by two different mechanisms, which is a reasonable
argument for treating any single-run register claim as provisional.

## Reproducibility

Two independent read sweeps, with a reboot between them, returned **1,024 of
1,024 identical values**. `BOOT_0`, `PMC_ENABLE` and the `0x160` constant all
reproduce exactly. The surviving findings are deterministic.

## What this cost, and what the limits are

**One full lockup.** A blind `0` into `NV_PMC_ENABLE` took the processor down
with the GPU, so the watchdog could not fire and a power cycle was the only way
back. In the same 128 registers `0x000004` — `NV_PMC_BOOT_1` — flipped the MMIO
endian switch, so every access for the rest of that run was byte-swapped and
two spurious findings were published before anyone noticed. The power cycle
reset the switch. **Two of 128 written registers did something the sweep could
not undo, and one of them silently corrupted every measurement after it.**

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
