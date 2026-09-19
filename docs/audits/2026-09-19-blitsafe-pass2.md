# Audit pass 2 — PR #102, `lane.blitsafe`: the pass-1 findings are closed, and the device found something pass 1 could not

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #102, branch `lane/blitsafe`, tip **`f0a344dadd`**, twenty-two
commits over `origin/master` (**`38385b79c1`**).
**Date** 2026-09-19. **Records** `2026-09-19-blitsafe-pass2.{md,json}`.
**Pass 1** `2026-09-19-blitsafe-pass1.md` (0 HIGH, 2 MEDIUM, 5 LOW) at tip
`aec3641413`.

**Pass 1: M1 CLOSED, M2 CLOSED. L1 CLOSED, L2 DECIDED, L3 CLOSED, L4 OPEN
(partly), L5 CLOSED-then-reopened at the tip. Carried N1 and N2 CLOSED, N5
OPEN, M3 closed with M1.**

**New: 1 HIGH, 2 LOW. PR #102 goes to `needs-remediation`.**

The remediation of pass 1 was good work and I could not break it. M2's exact
failure world no longer produces silence; M1's two dead predictions did not
merely get re-bound, they **ran** — which is the only proof that mattered, and
it is stronger than the one pass 1 asked for.

**What sends this back is not a pass-1 scenario.** Between pass 1 and now the
arms job returned two verdicts, both FAIL, and they agree: `#88`'s colour-wins
policy — the only code difference between the two arms — moves
`Color_zeta_overlap/Swap` from **165,447 to 304,750 differing pixels**, against
a `must_not_move` leg the lane itself registered. That is a scored capture
getting 139,303 px **further from its golden**, reproduced across two
independent A/B pairs on two different discs, and the branch tip still carries
it. A `fold-ready` label on this PR would put that on master.

The lane knows. Its `NOTES.md` says so plainly and attempt 3 registered a
diagnosis arm for it. This finding exists because the pipeline label, not the
prose, is what fold.sh reads.

---

## Pass-1 findings, verified at the tip

### M1 — CLOSED, and closed by demonstration rather than by inspection

