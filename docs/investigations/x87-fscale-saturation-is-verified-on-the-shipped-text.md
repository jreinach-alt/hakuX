# `#82` is verified on the shipped text — by a check that fails on the commit that introduced it

Issue #82 (audit pass 1, HIGH) said the x87 hard-FPU integer conversions in
`target/i386/tcg/fpu_helper.c` returned `INT32_MIN` for *both* signs of overflow
and for NaN, where softfloat's `partsN(float_to_sint)` returns `max` for positive
overflow and NaN; and that `helper_fscale` is the one consumer that reads the
value unguarded, so a guest `FSCALE` with finite `|ST1| >= 2^31` returned ±0
where x87 returns ±inf. The fix, `19737094`, landed the same day. The issue
stayed open on its own last line: **"Read from source, not confirmed against a
binary."** The commit's verification lived in a scratchpad and could not be
re-run by anyone, which makes it a claim rather than a record.

This closes that gap. Reproduced by

```
python3 docs/testing/x87_conv_check.py                  # working tree: must pass
python3 docs/testing/x87_conv_check.py --ref 62218327   # introducing commit: must FAIL
```

## What the check does

It carves the helper block out of the source file between two markers —
`static inline double floatx80_round_to_int_nds` and
`#define floatx80_to_int64_round_to_zero` — so it tests the **shipped text**, not
a retyping. That block lives inside `#if defined(XBOX) && defined(__aarch64__)`
(`:132`), so no desktop build ever compiles it. The carve is wrapped in a stub
that declares only what the block touches: the two integer typedefs, the four
`INT*_MIN/MAX` constants, five libm prototypes, the `FloatRoundMode` enum with
softfloat's real values, `float_flag_invalid`, a two-field `float_status`, and
`float_raise`. No libc header is included, which is what lets the identical
translation unit cross-compile for aarch64 without a sysroot.

Then it

1. compiles the block natively (`cc -std=gnu11 -O2 -Wall`) and **runs** it
   through 35 assertions: all four rounding modes on `FIST`, `FISTTP` truncating
   under every RC, both `int32` boundaries exactly, overflow in **each direction
   separately**, ±inf separately, NaN, the `2^63-1` representability trap on
   `int64`, and the `FSCALE` composition itself;
2. compiles the same translation unit for aarch64
   (`clang --target=aarch64-linux-gnu -c -Werror`), on a TU that references all
   four helpers so an unused-function warning cannot hide one that failed to
   carve. **Compile only.** There is no aarch64 execution environment on this
   host and the script prints that caveat rather than implying more.

The `FSCALE` rows are the composition `helper_fscale` performs, not an analogy:
`n = floatx80_to_int32_rtz_nds(ST1)` then `scalbn(ST0, n)`. That is `:3189`
feeding `:3192`, and on this path `floatx80_scalbn` *is* libc `scalbn` —
`floatx80_scalbn_nds` at `:504-509` discards the status and returns
`scalbn(a, n)`.

## The power test

A checker that cannot fail on the known-bad revision tests nothing, so
`--ref <git-ref>` carves from that revision instead of the working tree:

| ref | what it is | failed / 35 | aarch64 | exit |
|---|---|---:|---|---:|
| `62218327` | the #74 fix that introduced the defect | **13** | compiled | 1 |
| `5ce23e28` | parent of the fix (`19737094^`) | **13** | compiled | 1 |
| `19737094` | the fix | 0 | compiled | 0 |
| `8c864b1d` | last commit touching the file | 0 | compiled | 0 |
| `a2a75f0d` | HEAD when this was written | 0 | compiled | 0 |

The thirteen that fail on the introducing commit, verbatim:

```
FAIL 2147483648 -> INT32_MAX + invalid                     got -2147483648 inv=1
FAIL +2^40 -> INT32_MAX + invalid                          got -2147483648 inv=1
FAIL +inf -> INT32_MAX + invalid                           got -2147483648 inv=1
FAIL NaN -> INT32_MAX + invalid (softfloat parity)         got -2147483648 inv=1
FAIL rtz +2^40 -> INT32_MAX + invalid                      got -2147483648 inv=1
FAIL rtz NaN -> INT32_MAX + invalid                        got -2147483648 inv=1
FAIL 2^63 (what 2^63-1 rounds to) -> INT64_MAX + invalid   got -9223372036854775808 inv=1
FAIL +2^70 -> INT64_MAX + invalid                          got -9223372036854775808 inv=1
FAIL NaN -> INT64_MAX + invalid                            got -9223372036854775808 inv=1
FAIL rtz +2^70 -> INT64_MAX + invalid                      got -9223372036854775808 inv=1
FAIL rtz NaN -> INT64_MAX + invalid                        got -9223372036854775808 inv=1
FAIL ST0=1.5,  ST1=+2^40 -> +inf                           got 0
FAIL ST0=-1.5, ST1=+2^40 -> -inf                           got -0
```

Every one is a positive overflow, a NaN, or `FSCALE` with a positive runaway
exponent. **Every negative-overflow row passes on both sides**, and so does every
rounding-mode row: the check is targeted at the half softfloat specifies
differently, and it confirms the pre-fix code was right about rounding and
wrong about saturation — which is what the issue said. The `invalid` flag is
raised on both sides; only the value differs. The two `FSCALE` rows are the
defect as the issue stated it: infinity became zero.

The fix commit's message reports a scratchpad control of 7 failures out of 30.
That harness is not in the repository and cannot be re-run; this one supersedes
it. The counts differ because this check splits `int32`/`int64` and RC/`rtz`
into separate rows, not because the two disagree — the failing set has the same
shape.

Two `diff`s pin what was measured:

