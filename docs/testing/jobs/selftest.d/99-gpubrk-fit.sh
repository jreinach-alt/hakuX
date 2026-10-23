# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, ok/bad/check. Not executable, no shebang, no exit.
#
# The hakuX-gpubrk line (vk/draw.c, lane gpubreak1022, #433) says where the
# main pass's GPU time per draw goes only if its arithmetic is right. That
# arithmetic is vk/gpubrk.h, standalone so it builds here without qemu or
# Vulkan. This pins:
#
#   T1  a noise-free window with known per-feature costs: the fit gives each
#       beta back within 2%, the shares sum to the window's us per draw within
#       1%, and R^2 > 0.99.
#   T2  features that never move (fd, kill, blend all zero) get beta 0 and stay
#       out of the system; the rest are still recovered within 2%.
#   T3  two features that always move together (fd == zw): their betas still
#       sum to the true total, split about evenly, instead of failing.
#   T4  a window whose time does not depend on the features (constant plus
#       noise) reads R^2 < 0.3: the fit cannot pass an unrelated window as
#       explained.
#   T5  the histogram's p50 and p90 land on the bins where the cumulative weight
#       first reaches 50% and 90%, the boundary case included.
#   T6  the line gb_win_format writes, behind a logcat prefix, is read back by
#       docs/testing/perf/gpubrk_sum.py with the values it was given.
#
# Each GB_MUT_* line in gpubrk.h has a mutant here that must fail one of them,
# and a renamed field in the format must fail the parser (exit 2, not a row
# with the field missing).

echo "== vk/gpubrk.h fit, histogram and line, and gpubrk_sum.py"
GB=$(mktemp -d "$T/gpubrk.XXXXXX")   # fresh: no binary from an earlier run can stand in
mkdir -p "$GB/real" "$GB/zeroskip" "$GB/ridge" "$GB/center" "$GB/pct" "$GB/rename"
HDR="$REPO/hw/xbox/nv2a/pgraph/vk/gpubrk.h"
SUM="$REPO/docs/testing/perf/gpubrk_sum.py"

cat > "$GB/gpubrk_test.c" <<'C'
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <gpubrk.h>

static uint64_t lcg = 0x9E3779B97F4A7C15ull;
static double rnd(void) /* [0, 1) */
{
    lcg = lcg * 6364136223846793005ull + 1442695040888963407ull;
    return (double)(lcg >> 11) / 9007199254740992.0;
}

/* A segment of `cmd` draw commands, each feature drawn on its own */
static void seg(double *x)
{
    double cmd = 8 + (int)(rnd() * 17);
    x[GB_F_CMD] = cmd;
    x[GB_F_PCHG] = (int)(rnd() * cmd * 0.8);
    x[GB_F_FD] = (int)(rnd() * cmd);
    x[GB_F_KILL] = (int)(rnd() * cmd * 0.5);
    x[GB_F_BLEND] = (int)(rnd() * cmd * 0.6);
    x[GB_F_ZW] = (int)(rnd() * cmd);
    x[GB_F_TEX] = (int)(rnd() * cmd * 3);
    x[GB_F_DTX] = (int)(rnd() * cmd * 1.5);
    x[GB_F_KVTX] = rnd() * cmd * 0.4;
    x[GB_F_UKB] = rnd() * cmd * 0.25;
}

static const double truth[GB_NF] = { 12, 3, 6, 2, 1.5, 4, 2.5, 0.8, 9, 1.2 };

static double dot(const double *b, const double *x)
{
    double s = 0;
    for (int j = 0; j < GB_NF; j++) {
        s += b[j] * x[j];
    }
    return s;
}

static int fails;
#define EXPECT(cond, ...)                                                  \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAIL %s: ", __func__);                                 \
            printf(__VA_ARGS__);                                           \
            printf("\n");                                                  \
            fails++;                                                       \
        }                                                                  \
    } while (0)

