# Mapping the NV2A from the device

A plan for deriving a hardware specification by measurement, and for answering
the question that currently has no evidence behind it: **is a method-level
model of the NV2A capable of matching silicon, or not?**

Cross-reference: #112. Console: `xbox-console-provenance.md`. Calibration:
`xbox-calibration-2026-09-20.md`.

## Why this exists

The SNES was emulated accurately because its hardware was documented. The NV2A
is not. This project's only fidelity metric is pixel comparison against 5,608
goldens, and those goldens cover what one author chose to test. State that is
wrong but not yet observable stays wrong until a game reaches it.

That is not an argument for replacing the emulator. It is an argument that
**the base cannot be evaluated without a fidelity metric that does not depend
on test coverage**, and that building one is cheaper than arguing about it.

### A number that does not mean what it looks like

An earlier draft of this argument cited "121 of 135 PGRAPH registers hardware
modified are unnamed in `nv2a_regs.h`". That is true and it is not a defect
count. `pgraph.c` has **108 `case NV097_*` method handlers and 13 raw register
cases**: the emulator models the NV2A at the *method* level, and those 121
registers are internal state in an abstraction it deliberately does not mirror.
Recorded here because it was nearly used as evidence for a rewrite.

## The measurement that changes things

`pb_fetch_pgraph_registers()` reads `PGRAPH_REGISTER_ARRAY_SIZE` (0x2000 =
2,048 dwords) **locally on the console** by direct MMIO. A method-to-register
delta is one pushbuffer write plus two local block reads. The measurement is
free; the cost is harness overhead.

Measured basis, not estimated:

| quantity | measured |
|---|---|
| median cost of a suite test that renders **and** captures a framebuffer | 330 ms |
| PGRAPH snapshot | 2,048 dwords, local MMIO |
| probe register reads over TCP (upper bound on the slow path) | 2,779 dwords/s |
| full pgraph run, 2,934 tests | ~29 min |

A method diff renders nothing and captures nothing, so it is far below 330 ms.
Method opcodes number roughly 219 — roughly, because the tree declares them
under at least three conventions and **has no machine-readable inventory of its
own method surface**, which is itself a finding.

At 219 methods × 32 operand bits ≈ 7,000 measurements: **~70 s at 10 ms each,
~12 min at a conservative 100 ms.** The interface map is an afternoon,
most of it spent writing the harness change rather than running it.

The technique is already proven in miniature. `pgraph_diff_token.cpp` says its
blacklist "was compiled by comparing the raw diff across a
`NV097_SET_SHADOW_COMPARE_FUNC` to a diff across a `NV097_SET_MATERIAL_ALPHA`".
That is method-to-register mapping, done by hand, for two methods. Nobody
systematised it.

## Workstream 1 — method to register map

**Deliverable:** for every method opcode, the set of PGRAPH registers it
modifies and how, measured from a known-clean state.

**Harness change:** `PGRAPHDiffToken::Capture()` runs at suite `Initialize()`
and `DumpDiff()` at `Deinitialize()`, so today's diff is cumulative per suite.
Move it to per-test — small change in `test_suite.cpp`.

**Semantics come free.** Nothing here reverse-engineers what a register means.
If `NV097_SET_BLEND_ENABLE` always and only toggles bit 2 of register R, then
bit 2 of R *is* blend-enable: the method's name supplies the label, and all
~219 methods are named. Registers no method touches are characterised as
functions of state that can be set, not by name.

**Success criterion:** every method either has a recorded delta or is recorded
as producing none. A method with no observable delta is a result, not a gap.

## PREFLIGHT, run on hardware before committing to any of this

Everything above was costed before anything was tried. The preflight ran on the
console and **falsified part of workstream 1**, which is recorded here rather
than quietly corrected.

### What validated

- **Single-test isolation needs no build.** A config naming one test runs it as
  the whole suite (`Starting [1/1]`), so `Initialize()` → `Deinitialize()`
  brackets exactly that test. Per-test resolution is available today.
- **The blacklist is exactly right.** `pgraph_diff_token.cpp` lists 63
  registers that move regardless of method. All 63 appeared in a measured
  135-register suite delta — a perfect hit, and **47% of a raw diff is noise**.
  Note it is commented out in `DumpDiff()`; it should not be.
- **Deltas are clean.** Two single-test runs moved 299 registers each, of which
  **294 ended at identical values and only 5 differed** — no noise beyond the
  blacklist. The signal is sharp enough to attribute.
- The whole loop ran unattended over `SITE EXEC`.

### What was falsified

The prediction was that `#spot_0_ADD` and `#spot_0_MIN`, which differ only in
blend equation (`NV097_SET_BLEND_EQUATION_V_FUNC_ADD` vs `_V_MIN`, confirmed in
`blend_tests.cpp`), would differ in `NV_PGRAPH_BLEND`.

**They do not.** `NV_PGRAPH_BLEND` ends identical for both. The only five
registers that differ are `CLEARRECT`-family aliases, and their values track
the length of the test's *name*:

```
FD400D64                        ADD 0270000F=>007D0078   MIN 0270000F=>007E007D
FD401864 NV_PGRAPH_CLEARRECTX   ADD 0270000F=>007D0078   MIN 0270000F=>007E007D
FD401964 / FD401C64 / FD401D64  (same values -- context mirrors)
```

That is the on-screen parameter label, not the blend state.

### Why, and what it costs

`Capture()` sits at `test_suite.cpp:341` (suite `Initialize`) and `DumpDiff()`
at `:372` (suite `Deinitialize`). Every test draws its parameter label *after*
its own geometry, and that draw sets its own raster state. So the mechanism
measures **residual state after the label draw and teardown**, not the state
the test established.

