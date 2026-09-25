# shadetie224: #224 family B, the fixed-function lighting tie

> **Outcome: lt(N) is REFUTED on the device and withdrawn (section 6).** It
> made all 18 family-B Flat captures exact, as predicted. But it also moved a
> flat Lighting_range/Directional specular block from silicon's blue 224 to
> 225, and 19 other lit captures got worse. Sections 2 and 3 describe the
> candidate as it was registered, before that verdict. The branch now
> carries no code change.

Lane brief: find a float pipeline in vsh-ff.c's lighting path that puts
Shade model's normal 3 on silicon's side of the tie (blue 60, ours 59). It must
leave the 178.5 tie of normal 1 at 179, and it must be derived from something
other than the two ties.

## 1. The premise was half wrong: the tie is not at 59.49999

shade224 NOTES 1B priced B as `0.7f x 0.3333333f x 255 = 59.49999`, a tie
that rounding decides. That skips two things the shader on master already
does. Both were in the capture's ref (40ca2bcb22, which descends from
1ff7ab3afe and 5c2b26db2f):

- `lightDiffuseColor` is `lt()`'d (vsh-ff.c:94, envytools xf_s2lt: round
  to a 13-bit fraction). 0.7f becomes **0.7000122**, so our lit blue is
  0.23333739, and x255 gives **59.501**. Plain round-to-nearest would give
  60 here, so our 59 has to come from somewhere else.
- It does: `colorPrecision()` (vsh.c:476) **truncates** oD0 to a 13-bit
  fraction before `floor(x*255 + 0.5)`. At 0.233 the grid step is 2^-16, so
  0.23333739 truncates to 0.2333221, which is 59.497, which is **59**. Normal
  1 is 0.7000122 x 1, already on the grid, so nothing is lost: 178.503
  gives 179.

The first check on the model: `price.py` reproduces master's wrong 59 and
all nine right colours.

## 2. The candidate and its independent argument

The eye-space normal is a value the transform unit (XF) hands to the lighting
unit (LT). The file's own header, citing envytools' Celsius model, says the
LT rounds **every** value it takes in with xf_s2lt. master applies that to the
light registers and the vertex colours, but not to N. So the candidate is
`vec3 N = lt(tNormal)` inside `append_lighting` (both paths, both faces). The
matrix product and texgen's use of tNormal stay float32, because they are XF.

The inputs come from the source (`shade_model_tests.cpp` @ 6743b6ab), not from
NOTES. The light is (0,0,1) and the diffuse (0,1,0.7). COLOR_MATERIAL takes
everything from the material, and ambient, emission and the specular colour
are all 0. The modelview is the XDK look-at from (0,0,-7), whose rotation is
identity, so the eye-space normal is the input normal bit for bit.

| n | z | golden G/B | master | lt(N) | lt(N) + truncating mul/add |
|---|---|---|---|---|---|
| 0 | 0.5773503 | 147/103 | ok | ok | ok |
| 1 | 1.0 | 255/179 | ok | ok | ok |
| 2 | 0.8164966 | 208/146 | ok | ok | ok |
| **3** | **0.3333333** | **85/60** | **85/59** | **ok** | **ok** |
| 4 | 0.9045 | 231/161 | ok | ok | ok |
| 5 | 0.7276 | 186/130 | ok | ok | ok |
| 6 | 0.4685 | 119/84 | ok | ok | ok |
| 7 | 0.8018 | 204/143 | ok | ok | ok |
| 8 | 0.29 | 74/52 | ok | ok | ok |

lt(0.3333333f) rounds **up** to 0.3333435, and that carries the product
over the truncation step: 0.2333445 truncates to 0.2333374, which is 59.501,
which is 60. For n = 1 the input rounding does nothing, because 1.0 is
already on the grid. Adding the LT's truncating multiply and add
(`ltN+trunc`) changes nothing here, so I did not add it. It stays unpriced.

Rejected: dropping colorPrecision's truncation would also give 60. But the
0.1f -> 25 goldens that fixed that rule (vsh.c:470) pin it, so it is not
free to move.

**Why this is not a two-point fit.** Nothing was tuned. The rule is the one
the file already applies to every other LT input, and it has no parameter.
Its prediction over the nine points is the same as master's except at n = 3.
The arm's must_not_regress over every other lit suite is the out-of-sample
test, because each of those suites lights different normals.

## 3. The arm

`docs/testing/predictions/shadetie224-ltnormal.json`, a = 0a4e284536,
b = (see the JSON). Registered by `register.py`.

- **expect = 0**: the 18 Fixed/W_Fixed Flat captures that carry B, and the
  six B-free ones stay at 0. The baseline is 1789968297-arms-primpv13-fix,
  where every differing pixel is the (0,85,59)/(0,85,60) pair.
