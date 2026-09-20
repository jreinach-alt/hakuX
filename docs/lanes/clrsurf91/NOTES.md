# lane.clrsurf91 -- #91: a zeta image is downloaded over a colour address

**Branch** `lane/clrsurf91`, base `origin/master` @ `6ca12eb803`. **PR #148.**
Files touched: `hw/xbox/nv2a/pgraph/vk/surface.c` only. `vk/draw.c` was granted
and is **not** edited; why is below, because it is the substantive finding.

## Why attempt 1 did not finish (recorded per the resume)

Nothing was missing from the work. The fix, the prediction, the arm
scaffolding and this file were all committed and pushed at `b119c43a72`, and CI
went green on that head. **The session ended waiting for that CI result with
the PR still in draft**, and a draft is invisible to every actor here --
`board.sh:107` skips drafts, `fleet.py`'s READY-NOT-FOLDED counts only
non-drafts, `fold.sh` folds only non-drafts, `handback.sh` does not look at
them. So a finished, green PR sat unfoldable and indistinguishable from an
abandoned one, and cost a whole resume.

The lesson is the ordering, not the vigilance: **mark ready when the head is
green and current, not after some later re-merge**. Waiting for CI is not a
reason to stay in draft -- a red check on a ready PR is visible and
actionable; a green check on a draft is not visible at all. Attempt 2 did only
this: merged `origin/master` (clean, 5 commits, no conflict with the index),
re-verified both prediction refs are still ancestors of the merged head, ran
the selftest, and marked ready.

## What this lane changed

`update_surface_part()`'s gate was

```c
bool gate_open = !current_binding || (upload && (buffer_dirty || mem_dirty));
```

and is now

```c
bool gate_open = upload && (!current_binding || buffer_dirty || mem_dirty);
```

plus a tail that copes with the NULL binding that change makes reachable: it
skips the download and **retires the flags**. Plus `dl91_probe()`, which counts
the declined downloads.

The upload side is bit-identical -- the two predicates agree whenever `upload`
is true. Only the download side changes, and only by declining to invent a
binding.

## The finding, and why the issue's own attribution sent two lanes at a wall

The tracker's live falsifier says the `0xFE242424 -> 0x00000024` background is
"a Z24S8 depth-only clear of 0 landing on the COLOUR surface" and points the
next lane at `pgraph_vk_clear_surface()`. **The byte arithmetic is right and
the word "clear" is wrong.**

Both clear paths in `vk/draw.c` guard `write_zeta && r->zeta_binding` -- the
inline one at the `vkCmdClearAttachments` block and the fall-through pipeline
one the brief pointed me at. I read both. Neither can issue a depth clear with
no zeta binding, and the signature needs *one image to have taken both clears*.
lane.blitsafe hit this wall and said so; the brief's "look at the fall-through
PIPELINE clear path instead" is the same wall one step along. **Do not spend a
third lane there.**

The same word falls out of the surface conversion path with no free parameter:

| step | where | result |
|---|---|---|
| VRAM holds the colour clear | `PrepareDraw(0xFE242424, 0)` | `0xFE242424` |
| a Z24S8 zeta image is uploaded from it | `unpack_z24s8_to_d32_sfloat_s8_uint_glsl` | depth `0xFE2424`, stencil `0x24` |
| the test's own depth clear of 0, on the legitimate zeta target | correctly guarded | depth `0`, stencil **untouched** |
| that image is packed back over VRAM | `pack_*_to_z24s8`, `depth << 8 \| stencil` | **`0x00000024`** |

So nothing mis-clears anything. **A zeta image is downloaded over a colour
address.** That also accounts for the one fact the clear model could not, and
which the record notes and then argues past: the three colour populations are
partitioned *identically* in both arms (165,447 / 139,303 / 2,450) while only
the background's **value** moves. A clear lands on pixels and moves a boundary;
a download lands on a whole surface and moves a value.

### The route

