# lane.vshcpu345: #345 half 2, silicon arithmetic in nv2a_vsh_cpu

The nv2a_vsh_cpu library is third-party. It is fetched by
`subprojects/nv2a_vsh_cpu.wrap` and again by
`android/app/src/main/cpp/CMakeLists.txt`, both at `1115255708`. Its CPU
evaluator runs in three places in `pgraph.c`:

- `LAUNCH_TRANSFORM_PROGRAM`;
- `pgraph_vsh_writeback_constants`;
- the #242 no-Begin vertex.

nxdk_vsh_tests' `CPU Shader Tests` reads its results through the evaluator.
This lane makes that evaluator agree with PR #344's silicon rows.

## The change

There is one patch file,
`subprojects/packagefiles/nv2a_vsh_cpu/0001-silicon-arithmetic.patch`.
`*.patch` is gitignored, so it is force-added. It changes
`src/nv2a_vsh_cpu.c` only:

| op | before | after (silicon) |
|---|---|---|
| MUL, MAD | 0×inf and 0×NaN give NaN; −0×5 gives −0 | a product with a ±0 operand gives **+0**. A NaN operand is not a zero (the GLSL `_MUL` rule, `NaNToOne`) |
| DP3, DPH, DP4 | a plain sum, so a 0×inf term gives NaN | if the plain sum is NaN, it is recomputed from zero-forced products. Otherwise it is unchanged (the GLSL `_DotZeroForced` rule) |
| RCC | clamps to the decimals 5.42101e-20 and 1.884467e19, chosen by `result > 0`, so RCC(+inf) = +0 falls into the negative branch and gives `0x9F7FFFFD` | clamps into exactly [2^-64, 2^64] on the side of the result's **sign bit** (`clampAwayZeroInf`) |
| RCP, RCC, RSQ of NaN | pass the input NaN through | return `0x7FFFFFFF`, the ILU's canonical NaN on silicon |

The patch reaches both builds:

- **meson**: the wrap's `diff_files`. meson applies it only when it
  downloads the subproject. An existing checkout needs
  `meson subprojects update --reset nv2a_vsh_cpu`.
- **Android CMake**: `src/` is copied from the local checkout or the
  FetchContent clone into `${CMAKE_BINARY_DIR}/nv2a_vsh_cpu-stage`, and the
  patch is applied there. The result is copied into `nv2a_vsh_cpu-patched`
  only where a file differs, so a reconfigure rebuilds nothing. Neither
  checkout is modified. A checkout that meson already patched is recognised
  by the `hakuX #345` marker and copied as it is.

**The trap the CMake step avoids.** `git apply` run inside any git work tree
resolves the patch's paths against that tree's root. The build tree is inside
the hakuX checkout, so the paths fall outside the cwd, git skips them, and it
**exits 0 having changed nothing**. A pristine copy in a subdirectory of
this worktree showed it: `patch -p1` patched it, `git apply` returned 0 and
left it unpatched, and `git apply` with a ceiling patched it. The step sets
`GIT_CEILING_DIRECTORIES=${CMAKE_BINARY_DIR}`, and after applying it checks
for the marker. If the marker is missing, configure stops with a fatal error.

## Host evidence (before any device run)

`cpu_rows.py ORIG NEW SPECIAL_raw.txt` builds `cpu_rows.c` against the
pristine and the patched library on this x86-64 host. It then reads the
console's rows.

- **SPECIAL_RAW, all four components:** 20/44 rows match silicon before the
  patch and **42/44** after. The two left are `RSQ(±MaxSub)`: the host gives
  `0x5F000001` in both builds because it does not flush the subnormal. The
  device does flush it: the Nova dry run `0-0-x-1790388689-xbox-special-dry`
  already matches silicon on both rows. So this residual is the host's, not
  the patch's.
- **Finite-input sweep**, 200000 inputs per op, weighted toward signed zeros
  and the 2^±64 edges. The sweep classifies every changed component:

| op | changed | what changed |
|---|---:|---|
| MUL | 15830 | −0 → +0 only |
| MAD | 169 | −0 → +0 only |
| DP3 / DPH / DP4 | 0 / 0 / 0 | nothing |
| RCC | 55200 | 52989 were in [5.42101e-20, 2^-64) and are now 2^-64; 2211 were in (2^64, 1.884467e19] and are now 2^64. Signs are kept |
| RSQ / RCP | 0 / 0 | nothing |

