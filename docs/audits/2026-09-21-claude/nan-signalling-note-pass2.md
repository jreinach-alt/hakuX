# Audit pass 2 — PR #202, `claude/nan-signalling-note`: a third explanation for `-NaNs_NaNs`

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #202, branch `claude/nan-signalling-note`, tip **`20268c7f58`**
(= `gh pr view 202 --json headRefOid`, 4 commits). Not a draft, MERGEABLE, both
`build` checks SUCCESS at this sha.
**Date** 2026-09-21. **Records** `2026-09-21-claude/nan-signalling-note-pass2.md`.
**Pass 1** `2026-09-21-claude/nan-signalling-note-pass1.md` (0 HIGH, 2 MEDIUM,
3 LOW). **Remediation** `20268c7f58`, over the master merge `8696047842`.

**Clean. Every pass-1 scenario is discharged, and none of the seven factual
claims the remediation added to buy that is wrong.** → `fold-ready`.

Pass 1's findings were all about what the insert *left standing* and where it
*pointed the next worker*, so "the scenario can no longer occur" here means a
reader arriving at the named line now takes away something different. I checked
that by reading the file as it now stands at each of those entry points, not by
reading the diff — and then I re-derived every number, quotation, sha and field
name the remediation introduced, because the cheapest way for a documentation
remediation to fail is to discharge the finding with a new false assertion.

## MEDIUM-1 — discharged

*Scenario: a reader reaches the prescription line and records `-NaNs_NaNs` as
blocked on hardware this project does not have.*

The line that produced the scenario is gone. The prescription now reads, at
`nv2a-hardware-gap-list.md:86`, **"None of the three needs a second console to
make progress"**, followed by the offline discriminator for each candidate
(`:89-102`), with the silicon-revision candidate named last and explicitly
priced: *"a 60 px residual on a capture where our own emulator is 14,637 px
out."* `grep -n 'second console' nv2a-hardware-gap-list.md` returns exactly the
two lines that say one is *not* needed. A reader cannot now leave this section
holding "blocked on a second Xbox"; the reclassification is also in the table
cell (`:55`) and in the closing sentence (`:115-117`).

The remedy pass 1 asked for was three specific things. All three are present
and all three are true:

* **Cite `gap-list-b-resolved.md`.** Cited at `:54`, `:55`, `:60`, `:116`.
* **Replace the prescription with what is actually outstanding.** `:67-70` and
  `:100-102`: the 60 px residual, against a 14,637 px emulator defect.
* **Name the offline discriminator for the suite-build candidate.** `:89-93`.

### The numbers, re-derived from the source the insert cites

`gap-list-b-resolved.md:10-13`:

| capture | emu vs golden | emu vs **our hw** | our hw vs golden | verdict |
|---|---:|---:|---:|---|
| `TexFmt_R6G5B5` | 134,902 px | **identical** | 134,902 px | the golden is the outlier |
| `-NaNs_NaNs` | 14,697 px | 14,637 px | **60 px** | emulator defect |

Every figure the diff quotes — 14,637, 14,697, 60, 134,902, "byte-identical",
"the golden is the outlier" — matches that table and its prose
(`gap-list-b-resolved.md:19-28, 31-38`) exactly. The row-cell summaries at `:54`
and `:55` state the same thing in one clause each without overstating it.

### The two offline discriminators are real, and neither is a guess

* **The goldens' provenance.** `abaire/nxdk_pgraph_tests_golden_results` @
  `6e159f15` is `xbox-calibration-2026-09-20.md:23`, verbatim.
* **The golden's filename.** The insert prescribes comparing *"that commit's
  `-NaNs_NaNs.png`"*. This is the obvious place for the remedy to have gone
  wrong, because the file it cites records the trap: the goldens directory holds
  **sanitised filenames, not test names** (`gap-list-b-resolved.md:56-63`). It
  does not step in it — that table's first row (`:62`) is literally
  `` `-NaNs_NaNs.png` `` ↔ `-NaN to +NaN (signalling)`, so the prescribed
  filename is the one on disk. (The test *name*, which is what a disc build
  takes, is the right-hand column; the insert asks for an image comparison, not
  a run, so the filename is the correct half to name.)