`pgraph_vk_set_surface_dirty()` sets `pg->surface_zeta.draw_dirty` from `zeta`
**alone** -- the per-binding flag on the line below it is guarded by
`r->zeta_binding`, the Surface-level one is not. So the `Surface` can carry
`draw_dirty` with no binding behind it. `pgraph_vk_surface_update()`'s download
branch then re-enters `update_surface_part(d, false, false)` on the strength of
that flag, and the old gate was open **by definition** because the binding was
absent. The gate is not a cache-hit test: it unbinds, resolves the target
address, evicts or creates a surface there and **binds** it -- and then the
tail downloads what it just bound over guest VRAM. The address it resolves
comes from the **current registers**, not from wherever the draw went.
`TestSwap()` is the test that trades the two addresses.

### GL already has the fixed form, and #88's prediction saw the difference and read it as benign

The strongest independent evidence, found after the fix was written and not
used to derive it. `pgraph/gl/surface.c:2956`:

```c
if (upload && (surface->buffer_dirty || no_binding)) {
```

That is exactly the shape this change gives Vulkan. **GL has gated the
absent-binding term on `upload` all along**, so on GL a download has never
been able to resolve a binding.

And this was *noticed*. #88's own registered prediction says, in terms:

> Vulkan's gate is already `!current_binding || (upload && (pg_surface->buffer_dirty || mem_dirty))` [...] and it is **strictly MORE permissive** than GL's fixed form because it is not gated on `upload`. So ONLY THE POLICY IS PORTED.

The observation is exact and the inference from it is the defect: "strictly
more permissive" was read as harmless breadth, and the conclusion drawn was
that the gate needed no porting. The half of #66's chain that was skipped is
the half that mattered here. **A renderer difference that has been written
down and dismissed is worth re-reading before it is worth re-deriving.**

This citation is deliberately **not** added to the code comment in
`vk/surface.c`. It was found after `7980d1caa2` was written, and that commit is
the arm's `b_ref`; leaving the tree byte-identical to the binary the arm
measures is worth more than a comment, which is why it lives here and in #148
instead. It belongs in the code the next time that function is edited for a
reason.

One thing this comparison does *not* license, stated so it is not carried
further: GL's `unbind_surface()` does not clear `draw_dirty` either, so GL's
own tail (`gl/surface.c:3212`) can in principle reach `surface_download(d,
NULL, true)`. Whether that is reachable or guarded downstream was **not**
established here -- `gl/surface.c` is not this lane's file and was read only
for the gate. It is an observation for whoever owns that file, not a finding.

### This resolves blitsafe's impasse rather than picking a side of it

blitsafe established by reading that the decline **cannot fire inside `Swap`**
(`SET_CONTEXT_DMA_COLOR` sets `surface_color.buffer_dirty`, `pgraph.c:2387`, so
colour rebinds first and `surface == other` is false when zeta asks) and
refused to fit a patch to the half it could not establish. **That reading is
correct**, and it is not in tension with the measurement: this route does not
need the decline to fire in `Swap` at all. #88's policy does not create the
route, it **widens** it, by leaving zeta's binding absent far more often. The
"one of those two halves is wrong" framing had a third answer.

The withdrawn patch's known second defect -- the decline returning early with
`draw_dirty` left set, written into the file by `f147a588b1` -- is the same
mechanism reached by a shorter path. This fixes both, at the consumer.

## The arm, and the branch shape it forced

**The regression is unreachable on master.** Master's overlap policy has
whichever unit asks last evict the other, so zeta rebinds immediately and the
binding-less download essentially never happens. An arm of `master ->
master+fix` would score `Swap` at 165,447 in **both** arms and return a clean
PASS having tested nothing. That is an inert control and it discharges no
blocker: no change in the patch could move the leg.

So the branch is four commits and the middle two are a matched pair:

| commit | what |
|---|---|
| `aec524681e` | **arm scaffolding** -- restores `67dc7724ee`'s decline verbatim. **a_ref.** |
| `7980d1caa2` | the fix, on top of the policy. **b_ref.** |
| `b86517efe7` | **arm scaffolding** -- withdraws the decline again. |
| (tip) | prediction, index, these notes |

