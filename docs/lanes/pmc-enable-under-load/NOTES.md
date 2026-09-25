# lane.pmc-enable-under-load — PR #203, #188 / #110

Branch `claude/pmc-enable-under-load`. Documentation only: no emulator code, no
device run queued from this lane, no prediction registered.

Status: remediated against audit pass 1 (`docs/audits/2026-09-21-claude/
pmc-enable-under-load-pass1.md` — 2 HIGH, 3 MEDIUM, 3 LOW). All five HIGH and
MEDIUM findings fixed; all three LOWs also taken. See "What remediation
changed" below.

## What this lane claimed, and what survived it

The lane read `NV_PMC_ENABLE` (0x200) on silicon from inside a running graphics
application and got `0x13111113`, against `0x01110000` measured idle by
`tools/nv2a_probe`. Two commits landed twenty minutes apart:

- `1eee7098f8` — the under-load read, and "every bit envytools names behaves as
  named; the generic layout does describe this chip".
- `42740526d7` — `pb_init()` writes `NV_PMC_ENABLE_ALL_ENABLE` = `0xFFFFFFFF`
  unconditionally, so the under-load word is the read-back of an all-ones
  write.

**The second commit refutes the first and did not go back to correct it.** That
is the whole of HIGH-1, and it is the lesson worth carrying: an all-ones write
sets every *implemented* bit whatever each bit gates, so the running read
carries exactly one fact — the implemented-bit mask — and zero bits about the
bit→engine map. It also does not discriminate the two candidate explanations of
the idle value, because under "the generic positions are not NV2A's" `pb_init()`
still writes a 1 to bit 12 and bit 12 still reads back 1 if implemented. The
observation is identical under both hypotheses.

The only information-bearing column in the table is the **idle** one, because
it is the only one taken with no write in the run.

### What does survive, and it is the valuable half

**Retiring the planned write.** The open item on #188 was to set bit 28 on
silicon to find out whether it is PVIDEO. Two independent reasons not to, and
neither needs the bit map:

- whatever bit 28 gates, `pb_init()` already sets it in every graphics title on
  the machine, so the state that write was meant to create occurs on its own;
- `NV_PMC_ENABLE_ALL_DISABLE` is the library's own name for `0`, and `0` is
  exactly what was written when this console stopped dead. The danger was never
  writing this register — every title writes `0xFFFFFFFF` at startup. It was
  writing **zero**.

Reading before writing, to test a premise that was about to cost a risky device
write on a register that has already halted this console once, is what produced
both. The read cost nothing.

**The implemented-bit mask.** Ten bits — 0, 1, 4, 8, 12, 16, 20, 24, 25, 28.
Every other bit ignores a 1. Verified arithmetically, and the idle value
`{16,20,24}` is a strict subset of it, as it must be.

**The endian control held.** `NV_PMC_BOOT_0` read `0x02A000A3` in the same pass.
That is a real control and not a ritual one: byte-swapped it is `0xA300A002`, so
a flip would have been unmissable. Carrying it forward from the withdrawn
findings higher up in the same document is right.

## What the next lane must NOT repeat

1. **Do not model bit 12 as PGRAPH or bit 28 as PVIDEO on the strength of this
   document.** Four of the ten implemented bits — 0, 1, 20, 25 — are unnamed by
   envytools, and nothing measured rules out one of *those* being NV2A's PGRAPH
   or PVIDEO gate. The error would stay invisible until a title wrote a partial
   mask rather than all-ones.
2. **Retiring the write also retired the only measurement that would have
   identified bit 28.** That trade is recorded in the findings document as a
   trade, not as an answer. The experiment that would settle the map is a
   *selective* write — from a known-zero baseline, one bit at a time, observing
   which block responds — which is a different and considerably more dangerous
   experiment than the one that was run. Nobody should re-derive that it is
   open; the document says so in a section headed `STILL OPEN`.
3. **#110 is not unblocked.** The lane wrote that it was. It is a hypothesis
   with three unchecked steps (bit 28's identity; whether the pvideo probe
   leaves PMC where the *PMC* probe found it, since they are different XBEs;
   and whether enabling the block is *sufficient* for those 12 registers to
   latch). Do not spend a ~90 minute device run on "add `pb_init()` and see".
