# Audit pass 2d — PR #141, `lane/linecap13`: the wide-line cap rule, derived from the goldens and drawn

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #141, branch `lane/linecap13`, tip **`ce96ac11aa`**, four commits
over pass 2c's tip `68b5ac7dcb` plus the merge of `origin/master`. Mergeable;
CI green on this head (`check` SUCCESS, both `build` jobs SUCCESS). Labelled
`regressed`.
**Date** 2026-09-19 local (2026-09-20 UTC), filed beside the earlier passes.
**Records** `2026-09-19-linecap13-pass2d.{md,json}`.

**Pass 2c's N4, N5 and N6 are all CLOSED. Pass 2b's A1, pass 2's three and
pass 1's eight stay closed. 2 new LOW, no HIGH, no MEDIUM. `fold-ready`.**

N4 is the interesting one, and I did not take any step of it on trust. The
lane's claim is that `Line_width/Fill_*` was never a fill-only capture: the
suite's first block is a `LINE_LOOP`, a polygon mode decides nothing for a line
primitive, so the cap clip reaches it and the four pixels it moved are the fix
working. I verified that **three independent ways** — at the source, at the
goldens, and on silicon — and then verified the thing the re-scope actually
rests on, which nobody had checked: that the absolute now registered in
`expect` is not a fact about one of the two handhelds.

---

## N4 — `Fill_*` is a wide-line capture, and the leg is re-scoped by the mechanism — **CLOSED**

### The mechanism, read at the source rather than quoted

`hw/xbox/nv2a/pgraph/prim_rewrite.c:52-72` — `pgraph_prim_rewrite_get_output_mode()`
returns `PRIM_TYPE_LINES` for `PRIM_TYPE_LINES`, `LINE_STRIP` **and**
`LINE_LOOP` with no reference to `polygon_mode`; only the
`QUADS`/`QUAD_STRIP`/`POLYGON` arm consults it, at `:66-67`. And
`glsl/geom.c:36-38` is the link the claim needs:
`state->primitive_mode = pgraph_prim_rewrite_get_output_mode(pg->primitive_mode,
state->polygon_front_mode)`, so the field `widen_lines` tests at `:138-141`
**is** the output mode. `vk/shaders.c:1406-1409` refreshes it the same way on
the cached-state path. A `LINE_LOOP` draw is widened whatever `SetFill()` did.

So the sentence the old prediction rested on — *"with `widen_lines` false the
generator emits the byte-identical fill shader"* — is false for these captures,
and the new comment at `geom.c:124-135` says so at the place the reader would
otherwise make the same mistake.

### The goldens say it too, and much more sharply than `--fills` claims

`line_cap_phase.py --fills` reproduces here exactly, four legs PASS, every
figure matching the PR body and `NOTES.md`:

| golden pair | differ | in label | outside loop | outside MUTANT |
|---|---:|---:|---:|---:|
| `Fill_0000.0` vs `Fill_0032.0` | 12021 | 59 | **0** | 11801 |
| `Fill_0001.0` vs `Fill_0032.0` | 11730 | 59 | **0** | 11510 |

| test | w | bites | bites db=0 | quant px | quant db=0 |
|---|---:|---:|---:|---:|---:|
| `Fill_0000.0` | 0.000 | 0 | 0 | 0 | 0 |
| `Fill_0001.0` | 1.000 | 0 | 0 | 0 | 0 |
| `Fill_0032.0` | 32.000 | **6** | **8** | 1 | 1 |

I did not stop at the lane's own mutant. Leg 1 is a containment test, and a
containment test passes for free if its mask is large, so I measured the mask
and moved it:

```
frame px                 307200
label mask px              6182 (2.01% of frame)
loop w=32 footprint px    12559 (4.09% of frame)
leg-1 'inside' mask px    18726 (6.10% of frame)
other-5-blocks foot px    52858        loop & other overlap    199 px
```

The mask is 6.1% of the frame, and the five filled blocks' own footprint is
**four times larger** than the loop's — so the lane's mutant is the harder
direction, not the easier one. Two mutants of my own, neither the lane's:

```
translate the loop footprint in x, keep the label
   +2 px    100 px outside -> leg 1 FAILS
   +4 px    368 px           FAILS
   +8 px    890 px           FAILS
  +64 px   7335 px           FAILS

build the loop footprint at the WRONG width
  w = 0    11962 px outside -> FAILS        w = 24    952 px -> FAILS
  w = 1     8551 px           FAILS         w = 32      0 px -> PASSES
  w = 8     4445 px           FAILS         w = 48      0 px -> PASSES
  w = 16    2386 px           FAILS
```

