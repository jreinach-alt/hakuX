# Gap list A, verified from both sides

`nv2a-hardware-gap-list.md` lists five things modelled nowhere, each
established from the tree plus a hardware measurement. This verifies them
against the emulator *empirically* rather than by reading `pmc.c`.

Method: the NV2A probe, built as a bootable ISO and run **inside** a desktop
build of this tree. Under slirp the guest reaches the host at `10.0.2.2` and
takes an address by DHCP, so the probe gained a config file
(`d:\nv2a_probe.cfg`) and the same binary now runs on the console and under
emulation. It read the whole PMC block on both.

**PMC, 1024 dwords: 959 identical, 65 different.**

## Verified, both sides

| | hardware | emulator | |
|---|---|---|---|
| **A1** `NV_PMC_ENABLE` (0x200) | `01110000` | `00000000` | **confirmed** |
| **A3** `0x160` | `00000001` | `00000000` | **confirmed** |
| **A3** `0x204`–`0x2FC` | `1` on all **63** dwords | `0` on all 63 | **confirmed** |

The 65 differing registers are exactly `0x160`, `0x200`, and the 63-dword
region. Nothing else in PMC disagrees, which is worth stating: the emulator
matches silicon on 959 of 1024 PMC dwords.

This is the first time A1 and A3 have been checked against a running emulator
rather than inferred from `pmc.c` having no `case`. The code reading was right,
and after several wrong readings this session that was worth confirming.

## A2 cannot be seen this way, and that is the finding

| | hardware | emulator |
|---|---|---|
| **A2** `NV_PMC_BOOT_1` (0x004) | `00000000` | `00000000` |

They **match**. A2 is the MMIO endian switch, and its divergence is
**write-only**: hardware honours a write by byte-swapping every subsequent
access, and this tree does nothing. A read comparison is structurally blind to
it.

Confirming A2 from the emulator side needs a *write* to `0x004` — the register
that byte-swapped an entire PMC run on hardware and is on the probe's hazard
list for exactly that reason. It would be safe under emulation, where a wedged
guest costs nothing, but it is not safe with the same binary pointed at the
console, so it wants a deliberate emulator-only mode rather than a relaxed
hazard list.

A2 therefore stands on its original evidence: the hardware write sweep, plus
`nv2a_regs.h` not naming `0x004` and `pmc.c` having no handler for it.

## A4 and A5 are not reachable by this method either

Both are PVIDEO: overlay composition (`d->vga.enable_overlay` commented out)
and the absent size cap (`pvideo_write`'s `default:` storing all 32 bits). Both
are **write and render** behaviours, so a read sweep says nothing about them,
and PVIDEO is inert on hardware until `NV_PMC_ENABLE` bit 28 is set.

## Score for A

| item | status |
|---|---|
| A1 `NV_PMC_ENABLE` | **verified both sides** |
| A2 endian switch | read values match; divergence is write-only, unchanged |
| A3 PMC read regions | **verified both sides** |
| A4 PVIDEO composition | not reachable by a read sweep |
| A5 PVIDEO size cap | not reachable by a read sweep |

Two of five moved from "inferred from the tree" to "measured on both sides".
The other three are not failures of the measurement; they are outside what a
read comparison can observe, which is worth knowing before anyone plans around
it.
