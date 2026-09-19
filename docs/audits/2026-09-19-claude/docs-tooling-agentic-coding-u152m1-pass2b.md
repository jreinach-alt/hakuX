# Audit pass 2b — PR #162, `claude/docs-tooling-agentic-coding-u152m1`: the GL surface pad-bit write side (#158), and #60 re-measured

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #162, branch `claude/docs-tooling-agentic-coding-u152m1`, tip
**`26754a5e7e`**, against `origin/master` **`bb4b78689e`** — merge-base
**`732b97e2df`**, so the branch is 3 commits behind master, `MERGEABLE`, and
the base pass 2 audited over is unchanged.
**Date** 2026-09-19. **Records** `2026-09-19-claude/docs-tooling-agentic-coding-u152m1-pass2b.{md,json}`.
**Pass 1** `…-pass1.md` at tip `44b35be1eb`. **Pass 2** `…-pass2.md` at tip
`e81aaca8ae`.

**Why 2b.** Pass 2 closed all six pass-1 scenarios and raised two new MEDIUMs
(N1, N2) in tooling added after pass 1 read the diff. Those were remediated
(`07a623f0`, `833ab676`, `cb141001`) and the PR came back as `needs-audit-2`.
This pass verifies **N1 and N2**, re-confirms the six pass-1 closures still hold
at the new tip, and reads the one file that has landed since pass 2 and that no
audit has seen: **`docs/testing/skip_ci_marker_check.sh`** (117 lines, new).

**N1 and N2: CLOSED, both verified by running the mutant rather than reading the
claim. Three new findings in `skip_ci_marker_check.sh`: 1 MEDIUM, 2 LOW, plus
one correction to pass 2's own record.**

Disposition: **`needs-remediation`** — P1 only. Nothing in `hw/` is in question
and remediation must not open it; nothing in `gles_token_check.py` or
`pgraph_capture_run.sh` is in question either. The whole of this pass's
remediation is a few lines in one new shell script and one clause in the PR
body.

---

## Part 1 — the two pass-2 findings

### N1 — CLOSED. The `#else` arm of an undecided conditional is scanned, and both halves of the fix have a failing case

Pass 2's scenario: *a lane puts a desktop-only token in the `#else` of a
`#if defined(__APPLE__)`, a `#if DEBUG_NV2A_GL` or an `#ifdef GL_FOO` fallback
chain, runs `gles_token_check.py`, reads `0 findings`, pushes, and the arm64-v8a
job fails — H1 again, with the check that exists to prevent it reporting clean.*

It cannot occur at this tip. `gles_token_check.py:109-120` now inverts `live` on
`#else` only for a frame `__ANDROID__` decided (`decided` is set at `:94`/`:96`
and cleared at `:106` for `#elif`), so an unknown frame stays live in both arms.
I re-derived every leg rather than reading the commit message:

* **The two lines pass 2 named as invisible are scanned.** Driving
  `gles_visible_lines()` directly over the default target: `gl/debug.c` now
  yields lines 60-65, **67, 68**, 70, 71, 73 — 67 and 68 are the
  `glEnable(GL_DEBUG_OUTPUT)`/`assert` arm of `#if defined(__APPLE__)`, which is
  precisely what an Android build compiles. `gl/debug.h` yields 50-52, **54-61**,
  63, 65 — the macro arm of `#if DEBUG_NV2A_GL`.
* **No power lost.** `gles_token_check.py` on `gl/draw.c` at `7ffcd2bc` (the
  pre-remediation file, extracted with `git show`) reports **`:151
  GL_SRC1_ALPHA`** and **`:153 GL_ONE_MINUS_SRC1_ALPHA`** — the same two lines,
  by number, that the arm64-v8a compiler reported in H1 — and exits 1. The
  default target is **`13 files scanned, 0 findings`**, exit 0, which is the
  regression guard on a fix that makes *more* code visible.