static int near(double got, double want, double rel)
{
    return fabs(got - want) <= rel * fabs(want);
}

static void t1(void)
{
    GbFit f = { 0 };
    double x[GB_NF], beta[GB_NF], sh[GB_NF], fx[GB_NF], ysum = 0;
    for (int i = 0; i < 400; i++) {
        seg(x);
        double y = dot(truth, x);
        ysum += y;
        gb_fit_add(&f, x, y);
    }
    int m = gb_fit_solve(&f, beta);
    EXPECT(m == GB_NF, "solved %d of %d columns", m, GB_NF);
    for (int j = 0; j < GB_NF; j++) {
        EXPECT(near(beta[j], truth[j], 0.02), "beta %s %.4f, want %.4f",
               gb_fname[j], beta[j], truth[j]);
    }
    gb_fit_shares(&f, beta, sh, fx);
    double s = 0, want = ysum / f.sx[GB_F_CMD];
    for (int j = 0; j < GB_NF; j++) {
        s += sh[j];
    }
    EXPECT(near(s, want, 0.01), "shares sum %.4f, want %.4f", s, want);
    double r2 = gb_fit_r2(&f, beta);
    EXPECT(r2 > 0.99, "r2 %.4f", r2);
    printf("t1 beta cmd=%.3f fd=%.3f kvtx=%.3f shares=%.3f/%.3f r2=%.5f\n",
           beta[GB_F_CMD], beta[GB_F_FD], beta[GB_F_KVTX], s, want, r2);
}

static void t2(void)
{
    GbFit f = { 0 };
    double x[GB_NF], beta[GB_NF];
    for (int i = 0; i < 400; i++) {
        seg(x);
        x[GB_F_FD] = x[GB_F_KILL] = x[GB_F_BLEND] = 0;
        gb_fit_add(&f, x, dot(truth, x));
    }
    int m = gb_fit_solve(&f, beta);
    EXPECT(m == GB_NF - 3, "solved %d columns, want %d", m, GB_NF - 3);
    for (int j = 0; j < GB_NF; j++) {
        if (j == GB_F_FD || j == GB_F_KILL || j == GB_F_BLEND) {
            EXPECT(beta[j] == 0, "beta %s %.4f, want 0", gb_fname[j], beta[j]);
        } else {
            EXPECT(near(beta[j], truth[j], 0.02), "beta %s %.4f, want %.4f",
                   gb_fname[j], beta[j], truth[j]);
        }
    }
    printf("t2 solved=%d beta cmd=%.3f fd=%.3f\n", m, beta[GB_F_CMD], beta[GB_F_FD]);
}

static void t3(void)
{
    GbFit f = { 0 };
    double x[GB_NF], beta[GB_NF];
    for (int i = 0; i < 400; i++) {
        seg(x);
        x[GB_F_ZW] = x[GB_F_FD];
        gb_fit_add(&f, x, dot(truth, x));
    }
    int m = gb_fit_solve(&f, beta);
    double sum = beta[GB_F_FD] + beta[GB_F_ZW];
    double want = truth[GB_F_FD] + truth[GB_F_ZW];
    EXPECT(m == GB_NF, "solved %d", m);
    EXPECT(near(sum, want, 0.02), "fd+zw %.4f, want %.4f", sum, want);
    EXPECT(beta[GB_F_FD] > 0.25 * want && beta[GB_F_FD] < 0.75 * want &&
           beta[GB_F_ZW] > 0.25 * want && beta[GB_F_ZW] < 0.75 * want,
           "fd %.4f zw %.4f, want each about %.1f", beta[GB_F_FD],
           beta[GB_F_ZW], want / 2);
    EXPECT(near(beta[GB_F_CMD], truth[GB_F_CMD], 0.02), "beta cmd %.4f",
           beta[GB_F_CMD]);
    printf("t3 fd=%.3f zw=%.3f sum=%.3f\n", beta[GB_F_FD], beta[GB_F_ZW], sum);
}

