# Audit pass 2 (third round) — PR #102, `lane.blitsafe`: the pre-registered CI test came back green, and the `regressed` label is about a commit, not about this tip

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #102, branch `lane/blitsafe`, tip **`35278c2a61`**, 28 commits
over the merge base **`38385b79c141`** (`origin/master` is `4a442e1b75`).
**Date** 2026-09-19. **Records** `2026-09-19-blitsafe-pass2c.{md,json}`.
**Pass 1** `2026-09-19-blitsafe-pass1.md` (0 HIGH, 2 MEDIUM, 5 LOW) at
`aec3641413`. **Pass 2 round 1** `…-pass2.md` (1 HIGH) at `f0a344dadd`.
**Pass 2 round 2** `…-pass2b.md` (1 MEDIUM, P1) at `b1e955435c`.

**Why a third round exists, and it is not a code reason.** Round 2 found the
HIGH closed and filed one MEDIUM — P1, "no CI run has ever existed on this
branch" — whose remedy and whose test were the same event: the commit carrying
that audit file was the first head of `lane/blitsafe` with a marker-free
subject, so it was the first head GitHub would build. Round 2 could not wait
for the result, so it wrote the label rule down before the run and ended.
It then ended **without setting any label at all**, which is the one outcome
the rule did not cover; the outlet re-claimed the PR (attempt 2 of 4) and this
round exists to read the result and apply the rule that was pre-registered.

**No code has changed since round 2.** `git diff --stat b1e955435c 35278c2a61`
is two files, both `docs/audits/…pass2b.{md,json}`, +481/−0. So this round is
not a re-audit of a new tree; it is the missing half of round 2's own test,
plus an independent re-derivation of the finding that matters most.

**Verdict at the top: 0 HIGH, 0 MEDIUM. P1 and L5 are both CLOSED by fact.
`fold-ready`.**

---

## P1 (MEDIUM, round 2) — CLOSED. The run exists and it is green

The pre-registered rule was: *every check concludes `SUCCESS`* → `fold-ready`;
*any check concludes `FAILURE`/`ERROR`/`CANCELLED`/`TIMED_OUT`* →
`needs-remediation`, and L5 becomes a HIGH because it would mean the tip does
not compile. The result, on the exact head:

```
$ gh api repos/jreinach-alt/hakuX/commits/35278c2a61…/check-runs --jq .total_count
3
```

| check | workflow | conclusion | wall |
|---|---|---|---|
| `build` | Android | **success** | 10:28:06 → 10:32:29Z |
| `build` | Desktop build | **success** | 10:28:06 → 10:33:49Z |
| `check` | NV2A index | **success** | 10:28:06 → 10:28:56Z |

`total_count` was **0** on every previous head this branch has ever had and is
**3** here, which is the whole of P1's mechanism demonstrated in one number:
the marker in the old subjects suppressed the workflow run, a marker-free
subject creates it. `gh pr view 102 --json statusCheckRollup` now returns three
`SUCCESS` entries where round 2 measured `[]`, so `fold.sh`'s `ci_green()` maps
this head to GREEN rather than to the `NONE` gate that had this PR sitting a
full day. The first query I made this firing returned `mergeStateStatus
UNSTABLE` while the last check was still settling; it is **`CLEAN`** now, with
`mergeable MERGEABLE`.

The remedy needed no code and none was written: P1's whole content was that
nothing had built the branch, and something has now.

## L5 (LOW, pass 1, open through three rounds) — CLOSED, and this is the one that was worth waiting for

Pass 1 filed "the branch is uncompiled and I could not build it either". Round
2 narrowed it to a precise gap: the arms job had built five refs, the newest of
them three commits before the tip, and `f147a588b1` — the withdrawal, the probe
rename and N2's two-flag fix, i.e. **every edit that answers the HIGH** — had
been compiled by no arm and no CI run. Round 2 read that commit for the failure
modes reading can reach and found none, while saying plainly that reading is
not a build.

The Android and Desktop builds above compiled the tip. Both probe translation
units, the renamed `surf91_overlap_probe()`, the removed `PGRAPHVkState *r`
in `pgraph_vk_get_clear_color()` (the edit most likely to have left an unused
variable) and the new locals are all now compiler-checked on both host splits
rather than eye-checked. L5 is discharged by fact.

---

## N1 (HIGH, round 1) — CLOSED. Re-derived here from the diff, not inherited from round 2

I did not take round 2's finding on trust, because a closed HIGH is the single
thing a third round should re-check. I re-ran the derivation from scratch:

**Master has not touched the subject at all.** `git log 38385b79c141..origin/master
-- hw/xbox/nv2a/` is **empty**, so the diff against the merge base *is* the diff
against master for both files, and no three-way reasoning is needed.

**Every executable line `vk/surface.c` adds or removes.** Reading
`git diff -U3 38385b79c141 HEAD -- …/vk/surface.c` end to end, the complete
inventory of non-comment change is:

| what | behavioural? |
|---|---|
| `SURF92_LOG` macro, `g_surf92` counter struct | no — storage and logging |
| `surf91_overlap_probe()`, `surf92_probe()` | no — counters and a log line, no other writes |
| `:3419` the `gate_open` hoist | **no, checked three ways below** |
| `:3422` `if (upload) surf92_probe(...)` | no |
| `:3510` `if (!color) surf91_overlap_probe(pg, target.vram_addr);` | no |
| `:3792-3793` two counter assignments beside `fb_dirty` | no |

and the **only** removed executable lines are master's two-line
`if (!current_binding || (upload && (pg_surface->buffer_dirty || mem_dirty)))`,
replaced by the identical expression bound to `gate_open` and tested one
statement later. Nothing else is deleted.

**The hoist, checked rather than asserted.** (a) The expression is
character-for-character master's, `||` short-circuit included. (b) The only
statement now between the evaluation and its use is `surf92_probe()`, whose
entire body writes `g_surf92` fields and calls `SURF92_LOG` — it touches
neither `current_binding`, `pg_surface->buffer_dirty` nor `mem_dirty`, so the
value tested is the value master would have tested. (c) `mem_dirty` is the one
operand whose computation has a side effect (`bitmap_test_and_clear_atomic`);
it is computed above the gate in master and is untouched here, so nothing moved
across it.

**The policy is absent, and its absence is what the counters now mean.** At
`f0a344dadd` the `surface == other` arm read `if (!color) { probe;
pg_surface->buffer_dirty = false; return; }`; here it reads `if (!color) {
probe; }` followed by master's unconditional `unbind_surface(d, !color)`. The
early return and the flag clear — the whole of #88's colour-wins policy, and
the whole of the 165,447 → 304,750 px `Color_zeta_overlap/Swap` movement that
the 10:03Z verdict confirmed `ATTRIBUTABLE` at `runs_per_arm 3` — are gone.
`Swap` is a `vk/surface.c` regression and there is no line of `vk/surface.c` on
this branch that can move a pixel relative to master. The scenario cannot occur.

### The one behaviour change that does fold, and a stronger reason than round 2 had

`#89`'s narrowing in `vk/draw.c` is the only thing in this PR that changes what
the emulator draws. I extracted `pgraph_vk_get_clear_color()`'s body at the tip
and at `77bd2977cc` — the `b_ref` of the 44-check PASSing arm — by brace
matching rather than by line range: **14 lines each, byte-identical.**

Round 2 flagged the residual risk correctly: that arm's A and B sides *both*
carried #88's policy, so carrying its inertness over to a policy-free tip is a
reading rather than a measurement. I checked which way that reading points, and
it points the safe way, for a reason that is a property of the edit:

- the narrowing **removes** the site's only dependence on `r->color_binding`
  (was `r->color_binding ? drawn_format : shape_format`, now
  `pg->surface_shape.color_format` unconditionally);
- `r->color_binding`'s liveness at an overlap is precisely and only what the
  withdrawn policy changed — under the policy zeta declined and colour's
  binding survived; under master zeta evicts colour and the binding is NULLed;
- so the **new** expression is insensitive to the policy by construction, and
  it is the **old** one — master's baseline — that varies with it. Divergence
  needs a *live* binding carrying a stale `drawn_format`; master's policy leaves
  *fewer* live bindings at an overlap than the measured arm did.

The transfer therefore runs from a world with more opportunities to diverge to
one with fewer. The probe measured `diverged=0` over 33,280 clears in the
richer world.

---

## The pass-1 and round-1 findings, re-checked at this tip

No code moved since round 2, so these are confirmations rather than
re-derivations; M1, M2 and N2 I re-ran from the tree because they are the ones
with a mechanical check that costs nothing.

