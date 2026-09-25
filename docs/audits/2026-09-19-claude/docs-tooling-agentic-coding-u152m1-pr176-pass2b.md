# Audit pass 2b — PR #176, `claude/docs-tooling-agentic-coding-u152m1`: X1A7R8G8B8 is 458,042 px and shared between the backends

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #176, audited at head **`e58fce12`** (the remediation of pass
2); the lane merged `origin/master` into the branch as **`108e8583`** while
this audit was running, and everything below was re-checked against that head
— see "The mid-audit merge" at the end of Part 5. `MERGEABLE`, ready (not
draft). **Date** 2026-09-19 (2026-09-20 UTC). **Records**
`2026-09-19-claude/docs-tooling-agentic-coding-u152m1-pr176-pass2b.{md,json}`,
beside `…-pr176-pass1.md` and `…-pr176-pass2.md` — the `pr176` name, because
the bare branch-derived name is PR #162's record.

**Pass 2's three open findings — M1-R (MEDIUM), L-new (LOW), L-new-2 (LOW) —
are all closed.** Each was verified by building the mutant the remediation
claims to catch and running the gate against it, or by running the tool in the
arrangement the finding described; none by reading the commit that claims them.
**Pass 1's seven findings were re-run at this head and all seven still hold.**

**2 new LOW.** Verdict: **`fold-ready`.**

## Part 1 — pass 2's three findings

Method: fragment 76 alone against a scratch tree holding only
`docs/testing/x1a7_forward_model.py`, with a harness supplying `$REPO`, `$T`
and `check`/`ok`/`bad`. The real path was never modified. Baseline at
`e58fce12`: **19 passed, 0 failed** (17 at `9a4a070d`, so the remediation adds
three checks and retires one).

### M1-R — "a guard that cannot fail" — **CLOSED**

The old check grepped `--selftest`'s output for `scoring the PROPOSED
implementation`, a string only `score()` ever printed. It is gone. In its place
are two source assertions (`76-x1a7-model.sh:60-63`) and one behavioural one
(`:96-99`). Pass 2 asked for exactly one thing: **reinstating a `--proposed`
dispatch in `__main__` must turn at least one check red.** Three mutants,
each a scratch copy of the model file with nothing else changed:

| mutant | fragment 76 |
|---|---|
| **A — the historical mode, restored verbatim**: `if '--proposed' in sys.argv`, the `not today's behaviour` advertisement, `proposed_predictions` | **3 FAIL** — both source checks and the behavioural one |
| **B — evades both source greps and still advertises**: `flags = set(...)`, `'--proposed' in flags`, helper renamed `_alt_preds` | **1 FAIL** — `passing --proposed selects no different mode` |
| C — evades the greps *and* prints nothing until goldens resolve (scores a different prediction set) | 0 FAIL — see **L2b-2** |

Mutant A is not a constructed straw man: it is `b07c1229`'s own
`__main__`, the code the finding named. All three new checks fire on it, where
the retired check was green against that same file. The whole pre-remediation
model file now turns **12 of 19** red (it was 9 of 17 at `9a4a070d`).