static void t4(void)
{
    GbFit f = { 0 };
    double x[GB_NF], beta[GB_NF];
    for (int i = 0; i < 400; i++) {
        seg(x);
        gb_fit_add(&f, x, 100 + (rnd() - 0.5) * 2);
    }
    int m = gb_fit_solve(&f, beta);
    double r2 = m > 0 ? gb_fit_r2(&f, beta) : 1;
    EXPECT(r2 < 0.3, "r2 %.4f on a window the features do not explain", r2);
    printf("t4 r2=%.3f\n", r2);
}

static void t5(void)
{
    double h[GB_HBINS] = { 0 };
    gb_hist_add(h, 2.2, 50);  /* bin 4: 2.0-2.5 us */
    gb_hist_add(h, 10.1, 40); /* bin 20 */
    gb_hist_add(h, 10.4, 10); /* bin 20 */
    gb_hist_add(h, 900, 0);   /* the open bin, no weight */
    double p50 = gb_hist_pct(h, 0.5), p90 = gb_hist_pct(h, 0.9);
    EXPECT(p50 == 2.25, "p50 %.3f, want 2.25 (cumulative 50 of 100 at bin 4)", p50);
    EXPECT(p90 == 10.25, "p90 %.3f, want 10.25", p90);
    printf("t5 p50=%.2f p90=%.2f\n", p50, p90);
}

/* The line: 60 flips, 1000 main-pass commands a flip at 26 us in-pass */
static void t6(void)
{
    static GbWin w;
    double x[GB_NF];
    memset(&w, 0, sizeof(w));
    w.fl = 60;
    w.s = 2.0;
    w.cb = 61;
    w.k = 16;
    w.mp = 60;
    w.mcmd = 60 * 1000;
    w.min_ms = 60 * 26.0;
    w.mout_ms = 60 * 27.3;
    for (int i = 0; i < 60; i++) {
        w.rep[w.nrep++] = 1.05;
        w.drain[w.ndrain++] = 40;
    }
    for (int i = 0; i < 400; i++) {
        seg(x);
        double y = dot(truth, x);
        gb_fit_add(&w.fit, x, y);
        gb_hist_add(w.hist, y / x[GB_F_CMD], x[GB_F_CMD]);
    }
    w.cfmt = 37;
    w.zfmt = 129;
    w.w = 640;
    w.h = 480;
    w.ld[0] = w.ld[1] = w.ld[2] = 0;
    w.st[0] = w.st[1] = 0;
    w.st[2] = 1;
    w.cmd = 60 * 1100;
    w.mhz = 401;
    w.busy = 97;
    char buf[2048];
    size_t n = gb_win_format(&w, buf, sizeof(buf));
    EXPECT(n > 0 && n < sizeof(buf) - 1, "line length %zu", n);
    printf("10-22 22:31:05.123 I/hakuX-gpubrk( 4242): %s\n", buf);
}

int main(int argc, char **argv)
{
    if (argc > 1 && !strcmp(argv[1], "line")) {
        t6();
        return fails ? 1 : 0;
    }
    t1();
    t2();
    t3();
    t4();
    t5();
    printf("fails=%d\n", fails);
    return fails ? 1 : 0;
}
C

cp "$HDR" "$GB/real/gpubrk.h"
# Each mutant reinstates the weaker rule its GB_MUT_* line replaced.
sed '/GB_MUT_ZEROSKIP/s/if (f->a\[j\]\[j\] > 0)/if (1)/' "$HDR" > "$GB/zeroskip/gpubrk.h"
sed '/GB_MUT_RIDGE/s/+= GB_RIDGE \* f->a\[idx\[i\]\]\[idx\[i\]\];/+= 0;/' "$HDR" > "$GB/ridge/gpubrk.h"
sed '/GB_MUT_CENTER/s/= f->yy - f->sy \* f->sy \/ f->n;/= f->yy;/' "$HDR" > "$GB/center/gpubrk.h"
sed '/GB_MUT_PCT/s/cum >= p \* tot/cum > p * tot/' "$HDR" > "$GB/pct/gpubrk.h"
sed 's/ mus=%\.2f muso=%\.2f/ mu=%.2f muso=%.2f/' "$HDR" > "$GB/rename/gpubrk.h"
for v in real zeroskip ridge center pct rename; do
    cc -O0 -Wall -I"$GB/$v" "$GB/gpubrk_test.c" -o "$GB/test-$v" -lm 2> "$GB/cc-$v.log"