Pass 1's scenario: both predictions named `a_ref f343580647` / `b_ref
4726557b0f`, reachable from no ref, and `arms.sh:213` records that as a
*structural* skip which "stands until the prediction itself changes" — so
neither arm could ever be queued, including by this pass.

All four predictions on the branch now name refs that are reachable:

| prediction | a_ref | b_ref | `git branch -r --contains b_ref` |
|---|---|---|---|
| `issue88-vk-same-offset-colour-wins.json` | `55bc6c6c2b` | `67dc7724ee` | `origin/lane/blitsafe` |
| `issue91-swap-solo-classification.json` | `55bc6c6c2b` | `67dc7724ee` | `origin/lane/blitsafe` |
| `issue89-clear-pad-alpha-shape.json` | `3f2563d6e9` | `77bd2977cc` | `origin/lane/blitsafe` |
| `issue91-decline-frame-attribution.json` (new) | `55bc6c6c2b` | `bb0ddde27d` | `origin/lane/blitsafe` |

`55bc6c6c2b` is contained by `origin/master` as well.

But reachability is what pass 1 already established was fragile — it was true
when the first re-bind was written, too. **The closing evidence is that the
arms ran.** Both previously-dead predictions were queued at 08:30:49Z, built
(`apk 1b691b048198` / `dea6d0d3ec27`), executed on the device and judged at
09:01Z, and both verdicts are on the PR. A prediction that produces a
`[job.arms]` verdict is, by construction, not being skipped. M1's scenario
cannot be occurring.

**And the fold will not re-create it.** Pass 1's worry was that a fold would
rewrite these shas the way the rebase did. `jobs/fold.sh:187` integrates with
`git merge --no-ff --no-edit`, never a rebase or a squash — so every sha named
by these four predictions becomes reachable from `master` at the fold rather
than orphaned by it. Checked in the script, not assumed. The residual risk is
the one the lane reported to the board (nothing re-checks a registration after
history moves under it), which lives in `arms.sh` and is outside this lane's
grant.

Pass 2 of 2026-09-18 recorded **M3** as the same defect one event earlier. It
is closed here with M1.

### M2 — CLOSED. The heartbeat is independent and the silent world is gone

`hw/xbox/nv2a/pgraph/vk/draw.c:861-863` at the tip:

```c
bool flood_capped_event = diverged && g_clr89.diverged <= 20;
if (!(flood_capped_event || g_clr89.clears % 512 == 0)) {
    return;
}
```

I walked pass 1's exact scenario against this code. Divergence becomes
persistent at clear *k*: lines print for divergences 1…20, then
`flood_capped_event` is false forever. `g_clr89.clears` is incremented at `:838`
**before** the gate and unconditionally on every call, so `clears % 512 == 0`
is still reached and still true every 512th clear whatever `diverged` does.
The probe prints `diverged=N` for the rest of the run. "Twenty divergences and
twenty thousand read identically" can no longer happen: the totals keep
arriving, and an absent tag still means a filtered tag.

The same correction was applied to the two probes added *after* pass 1 —
`surf91_decline_probe()` (`vk/surface.c:253`) and `clr91_probe()`
(`vk/draw.c:6851`) both OR their heartbeat. That is the finding being
generalised rather than patched, which is the better outcome.

### L1 — CLOSED

`draw.c:876` prints `nobind=%lu(structural-0)`, and `:867-875` records why it is
one. The constant no longer sits unlabelled beside three measurements.

### L2 — DECIDED, with a residual that is now a new LOW

`vk/surface.c:171-182` carries the lifetime decision pass 1 asked for: the
probes are unconditional on purpose, not by omission, and the removal condition
is written into the file. That discharges L2 as framed — a logged decision
existed nowhere before and exists now.

The residual is that the condition it names has since been met. See **N3**.

### L3 — CLOSED

`vk/surface.c:298` prints `shapedirty=%lu(per-surface_update)`, and `:289-297`
names the 2× hazard explicitly. The number no longer invites division by
`updates`.

### L4 — OPEN. Two of the four artifacts still carry the stale citation

The code comment was fixed the right way — `draw.c:767-771` now cites the call
**by callee** rather than by line, with the reason ("the number was :6751 when
this was written, was already wrong"). That is better than the correction pass 1
proposed, and it has already paid: the call is now at `draw.c:6894`, having
moved a third time under the new probes.

The remediation comment's table records L4 as "fixed". It is fixed in one
artifact of four. Still stale at the tip:

| artifact | cites | correct |
|---|---|---|
| `docs/investigations/surface-shape-has-no-address.md:136` | `vk/draw.c:6751` | `:6894` |
| `docs/investigations/color-zeta-same-surface.md:254` | `pgraph.c:2386` | `:2387` |

Verified, not assumed: `pgraph.c:2386` is `pg->dma_color = parameter;` and
`:2387` is `pg->surface_color.buffer_dirty = true;`.

`issue91-swap-solo-classification.json` **was** corrected. The fourth,
`issue89-clear-pad-alpha-shape.json`, still says `(draw.c:6751)` and there is a
good reason not to touch it — its sha256 is bound to a PASS verdict, and
editing a byte requeues a 42-leg arm that has already been paid for. **That
decline is correct and I accept it in advance**; what is not correct is the two
investigation records, which are bound to nothing and cost one line each.

LOW. It stays LOW. It is listed because the disposition said "fixed" and a
reader who trusts that table will not look.

### L5 — CLOSED for what pass 1 read, reopened by what landed after it

Pass 1's L5 was "the branch is uncompiled and I could not build it either".
Discharged for those commits by evidence rather than by argument: the arms job
built all four refs pass 1 could see and ran them on a device
(`3f2563d6e9`/`77bd2977cc` at 05:34Z, `55bc6c6c2b`/`67dc7724ee` at 09:01Z, four
distinct apk shas). Compilation is no longer a reading.

**`bb0ddde27d` is not covered by that.** It adds 177 lines across both files —
`surf91_decline_probe()`, `clr91_probe()`, four new struct members and two call
sites — and was pushed at 09:25Z, after every build this branch has had. I read
it for the same two failure modes pass 1 named and found neither: both new
loggers reuse `SURF92_LOG`/`CLR89_LOG`, which are already reached in both
files; `pg->frame_time` is `int` and is printed with `%d`; the two `hwaddr`
arguments use `HWADDR_PRIx`; `f_declines`/`zdrop`/`cdrop` are `unsigned long`
against `%lu`. Reading is still not a build — but `issue91-decline-frame-
attribution.json` names `bb0ddde27d` as its `b_ref`, so the arms job will
compile it on the next tick and a failure will be loud. Recorded as an open
item rather than a finding against the lane.

---

## Carried forward from `2026-09-18-blitsafe-pass2`

- **N1** (LOW) — **CLOSED**. `nv2a_index.json` was regenerated at `f0a344dadd`
  and `preflight.sh` passes on this tree with no `--allow-tracker` ("nv2a index
  ok"). The silent-deletion mode pass 1 warned about did not occur: provenance
  reads `tests_commit 91a0de45ca31…`, `suites 103`, `symbols 951`, `sites 2833`,
  `gaps 498`, `unread 145` — the suite count the index already named, against a
  tests tree that no longer predates the `Surface as vertex array` suite.
- **N2** (LOW) — **CLOSED**. The three-suite disc for #88 is no longer prose.
  `issue88-vk-same-offset-colour-wins.json` carries
  `disc.suites = ["Color Zeta Disable", "Color zeta overlap", "Null surface"]`,
  which `arms.sh`'s `suites_for()` reads, and the verdict confirms the job
  requested all three (11 captures, `Color_Zeta_Disable` 1 + `Color_zeta_overlap`
  9 + `Null_surface` 1).
- **N5** (LOW) — **OPEN**, unchanged. The Khronos validation layer is still
  owed. `bb0ddde27d` adds a fourth Vulkan-backend change on top of it.

---

## What pass 1 asked pass 2 to count, counted

Pass 1 could not reach `/home/justin/goldens/` and asked pass 2 to check the
lane's claim that only 32 of #89's 42 legs can fail. **The claim is exactly
right**, and so is the reasoning under it:

| suite | goldens on disk | lane's count |
|---|---|---|
| `Blend_surface` | 32 | 32 — the arm |
| `Color_mask_blend` | 1 | 1 — impossible row |
| `Color_zeta_overlap` | 9 | 9 — inert by construction |

42 legs from three globs. And the inertness claim is not an assertion: in
`/home/justin/nxdk_pgraph_tests` at `91a0de45` — byte-for-byte the
`tests_commit` the committed index names —
`src/tests/color_zeta_overlap_tests.cpp` sets `SCF_A8R8G8B8` at all six
`SetSurfaceFormat` sites, at `:53`, `:199`, `:212`, `:234`, `:267` and `:292`,
which are the exact lines the lane cited. `A8R8G8B8` is `PAD_ALPHA_NONE` and
takes neither branch of the switch under either source, so those nine legs and
the one `Color_mask_blend` leg discharge nothing. A PASS on that arm is 32
measurements and 10 restatements, as the lane said.

(The verdict header says "44 registered checks" against 42 legs; the two extra
are the structural checks, not legs. Noted so the numbers are not read as a
discrepancy.)

---

## N1 — HIGH. The branch carries a reproducible, registered regression, and the tip still has it

`hw/xbox/nv2a/pgraph/vk/surface.c` (#88's colour-wins policy, `67dc7724ee`).

### The measurement

Two `[job.arms]` verdicts, both FAIL, both on `a_ref 55bc6c6c2b` → `b_ref
67dc7724ee`:

| | disc | captures | `Color_zeta_overlap/Swap` |
|---|---|---|---|
| `issue88-vk-same-offset-colour-wins` | 3 suites | 11 | **165,447 → 304,750** (+139,303) |
| `issue91-swap-solo-classification` | `Color zeta overlap` | 9 | **165,447 → 304,750** (+139,303) |

`Swap` is on `must_not_move` in the first prediction. "Worse" here means the
capture's differing-pixel count against its golden went **up** by 139,303 on a
307,200-px frame — the frame goes from roughly half wrong to almost entirely
wrong.

### Why this is attributable, when `ab_compare` itself says it is not

Each verdict carries `NOT ATTRIBUTABLE: one run per arm cannot tell a change
from device nondeterminism`. That caveat is correct **within** one comparison
and it is defeated **across** the two, which is a fact only pass 2 is in a
position to state because it can read both:

- four distinct device runs, four distinct result directories
  (`…-base-2811175`, `…-fix-2811205`, `…-base-2811285`, `…-fix-2811314`);
- two independent A runs on different discs both scored `Swap` at **165,447**;
  two independent B runs both scored it at **304,750**;
- the whole suite agrees, not just that capture: `Color_zeta_overlap` totals
  399,197 → 387,179 in *both* comparisons, `better 2 / worse 1 / same 6` in
  both.

Nine captures reproducing to the pixel across independent runs is not a band.
The disc is not the variable either — three suites and one suite gave the same
numbers, which is the lane's own (unplanned, and correct) finding that
cross-suite composition is excluded.

The two arms differ in `vk/surface.c` alone, +61 −2, verified by patch-id at
pass 1. So the +139,303 belongs to this PR's code.

### The tip carries it

`bb0ddde27d` is probe-only — I diffed it ignoring comments: two new `static`
probe functions, four struct members, and two call sites that pass values and
return `void`. `1393571fe0` is a prediction file, `16074b8fb0` is `NOTES.md`,
`f0a344dadd` is the index. **Nothing between `67dc7724ee` and `f0a344dadd`
changes rendering behaviour**, so the measurement taken at `67dc7724ee` is a
measurement of the tip.

### And the new prediction registers the regression rather than fixing it

`issue91-decline-frame-attribution.json` sets
`expect["Color_zeta_overlap/Swap"] = 304750` and says so in its own first
sentence: *"DIAGNOSIS AND REPLICATION ARM, NOT A FIX ARM… Reading a PASS here
as '#91 is resolved' would be exactly backwards."* The lane is right to have
registered it that way, and it is the reason this PR cannot be folded on the
strength of a future PASS: that arm passing means the regression **replicated**.

### Remediation

Not a revert. #88's mechanism is confirmed to the pixel — both absolutes
derived from the goldens' own histograms before the run (`ColorIntoZeta_ZB`
10,766 and `ZetaIntoColor` 71,663) landed exactly, from pre-fix 131,495 and
102,255, and arm A reproduced both pre-fix values, so `ARM A IS THE CHECK` was
discharged as written. A failed leg on a confirmed mechanism is a diagnosis.

What has to happen before `fold-ready`, and one of these is enough:

1. **Fix `Swap`.** The diagnosis arm is registered on live refs
   (`55bc6c6c2b` → `bb0ddde27d`, `runs_per_arm 3`, no `only_tests` — so it will
   not be voided by the `arms.sh` defect the lane reported) and the arms job
   will run it. Its `[surf91] frame=` / `[clr91] frame=` join answers whether
   the decline fires inside `Swap`'s frame, which is the fork between a local
   fix and within-suite contamination from `ColorIntoZeta`/`ColorIntoZeta_ZB`.
2. **Or split the fold**, if the board wants #89's narrowing and #92's
   instrument on master without waiting: those are separate commits with their
   own PASSed arm and no regression against them.

What must not happen is a `fold-ready` label while `Color_zeta_overlap/Swap`
reads 304,750 on this branch's code.

---

## N2 — LOW. `clr91_probe()`'s "first drop of each kind" is one flag for both kinds

`hw/xbox/nv2a/pgraph/vk/draw.c:6847-6850`:

```c
bool first_event = (zdrop || cdrop) && !g_clr91.reported;
if (first_event) {
    g_clr91.reported = true;
}
```

The comment immediately above it (`:6840-6846`) says *"FIRST drop of each kind
in each frame"* and *"One line per frame per kind"*. There is one `reported` flag, not one per kind.

**The scenario.** In a frame where a `cdrop` occurs first and a `zdrop` occurs
later, the `zdrop`'s first occurrence prints nothing: `reported` is already
true. Its count reaches the log only at the next `clears % 512` heartbeat —
and `f_zdrop` is reset per frame, so a heartbeat landing in a later frame shows
that frame's zero. A reader joining `[surf91]` to `[clr91]` on `frame=` would
conclude "no zeta clear was dropped in this frame", which is the precise
inference #91's classification turns on.

**Why it is LOW and not MEDIUM.** The scenario needs `cdrop` — `write_color`
true with `r->color_binding` NULL — and the call path makes that all but
unreachable: `pgraph_vk_clear_surface()` calls
`pgraph_vk_surface_update(d, true, write_color, write_zeta)` at `draw.c:6894`
before the probe, which creates the colour binding when colour is being
written, and #88's policy is *colour always wins*. I could not construct a
live route to a `cdrop`. So this is a latent mis-report, not an active one —
but it is latent in the one instrument the fold decision above now depends on,
and the fix is a second bool.

## N3 — LOW. The probes' removal condition has already been met, and three probes remain

`vk/surface.c:178-182` states the L2 decision as: *"REMOVE IT when #88's and
#91's arms have returned a verdict — both are registered against a_ref
55bc6c6c2b / b_ref 67dc7724ee — and not before."*

Both arms returned verdicts at 09:01Z. By its own terms the condition is
satisfied, and the probes are still in — plus a third, added at `bb0ddde27d`
after the verdicts landed, whose own note says *"LIFETIME: same as
surf92_probe/clr89_probe — out when #91 has a verdict"* while #91 now has one.
The same paragraph also says `clr89_probe`'s question *"#89's arm has ALREADY
answered (diverged=0 over 33,280 clears)"* and keeps it anyway "so the two
probes leave together".

No failure scenario: three probes in the shipping Android build's hot path cost
a call and a few increments, and this project has precedent for permanent
`hakuX` instruments. Filed because L2 asked for a decision that a fold could
not lose, and the decision as written now reads as expired the moment anyone
checks it against the verdict dates. One sentence fixes it — re-anchor the
condition on the diagnosis arm (`issue91-decline-frame-attribution`) rather
than on arms that have already reported.

---

## What I checked and found clean

- `preflight.sh` passes on this tree with **no** `--allow-tracker`: psh_differ,
  aci_vmstate, nv2a index, territory, coverage and board files all ok.
- The four predictions' suites all resolve to golden directories on disk, so
  none will be refused at queue time for unmatched keys.
- `issue91-decline-frame-attribution.json` registers `only_tests: []` — it does
  not depend on the `arms.sh` narrowing defect the lane reported to the board,
  so it will measure the disc it registered.
- `bb0ddde27d` touches no rendering path; both new probes are `static`, take
  their state from one file-scope struct each, and return `void`.
- `#89`'s PASS is undisturbed by everything above: its arm pair
  (`3f2563d6e9` → `77bd2977cc`) is a different pair from the regressing one,
  and `Color_zeta_overlap` is inert under *that* change for the reason verified
  in the tests tree above. The two facts are consistent, not contradictory.

---

## Verdict

**Pass 1: M1 CLOSED, M2 CLOSED, L1 CLOSED, L2 DECIDED, L3 CLOSED, L4 OPEN,
L5 CLOSED (reopened for `bb0ddde27d` only). Carried N1, N2 CLOSED; N5 OPEN;
M3 closed with M1.**

**Pass 2 new: 1 HIGH (N1), 2 LOW (N2, N3).**

The remediation of pass 1 was thorough and it held under an adversarial read.
The PR is not foldable for an unrelated reason: it carries a measured,
reproduced, self-registered regression. **PR #102 goes to
`needs-remediation`.**
