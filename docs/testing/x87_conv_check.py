#!/usr/bin/env python3
"""#82: prove the x87 hard-FPU integer conversions SATURATE, on the shipped text.

The four floatx80_to_int{32,64}[_rtz]_nds helpers in target/i386/tcg/fpu_helper.c
live inside `#if defined(XBOX) && defined(__aarch64__)`, so nothing on a desktop
build ever compiles them, and nothing on the test disc issues an FSCALE with a
runaway exponent, so no capture arm could ever reach the defect (#82). This is
the check that closes that gap: it carves the helper block out of the source
file by its markers -- shipped text, not a retyping -- wraps it in the two stub
types it needs, and

  1. compiles and RUNS it natively, driving every helper through rounding modes,
     both boundaries, overflow in each direction separately, +/-inf, NaN, the
     2^63-1 representability trap, and the FSCALE composition itself;
  2. compiles the identical translation unit for aarch64 (clang --target), which
     is the only architecture the block is ever built for. Compile only: there
     is no aarch64 execution environment on this host, and the script says so
     rather than implying more.

`--ref <git-ref>` carves from that revision instead of the working tree, which
is how the check proves it has POWER: against 62218327 (the commit that
introduced the defect) the saturation and FSCALE assertions must FAIL; against
19737094 or later they must pass. A checker that cannot fail on the known-bad
revision tests nothing.

Usage:  x87_conv_check.py [--ref <git-ref>] [--src <path/to/fpu_helper.c>]
        exit 0 = every assertion passed (and the aarch64 compile succeeded)
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

SRC_DEFAULT = 'target/i386/tcg/fpu_helper.c'
START = 'static inline double floatx80_round_to_int_nds'
END = '#define floatx80_to_int64_round_to_zero'

# Self-contained on purpose: no libc headers, so the same TU cross-compiles for
# aarch64 without a sysroot. Enum values and the float_status field names are
# the real ones from include/fpu/softfloat-types.h; only the fields the helpers
# touch are declared.
STUB = r'''
typedef __INT32_TYPE__ int32_t;
typedef __INT64_TYPE__ int64_t;
typedef __UINT16_TYPE__ uint16_t;
#define INT32_MIN (-2147483647-1)
#define INT32_MAX 2147483647
#define INT64_MIN (-9223372036854775807LL-1)
#define INT64_MAX 9223372036854775807LL
double floor(double); double ceil(double); double trunc(double);
double rint(double); double scalbn(double, int);
typedef enum { float_round_nearest_even = 0, float_round_down = 1,
               float_round_up = 2, float_round_to_zero = 3 } FloatRoundMode;
enum { float_flag_invalid = 0x0001 };
typedef struct float_status { uint16_t float_exception_flags;
                              FloatRoundMode float_rounding_mode; } float_status;
static inline void float_raise(uint16_t f, float_status *s) { s->float_exception_flags |= f; }
'''

MAIN = r'''
#include <stdio.h>
#include <string.h>
#include <math.h>
static int fails, total;
static float_status st;
static void reset(FloatRoundMode m) { st.float_exception_flags = 0; st.float_rounding_mode = m; }
#define INV() ((st.float_exception_flags & float_flag_invalid) != 0)
static void chk(const char *name, int ok, const char *got) {
    total++; if (!ok) fails++;
    printf("  %-4s %s%s%s\n", ok ? "ok" : "FAIL", name, ok ? "" : "   got ", ok ? "" : got);
}
#define C32(name, expr, want, winv) do { reset(mode); int32_t v = (expr); char b[64]; \
    snprintf(b, sizeof b, "%d inv=%d", (int)v, INV()); chk(name, v == (want) && INV() == (winv), b); } while (0)
#define C64(name, expr, want, winv) do { reset(mode); int64_t v = (expr); char b[64]; \
    snprintf(b, sizeof b, "%lld inv=%d", (long long)v, INV()); chk(name, v == (want) && INV() == (winv), b); } while (0)
#define CD(name, expr, want) do { double v = (expr); char b[64]; snprintf(b, sizeof b, "%g", v); \
    chk(name, (isinf(want) ? (isinf(v) && signbit(v) == signbit(want)) : \
               ((want) == 0.0 ? (v == 0.0 && signbit(v) == signbit(want)) : v == (want))), b); } while (0)
int main(void) {
    const double NaN = __builtin_nan(""), Inf = __builtin_inf();
    const double P40 = 1099511627776.0, P70 = 1180591620717411303424.0;
    FloatRoundMode mode;
    printf("rounding modes (FIST honours RC; FISTTP truncates)\n");
    mode = float_round_nearest_even;
    C32("nearest_even  2.5 -> 2 (ties-to-even)", floatx80_to_int32_nds(2.5, &st), 2, 0);
    C32("nearest_even  3.5 -> 4 (ties-to-even)", floatx80_to_int32_nds(3.5, &st), 4, 0);
    C32("nearest_even -2.5 -> -2", floatx80_to_int32_nds(-2.5, &st), -2, 0);
    mode = float_round_down;
    C32("down  2.5 -> 2", floatx80_to_int32_nds(2.5, &st), 2, 0);
    C32("down -2.5 -> -3", floatx80_to_int32_nds(-2.5, &st), -3, 0);
    mode = float_round_up;
    C32("up    2.5 -> 3", floatx80_to_int32_nds(2.5, &st), 3, 0);
    C32("up   -2.5 -> -2", floatx80_to_int32_nds(-2.5, &st), -2, 0);
    mode = float_round_to_zero;
    C32("zero  2.9 -> 2", floatx80_to_int32_nds(2.9, &st), 2, 0);
    C32("zero -2.9 -> -2", floatx80_to_int32_nds(-2.9, &st), -2, 0);
    mode = float_round_up;   /* rtz must ignore RC */
    C32("rtz ignores RC:  2.9 -> 2", floatx80_to_int32_rtz_nds(2.9, &st), 2, 0);
    C32("rtz ignores RC: -2.9 -> -2", floatx80_to_int32_rtz_nds(-2.9, &st), -2, 0);

    printf("int32 boundaries and SATURATION (#82: MIN for negative, MAX for positive AND NaN)\n");
    mode = float_round_nearest_even;
    C32("2147483647 exact, no invalid", floatx80_to_int32_nds(2147483647.0, &st), INT32_MAX, 0);
    C32("-2147483648 exact, no invalid", floatx80_to_int32_nds(-2147483648.0, &st), INT32_MIN, 0);
    C32("2147483648 -> INT32_MAX + invalid", floatx80_to_int32_nds(2147483648.0, &st), INT32_MAX, 1);
    C32("-2147483649 -> INT32_MIN + invalid", floatx80_to_int32_nds(-2147483649.0, &st), INT32_MIN, 1);
    C32("+2^40 -> INT32_MAX + invalid", floatx80_to_int32_nds(P40, &st), INT32_MAX, 1);
    C32("-2^40 -> INT32_MIN + invalid", floatx80_to_int32_nds(-P40, &st), INT32_MIN, 1);
    C32("+inf -> INT32_MAX + invalid", floatx80_to_int32_nds(Inf, &st), INT32_MAX, 1);
    C32("-inf -> INT32_MIN + invalid", floatx80_to_int32_nds(-Inf, &st), INT32_MIN, 1);
    C32("NaN -> INT32_MAX + invalid (softfloat parity)", floatx80_to_int32_nds(NaN, &st), INT32_MAX, 1);
    C32("rtz +2^40 -> INT32_MAX + invalid", floatx80_to_int32_rtz_nds(P40, &st), INT32_MAX, 1);
    C32("rtz -2^40 -> INT32_MIN + invalid", floatx80_to_int32_rtz_nds(-P40, &st), INT32_MIN, 1);
    C32("rtz NaN -> INT32_MAX + invalid", floatx80_to_int32_rtz_nds(NaN, &st), INT32_MAX, 1);

    printf("int64 boundaries and the 2^63-1 representability trap\n");
    C64("-2^63 exact, no invalid", floatx80_to_int64_nds(-9223372036854775808.0, &st), INT64_MIN, 0);
    C64("2^63 (what 2^63-1 rounds to) -> INT64_MAX + invalid", floatx80_to_int64_nds(9223372036854775808.0, &st), INT64_MAX, 1);
    C64("+2^70 -> INT64_MAX + invalid", floatx80_to_int64_nds(P70, &st), INT64_MAX, 1);
    C64("-2^70 -> INT64_MIN + invalid", floatx80_to_int64_nds(-P70, &st), INT64_MIN, 1);
    C64("NaN -> INT64_MAX + invalid", floatx80_to_int64_nds(NaN, &st), INT64_MAX, 1);
    C64("rtz +2^70 -> INT64_MAX + invalid", floatx80_to_int64_rtz_nds(P70, &st), INT64_MAX, 1);
    C64("rtz -2^70 -> INT64_MIN + invalid", floatx80_to_int64_rtz_nds(-P70, &st), INT64_MIN, 1);
    C64("rtz NaN -> INT64_MAX + invalid", floatx80_to_int64_rtz_nds(NaN, &st), INT64_MAX, 1);

    printf("FSCALE composition: helper_fscale feeds the rtz result straight into scalbn\n");
    reset(float_round_nearest_even);
    int n_pos = floatx80_to_int32_rtz_nds(P40, &st);     /* ST1 = +2^40: runaway exponent */
    int n_neg = floatx80_to_int32_rtz_nds(-P40, &st);    /* ST1 = -2^40 */
    CD("ST0=1.5,  ST1=+2^40 -> +inf", scalbn(1.5, n_pos), Inf);
    CD("ST0=-1.5, ST1=+2^40 -> -inf", scalbn(-1.5, n_pos), -Inf);
    CD("ST0=1.5,  ST1=-2^40 -> +0",   scalbn(1.5, n_neg), 0.0);
    CD("ST0=-1.5, ST1=-2^40 -> -0",   scalbn(-1.5, n_neg), -0.0);
    printf("\n%d assertions, %d failed\n", total, fails);
    return fails ? 1 : 0;
}
'''


def carve(text):
    lines = text.splitlines()
    try:
        s = next(i for i, l in enumerate(lines) if l.startswith(START))
        e = next(i for i, l in enumerate(lines) if l.startswith(END))
    except StopIteration:
        sys.exit(f'markers not found: START={START!r} END={END!r}')
    return '\n'.join(lines[s:e + 1]) + '\n'


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref', help='git ref to carve from instead of the working tree')
    ap.add_argument('--src', default=SRC_DEFAULT)
    a = ap.parse_args()

    if a.ref:
        p = run(['git', 'show', f'{a.ref}:{a.src}'])
        if p.returncode:
            sys.exit(p.stderr.strip())
        text, origin = p.stdout, f'{a.ref}:{a.src}'
    else:
        with open(a.src) as fh:
            text = fh.read()
        origin = a.src
    block = carve(text)
    print(f'source: {origin}  ({block.count(chr(10))} lines carved)')

    tmp = tempfile.mkdtemp(prefix='x87conv-')
    hdr = os.path.join(tmp, 'conv_block.h')
    with open(hdr, 'w') as fh:
        fh.write(STUB + '\n' + block)
    native = os.path.join(tmp, 'native.c')
    with open(native, 'w') as fh:
        fh.write('#include "conv_block.h"\n' + MAIN)
    # The aarch64 TU references all four helpers so an unused-function warning
    # cannot hide one that failed to carve.
    a64 = os.path.join(tmp, 'a64.c')
    with open(a64, 'w') as fh:
        fh.write('#include "conv_block.h"\n'
                 'int64_t use(double d, float_status *s) { return floatx80_to_int32_nds(d, s)'
                 ' + floatx80_to_int64_nds(d, s) + floatx80_to_int32_rtz_nds(d, s)'
                 ' + floatx80_to_int64_rtz_nds(d, s); }\n')

    cc = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
    exe = os.path.join(tmp, 'native')
    p = run([cc, '-std=gnu11', '-O2', '-Wall', '-Wno-unused-function', '-I', tmp,
             native, '-o', exe, '-lm'])
    if p.returncode:
        print(p.stderr)
        sys.exit('native compile FAILED')
    print(f'native  ({os.path.basename(cc)}): compiled')
    r = run([exe])
    sys.stdout.write(r.stdout)
    native_ok = r.returncode == 0

    clang = shutil.which('clang')
    a64_ok = None
    if clang:
        p = run([clang, '--target=aarch64-linux-gnu', '-std=gnu11', '-O2', '-Wall',
                 '-Wno-unused-function', '-Werror', '-I', tmp, '-c', a64,
                 '-o', os.path.join(tmp, 'a64.o')])
        a64_ok = p.returncode == 0
        print(f'aarch64 (clang --target=aarch64-linux-gnu -c): '
              f'{"compiled" if a64_ok else "FAILED"}  '
              f'[compile only -- no aarch64 execution environment on this host]')
        if not a64_ok:
            print(p.stderr)
    else:
        print('aarch64: clang not found, compile check skipped')

    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0 if (native_ok and a64_ok is not False) else 1)


if __name__ == '__main__':
    main()