* **`--selftest` is 9/9**, and the two fixtures that matter are discriminating,
  which I established with two mutants of my own rather than trusting the two
  in the commit messages:

  | mutant | result |
  |---|---|
  | `#else` inverts unconditionally (the pre-fix line) | **7/9** — `n1-else-of-unknown-conditional` and `else-after-elif-on-an-android-frame` red, the other seven unmoved |
  | `#elif` no longer clears `decided` | **8/9** — `else-after-elif-on-an-android-frame` red *alone* |

  So each half of the fix has exactly one failing case and the set is specific
  to the defect. That answers pass 2's remediation in the form pass 2 asked for
  (*"add the mutant above as a fixture and confirm it trips"*), and `cb141001`'s
  separate claim — that the `#elif` fixture's expected 1 is a **true** positive
  and not a knowing false one — is right on the preprocessor's own semantics:
  `SOME_OTHER_THING` is undefined, so on Android the `#ifndef` arm is skipped,
  the `#elif` is not taken, and the `#else` arm is what compiles.
* **The direction of the residual error is still the conservative one.** On an
  `#ifdef __ANDROID__ … #elif … #else …` chain the script marks the `#elif` and
  `#else` arms live where Android would compile neither: it over-reports, which
  is the docstring's stated contract.

### N2 — CLOSED. The runner refuses a mislabelled run, and the fixtures fail on a mutant

Pass 2's scenario: *a sweep loops the runner over `OPENGL` and `VULKAN` on a
host whose GL context is unavailable; both arms come up on Vulkan, both exit 0,
both produce 236 captures, and the OPENGL arm's captures are Vulkan's — which
reads out as "GL is byte-identical to Vulkan", this PR's own headline.*

It cannot occur. `pgraph_capture_run.sh:109-117` lowercases both sides and
`die`s on a mismatch, before the extractor. Run here, with `SELFTEST_TMP` inside
the worktree:

* `pgraph_capture_run_selftest.sh` — **13 assertions, all pass**, in under a
  second with no emulator, firmware, disc or X server.
* **Against a mutant** built by deleting exactly the nine lines the fix added
  (`sed '/^# \.\.\.and ENFORCE it\./,/^fi$/d'`) and pointed at with `RUNNER=`:
  **`mismatch-refuses`, `mismatch-names-both` and `mismatch-says-discarded` go
  red; cases 2 and 3 are unmoved.** The mutant/control claim in the PR body is
  therefore not a claim I took on trust — case 2 (`OPENGL` asking, `OpenGL`
  reported) still reaches the extractor and still logs
  `requested=OPENGL got=OpenGL`, so the cheapest way to pass case 1 — a blanket
  `die` — fails case 2.
* Every assertion reads words in the message and each case separately asserts
  the stub ran (`nv2a: init` in the run log), so a refusal cannot be confused
  with a broken harness. That is the fix to the "green for the wrong reason"
  the lane found in its own case 3, and it is implemented, not just described.

### N3 (LOW) — CLOSED as prose

The PR body now reads *"the call site now excludes GLES the way `gl/renderer.c`
does -- by preprocessor, because on GLES the tokens themselves are absent rather
than merely unwanted -- while `psh.c:2018` and `:3568` keep the run-time
`&& !ps->opts.gles` term, a shader gate having no token to be absent"*, and
names it as a deliberate two-and-one. That is exactly the clause N3 asked for.

## Part 2 — the six pass-1 scenarios, re-confirmed at this tip

Pass 2 closed all six at `e81aaca8ae`. Nothing since touches the emulator, so
none can have reopened, and I checked that rather than assuming it:

* `git diff --stat e81aaca8ae HEAD -- hw/` is **empty**. The four commits since
  are `docs/audits/`, `docs/lanes/remote/NOTES.md`, `docs/testing/`.
* `grep -rn SRC1 hw/xbox/nv2a/pgraph/gl/` gives seven hits; the two code
  references are `draw.c:169` and `:171`, both inside the `#ifndef __ANDROID__`
  at `:164`-`:176`. **H1 stays closed.**
* The prediction is untouched and still bound: `sha256` is
  `29eb63008be367c497d943d5c7f1d91ca2b08aede2d2523feada4b2bae776cfa`, matching
  the PR body's `Prediction:` line, and `a_ref dcefe55745` / `b_ref 7ffcd2bce8`
  are both still ancestors of `26754a5e7e`. **L3 stays closed.**
* `nv2a_index.json` at HEAD and at `origin/master` agree: **suites 103, symbols
  951, `tests_commit 91a0de45ca`.** No suite lost. **L4 stays closed.**
* M1 and L1/L2 are prose and code that has not moved.

