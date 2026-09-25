# Audit pass 2 — PR #203 `claude/pmc-enable-under-load`

Head `fcdce59bed` (remediation `08f247cdac` merge + `fcdce59bed`), base
`origin/master`. Pass 2 asks, for each pass-1 failure scenario, whether it can
still occur against this head, not whether a commit mentions it.

**Verdict: clean. All 2 HIGH, 3 MEDIUM and 3 LOW scenarios no longer occur.
→ `fold-ready`.**

State checked 2026-09-24: `mergeable: MERGEABLE`, `mergeStateStatus: CLEAN`,
`git merge-tree --write-tree origin/master HEAD` exits 0, both `build` checks
`pass` on this head (runs 36097594733 / 36097594750).

## HIGH-1 — running read taken as the bit→engine map — **closed**

Scenario: a lane implementing `pmc_write` reads "the generic layout does
describe this chip" as settled and models bit 12 = PGRAPH, bit 28 = PVIDEO.

- The three sentences are gone as assertions. The only surviving occurrences in
  `nv2a-probe-pmc-findings.md` (lines ~147–151) are inside the "Three sentences
  are withdrawn" list, each with its reason. A repo-wide grep finds them nowhere
  else outside `docs/audits/` and the lane NOTES (which also quotes them as
  withdrawn).
- The `pb_init()` all-ones explanation now precedes the number's
  interpretation, and a two-column table states "establishes: implemented
  mask / does not establish: which engine any bit gates".
- The identical-observation argument (PGRAPH at bit 3 still reads 1 at bit 12)
  is in the document verbatim.
- `STILL OPEN: what each bit gates` names the unnamed bits 0, 1, 20, 25, the
  selective-write experiment, and records that retiring the write retires the
  only bit-28 measurement, as a trade.
- The gap-list row, the one point of use, says "leaves **what each bit gates
  unestablished**".

A reader of either file can no longer come away with a bit→engine map.

## HIGH-2 — stale gap-list row, #198 regressed, conflict — **closed**

Scenario: conflict resolved from the branch side, gap list regresses to "`pmc.c`
has no read case" and loses the caveat.

- Branch merged `origin/master`; the PR is `MERGEABLE`/`CLEAN` and merge-tree
  is clean against today's master.
- The row starts from master's text: "`pmc_read` has returned that constant
  since PR #198" and "`pmc_write` still drops it via `default:`" are kept, and
  the caveat is kept. Checked against the tree: `hw/xbox/nv2a/pmc.c:64` has the
  `NV_PMC_ENABLE` case and `:102` returns `0x01110000`, so the row is accurate.
- The PR body's "emulator read `0x00000000`" sentence is gone.
- Bonus beyond the audit: the findings doc's own stale "neither a read case nor
  a write case" heading on master is corrected in place.

## MEDIUM-1 — `pb_init()` as the settled prerequisite for #110 — **closed**

Scenario: a lane treats #110 as unblocked and spends a ~90 min run that cannot
tell its outcomes apart. The section is now "a hypothesis with a cheap test,
not a result", lists the three unchecked steps, and prescribes reading
`NV_PMC_ENABLE` back in the same run with a three-row decision table that
separates the outcomes. The hand-rolled write stays retired.

## MEDIUM-2 — headline number without provenance — **closed**

Scenario: a later reader cannot place `0x13111113` in time and takes it as
reproducible. The provenance cannot be recovered after the fact, so the remedy
is disclosure, and the disclosure is complete: a `Provenance` table marks date,
instrument, artifact and repeats as **not recorded** (n = 1, bounded only by
commit `1eee7098f8`), the Reproducibility section is scoped to the idle sweeps,
the prediction claim is withdrawn in body and doc, and the #110 pvideo figures
are flagged "re-establish, do not cite onward". No reader can now mistake the
value for a reproducible one.

## MEDIUM-3 — no template, `Files:` names nothing — **closed**

Body has `Lane:`, `Base:`, `Files:`, `Prediction:`, `Needs device:`. `Files:`
lists the three diffed doc paths plus the pass-1 audit file, matching
`git diff --stat origin/master...HEAD`. This pass-2 file is added by the audit
itself, per the audit protocol.

## LOWs — **closed**

- LOW-1: `docs/lanes/pmc-enable-under-load/NOTES.md` exists, per-lane path.
- LOW-2: "implemented", with the settable subset {0,1,4,8,12,25,28} attributed
  to the idle column and the bit-12 clear/re-set caveat stated.
- LOW-3: citations now by symbol (`pb_OldMCEnable`,
  `NV_PMC_ENABLE_ALL_ENABLE` = `0xFFFFFFFF`, `NV_PMC_ENABLE_ALL_DISABLE` = `0`)
  with the code quoted, which is the "quote enough to survive a renumber"
  branch of the remedy. NOTES says "pinned"; strictly no nxdk sha is pinned,
  but the symbol form meets the remedy. Not a new finding.

## New findings

None at MEDIUM or above. Checked: the new gap-list claim "the constant is
right for the one state it was measured in and wrong for the rendering one" is
supported by the two silicon reads and `pmc.c:102`; the new
bit table's columns match the pass-1-verified decompositions
(`0x13111113` → {0,1,4,8,12,16,20,24,25,28}, `0x01110000` → {16,20,24}).
The #211 overlap on `nv2a-hardware-gap-list.md` touches a different row and
merges clean; it is #211's concern, not a defect here.

— cloud audit pass 2, 2026-09-24
