# lane.pmc188 -- #188: NV_PMC_ENABLE reads 0, silicon reads 0x01110000

Status: done, and remediated against audit pass 1 (3 MEDIUM fixed, 6 LOW
decided -- see "Remediation after audit pass 1" below). One hunk in `pmc_read`,
plus a committed selftest and its committed mutant suite. PR #198.

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

**Corrected after audit pass 1 (M3). The first version of this section said the
header and the measurement "do not reconcile". That was wrong, and two
documents already in this tree said so.**

`nv2a_regs.h:72-74` puts `_PFIFO` at bit 8 and `_PGRAPH` at bit 12. The
measured word `0x01110000` has **both of those bits clear** and sets 16, 20 and
24. Clear is not a contradiction -- it is the header saying "these two engines
are not enabled", and in the same read-only survey **PGRAPH read 0/2048
non-zero** (`nv2a-probe-pmc-findings.md`). A word with `_PGRAPH` clear, read on
a console whose PGRAPH block is entirely silent, is what the header *predicts*.
`nv2a-mapping-programme.md:168` goes further and already reads **bit 16 as
PTIMER**, cross-checked against PTIMER reading 992/1024 non-zero in that survey
and used as the reason a blind write there wedges the machine (:204).

One honest caveat the audit's version smoothed over: **PFIFO read 382/2048
non-zero** in the same survey, so PFIFO is not silent the way PGRAPH is. That
does not reopen the question -- a disabled engine's registers can still hold
reset defaults -- but it is not confirmation either, and it should not be
quoted as one.

So what is actually unestablished is narrower than this lane first wrote, and
naming it narrowly is the point, because the envytools cross-reference #188
asks for next is briefed from here:

1. **what bits 20 and 24 gate.** Nothing in this tree assigns them.
2. **what this register reads on a busy machine.** Both sweeps were the console
   freshly out of the dashboard with the engines idle. 1,024/1,024 across a
   reboot bounds **repeatability in one state**; it says nothing about
   state-independence, which is the property a hardcoded constant needs.
   `nv2a-probe-pmc-findings.md` says exactly this of its own numbers -- *"nothing
   here should be turned into an emulator change without a second read in a
   known state"* -- and this diff is that change, so the restriction is now
   recorded beside the constant in `pmc.c` rather than only in the probe notes.

**The consequence to hold on to:** if the header positions are right, we now
answer "PFIFO and PGRAPH are down" to any guest that reads this register, at
all times, including mid-frame -- and #188's body names precisely that reader.
That is not a regression, which is why the value stays: the `0` we returned
before said the same thing about those two bits *and* was wrong about
everything else in the one state anyone has measured. It is a reason the write
lane cannot treat this as inert.

Still: no field decomposition, no `SET_MASK`, no new macros. A bare constant is
the honest shape -- it says "silicon reads this, in this state" and nothing
about why.

**The endian rival is dead; do not re-derive it.** `0x01110000` byte-swapped is
`0x00001101` -- bits 0, 8 and 12, i.e. exactly the header's `_PFIFO`/`_PGRAPH`
pair -- and this probe campaign has already retracted one bit-position claim as
an endian artefact, so the coincidence will stop the next reader. It does not
apply here: the endian switch is `NV_PMC_BOOT_1` and it is flipped only by a
*write*, the sweep that produced this value issued no writes at all, and
`NV_PMC_BOOT_0` read its correct `0x02A000A3` in that same run as the control.
This is now written into `pmc_enable_selftest.c` beside the falsifier, where
someone doubting the value will be standing.

The write side is untouched for a blunter reason. Writing 0 to this register
**halted the physical console** in the sweep that found it -- no ICMP
afterwards, ARP `FAILED`, power cycle required. Modelling a write means
modelling a halt on a guess about which bit gates which engine, which is
exactly the guess above. Writes stay a silent no-op via `pmc_write`'s
`default`.

