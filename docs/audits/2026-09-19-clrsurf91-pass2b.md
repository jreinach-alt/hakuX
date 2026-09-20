# Audit pass 2b — PR #148, `lane/clrsurf91`, over the remediation of pass 2

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #148, branch `lane/clrsurf91`, tip **`f3ea0760c7`**, four
commits over pass 2's record at `08264445ef`:

| commit | what |
|---|---|
| `beea9729e8` | pass 2's own record landing on the branch |
| `be2208ffcf` | `Merge remote-tracking branch 'origin/master'` — the merge M3 asked for |
| `7940e23cf8` | **M3 + N1** — index regenerated on the merged tree; the `!tcg_enabled()` paragraph added to the M1 block |
| `f3ea0760c7` | `NOTES.md` records the attempt-4 re-verification |

**Why `pass2b` and not `pass3`.** Pass 2 closed M1, M2 and L1 and left exactly
one MEDIUM open (M3's mergeability half). This is the same pass-2 question
asked again of a moved tree, not a new pass over a new diff — the same shape
as `…-u152m1-pass2b/2c/2d` already in this directory. The pass-1 record
remains `2026-09-19-clrsurf91-pass1.{md,json}`.

**Date** 2026-09-19. **Records** `2026-09-19-clrsurf91-pass2b.{md,json}`.

**M1 CLOSED. M2 CLOSED. M3 CLOSED. L1 CLOSED. N1 CLOSED. N3 CLOSED. N2 open
by an explicit, reasoned deferral (LOW, out of territory, recorded). No new
findings.**

**CLEAN.** Every pass-1 scenario and every pass-2 scenario was re-derived
against the live tree at `f3ea0760c7`, not read off a diff and not taken from
pass 2's word — the branch has absorbed a 130-commit master merge since pass 2
wrote, and a merge is exactly the event that can quietly undo a verified
finding. None was undone. This goes to **`fold-ready`**.

**Read this before expecting it to fold.** The PR carries `regressed`:
`[job.arms]` judged the registered prediction **FAIL** at 16:18Z with arm B
byte-identical to arm A on all 11 captures. `jobs/fold.sh:503-513` reads that
label and declines, and the comment it posts says so explicitly — *"Your
`fold-ready` label is kept and your head is not marked failed… the fold
re-tries every tick and folds the moment the label clears."* So `fold-ready`
is the correct label to set here and it is not a claim that this will fold:
the two ways forward are the owner's `regression-accepted:<issue>` or a fix
that makes the arms job re-judge. **That is an owner decision about whether to
take a correctness-only change that moves no pixels, and an audit does not
rule on it.** Recorded here rather than left to the fold comment because pass
2 recorded it and the next reader needs it in the same place as the verdict.

---

## M3 — CLOSED, both halves, and the clean merge is genuine rather than lucky

Pass 2's scenario: `docs/testing/nv2a_index.json` conflicts, and whichever
side the resolver takes is wrong — the branch side lands `loc` values pointing
at the wrong lines for every file master has moved, master's side discards the
`surface.c` locs the change actually moved.

**It can no longer occur, and it cannot recur by the same route today.**

| check | result |
|---|---|
| `git merge-tree --write-tree origin/master HEAD` | no conflict; tree `ba30b96d13` |
| GitHub | `mergeable: MERGEABLE`, `mergeStateStatus: CLEAN` |
| `git rev-list --left-right --count origin/master...HEAD` | 29 / 19 |
| `nv2a_index.py check --tests … --support …` | **"index matches the tree (951 symbols, 2839 sites, 103 suites)"** |

**I checked the way a clean merge-tree can still be a wrong answer.** A JSON
file both sides regenerate can merge without conflict and still land a
nonsense blend of two generations — git would not object, because the hunks
are disjoint. That is not what happened here:
`git log origin/master --not HEAD -- docs/testing/nv2a_index.json` is **empty**
— master has not touched the file in any of the 29 commits it is ahead. The
merge therefore takes the branch's regeneration whole, and there is no second
generation to blend with. (The lane asserted this at 13 commits; it still
holds at 29, and I re-ran it rather than carrying the claim forward.)

**The content half re-verified against master rather than against pass 2.**
Parsing both sides of `docs/testing/nv2a_index.json`:

| | `origin/master` | `HEAD` |
|---|---|---|
| `sites` / `suites` / `symbols` / `gaps` | 2839 / 103 / 951 / 498 | 2839 / 103 / 951 / 498 |
| `suites` / `symbols` / `gaps` / `sites` array lengths | 103 / 951 / 498 / 765 | 103 / 951 / 498 / 765 |
| `tests_commit` | `91a0de45ca` | `91a0de45ca` |
| `emulator_commit` | `e239097c61` | `be2208ffcf` |

The whole 56-line diff against master is `emulator_commit` plus **forward**
`loc` motion inside `hw/xbox/nv2a/pgraph/vk/surface.c` (`1293→1372`,
`3428→3612`, `3757→3959`, …), which is the ~200 lines this branch adds to that
file. No entry is added, dropped or re-keyed. Spot-checked the arithmetic
against the file rather than trusting the tool: the index puts
`// FIXME: Cannot monitor for reads/writes; flush now` at `surface.c:3959`,
and line 3959 is that comment.

Worth stating because it inverts the finding's original direction: the
branch's index is **fresher than master's own**. Master's copy names
`emulator_commit e239097c61`, which is 29 commits behind master's tip; the
branch's names `be2208ffcf`, the merge it was generated on. The fold does not
lose index freshness here, it gains it.

**Neither prediction ref was un-ancestored by the merge.**
`git merge-base --is-ancestor aec524681e HEAD` and the same for `7980d1caa2`
both succeed at `f3ea0760c7`. Nothing was rebased. The committed prediction
still hashes to `dfcf84103eb3287dd23d171d2765607b7acdb4ac0d6378fbecf2b5f19f08f533`,
which is the sha256 in the PR body **and** the sha the `[job.arms]` comment
says it judged — so the registered artefact, the body and the verdict all name
one file.

## M1 — still CLOSED after the merge, re-derived rather than carried forward

Pass 1's scenario: a binding-absent download test-and-clears
`DIRTY_MEMORY_NV2A` over the range, hands `mem_dirty` to nobody, and the next
upload computes `mem_dirty == false` because this call already ate the
evidence — leaving `upload_pending` false and taking the stale host image.

**It still cannot occur.** The scan at `surface.c:3515` is
`if (upload && !tcg_enabled())`, so no call with `upload == false` reaches the
`bitmap_test_and_clear_atomic` at `:3530`. I re-walked the containment at the
new line numbers rather than reusing pass 2's: the gate is
`bool gate_open = upload && (!current_binding || pg_surface->buffer_dirty || mem_dirty)`
at `:3603`, `if (gate_open) {` opens at `:3610` and closes at `:3934`, and both
consumers — `surface->upload_pending |= mem_dirty` at `:3812` and
`surface->upload_pending = shelf_stale || mem_dirty` at `:3883` — are inside
it. A producer that only runs when `upload` is true cannot starve a consumer
that only runs when `upload` is true.

**The one way the widening could be wrong is still shut, and the merge is
exactly what could have reopened it.** Pass 2's argument rests on no
download-path writer of `DIRTY_MEMORY_NV2A` existing — if a download set the
bit, a retained bit would no longer mean a real CPU write and the following
upload would push guest RAM over a possibly-newer host image. 130 commits of
master arrived since that was checked, so I re-grepped the whole writer set in
`hw/`: `vk/blit.c:757`, `vk/blit.c:924`, `gl/blit.c:686` — guest-visible blit
writes, which is what the bit is for — plus the guest's own stores via
`memory_region_set_log(d->vram, true, DIRTY_MEMORY_NV2A)` at `nv2a.c:1283`.
Unchanged, and no new writer anywhere. A retained bit still means a real CPU
write, and uploading it is still the correct action.

**Master brought no competing change to this code.**
`git log origin/master --not HEAD -- hw/xbox/nv2a/pgraph/vk/` is **empty**, so
the merge could not have silently reshaped the gate, the tail or the probes.
That is why a mergeable, non-conflicting merge is also a semantically quiet
one here, and it is worth saying explicitly rather than inferring it from the
absence of a conflict marker.

The comment pair the finding asked for is still in place and still accurate:
`:3471-3499` on what the scan costs, and `:3588-3602` on what a declined
download may consume — *"the draw flags and nothing else"* — which matches the
tail, where `:3971-3972` clears `write_enabled_cache` and `draw_dirty` and
nothing else.

## M2 — still CLOSED. `addr=` survives the merge

Pass 1's scenario: an operator reads the arm log, is told by the code that
`addr=` is the number worth having, greps for it and finds no such field.

**Still cannot occur.** At the current tip: signature `:340` is
`dl91_probe(PGRAPHState const *pg, bool color, hwaddr addr)`; the format at
`:360-363` is
`"[dl91] frame=%d declined=%lu f_declined=%lu part=%s " "addr=0x%08" HWADDR_PRIx`;
the sole call site is `:3968`, `dl91_probe(pg, color, target.vram_addr)`, on
the `else` arm of `if (drawn)` — i.e. precisely the declined download. `hwaddr`
against `HWADDR_PRIx`, and both CI builds are SUCCESS on this head, which is
where a `-Wformat` mismatch would surface.

## L1 — still CLOSED. Five names, five probes

Pass 1's scenario: whoever closes #91 removes probes by the heading's count,
removes four, and ships the fifth as an always-on `SURF92_LOG` on a per-draw
surface path in a release build.

**Still cannot occur.** `:178` reads "REMOVE ALL FIVE", and I counted
definitions in the tree rather than names in the sentence: `surf91_overlap_probe`
(`surface.c:264`), `dl91_probe` (`surface.c:340`), `surf92_probe`
(`surface.c:366`), `clr89_probe` (`draw.c:838`), `clr91_probe`
(`draw.c:6839`). Five.

## N1 — CLOSED, and the citation it rests on is real

Pass 2's scenario: a later lane reads the M1 block, takes the lost write for a
defect the arms could have caught, and spends a capture set or an arm looking
for it in a `[surf92]`/`[dl91]` log or a score — where the instrument is blind
by construction, because the scan is behind `!tcg_enabled()` and the device
runs TCG.

**It can no longer occur.** `:3501-3511` now opens "WHERE THIS IS REACHABLE,
because every measurement in this project is taken where it is NOT", states
that `mem_dirty` is unconditionally false on an arm, says the fix repairs a
non-TCG host and elsewhere tightens an invariant nothing can violate, tells
the reader not to go looking in a `[surf92]`/`[dl91]` log or a score, and adds
the operational form — the gate is *"a two-term condition on every arm"*. That
is the second half of pass 2's scenario answered as well as the first.

**I read the citation rather than accepting it.** The block cites
`vk/draw.c:115-121`, and those lines say exactly what is claimed: *"The surface
upload read … is deliberately NOT instrumented: nothing on the device clears
DIRTY_MEMORY_NV2A over a surface range — the only clearer is the vertex sync
below, for its own ranges, and update_surface_part's own scan is behind
!tcg_enabled() and therefore dead here."* Same file, same line range, same
claim. A cross-file line citation is the kind that rots silently across a
merge, which is why it is checked here.

## N3 — CLOSED. The body no longer contradicts the index

Pass 2's scenario: a fold reader or the owner compares the body's "2833 sites"
against the index's 2839 and either re-regenerates the file that is already
the conflict, or re-opens the "a suite was silently dropped" question the
number existed to close; `Base: … clean` does the same for mergeability.

**It can no longer occur.** The body now reads 2839, names the `--support`
argument as non-optional (with the reason: omitting it reads exactly like a
stale index), and `Base:` names `151dc05954` with the merge at `be2208ffcf`
and how the conflict was resolved. I re-derived the `Files:` line rather than
eyeballing it — the body's eight paths are exactly
`git diff --stat origin/master...HEAD`:

```
docs/audits/2026-09-19-clrsurf91-pass1.{json,md}
docs/audits/2026-09-19-clrsurf91-pass2.{json,md}
docs/lanes/clrsurf91/NOTES.md
docs/testing/nv2a_index.json
docs/testing/predictions/issue91-download-may-not-resolve-a-binding.json
hw/xbox/nv2a/pgraph/vk/surface.c
```

(This record adds `…-pass2b.{md,json}` to that set. The lane could not list a
file that did not exist; audit records are per-pass and uniquely named, so they
are not a collision surface and the `Files:` line does not need chasing for
them.)

## N2 — open, correctly, and not a reason to hold this PR

`vk/blit.c:778-786` still justifies `pgraph_vk_solid_line()`'s direct
`upload_pending` write with a reason this PR makes false: *"their scans
test-and-clear it before the guard that consumes it, and with `upload == false`
on a live binding the bit is cleared and discarded."* With the scan
upload-only, `upload == false` now clears nothing.

The lane did not fix it and gave a reason I accept: `vk/blit.c` is in `[free]`
and is not this lane's file, so fixing it is a territory claim this lane does
not hold. It is **not left silent** — the hazard is written down at
`docs/lanes/clrsurf91/NOTES.md:433-496`, and the PR body asks the board
directly whether this lane may have the file or whether it should go to
whoever takes it next. That is the documented handling for a defect outside a
lane's grant, it is a LOW, and per the cloud role file only HIGH and MEDIUM
block. **It should not hold this PR, and it should not be dropped either** —
the board owes it an answer, because the comment's conclusion (keep the direct
write) is still right while its stated reason is now wrong, and that is the
configuration a future simplification lane deletes.