- **must_not_move**: Shade_model Prog*, FixedTex*, W_FixedTex*. Prog* runs
  with lighting off, so no lighting block is emitted. FixedTex* uses a
  TEX0-only combiner.
- **must_not_regress**: Lighting_*, Material_*, Specular, Specular_back,
  SetVertexData.
- **In no leg**: the 12 Fixed/W_Fixed Smooth captures. Vertex 3 goes from
  59 to 60 there too. The baseline's signed blue error is mixed (in
  Fixed_Quad_Smooth_First it is -1: 23,188, 0: 20,975, +1: 8,817), so the
  move can go either way, bounded by the area of vertex 3's triangles.
- **The world in which it fails**: the tie is some other light-path precision.
  Then the pixels go to 59 or 61, or they stay put.

Before trusting the verdict, read scores1.tsv `status` for `unreadable`,
and run1.log for PARTIAL COVERAGE or UtilAcceptVsock.

## 4. For the next lane

- Do not re-price the tie as 59.49999. The 13-bit truncation in
  colorPrecision() decides it.
- If Lighting_normals regresses, the mechanism is refuted, not the leg. The
  next thing to price is the LT's truncating multiply/add (`ltN+trunc` in
  price.py), which this suite cannot tell apart.

## 5. State at end of session 1 (2026-09-25)

Waiting on the arm. The prediction is committed at 437a73388f with live
refs (a = 0a4e284536, b = 6765c1f5e9). The arms job will run it and post a
`[job.arms]` verdict on PR #252. When it lands: read scores1.tsv `status` for
`unreadable`, and run1.log for PARTIAL COVERAGE and UtilAcceptVsock. Then
mark the PR ready if every leg holds. If the must_move leg fails, record it
here as a refutation.

**Why session 1 did not finish:** it ended correctly, waiting on a ~90 min
arm with no way to sleep. `jobs/handback.sh` resumed it (attempt 2) once the
verdict was in.

## 6. The verdict: must_move held, the mechanism is refuted

`[job.arms]` FAIL on PR #252, 20 of 346 checks violated. a = 0a4e284536
(`1790350154-arms-shadetie224-base-95329`), b = 6765c1f5e9 (`...-fix-95351`).
Full text: `$WORK/arms/pairs/b5347566b510...verdict.txt`.

**Status column:** both arms show `ok` for 370 of 370 captures. Neither
run1.log has PARTIAL COVERAGE or UtilAcceptVsock, and the disc is identical
in both arms. The 18 "now exact" are real, not unreadable captures scored
as 0.

| leg | result |
|---|---|
| expect = 0, the 18 Fixed/W_Fixed Flat carrying B | **all 18 went to 0** (e.g. W_Fixed_QuadStrip_Flat 125,652 -> 0) |
| expect = 0, the six B-free | stayed 0 |
| must_not_move, Prog*/FixedTex* | held |
| (no leg) the 24 Fixed/W_Fixed Smooth | all better, by 834 to 20,595 each |
| must_not_regress | **20 worse**: see below |

Regressions (base -> fix):

- **Lighting_range/Directional: 792 -> 66,328.** Exactly +65,536: one
  256x256 block, every pixel `(255,255,224)` -> `(255,255,225)`. The base
  has 0 off-by-one pixels there, so silicon writes 224.
- Lighting_control: 10 worse (+13..+97) and 6 better (-41..-58). The
  NoSpec rows all move by the same +52 or -58.
- Specular: 5 worse, including Pow24_0 +321, and 5 better. Specular_back: 4
  worse and 5 better.

The Directional block is the decisive one. It is a flat, uniformly lit
area where lt(N) pushes a byte across a truncation step, **away** from
silicon. Section 3 registered "a capture that gets WORSE there refutes the
mechanism, not the leg", so rounding the normal at the XF->LT boundary, as
implemented, is not silicon's rule. Every mover in the other suites is a
1-LSB class, and they are mixed in direction. That is the signature of a
rule that is near silicon's but not the same.

What the verdict does establish: family B **is** a precision effect on the
light path's inputs. Moving N by at most 2^-14 relative fixed all 18
captures exactly and did not move one B-free capture. So the brief's
"world in which must_move fails" (a reduced-precision store before the
interpolator, moving 59 to 61) did not happen.

### Third tie point: Lighting_range/Directional

The inputs, from nxdk_pgraph_tests `src/tests/lighting_range_tests.cpp`:

- The light is a directional light, dir (0,0,1). Its ambient is 0.05 grey,
  its diffuse (1,1,0) and its specular (0,0,1). Scene ambient is 0.031373,
  emission 0.
