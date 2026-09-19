# Audit pass 2d — PR #162, `claude/docs-tooling-agentic-coding-u152m1`: the GL surface pad-bit write side (#158), and #60 re-measured

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #162, branch `claude/docs-tooling-agentic-coding-u152m1`, tip
**`5baea4836e`** (local == `origin/…u152m1`), merge-base with master
**`3b27da7a3e`**, i.e. **34 ahead / 12 behind** the current `origin/master`
**`f5d40ca778`**. `MERGEABLE`, ready (not draft).
**Date** 2026-09-19. **Records** `2026-09-19-claude/docs-tooling-agentic-coding-u152m1-pass2d.{md,json}`.
**Prior passes** `…-pass1.md`, `…-pass2.md`, `…-pass2b.md`, `…-pass2c.md`.

**Why 2d.** Pass 2c closed P1–P4 and raised **A1 (MEDIUM)** — the condition
`a5fdb6a7` added at `gl/surface.c:1331` could not execute, and the commit's
central factual claim was false on this tree — plus **A2 (LOW)**, an
undeclared file. Both were remediated (`d7ef9820`, `5baea483`) and the PR came
back `needs-audit-2`. This pass verifies **A1 and A2**, re-confirms every
earlier closure at the new tip, and reads the three commits that have landed
since pass 2c and that **no pass has read**: the master merge `e239097c61`, the
revert `d7ef982090`, and the notes correction `5baea4836e`.

**Verdict: CLEAN. A1 and A2 are closed, each verified against the tree rather
than against the commit message claiming it. H1, M1, L1–L4, N1, N2 and P1–P4 all
still hold at this tip. Nothing new above LOW; the one LOW found is recorded in
"Not a blocker" below and does not warrant a pass of its own.**

Disposition: **`fold-ready`**.

---

## Part 1 — the two pass-2c findings

### A1 (MEDIUM) — CLOSED. The code is gone, and every place the false premise was read has been corrected

Pass 2c's scenario, verbatim in substance: *a lane is dispatched on #62 finding
2's device half with this PR as its brief. It arms an A/B on `a5fdb6a7`, runs
the `Texture_render_target` and `Surface_format` 565 captures on a handheld, and
gets a byte-identical result on every one. It either closes #62 as confirmed —
recording a fix that never ran as verified silicon agreement — or opens a
regression against the ratio/replicate model #59 measured. The same brief sends
a second lane at X1R5G5B5 for the same null.*

**It cannot occur at this tip, and I checked the four things that would have to
be true for it to occur anyway.**

**1. There is no longer a commit to arm.** `d7ef982090` reverts `a5fdb6a7d1`.
The file is not merely similar to master's, it is the same blob:

```
git rev-parse origin/master:hw/xbox/nv2a/pgraph/gl/surface.c  ->  c21e194098…
git rev-parse HEAD:hw/xbox/nv2a/pgraph/gl/surface.c           ->  c21e194098…
git diff --stat origin/master HEAD -- hw/xbox/nv2a/pgraph/gl/surface.c  ->  (empty)
```

`grep -rn SRC1 hw/xbox/nv2a/pgraph/gl/` and a read of the file confirm no
remnant of the condition; the branch's whole `hw/` footprint is now `gl/draw.c`,
`gl/renderer.c` and `glsl/psh.c`, which is what pass 1 and pass 2 read.

**2. The revert took the index with it, and took it cleanly.** `a5fdb6a7` had
regenerated `nv2a_index.json`; a revert of the C without the index would leave
the index describing a file that no longer says that, which is the #157 class
and exactly the kind of half-revert worth checking. It did not happen. The
branch's index diff against master touches **only** `glsl/psh.c` (198 `loc`
lines), `gl/draw.c` (102) and `gl/renderer.c` (1) — **zero `surface.c` lines**,
so every entry `a5fdb6a7` moved is back where master has it. Structure across
`a5fdb6a7^`, `a5fdb6a7`, the merge, the revert, HEAD and master is identical:
suites 103, symbols 951, sites 765 groups, gaps 498, `tests_commit`
`91a0de45ca` throughout. `preflight.sh --allow-tracker` reports `nv2a index ok`
at this tip, and the **NV2A index** workflow is `SUCCESS` on this head.

**3. Every place the false premise was read now says it is withdrawn.** Pass 2c
named three: the PR body, `docs/lanes/remote/NOTES.md`, and a comment on #62.
All three are done, and I checked the *order a reader meets them in* rather than
just their existence, because a correction appended after three pages of the
claim it corrects does not reach a top-down reader:

