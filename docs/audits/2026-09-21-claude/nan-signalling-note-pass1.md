# Audit pass 1 — PR #202, `claude/nan-signalling-note`: a third explanation for `-NaNs_NaNs`

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #202, branch `claude/nan-signalling-note`, tip **`4051e8f9e3`**,
one commit over `origin/master`. Not a draft, MERGEABLE/CLEAN, both `build`
checks green. Master is 45 commits ahead; none of them touch
`docs/testing/nv2a-hardware-gap-list.md`, so the diff applies as written.
**Date** 2026-09-21. **Records** `2026-09-21-claude/nan-signalling-note-pass1.md`.

**0 HIGH. 2 MEDIUM. 3 LOW.**

The diff is +12/−0 in one file: a two-paragraph insert into section B of
`docs/testing/nv2a-hardware-gap-list.md` at lines 56–66. No code, no tool, no
prediction, no device. The whole audit surface is "is what it asserts true,
does it leave the file consistent, and is its prescription for the next worker
the cheapest correct one".

**The citation is exact and the correction's direction is right.** Both MEDIUMs
are about what the insert leaves standing and where it points the next worker:
the repository already answered, one commit earlier on this very branch, the
question the insert says needs a second Xbox, and the table row the insert is
withdrawing is left unmarked above it.

## What I checked and found correct, so remediation does not re-derive it

* **The quotation is verbatim and the line number is exact.**
  `/home/justin/nxdk_pgraph_tests/src/tests/attribute_float_tests.cpp:55` is
  `// TODO: It appears that the handling of the signaling NaN is nondeterministic.`
  and `:56` continues `// Sometimes it is converted to quiet NaN.` The comment
  sits directly above the `-NaNs_NaNs` entry of `testConfigs[]` at `:58`
  (`{"-NaNs_NaNs", "-NaN to +NaN (signalling)", {f(negNanS), f(posNanS)}}`), so
  it is about this capture and not a neighbouring one. The insert preserves the
  source's own American spelling inside the quote marks and uses the British
  one outside; that is correct quoting, not an inconsistency.
* **"Which this list omitted" is true of this list.** Before the diff,
  `nv2a-hardware-gap-list.md` offered exactly the two causes at lines 52–54 and
  named no third.
* **The logical point at lines 62–64 is sound.** Per-console determinism does
  not exclude console-to-console variation; "deterministic across runs and
  discs" is a statement about one console and does not falsify a
  nondeterministic-handling story. The insert correctly refuses to let the
  existing measurement close the question.
* **Placement beats the obvious alternative.** Putting the correction inside
  section B rather than appending it to the end of the file is the right call
  and is what the PR body claims it did.
* **The withdrawal is directionally right, and understated** — see MEDIUM-1:
  `-NaNs_NaNs` should indeed not be quoted as a settled hardware disagreement,
  for a stronger and already-measured reason than the one given.

## MEDIUM-1 — the insert prescribes a second console for a question this repo answered one commit ago

`nv2a-hardware-gap-list.md:64-65` (new): *"Deciding between the three needs the
test run on a second console, not more runs on this one."*

`docs/testing/gap-list-b-resolved.md` is **commit `7bf384c44d`, folded as
`28531197b6`, which is the direct parent of this PR's only commit**. It is in
this branch's own history and in `origin/master`. Its table reads:

| capture | emulator vs golden | emulator vs our hardware | our hardware vs golden | verdict |
|---|---:|---:|---:|---|
| `-NaNs_NaNs` | 14,697 px | 14,637 px | **60 px** | **emulator defect** |

and its prose (`gap-list-b-resolved.md:31-38`): *"This was listed as a
hardware/golden disagreement. It is not: hardware essentially agrees with the
golden and **the emulator is the outlier** on signalling-NaN vertex
attributes."* and *"The 60 px is noise beside that."*

Separately, `docs/investigations/attrib-float-is-nantoone-and-the-colour-floor.md:25-27`
already quotes **the same TODO** and already tested it on the emulator side:
*"On this host it is **not** — `-NaNs_NaNs` sits at exactly 44,091 in all five
runs"*, across five binaries from `0.3.3-j1-102` to `0.4.0-j1-331`.

The insert cites neither, and a second console cannot decide two of its own
three candidates anyway. A suite-build difference is settled by building the
suite or reading the goldens' provenance, not by more silicon. And the source
comment's own third sentence — dropped from the quote, see LOW-1 — locates the
suspected mechanism in the *test's* conversion path, which is readable offline
from the XBE; this repo owns that instrument and has used it on this exact XBE
before (`nv2a_issues.toml:2982`, the FIST/`fldcw` disassembly of all 61 sites).

