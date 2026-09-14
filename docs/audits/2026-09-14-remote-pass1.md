# Audit pass 1 — `lane.remote`'s 24 commits, before they fold

Review of the compiled changes on `origin/claude/docs-tooling-agentic-coding-u152m1`
that have **not yet folded** into the campaign branch, plus the measurement and
gate claims the same commits make. Machine-readable companion:
[`2026-09-14-remote-pass1.json`](2026-09-14-remote-pass1.json).

| | |
|---|---|
| Auditor | lane.audit-remote (pass 1 of 2) |
| Base | `8c5218af3f0` (merge-base with the campaign branch) |
| Head | `082878a1ca7` *take L5, and put P2's exception-flag scope where P2 asked for it* |
| Scope | 24 commits; 4 compiled files, +212 lines; `gate.sh`; two investigation records |
| Method | reading, plus one live process probe against `gate.sh`'s interlock. **Nothing was built.** |

## Why this pass exists rather than a fold

The same category folded unaudited twice tonight — a 53-commit merge, then
#73's `accel/tcg` fix on a green build and preflight, whose audit then found a
`siglongjmp` into a returned frame with two page spinlocks held, reachable from
the DMA thread. This work is already durable on `origin` on lane.remote's own
branch, so nothing was at risk in waiting.

## Counts

| Severity | Count |
|---|---|
| HIGH | 1 |
| MEDIUM | 5 |
| LOW | 9 |

Three of the MEDIUMs and one LOW are in `gate.sh` and the investigation
records rather than in compiled code. They are severity-rated by the same
rubric — each has a named failure and a named consumer — and each says so.

## HIGH

### H1 — `fpu_helper.c:3154` — the new conversions return the wrong saturation, and `helper_fscale` is the one caller that reads the value

`622183271b` replaced the four round-to-zero / round-per-RC conversion macros
on the hard-FPU path with real functions. The rounding half is right and closes
#74. The out-of-range half returns the wrong value:

```c
if (!(r >= -2147483648.0 && r <= 2147483647.0)) {
    float_raise(float_flag_invalid, s);
    return INT32_MIN;                 /* both signs, and NaN */
}
```

Softfloat, on the other path of the same `MAP_HELPER_SOFT_HARD` pair,
**saturates**: `fpu/softfloat-parts.c.inc:1239` returns `max` for NaN, `:1244`
returns `sign ? min : max` for infinity, `:1267`/`:1271` return `min`/`max` for
normal overflow. So positive overflow and NaN now disagree between the two
builds of this file.

Every FIST/FISTP/FISTTP/FBSTP caller overwrites the returned value whenever
`float_flag_invalid` is set, so the divergence is invisible at the six sites
the change was written for. I enumerated all ten consumers:

| site | guarded? |
|---|---|
| 1029, 1043, 1056, 1069, 1083, 1096 | yes — `float_flag_invalid` or the int16 range test |
| 1594 `helper_fbst_ST0` | yes — the `±1e18` test |
| 1918, 2293 | soft path only (inside the `#else` of `#if USE_NATIVE_DOUBLE_STORAGE`) |
| **3154 `helper_fscale`** | **no** |

**Scenario.** A guest runs `FSCALE` with a finite `ST1` of magnitude ≥ 2³¹ —
`ldexp()`/`scalbn()` with a runaway exponent. NaN and infinite `ST1` are
handled earlier (`:3119-3147`), so only the finite case reaches the conversion.

- Before: `(int32_t)ST1` is UB, but on aarch64 it is `fcvtzs`, which saturates
  to `INT32_MAX` → `scalbn(ST0, INT32_MAX)` → `±inf`. That is the x87-correct
  masked-overflow result, and what the soft path gives.
- After: `n = INT32_MIN` → `scalbn(ST0, INT32_MIN)` → `±0`.

The error inverts rather than shifting: **infinity becomes zero.** And because
the soft path still gives infinity, the same guest code now computes a
different answer depending on the Android *Native Floats (JIT)* setting.

No pixel corpus reaches it. `nxdk_pgraph_tests` does not exercise FSCALE
overflow, which is exactly the "wrong outside the cases the goldens exercise"
clause.

**Remediation.** Saturate like softfloat in all four helpers — return
`r < 0 ? INT32_MIN : INT32_MAX` (resp. `INT64`) on overflow and the `MAX` value
for NaN. The FIST/FBSTP guards key on the flag and not on the value, so this
does not touch the behaviour #74 was fixing.

## MEDIUM

### M1 — `psh.c:2376` — the cube corner reads signs *after* the border remap has rebuilt the vector

`4a08abef66` samples `dotSTR%d.x` and `dotSTR%d.y`, twenty lines after
`apply_border_adjustment(ps, vars, i, "dotSTR%d")` at `:2356`. For a cubemap
that call emits `remapBorderCube`, and `remapBorderCube` (`:2187-2206`) does
not scale in place — it projects to the dominant face, remaps `(s,t)`, and
**reconstructs a direction with the major axis forced to ±1.0**:

```
if (face == 0) return vec3(1.0, -st.y, -st.x);
```

So with a border enabled, `.x` is the sign of the major axis, not of
`dot_{i-2}`. The measured rule is stated in terms of the raw dot signs, and
the fix no longer reads them. The six `DotSTR3D_*` captures carry no border,
so 296,177 px → 150 px does not exclude this.

Second, smaller: with a border the outermost texel *is* the border ring, so
`K = 1 - 1/8192` lands there rather than on the logical corner, even with
correct signs.

### M2 — `psh.c:2381` — the coordinate is now a step function, and the fetch is still implicit-LOD

`texture(texSamp%d, dotSTR%dDir)` derives its mip level from the screen-space
derivative of the coordinate. That coordinate now takes exactly four values, so
the derivative is **identically zero** inside a sign region and **~2K** across
a boundary. On a mipmapped cube that pins LOD 0 everywhere inside a region
regardless of minification, and selects the coarsest level (1×1 on a full
chain) on the single quad that straddles a sign change.

Both are new; the old coordinate varied smoothly with the interpolated dots.
The investigation's own observation that the coordinate "saturates" over
13,000–29,000 px regions establishes the region structure but says nothing
about the derivative the sampler sees.

Fix is one call: `textureLod(..., 0.0)`, available on all three targets
`pgraph_glsl_append_version` emits — and then say which level silicon fetches,
because the comment does not mention LOD at all.

### M3 — `gate.sh:147` — the new warning delta can never contain a header

`aadd7d8f7f`'s delta restricts to files compiled in both runs by mapping a
source path to a meson object name with `tr '/' '_'` and grepping for
`[/_]<name>\.o$`. Objects are named after `.c` files. A `.h` path never
matches, so **every header warning is silently dropped from the delta** — two
commits after `d844e6067f` widened the census regex to `\.[ch]` *because*
headers were being missed, and while `desktop-gate-warnings.md:200-214` lists
header warnings in the census.

A warning introduced in a shared header — the case `c19074ed8a`'s desktop gate
was added for — raises `distinct warning sites` and reports as neither removed
nor added. The block prints how many files are common but not which were
dropped, so the exclusion is not visible in kind.

### M4 — the skew-bound doc's mode-2 conclusion is one of two explanations, and the instrument that separates them was not available

The doc concludes mode 2 costs the same as mode 1 because "on this workload
essentially every published segment carries a draw". `pfifo.c:1064-1082` shows
mode 2 skips the hold **only** on `FSK_SEG_NO_DRAW`; hitting
`FIFO_SKEW_SCAN_MAX_WORDS` and holding anyway falls through to the same
`pfifo_bound_skew()` as mode 1. "The scan kept giving up" produces exactly the
measured result.

The doc's own positive-control paragraph says why this was not checked: the
`fifoskew` line, which carries the `big=` counter that distinguishes them,
goes through `__android_log_print` and prints nothing on the desktop.

And the chosen explanation is contradicted by the code it is about —
`pfifo.c:86-87` records **148,704 submissions for 180 draws**, 0.12% carrying a
draw, not "essentially every". A different disc is not an explanation for a
factor of 800.

**Checked and clean, because the brief's precedent warned about it:** the
mode-2 arm is *not* a tautological falsifier. `80512e37` does carry
`FIFO_SKEW_DRAW_ONLY` and its own code path at `pfifo.c:1064`, so
`HAKUX_FIFO_SKEW_BOUND=2` did not fall through to `FIFO_SKEW_EVERY`.

### M5 — "bounds the noise floor's cause completely" extrapolates a two-test disc to the full disc

The run was on a two-test disc and measured a **varying score**
(11,392/13,056/15,360 → 10,240). The full-disc figure the sentence then absorbs
is described in the same breath as *2,341 px moving at a constant score* — a
different signature. An experiment that only saw the first does not show they
are one hazard. This is the decision the owner is holding, so the claim's scope
matters: restrict it to the disc that was run, and keep the constant-score
observation open with its signature named.

## LOW

| id | site | one line |
|---|---|---|
| L1 | `fpu_helper.c:120` | "handed back to the UI, so the switch reads OFF" — `nativeGetFpSafe` is declared and never called; `setupSwitch` reads SharedPreferences, so it reads **ON** and does nothing. The cache-key half of the sentence is correct. |
| L2 | `fpu_helper.c:233` | Names two flag-reading helpers as if exhaustive; `helper_fisttl_ST0`/`helper_fisttll_ST0` do the same. |
| L3 | `gl/texture.c:844` | `downloaded` / "actually written back" — the helper returns `found_overlap`, true whether or not anything was dirty. Behaviour is right; the name and comment are narrower than the test. |
| L4 | `gate.sh:46` | `emulator_pids()` returns 1 even when it found a pid (probed: it did). Harmless under `set -uo pipefail`; a later `set -e` aborts the gate with status 1, not the 2 it reserves for REFUSING. |
| L5 | `gate.sh:26` | `cd "$REPO"` unchecked, `REPO=/home/user/hakuX` hard-coded and absent on this host. Pre-existing; fails closed. |
| L6 | `gate.sh:147` | Unescaped `.` interpolated into `grep -qE`; `grep -Ff` matches paths as unanchored substrings. Both err toward including. |
| L7 | `gate.sh:125` | `find build -name '*.c.o'` as the denominator: not the tree's count, excludes C++, and grows with use — so two runs' percentages are not comparable. |
| L8 | `psh.c:2729` | `#define DOT_STR_3D_K` emitted into every pixel shader, used by one case arm. |
| L9 | skew-bound doc:38 | The GL tree is named (`80512e37`); the Vulkan digest's tree is not, and the equality carries the section's conclusion. |