A two-pixel shift already breaks it, and **`w = 32` is the smallest width at
which it passes at all**. That is a stronger statement than the one `--fills`
prints: the goldens do not merely put the width dependence somewhere inside the
loop's region, they put it at the loop's position *and at the suite's own
width*. Hardware drew a 32-pixel-wide line loop in a capture named `Fill`.

### And the device, on the capture itself

From the arm result directories rather than from the score column
(`dispatch/results/1789866964-...-base-2557022` arm A, `...-fix-2557051` arm B,
both 2 runs, both sides byte-identical with themselves):

```
Line_width/Fill_0032.0, master vs deadbanded:      4 px differ
  of those, the deadbanded value == the golden:    4
  of those, master's value       == the golden:    0
```

Every pixel the change moves on that capture it moves **to** the golden, and
master was wrong at all four. `26,721 -> 26,717` in both runs of each side.

### The re-scoped leg, checked as a registration and not as prose

`Fill_0000.*`/`Fill_0001.*` stay under `must_not_move`; `Fill_0032.0` moves to
`expect` at `26717` and is labelled a reproduction leg in the file. Everything
a registration has to satisfy, run here:

* **Every key binds.** Running `request.sh`'s own gate logic against
  `~/goldens/results`: 9 `must_not_move` globs bind 1,714 captures, the one
  `expect` key binds 1. Nothing matches nothing.
* **Both refs are live ancestors of the tip**, checked after the last merge:
  `a_ref 613802831a` and `b_ref a170ba01e7` are both ancestors of `ce96ac11aa`.
* **The B-side binary is the binary that produced 26,717.** `git diff
  --name-only 36e85c96c9 a170ba01e7` outside `docs/` is `glsl/geom.c` alone,
  and that file is code-identical: stripping C comments and normalising
  whitespace gives **12,973 bytes on both sides, byte for byte**, against
  45,071 -> 51,586 bytes of raw growth. `HEAD` adds only the prediction file
  itself (`git diff --stat a170ba01e7..HEAD` is 1 file, 3 lines).
* **The A-side binary is unchanged too**, which the prose does not claim and
  which matters for the nine `must_not_move` globs: `git diff --name-only
  28a3805b93 613802831a` outside `docs/` is **empty**. The in-flight base arm
  confirms it — same `apk_sha 215d41ca8268` as the last one, and its
  `Fill_0032.0` already reads **26,721** again.
* **The composition is unchanged**, which an `expect` leg needs and the old
  registration did not: `ab_compare.composition_notes()` `die()`s on an
  absolute whose disc differs, and the `disc` block (`Blend_tests`,
  `Line_width`, no skips, no `only_tests`) is identical to the superseded
  file's.
* `preflight.sh --allow-tracker` passes on this head; the PR body's `Files:`
  line matches `git diff --name-only origin/master...HEAD` exactly, 19 for 19;
  the prediction's sha256 `94b0428a0277…` is the one the body and the PR
  comment quote.

### The one thing that could still have broken it, which nobody had checked

An `expect` leg is an **absolute**, and `26,717` was measured on a particular
handheld. Every request in this lane's chain carries `"device": ""` — no pin —
and the fleet has two:

```
arm 1  base 2e1c5790aa / fix 9fdc6b5d70    device_label  nova
arm 2  base 28a3805b93 / fix 36e85c96c9    device_label  thor   <- 26,717 measured here
arm 3  base 613802831a (running)           owner file    nova   <- will judge the leg
```

The pair that produced the registered value ran on the **thor**; the pair that
will be judged against it is running on the **nova**. AGENTS.md records that
the two handhelds' byte-equivalence "has never been run on the interactive
disc, nor on 1,673 captures", and that a device split silently redefined a
registered comparison once already. So I measured it, on the one binary both
devices have now run (`apk_sha 215d41ca8268`):

```
166 captures compared, nova vs thor, same APK, same disc
  differing: 0        (Line_width 61 of 61 byte-identical, Blend_tests 105 of 105)
```

**Zero.** The two devices are byte-identical on every capture this prediction
touches, so the absolute is a fact about the binary and not about the thor, and
the `must_not_move` globs cannot fire on a device difference either. That also
retro-validates pass 2c's N5 measurement, which compared a nova capture
(pre-deadband) against a thor capture (deadbanded) — a comparison that was
device-confounded on its face and is not, now that the control exists.

**Pass 2c's scenario can no longer occur.** The leg that fired is gone, the
half of the glob the mechanism supports is kept and is the discriminating half
(anything moving `Fill_*` for a non-loop reason — a push-constant range, a
pipeline layout, a cache key — moves all three), the replacement absolute binds
to a real golden, and the binary, the disc and the device axis are all pinned
by measurement rather than by argument. And the record no longer tells the next
reader that a capture nothing can reach moved anyway.

