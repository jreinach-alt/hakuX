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

### `NV_PMC_ENABLE` (0x200) — the read landed, the write is unmodelled, and the constant is state-blind

**Emulator side, current as of PR #198:** `pmc_read` returns the bare constant
`0x01110000` for this offset, and `pmc_write` still drops writes via
`default:`. Before #198 there was neither case — reads returned 0 — and the
paragraphs below were first written against that state. The silicon
measurements are unchanged; the sentence about what the emulator answers is
not, so read `pmc.c` rather than this heading before writing "the emulator
models nothing here" into a brief.

The clean read sweep — no writes, therefore no endian flip, and `BOOT_0`
verified correct in the same run — reads **`0x01110000`**.

Writing `0` to it **stopped the console dead**: no ICMP, ARP `FAILED`, power
cycle required. The register is live, and it gates something the machine cannot
run without.

#### A second state: `0x13111113` under a graphics load

The idle sweep left a question open. The header declares `PFIFO` at bit 8 and
`PGRAPH` at bit 12, while `0x01110000` has bits 16, 20 and 24 set and those two
clear. Either the generic NVIDIA positions are not NV2A's, or the engines were
simply idle — a probe XBE does not initialise the GPU.

Reading the same register from inside a running graphics application gives
**`0x13111113`**. **It does not settle that question**, and why not has to be
said before the number is used, because the obvious reading of it is wrong.

**The load state is produced by an indiscriminate write.** `pb_init()` does
this, unconditionally:

```c
pb_OldMCEnable = VIDEOREG(NV_PMC_ENABLE);            // saved
...
VIDEOREG(NV_PMC_ENABLE) = NV_PMC_ENABLE_ALL_ENABLE;  // 0xFFFFFFFF
```

`NV_PMC_ENABLE_ALL_ENABLE` is **`0xFFFFFFFF`**, defined in `lib/pbkit/outer.h`.
`pb_kill()` puts the saved value back. The only other writes to the register in
the whole library clear and re-set bit 12. (nxdk is not vendored in this tree,
so these are cited by symbol rather than by line number — see *Provenance*
below for why, and for what to grep.)

So the word read under load is the read-back of an all-ones write, with one bit
toggled off and on again. A bit reads 1 there **because a 1 was written to
every bit of the register** and the bit is implemented — whatever that bit
gates, and whether or not the engine it gates is doing anything.

| the under-load read establishes | it does not establish |
|---|---|
| **Which bits are implemented**: 0, 1, 4, 8, 12, 16, 20, 24, 25, 28 — ten of them. Every other bit ignores a 1. | **Which engine any bit gates.** An all-ones write sets every implemented bit regardless of what it controls. |

Nor does it discriminate the two candidates. Under "the generic positions are
not NV2A's" — suppose PGRAPH sits at bit 3 — `pb_init()` still writes a 1 to
bit 12, and bit 12 still reads back 1 if it is implemented. The observation is
*identical* under both hypotheses, so it separates neither.

| bit | envytools NV4:G80 | idle, no write issued | after pbkit's all-ones write |
|---|---|---|---|
| 0 | *(unnamed)* | 0 | 1 |
| 1 | *(unnamed)* | 0 | 1 |
| 4 | PMEDIA | 0 | 1 |
| 8 | PFIFO | 0 | 1 |
| 12 | PGRAPH | 0 | 1 |
| 16 | PTIMER | 1 | 1 |
| 20 | *(unnamed)* | 1 | 1 |
| 24 | PCRTC | 1 | 1 |
| 25 | *(unnamed)* | 0 | 1 |
| 28 | PVIDEO | 0 | 1 |

**The information-bearing column is the idle one**, because it is the only one
taken with no write in the run. Bits 16, 20 and 24 are set with the console
otherwise idle; envytools names 16 PTIMER and 24 PCRTC, and a clock and the
CRTC being up in the dashboard is weak corroboration of those two names. That
is the whole of what the bit names get from this pair of reads. It says nothing
whatever about bit 28, which is 0 in the only column that carries information.

**Three sentences are withdrawn** from the first version of this section
(`1eee7098f8`), because the `pb_init()` finding that arrived twenty minutes
later in `42740526d7` invalidates them and did not go back to correct them:

- *"Every bit envytools names behaves as named."* Unsupported: the "running"
  column is a write read back.
- *"The generic layout does describe this chip."* Unsupported, same reason.
- *"Reading the same register from inside a running graphics application
  separates the two."* It does not; see the identical-observation argument
  above.

**"Implemented", not "implemented-and-settable".** A read-back of all-ones
cannot tell "settable, and we set it" from "hardwired to 1" for a bit that read
1 already. Settable is supported only for the seven bits observed 0 idle and 1
after the write — 0, 1, 4, 8, 12, 25, 28 — and strictly the word is the mask as
read *after* pbkit's bit-12 clear-and-re-set. The idle column carries the
settable subset; the headline number is the implemented mask.