## Does each remediation close the finding it claims?

| claim | verdict |
|---|---|
| **L5** — delete the `floatx80_round` alias | **CLOSED.** Zero callers in `target/i386/`; the macro was translation-unit-local, so m68k's call sites get the real softfloat function. Deleting is strictly better than the comment it replaced — a future caller is now a compile error. |
| **P2** — exception-flag scope | **CLOSED as specified.** P2 offered two options and this took the second: the statement is at the top of the `#ifdef USE_HARD_FPU` block (`:211-241`), where it covers the whole path rather than three functions. I re-verified its factual claims: `fpu_set_exception()` has exactly one caller (`:860`), inside the `#ifndef USE_HARD_FPU`; every other `env->fpus \|=` in the file writes condition codes (C0–C3), never IE/ZE/OE/UE/PE/DE. **It documents rather than fixes** — the guest-visible defect (FNSTSW/FSTENV read clear, no #MF when unmasked) is unchanged, and that is what P2 permitted. |
| **M2 / #74** — FIST honours RC, can raise invalid | **CLOSED for what it named,** and it introduces **H1** at the one consumer nobody guarded. FIST/FISTP/FISTTP/FBSTP/FIST-m16 all now round per RC and substitute integer-indefinite correctly; the range tests are sound (`2147483647.0` and `±2^63` are all exactly representable, and the `!(lo ≤ r ≤ hi)` form does take NaN to the invalid branch, as the comment claims). |
| **M4 / #80** — `glGetError()` behind the writeback | **CLOSED,** exactly as pass 1 proposed: capture the return, call the probe only when true. Restores both the old cost and the truth of the `download_overlap` label. L3 is a naming nit on top, not a reopening. |
| **L6** — `rint()` follows host rounding | **DECLINED WITH A REASON,** which AGENTS.md explicitly permits. The blocker named (NDK `roundeven()` availability unverifiable from here, block invisible to the desktop build) is the right shape, and I re-checked the underlying grep: no `fesetround`/`fegetround` outside `tests/`. |
| **`d844e6067f`** — the gate's interlock never fired | **CLOSED, and I verified it functionally rather than by reading.** Against a live process named `qemu-system-i386`: old `pgrep -x qemu-system-i386` → rc=1 (inert, as claimed); `/proc/N/comm` → `qemu-system-i38`, 15 chars, confirming the truncation premise; new `emulator_pids()` → returned the pid. **The gate now fires.** |
| **`aadd7d8f7f`** — the warning census was a slice | **PARTIALLY.** The scope line and the file+message keying are both real improvements. The delta it adds cannot see headers — **M3**. |

## What I could not audit, and why

- **Nothing was built.** The desktop build is a KNOWN GAP here
  (`libcurl4-openssl-dev`), and the `fpu_helper.c` block in question is inside
  `#if defined(XBOX) && defined(__aarch64__)`, so even a working desktop build
  would not compile it. **I did not compile any of the four files.** H1, M1 and
  M2 are read from source; none is confirmed against a binary.
- **No device.** Every measurement claim in the window is taken on trust:
  #51's 296,177 px → 150 px and "GL vs Vulkan 78/78 byte-identical", #34's four
  validation findings being gone, #60's 31,436 px, the skew-bound score table
  and its digests. M4, M5 and L9 are about the *reasoning* over those numbers
  and are checkable from the tree; the numbers themselves are not.
- **M2's LOD claim is untested on hardware.** Whether silicon's DOT_STR_3D cube
  fetch uses LOD 0 or a computed level is not established anywhere in the
  record, so the remediation (`textureLod(..., 0.0)`) picks the level that
  matches the derivation, not one that was measured.
- **M1 is not reachable by anything on the test disc,** so the only way to
  confirm the wrong corner is a new capture with a bordered cubemap on a
  DOT_STR_3D stage. No such capture exists.
- **`gate.sh` was exercised only at the interlock.** The delta block was read,
  not run: running it needs two real gate logs from two builds, which needs the
  desktop build.

## Outside my territory

`45c8adb4f6` edits `docs/testing/nv2a_issues.toml` directly, which AGENTS.md:228
bars a lane from doing. Filed as a board request rather than fixed here — see
`$DISPATCH_DIR/board-requests/audit-remote.md`. (`nv2a_index.json`, touched by
three other commits, is *generated* by `nv2a_index.py build` and is not the
same problem.)