---

## N5 — the half-pixel proof bounds coverage, and scale 1 is not free — **CLOSED**

Corrected **in place** in all three places the claim is made, not appended:

* `geom.c:611-629`, inside the derivation paragraph itself, directly under the
  sentence calling scale 1 "the control row that must read zero on every
  column". It names what the proof bounds (samples inside the footprint), what
  it does not (the value at a sample that stays covered), why (a cut
  synthesises a vertex and re-triangulates the strip), the two pixels, and
  ends *"It is a known limit, not a measured zero"* — with the list of which
  modes are blind to the class.
* `NOTES.md:301-310` and `:432-448`, each immediately below the paragraph it
  corrects. The unqualified sentence pass 2c quoted is **gone from the
  assertion**; it survives only inside the correction block quoting itself.
* `line_cap_phase.py:44-49`, in the module docstring, so the next person
  reading a zero out of `--controls` or `--scale-cost` is told in the tool that
  it does not cover `Fill_*` or interpolated values.

Every number the comment now commits to permanent source, re-measured from the
captures:

| `Fill_0032.0` px | master | pre-deadband | deadbanded | golden |
|---|---|---|---|---|
| (271, 93) | `51 155 151` | `51 154 152` | `51 155 151` | `51 154 152` |
| (264, 123) | `51 228 78` | `51 227 79` | `51 228 78` | `51 227 79` |

Exact, and **exactly two** — the pre-deadband and deadbanded builds differ on
this capture in those two pixels and no others. The one-directional claim holds
at both: `deadbanded == master` is True at each, so the deadband gives up a
win, it does not introduce a loss. Both runs of the deadbanded arm are
byte-identical, and the cross-device control above removes the confound in the
comparison itself.

Pass 2c's scenario — the next lane on #13's colour phase sizing the deadband's
scale-1 cost at zero — can no longer occur from any of the three documents that
asserted it, and the figure it would find instead is the right one.

---

## N6 — the `scale^2` conversion — **CLOSED**

The PR body's pass-2b section now reads *"a twelfth of the clip's own work
above 1x — **after the `scale^2` conversion**, which `geom.c` and `NOTES.md`
carry and this paragraph dropped (audit N6). 112 device samples at scale 2 and
393 guest px at scale 1 are not in one unit; read as though they were, they
give 28%, four times the figure."* It states the trap as well as the fix.
`geom.c` and `NOTES.md` were already right and are unchanged.

---

## Everything earlier stays closed, re-run rather than assumed

Nothing in the remediation touches compiled code: `geom.c` is comment-only
(proved above), `line_cap_phase.py` gains `fills()`/`fill_golden()`/
`FILL_WIDTHS` and a dispatch line and modifies no shared helper, and the rest
is the prediction, the nv2a index and notes. The instruments the earlier passes
rest on, all re-run on this tip:

```
--depth       shipped worst |error| 1.11e-16, mutant worst 0.583       PASS / PASS   (pass-1 H1)
--quantise    0 quantised px after, 4 on 4 captures before             3 legs PASS   (pass-2 N1)
--controls    393 removed / 393 golden-dark / 0 golden-lit
              1104 = 617 low + 487 high, 1038 centre                                 (pass-1 M3, pass-2 N2)
--scale-cost  1: 0/0/0   2: 191/278/112   3: 295/860/298   4: 337/1666/568
              scale-1 control zero on every column                     3 legs PASS   (pass-2b A1)
--fills       4 legs PASS, plus my two mutants above                                 (pass-2c N4)
```

The device half agrees with the offline half where both can see: the second arm
came back **20 better, 0 worse, 146 same**, the eight captures at `w = 4` to
`14` that the pre-deadband build made worse did not move, the VOID captures
held, and `Line_0063.0`/`Line_0063.1` — the wide-end pair the lane declined to
defend — came back better.

---

## LOW

### N7 — the PR body's pass-2 section still asserts the premise N4 falsified, uncorrected in place

`NOTES.md:355-361` carries the original sentence and `NOTES.md:363-375` marks
it `> **WRONG, and corrected in place by audit finding N4 (pass 2c)**` directly
underneath. The PR body carries the same paragraph, in its "Pass-2 audit
remediated" section, and it was **not** given the same marker:

> **One thing this lane cannot settle.** `Line_width/Fill_0032.0` moved
> 26,721 -> 26,715 on the failing arm under a `must_not_move` glob, and nothing
> in this branch's diff can reach it: with `widen_lines` false the generator
> emits the byte-identical fill shader it emitted before […] The glob stays.

