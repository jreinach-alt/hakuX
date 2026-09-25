# Audit pass 1 — PR #203 `claude/pmc-enable-under-load`

*docs/testing: NV_PMC_ENABLE under load settles the bit positions, and retires
the planned write*

Scope: the diff (`gh pr diff 203`), two files, +78/-8. Head `42740526d7`,
base `origin/master`. Pass 1 reads the diff; unchanged text is cited only
where the diff's meaning depends on it.

**Summary: 2 HIGH, 3 MEDIUM, 3 LOW.** The arithmetic in the diff is right —
`0x13111113` is exactly bits 0, 1, 4, 8, 12, 16, 20, 24, 25, 28, `0x01110000`
is exactly 16, 20, 24, and `0x02A000A3` byte-swapped is `0xA300A002`, so the
endian control does discriminate. What is wrong is what the number is taken to
prove, and how stale the file it lands in has become.

---

## HIGH-1 — the running read cannot establish the bit layout, and the diff's own second half says so

`nv2a-probe-pmc-findings.md`, the block added at the "*This was left open and
is now closed, by a read*" paragraph, against the block added below it at
"### Why it reads `0x13111113`".

The first block claims:

> Reading the same register from inside a running graphics application
> separates the two, and needs no write.

> Every bit envytools names behaves as named: PTIMER and PCRTC are up when the
> machine is otherwise idle, and PMEDIA, PFIFO, PGRAPH and PVIDEO come up only
> when something draws. The generic layout does describe this chip.

The second block, forty lines later in the same diff, establishes:

> `pb_init()` does this, **unconditionally** […]
> `VIDEOREG(NV_PMC_ENABLE) = NV_PMC_ENABLE_ALL_ENABLE;` […] `0xFFFFFFFF`
> […] the value read from inside a graphics application is the read-back of an
> all-ones write.

These cannot both stand. If the running value is the read-back of `0xFFFFFFFF`,
then bits 0, 1, 4, 8, 12, 25 and 28 read 1 **because a 1 was written to every
bit of the register**, not because PMEDIA, PFIFO, PGRAPH and PVIDEO "come up
when something draws." An all-ones write sets every implemented bit whatever
each bit gates. The running read therefore carries exactly one fact — *which
bits are implemented* — and zero bits of information about *which engine each
one controls*.

Nor does it "separate the two". The two candidates were (a) the generic NVIDIA
positions are not NV2A's, and (b) the engines were idle. Under (a) — suppose
PGRAPH is at bit 3, not 12 — `pb_init()` still writes a 1 to bit 12 and bit 12
still reads back 1 if implemented. The observation is identical under both
hypotheses, so it discriminates neither.

The only information-bearing observation in the table is the **idle** column:
bits 16, 20, 24 set with nothing running, of which envytools names 16 PTIMER
and 24 PCRTC. A clock and the CRTC being up in the dashboard is weak
corroboration of those two names. It is not "every bit envytools names behaves
as named", and it says nothing at all about bit 28.

The second commit (`42740526d7`) added the correct explanation and did not go
back and correct the inference in the first (`1eee7098f8`) that it invalidates.
The PR body still leads with the invalidated claim, and so does the table's
framing.

**Failure scenario.** A lane picks up #188 to implement `pmc_write` (or the
PVIDEO half of #110) and needs to know what to gate on. It reads this document
— the repository's silicon-of-record for PMC — finds "The generic layout does
describe this chip" and "Every bit envytools names behaves as named" presented
as a closed question, and models `pmc_write` so that bit 12 gates PGRAPH and
bit 28 gates PVIDEO on NV2A. Four of the ten implemented bits (0, 1, 20, 25)
are unnamed by envytools and this measurement gives no way to tell whether one
of *those* is the PGRAPH or PVIDEO gate on this chip. The emulator then models
a bit assignment no measurement supports, and the error is invisible until a
title writes a partial mask rather than all-ones.

**Remedy.** State the actual result: the running read establishes the
**implemented-bit mask** and nothing about bit semantics, because the write
that produced it was indiscriminate. Withdraw "Every bit envytools names
behaves as named", "The generic layout does describe this chip", and "separates
the two", in the table's prose and in the PR body both. If the bit→engine map
is still wanted, the experiment that would give it is a *selective* write (set
one bit at a time from a known-zero baseline and observe which block responds),
which is a different and more dangerous experiment than the one that was run —
and note that retiring the planned write, on safety grounds, also retires the
only measurement that would have identified bit 28. That is a fine trade, but
it must be recorded as an open question, not a closed one.

## HIGH-2 — the gap-list row is stale by 62 commits, re-asserts a fact #198 falsified, and conflicts

`nv2a-hardware-gap-list.md`, the single changed row. The diff writes:

> | `NV_PMC_ENABLE` (0x200) | declared with PFIFO/PGRAPH bits; `pmc.c` has
> **no read and no write case**. Silicon reads `0x01110000` idle and
> **`0x13111113` with a graphics app running**; writing 0 halted the console
> outright | #188 |