The policy is therefore **constant in both arms** and the fix is the single
variable, while the branch's net diff against master is the fix alone. Verified
rather than asserted: `git diff clrsurf91-fix HEAD` is empty, i.e. the tip tree
is byte-identical to master-plus-fix.

**The tension this has with M3, stated rather than glossed:** M3 wants a fix
arm's `b_ref` to be the code that ships, and `7980d1caa2` is not -- it carries
#88's policy. The alternative was an arm that measures nothing. I took the
measurement and made the scaffolding visible and self-cancelling; an auditor
who disagrees should say so on #148 rather than silently re-running it.

`67dc7724ee` is itself a live ancestor and the dispatcher would accept it as a
ref, but it sits **195 commits** behind master, so an arm across it would
differ by those 195 commits too and could attribute nothing.

**Registered:** `docs/testing/predictions/issue91-download-may-not-resolve-a-binding.json`,
sha256 `dfcf84103eb3`, three-suite disc. Not queued by this lane.

## What is NOT established, so the next actor does not inherit it as fact

- **Nothing here was measured on a device.** Every claim above is reading plus
  arithmetic. The arithmetic closes exactly, which is why it is worth an arm;
  it is not why it is true.
- **The fix's effect under master's policy is untested by construction** --
  neither arm is master. It is *expected* to be inert on master's scores. If
  that matters to someone, it is a different arm.
- **`n>0` on `dl91_probe` is a precondition, not the pixel claim.** The old
  code would have downloaded whatever sat at the current target address, which
  is only wrong when that address is not where the draw went. The pixel claim
  belongs to the A/B.