- the carved region is **byte-identical** between `19737094` and HEAD, so
  verifying the working tree verifies the fix as it landed and nothing since
  has touched it;
- between `62218327` and the fix's parent the region differs by comment text
  and one removed dead macro (`floatx80_round`) only — the four helper bodies
  are the same, and the identical 13-row failure set at both refs is the
  corroboration. (123 lines carve at HEAD against 89 at `62218327`; the growth
  is the comment block the fix added.)

## The blast radius, re-walked at HEAD

The fix commit enumerated ten consumers and found one unguarded. Re-derived
here at HEAD's line numbers, with the preprocessor context walked by a script
rather than read around:

| line | helper | what happens to the value |
|---|---|---|
| `:1064` | `fist_ST0` | overwritten by `val != (int16_t)val` |
| `:1078` | `fistl_ST0` | overwritten on `float_flag_invalid` |
| `:1091` | `fistll_ST0` | overwritten on `float_flag_invalid` |
| `:1104` | `fistt_ST0` | overwritten by `val != (int16_t)val` |
| `:1118` | `fisttl_ST0` | overwritten on `float_flag_invalid` |
| `:1131` | `fisttll_ST0` | overwritten on `float_flag_invalid` |
| `:1629` | `fbst_ST0` | overwritten by the ±1e18 range test, which both conventions trip |
| `:1953` | `f2xm1` table index | inside `#else` of `#if USE_NATIVE_DOUBLE_STORAGE` (`:1895/:1897`) — the softfloat-only arm, never sees the macro |
| `:2328` | `fyl2x` split | inside `#else` of `#if USE_NATIVE_DOUBLE_STORAGE` (`:2134/:2137`) — same |
| `:3189` | **`fscale`** | **unguarded**: flags saved, zeroed, restored around the call, value passed straight to `floatx80_scalbn` at `:3192` |

Ten sites, seven guarded, two unreachable on this path, one exposed. The two
array-index uses mattered enough to walk rather than trust: a wrong saturation
there would be an out-of-bounds read, not a wrong value.

## What a binary says here, and what it cannot

**Corrected 2026-09-18, a few hours after this was first written.** The first
version of this section claimed the corpus binary `0.4.0-j1-331-gd7dfe146` had
compiled this block with the fix in it. **That was wrong.** This lane's corpus
runs are the **desktop** build, `build/qemu-system-i386`, an x86-64 ELF run
under `xvfb-run`; the git-describe string it embeds names the *source*, not the
*target*. `fpu_helper_hard.c:1-4` does compile the helper file a second time
with `USE_HARD_FPU` on x86-64, but the `_nds` block additionally needs
`__aarch64__` (`:132`), so that binary never compiled a line of it. The fix
commit's own message says exactly that -- "x86-64 does not compile it" -- and I
had it in front of me.

The APK is `arm64-v8a` only (`android/app/build.gradle.kts:37`) and *would*
compile it. **No arm64 build containing `19737094` exists anywhere**, and the argument
that settles it is containment: `git branch -a --contains 19737094` returns
this branch and nothing else, so no build of any other ref can carry it. Two
supporting facts, stated by host because a first draft of this sentence
conflated them: this lane's container holds no APK at all (`find / -iname
'*.apk'` is empty), and the orchestrator's host holds seven, all built
2026-09-06, eight days before the fix. The fix commit recorded the Android
cycle as owed. It still is.

So what has *executed* the fixed text is the checker's native build of the
carved helpers, on x86-64; what has *compiled* it for aarch64 is the checker's
cross-compile leg, compile only. The corpus could not have judged the semantics
in any case: #74's instrumented run found zero x87 float-to-integer stores in
619 captures, and nothing on any disc we can build issues `FSCALE` with a
runaway exponent. The corpus is blind here by construction, which is why the
audit found this and no arm did. The semantic evidence is this checker, and
nothing else.

Not established, stated so nobody reads more into this than it holds:

- **aarch64 execution of the carved text.** Compile only. The arithmetic is
  IEEE double and `trunc`/`rint`/`floor`/`ceil`/`scalbn`, none of which is
  architecture-dependent, but that is an argument and not a run.
- **A real Android build of this block since the fix.** Owed, and the one
  thing this record cannot substitute for. A cross-compile of the carved region
  under stubs is not the real TU under the real headers.
- **Whether any title reaches it.** A guest `FSCALE` with `|ST1| >= 2^31` is
  `ldexp` with a runaway exponent; the fix is correct by specification whether
  or not a shipped title ever does it.
- **The `invalid` flag still does not reach the x87 status word** on this path.
  That is the known, separately scoped incompleteness the file's own comment
  records (`:407-412`), not #82.

## Where this leaves the fold

The orchestrator's notes hold the fold of `lane.remote`'s 24 commits on two
things: this HIGH, and audit pass 1's M1/M2 against #51's `DOT_STR_3D` work in
`glsl/psh.c`. This record lifts the first. The second is in a file this lane
does not hold, and nothing here touches it.

## The rule

**A number that cannot be re-run is a claim.** The fix was right on the day it
landed, and its own commit message said it had been verified thirty ways — but
the harness was a scratchpad, so the issue could not close on it and the fold
sat behind it for four days. The check now lives next to `psh_differ`, takes a
`--ref`, and fails where it must. Suggested wiring, for whoever holds
`docs/testing/preflight.sh` and `desktop.yml`: a third gate,
`python3 docs/testing/x87_conv_check.py`, exit code as the verdict. With
`clang` present it also runs the aarch64 compile leg; without it, it runs the
native leg only and prints that it skipped the other.

**And a second rule, earned by the correction above: a version string names
the source, not the target.** `git describe` is embedded in every build of a
commit, on every architecture. It says which tree was compiled and nothing
about which blocks of it were.