`origin/master` line 38 of the same file now reads:

> | `NV_PMC_ENABLE` (0x200) — **read landed, write still nowhere** | silicon
> reads `0x01110000` with the console idle; `pmc_read` has returned that
> constant since PR #198. `pmc_write` still drops it via `default:`,
> deliberately — writing 0 halted the console outright, and what each bit gates
> is unestablished | #188 |

So the diff's "`pmc.c` has **no read and no write case**" is false as of PR
#198, which landed `pmc_read`. The branch is 62 commits behind and its row is
the pre-#198 text with one clause added. Master's row also already contains the
correct form of HIGH-1 — "what each bit gates is unestablished" — which this
PR's row drops.

This is not hypothetical staleness: `git merge-tree origin/master HEAD` reports

```
CONFLICT (content): Merge conflict in docs/testing/nv2a-hardware-gap-list.md
```

and the PR reports `mergeable: CONFLICTING`, `mergeStateStatus: DIRTY`. The two
`build` checks on the rollup are `SUCCESS` and predate the conflict — GitHub
builds the merge commit, so a green rollup beside a dirty merge state is stale
evidence, not a passing gate.

Related, in the PR body rather than the diff: "The emulator read `0x00000000` —
#188 from the guest's side." After #198, `pmc_read` returns `0x01110000`, so
either that emulator read predates #198 and the sentence is stale, or it was
taken on this 62-commit-old base. Either way it cannot be published as the
current emulator behaviour.

**Failure scenario.** The conflict is resolved by taking the branch's side (the
natural choice — it is the side the PR is *about*), and master's gap list
regresses to claiming `pmc.c` has no read case. The board dispatches a lane
against #188 to implement the PMC read that already exists, and that lane
spends its session rediscovering #198. Meanwhile the correct caveat "what each
bit gates is unestablished" is deleted from the one row most likely to be read
by whoever implements `pmc_write` — compounding HIGH-1 at the exact point of
use.

**Remedy.** `git merge origin/master` on the branch and resolve this row by
starting from **master's** text, adding only the new fact (the under-load value
and what it does and does not establish). Re-check the emulator-read sentence in
the PR body against post-#198 behaviour. Do not rebase.

## MEDIUM-1 — "the prerequisite is `pb_init()`" is a hypothesis published as a settled result

The added "### What this unblocks for #110" section:

> That diagnosis was right and the remedy is unnecessary. The probe XBE calls
> `XVideoSetMode` and never `pb_init()`, so it runs with PGRAPH, PFIFO, PMEDIA
> and PVIDEO all down […] The prerequisite is `pb_init()`, not a hand-rolled
> write.

Three unstated steps sit between the measurement and this conclusion:

1. That bit 28 is PVIDEO's enable — unestablished, per HIGH-1. The whole
   argument that `pb_init()` brings PVIDEO up runs through it.
2. That `hardware/probe/pvideo` leaves PMC in the same state the *PMC* probe
   observed. `0x01110000` was read by `tools/nv2a_probe`, a different XBE.
   Whether `XVideoSetMode` touches `NV_PMC_ENABLE` is not shown — it is
   inferred across binaries from "neither calls `pb_init()`".
3. That enabling the block is *sufficient* for those 12 registers to latch. The
   probe found `orig=0 ones_readback=0 zeros_readback=0`; a disabled block
   explains that, but so would several other things, and nothing here rules
   them out.

**Failure scenario.** A lane takes #110 as unblocked, adds `pb_init()` to
`hardware/probe/pvideo`, and spends a device run (~90 min, and the device is
the scarce resource here) to find the 12 registers still reading zero — because
the gating bit was one of the four unnamed ones, or because `XVideoSetMode`
already enables what it needs, or because inertness had another cause. The
document told it the prerequisite was known.

**Remedy.** Downgrade to what it is: a well-argued hypothesis with a cheap test.
Say that the next `hardware/probe/pvideo` run should call `pb_init()` first
**and read `NV_PMC_ENABLE` back in the same run**, so the run distinguishes
"block was down and is now up, registers latch", "block is up and registers
still do not latch", and "`pb_init()` did not change PMC here". Keep #110's
prescribed hand-rolled write retired — that part is sound and is the safety
win — but say the replacement is untested.

## MEDIUM-2 — the headline number has no provenance

`0x13111113` is the number the whole PR turns on, and the diff records nothing
about where it came from: no date, no run id, no artifact path, no name for the
"running graphics application", no logcat or capture reference. The document it
lands in opens with precisely that discipline — a console-provenance link, a
GPU revision, "Two runs of the PMC block, 2026-09-20", a table of what each run
did and how many registers it touched. The new section meets none of it.

The PR body says "Prediction was registered before the run and both sides
matched it." No prediction file for this work exists on the branch
(`git ls-tree -r HEAD docs/testing/predictions | grep -i pmc` → nothing; the
only PMC/PVIDEO hit is `2026-09-18-pvideo-overlay-size-pitch-limits.md`,
unrelated and pre-existing), the PR body names no path or sha, and no
`[job.arms]` verdict is cited.