`NV_PMC_BOOT_0` was read in the same pass and returned `0x02A000A3` every time,
so this is not the byte-swapped window that produced confident nonsense above.
That control is a real one and not a ritual: `0x02A000A3` byte-swapped is
`0xA300A002`, so the flip would have been unmissable.

#### STILL OPEN: what each bit gates

This is the question #188 and #110 actually need, and no measurement on this
console has answered it. Four of the ten implemented bits — 0, 1, 20, 25 — are
unnamed by envytools, and nothing here rules out one of *those* being NV2A's
PGRAPH or PVIDEO gate.

The experiment that would settle it is a **selective** write: from a known-zero
baseline, set one bit at a time and observe which block responds. That is a
different and considerably more dangerous experiment than the one that was run,
on the register that has already halted this console once.

**Retiring the planned write (below) also retires the only measurement that
would have identified bit 28.** That is a fine trade and it is recorded here as
a trade, not as an answer. Anyone implementing `pmc_write` for #188, or the
PVIDEO half of #110, must treat the bit→engine map as **unknown**. Modelling
bit 12 as PGRAPH and bit 28 as PVIDEO on the strength of this document would be
modelling an assignment no measurement supports, and the error would stay
invisible until a title wrote a partial mask rather than all-ones.

#### The planned write is retired, and that part does stand

Independently of everything above, and this is the most useful thing in the
section. The open item on #188 was to set bit 28 on silicon to find out whether
it is PVIDEO. Two reasons not to, neither of which needs the bit map:

*The state that write was meant to create occurs on its own.* Whatever bit 28
gates, `pb_init()` sets it — along with every other implemented bit — in every
graphics title on the machine. Nothing has to be hand-rolled to reach the
all-bits-set state. (What that state does *not* give you is the attribution,
which is exactly the trade recorded above.)

*The halt is explained.* `NV_PMC_ENABLE_ALL_DISABLE` is the library's own name
for `0`, and `0` is precisely what was written when this console stopped dead.
The danger was never writing this register — every graphics title writes
`0xFFFFFFFF` to it at startup. The danger was writing **zero**.

Reading before writing, to test a premise that was about to cost a risky device
write, is what produced both of those. The read cost nothing and the write was
never needed.

#### What this suggests for #110 — a hypothesis with a cheap test, not a result

The `pvideo` probe run concluded that PVIDEO is inert — 12 registers written,
nothing latched, `orig=0 ones_readback=0 zeros_readback=0` — and prescribed a
targeted `NV_PMC_ENABLE` write to bring the block up first.

**The prescribed write is retired**, per the section above, and that much is
settled. What replaces it is a *hypothesis*: that the pvideo probe calls
`XVideoSetMode` and never `pb_init()`, so it runs with the engines down and
measured a machine it had made itself, and that calling `pb_init()` first is
therefore the prerequisite.

It is a good hypothesis and it is not a result. Three steps between the
measurement and it are unchecked:

1. **That bit 28 is PVIDEO's enable.** Unestablished, above. The whole argument
   that `pb_init()` brings PVIDEO up runs through it.
2. **That the pvideo probe leaves PMC in the state the *PMC* probe observed.**
   `0x01110000` was read by `tools/nv2a_probe`, a different XBE. Whether
   `XVideoSetMode` touches `NV_PMC_ENABLE` is not measured; it is inferred
   across two binaries from "neither calls `pb_init()`".
3. **That enabling the block is *sufficient* for those 12 registers to latch.**
   `orig=0 ones_readback=0 zeros_readback=0` is consistent with a disabled
   block, and with several other things, and nothing here rules those out.

**The test is one run, and the whole cost is one extra printed word.** The next
pvideo run should call `pb_init()` first **and read `NV_PMC_ENABLE` back in the
same run**. That single addition separates three outcomes the hypothesis cannot
currently tell apart:

| PMC reads back | the 12 PVIDEO registers | reading |
|---|---|---|
| `0x13111113` | latch | hypothesis holds; #110 proceeds |
| `0x13111113` | still `0` | the block is up and something else makes them inert — steps 1 and 3 are where to look |
| anything else | either | `pb_init()` did not put PMC where we assumed; step 2 is wrong, and the run says so instead of costing a second one |

Without that read-back, the second and third rows are the *same observation*,
and a run that costs ~90 minutes of the scarcest resource here cannot say which
of them it saw.

#### Provenance of the under-load read — thinner than the rest of this file

This document opens with a console-provenance link, a GPU revision, dated runs
and a table of what each run touched. **The `0x13111113` read does not meet
that standard, and the gap is recorded here rather than left for a reader to
discover.**

