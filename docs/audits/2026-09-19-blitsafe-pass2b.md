# Audit pass 2 (second round) — PR #102, `lane.blitsafe`: the HIGH is closed by withdrawal, and nothing has ever built this branch

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #102, branch `lane/blitsafe`, tip **`b1e955435c`**, 27 commits
over the merge base **`38385b79c1`** (`origin/master` is now `4a442e1b75`).
**Date** 2026-09-19. **Records** `2026-09-19-blitsafe-pass2b.{md,json}`.
**Pass 1** `2026-09-19-blitsafe-pass1.md` (0 HIGH, 2 MEDIUM, 5 LOW) at tip
`aec3641413`. **Pass 2, first round** `2026-09-19-blitsafe-pass2.md`
(1 HIGH, 2 LOW new) at tip `f0a344dadd`.

**Why `pass2b` and not `pass2`.** The remediation that followed the first
pass-2 round was written against that file; overwriting it would destroy the
record the lane answered. This is the second pass-2 round of the same day, so
it gets its own name and cites the first rather than replacing it.

**Pass 1: M1, M2, L1, L2, L3 CLOSED at this tip. L4 OPEN (third round).
L5 OPEN. Pass 2 round 1: N1 (HIGH) CLOSED, N2 CLOSED, N3 CLOSED. N5 OPEN.**

**New: 1 MEDIUM (P1), whose remedy is the commit that carries this file — so
the label is pre-registered on its outcome, in "Verdict" below.**

The remediation is the strongest of the three rounds this PR has had. The HIGH
is not merely argued away: `vk/surface.c` at the tip has **no rendering
behaviour difference from master at all**, which I verified mechanically rather
than by reading the lane's summary of it, and the one behavioural change left
on the branch is the function the `#89` arm PASSed on — byte-identical at the
tip to the `b_ref` that was measured.

**The one thing that is not verified is that any of it compiles.** No CI run
has ever existed on this branch: every head it has had before this one carries
the retired skip-ci marker in its commit subject, so GitHub created no workflow
run at all and `gh api .../check-runs` returns `total_count 0`. `fold.sh`'s
`ci_green()` maps an empty rollup to `NONE` and refuses to fold, and its own
NONE text names **#102** as the PR that already sat a full day that way. This
audit's own push is a marker-free head, so it creates that missing run; the
verdict below says what each outcome means before the outcome is known.

---

## N1 (HIGH, pass 2 round 1) — CLOSED. The regressing behaviour is gone, verified as a property of the diff

Pass 2's scenario: the tip carried `#88`'s colour-wins policy, and that policy
moved `Color_zeta_overlap/Swap` from **165,447 to 304,750** differing pixels
against a `must_not_move` leg — reproduced on two discs, and confirmed
`ATTRIBUTABLE` at `runs_per_arm 3` by the 10:03Z verdict. A fold would have put
that on master.

The lane took the auditor's second route and withdrew the policy. I checked the
withdrawal the only way that settles it — the comment-stripped diff of the file
against the merge base, since master has not touched `hw/xbox/nv2a/` since:

```
$ git diff 38385b79c1 HEAD -- hw/xbox/nv2a/pgraph/vk/surface.c \
    | grep -E '^[+-]' | grep -vE '^[+-]{3}|^[+-]\s*(\*|/\*|//|\*/)|^[+-]\s*$'
```

Everything it returns is one of four things: the `SURF92_LOG` macro, the
`g_surf92` counter struct, the two probe functions `surf91_overlap_probe()` and
`surf92_probe()`, and these call sites —

| site | what it is |
|---|---|
| `surface.c:3419-3420` | `bool gate_open = !current_binding \|\| (upload && (pg_surface->buffer_dirty \|\| mem_dirty));` hoisted out of the `if` |
| `surface.c:3422-3423` | `if (upload) surf92_probe(...)`, before the gate |
| `surface.c:3508` | `surf91_overlap_probe(pg, target.vram_addr);` under `if (!color)`, inside the existing `surface == other` arm |
| `surface.c:3793-3794` | two counter assignments beside the existing `fb_dirty` |