**CI.** At the time of writing, the head `26754a5e7e` has `check` **pass** and
two `build` runs **pending**. H1's closure does not rest on them — it rests on
the Android job that went green on `e81aaca8ae` with `arm64-v8a` built rather
than skipped, plus the fact that `hw/` is byte-identical since. But
`fold.sh` needs a green head, so the fold gate is the two pending builds, not
this audit.

---

## Part 3 — new findings, in the file that landed after pass 2

`26754a5e7e` adds **`docs/testing/skip_ci_marker_check.sh`** (117 lines). It is
a good idea, it is well-argued, and its three fixtures pass. The findings below
are all about what it cannot see.

Run against this branch it does exactly what it says: it reports
**`14312cb34f`**, exit 1 — a genuine positive in real history.

### P1 (MEDIUM) — a range that does not resolve prints `clean` and exits 0, having scanned nothing

`docs/testing/skip_ci_marker_check.sh:56` (and `:103`)

```sh
done < <(git log --format='%H' "$range" 2>/dev/null)
```

`git log` on an unresolvable range writes nothing to stdout, its error goes to
`/dev/null`, the `while` body never runs, `found` stays 0, and `scan` returns
success. The caller then prints **`clean`** and exits 0. Measured:

```
$ skip_ci_marker_check.sh origin/mastr..HEAD
scanning every commit body in origin/mastr..HEAD for the retired CI-skip marker
clean            # exit 0
```

There is nothing in the output that distinguishes *"I read 24 commit bodies and
none carried the marker"* from *"I read nothing"*. The count is never printed
and git's own diagnosis is discarded.

**Failure scenario.** A lane runs the check before pushing — which is the only
way it ever runs; it is wired into nothing (`grep -rn skip_ci_marker_check`
matches only its own usage lines) — in a worktree or container where
`origin/master`, the **default** range's left endpoint, is not present: a
single-branch clone, a fetch that named only the lane branch, an agent worktree
created off a bare mirror. Or it mistypes the range it passes. The check prints
`clean`, the lane pushes a commit whose body carries the marker, GitHub creates
no workflow run, the PR's check rollup comes back empty, and `fold.sh` cannot
fold a head nothing has built — the #101/#123/#129/#139 stall this script was
written to prevent, with the instrument that exists to prevent it reporting
success. **There is no downstream gate for this class**: `fold.sh:343` only
names the marker as "the usual cause" *after* a fold has already landed with no
CI. That is what separates P1 from pass 2's N1, where the Android CI job was the
gate of record and the script a convenience.

**Remediation.** Make the range a precondition rather than a silent input, and
print what was scanned:

```sh
n=$(git rev-list --count "$RANGE" 2>&1) || {
    echo "cannot resolve $RANGE: $n" >&2; exit 2; }
echo "scanning $n commit bod{y,ies} in $RANGE …"
```

and add a fixture: a range naming an absent ref must exit **2** with a message,
not `clean`. The existing three fixtures all pass a resolvable range, so this
invariant currently has no failing case.

### P2 (LOW) — `pipefail` plus `grep -q` loses a marker in a commit body larger than the pipe buffer

`docs/testing/skip_ci_marker_check.sh:41,52`

`set -o pipefail` is on, and `grep -qF` exits at the first match, closing the
pipe. On a message small enough for git's write to complete first this is
harmless; once the body exceeds the 64 KB pipe buffer, `git log` is killed by
SIGPIPE, the pipeline's status becomes **141**, `pipefail` propagates it, the
`if` is false, and the commit is **not reported**. Measured on a throwaway repo,
marker in the first line of the body:

| body | verdict |
|---|---|
| 4 KB, 16 KB, 32 KB, 60 KB, 64 KB | found |
| 128 KB | **MISSED — prints `clean`, exit 0**, 10 runs out of 10 |

and directly: `git log -1 --format=%B <c> | grep -qF -- "$MARKER"` returns
**141** with `pipefail` and **0** without, while `grep -cF` on the same input
returns 1.

**This is LOW and should not be escalated**, for a measured reason: the largest
commit-message body in the last 3,000 commits of this repository is **10,919
bytes**, six times under the threshold, so no commit that exists today can hit
it. It is a latent hazard in a new instrument, not a live miss.

