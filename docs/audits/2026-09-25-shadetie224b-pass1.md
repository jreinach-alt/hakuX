# Audit pass 1: PR #263 (lane shadetie224b), #224 family B

Auditor: `[job.cloud]`, 2026-09-25. Diff read: `origin/master...9afbc48b20`
(merge base 2b04d4d422), 12 files, +1543/-123. The code is
`hw/xbox/nv2a/pgraph/glsl/vsh-ff.c`; the rest is lane notes, offline tooling
under `docs/lanes/shadetie224/` and the prediction file.

**Result: no HIGH, no MEDIUM, four LOW.** Next state: `needs-audit-2`.

## What was checked

1. **GLSL helpers against the Python envytools port** (`celsius_lt.py`), line
   by line:
   - `ltMulCore` matches `lt_mul`: NaN, zero, inf, exponent, 14x14-bit
     product, renormalise, saturate.
   - `ltA3` matches `lt_add3`: `er = max(e)+2`, shift `er-e-7`, normalise to
     bit 20, `>>7`, saturate at 0xFE.
   - `ltsA` matches `lts_add`.
   - `ltR` matches `lt_rcp`: the LUT is identical, and so is the Newton step
     (`((1<<21) - s0*f) * s0 >> 14 << 11`).
   - `ltMk` matches `mkfin_rz_ftz` for mantissas already normalised to bit
     13, which is all its callers pass.
   - Integer ranges fit in 32 bits: the product is at most 28 bits, the
     `ltA3` sum at most 21, the `ltR` intermediate at most 28.
   - The shift arguments are never below -5 (`ltA3`) or below 0 (`ltsA`), so
     `ltShr` never shifts by a negative amount of 32 or more.
2. **The fold moved into the light loop (`fold_specular`)** instead of
   `oD0 += oD1` after it:
   - The specular output starts at `(0,0,0,a)` in
     `append_lighting_constant`, and only lights add to it.
   - The removed FF-path `oB0 += oB1` for one-sided lighting added vsh.c's
     default `oB1 = (0,0,0,1)` rgb, which is zero. Nothing is lost.
   - In the vertex-program path, `oD1` no longer holds the lit specular under
     SPECULAR_ENABLE clear. That does not matter: vsh.c:969 only writes `vtxD1`
     from `oD1` when `specular_enable` is set.
3. **Infinity now reaches the outputs** where FLOAT_MAX used to stand in (a
   zero attenuation denominator makes `ltR(0)` return +inf):
   - `ltM(inf, 0)` is 0, because the zero check comes before the inf check.
     The AtFixed 0/0/0 behaviour the comment describes holds.
   - A nonzero channel gives +inf, and inf + -inf gives NaN. vsh.c:954-955
     applies `clamp(NaNToOne(...))` to `oD0`/`oB0` before interpolation, so
     no inf or NaN varying leaves the vertex stage.
4. **Removed `assert(false)` default:** light types other than INFINITE fall
   into the local branch. The enum is OFF/INFINITE/LOCAL/SPOT, and OFF is
   skipped at line 408, so nothing new is reachable.
5. **Local-eye / local-light half vector:** the homogeneous form
   `(s^2 + k0|H|^2) / (s^2 k1 + |H|^2 k2)` equals the old
   `((N.H)^2/|H|^2 + k0) / (... k1 + k2)` in exact arithmetic, because
   `|H|^2 > 0`. The old zeroing on `numerator <= 0` becomes the
   `t < 0` → zero test.
6. **The prediction and its arm:**
   - The verdict is FAIL on 1 of 370 legs: `Specular_back/SpecParams_FF_Pow0_1`,
     1259 -> 1280.
   - The PR already carries `regression-accepted:224`, so the board has
     decided that leg. This audit does not reopen it.

## Findings

### LOW-1: the non-precomputed half-vector path has no offline model

`celsius_lt.py` ports only an infinite light with a non-local eye (its own
docstring says so). `exact.py` checks the helpers, not how they are composed.
Two parts of the local-light / local-eye composition are therefore the
author's reading of `pgraph_celsius_lt_full`, and nothing in this PR checks
them:

- `if (s < 0.0) zero = true;`, which the precomputed path does not have;
- the extra truncation `ltsA(ltsM(ss, k.y), 0.0)` in the denominator.

The must_not_regress legs on the Lighting spotlight / point / local-eye
goldens held, so any error is bounded by what those goldens exercise.

*Failure scenario:* if envytools does not zero on `s < 0` in this mode, a
local light whose unnormalised `N.H` is slightly negative with `k0 > 0` shows
no highlight where silicon shows a faint one. No golden in the corpus has been
shown to reach this case.

### LOW-2: `ltR` handles NaN differently from the port

The GLSL `ltR` returns NaN for a NaN input. `lt_rcp` in the port has no NaN
case: exponent 0xFF gives `er = -2`, which returns signed zero. The GLSL NaN
then reaches the output as `NaNToOne` → 1, while the port gives specular 0.

*Failure scenario:* this needs `b` to be NaN, which means an overflowed
`ltsM(ss,k.y)` and `ltsM(hd,k.z)` of opposite infinite signs. D3D's specular
tables do not produce such values. It is unreachable in practice.

### LOW-3: `< 0.0` tests zero sign differently from the port's sign bit

The GLSL tests `cd < 0.0`, `t < 0.0` and `s < 0.0`. The port tests `S(x)`,
the sign bit. The two disagree only on -0.0. `ltMk` returns -0.0 only when a
negative result underflows below 2^-126, and `r == 0` returns +0.0.
Unreachable with colour-range operands.

### LOW-4: shader cost is unmeasured

Each light on each side now costs about 40 integer-emulated operations. Each
`ltA3` call runs three loops over local arrays. `check.py` compiles 240
states with glslc (the SPIR-V frontend), which says nothing about driver
compile time or vertex throughput on Adreno or Mali. The arm shows the shader
compiles and renders on the arm device. With 8 lights and two-sided
lighting, per-vertex cost may be noticeable in games.

*Failure scenario:* frame-time regressions in lit-geometry-heavy titles.
Nothing in the gate measures them.

## Leads for the Pow0_1 back-face regression (not findings)

- **NOTES candidate 2 (negate before or after `lt()`) is moot.** `ltBits`
  adds 0x200 to the magnitude and never touches bit 31, since a carry out of
  exponent 0xFE lands in 0xFF, not in the sign bit. So
  `lt(-x) == -lt(x)` for every x.
- **Another candidate to price with `celsius_lt.py`.** The precomputed path
  (an infinite light with a non-local eye, which is what SpecParams_FF uses)
  no longer zeroes the specular when `N.H <= 0`; the old code did. When
  `s < 0` but `s + k0 >= 0`, the port gives a nonzero highlight. At power 0.1,
  k0 is where the fit is steepest. On the back face, `N = -tNormal` against
  the front half-vector register makes `s < 0` common. This matches envytools
  as ported, so if it is the cause, the question is whether the back side uses
  a different half vector on silicon, not whether the arithmetic is wrong.

## For pass 2

No remediation is required. Pass 2 should confirm that none of the LOWs has
become a MEDIUM in the head it audits: that the head's vsh-ff.c helpers are
unchanged from 9afbc48b20, or that any change was re-run through `exact.py`.
