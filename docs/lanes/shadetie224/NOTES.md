# shadetie224: #224 family B, the fixed-function lighting tie

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