**Remediation.** Both P1 and P2 disappear with one change — take the pipe out:

```sh
msg=$(git log -1 --format='%B' "$c") || die …
case "$msg" in *"$MARKER"*) … ;; esac
```

### P3 (LOW) — the new script is on no `Files:` line and in no lane record

`docs/testing/skip_ci_marker_check.sh`

The PR's `Files:` line names `pgraph_capture_run.sh`,
`pgraph_capture_run_selftest.sh`, `gles_token_check.py` and `nv2a_index.json`;
it does not name `skip_ci_marker_check.sh`, and neither
`docs/lanes/remote/NOTES.md` nor the PR body mentions the file at all. `board.sh`
reads `Files:` from open PRs to keep two lanes off one file, and `docs/testing/`
is `lane.toolsmith`'s domain — this is the same omission pass 2 recorded for
`nv2a_index.json` and the lane then fixed. It is a new file, so a collision
would be a visible create/create conflict rather than a silent overwrite, which
is why it is LOW.

**Remediation.** Add the path to `Files:` and one paragraph to `NOTES.md` saying
what the script is and that it is deliberately not wired into `preflight.sh`.

### P4 (LOW) — correction to pass 2's record: this branch *does* carry the retired marker, in `14312cb34f`

Pass 2's "checked and did not find wrong" list states: *"None of the branch's
commit subjects or bodies carries the retired skip-ci marker."* **That is
wrong**, and the instrument this branch itself added is what shows it:
`skip_ci_marker_check.sh origin/master..HEAD` reports `14312cb34f` and exits 1.
The marker sits in that commit's body, inside a sentence recording that the
marker had been retired — the trap `AGENTS.md` names in its own words, since
GitHub matches the string in prose as readily as in an instruction.

**It is inert at this head and must not be "fixed" by rewording.**
`14312cb34f` is not the head; the head `26754a5e7e` is clean and has workflow
runs; and `fold.sh` merges rather than squashes, so no fold promotes that body
to a head. Rewording is affirmatively the wrong answer here: `14312cb34f` is an
**ancestor of the prediction's `b_ref 7ffcd2bce8`** (verified with
`git merge-base --is-ancestor`), so rewriting it rewrites history a registered
prediction depends on — which `roles/lane.md` forbids and which the script's own
header correctly warns against.

**Remediation.** One line in the PR body: name the commit, say it is inert
because it is not and cannot become a head, and say why it is not being
reworded. That is what the script tells its own operator to do, and it converts
the finding from a thing a future reader will re-discover into a thing the PR
records.

---

## What this pass checked and did not find wrong

* The N1 fix does not over-reach: the default target is still `0 findings`
  after 21 previously-hidden frames became visible, so the fix added coverage
  without adding noise.
* The N2 comparison is case-insensitive over the whole string, and the two
  values it must reconcile are the script's `OPENGL`/`VULKAN` and xemu's
  `OpenGL`/`Vulkan`. Case 2 proves the equal path does not fire.
* `pgraph_capture_run_selftest.sh` honours `SELFTEST_TMP`, which is what let it
  run under a sandbox that permits writes only inside the worktree. It empties
  that directory on entry and says so in its header.
* The branch is 3 commits behind `origin/master` and GitHub reports
  `MERGEABLE`; the prediction's refs are ancestors of the tip and no rebase has
  happened (the branch merges master in).
* `docs/lanes/remote/NOTES.md`'s new 117-line section is accurate against what I
  re-ran: 9/9, the two named debug lines now visible, `:151`/`:153` still
  reported, 13 assertions, and the mutant result. The one figure I did not
  check is "7,341 non-blank lines are visible on the default target now".

## Disposition

**`needs-remediation`** — **P1** (MEDIUM) alone forces it. P2, P3 and P4 are
LOW; P2 shares P1's one-line fix, P3 is a `Files:` edit and a paragraph, P4 is a
sentence in the PR body. A remediation pass that takes all four is under half an
hour and touches one 117-line shell script plus the PR body.

**Do not reopen `hw/`, `gles_token_check.py` or `pgraph_capture_run.sh`.** The
three renderer files have been settled since pass 2; the two instruments now
each carry a fixture per invariant and a mutant that trips it, which is more
than anything else in `docs/testing/` can say.