**The hoist is not a behaviour change, and I checked the three ways it could
have been one.** The expression is character-for-character master's, including
the `||` short-circuit; `framebuffer_dirty()` is not in it and is still called
once, elsewhere; and `mem_dirty` — whose `bitmap_test_and_clear_atomic()` loop
is a *side effect*, not a read — is computed above the gate in master and is
untouched here, so nothing moved across it.

**The two removed lines are the whole of the policy.** At `f0a344dadd` the
`surface == other` arm read `if (!color) { probe; pg_surface->buffer_dirty =
false; return; }`; at the tip it reads `if (!color) { probe; }` followed by the
unconditional `unbind_surface(d, !color)` that master has always had. The
early return and the flag clear are gone. `surf91_decline_probe` was renamed
`surf91_overlap_probe` to match what the site now means, and no reference to
the old name survives anywhere in `hw/`.

So the scenario cannot occur: there is no code on this branch's `vk/surface.c`
that can move a pixel relative to master, and `Swap` is a `vk/surface.c`
regression.

**The one behavioural change that remains is `#89`'s narrowing in
`vk/draw.c`, and it is the arm that PASSed.** `pgraph_vk_get_clear_color()` at
the tip is byte-identical to the same function at `77bd2977cc`, the `b_ref` of
the PASSing 44-check arm — I diffed the function body, not the commit message.
Its inertness on `Color_zeta_overlap` was measured on an A/B pair that both
carried the policy, so the transfer to a policy-free tip is a reading rather
than a measurement; the reading is the one pass 2 round 1 verified in the tests
tree at `91a0de45` (all six `SetSurfaceFormat` sites in
`color_zeta_overlap_tests.cpp` are `SCF_A8R8G8B8`, i.e. `PAD_ALPHA_NONE`, which
takes neither branch of the switch under either source). It holds independently
of the policy, because the policy is not in that switch.

---

## N2 (LOW, pass 2 round 1) — CLOSED

Pass 2's scenario: one `reported` flag for two kinds of drop, so a frame whose
first drop is a `cdrop` suppresses that frame's first `zdrop` line entirely,
and the `zdrop` reaches the log only at a `clears % 512` heartbeat that can
land in a later frame and print *its* zero.

`draw.c:6865-6874` now computes `first_z` and `first_c` independently against
`reported_z` / `reported_c`, sets each only on its own kind, and ORs both into
`first_event`. I walked the exact scenario: `cdrop` at clear *k* sets
`reported_c` and leaves `reported_z` false, so the frame's first `zdrop` at
clear *k+n* still evaluates `first_z = true` and still prints. Both flags are
reset together on a frame change (`:6846`). The mis-report is unreachable.

## N3 (LOW, pass 2 round 1) — CLOSED

The removal condition at `surface.c:171-190` (the `LIFETIME` block, `REMOVE ALL
THREE` at `:178`) is re-anchored on **#91 being
closed**, and the text says in terms why that anchor and not the previous one:
an arm that merely replicates the regression cannot satisfy it, and it does not
expire when a ref is superseded. It also names the open arm
(`issue91-decline-frame-attribution`, `b_ref bb0ddde27d`) and records that a
PASS there means the regression reproduced. The decision now survives the event
that invalidated the first version of it.

## Pass-1 findings, re-verified at this tip

The first pass-2 round closed these at `f0a344dadd`; the remediation since then
touched both files, so they are re-checked rather than inherited.

- **M1 — CLOSED.** All four predictions still name refs contained by
  `origin/lane/blitsafe` (`git branch -r --contains`: `55bc6c6c2b` also by
  `origin/master`; `67dc7724ee`, `3f2563d6e9`, `77bd2977cc`, `bb0ddde27d`). No
  prediction file changed in this round, so no sha moved and no arm was
  re-queued. Three of the four have returned judged verdicts, which is what
  makes "not being skipped" a fact rather than an inference.
