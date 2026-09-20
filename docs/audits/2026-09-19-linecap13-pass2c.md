# Audit pass 2c — PR #141, `lane/linecap13`: the wide-line cap rule, derived from the goldens and drawn

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #141, branch `lane/linecap13`, tip **`68b5ac7dcb`**, one commit
over pass 2b's tip `3beca48079`: the A1 remediation, comment-and-instrument
only. Mergeable; `check` green, both `build` jobs in progress on this head at
the time of writing. Labelled `regressed`.
**Date** 2026-09-19. **Records** `2026-09-19-linecap13-pass2c.{md,json}`.

**Pass 2b's A1 is CLOSED. Pass 2's three and pass 1's eight stay closed. 2 new
MEDIUM, 1 new LOW — all three from the arm that landed while pass 2b was being
written.**

A1 is closed the way the audit offered: option 2, the precondition written
down at the point of derivation with the cost measured rather than described.
I reproduced every figure the new instrument prints, rebuilt the generator
against `4cc0d26dc0` to confirm the commit cannot move a pixel, and re-ran the
three instruments the PR says are unchanged. All of that holds.

What does not hold is a claim this pass is the first to be able to check,
because the verdict for it arrived at 01:48 UTC, an hour after pass 2b was
posted. **`[job.arms] VERDICT: FAIL — 1 of 147 checks violated`** on the very
pair pass 2b blessed (`a_ref 28a3805b93` / `b_ref 36e85c96c9`, 2 runs per arm):

```
must not move, but moved: Line_width/Fill_0032.0        26721 ->     26717
```

Everything else in that arm is the change working: **20 better, 0 worse, 146
same**, every `Line_*` capture below `w = 24` bit-identical, both wide
captures C3 said might worsen unmoved. C2's structural claim held on silicon.
The one violated leg is a leg the prediction, the PR body and `NOTES.md` all
justify with a sentence that is false — *"nothing in this branch's diff can
reach it"* — and the arm captures on disk show what actually happened: the
change reaches `Fill_0032.0`, and every pixel it moves there it moves **to the
golden**.

---

## A1 — the deadband is half a guest pixel where the sample grid is device pixels — **CLOSED**

### The precondition is stated where the proof is made

`geom.c:561-572` now carries the hypothesis in the paragraph that needs it,
not in an appendix: `THE HYPOTHESIS IN THAT PROOF IS surface_scale_factor == 1`,
with the two coordinate spaces named, `geom_line_params()` cited as the
authority for the geometry stage working in guest pixels, and the quarter-of-a-
guest-pixel figure at Rendering Scale 2 stated explicitly. `:573-598` states
the direction (`0.5 > 0.5/scale` for every `scale >= 1`, so it can only
suppress *more* cutting), the cost table, and why the behavioural fix was not
taken. `NOTES.md:292-300` marks the original derivation paragraph corrected
**in place**, above the paragraph it corrects, and points forward to Attempt 5.
The PR body carries the same. Pass 2b's scenario — a reader at Rendering
Scale 2 told by the comment that the deadband provably removes no sample —
can no longer occur, because the comment now says at which scale that is true
and what it costs where it is not.

### The rejected option's cost is real, and I checked it rather than the prose

The lane declined option 1 (`0.5 / surface_scale_factor` pushed in) on a
push-constant argument. Every step of it checks out:

* `glsl/geom.c:235-239` — `vec4 lineParams`, and all four components are live
  (`lineNdcScale` = `.xy`, `lineHalfExtentScale` = `.z`, `lineTieBias` = `.w`).
  A fifth value needs a fifth component.
* `vk/draw.c:1212` and `vk/shaders.c:55` — `GEOM_PUSH_CONSTANT_SIZE` is
  `4 * sizeof(float)` in both, KEEP-IN-SYNC.
* `glsl/vsh.c:994-999` — the vertex stage's block is declared
  `layout(offset = %d) vec4 inlineValue[%d]` at `vertex_push_offset`, which
  `vk/shaders.c:841` sets to `GEOM_PUSH_CONSTANT_SIZE`. A `vec4` array at
  offset 20 is not 16-byte aligned, so the growth really is 16 → 32.
