# Audit pass 2 — PR #176, `claude/docs-tooling-agentic-coding-u152m1`: X1A7R8G8B8 is 458,042 px and shared between the backends

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #176. Audited across two heads: **`b8aa251b`** (the remediation
of pass 1) and **`9a4a070d`**, which the lane pushed while this audit was
running. Merge-base with `origin/master` **`20e4708d5`**. `MERGEABLE`.
**Date** 2026-09-19 (2026-09-20 UTC). **Records**
`2026-09-19-claude/docs-tooling-agentic-coding-u152m1-pr176-pass2.{md,json}`,
beside pass 1's `…-pr176-pass1.md` — the `pr176` name, as pass 1 asked.

**Pass 1's seven findings: all seven verified closed**, by running the code in
constructed arrangements rather than by reading the commit that claims them.

**Pass 2 raised one HIGH of its own (H1-R), and the lane fixed it mid-audit in
`9a4a070d`; I re-verified the whole of pass 1 and H1-R against that head and
both hold.** What remains is **1 MEDIUM and 2 LOW**, so:
**`needs-remediation`** — on M1-R alone, which is one line plus a mutant.

## Part 1 — each pass-1 scenario, re-run (head `9a4a070d`)

Fixtures: synthetic goldens painted from `predictions()` at the real grid
geometry, in six arrangements. Fixtures and mutants lived in a scratch
directory; the real path was never modified.

### H1 — "a golden it never opened is not a golden that agreed" — **CLOSED**

Pass 1's scenario was a reader running the documented reproduction line against
an empty `/tmp/goldens/results`, getting
`0 of 32 modelled halves differ; worst |delta| = 0` and exit 0, and recording
the model as re-confirmed. It cannot happen now:

| goldens root | output | exit |
|---|---|---|
| absent | `compared 0 of 32 modelled halves`, `32 modelled halves were NOT compared -- this is a FAILURE, not agreement` | **1** |
| one of four captures | `compared 8 of 32`, three `PROBLEM:` lines | **1** |
| all four | `compared 32 of 32 modelled halves; 0 differ; worst |delta| = 0` | **0** |
| all four, one half painted `+3` | `golden 0x59 model 0x56 off by 3`, `compared 32 of 32; 1 differ; worst |delta| = 3` | **1** |

The last row matters as much as the first three: the new accounting still
*fails* on a real disagreement, so the pass is not bought by leniency.

### M1 — `--proposed` could not disagree with the default mode — **CLOSED**

The mode is removed, not patched: `__main__` is
`args = [a for a in sys.argv[1:] if not a.startswith('--')]` with no
`--proposed` dispatch, and `grep` finds only prose and `coincidence()`. The
claim is withdrawn **where it is read**, in all three places — PR body
§"WITHDRAWN: the fix, simulated at 0 of 32", `NOTES.md:99`, module docstring
`:26-40` — and `NOTES.md:35`, the top-of-file summary row where a withdrawal
usually fails to reach, says only "modelled exactly", which is the golden fit
and still stands. The surviving statement of support names the model fit plus
an assumption and explicitly denies a simulation.

The residue the lane extracted is itself checkable and checks out: `--selftest`
now *demonstrates* the coincidence (`write_transform` equals
`r1_blend_dst_alpha` on all 256 values; `0x22` is its fixed point) instead of
asserting it in a comment. See **M1-R** for the one guard of the three that
cannot fail.

### M2 — `hit[0]` out of an unordered glob, no path in the output — **CLOSED**

`glob.glob` is `sorted(...)`, `len(hits) > 1` is refused rather than resolved,
and the resolved path is printed once per capture (4 of 4 on the full
fixture). Duplicate fixture — `iso_surf1/` and `iso_surf1_rerun/` both carrying
one capture:

```
PROBLEM: 1-DstAlpha_XA_O1A7RGB8: 2 candidate goldens, ambiguous --
  …/g_dup/iso_surf1/1-DstAlpha_XA_O1A7RGB8.png,
  …/g_dup/iso_surf1_rerun/1-DstAlpha_XA_O1A7RGB8.png
compared 24 of 32 modelled halves; … 8 modelled halves were NOT compared
```

exit 1, both candidates named. (One corner of this regressed in `9a4a070d` —
L-new-2 below.)

### L1..L4 — **all four CLOSED**

* **L1** — one `compose()` (`:80-94`); `swatch()` delegates to it and the rival
  loop calls it with `(r1, r2)`. `model_with()` is gone, so a rival can no
  longer be refuted by a divergence between two transcriptions.