**Failure scenario.** A reader opens the headline "where we differ from the
console" document, reaches line 64, and records `-NaNs_NaNs` as blocked on
hardware this project does not have. The repository's newest word on the entry
— that our hardware agrees with the golden to 60 px while the emulator is
14,637 px out, i.e. that the actionable defect is ours and needs no console at
all — is two files away and unlinked. Best case the entry is parked; worst case
a second Xbox is argued for from this line. `AGENTS.md`'s standing rule is that
a blocker is a claim and gets tested before it is written down; this one was
written down with the counter-evidence already in the tree.

**Remedy.** Cite `gap-list-b-resolved.md` in the insert and replace "needs the
test run on a second console" with what is actually outstanding after that
reclassification (if anything: the 60 px residual, against a 14,637 px emulator
defect), and name the offline discriminator for the suite-build candidate.

## MEDIUM-2 — the row being withdrawn is left unmarked, above the withdrawal

The insert lands at line 56. Above it, unchanged:

* `:44` the section heading, **"B. Behaviour that provably differs from
  hardware"**;
* `:50` the row itself, `| `Attrib_float::-NaNs_NaNs` | **60 px**, likewise
  deterministic across runs and discs | new |`, carrying no caveat;
* `:52-54` *"The last two are this console disagreeing with a golden captured
  on 1.0 silicon. **Either** a V1.1-vs-1.0 difference **or** a golden from a
  different suite build; both reproduce exactly and neither is noise."*

Line 53's "Either … or" is a two-way enumeration that the next paragraph exists
to say is a three-way one, and it is left asserting the dichotomy verbatim. Per
`gap-list-b-resolved.md` the row's placement under "provably differs from
hardware" is wrong for `-NaNs_NaNs` outright, and its narrowing for
`TexFmt_R6G5B5` ("the golden is the outlier") is also unrecorded here — though
only the first is this PR's subject.

**Failure scenario.** This document is four tables with prose between them, and
a reader scanning the tables for "what differs from hardware" takes away line
50 under the line-44 heading and stops; a reader who reads line 52 and skips to
section C takes away the false dichotomy. Either one carries off exactly the
claim the PR was opened to withdraw. The PR body asserts the opposite — *"in
the table's own section rather than appended at the end, because the top of the
file is what a reader takes away"* — but the top of the section is the part
left untouched.

This is the weaker of the two MEDIUMs: the correction is ten lines below, in
the same section, and a linear reader will reach it. It is raised because it is
a recurring failure in this repo — a withdrawal placed where the premise is not
read — and because the remedy is two small edits.

**Remedy.** Mark the line-50 cell (a parenthetical pointing down, or to
`gap-list-b-resolved.md`), and amend line 53's "Either … or" so it does not
enumerate two causes ten lines above a paragraph naming three.

## LOW-1 — the quote is truncated where it stops being quotable and starts being actionable

The source comment runs three sentences (`attribute_float_tests.cpp:55-57`).
The insert takes the first two. The third is: *"As pgraph operates on integers
and does a conversion from float back to int, it may be better to fall back
into setting raw values without doing the float conversions."*

That sentence is the test author's own guess at the mechanism, and it points at
the submission path rather than at the GPU — which is the difference between
"needs another console" and "read what the XBE puts in the pushbuffer". Its
omission is what makes MEDIUM-1 possible. Including it costs one line.

## LOW-2 — no cross-reference to the investigation that already carries this quote

`docs/investigations/attrib-float-is-nantoone-and-the-colour-floor.md:25` has
the same TODO and a determinism result against it. The insert's framing ("which
this list omitted") is correctly scoped to this list and is not wrong, but a
reader landing here has no route to the measurement.

## LOW-3 — the PR body is not the lane template, and there is no per-lane NOTES

`docs/testing/jobs/roles/lane.md` requires the body to carry
`Lane:`/`Base:`/`Files:`/`Prediction:`/`Needs device:`; #202's body is free
prose with none of them, and the diff adds no `docs/lanes/<lane>/NOTES.md`. The
board reads `Files:` from open PRs to keep two lanes off one path. Blast radius
here is small — one commit, one documentation file, and CI is green — so this
is a LOW, but `docs/testing/nv2a-hardware-gap-list.md` is a file other lanes do
edit, and this PR is invisible to that check.

## Not findings

* **The 14,667 vs 14,697 discrepancy between the investigation's per-column
  table and `gap-list-b-resolved.md`'s total is not this PR's.** Both predate
  it and neither is quoted by the diff.
* **British/American spelling inside versus outside the quotation** is correct
  quoting.
* **CI, mergeability and base freshness are all clean** and are recorded above
  so pass 2 need not re-check them at this sha.

## Verdict

2 MEDIUM → `needs-remediation`. Both are in the same ten lines and neither
requires a device, a build or a new measurement: the evidence MEDIUM-1 asks for
is already committed in this branch's own parent, and MEDIUM-2 is two edits to
lines the diff already sits beneath.