**Failure scenario.** A later reader needs to know whether this read predates
or postdates a change to the probe, the title, or the emulator — the exact
question that produced the two withdrawn findings recorded higher up in this
same file, and the same question that makes a stale capture read as a live
defect. With no date and no artifact, the number cannot be placed in time or
re-derived, and the only recourse is another device run.

**Remedy.** Add provenance in the document beside the value: the date, which
XBE/title produced the load, how the read was taken, and the artifact or run
directory. Either cite the registered prediction by path and sha, or drop the
claim that one was registered.

## MEDIUM-3 — the PR body does not follow the lane template, so `Files:` names nothing

`docs/testing/jobs/roles/lane.md` gives the body template and says why:
"The board reads `Files:` from every open PR to keep two lanes off one file. A
path you edit that is not on that line is a collision nothing can see." The
body of #203 has no `Lane:`, `Base:`, `Files:`, `Prediction:` or
`Needs device:` lines at all — it opens straight into prose.

**Failure scenario.** The board, seeing no open PR that declares
`docs/testing/nv2a-hardware-gap-list.md`, dispatches another lane onto it. That
is not speculative — the collision this PR already has with master is on that
exact file, and an undeclared file is how the second one arrives.

Note `gh pr edit` applies nothing on this host, including `--body-file`; the
body has to be PATCHed through `gh api` and read back.

**Remedy.** Fill in the template header, with `Files:` matching
`git diff --stat origin/master...HEAD` (both paths), and
`Prediction: none: analysis-only` or the real path and sha per MEDIUM-2.

## LOW-1 — no `docs/lanes/<lane>/NOTES.md`

Definition of done item 3. `git ls-tree -r HEAD docs/lanes` has no entry for
this lane. The next lane on #188 or #110 has no record of what was tried, and
in particular no record of the "a probe XBE does not initialise the GPU"
insight except as a conclusion inside a findings doc.

## LOW-2 — "implemented-and-settable" overclaims for bits 16, 20 and 24

> **`0x13111113` is the implemented-and-settable bit mask of `NV_PMC_ENABLE` on
> this silicon**

Bits 16, 20 and 24 already read 1 *before* any write (the idle value). A
read-back of all-ones cannot distinguish "settable, and we set it" from
"hardwired to 1" for a bit that was already 1. "Every other bit ignores a 1" is
supported; "settable" is supported only for the bits observed at 0 idle and 1
after the write (0, 1, 4, 8, 12, 25, 28). Strictly the value is also the mask
as read *after* pbkit's bit-12 clear-and-re-set, which the text notes and then
elides. Say "implemented" and let the idle column carry the settable subset.

## LOW-3 — the pbkit citations index a tree that is not named

`pbkit.c:2391/2400/2217/2584/2585` and `outer.h:87/88` are load-bearing for the
whole second half, and nxdk is not vendored in this repository — the citations
cannot be checked from the tree and no nxdk commit, tag or version is given.
Line numbers into an external checkout go stale silently and then read as
precise. Pin the nxdk sha (or quote enough surrounding source that the claim
survives a renumber). The quoted code itself is internally consistent and the
`ALL_ENABLE` = `0xFFFFFFFF` / `ALL_DISABLE` = `0` pair explains the halt
convincingly; this is about durability, not doubt.

---

## What holds

Worth saying plainly, because most of the diff is good and remediation should
not touch it:

- The bit decomposition is exact. `0x13111113` → {0,1,4,8,12,16,20,24,25,28};
  `0x01110000` → {16,20,24}. Both tables' columns are right.
- The `NV_PMC_BOOT_0` = `0x02A000A3` control is a real control, not a ritual
  one: the byte-swapped form is `0xA300A002`, so it would have been obvious.
  Carrying the endian control forward from the withdrawn findings is exactly
  right.
- **Retiring the planned write is the correct call and the most valuable thing
  in the PR**, independent of HIGH-1. The register has halted this console
  once; `outer.h:88` naming `0` `ALL_DISABLE` explains that halt; and the
  argument that no hand-rolled write is needed to reach the all-bits-set state
  stands on `pb_init()`'s unconditional `0xFFFFFFFF` alone. The reasoning for
  *why* it is unnecessary needs the HIGH-1 correction; the decision does not.
- Reading before writing, to test a premise that was about to cost a risky
  device write, is the right instinct and should be said so in the remediation
  notes rather than lost.

## Verdict

HIGH present → **`needs-remediation`**. HIGH-1 and HIGH-2 must be fixed;
MEDIUM-1, MEDIUM-2 and MEDIUM-3 must be fixed. The LOWs are the lane's call.

HIGH-2 requires `git merge origin/master` before anything else — the PR cannot
fold in its current state regardless of the rest.

— cloud audit pass 1, 2026-09-21