* **L2** — the gate counts `'^  golden .* ok$'` and requires **exactly** 16,
  not `>= 16` over every line containing `' ok'`. Mutant-checked below.
* **L3** — `validate_geometry()` compares the grid against the image. A
  320x240 golden yields `PROBLEM: …: image is 320x240 but the swatch grid needs
  at least 592x220`, `compared 24 of 32`, exit 1 — a report naming the file and
  both dimensions, not `ValueError: attempt to get argmax of an empty
  sequence`.
* **L4** — I ran the command as written:
  `grep -rn "X1A7R8G8B8_[ZO]" hw/ | grep -v /vk/` returns **11 lines**, and
  every one of them matches a row of the table, which now lists all eleven in
  six groups including `pgraph.c:4664`.

### The gate's discriminating power, measured

Fragment 76 run against mutant trees (a scratch root holding only
`docs/testing/x1a7_forward_model.py`). Baseline on `9a4a070d`:
**17 passed, 0 failed**.

| mutant | result |
|---|---|
| the **exact pre-remediation model** (`b07c1229`'s file) | **9 red**, including all five H1 checks |
| `write_transform` truncates instead of bit-replicating | 2 red |
| two `GOLDEN_DSTALPHA` entries edited to match a wrong model | 3 red, golden count drops to 14 |
| **the H1-R fix reverted** (imports back at the top of `score()`) | **2 red** — the gate now guards its own fix |
| `--proposed` reinstated, printing its old advertisement | **0 red — see M1-R** |

## Part 2 — pass-2 findings

### HIGH — H1-R: the H1 gate could not run on the machine that runs it — **raised at `b8aa251b`, FIXED in `9a4a070d`, verified closed**

Recorded in full because the finding and its fix are both part of this PR's
history, and because the reason it was invisible is worth keeping.

**What was wrong.** `score()` opened with `import numpy as np` /
`from PIL import Image`, and fragment 76 was the first thing in `selftest.d/`
ever to reach `score()` — no other fragment imports either module. The
`jobs selftest` workflow is `runs-on: ubuntu-latest` running
`bash docs/testing/jobs/selftest.sh` with **no `pip install` and no
`setup-python`**, and the runner has neither module. CI on `b8aa251b`:
`selftest: 993 passed, 2 failed`, and the two failures were exactly the new H1
word checks. The pre-remediation head `aab3a66f4` was green on that job, so the
remediation is what turned it red.

Worse than the redness: the third check,
`check "…exits non-zero" [ "$x1a7nrc" -ne 0 ]`, **passed on the
ImportError** — a traceback exits 1 too. Relax the two word checks instead of
fixing the cause and the gate written to stop "a pass over nothing read" would
itself pass on nothing run.

**Why it was invisible.** The remediation comment's `958 passed, 0 failed` is
**true**; I reproduced exactly that on this host, which has `numpy 2.5.2` and
`PIL 12.3.0`. A green local run of this suite was never evidence about this
check. The runner is the gate of record.

**The fix, verified.** `9a4a070d` resolves the goldens with `glob` alone,
reports first, and imports the image stack only when there is something to
open, with an explicit `ImportError` path that still prints the verdict. Three
runs with both modules shadowed by a module that raises `ImportError`:

| condition | output | exit |
|---|---|---|
| no image stack, absent goldens | `compared 0 of 32`, `NOT compared -- this is a FAILURE` | **1** |
| no image stack, **goldens present** (the dangerous case) | `PROBLEM: cannot compare: shadowed`, `compared 0 of 32`, same FAILURE line | **1** |
| real environment, all four captures | `compared 32 of 32 modelled halves; 0 differ` | **0** |

And the gate now guards its own fix: reverting the imports to the top of
`score()` turns two checks red (mutant `noimp` above), so this cannot come back
unnoticed. Fragment 76 grew from 15 checks to 17.

**Confirmed on the runner, not just here.** `jobs selftest` on `9a4a070d` is
`SUCCESS` (run
[35489278941](https://github.com/jreinach-alt/hakuX/actions/runs/35489278941)),
`997 passed, 0 failed`, and all five H1 checks *ran* — they are not skipped and
not conditional:

```
ok   scoring against an absent goldens root exits non-zero
ok     and says nothing was compared, rather than that nothing differed
ok     and calls it a failure in those words
ok   with no image stack it still REPORTS rather than dying on the import
ok     and does not leak a traceback instead of a verdict
```

All three checks on the PR are green at `9a4a070d`.

### MEDIUM — M1-R: `check "no --proposed mode is advertised"` greps the wrong artifact and cannot fail — **OPEN**

`docs/testing/jobs/selftest.d/76-x1a7-model.sh:54-55`:

```sh
check "no --proposed mode is advertised" \
      x1a7hasnt "scoring the PROPOSED implementation" "$X1A7"
```

`$X1A7` is the output of `--selftest`. The string
`scoring the PROPOSED implementation` was **never** printed by `--selftest`: in
the pre-remediation file it was printed by `score()` on the `--proposed` path
(`b07c1229:…:267`), a different artifact. So the assertion is green against the
exact code it forbids, and always was — it is green on `b07c1229`'s own file
(it is not among the nine red checks in that mutant).

I built the mutant: reinstate a `--proposed` branch in `__main__` printing the
old advertisement, change nothing else. Fragment 76: **17 passed, 0 failed**,
identical to baseline. The other two M1 checks cannot help — they assert that
the write transform *equals* R1 and that `0x22` is its fixed point, which is
exactly what stays true when the mode returns.

**Failure scenario.** A later lane reads the docstring's long account of
`--proposed` and reinstates it as a convenience, or a fold resolves a conflict
in `__main__` by taking the older side. Fragment 76 stays 17/17, the check
named for exactly this event reports `ok`, and the next auditor reading the
gate concludes the mode cannot return silently. The commit message offers three
M1 guards — *"so neither the silent pass nor the vacuous mode can return
unnoticed"* — and the vacuous-mode half of that sentence is not supported by
any of them.

**What remediation should do.** Grep the artifact the mode would actually
write: run the script with `--proposed` against a scratch path and assert the
advertisement is absent from *that* output; or better, because it does not
depend on the wording of a string that no longer exists, assert against the
source that `__main__` carries no `--proposed` dispatch. Either way,
mutant-check it: reinstating the mode has to turn it **red**. This is the same
correction H1-R just received one section up — an assertion pointed at
something other than what it names.

### LOW — L-new-1: `coincidence()`'s 1,024-input sweep is computed and discarded

`docs/testing/x1a7_forward_model.py:196-201`, `:233`, `:240`. `coincidence()`
computes `differ` over all 1,024 inputs and `selftest()` unpacks it as `_`. The
line the reader sees — `so TestDstAlpha cannot distinguish them over any of
1024 inputs` — takes its number from `total = 256 * 2 * 2`, a product of
constants, not from the sweep that was just run and thrown away. Nothing is
wrong today (`same_fn` implies `differ == 0`, since `compose` is the only
path), so this is quality: but it is a figure in prose standing where a scored
count should be. `bad += differ != 0`, and print `differ` beside `total`.

### LOW — L-new-2: when *every* capture is ambiguous, the run reports "no golden", which is the opposite of what happened

New in `9a4a070d`. The pre-import resolve pass keeps only `len(hits) == 1`, and
if `resolved` is empty it prints `'%s: no golden under %s'` for every name and
returns. With two candidate directories for all four captures I get four
`PROBLEM: …: no golden under <root>` lines — under a root that holds **eight**
goldens. The verdict is right (`compared 0 of 32`, FAILURE, exit 1) and M2's
real scenario still reports correctly, because a stale set beside a fresh one
normally leaves at least one capture resolvable and the main loop then prints
the ambiguity with both paths. Only the all-ambiguous corner is misdescribed,
and the cost is a reader sent to look for a missing file instead of a duplicate
one.

Distinguishing the two cases in the early return costs one branch — and would
let the second `glob` pass be dropped, since `resolved` already holds every
answer the main loop re-derives.

## Verdict

**`needs-remediation`**, on M1-R.

Pass 1's seven findings are genuinely closed; I ran all seven rather than
reading the diff for them, and the H1 fix holds in every arrangement I could
construct, including the two that would have made a lenient fix look good. The
gate catches the exact pre-remediation file on nine checks, catches a reverted
H1-R on two, and catches a golden table edited to match a wrong model on three.
The analysis this PR exists for is untouched by anything here, and none of this
can move a pixel.

H1-R was real and the lane closed it mid-audit, correctly and with a
regression check that I confirmed fires. What is left is one guard that cannot
fail, which is the same class of defect as the two this PR already retired, and
two LOWs. None of it requires re-deriving any of the model work.

Pass 2b has one thing to verify, and it is a mutant rather than an argument:
**reinstating a `--proposed` dispatch in `__main__` must turn at least one
check in fragment 76 red.** CI is already green on `9a4a070d` (997/0, all
three checks `SUCCESS`), so nothing else is outstanding.