- **No Khronos validation-layer run.** This changes when a binding exists,
  which is exactly the class the layer found eight defects in (#34), and the
  desktop build is a known gap on this host. Reading was substituted. Reading
  is an argument, not a run.
- **Neither 165,447 nor 304,750 is correct**, and this lane does not fix that.
  At 165,447 the quad is still `#E91A24` against the golden's `#E91624`, off by
  4 in green. This arm claims the **background**, not the quad. A PASS means
  the stray download is gone, not that `Swap` is right. That residual is a
  separate defect and belongs to #92's neighbourhood, not here.

## Two corrections to the record the next actor should not re-derive

1. **The tracker's #91 `status_note` still ends on a conclusion its own issue
   comments refuted.** It says the solo disc read 304,750 in **both** arms, so
   "304,750 is simply `Swap`'s value when nothing precedes it" and "the policy
   is exonerated on `Swap`". The 2026-09-19 08:06Z and 09:30Z comments on #91
   record that `jobs/arms.sh` never passes `--only-tests` -- it builds its
   request from `disc.suites` alone -- so that arm ran the **full nine-capture
   suite**, was never solo, and read 165,447 -> 304,750 like the other disc.
   The exoneration does not stand, and the `status_note` has not been updated.
   A board request should correct it; this lane may not edit the tracker.
   **Filed in attempt 2 to `$DISPATCH_DIR/board-requests/clrsurf91.md`.**
   Attempt 1 wrote both corrections into the PR body and this file and filed
   nothing -- the record is not the delivery, and a correction that exists only
   in a PR body reaches no one who edits the tracker. Re-verified before
   filing rather than carried forward: `grep -n "only.tests"
   docs/testing/jobs/arms.sh` has no match on master at `415dcc6997`, and
   `arms.sh:519,522` pass `--suites` alone. Note `board-requests/blitsafe.md`
   carries the same exoneration claim in its own #91 section.
2. **The brief says the two diagnosis arms "found the regression intrinsic, not
   contamination from ColorIntoZeta".** Cross-suite composition is excluded;
   *within*-suite contamination is exactly what those comments say **remains**
   open. It does not change this fix -- the route is a download, not a
   predecessor -- but do not carry "contamination is excluded" forward as
   settled.

## What the next lane should not repeat

- Do not re-read the clear paths. Both are correctly guarded, three lanes have
  now confirmed it, and the signature is not a clear.
- Do not re-run the solo/contamination classification arm. It cannot be
  narrowed until `arms.sh` passes `--only-tests`, which is a filed harness
  defect, and the two runs that were spent on it are already read.
- Do not register an absolute for `Swap` on a **narrowed** disc. #89 measured a
  capture in this very suite moving 141,125 px on composition alone, so
  composition can violate the leg and read as a refutation of the mechanism.
  This prediction uses #88's three-suite disc for that reason.

---

# Attempt 3 (2026-09-19, job.cloud): audit pass 1 remediated -- and the arm came back FAIL

Two separate things happened between attempt 2 and this one, and they must not
be read as one. Audit pass 1 landed (0 HIGH, 3 MEDIUM, 1 LOW) and is
remediated below. **Independently, `[job.arms]` returned a FAIL at 16:18Z that
the audit never saw** -- it was written from the diff at 16:08Z, ten minutes
earlier. The audit's MEDIUMs are fixed. The FAIL is not something remediation
can fix, and this section exists so nobody folds this branch believing the
measurement went the other way.

## The arm FAILED, and the interesting part is not the failed leg

```
predicted Color_zeta_overlap/Swap = 165447, measured 304750
predicted better = 1, measured 0
```

Read past those two lines to the body of the comparison, because that is where
the information is:

| | |
|---|---|
| movers | **none** -- no capture moved outside its band |
| counts | better 0, worse 0, **same 11** of 11 |
| byte check | hashed 11 of 11 shared captures; **every one byte-identical between the arms** |

**Arm A reproduced 304,750.** The prediction registered "ARM A IS THE CHECK"
as a real condition -- if A does not reproduce, the base or disc does not carry
the regression and the absolute is unearned. It *did* reproduce. So the base
and the three-suite disc are sound, and the arm is not void. That check
passing is what makes the rest of the result mean something.

**Arm B is bit-identical to arm A on all eleven captures.** The fix is not
"less effective than predicted" and did not land "a third value between the
two", which is the shape of failure the prediction said to expect if the stray
download were only part of the 139,303 px. It moved **nothing at all**.

### What that does and does not refute

It refutes, cleanly: **`update_surface_part()`'s gate is not the route by
which anything reaches `Color_zeta_overlap/Swap`'s background.** Restricting
the gate to `upload` changes no pixel in that suite, on the very policy that
was supposed to widen the route.

It does **not** refute the byte arithmetic. `0xFE242424 -> 0x00000024` is still
`depth << 8 | stencil` with stencil preserved, both clear paths are still
correctly guarded, and "a zeta image is downloaded over a colour address" is
still the only reading of that word anyone has produced. What has been
falsified is the **route**: some other path performs that download, and this
gate is not it. Do not let the next lane throw away the arithmetic along with
the route -- that was the part with no free parameter, and it is untouched.

Stated as a limit rather than talked past: this says nothing about the fix
under master's policy, because neither arm is master. Both arms carry the
decline, exactly as registered.

### Falsifier (5) is unreadable as registered -- the instrument is not in the arm it names

The prediction's leg (5) says: *"n>0 in arm A over a run containing TestSwap()
proves the download branch reached a Surface carrying draw_dirty with no
binding behind it"*, and *"n==0 REFUTES THIS FIX'S MECHANISM OUTRIGHT"*.

**Arm A's binary contains no `dl91_probe`.** Verified, not assumed:

```
git show aec524681e:hw/xbox/nv2a/pgraph/vk/surface.c | grep -c 'static void dl91_probe'   -> 0
git show 7980d1caa2:hw/xbox/nv2a/pgraph/vk/surface.c | grep -c 'static void dl91_probe'   -> 1
```

The probe was added *with the fix*, so it exists only in arm B. Leg (5) names
a counter in an arm whose binary cannot emit it: it could never have returned
either n>0 or n==0, and it discharged nothing. A leg that names no capture and
no reachable instrument is bound, not measured -- it was stamped
`PRE-REGISTERED` along with the ten real ones and reads in the verdict like a
leg that held.

**The readable version, and it is one grep for whoever has `$WORK`.** This
session is sandboxed to its worktree and cannot read the run directories, so
this is left as a stated open read rather than a guess:

```
grep -h '\[dl91\]' <arm-B run dir>/**/logcat*        # 1789825274-arms-clrsurf91-fix-1110297
```

- **`n == 0`** -- the declined branch never fired. The precondition of the
  whole model never occurred in this suite, the mechanism is refuted outright
  on its own registered terms, and the byte-identical arms are explained
  entirely: the fix could not act because there was nothing to decline.
- **`n > 0` with arms still byte-identical** -- the branch fired and every
  declined download would have written bytes already at the address. The
  precondition occurs and is harmless here, which is a different and more
  interesting finding, and it is where `addr=` (added in this attempt, M2)
  earns its place: it says which address those declines were for.

**These two are not the same result and the next actor should not proceed
without separating them.** One grep decides it and needs no device.

## Audit pass 1 remediation (commit `5953a80814`)

| | what changed |
|---|---|
| **M3** | merged `origin/master`; regenerated `nv2a_index.json` on the merged tree |
| **M1** | the `DIRTY_MEMORY_NV2A` test-and-clear is now upload-only |
| **M2** | `dl91_probe` takes and prints `addr=` |
| **L1** | "REMOVE ALL FOUR" over five names -> "REMOVE ALL FIVE" |

**M3.** The conflict was the shared generated index, and taking either side
whole was wrong: the branch's copy predated master's `renderer.c` growth, so
its `renderer.c` locs ran *backwards* (1096->1071, 1297->1272, 1370->1345) and
it carried 2833 sites against master's 2839. Regenerated instead.
`--tests /home/justin/nxdk_pgraph_tests` was checked to be at `91a0de45ca`
first -- the same `tests_commit` master's copy names -- because an older tests
checkout silently deletes suites while fixing line numbers. **A bare
`nv2a_index.py build` with no `--tests` writes `0 suites` and says so only in
one line of output; it was run and discarded.** Result: 951 symbols / 2839
sites / 103 suites / 498 gaps, every count equal to master, and the whole
remaining diff against master is this branch's own `surface.c` locs. Both
prediction refs re-verified as ancestors after the merge (`aec524681e`,
`7980d1caa2`); nothing re-registered, and no rebase.

**M1** is the one with teeth. The dirty-bitmap loop is a *destructive* read --
`bitmap_test_and_clear_atomic` -- and `mem_dirty`'s only two consumers
(`upload_pending |= mem_dirty`, `upload_pending = shelf_stale || mem_dirty`)
both sit inside the gate block, which this branch made upload-only. So a
download consumed the guest's CPU writes and handed them to nobody, and the
next upload computed `mem_dirty == false` because this call had already eaten
the evidence, took the host image as-is, and lost the write. Checked rather
than inherited from the audit: `grep -n mem_dirty` gives exactly those uses
and the gate. The scan is now `if (upload && !tcg_enabled())`.

Two scope facts recorded so pass 2 need not infer them. This **also** repairs
the pre-existing loss on a binding-*present* download, which this branch did
not introduce -- same line, and it is flagged here rather than smuggled. And
it can only turn `upload_pending` from false to true, i.e. cause a redundant
upload of memory the deferred download has already made current, never a wrong
one. It additionally stops the bit being eaten out from under the vertex-RAM
sync, the only other consumer of this bitmap.

**M2.** The probe's own comment called `addr=` "the number worth having" and
the probe did not emit it -- the one field that separates "declined a download
that would have landed wrong" from "declined a harmless one". As the section
above shows, that distinction is now exactly the open question, so this was
not cosmetic.

## What the next actor should do, in order

1. **Grep arm B's log for `[dl91]`.** One command, no device, and it decides
   between "mechanism refuted outright" and "precondition fires but is
   harmless here". Everything else waits on it.
2. Do not re-register this prediction as-is. Leg (5) must name an instrument
   present in **both** arms, or be dropped; a probe added with the fix cannot
   measure the baseline.
3. Do not re-read the clear paths, and do not discard the byte arithmetic.
   The route is refuted; the signature is not.

## Audit pass 2 remediation (this commit)

Pass 2 (`docs/audits/2026-09-19-clrsurf91-pass2.md`) closed M1, M2 and L1
against the live file and re-opened **M3's mergeability half only**: the
content half is closed for good and is not re-derived here. Three new LOWs.

**M3 (the only open MEDIUM) -- closed the way pass 2 asked.** Merged
`origin/master` (130/16 at the time; **merge, not rebase** -- both prediction
refs `aec524681e` and `7980d1caa2` re-verified as ancestors *after* the merge),
resolved the single conflict in `docs/testing/nv2a_index.json` by
**regenerating** rather than hand-merging either side, and confirmed
`nv2a_index.py check --tests /home/justin/nxdk_pgraph_tests --support
/home/justin/pbkitplusplus` prints "index matches the tree (951 symbols, 2839
sites, 103 suites)". The `--support` argument is not optional: without it the
same command reports five suites changed, which reads exactly like a stale
index. `git merge-tree` now reports no conflict.