- SPECULAR_PARAMS are the six raw words 0xBF56C33A, 0xC038C729, 0x4043165A,
  0xBF34DCE5, 0xC020743F, 0x40333D06. Specular is on, with
  LIGHT_CONTROL SEPARATE_SPECULAR | ALPHA_FROM_MATERIAL_SPECULAR.
- The mesh is FlatMeshGridModel. The quad normals are
  (±0.099014754, ±0.099014754, -0.990147543).
- The combiner is diffuse + specular.

The blue in that block is specular, because the light's diffuse has no
blue. So the refuting tie runs through the specular power function, not
through N.L x diffuse. The next candidate has to be priced against all
three points: Shade_model n=3 (60), n=1 (179) and this block (224). It is
not priced here. price.py models diffuse only; extending it needs vsh-ff.c's
specular-params evaluation.

## 7. Withdrawn, and what the next lane should do

The vsh-ff.c change is reverted (353f68c938) and master is merged in
(f533edc352). The diff against master is now docs only: this file,
price.py, register.py, and the refuted prediction, kept as the record.

**The `regressed` label will stay.** `arms.sh` works it out from the
verdicts on disk, per issue, for this branch. Only a newer #224 verdict can
supersede the FAIL. I did not queue a withdrawal arm: a docs-only head builds
master's binary, so the two arms would be one APK. ab_compare refuses that
without `--allow-same-binary`, which is the noise-floor mode, and a PASS
there would test nothing. The PR carries no pixel change. Folding it needs
one of two things. The owner can add `regression-accepted:224` (the
"regression" is on a sha this diff no longer contains), or the PR can be
closed and these notes carried by a later #224 lane. A harness rule that
drops a FAIL once the branch no longer touches the arm's files would cover
this case in general.

For the next #224 family-B lane:

- Do not re-run lt(N) on the whole normal. This arm refutes it.
- Candidates that are still unpriced: the LT's truncating multiply and add
  (`ltN+trunc`, identical to lt(N) on Shade_model, so it needs the
  Directional point to separate them); lt() on N.L only, or on the
  diffuse product only (leaving the specular path's inputs alone); and
  round-to-nearest in place of truncation at one named stage. Price each
  against all three ties, and against the Lighting_control NoSpec rows,
  which move as a single block of 52 or 58 px.
- If none fits all three with an argument that is independent of them,
  the capture to ask for is an nxdk_pgraph_tests case. It would be
  Shade_model's light and material with one flat quad per normal, the
  normal's z stepped across the 0.3333 tie at 1-ulp spacing (±8 ulp), and
  a second row stepping the Directional specular setup's normal z the same
  way. It needs no specular for row 1 and no diffuse blue for row 2. Each
  quad's byte then reads off which side of the tie silicon puts that input
  on, and the rounding point is a measurement, not a fit.

## 8. shadetie224b (2026-09-25): envytools' lighting unit, priced and ported

PR #263, lane shadetie224b. The candidate is not a new rounding rule. It is
envytools' Celsius lighting-unit model, which was already the source of
`lt()`, ported whole.

### The three ties are 0.03 of a byte wide, and they pull opposite ways

- **Shade model n3.** Master's product 0.7000122 x 0.3333333 is
  0.23333739. That is one float32 ulp *under* the 13-bit grid point
  15292/65536 = 0.2333374, which would give 60. Any upward nudge at 13 bits
  fixes it.
- **Directional.** Blue = diffuse 21 (ambients 0.031373 + 0.05) + specular.
  The specular is S(x) = (x + k0)/(x k1 + k2) at x = N.H = 0.9901475, with
  dS/dx of about 17. Master gives 203.47, just 0.03 under the 203.5 tie.
  Rounding x to 13 bits to nearest (0.990173) gives 204. Truncating it, or
  not rounding it, keeps 203.
- So N.L wants rounding **up** and N.H wants rounding **down/none**. No rule
  that rounds both dot products (or N) the same way fits both points.

### Pricing (`python3 price.py --three`)

| candidate | n3 (60) | n1 (179) | Dir spec (203) | 0.1f (25) | fits | independent argument |
|---|---|---|---|---|---|---|
| master | 59 | 179 | 203 | 25 | | |
| lt(N) (refuted on device) | 60 | 179 | **204** | 25 | | |
| lt(N.L) only | 60 | 179 | 203 | 25 | all | none: rounds N.L and not N.H |
| lt(N.L) and lt(N.H) | 60 | 179 | **204** | 25 | | |
| lt(diffuse product) only | 60 | 179 | 203 | 25 | all | none |
| lt(both products) | 60 | 179 | 203 | 25 | all | none: envytools says products truncate |
| RN at colorPrecision | 60 | 179 | 203 | 25 | all | contradicted by the Point size goldens (0.7 -> 178, 0.9 -> 229 need truncation) |
| **envytools Celsius LT, unmodified** | **60** | **179** | **203** | 25 | **all** | a hardware-tested model with no free parameter |

Four rules fit the three ties and have no argument outside them. They are
curve fits, per the brief, and they are not carried. The Celsius model also
gives:

- all nine Shade model flat colours (0 of 9 wrong);
- **127 for five 0.1 ambients**. That is the Lighting accumulation
  Directional-5 fact in vsh-ff.c's header, which the file says "no rounding
  of the float32 sum produces";
- a direction that matches Lighting accumulation's master residuals: ours is
  +1 over silicon in Point-2 (52/51), All (76/75) and Point-4 (103/102),
  which is what a truncating accumulation removes.

### The model

envytools `nvhw/pgraph_celsius_xfrm.c` `pgraph_celsius_lt_full` works like
this. Every LT input goes through `xf_s2lt` (`convert_light_v`): the normal,
the eye vector, the light vectors, the colours and the LTC scalars
(specular params). The multiply keeps the top 14 bits of the 14x14 product,
truncating (`lt_mul`). The adds align in fixed point and drop bits, towards
zero (`lt_add3`, `lts_add`). The reciprocal is a 64-entry table plus one
Newton step (`lt_rcp`). Then:

- An infinite light with a non-local eye: cd = N.L, s = N.H,
  cs = (s + k0) * rcp(s k1 + k2).
- Otherwise: H = eye + L unnormalised, and the second triple is evaluated
  homogeneously.

`celsius_lt.py` is a port of those functions.

### The change (fe07f11f50)

vsh-ff.c's loop now does what `pgraph_celsius_lt_full` does:

- `N = lt(normal)`, `lv = lt(dir)`, `k = lt(specularParams)`;
- ca, cd and cs come from the LT operations above;
- every colour product and sum is `ltVM`/`ltVA`;
- a folded specular (SPECULAR_ENABLE or SEPARATE_SPECULAR clear) is added
  into oD0 light by light, as envytools' `!spec_out` does, not after the
  loop.

Stages envytools does not model are the local-light (1, d, d^2) attenuation
input and the spot factor ("XXX spotlight"). Those stay float32 and are
rounded into the LT multiply.

### Checks run offline

- `vshemit/check.py`: the emitted lighting GLSL compiles under the NDK's
  glslc (Vulkan 450) for 120 VshStates x both paths, 240 of 240.
- `vshemit/exact.py`: the emitted GLSL helpers, compiled as C++, match
  `celsius_lt.py` bit for bit on 60,000 random operands. One bug was found
  and fixed this way: an underflowed product must be -0, not +0.

### The arm

`docs/testing/predictions/shadetie224b-celsius-lt.json` (sha256
a023d0f6...), a = 2b04d4d422 (master), b = fe07f11f50. It was registered by
`register_b.py` from a scores1.tsv, so every leg is named individually.

- expect = 0: the 24 Fixed/W_Fixed Flat captures.
- must_not_move: 136. These are Shade model Prog*/FixedTex*/W_FixedTex* and
  Lighting control VS_*_LightOff, where no LT code runs.
- must_not_regress: the other 210.

The world in which it fails: Directional leaves 224, or Lighting control or
Specular get worse in 1-LSB blocks. The Spot captures carry the one stage
that is not modelled.

Before believing the verdict: check scores1.tsv `status` for `unreadable`,
and run1.log for PARTIAL COVERAGE / UtilAcceptVsock.

### State at end of session 1 (2026-09-25)

Waiting on the arm. The prediction is committed at ca9d8dbe04 with live refs
(a = 2b04d4d422, b = fe07f11f50), so the arms job will run it and post a
`[job.arms]` verdict on PR #263. When it lands:

- check the status column and run1.log, as above;
- record the verdict here;
- mark the PR ready if every leg holds. If one fails, record the regressing
  suite as the stage that is refuted.

### The verdict (2026-09-25): FAIL on one leg, Specular_back Pow0_1

- **Result:** 18 of 18 B captures exact, and Directional stayed at 224.
  Differing went from 4.94M to 3.84M; 104 captures got better and 1 got worse.
- **The one worse leg:** `Specular_back/SpecParams_FF_Pow0_1`, 1259 -> 1280,
  all off-by-one. That capture is deterministic on disc across seven apks,
  and its front-face twin improved (2296 -> 1979). So the refuted stage is
  the back-face specular path, not the LT arithmetic.
- **Readability:** no `unreadable` captures and full coverage in both arms.

The details and the next steps are in `docs/lanes/shadetie224b/NOTES.md`.