* `vk/shaders.c:44-50, 317-327` — the geometry range is declared on every
  graphics pipeline layout and every push-descriptor template, guarded
  identically, because layouts whose push-constant ranges differ are not
  compatible for set 0 (issue #34 finding 3).

So the trade the lane describes is the trade that exists.

### The instrument reproduces, and its load-bearing leg is not a tautology

`line_cap_phase.py --scale-cost`, run here against `~/goldens/results`:

| scale | suppressed | over-reach | lost |
|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 |
| 2 | 191 | 278 | 112 |
| 3 | 295 | 860 | 298 |
| 4 | 337 | 1666 | 568 |

```
the scale-1 control reads zero on every column: PASS
the cost above 1x is visible at all: PASS
every over-reached sample is one the SHIPPED footprint lights: PASS
```

Identical to the table in `geom.c:585-590`, in the commit message and in
`NOTES.md`, and the `suppressed` column reproduces pass 2b's own independent
count (191 / 295 / 337 against my script's 191 / 293 / 338; the lane's
explanation — it models the tie bias at the scale and pass 2b held it at
1/256 — is the right size for a two-cut difference).

I read `over_reach()` and `scale_cost()` rather than only their PASS lines.
The row range `ceil(lo_m*scale - 0.5) .. floor(hi_m*scale - 0.5)` is the
correct inversion of a device sample centre at `(j + 0.5)/scale` guest pixels;
`lo_m`/`hi_m` are the over-reached side of the plane under each `dirn`, matching
`cap_clip()`'s own sign convention; `lost` is scored against the union of all
57 edges' scale-correct footprints, which is what makes it smaller than
`over-reach` rather than equal to it.

**The third leg fires on a mutant.** I copied the file into
`scratch-audit2c/` (symlink tree; the real path was never touched) and moved
the sample centre by half a sample, `m = (j + 0.5)/scale` → `m = j/scale`.
The totals stay plausible — 112 → 0, 298 → 69, 568 → 222 — and the leg
reports `FAIL -- 57 counted samples no emitted polygon covers`. Different
numbers from the lane's own reported mutant (26 phantoms, 112 → 103, so a
different off-by-half), the same conclusion: the `covers()` cross-check
discriminates, and a sign or index error in the span arithmetic would not pass
silently.

**The scale-independence claim reproduces exactly.** `geom.c:829-838` says the
first capture with a cut is `Line_0024.0` and 19 captures cut, identically, at
scales 1-4. My own count, over the same captures with the tie modelled at each
scale and bites taken from `cap_clip()`'s own violation expression:

```
scale 1: first capture with a cut Line_0024.0, 19 captures cut
scale 2: first capture with a cut Line_0024.0, 19 captures cut
scale 3: first capture with a cut Line_0024.0, 19 captures cut
scale 4: first capture with a cut Line_0024.0, 19 captures cut
```

### The commit really is comment-only, checked two ways

The PR says the queued arm on `36e85c96c9` stands because `geom.c` changed
only comments. That is the claim the whole disposition of the pending verdict
rests on, so I checked it twice and neither check is the lane's:

1. Strip C comments from `4cc0d26dc0:glsl/geom.c` and `68b5ac7dcb:glsl/geom.c`
   and normalise whitespace — **identical** (45,071 → 49,308 bytes of comment
   growth, zero bytes of code).
2. Build `geom_dump` twice — once against this tree, once against a symlink
   tree holding `4cc0d26dc0`'s `glsl/geom.c` — and run both binaries.
   **Byte-identical output, 42,049 bytes, md5 `d16bf20f526caf274e5f58640b72823d`**,
   which is the md5 the commit message quotes.

So `b_ref 36e85c96c9` is still the last commit on this branch that can move a
pixel, and the verdict that arrived on it is a verdict on the shipped shader.

### And the instruments the PR says are unchanged are unchanged

* `--quantise`: 0 quantised px moved after, 4 on 4 captures before, three legs
  PASS.
* `--controls`: 393 removed / 393 golden-dark / 0 golden-lit; 1104 boundaries
  on a whole index = 617 low + 487 high.

Both match the body. `shader_poly()`'s new `bites` parameter is inert when it
is `None`, which is every call site but `scale_cost()`'s.

---

## MEDIUM

### N4 — `Fill_*` is under `must_not_move` on a premise the device has now falsified twice; the change *does* reach `Fill_0032.0`, and every pixel it moves there it moves to the golden

`predictions/line-cap-clip.json` (LEG C2) and the PR body both say:

> `Line_width/Fill_*` — fill mode; with `widen_lines` false the generator
> emits the byte-identical shader it emitted before, so a line change must not
> touch them. `Fill_0032.0` moved 26,721 → 26,715 on the failing arm **and
> nothing in this branch's diff can reach it.**

That sentence is false, and the arm result dirs on this host say so without
ambiguity. Comparing the captures rather than the scores:

| | `Fill_0000.0` | `Fill_0001.0` | `Fill_0032.0` |
|---|---:|---:|---:|
| arm 1 (`9fdc6b5d70`, pre-deadband), px changed vs its base | 0 | 0 | **6** |
| arm 2 (`36e85c96c9`, deadbanded), px changed vs its base | 0 | 0 | **4** |
| of those, changed **to the golden's exact value** | — | — | **6 of 6, 4 of 4** |

The narrow fills do not move; the `w = 32` fill does, at both tips of the
range the cap rule acts on, and one of the moved pixels goes from lit cyan
`(54,252,252)` to background `(32,34,36)` — the golden's own value. That is
the cap clip removing an over-reaching cap pixel, on a capture the offline
model never scores. The goldens agree that this test is width-dependent on
real hardware: `Fill_0032.0` differs from `Fill_0000.0` in **12,021 px**.

Three further facts close off "device nondeterminism", which is what the lane
kept the glob to test for:

* arm 2 ran **2 runs per side** and both sides were byte-identical with
  themselves; `ab_compare` classes `Fill_0032.0` **ATTRIBUTABLE to the change**.
* the two arms' **base** captures of `Fill_0032.0` are pixel-identical to each
  other across all three base runs, so the 20 master commits merged between
  the arms change nothing here.
* the two **fix** captures differ from each other by exactly 2 px — so the
  deadband itself moved the answer on this capture (see N5).

**Failure scenario.** As registered, this prediction cannot pass. The arms job
re-runs every registered prediction whose refs are live, so any future
re-registration that keeps `Line_width/Fill_*` under `must_not_move` fails on
`Fill_0032.0` again, `arms.sh` recomputes `regressed` from the verdicts, and
`fold.sh:503-510` refuses to fold a `regressed` PR — the lane is parked on a
leg that fires every time the change works. Worse for the record: the PR
currently tells the next reader that a movement it cannot explain happened on
a capture nothing can reach, when what happened is the cap rule correcting six
pixels of a fill-mode capture. A future genuine regression in `Fill_*` will be
read as the same unexplained noise.

**Remediation.** The mechanism first, then the leg. Name what actually draws
in `Line_width/Fill_0032.0` — the evidence above says the widened-line path
runs for it, so `widen_lines` is not false there and the "byte-identical fill
shader" argument does not apply. Then re-scope C2 so it states what this lane
now believes *before* the next arm: `Fill_0000.*`/`Fill_0001.*` are genuinely
below the deadband's reach and belong in `must_not_move`; `Fill_0032.0` is a
capture the cap rule legitimately improves and belongs with the movers. That
is a post-hoc edit to a leg that fired, which this lane has rightly resisted
twice — the distinction that makes it legitimate here is that the *premise*
was falsified, not the *result*: the device did not disappoint the prediction,
it disproved the sentence the prediction was justified by. Say that in the
file. Re-register (a changed file is a new registration and the arms job picks
it up on the next tick); nothing else clears `regressed`.

### N5 — "it gives up nothing at scale 1" is a property of 48 `Line_*` captures, not of the renderer: on the device the deadband gives up 2 golden-correct pixels at scale 1

`NOTES.md:406-408` states, unqualified:

> **It gives up nothing at scale 1, and it can never make anything worse than
> master at any scale.**

and `geom.c:595-596` calls scale 1 the control row that "must read zero on
every column". The second half of the NOTES sentence is sound — a suppressed
cut emits master's own four corners, and I have no evidence against it. The
first half is measured over the 48 non-void `Line_*` captures, which is the
only set any instrument in this lane scores, and the device contradicts it
outside that set:

| `Fill_0032.0` pixel | pre-deadband build | deadbanded build | golden |
|---|---|---|---|
| (271, 93) | `51 154 152` | `51 155 151` | `51 154 152` |
| (264, 123) | `51 227 79` | `51 228 78` | `51 227 79` |

Both arms' base captures are identical, so this is the deadband: at
`surface_scale_factor == 1` it suppressed a sub-half-pixel cut that the
pre-deadband build took, and two pixels that were exactly right became wrong
by one unit in two channels.