The body does correct it, 1,400 words later, in the pass-2c section. So this is
a currency defect and not a contradiction left standing unremarked — but it is
the one place the lane applied its own standard unevenly, and the PR body is
what the board and the next lane read first.

**Failure scenario.** A reader scanning the body for "Fill" — which is what
anyone re-opening this question does — hits the pass-2 section first, reads
that the diff cannot reach `Fill_*`, and re-derives the error that cost this
lane an arm. The campaign's own lesson is the exact shape: a withdrawal
appended at the end leaves the earlier assertion still asserting itself.

**Decision: reviewed, not blocking the fold.** Two sentences in the PR body,
mirroring the `NOTES.md` block. `gh pr edit --body-file` is broken on this host
(Projects-classic GraphQL error); the REST `PATCH` works and the value should
be read back. Worth doing before the fold, and not worth holding it.

### N8 — the prediction enumerates what C4 can catch, and the device axis is not on the list

`line-cap-clip.json`'s C4 says the leg catches "a capture that is not
deterministic after all, a pair that is not the pair this file names, or a
change that reaches this shader without anyone noticing", and justifies `26717`
as "the value the device measured twice with band 0 on this same binary". True,
and it omits that "the device" was the **thor** while the arm now judging it is
on the **nova**, with `"device": ""` in every request and nothing pinning the
pair-to-pair choice. The same omission sits under N5's two-pixel measurement,
which compares a nova capture with a thor one.

**Failure scenario.** As written the reasoning is an absolute transferred
across an axis it does not name — the shape AGENTS.md records as an
availability change silently redefining a registered comparison. Had the two
devices disagreed on this suite, the leg would have failed on the next arm and
`regressed` would have stayed for a reason having nothing to do with the cap
rule, with the prediction's own text offering no way to see it.

**Decision: reviewed; record the control, do not change the leg.** I measured
the axis instead of flagging it: 166 of 166 captures byte-identical between the
nova and the thor at `apk 215d41ca8268`, so the absolute is safe and the leg is
right as registered. What is missing is the sentence saying so. This is also
worth more than this lane — it is the first cross-device byte control on a
multi-suite disc in this campaign, and AGENTS.md's "Do not reach for the
equivalence check to rescue it" paragraph is the place it belongs.

---

## What I ran

* `line_cap_phase.py --fills`, `--quantise`, `--controls`, `--depth`,
  `--scale-cost` against `~/goldens/results` — every table above, every leg
  PASS.
* Two mutants of `--fills` leg 1 that are not the lane's, from a scratch
  directory (`scratch-audit2d/`, deleted; nothing outside `docs/audits/` is
  touched by this pass): the loop footprint translated in x by 2 to 64 px, and
  rebuilt at w = 0, 1, 8, 16, 24, 32, 48. Leg 1 fails on every one but the two
  widths at or above the suite's own.
* `hw/xbox/nv2a/pgraph/prim_rewrite.c:49-72`, `glsl/geom.c:27-45, 120-141`,
  `vk/shaders.c:1400-1412` — the output-mode chain, read rather than taken.
* A C-comment strip of `glsl/geom.c` at `36e85c96c9` and at `a170ba01e7`
  (12,973 code bytes both sides), and `git diff --name-only` outside `docs/`
  across both ref pairs.
* `request.sh`'s key-binding gate logic against the goldens: 1,715 captures
  bound across 10 keys, none matching nothing.
* `git merge-base --is-ancestor` on both refs, after the last merge.
* `ab_compare.py` `expect` evaluation (`:938-948`) and `composition_notes()`
  (`:1153-1210`) — what an absolute does on a composition mismatch.
* The arm result directories for all three arms, including the one in flight:
  `result.json` `device_label`, `dispatch/running/*.owner`,
  `dispatch/queue/*.req`, and a pixel-for-pixel RGBA comparison of all 166
  captures between the nova and the thor at one APK, plus `Fill_0032.0` across
  master / pre-deadband / deadbanded / golden.
* `preflight.sh --allow-tracker`; `gh pr view` for the check rollup and the
  `Files:` line.

## Disposition

Every scenario pass 2c named is closed, by a mechanism verified at the source,
at the goldens and on silicon rather than by a commit existing. The re-scope is
the legitimate kind — the device falsified the leg's premise, not its result —
and the lane said so in the file, in the commit message and in the body rather
than quietly widening a glob. The two LOWs are both about what the record says,
not about what the code or the prediction does; neither blocks a fold, and both
are logged here as decisions.

The `regressed` label is the arms job's. The third arm is running now (base on
the nova at `613802831a`, fix queued at `a170ba01e7`), and `arms.sh` recomputes
the label from its verdict — so the fold will wait for that regardless of this
audit's label.

**Clean. `needs-audit-2` off, `fold-ready` on.**