The behavioural check needs neither goldens nor an image stack, and the
**runner** confirms it: `jobs selftest` on `e58fce12`
([35489863745](https://github.com/jreinach-alt/hakuX/actions/runs/35489863745))
is `999 passed, 0 failed` and the log carries

```
  ok   no --proposed mode is wired into argv
  ok   passing --proposed selects no different mode
```

so the new guards ran on the machine with no `numpy` and no `PIL`, which is
where the previous remediation's gate could not run at all (H1-R).

### L-new — the 1,024-input sweep was computed and discarded — **CLOSED**

`selftest()` now unpacks `differ`, counts it (`bad += differ != 0`) and prints
it:

```
  substituting the write transform changes 0 of 1024 inputs  ok
```

The question a "now it is counted" claim has to answer is whether the printed
number is the sweep's or still a constant. Mutant F — `write_transform`
truncates instead of bit-replicating — answers it:

```
  the write transform is r1_blend_dst_alpha on all 256 values NO LONGER TRUE
  substituting the write transform changes 512 of 1024 inputs  UNEXPECTED
```

512, not 0, and the selftest's verdict flips: fragment 76 goes **2 red** on
that mutant (`the write transform is still shown to equal R1`, `the selftest's
own verdict is a pass`). The figure moves with the measurement.

### L-new-2 — all-ambiguous reported as "no golden" — **CLOSED**

Fixture: `iso_surf1/` and `iso_surf1_rerun/`, both carrying **all four**
captures — the corner where `resolved` is empty.

```
PROBLEM: 1-DstAlpha_XA_O1A7RGB8: 2 candidate goldens, ambiguous --
  …/g_dupall/iso_surf1/1-DstAlpha_XA_O1A7RGB8.png,
  …/g_dupall/iso_surf1_rerun/1-DstAlpha_XA_O1A7RGB8.png
… (one per capture)
compared 0 of 32 modelled halves; 0 differ; worst |delta| = 0
32 modelled halves were NOT compared -- this is a FAILURE, not agreement
```

exit **1**, four ambiguity lines with both paths each. The reader is no longer
sent to look for a missing file under a root holding eight of them. The
partial case (one capture duplicated) still reports as pass 2 recorded it:
`compared 24 of 32`, exit 1, both candidates named.

## Part 2 — pass 1's seven scenarios, re-run at `e58fce12`

Synthetic goldens painted from `predictions()` at the real grid geometry
(`MARGIN/TOP/SPACING/ROW_PITCH/SIZE`), one arrangement per row. This repeats
pass 2's work at the new head deliberately: the remediation edited `score()`'s
resolve pass, which is the code H1, M2 and L3 all live in.

| arrangement | output | exit |
|---|---|---|
| root absent | `compared 0 of 32`, `32 modelled halves were NOT compared -- this is a FAILURE, not agreement` | **1** |
| root exists, empty | same | **1** |
| one capture of four | `compared 8 of 32`, three `PROBLEM:` lines | **1** |
| all four | `compared 32 of 32 modelled halves; 0 differ; worst |delta| = 0`, four resolved paths printed | **0** |
| all four, one half painted `+3` | `1 differ; worst |delta| = 3` | **1** |
| one capture duplicated | `2 candidate goldens, ambiguous`, `compared 24 of 32` | **1** |
| every capture duplicated | four ambiguity lines, `compared 0 of 32` | **1** |
| goldens 320x240 | `image is 320x240 but the swatch grid needs at least 592x220`, per file | **1** |
| image stack shadowed, goldens **present** | `PROBLEM: cannot compare: shadowed`, `compared 0 of 32`, FAILURE line | **1** |
| image stack shadowed, root absent | `compared 0 of 32`, FAILURE line | **1** |

H1 (a golden never opened is not a golden that agreed), M2 (`hit[0]` out of an
unordered glob, no path in the output), L3 (an undersized golden crashing) and
H1-R (the gate dying on an import instead of reporting) are all still closed,
and the `+3` row shows the accounting still **fails** on a real disagreement —
the pass is not bought by leniency. L1 (one `compose()`), L2 (exactly sixteen
`^  golden .* ok$` lines) and L4 (the reproduction command and its eleven
sites) are unchanged by this remediation and re-checked green.

## Part 3 — what the gate catches, at this head

| mutant | fragment 76 |
|---|---|
| baseline `e58fce12` | 19 passed, **0 failed** |
| the pre-remediation model file (`b07c1229`) | **12 red** |
| `--proposed` restored verbatim | **3 red** |
| `--proposed` restored under another spelling, still advertising | **1 red** |
| `write_transform` truncates | **2 red** |
| the model file absent entirely | 12 red (see L2b-1) |
| the L-new print reverted | 0 red |
| the L-new-2 branch reverted | 0 red |

The last two rows are stated rather than charged as findings: both were LOWs,
both are fixed in the code, and a LOW does not owe a regression check. They are
here so the next reader knows which of these behaviours are pinned and which
are only correct.

## Part 4 — pass 2b's own findings

### LOW — L2b-1: the two source greps are vacuously green if the file cannot be read

`docs/testing/jobs/selftest.d/76-x1a7-model.sh:59-63`. `X1A7SRC=$(cat
"$REPO/docs/testing/x1a7_forward_model.py")` and two `x1a7hasnt` assertions
over it. If the `cat` fails, `X1A7SRC` is empty and **both** checks report
`ok` — a negative assertion over an empty artifact, which is the shape M1-R
itself was.

**Failure scenario, with its own bound stated.** Measured: with the model file
absent from the tree, those two checks pass while **12 other checks in the same
fragment fail**. So the vacuous pass can never be the only thing the reader
sees, and this cannot produce a green run over nothing. What it can do is
mislead an auditor reading the fragment for what each check proves. One line
fixes it — assert the read succeeded (`x1a7has "def score(" "$X1A7SRC"`)
before the two negatives — and it is mutant-checkable by pointing `$REPO` at a
tree without the file.

### LOW — L2b-2: `passing --proposed selects no different mode` compares only the absent-goldens path

`76-x1a7-model.sh:96-99` compares `--proposed <nonexistent root>` against
`<nonexistent root>`. Both runs return from the early `if not resolved:` branch
before any prediction set is consulted, so the check sees a mode that diverges
only *after* goldens resolve as identical.

**Failure scenario.** Mutant C above: `--proposed` selects a different
prediction set, prints no banner, and is not spelled
`'--proposed' in sys.argv`. Fragment 76 stays **19/19** and the check named for
exactly this event reports `ok`. The bound: every reinstatement that prints
anything, and every one that copies the historical spelling, is caught — which
covers the finding M1-R actually described, since the withdrawn mode's whole
danger was the advertisement. A silent variant publishes no claim on its own.

**What would close it.** Assert against the source that `__main__` dispatches
on nothing but `--selftest` — e.g. that `--proposed` does not appear below the
docstring at all — rather than on one spelling of the argv test. Mutant C then
goes red.

## Part 5 — fold readiness

* **CI green on the audited head.** All three checks `SUCCESS` on `e58fce12`:
  Android `build`, Desktop `build`, `jobs selftest` (`999 passed, 0 failed`).
* **`preflight.sh` passes on this head**, all seven steps: `psh_differ build`,
  `psh_differ report`, `aci_vmstate`, `nv2a index`, `territory`, `coverage`,
  `board files` — `preflight passed - safe to push`.
* **`MERGEABLE`, ready, not draft.** No board file is touched:
  `git diff --name-status origin/master...HEAD` is four audit records,
  `docs/lanes/remote/NOTES.md`, the model and the selftest fragment. No `hw/`
  change, no prediction, no device — `Prediction: none: analysis-only` is still
  the right answer.
* **`Files:`** matched the diff at pass 2. Adding this record changes the diff,
  so I extended the body's `pass{1,2}` brace to `pass{1,2,2b}` over the REST
  API (`gh pr edit` applies nothing on this host) and read the value back. That
  is the only edit I made outside `docs/audits/`.
* **The mid-audit merge.** `108e8583` merged `origin/master` into the branch
  after I had finished running everything above against `e58fce12`. It changes
  **none** of the audited files: `git diff --name-only e58fce12 108e8583 --
  docs/testing/x1a7_forward_model.py docs/testing/jobs/selftest.d/76-x1a7-model.sh
  docs/lanes/remote/NOTES.md docs/testing/jobs/selftest.sh` is empty. It brings
  in `linecap13`'s lane, a new `selftest.d/72-cloud-tail.sh`, `geom.c` and the
  regenerated `nv2a_index.json` — none of which fragment 76 reads. Fragment 76
  re-run in the merged tree: **19 passed, 0 failed**, and `jobs selftest` on
  `108e8583` ([35491678780](https://github.com/jreinach-alt/hakuX/actions/runs/35491678780))
  is `999 passed, 0 failed` with both new guards `ok` in the log. The two
  `build` workflows were still in progress when this record was written; this
  audit commit is itself a new head and gets its own runs, and `fold.sh` gates
  on the rollup, so green-before-fold is not something `fold-ready` can skip.
* The prose is consistent with the code at this head: the PR body's
  "identical on all **1,024** inputs" and `NOTES.md:106` now match a printed,
  swept count rather than a literal, and `NOTES.md:35`'s summary row still says
  only "modelled exactly", which is the golden fit and still stands.

## Verdict

**`fold-ready`.**

Pass 2's one MEDIUM is closed against the exact artifact it named, and closed
three ways rather than one: the historical mode turns three checks red, a
differently-spelled one turns the behavioural check red, and the whole
pre-remediation file turns twelve red. The two LOWs are closed behaviourally.
Pass 1's seven were re-run at this head rather than assumed to have survived
the edit to `score()`'s resolve pass, and all seven hold, including the two
arrangements that would make a lenient fix look good.

What is left is two LOWs about what the gate's assertions *prove*, not about
what the code does; neither can produce a green run over nothing, and neither
touches the model, the 32 of 32 fit, or the 458,042 px figure this PR exists
for. Nothing here can move a pixel.