* **The conversion path.** The insert attributes the 61-site disassembly to
  "`nv2a_issues.toml`, #74's `blocker_tested` … extracted from
  `nxdk_pgraph_tests_xiso.iso`, which is the calibration disc". I parsed the
  TOML rather than grepping it: the string lives at `.issue.74.blocker_tested`
  and reads *"All 61 FIST/FISTP sites in the 3,404,800-byte .text of the test
  XBE (extracted from `nxdk_pgraph_tests_xiso.iso`, linearly disassembled)…"*.
  The field name, the count, and the ISO are all exact. "Which is the
  calibration disc" is `xbox-calibration-2026-09-20.md:20` —
  `nxdk_pgraph_tests_xiso.iso`, sha256 `2371e743…`. So "this exact XBE" is a
  checked identity between two documents, not an assumption, and the instrument
  the insert points the next worker at demonstrably exists and has been run on
  this binary.

## MEDIUM-2 — discharged

*Scenario (a): a reader scanning the tables for "what differs from hardware"
takes away the unmarked row under the section heading and stops. Scenario (b):
a reader reads the "Either … or" and skips to section C, carrying off the false
dichotomy.*

**(a)** Both section-B rows now carry the reclassification **inside the cell**:
`:54` *"**Reclassified** — `gap-list-b-resolved.md`: the emulator matches our
console exactly, so the golden is the outlier"*, and `:55` *"**Reclassified** —
… the emulator is 14,637 px from our console, so the defect here is ours; the
60 px is the residual discussed below"*. The table-scanning reader is the one
this finding was about, and the correction is now in the only text that reader
reads.

**(b)** `grep -n 'Either' nv2a-hardware-gap-list.md` is empty. The paragraph at
`:57-73` replaces the dichotomy with what was measured per row, keeps the old
two-way reading only as history (*"Both were first read as…"*), and closes
(`:72-73`) with *"Both still reproduce exactly and neither is noise; what they
are evidence *about* has moved"* — which preserves the one part of the old
sentence that is still true.

**Placement, checked against the file's own convention rather than my taste.**
The rows stay under the heading "B. Behaviour that provably differs from
hardware" and are annotated in place. That is not a residue of the finding: it
is what this document already does one section up, where `:44-47` says **"Read
the row, not the heading… a row that has partly landed is annotated in place
rather than deleted"** and gives the reason (the table is what briefs are
written from, so rows must not vanish). The remediation's `:57`, "**Read the
rows, not the heading**, for the last two", is the same device applied to the
same problem, and "the last two" is correct — section B's three rows are #31,
`TexFmt_R6G5B5`, `-NaNs_NaNs`, in that order.

## LOW-1, LOW-2, LOW-3 — all three taken

* **LOW-1 (truncated quote).** `:76-80` now carries all three sentences. I
  compared them against `/home/justin/nxdk_pgraph_tests/src/tests/attribute_float_tests.cpp:55-57`
  character by character: exact, including the source's American "signaling"
  inside the quotation. The comment still sits directly above the `-NaNs_NaNs`
  entry at `:58`, so it is still about this capture. The insert goes further
  than the finding asked and *uses* the restored sentence (`:82-84`): it points
  at the submission path, not the GPU — which is the reason the finding was
  raised.
* **LOW-2 (cross-reference).** `:111` cites
  `../investigations/attrib-float-is-nantoone-and-the-colour-floor.md`; the
  relative path resolves from `docs/testing/`, and that file does carry the same
  TODO (`:25-27`) and the five-binary determinism result (`:13-21`).
* **LOW-3 (lane template, NOTES).** The PR body now carries all five fields.
  `docs/lanes/nan-signalling-note/NOTES.md` exists — **per-lane, not the branch
  root**, which is the form `roles/lane.md:40-44` requires. `Files:` lists three
  paths and `git diff --stat origin/master...HEAD` lists the same three, so
  definition-of-done item 2 holds. No other open PR's body names
  `nv2a-hardware-gap-list.md`, so the collision this field exists to prevent is
  not live.

