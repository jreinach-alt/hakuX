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

## A2 — verified, with an emulator-only build

A read comparison is blind to A2: `NV_PMC_BOOT_1` reads `00000000` on both
sides, because the endian switch diverges only on **write**.

So the probe gained a **build-time** flag, `PROBE_ALLOW_HAZARDS`, which drops
the hazard refusal. Build-time and not a config key on purpose: a config key
would mean the console binary could be talked into a hazardous write by editing
a file beside it, which is the structural guarantee the hazard list exists to
give. The relaxed build also announces itself in its HELLO line
(`nv2a-probe-HAZARDS-ALLOWED-EMULATOR-ONLY`), so no log from it can be
mistaken for a console run.

Run inside the emulator, writing `FFFFFFFF` to `0x000004`:

```
before:  BOOT_0=02A000A3  BOOT_1=00000000
write accepted
after:   BOOT_0=02A000A3  BOOT_1=00000000
```

**`BOOT_0` is unchanged, so the emulator does not honour the endian switch** —
where the same write on hardware byte-swapped every subsequent access. And
`BOOT_1` reads back `00000000`, so the write does not even latch, which matches
`pmc_write` having no case for it.

**A2 verified from both sides.**

## A5 — verified on the emulator side

A writable-bit sweep of PVIDEO's 12 declared parameter registers inside the
emulator returns `writable=FFFFFFFF` for **every one of them**. Every bit of
every register latches, including:

| register | declared fields | emulator accepts |
|---|---|---|
| `SIZE_IN` | `07FF07FF` | `FFFFFFFF` |
| `SIZE_OUT` | `0FFF0FFF` | `FFFFFFFF` |
| `FORMAT` (13-bit pitch) | `00131FFF` | `FFFFFFFF` |

"No size cap and no pitch handling" is now measured rather than inferred from
`pvideo_write`'s `default:` storing all 32 bits.

The **hardware half is still open**: PVIDEO is inert on the console until
`NV_PMC_ENABLE` bit 28 is set, so all 12 read `0` and latch nothing there. What
the real field widths are needs that bit set on silicon — a targeted
read-modify-write to the register that cost a power cycle, which is a decision
to take deliberately rather than fold into a sweep.

## What a read comparison still cannot reach


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
| A2 endian switch | **verified both sides** (emulator-only build) |
| A3 PMC read regions | **verified both sides** |
| A4 PVIDEO composition | not reachable by a read sweep |
| A5 PVIDEO size cap | **emulator side verified**; hardware half needs PMC_ENABLE bit 28 |

Three of five are now measured on both sides, and a fourth is measured on the
emulator side with its hardware half named precisely. Only A4 -- overlay
composition -- is outside what a register probe can observe at all, because it
is a render behaviour rather than a register one.