done
gb_run() { "$GB/test-$1" > "$GB/run-$1.log" 2>&1; }
gb_line() { "$GB/test-$1" line > "$GB/line-$1.log" 2>&1; }
check "gpubrk_test builds against vk/gpubrk.h with no warning" \
    bash -c 'test -x "$1" && ! test -s "$2"' _ "$GB/test-real" "$GB/cc-real.log"
check "T1-T5: betas, zero columns, a collinear pair, an unexplained window, percentiles" gb_run real
if [ -s "$GB/run-real.log" ]; then sed 's/^/       /' "$GB/run-real.log"; fi

check "T6: gb_win_format writes a line" gb_line real
gb_sum() { python3 "$SUM" "arm=$GB/line-$1.log" > "$GB/sum-$1.log" 2>&1; }
check "T6: gpubrk_sum.py reads the line (exit 0)" gb_sum real
if [ -s "$GB/sum-real.log" ]; then echo "       $(head -c 400 "$GB/sum-real.log")"; fi
gb_has() { grep -q -- "$2" "$GB/sum-$1.log"; }
check "T6: the summary carries the values the window was given" \
    bash -c 'grep -q " mus=26.00 " "$1" && grep -q " muso=27.30 " "$1" && grep -q " mrep=1.05 " "$1" && grep -q " mode=s1 " "$1" && grep -q " mhz=401 " "$1" && grep -q " perfquery=unavailable$" "$1"' \
    _ "$GB/sum-real.log"
printf 'nothing here\n' > "$GB/empty.log"
check "gpubrk_sum.py exits 1 on a capture with no window line" \
    bash -c 'python3 "$1" "$2" > /dev/null 2>&1; [ $? -eq 1 ]' _ "$SUM" "$GB/empty.log"

# ------------------------------------------------------------ falsifications
# A mutant is caught only if it built, ran to its own summary, and failed:
# one that does not compile must not read as one the tests caught.
gb_caught() {
    [ -x "$GB/test-$1" ] || return 1
    ! gb_run "$1" || return 1
    grep -q '^fails=[1-9]' "$GB/run-$1.log"
}
for v in zeroskip ridge center pct; do
    check "falsification ran: the $v mutant differs from gpubrk.h" \
        bash -c '! cmp -s "$1" "$2"' _ "$HDR" "$GB/$v/gpubrk.h"
done
check "FALSIFIED: a fit that keeps never-moving columns fails (T2)" gb_caught zeroskip
check "FALSIFIED: a fit with no ridge fails on a collinear pair (T3)" gb_caught ridge
check "FALSIFIED: an uncentred R^2 passes an unexplained window and fails (T4)" gb_caught center
check "FALSIFIED: a percentile that needs more than p of the weight fails (T5)" gb_caught pct

check "falsification ran: the renamed-field mutant differs from gpubrk.h" \
    bash -c '! cmp -s "$1" "$2"' _ "$HDR" "$GB/rename/gpubrk.h"
check "falsification ran: the renamed-field line was written" gb_line rename
check "FALSIFIED: a line with a field renamed fails gpubrk_sum.py (exit 2)" \
    bash -c 'python3 "$1" "$2" > "$3" 2>&1; [ $? -eq 2 ] && grep -q "lacks mus" "$3"' \
    _ "$SUM" "$GB/line-rename.log" "$GB/sum-rename.log"