- **M2 — CLOSED, and not regressed by the new probes.** `clr89_probe()`'s gate
  at `draw.c:869-870` still ORs `flood_capped_event` with the heartbeat, and
  `g_clr89.clears` is still incremented before the gate on every call. Both
  probes added since pass 1 do the same: `surf91_overlap_probe()`
  (`surface.c:278`) and `clr91_probe()` (`draw.c:6874`).
- **L1 — CLOSED.** `nobind=%lu(structural-0)` with the reason recorded above it.
- **L2 — DECIDED**, superseded by N3's re-anchoring.
- **L3 — CLOSED.** `shapedirty=%lu(per-surface_update)` with the 2× hazard named.
- **N5 — OPEN** (carried, LOW). The Khronos validation layer is still owed and
  the desktop build is still the known host gap. The lane's claim that it is
  *less pressing* now is correct and I checked why: the colour-only framebuffer
  it was most wanted for was a consequence of the withdrawn policy, and
  `vk/surface.c` no longer produces it.

---

## P1 — MEDIUM, new. No CI run has ever existed on this branch, so the fold gate will refuse the head

`b1e955435c` (head), `3c2f6622c5`, `f5a6239588` — and every earlier head this
branch has had.

### The scenario, from the job's own code

`jobs/fold.sh:97-104` defines `ci_green()` over `statusCheckRollup` and maps an
**empty** rollup to `NONE`. `NONE` is a gate, deliberately: the comment at
`:107-112` says folding a head nothing built would be the worse bug. So a
`fold-ready` label on this PR produces one `[job.fold]` comment and then an
indefinite wait, until a person pushes over it.

That is not a hypothetical, and the hypothetical was already spent: `fold.sh`'s
own NONE text names **#102** as the PR that "sat a full day that way, its only
record a line in `$WORK/logs/fold/tick.log` that no lane can read."

### Measured, not assumed

| check | result |
|---|---|
| `gh api repos/.../commits/b1e955435c/check-runs --jq .total_count` | **0** |
| `gh run list --branch lane/blitsafe` | empty |
| `gh pr view 102 --json statusCheckRollup` | `[]` |
| the same query on #143, #141, #140, #139, #137, #136, #135 | `SUCCESS,SUCCESS[,SUCCESS]` each |

Seven neighbouring PRs get two or three green checks; this one gets none. It is
not a path filter — `android.yml` and `desktop.yml` trigger on `pull_request:`
with no `paths:` — it is the retired skip-ci marker in the head commit's
subject, which makes GitHub create no workflow run at all.

### This is not a rule the lane could see, and that does not change the consequence