The finite changes are the ones silicon requires: `−0×5 = +0` is a measured
row, and the clamp is exactly 2^±64. The outputs between 2^64 and 1.884467e19
were not clamped at all before. Silicon's clamp point is exact:
`RCC(1e-30) = 0x5F800000`, and the GLSL helper uses the same bound.

## Build evidence

- `cmake_patch_test.py CMAKE ORIG` lifts the CMakeLists block verbatim into a
  small project inside this worktree, so the build runs inside a git
  repository just as the real one does. It runs four cases:
  - **fetch**, **local** and **premeson** each configure and build. Each
    compiles `.../nv2a_vsh_cpu-patched/src/nv2a_vsh_cpu.c` with the marker,
    leaves the checkout byte-identical, and keeps the file's mtime across a
    reconfigure.
  - **mismatch** is a checkout the patch cannot apply to. It fails at
    configure.
- **Falsifier:** `--no-ceiling` removes the `GIT_CEILING_DIRECTORIES` wrapper.
  fetch and local then fail at configure with "did not apply" instead of
  shipping unpatched sources. So the marker check is what catches git's
  silent no-op.
- `meson_wrap_test.py MESON CMAKE_BIN` copies this branch's wrap and
  packagefiles into a small meson project and uses `cmake.subproject()` as
  `hw/xbox/nv2a/pgraph/thirdparty/meson.build` does. The results:
  - setup prints `Applying diff file "nv2a_vsh_cpu/0001-silicon-arithmetic.patch"`;
  - ninja compiles the patched file (marker present);
  - the probe prints `MUL(0,inf)=0x00000000` and `RCC(+inf)=0x1F800000`.
- The APK build log for the fix ref must carry
  `nv2a_vsh_cpu: applied 0001-silicon-arithmetic.patch`, or `already carries`
  if the build host has a meson-patched checkout. Checked below once the
  build exists.

## Device runs (Nova, CPU Shader Tests, the SPECIAL_RAW disc)

Both runs are queued on the same disc that the dry run and the console run
used, `vsh-build-subnorm/.../nxdk_vsh_tests_xiso.iso` (sha256 `4605ccb8…`,
unchanged since before the dry run):

- base: master `a5b5b628f2`, request `1790434451-vshcpu345-2750318`;
- fix: `a3baa35286`, request `1790434455-vshcpu345-2750642`.

Each run is scored with
`vsh_score.py <result>/captures1 --reference ~/hakux-work/hardware/runs/2026-09-25-special/console-run/console`.
The dispatcher's default references do not hold these two files.

**Prediction (written before either run).**

- **SPECIAL_raw.** Base: 22/44 lines identical to silicon, the same set as
  the dry run. Fix: **44/44**.