**A note for whoever does take the write side.** The read now returns a
non-zero value, which is a change in what a guest sees before it decides to
write anything. A guest that reads `PMC_ENABLE`, clears a bit and writes back
now computes its write from `0x01110000` rather than from `0`. **No *write*
behaves differently today** -- the write is still discarded -- but the read
does, for every guest read of `0x200`, and that is the one live behavioural
change in this diff. Whether any title reads this register is unmeasured, and
"unmeasured" is not "nothing differs" (audit pass 1, L6: the first draft of
this paragraph and the PR body both said the latter). The day the write path
becomes live, the value being written will already have been shaped by this
commit. That is an argument for landing the read first, not against it; it just
means the write lane cannot treat the two as independent.

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
everything. The mutants are no longer a table someone typed once: they are
**`docs/lanes/pmc188/mutants.py`**, committed, each built in its own temp tree
(never by swapping the real path, which leaves the old code in the worktree),
each asserting the LINE the run goes red on and not merely the status.

```
python3 docs/lanes/pmc188/mutants.py              -> 14 mutants, 0 unexpected
python3 docs/lanes/pmc188/mutants.py --at c2e57d8d86
                                                  -> 6 of 14 disagree:
                                                     M1b M1c M2b M7b L1 L2
```

| mutant | expected | got | went red on |
|---|---|---|---|
| M0 unmutated tree | exit 0 | exit 0 | -- (this is the one that makes the rest mean something) |
| M1 `pmc_write` gains `case NV_PMC_ENABLE:` | exit 1 | exit 1 | `REFUSED: pmc_write has a case for NV_PMC_ENABLE (0x200)` |
| **M1b** `pmc_write` gains `case 0x200:` | exit 1 | exit 1 | same REFUSED -- **was exit 0 before remediation** (audit M1) |
| **M1c** `pmc_write` gains `case 0x00000200 ... 0x2FC:` | exit 1 | exit 1 | same REFUSED -- was exit 0 before |
| M2 `pmc_write` uses `0x01110000` | exit 1 | exit 1 | `REFUSED: the measured read-back constant appears in pmc_write` |
| **M2b** ...spelled `0x1110000` | exit 1 | exit 1 | same REFUSED -- was exit 0 before |
| M3 the read reverted to 0 | exit 1 | exit 1 | `FAIL NV_PMC_ENABLE ... got=0x00000000` |
| M4 the case widened to `+4` | exit 1 | exit 1 | `FAIL unmodelled 0x204` |
| M5 constant lands on `BOOT_0`'s arm | exit 1 | exit 1 | `FAIL NV_PMC_BOOT_0` |
| M6 `pmc_read` renamed | exit **2** | exit 2 | `anchors not found in pmc.c` |
| M7 trace logs 0 instead of `r` | exit 1 | exit 1 | `the trace is wrong` |
| **M7b** trace logs the wrong width | exit 1 | exit 1 | `the trace is wrong` -- was exit 0 before (audit L3) |
| **L1** an unrelated later function holds the constant | exit **0** | exit 0 | must NOT fire -- was a false `REFUSED` before (audit L1) |
| **L2** a helper using an unstubbed type sits between the two | exit **0** | exit 0 | must NOT fire -- was "pmc.c did not compile" before (audit L2) |

Each went red on its own line, not all on one reason. M6 is the one that
matters most for the long run: a silent mis-extract compiles to nothing and
passes, so the anchor failure is a distinct exit code with its own message.

M1/M1b/M1c and M2/M2b are anchored on the **code** -- a `case` label and the
constant -- not on prose, because a comment in `pmc_write` mentioning
`NV_PMC_ENABLE` is legitimate and in fact likely, and a grep for the words
would go red against a correct file. The offset spellings are there because
every arm in `pmc_write` today uses a macro but the *offset* is what a future
editor copies out of `nv2a_regs.h` (`0x00000200`) or a probe log
(`0xFD400200`), and the range form is how #190's block would arrive.

**M7b needed care and the first attempt was void.** Logging size `0` removes
the last use of `size`, so `-Werror=unused-parameter` reddened the build before
the assertion could fire -- a red for the wrong reason, which is the
exit-code-is-coarse trap one level down. The mutant logs `size - 1` instead.

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

## Remediation after audit pass 1 (`docs/audits/2026-09-21-pmc188-pass1.md`)

0 HIGH, 3 MEDIUM, 6 LOW. Every MEDIUM is fixed; every LOW has a decision here,
because silence on a LOW is not an outcome.