`roles/lane.md` puts the marker in its **Never** section for exactly this
reason and names #101, #123, #129 and #139 as stalled by it. That text landed
on master at `4a442e1b75` (PR #140, `lane.ciskip`) — **after** this branch's
merge base `38385b79c1`, so the copy of `roles/lane.md` in this worktree does
not contain the word "marker" at all. The lane was following the instruction it
had. The gate is still shut.

### The remediation is this commit, and that is why the verdict is pre-registered

An auditor may push the audit file to the lane branch, and nothing else. That
push is a normal `pull_request: synchronize` with a marker-free subject, so
**the commit carrying this file is itself the first head of `lane/blitsafe`
that GitHub will build.** The finding's remedy and the finding's test are the
same event, which would be a tautology if I graded it afterwards — so the rule
is written down before the run, in the section below, and the label follows the
result rather than the result following the label.

If it is green, P1 and L5 are both discharged by fact rather than by argument,
and the `fold-ready` label means what `roles/board.md` says it means ("check CI
is green on its head"). If it is red, the tip does not compile — which no arm
and no audit has been in a position to say — and that is a HIGH, not a
MEDIUM.

**Note for whoever pushes next: do not quote the marker in a commit message or
a PR comment.** GitHub matches it anywhere in the message, body included, which
is how an empty commit pushed to restore a missing run suppressed that very run
on 2026-09-18.

---

## L4 — OPEN, third round. The citation habit was fixed inside `surface.c` and is still live everywhere else

Pass 1 filed three artifacts citing `draw.c:6751` for a call at `:6757`. The
first pass-2 round found it fixed in one artifact of four. This round's
remediation fixed the two investigation records and converted five `surface.c`
self-citations in `draw.c`'s comment block to symbols — the right fix, and the
commit message says so.

It did not sweep. I resolved **every** `file:line` citation in the five
artifacts this lane owns against the tip's own tree (`audit_cite_check.py`, not
committed — the check is a `re` over `file:line` and a `splitlines()`), and
twelve sites are wrong at the tip:

| artifact | cites | what is actually there | correct |
|---|---|---|---|
| `vk/draw.c:820` | `draw.c:7820` | `assert(snap.primitive_mode == …)` | the block beginning `:7987` |
| `vk/draw.c:864` | `dispatcher.sh:934` | a comment about snapshot hashes | `:1050` |
| `vk/draw.c:6798` | `draw.c:3360` | a blank line | `:3368` |
| `vk/surface.c:169` | `dispatcher.sh:934` | as above | `:1050` |
| `NOTES.md:192` | `arms.sh:213` | a goldens-directory filter | `:329` |
| `NOTES.md:276` | `surface.c:3305`, `:3276`, `:3308`, `:3322` | four numbers, all landing elsewhere (`:3305` is a `glsl/psh.c` comment) | `:3416`, `:3387`, `:3419`, `:3510` |
| `NOTES.md:463` | `draw.c:3360` | a blank line | `:3368` |
| `surface-shape-has-no-address.md:58` | `surface.c:186-221` | the probe's lifetime comment | `:287-332` |
| `surface-shape-has-no-address.md:100` | `dispatcher.sh:934` | as above | `:1050` |
| `surface-shape-has-no-address.md:126` | `surface.c:3500` | prose inside the withdrawn-policy comment | `:3617` |
| `surface-shape-has-no-address.md:131` | `surface.c:3215` | the body of the `DO_CMP` macro | `:3326` |
| `surface-shape-has-no-address.md:181` | `draw.c:6876` | a closing brace | `:7038`, `:7134` |

Four of those are in **compiled-code comments**, which is what the fold puts on
master. Two of them — `draw.c:3360` and `draw.c:7820` — are `draw.c` citing
`draw.c`, drifted by this lane's own probes: the same mechanism, in the same
file, as the finding the same commit claimed to have fixed "five more times".
The `dispatcher.sh:934` trio drifted the other way, when the branch merged
master and `dispatcher.sh` grew under a citation that was true when written.

**Still LOW, and one decline is accepted in advance.**
`issue89-clear-pad-alpha-shape.json` and
`issue91-decline-frame-attribution.json` both carry stale line numbers and both
are sha-bound to judged verdicts; editing a byte re-queues a 42-leg arm and a
3-runs-per-arm arm that have already been paid for. **Do not touch them.**
Everything in the table above is bound to nothing and costs one line each, and
the rule the lane already found is the right one: cite by symbol, or by the
condition, and the citation stops expiring.

## L5 — OPEN. Nothing has compiled the code at this tip

Pass 1 filed "the branch is uncompiled and I could not build it either". The
first pass-2 round discharged it by evidence for the refs the arms job had
built, and re-opened it for `bb0ddde27d`.

At this tip the gap is wider than it was, and it is worth stating exactly:

- the arms job has built `3f2563d6e9`, `77bd2977cc`, `55bc6c6c2b`, `67dc7724ee`
  and `bb0ddde27d`. The newest of those is **three commits before the tip**;
- `f147a588b1` — the withdrawal, the probe rename and N2's two-flag fix — has
  been built by no arm and by no CI run;
- I could not build it either. The Android build needs paths outside this
  session's writable scope and was refused; `check_android_guards.py` (3,298
  files) and `preflight.sh` both pass, and neither is a compiler.