| | idle `0x01110000` | under-load `0x13111113` |
|---|---|---|
| date | 2026-09-20, stated in the run table above | **not recorded.** Bounded only by its commit, `1eee7098f8`, 2026-09-20 18:27 -0700 |
| instrument | `tools/nv2a_probe`, clean read sweep, no writes issued | **not recorded.** No XBE or title is named |
| artifact | the two sweeps, 1,024 dwords each | **none in this tree.** No run directory, logcat, or capture |
| repeats | two sweeps, reboot between, 1,024/1,024 identical | **not recorded.** Treat as *n* = 1 |
| endian control | `BOOT_0` = `0x02A000A3` verified in the same run | `BOOT_0` = `0x02A000A3`, stated as read in the same pass |

The "Reproducibility" section below bounds the **idle** sweeps and nothing else;
do not read its 1,024/1,024 as covering this value.

So the under-load word is **not reproducible from this tree**: a later reader
cannot place it relative to a change in the probe, the title or the emulator,
and the only recourse is another device run. What would close this is cheap and
belongs in the same run as #110's test above — name the title, keep the run
directory, and record the read twice.

**No prediction was registered for this work.** An earlier version of PR #203's
body said one was and that both sides matched it; that sentence is withdrawn.
The only PMC/PVIDEO prediction in the tree is
`docs/testing/predictions/2026-09-18-pvideo-overlay-size-pitch-limits.md`, which
is pre-existing, belongs to `lane.cloud-110`, and registers no arm.

**The pvideo figures quoted for #110 above** — 12 registers, `orig=0
ones_readback=0 zeros_readback=0` — have the same gap: no file in this tree
records that run either. They are reproduced as the lane reported them and
should be re-established, not cited onward, by whoever takes #110.

**nxdk is not vendored here.** The `pb_init()` / `pb_kill()` citations above are
to `lib/pbkit/pbkit.c` and `lib/pbkit/outer.h` in an external checkout. The
lane's original text gave bare line numbers (`pbkit.c:2391/2400/2217/2584/2585`,
`outer.h:87/88`); line numbers into a tree this repository does not pin go stale
silently and then read as precise, so the claims above are stated by *symbol*
instead — `pb_OldMCEnable`, `NV_PMC_ENABLE_ALL_ENABLE` = `0xFFFFFFFF`,
`NV_PMC_ENABLE_ALL_DISABLE` = `0` — which survive a renumber. Anyone rechecking
them should grep those symbols rather than trust the offsets.

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

## A read-only survey of every modelled block

19,456 dwords across 17 blocks, **no write issued**, canary verified before and
after each block, 7 seconds. Breadth is affordable precisely because reads
cannot perturb anything.

| block | non-zero | distinct | dominant value | reading |
|---|---:|---:|---|---|
| PVPE | 1024/1024 | 1 | `00000025` | one constant for a whole 4 KiB block |
| PTV | 1024/1024 | 1 | `00000025` | identical to PVPE |
| PRMCIO | 1024/1024 | 11 | `00048328` ×764 | large repeated regions |
| PCRTC | 1014/1024 | 11 | `000D8328` ×766 | large repeated regions |
| PTIMER | 992/1024 | 138 | `00001DCD` ×128 | structured repeats |
| PCOUNTER | 752/1024 | 45 | — | |
| PFIFO | 382/2048 | 9 | — | |
| PGRAPH | **0**/2048 | 1 | `00000000` | reads entirely zero |
| others | sparse | | | PMC 67, PRAMDAC 68, PBUS 65, PRMVIO 64, PFB 45 |

`stubs.c` generates read handlers that `return 0` for the blocks with no `.c`
of their own — PCOUNTER, PVPE, PTV, PSTRAPS among them. So the blocks above
that answer with data are answering where we return nothing.

**These are not 17 defects, and mostly not defects at all.** Three things have
to be said before any of it is quoted:

- **A whole block returning one value is aliasing, not registers.** PVPE and
  PTV each return `00000025` for all 1,024 dwords. That is one fact about the
  block, not 2,048 facts about registers.
- **Values are state-dependent.** These reads were taken with the console
  freshly out of the dashboard and the engines idle. PGRAPH reading entirely
  zero is consistent with the graphics engine simply not being enabled —
  `NV_PMC_ENABLE` reads `01110000` here — rather than with anything being
  wrong. A different machine state gives different values, and that is not
  hypothetical: the same register reads `13111113` under a graphics load.
- **PTIMER is a clock.** Distinct values across a sweep are the counter
  advancing, not distinct registers, and the repeats within it look like
  aliasing again.

What the survey is genuinely good for is a map of which blocks are live on this
silicon and which are silent, taken cheaply and repeatably. What it is not is a
specification, and nothing here should be turned into an emulator change
without a second read in a known state.

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