**One thing about that file the next regeneration should expect, because it
guarantees this conflict recurs.** `provenance.tests_root` and
`support_dirs` are absolute paths of whichever host generated the index.
Master's copy says `/home/user/...`; every regeneration on this host writes
`/home/justin/...`. Those two lines differ from master permanently and will
conflict again on any master touch of the file. They are not wrong -- they
record where this index actually came from, and CI clones the test sources to
a third path (`$RUNNER_TEMP`) and passes, so `check` is path-agnostic. Do not
"fix" them by hand-editing master's paths in: that fabricates provenance.
Regenerate, as this commit did.

**N1 (LOW, fixed).** The M1 comment block described the lost write in the
present tense with no mention that the scan is behind `!tcg_enabled()` and so
has never executed on a device arm. Added a paragraph saying where the failure
is reachable (a non-TCG host) and that the gate is a two-term condition on
every arm, citing `vk/draw.c:115-121` rather than re-deriving it. The fix
itself is unchanged and correct.

**N2 (LOW, NOT fixed -- out of this lane's territory, and it needs a grant).**
`vk/blit.c:778-786` justifies `pgraph_vk_solid_line()`'s direct
`upload_pending` write with "their scans test-and-clear it *before* the guard
that consumes it, and with `upload == false` on a live binding the bit is
cleared and discarded". **This PR makes that false for the Vulkan renderer**
(with the scan upload-only, `upload == false` clears nothing), and it was
already false for GL (`gl/surface.c`, #85). The conclusion -- keep the direct
write -- is still right and the reason is now *stronger*, so the fix is a
two-sentence rewrite, not a decision change. It is not made here because
`vk/blit.c` sits in `[free]` (released at wave 110 when `lane.blitsafe`
retired) and this lane holds only `vk/draw.c` and `vk/surface.c`; a released
file is not an assignment. **Asked for on the PR.** If it is not granted
before fold, the next actor in that file must not read the stale comment as
licence to replace the direct write with a `DIRTY_MEMORY_NV2A` mark: on the
device that route is dead (N1), and the symptom is a stale `VkImage` with
nothing in the log.

**N3 (LOW, fixed).** The PR body asserted 2833 sites and a clean base; both
were stale. Patched via the REST API (`gh pr edit` applies nothing on this
host) with the post-merge counts, and `Files:` re-derived from
`git diff --stat origin/master...HEAD`.

**Unchanged by this pass, and it is the thing that decides the PR.** The
`regressed` label stands: `[job.arms]` judged the prediction FAIL with arm B
byte-identical to arm A on all 11 captures. `jobs/fold.sh` refuses to fold a
`regressed` PR without `regression-accepted:<issue>`, so clearing the conflict
did **not** make this PR foldable. That is an owner decision about taking a
correctness-only change that moves no pixels -- not a remediation, and not
mine to make.