I read `f147a588b1` for the failure modes that reading can reach and found
none: the renamed probe has no stale references, every probe symbol is defined
and called so nothing is `-Wunused-function`, `pg` is in scope at the new call
site, `pgraph_vk_get_clear_color()` no longer declares the `r` it stopped using
(which is the edit most likely to have left an unused variable), and the two
new `bool`s are locals. **Reading is still not a build**, and this is the second
reason P1's empty commit is worth more than a label: CI is the only thing on
this project that will compile this tip.

The lane reports a clean cold `assembleDebug` at `f147a588b1` with
`GRADLE_EXIT=0`. I have no way to check that from here and do not dispute it;
it is a claim in a comment, and a green check is a fact on the PR.

---

## What I checked and found clean

- **`preflight.sh` passes with no `--allow-tracker`**: psh_differ (build and
  report), aci_vmstate, nv2a index, territory, coverage, board files.
- **`check_android_guards.py` ok**, 3,298 files — the Android/desktop symbol
  split that an Android-only build cannot catch.
- **The `nv2a` index is current** at the tip (`preflight`'s own check), and its
  provenance `tests_commit` is unchanged, so the regeneration in `b1e955435c`
  did not silently drop a suite.
- **The PR body is accurate at this tip**, including the header block, and its
  `Files:` list matches `git diff --stat 38385b79c1 HEAD` — 14 paths, both
  ways. It will need the two paths this audit adds.
- **`NOTES.md` is per-lane** (`docs/lanes/blitsafe/NOTES.md`), not the branch
  root, so it cannot collide at fold time.
- **`surf91_overlap_probe()` fires at a site that exists under both policies**,
  and the comment says out loud that `declines=` counts the *opportunity* at
  this tip and the *action* at `bb0ddde27d`, keeping the field names
  byte-identical so the arm's two logs can be diffed. That is a documented
  trade and the right one; a reader who takes the field name literally at this
  tip is the only risk, and the paragraph above it forecloses that.
- **The probes cannot flood.** `surf91_overlap_probe()` is one line per frame
  plus every 512th resolution; `clr91_probe()` one line per frame per kind plus
  every 512th clear; `surf92_probe()` every miss, the first 64 address changes,
  then every 2048th update.
- **No arm will be re-queued by this round.** No prediction file changed, so no
  sha256 moved, so `already_ran()` still matches every judged verdict.

---

## Verdict

**Pass 1: M1, M2, L1, L2, L3 CLOSED; L4 OPEN; L5 OPEN. Pass 2 round 1: N1
(HIGH) CLOSED, N2 CLOSED, N3 CLOSED. Carried N5 OPEN.**

**New: 1 MEDIUM (P1), 0 HIGH, 0 LOW beyond the three carried open.**

The HIGH that blocked the fold is genuinely gone, and it is gone as a property
of the diff rather than of an argument. Nothing in the code sends this PR back.

**The label is pre-registered on P1's own test, and this is the whole rule.**
The commit carrying this file is the first head of this branch GitHub will
build, so the finding's remedy and its test are the same event and the decision
has to be written before the result:

| outcome of the checks on this head | label |
|---|---|
| every check concludes `SUCCESS` | remove `needs-audit-2`, add **`fold-ready`** |
| any check concludes `FAILURE`, `ERROR`, `CANCELLED` or `TIMED_OUT` | **`needs-remediation`**, naming the failing job — and L5 becomes a HIGH, because it would mean the tip does not compile |
| still pending when this unit must end | **`fold-ready`**, stated plainly as such: `fold.sh` folds only a GREEN head, comments on RED and on NONE, so the gate holds what I could not watch. A red result after that must be moved to `needs-remediation` by the next job to see it, not left sitting under a `fold-ready` label |

The two findings left open are both LOW and both have logged decisions: **L4**'s
twelve stale citations (fix by symbol; the two sha-bound prediction files are
declined in advance and must not be touched), and **N5**'s validation-layer
debt, which the withdrawal made less pressing for the reason checked above.

**The outcome, recorded when it arrived, is in the `[job.cloud]` comment this
audit is posted with.**