4. **When you do spend it, read `NV_PMC_ENABLE` back in the same run.** Without
   that one extra printed word, "the block is up and the registers are still
   inert" and "`pb_init()` did not put PMC where we assumed" are the *same
   observation*, and the run cannot say which it saw. The three-row table in the
   findings document is the decision procedure.

## What remediation changed

HIGH-2 first, because the PR could not fold in any state until it was done.

- **HIGH-2 — merged `origin/master` (62 commits) and resolved the gap-list row
  from master's side.** The branch's row was the pre-#198 text with one clause
  added: it asserted `pmc.c` has "no read and no write case", which PR #198
  falsified, and it *deleted* master's "what each bit gates is unestablished" —
  the correct form of HIGH-1, at the one point of use most likely to be read by
  whoever implements `pmc_write`. Resolved to keep both of master's clauses and
  add only the new fact. Do not resolve a stale row by taking the side the PR is
  "about"; that is how a fold regresses a file.
- **HIGH-1 — rewrote the `NV_PMC_ENABLE` section of
  `nv2a-probe-pmc-findings.md`.** The `pb_init()` explanation now comes *before*
  the inference rather than forty lines after it, so the number cannot be read
  the wrong way on the way past. Three sentences are withdrawn by name, in
  place, with the reason: "every bit envytools names behaves as named", "the
  generic layout does describe this chip", and "reading the same register from
  inside a running graphics application separates the two". A two-column table
  states what the read establishes and what it does not. A `STILL OPEN` section
  records the bit→engine map as unanswered and names the experiment that would
  answer it.
- **MEDIUM-1 — downgraded "What this unblocks for #110" to "What this
  suggests for #110 — a hypothesis with a cheap test, not a result",** with the
  three unchecked steps enumerated and the three-outcome table above. The
  retirement of #110's prescribed hand-rolled write is kept: that part is sound
  and is the safety win.
- **MEDIUM-2 — added a `Provenance` subsection.** See it for what is and is not
  recorded about the under-load read; the honest answer is that the run was not
  recorded and the value is not reproducible from this tree.
- **MEDIUM-3 — filled in the lane template in the PR body** (`Lane:`, `Base:`,
  `Files:`, `Prediction:`, `Needs device:`), and dropped the body's two
  unsupported sentences: "Prediction was registered before the run and both
  sides matched it" (no such file exists — the only PMC/PVIDEO prediction in the
  tree is `2026-09-18-pvideo-overlay-size-pitch-limits.md`, pre-existing and
  unrelated) and "The emulator read `0x00000000`" (true before #198; `pmc_read`
  has returned `0x01110000` since).
- **LOW-1 — this file.** LOW-2: "implemented-and-settable" is now "implemented",
  with the settable subset attributed to the idle column. LOW-3: the nxdk
  citations are pinned in `Provenance` instead of appearing as bare line numbers
  into a tree this repository does not vendor.

## Two things found during remediation that were not in the audit

**The PR body's `Files:` omission had already produced the collision it warns
about.** PR #211 (`lane/cloud190`, #190) declares
`docs/testing/nv2a-hardware-gap-list.md` on its `Files:` line and edits the row
directly below this PR's. `git merge-tree` says the two merge **clean** — they
touch different rows with the `NV_PMC_BOOT_1` row between them — so this costs
nothing this time. It is still two lanes on one undeclared file, and the second
one arrived because the first never declared it. That is MEDIUM-3's failure
scenario, not a hypothetical.

**`nv2a-probe-pmc-findings.md` carried its own stale `pmc.c` sentence, on
master, outside this PR's diff.** The section heading was "the emulator models
nothing at all" and the first line said `pmc.c` has "neither a read case nor a
write case" — false since #198, and sitting directly above the block this PR
adds. Corrected in place rather than contradicted forty lines later, which is
the same failure HIGH-1 is about.

## Gates

`preflight.sh --allow-tracker` on the merged head: every step **ok** except
`coverage`, which fails on issues **#213** and **#212** having neither a lane
nor a blocker. Both are board-owned rows about other lanes (`lane.remote` and
`lane.primpv13`); neither is touched by this PR and a lane cannot clear them.
`--allow-tracker` does not cover the coverage gate.

No build was run and none is claimed: this branch changes no compiled source.
The desktop half of the build obligation is the known, named gap in `AGENTS.md`
and is not this lane's failure.