| # | what | done |
|---|---|---|
| **M1** | the write guards matched the macro spelling only; `case 0x200:` passed green | both greps widened to `NV_PMC_ENABLE\|0x0*200\|512` and to the GCC range form, and the constant grep to `0x0*1110000` case-insensitively. Three new mutants (M1b, M1c, M2b) and the `--at` run show each was exit 0 before |
| **M2** | `nv2a-hardware-gap-list.md:38` said `pmc.c` has "no read and no write case" -- false the moment this folds | row rewritten to "**read landed, write still nowhere**" with what each side now does, plus a "read the row, not the heading" note under the table, since #189/#190 are briefed from it. File added to the PR's `Files:` |
| **M3** | "those two facts do not reconcile" was contradicted by two documents in this tree | corrected in all three places it is read -- `pmc.c`'s comment, this file's summary section, the PR body. Bits 8/12 are **clear**; PGRAPH read 0/2048; `nv2a-mapping-programme.md:168` already reads bit 16 as PTIMER. The open questions are now named as bits 20/24 and a busy machine, and the state the value was measured in sits beside the constant |
| **L1** | write extract ran to EOF | **fixed** -- both extracts are bounded at their own column-0 `}`. Mutant L1 must now pass and did |
| **L2** | read extract ran to `pmc_write`'s signature | **fixed** by the same change. Mutant L2 must now pass and did |
| **L3** | `g_log.size` / `g_log.block` captured, never asserted | `size` is asserted (mutant M7b). `block` is **not**, deliberately: `NV_PMC` lives in `nv2a_int.h`, which this stub set exists to avoid including. Said so in one line at the check, so the omission reads as chosen |
| **L4** | `unmodelled 0x204 == 0` is knowingly contrary to silicon (#190) and did not say so | clause added: silicon reads `1` there, this pins the case **width** not the value, and the #190 lane should change the line rather than investigate it |
| **L5** | the selftest is wired to no gate | **not fixed, and the auditor accepted the reasoning.** Wiring it means touching another job's tick, which makes every existing fixture for that job drive this code; all three unwired selftests (`audio_starve`, `glerr_report`, this) should be wired together, as their own piece of work. Logged rather than silently carried: **nothing in CI runs this file.** `mutants.py` is committed so the next person has the whole check, not just the script |
| **L6** | "nothing differs today" is false | reworded to "no *write* differs today" in both the PR body and this file, with the read named as the one live behavioural change and "unmeasured" separated from "nothing differs" |

One refinement of the audit's own reasoning, recorded because a remediation is
a claim too: M3 says the measured word is "consistent with both engines being
idle". PGRAPH yes -- 0/2048. **PFIFO read 382/2048 non-zero**, so it is not
silent, and the bit-8-clear reading is *unrefuted* rather than *confirmed* by
that half. Reset defaults in a disabled engine's registers explain it, but that
is an explanation, not a measurement. The section above says it that way.

## What the next lane should not repeat

- **Do not re-derive the bit layout from this one value, and do not re-derive
  the endian rival.** Three bits set at 16/20/24 invites a story, and the
  byte-swap coincidence (`0x00001101` = bits 0/8/12) invites a better one; both
  are answered above and in `pmc_enable_selftest.c`. What the cross-reference
  is actually for is bits 20 and 24, and a read on a machine that is rendering.
- **Do not queue a device arm for this.** There is no golden that can see it. A
  PMC register read never reaches a framebuffer, so an A/B on captures would
  come back "no change" and that verdict would be vacuous rather than
  informative. That is why `Prediction: none` here, and it is also the reason
  #188 notes no golden could ever have found this.
- **Do not reach for the write side without the envytools reference.** The
  cost of getting it wrong was already paid once, in a full console lockup.
- The extraction anchors are `^uint64_t pmc_read(` and `^void pmc_write(`, and
  the test assumes the second follows the first. Each extract now ends at its
  own column-0 `}`, so a helper added *between* the two functions or *after*
  `pmc_write` is outside both and cannot produce a failure about code it does
  not describe. Reordering the file is still fine; the test will tell you it
  happened rather than quietly testing an empty string.
- **If you change the selftest, run `mutants.py` both ways.** A guard that has
  never been seen to refuse anything is an assertion about a script. `--at
  <rev>` is how "this row is newly caught" gets measured instead of asserted.