Note *how* they are wrong: these are not coverage flips, they are shaded
values. The half-pixel proof is a **coverage** argument — the removed sliver
contains no sample centre — and it is correct as far as it goes. But taking
the cut also re-triangulates the strip and synthesises a vertex, which changes
how the varyings interpolate at samples that stay covered. "Removes no sample"
therefore does not imply "changes no pixel", even at scale 1, and every
instrument in this lane is blind to it by construction: `--rivals`,
`--controls`, `--shader`, `--quantise` and `--scale-cost` all score ink masks
or sample coverage. `--depth` is the one value-aware oracle here and it covers
`z`, not colour.

**Failure scenario.** A later reader — or the next lane on #13's colour phase,
which is 76.3% of the issue's residual — takes "exact at scale 1" and "gives
up nothing at scale 1" at face value, and sizes the deadband's cost at zero
for the configuration every arm and every golden in this campaign runs at. The
true figure is small but not zero, it is in the channel that lane cares about,
and no instrument in this repository would report it.

**Remediation.** Two sentences and a scope, not a code change: say that the
half-pixel proof bounds *coverage* and not interpolated values; scope the
scale-1 "costs nothing" claim to the 48 `Line_*` captures the instruments
score; and record the two pixels above, since they are the only measurement of
the deadband's true cost at scale 1 that exists. Whether to chase the value
class at all is a separate decision and needs a device, so it is not this
remediation's.

---

## LOW

### N6 — the PR body's "twelfth" is not the ratio of the two numbers it quotes

`geom.c:592-597` and `NOTES.md:404-406` both do it right — "whose
device-sample equivalent scales with `scale^2`, so … on the order of a
twelfth" — because `112` device samples at scale 2 is compared with
`393 × 4` device samples, not with 393. The PR body drops the conversion:

> Against the 393 guest px the cap rule removes at scale 1 (`--controls`), the
> deadband gives up on the order of a twelfth of the clip's own work above 1x.

Read with the numbers in the sentence above it, that is 112/393 ≈ 28%, four
times the figure it states. The commit message of `68b5ac7dcb` has the same
omission. Two of this campaign's standing lessons are exactly this shape (a
ratio built from two workloads; a bound quoted as a value), and the two places
that got it right show the lane knows the conversion — it is the summary that
lost it.

---

## What I ran

* `line_cap_phase.py --scale-cost`, `--quantise`, `--controls` against
  `~/goldens/results` — the tables above, every leg PASS.
* The same file copied into a symlink tree with the sample centre moved by
  half a sample: the `covers()` leg reports FAIL on 57 phantom samples.
* My own scale-independence count at scales 1-4, using `cap_clip()`'s own
  violation expression through `shader_poly(bites=...)`.
* `geom_dump` built against this tree and against a symlink tree holding
  `4cc0d26dc0:glsl/geom.c`; both binaries run and their output compared.
  Byte-identical, md5 `d16bf20f52…`.
* A C-comment strip of `glsl/geom.c` at both shas.
* `glsl/geom.c:235-239`, `vk/draw.c:1204-1212`, `vk/shaders.c:44-60, 317-330,
  841`, `glsl/vsh.c:985-1005` — the push-constant argument, read rather than
  taken.
* The arm result directories under `dispatch/results/` for both arms, pixel
  for pixel on all three `Fill_*` captures plus their goldens, and the full
  verdict text at
  `arms/pairs/82cbbed7e047….verdict.txt` for the violated leg.

Scratch files lived in `scratch-audit2c/` and are deleted. Nothing outside
`docs/audits/` is touched by this pass.

## Disposition

A1 is closed, and closed well: the precondition is at the point of derivation,
the cost is an instrument rather than a paragraph, its non-trivial leg fires on
a mutant, the rejected option's price is real, and the commit provably cannot
move a pixel. Pass 2's three and pass 1's eight stay closed.

But the arm that landed an hour after pass 2b was posted is a near-total
vindication of the shader — 20 better, 0 worse, every narrow capture
bit-identical — carrying one failed leg whose justification is a false
sentence, and a two-pixel measurement that contradicts an unqualified claim in
`NOTES.md`. Neither is in the shader. Both are in what this PR tells the next
reader is true, and one of them is what keeps `regressed` on the PR and the
fold shut.

**`needs-remediation`.**