| where | state |
|---|---|
| PR body | a `#62 finding 2 — WITHDRAWN` section with the six-row reachability chain; `gl/surface.c` off the `Files:` line with the reason given as the diff and not a territory hand-back |
| `NOTES.md:26` — the open-issues table, the **first** mention of #62 in the file | rewritten by `5baea483` to "**WITHDRAWN — reverted in `d7ef9820`**", naming `gl/surface.c:1543`, `c234c1cc`/`f0095555`, 2026-09-12 vs the 09-13 filing date, and "**the device ask is withdrawn**" |
| `NOTES.md:677` — the old analysis section | marked **SUPERSEDED in place** by `5baea483`, with the banner stating which claims below it are wrong (every reachability one) and which are unaffected |
| `NOTES.md:754+` — the pass-2c section | the chain, the decision, and the surviving arithmetic |
| #62 comment (21:02:48Z) | "Withdrawing finding 2's fix and the device ask… this finding was already dead when I filed it", with the same chain and "there is nothing here for a device lane to confirm" |

The SUPERSEDED banner matters for the second half of the scenario. The
X1R5G5B5 sibling offer lives at `NOTES.md:737-750`, which is **inside** the
superseded span (677–753), so the banner's "every reachability claim below is
wrong" covers it; the PR body withdraws it explicitly. I checked whether the
sibling was ever offered on the issue itself, where a device lane would read it
— `gh issue view 62` body and all comments: **no comment on #62 mentions
X1R5G5B5 at all**, so the withdrawal comment not naming it leaves nothing
standing. No route to the second null.

**4. The decision pass 2c asked for is stated, with its reason.** Pass 2c
offered keep-as-documented-guard or revert and left the choice to the lane.
`NOTES.md:797` states REVERTED and why — a guard that cannot execute cannot be
tested, so relabelling it "defensive" would make the comment honest and the code
no more verifiable — and points at whoever relaxes the `is_converted` refusal as
the person who can write the exclusion with a measurement attached. That is a
disposition, not a silence.

**And the arithmetic pass 2c asked to keep is kept, where it describes the model
rather than the route.** `NOTES.md:814-829`: 4/32 and 10/64 per channel,
23,200 of 65,536 (35.4%) whole pixels, endpoints agreeing under both rules, and
the 09-13 figure of 30,720 reconciled as truncating-vs-rounding — followed by
the sentence that does the work, that ratio-versus-replication is still real
wherever a 5/6-bit surface is host-decoded and it is the surface-to-texture
*route* that does not exist.

### A2 (LOW) — CLOSED. The file is declared

`docs/investigations/gl-pad-bit-write-side-patch-shape.md` is on the PR body's
`Files:` line. I re-derived the whole line rather than checking the one path:
`git diff --name-only origin/master...HEAD` is 20 paths; remove the eight
per-lane audit records and `docs/lanes/remote/NOTES.md` (per-lane paths that
cannot collide) and the prediction (declared on its own line), and the remaining
**nine match the nine on `Files:` exactly**, in both directions. `gl/surface.c`
is correctly absent, the revert having made it byte-identical to master.

---

## Part 2 — earlier closures, re-confirmed at this tip

Re-run rather than cited, because two merges and a revert have landed since the
passes that closed them.

* **H1 (HIGH, pass 1).** `grep -rn SRC1 hw/xbox/nv2a/pgraph/gl/` gives seven
  hits; the only two code references are `draw.c:169` and `:171`, inside the
  `#ifndef __ANDROID__` opened at `:164` and closed at `:176`. The **call site**
  is the half that pass 1's own remedy got wrong and that matters more: `:474-475`
  sits in the `#else` arm of the `#ifdef __ANDROID__` at `:459`…`:483`, so on
  Android neither the function nor any call to it is presented to the compiler.
  **Android** workflow `SUCCESS` on this head (run 35469865847). Closed.
* **M1 (MEDIUM, pass 1).** Filed as **#164**, open, titled for the clear half of
  #59's write side. Not this PR's to fix. Closed by filing.
* **L1, L2 (LOW).** Unchanged; `draw.c:445-458` carries the comment that records
  why the GLES exclusion is a preprocessor guard at all three sites.
* **L3 / prediction.** `docs/testing/predictions/2026-09-19-gl-pad-bit-write-side.json`
  hashes to `29eb63008be367c497d943d5c7f1d91ca2b08aede2d2523feada4b2bae776cfa`,
  matching the body's `Prediction:` line. `a_ref dcefe557`, `b_ref 7ffcd2bc`,
  both still ancestors of `5baea483` (`git merge-base --is-ancestor`, both yes).
  No rebase: the merge-base with master is `3b27da7a`, which is the `Base:` line.
* **L4 / index.** See A1 point 2. `provenance.tests_root`/`support_dirs` still
  name the regenerating container's `/home/user/…`; still read by nothing.