- **SUBNORM_MAC_raw.** Base: 20/32, as in the dry run. Fix: **22/32**. The
  two lines that move are `MUL a=0x807FFFFF b=0x4B800000` and
  `MUL a=0x80000001 b=0x71800000`. The device flushes the subnormal operand
  to −0, so the product's sign was −0, and the patch gives +0 as silicon
  does. The other 10 lines are unchanged, because they are subnormal
  handling (#255):
  - MOV and ADD pass the subnormal through or flush it on the wrong side;
  - `MAD 0x1C800000²+2^-126` keeps the subnormal product;
  - `MAD 2^-126×−0.5+0` gives −0 from a product that is not zero.
- **Must not move:** every line identical on base stays identical.

**pgraph arm.** `docs/testing/predictions/vshcpu345-must-not-move.json`
(a `a5b5b628f2`, b `a3baa35286`) guards every must-not-move vertex-program,
fog and NaN suite in the vshconst and dpforce345 arms.
GeometrySuperscreen_* is left out because it drifts on its own. The arms job
queues it.

## Results (attempt 2, 2026-09-26)

**Why attempt 1 did not finish.** Attempt 1 ended correctly, in a
`waiting:` state. It was waiting on three things outside its session: the two
vsh device requests, the arms job's pgraph arm, and the fix APK's build log.
It posted a `[lane.vshcpu345] waiting:` comment. `jobs/handback.sh` resumed
the lane once all three had finished. Nothing failed.

**Where the runs went.** Both vsh requests ran on **Thor** (`bdc158a5`), not
Nova. The disc is `vsh:iso:6fe98f/CPU Shader Tests`. Every capture was
written after its run started (read from `.fatx_times.json`). The two `STALE`
rows in `vsh1.txt` are leftovers from 09-25 (Exceptional_Float, MAC_mov) and
are not scored.

- base: APK `25abcaccbf45` (master `a5b5b628f2`)
- fix: APK `9ef7ad198dc3` (`a3baa35286`)

**vsh_score.py against the console text.** The reference is
`hardware/runs/2026-09-25-special/console-run/console`. Counts are lines
identical to silicon:

| capture | base | fix | predicted fix | base-exact lines lost |
|---|---:|---:|---:|---:|
| SPECIAL_raw | 22/44 | **44/44 (IDENTICAL)** | 44/44 | 0 |
| SUBNORM_MAC_raw | 11/32 | 11/32 | 22/32 | 0 |

- **SPECIAL_raw: the prediction holds.** Every must_move row now matches
  silicon: MUL, MAD and DP3/DP4 with 0×inf or 0×NaN, `−0×5`,
  RCC(±inf), RCC(±huge), and RCP/RCC/RSQ of NaN. vsh_score reports the file
  IDENTICAL.
- **SUBNORM_MAC_raw: the base and fix files are byte-identical**
  (sha256 `b7ef53098a93` for both), so must_not_move holds. The predicted
  +2 did not happen, because its premise was a Nova property. On Nova's dry
  run the evaluator flushed subnormal operands to −0, and the patch's +0
  rule then fixed two MUL rows. On Thor the evaluator does **not** flush:
  `MUL 0x807FFFFF×2^24` gives `0x8C7FFFFE`, a finite product, so the ±0 rule
  never applies. All 21 remaining lines are subnormal handling (MUL, ADD and
  MAD keep subnormals that silicon flushes to +0). That is #255 and not this
  patch. **Residual, named:** 21 subnormal lines on Thor, which differ from
  Nova because of the device's float-mode behaviour, not the patch.

**pgraph must-not-move arm.** The requests are
`1790435594-arms-vshcpu345-{base-2960820,fix-2960842}`. Judged locally with
`ab_compare.py --expect vshcpu345-must-not-move.json`:
**VERDICT: PASS, all 411 registered checks hold.** 420 of 420 captures are
byte-identical between the arms, with 146 exact on each side. As of this
writing the arms job has not posted its `[job.arms]` comment.

**The Android build compiled the patched source.** The gradle log does not
print CMake's `message(STATUS)` on success, so `build-a3baa35286.log`
carries no `nv2a_vsh_cpu:` line. The dispatcher build tree still has
`nv2a_vsh_cpu-patched/src/nv2a_vsh_cpu.c` with the `hakuX #345` marker,
written at 12:16 PDT, which is when the fix build ran. A later build of
another ref reconfigured that tree at 12:21, so its `compile_commands.json`
shows the unpatched `_deps` path. The behavioural proof is stronger than the
log line would have been: the fix APK changes exactly the 22 SPECIAL_raw
rows that the patch targets, and nothing else.

## Status (attempt 1, superseded by Results above)

**Waiting**, on things outside this session:

- the two vsh requests above, with 76 requests ahead of them in the queue
  when they were queued;
- the arms job's `[job.arms]` verdict on the pgraph prediction;
- the fix APK's build log, `dispatch/logs/build-a3baa35286*.log`, to grep for
  the CMake patch line.

preflight.sh passed on `29d006df02`. On resume:

1. Score both runs with the reference named above.
2. Check the prediction line by line.
3. Grep the build log.
4. Update the PR body with the before/after.
5. Mark the PR ready. It goes to audit, because it touches `android/`.

## Do not repeat

- Do not use `git apply` in a CMake or other build step inside this
  repository without a ceiling and a check that the patch actually applied.
  It exits 0 and applies nothing.
- Do not score RSQ/RCC subnormal rows on an x86 host and call the result a
  defect. The device flushes subnormals, and the host does not.
- Do not look for SPECIAL_raw's reference in vsh_score.py's defaults. The
  file is under `hardware/runs/2026-09-25-special/`.
- Do not predict SUBNORM_MAC rows from a Nova dry run when the request can
  land on Thor. The evaluator flushes subnormals on Nova and does not on Thor,
  so pin the device or predict both.
- Do not grep the gradle build log for CMake `message(STATUS)` lines. Gradle
  prints them only when configure fails. Read the build tree, or rely on the
  device rows.