---

## Checked and found still correct, so nothing re-derives it

* **CI is green on this exact head.** Queried by sha rather than by PR, because
  a rollup can be read off a stale head: `repos/:owner/:repo/commits/f3ea0760c7/check-runs`
  returns `build` (Android) success, `build` (Desktop build) success, `check`
  (NV2A index) success.
* **No retired skip-ci marker in any of the 19 commit messages.** Scanned the
  full `%H %s%n%b` of `origin/master..HEAD`; the only "skip" hits are prose
  about the fix skipping a download.
* **`docs/lanes/clrsurf91/NOTES.md` is at the per-lane path, not the branch
  root**, so `fold.sh`'s root-`NOTES.md` resolution is not involved.
* **The upload side is still bit-identical and `gate_open` still has no
  consumer outside its own block** — `:3610` and the `surf92_probe` argument at
  `:3607`, which sits inside `if (upload)`. The remediation touched comments
  only.
* **The M3 tension about the arm's shape** (that `master -> master+fix` would
  be an inert control) was settled in pass 1 and is not re-opened, as pass 1
  asked.
* **`g_nv2a_stats` accounting, the probe's frame-rollover logic, and the
  unconditional-probe choice** were disposed of in pass 1's "not findings"
  section and nothing since has touched them.

## Verdict

**Pass-1: M1 CLOSED, M2 CLOSED, M3 CLOSED, L1 CLOSED. Pass-2: N1 CLOSED, N3
CLOSED, N2 open as a reasoned out-of-territory deferral (LOW). 0 HIGH, 0
MEDIUM open. No new findings.**

**CLEAN → remove `needs-audit-2`, add `fold-ready`.**

The remaining obstacle to this PR landing is not an audit finding: the
`regressed` label gates `fold.sh`, which keeps `fold-ready` and waits for the
owner to either accept the regression with `regression-accepted:<issue>` or
see it re-judged. And the board owes N2 a one-line territory answer.