* **N1 (MEDIUM, pass 2).** `gles_token_check.py` on the default target: **13
  files scanned, 0 findings**, exit 0.
* **N2 (MEDIUM, pass 2).** `pgraph_capture_run_selftest.sh`: **all fixtures
  pass**, 13 assertions across the three scenarios, including the two negative
  ones (`match-no-mismatch`, `silent-not-a-mismatch`).
* **P1, P2 (pass 2b).** `skip_ci_marker_check.sh --selftest`: **7/7**, the three
  P1 fixtures and the 128 KB P2 fixture among them. On real history the script
  reports the range count and then `14312cb34f`, which is P4.
* **P3, P4 (pass 2b).** `skip_ci_marker_check.sh` is on `Files:` and in
  `NOTES.md`. P4 stays unfixed for the stated reason and the reason still holds
  — both prediction refs are ancestors of `14312cb34f`'s descendants, so a
  reword would rewrite history a live prediction names.
* **Territory.** `check_territory.py` reads `origin/board`: `territory ok (wave
  125, 29 lanes, 76 files claimed)`. The eight NOTE lines it prints are about
  other lanes' blockers, not this branch.
* **`preflight.sh --allow-tracker`** at this tip: psh_differ build/report,
  aci_vmstate, nv2a index, territory, coverage (genuinely executed, board read
  from `origin/board`), board files — **all ok, "preflight passed - safe to
  push"**.
* **CI on `5baea4836e`**: **Android `SUCCESS`, Desktop build `SUCCESS`, NV2A
  index `SUCCESS`** — 3 of 3, runs 35469865847 / 35469865822 / 35469865838.

## Part 3 — the three commits no pass had read

* **`e239097c61`, the master merge.** Not an evil merge, checked from both
  sides. `git diff --name-only e239097c61^2 e239097c61` is exactly the branch's
  own 20 files and nothing else — so the merge kept everything master's side
  brought. `git diff --name-only e239097c61^1 e239097c61` is exactly master's
  four (`docs/lanes/nightlynotes/NOTES.md`, two `selftest.d` fixtures,
  `nightly_build.sh`) — so nothing of the branch's was dropped and no third
  content was introduced in the merge commit.
* **`d7ef982090`, the revert.** Three files: `gl/surface.c` (back to master's
  blob, verified by hash), `nv2a_index.json` (back to no-`surface.c`-delta,
  verified by diffing the index against master), and `NOTES.md` (+80, the
  pass-2c section). Nothing else moved.
* **`5baea4836e`, the notes correction.** One file, `docs/lanes/remote/NOTES.md`,
  +10/−2, the two places described in A1 point 3. Nothing under `hw/`.

## What this pass checked and did not find wrong

* The branch is **12 behind** the current `origin/master` (it was 0 behind at
  pass 2c; master has moved). GitHub reports `MERGEABLE` and all three workflows
  are green on the head, which GitHub builds as the *merge* of head and base —
  so this is not the empty-rollup/conflict shape and is not a finding. `fold.sh`
  merges rather than rebases.
* The PR is **ready, not draft**, so it is visible to the board and to `fold.sh`.
* No commit on the branch beyond the known `14312cb34f` carries the retired
  CI-skip marker, by the branch's own instrument over the full range.
* `docs/investigations/gl-pad-bit-write-side-patch-shape.md` makes no claim
  about R5G6B5, #62 or `a5fdb6a7` — it is about the pad-bit write side only, so
  A1's correction did not need to reach it.
* `pgraph_capture_run.sh`, `gles_token_check.py` and `skip_ci_marker_check.sh`
  are untouched since pass 2c; their fixtures were re-run here rather than
  assumed.

### Not a blocker — one LOW, recorded and deliberately not made a finding

The PR body's `State:` line and the CI checkbox in the definition of done both
name **`d7ef9820`** as the head; the head is **`5baea4836e`**, one commit later.
The substance is not wrong — CI is green on `5baea483` too, 3 of 3, and I
verified that rather than inferring it — and `5baea483` changes only
`docs/lanes/remote/NOTES.md`, so nothing the checkbox asserts is affected. It is
a sha label one commit stale in a body that has been rewritten four times today.
Worth a one-line edit whenever the body is next open; it does not fire any
scenario, it does not justify another remediation round trip, and sending a PR
back for it would cost more than it buys.

## Disposition

**`fold-ready`.** A1 and A2 are closed. The six pass-1 scenarios, the two
pass-2 scenarios and the four pass-2b scenarios all still hold at
`5baea4836e`. `preflight.sh --allow-tracker` is green end to end and CI is 3 of
3 on the head. The one open item the PR carries forward is **#164**, which is
filed, open, and not this branch's to close.