## Checks pass 2 could make that pass 1 could not

* **The one numeric tension in the cited sources is not a defect, and the
  insert scopes around it correctly.** Pass 1 parked a "14,667 vs 14,697"
  discrepancy as pre-existing. It resolves: the investigation's totals are
  **channel** counts and its per-column figures are **pixels** (its `0_1` row
  sums to 31,115 px against a stated total of 93,345 — exactly ×3), so its
  44,091 is 14,697 px, which is `gap-list-b-resolved.md`'s emulator-vs-golden
  figure to the pixel. Its per-column row sums to 14,667, thirty short of its
  own total; that thirty is pre-existing, in neither file the diff quotes for a
  number, and is not this PR's. What matters for this audit is that the
  investigation's **passthru column reads 14,637** — the same integer as
  `gap-list-b-resolved.md`'s whole-capture emulator-vs-console figure, for a
  different quantity. The insert does not conflate them: it takes every number
  from `gap-list-b-resolved.md` and cites the investigation **only** for the
  determinism claim ("deterministic too, across five binaries"), which is what
  that file supports. Recorded so a later reader does not "correct" the
  attribution in the wrong direction.
* **Internal consistency of the new argument.** `:104-113` says the console is
  byte-identical across runs and discs (`xbox-calibration-2026-09-20.md:82`,
  confirmed), that the emulator is deterministic across five binaries
  (confirmed), and concludes the nondeterminism, if real, "resolves somewhere
  stable per machine rather than per run". That is the right conclusion from
  those two facts, and it is weaker than the evidence would let it be — it does
  not claim the TODO is refuted.
* **Base and gates at this sha.** `origin/master` has moved three commits since
  the branch's merge (`3da2151056`, `3af06a255a`, `fa6863f2f0`, the `fulldisc50`
  lane); `git diff HEAD...origin/master` over the four files this PR writes or
  cites is **empty**, so nothing it asserts has been overtaken. `preflight.sh
  --allow-tracker` is green on this tip end to end — including `coverage` and
  `board files`, which is a change since the PR body was written.

## Observations, not findings

* **The PR body's last paragraph is now stale.** It says `preflight.sh` is
  green "except `coverage`, which reads `nv2a_issues.toml` from `origin/board`
  and fails on #189/#190". The board has since fixed those rows and that step
  now passes. A stale note claiming a gate is red is the harmless direction —
  it can only make a fold-time reader check more, not less — and the body is
  not a committed file. Not a finding; noted so the fold does not go looking
  for a red gate that is green.
* **`xbox-calibration-2026-09-20.md:82` and `:92` still carry the pre-
  reclassification reading** ("real disagreement with the golden", "Two are
  genuine"). The lane declined to edit it, and says so, with a reason
  (`NOTES.md`: it is a dated record of one run, and editing it would put this
  lane on a path its `Files:` line does not claim). That is the correct call —
  the staleness predates this PR, `gap-list-b-resolved.md` did not correct it
  either, and a dated run record is supposed to say what was believed on its
  date. The gap list is the file briefs are written from and it is the one
  corrected. Someone should eventually add a forward pointer there; it is not
  this PR's to add, and it is not a pass-2 finding.

## Verdict

**0 HIGH, 0 MEDIUM, 0 LOW. Clean → `fold-ready`.**

Both MEDIUM scenarios are discharged at the exact lines that produced them, all
three LOWs are taken, and the remediation's own new assertions — four figures,
a three-sentence quotation, two shas, a TOML field path and an ISO identity —
were each re-derived from the source rather than accepted from the commit
message. The diff is documentation only, `preflight.sh --allow-tracker` is
green on `20268c7f58`, both `build` checks are SUCCESS on it, the PR is
MERGEABLE, and the three master commits since its merge touch none of it.