**The spec originally said "move it to per-test — small change". That was
wrong.** Per-test still means per-test-*teardown*. What is needed is a capture
point immediately after the test's own draw and before the label is rendered,
which is a change inside the test lifecycle rather than a relocation of two
calls.

Consequence for cost: this cannot be reached by toggling a config flag, so
workstream 1 requires **building the suite from source** — which needs `cmake`,
a dependency deliberately avoided when building the probe. That is a real
addition to the setup, not a change to the order of work.

The core costing is unaffected: the measurement is still two local MMIO block
reads, and harness overhead still dominates. The signal quality result — 5
attributable registers out of 299, with the known noise fully accounted for —
is a better outcome for the technique than the costing assumed.

## Workstream 2 — state dependence, as a screening problem

A method's effect may depend on prior state, which is combinatorial in
principle. It is not necessary to explore it.

Measure each method from **k widely separated base states** (8–16). Identical
delta from all of them means the method is state-independent: one rule, closed
forever. A differing delta puts it on a short context-sensitive list that gets
individual attention.

Cost is k× workstream 1 — still minutes. The expectation, to be falsified
rather than assumed, is that most methods land a value into a field and the
context-sensitive remainder is small.

## Workstream 3 — the event tracer (timing, ordering, interrupts)

Register diffing is completely blind to this class, and it is the class
`../investigations/freeze-analysis.md` chased through thirteen eliminated
hypotheses without a fix. `ROADMAP` item 5 asks for exactly this.

Everything needed is present and was checked:

- `KeInitializeInterrupt`, `KeConnectInterrupt`, `HalEnableSystemInterrupt` are
  declared in nxdk's `xboxkrnl.h`.
- `NV_PTIMER_TIME_0` (`0xFD409400`) is a free-running counter, with
  `NV_PTIMER_NUMERATOR` / `_DENOMINATOR` at `0x200` / `0x210` so the tick rate
  is knowable rather than guessed. PTIMER is enabled on this console
  (`NV_PMC_ENABLE` bit 16 set; the block reads 992/1024 non-zero).
- `NV_PMC_INTR_0` names the unit that raised an interrupt; it was read live
  with bit 24 (`PCRTC`) pending.

**Design:** an ISR timestamps every NV2A interrupt against PTIMER into a RAM
ring buffer, dumped over the probe's existing TCP socket. The console's drive
stays quiescent, so this keeps the power-cycle safety model.

**Deliverable:** a timestamped event stream comparable between hardware and
emulator — the first artifact this project would have for timing bugs.

## Workstream 4 — datapath behaviour, by generated sweep

Blend rounding never reaches a register; it exists only in pixels. Close it by
enumerating a unit's state space and rendering a known input through every
combination.

**The pattern is already in the tree and was not framed as mapping**:
`Blend_tests` carries 1,673 goldens, which is a combinatorial sweep of blend
state. Extend it to units that lack one. Where a space is too large, sample and
fit, then verify on held-out points — the falsifier discipline already used
here.

## Workstream 5 — hazards, and why this one goes first

Hazards cannot be reasoned about in advance. That was established the expensive
way: `NV_PMC_ENABLE`'s engine bits were read out of `nv2a_regs.h` and written
down *before* the run that used them to stop the console dead. Reasoning about
a hazard is not refusing it.

What exists now makes discovery survivable: a generated allow-list, a hazard
list refused inside the probe, a canary re-read after every write that catches
an instrument that has moved, a host-owned journal that names the operation in
flight when a link dies, a poison list, and a supervisor that relaunches over
`SITE EXEC` without a human.

**The one remaining gap is the hard wedge.** `NV_PMC_ENABLE` bit 16 is PTIMER,
so a blind write there stops the system clock and the CPU with it; no watchdog
can run. A relay across the front-panel power button turns that from "a person
walks over" into roughly a minute of automated reboot.

**The hazard map is a by-product.** Upstream already knows `0xFD400200` hangs
the Xbox — `pbkit_ext.cpp` skips it — but that knowledge is a code comment, not
a dataset.

## Order, because they are not independent

1. **Workstream 5** (relay). The enabler for everything unattended.
2. **Workstreams 1 and 2.** One harness change serves both.
3. **Workstream 4.** Extends a technique already proven in-tree.
4. **Workstream 3.** New tooling, and the only route to a bug class nothing
   else can see.

## What this does NOT close, and one thing dropped outright

**Analog output is out of scope, deliberately.** An earlier version of this
plan proposed a capture card for the PVIDEO overlay (#110), on the grounds that
the overlay is composited at scanout and never appears in a framebuffer
readback. That part is correct. The conclusion was not. The chain is
NV2A → RAMDAC → analog → capture ADC → USB: **two conversions and a transport,
against a project whose entire method is bit-identical comparison** (3,374 of
3,379 captures exact). A capture-card artifact cannot support that standard. It
would import perceptual tolerances into one suite while every other suite is
exact, and the resulting "golden" would record what survived the round trip
rather than what the hardware computed.

So #110 stays parked, for a better reason than "we need hardware we do not
have": the only available capture path is too lossy to produce an artifact
worth holding to this project's standard.

Also not closed: internal pipeline stages with no readback, and emergent
behaviour under real game workloads, which is a different problem from a
specification.

## The decision this is actually for

After workstreams 1, 2 and 5 there is a hardware-derived map and the same map
taken from the emulator. Either they converge — the method-level abstraction is
adequate and what remains is a bug list — or they do not, and there is a named
set of state the model cannot represent.

That is the objective evidence for or against the current base, and it is
cheaper to obtain than the argument about whether to obtain it.