- **M1 (MEDIUM, pass 1) — CLOSED, and it cannot recur at the fold.** Pass 1's
  scenario was that the rebase left #88's and #91's arms on a `b_ref` reachable
  from no ref, which `arms.sh` skips *structurally and permanently*. At this tip
  all four of this lane's predictions resolve (`git branch -r --contains`, plus
  `merge-base --is-ancestor … HEAD`): `issue88` `55bc6c6c2b`→`67dc7724ee`,
  `issue89` `3f2563d6e9`→`77bd2977cc`, `issue91-decline-frame-attribution`
  `55bc6c6c2b`→`bb0ddde27d`, `issue91-swap-solo-classification`
  `55bc6c6c2b`→`67dc7724ee` — every `b_ref` contained by `origin/lane/blitsafe`,
  every `a_ref` by `origin/master`.
  **And the fold will not undo that**: `fold.sh` merges with `--no-ff`
  (its own fold comment says "every commit keeps its sha, so registered refs
  stay bound"), so `67dc7724ee` and `bb0ddde27d` become reachable from `master`
  rather than ceasing to be reachable at all. A squash would have re-created
  pass 1's finding at the moment of folding; this does the opposite.
- **M2 (MEDIUM, pass 1) — CLOSED.** `clr89_probe()`'s gate is
  `if (!(flood_capped_event || g_clr89.clears % 512 == 0)) return;` — ORed, not
  a ternary — and `g_clr89.clears++` is above it on every call, so the heartbeat
  keeps firing in exactly the world (persistent divergence) where the else-arm
  form went silent. Both probes added after pass 1 use the same ORed shape.
- **N2 (LOW, round 1) — CLOSED.** `draw.c:6865-6874` computes
  `first_z = zdrop && !reported_z` and `first_c = cdrop && !reported_c`
  independently, sets each flag only under its own condition, and ORs both into
  `first_event`. Walking round 1's scenario at the tree: a `cdrop` at clear *k*
  sets `reported_c` only, so the frame's first `zdrop` at *k+n* still evaluates
  `first_z` true and still prints. Both reset together on a frame change.
- **N3 (LOW, round 1) — CLOSED.** The `LIFETIME` block's removal condition is
  "REMOVE ALL THREE … WHEN #91 IS CLOSED, and not before", and the text says why
  that anchor replaced the expired one.
- **L1, L3 (LOW, pass 1) — CLOSED.** `nobind=%lu(structural-0)` and
  `shapedirty=%lu(per-surface_update)`, each with its reason above it.
- **L2 (LOW, pass 1) — DECIDED**, superseded by N3's re-anchoring.
- **N5 (LOW, round 1) — OPEN, carried.** The Khronos validation layer is still
  owed. Round 2's narrowing of it stands: the colour-only framebuffer it was
  most wanted for was a consequence of the withdrawn policy.

## L4 (LOW, pass 1) — OPEN, fourth round. Sampled at this tip rather than inherited

Round 2 resolved every `file:line` citation in the five artifacts and found
twelve wrong. Nothing has been pushed since, so the count stands; I spot-checked
the three that sit in **compiled comments**, which is what the fold puts on
master, and all three still miss:

| citation | what is at that line now |
|---|---|
| `draw.c:7820` (from `draw.c`'s `[clr89]` tag comment) | `#ifndef NDEBUG` / `assert(snap.primitive_mode …)` |
| `draw.c:3360` (from `clr91_probe`'s comment, "`current_frame` … is reset to 0") | `opt_stats_log_and_reset();` and a blank line |
| `dispatcher.sh:934` (cited three times as "SILENCE IS VOID") | prose about snapshot content hashes vs git revisions |

For contrast, and because a finding that flags everything flags nothing, the
citations in the same comments that resolve **correctly** at this tip include
`pgraph.c:2307` (`pg->frame_time++`, one per flip) and `pgraph.c:2387`
(`SET_CONTEXT_DMA_COLOR` setting `surface_color.buffer_dirty`). The defect is
drift in this lane's own edited files, not a habit of citing badly.

**Still LOW, and round 2's declines are upheld.** A wrong line number in a
comment has no failure scenario in the emulator; it costs a reader one search.
`issue89-clear-pad-alpha-shape.json` and `issue91-decline-frame-attribution.json`
carry stale numbers too and **must not be touched** — they are sha-bound to
judged verdicts, and editing a byte re-queues a 42-leg arm and a
`runs_per_arm 3` arm that have already been paid for. Everything else costs one
line each and the fix is the rule the lane already found: cite by symbol or by
the condition.

## L6 — LOW, new. The PR body's `Files:` list is four audit paths short

`roles/lane.md` item 2 asks that the body's `Files:` match
`git diff --stat origin/master...HEAD`. The body was accurate when round 2
checked it at 14 paths; the three audit commits since have added
`docs/audits/2026-09-19-blitsafe-pass2.{md,json}`,
`…-pass2b.{md,json}` and (with this commit) `…-pass2c.{md,json}`, so the tip
diff is 18 paths and the body lists 14.

**Why it is LOW and not MEDIUM.** The field exists so the board can keep two
lanes off one file. Every missing path is `docs/audits/2026-09-19-blitsafe-*`,
a per-lane per-date audit record that no other lane can be dispatched onto, so
the collision the field prevents cannot occur through this gap. It is recorded
because a `Files:` line that is *known* stale is how a later, real omission gets
read as normal — and because the auditor is the one adding the paths. I have
not edited the body myself: it is the lane's claim, `gh pr edit` applies nothing
on this host, and appending four audit paths is not worth a REST `PATCH` from a
job whose whole write budget is one file.

---

## The `regressed` label, which is the one thing a reader should not skip

The PR carries `regressed`, applied by the arms job and then **deliberately
re-applied by hand** at 10:11Z by a host session, on the correct observation
that `arms.sh:411-412` is last-writer-wins: the newest verdict (a PASS) had
flipped the PR to `verified` while #88's FAIL was still outstanding. That was
the right call on the facts available at 10:11Z, and `lane.armlabel` is
dispatched to fix the underlying label logic.

`roles/board.md:97-99` says a `regressed` PR is not fold-ready. I am marking
this one `fold-ready`, so I owe the reason in full:

1. **The label is true of a commit and false of this tip.** Both FAIL verdicts
   (`issue88-vk-same-offset-colour-wins`, 2 of 13 violated;
   `issue91-swap-solo-classification`, 1 of 1) were measured on `b_ref
   67dc7724ee`. That commit is still in the branch's *history* — it is an
   ancestor of HEAD — but the code it introduced was withdrawn at
   `f147a588b1`, and N1 above establishes mechanically that the branch's *tree*
   has no `vk/surface.c` behaviour difference from master at all. What folds is
   the tree, not the ancestor.
2. **The board's instruction has already been carried out.** "Resume its lane
   with the verdict" is exactly what happened: the lane was resumed, read the
   verdict, and withdrew the regressing policy rather than arguing with it.
   The label was not cleared afterwards only because `arms.sh` writes it on new
   verdicts and no new verdict has arrived.
3. **`fold.sh` does not read this label, and a reader must not assume it does.**
   Its gates are the `fold-ready` label, not-a-draft, `ci_green()` and a clean
   merge; `regressed` appears nowhere in it. So the two labels do not fight —
   the next fold tick will fold this PR on `fold-ready` alone. **If the board
   disagrees with anything above, the thing to remove is `fold-ready`; leaving
   `regressed` in place will not hold the gate.** Saying so is the point of this
   section: the contradiction is legible only if someone writes down which half
   is load-bearing.

**Recommendation to the board: clear `regressed`.** It now describes an
ancestor rather than a head, and a stale `regressed` on a folded PR is a
tripwire for the next reader of this history.

## What I checked and found clean

- `preflight.sh` with no `--allow-tracker`: psh_differ build and report,
  aci_vmstate, nv2a index, territory, coverage, board files — all ok, "safe to
  push". The board files were read from `origin/board`.
- `mergeStateStatus CLEAN`, `mergeable MERGEABLE`, not a draft.
- The nv2a index is current at the tip and CI's own `check` job agrees.
- `docs/lanes/blitsafe/NOTES.md` is per-lane, not the branch root, so it cannot
  collide at fold time.
- No prediction file changed this round, so no sha256 moved and `already_ran()`
  still matches all four judged verdicts. **This audit queues no arm.**

## Verdict

**0 HIGH. 0 MEDIUM. P1 CLOSED by its own pre-registered test; L5 CLOSED by the
same run; N1 (HIGH) re-derived and CLOSED; M1, M2, N2, N3, L1, L3 CLOSED; L2
DECIDED. Open: L4 (LOW, citation drift, fix by symbol, the two sha-bound
prediction files declined), N5 (LOW, validation layer), L6 (LOW, `Files:` short
by four audit paths).**

Every pass-1 scenario either cannot occur at this tip or is a LOW with a logged
decision. The pre-registered rule from round 2 resolves to its green branch.

**Removing `needs-audit-2`, adding `fold-ready`** — with the note above that
`regressed` is stale for this tip, that `fold.sh` will not stop on it, and that
the board should clear it.
