/*
 * Geforce NV2A PGRAPH Vulkan Renderer: main-pass GPU breakdown (#433)
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

/*
 * The arithmetic behind draw.c's hakuX-gpubrk line (lane gpubreak1022): the
 * per-window least-squares fit of a segment's GPU time against what its draws
 * carried, the us-per-draw histogram, the render-mode reading of out/in, and
 * the line's formatter. draw.c records the stamps and features; everything
 * that turns them into numbers is here.
 *
 * Standalone (no qemu or Vulkan headers) so the selftest can build it on its
 * own: docs/testing/jobs/selftest.d/99-gpubrk-fit.sh. The GB_MUT_* comments
 * mark the lines its mutants rewrite; keep each on one line.
 */

#ifndef HW_XBOX_NV2A_PGRAPH_VK_GPUBRK_H
#define HW_XBOX_NV2A_PGRAPH_VK_GPUBRK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/*
 * A segment's features, each summed over the segment's GPU draw commands
 * (one vkCmdDraw*, or one entry of an indirect draw):
 *   cmd   draw commands
 *   pchg  pipeline binds that changed the bound VkPipeline (once per bind)
 *   fd    commands whose fragment shader writes gl_FragDepth (psh depth_needed)
 *   kill  commands with alpha test or alpha kill (discard)
 *   blend commands with NV_PGRAPH_BLEND_EN
 *   zw    commands with depth test and depth write on
 *   tex   texture stages the commands' shader samples (0-4 each)
 *   dtx   texture descriptor pushes or binds
 *   kvtx  vertices or indices fetched, in thousands
 *   ukb   uniform bytes uploaded, in KiB
 * No intercept: a segment's time is the sum of its draws' costs, and the
 * stamp's own cost rides on cmd (one stamp per K commands).
 */
enum {
    GB_F_CMD,
    GB_F_PCHG,
    GB_F_FD,
    GB_F_KILL,
    GB_F_BLEND,
    GB_F_ZW,
    GB_F_TEX,
    GB_F_DTX,
    GB_F_KVTX,
    GB_F_UKB,
    GB_NF
};

static const char *const gb_fname[GB_NF] = {
    "cmd", "pchg", "fd", "kill", "blend", "zw", "tex", "dtx", "kvtx", "ukb",
};

/* Relative ridge: a column's own diagonal times this. Splits an exactly
 * collinear pair evenly instead of failing (fd and zw move together in many
 * windows). Small, because every feature scales with cmd and that collinearity
 * magnifies the ridge's bias on the small columns: 1e-4 put ukb 3% off in the
 * selftest's noise-free window, 1e-6 keeps every beta within 0.1%. */
#define GB_RIDGE 1e-6

typedef struct GbFit {
    double a[GB_NF][GB_NF]; /* sum of x x^T */
    double b[GB_NF];        /* sum of x y */
    double sx[GB_NF];       /* sum of x */
    double yy, sy;          /* sum of y^2, sum of y */
    uint32_t n;
} GbFit;

static inline void gb_fit_add(GbFit *f, const double *x, double y)
{
    for (int j = 0; j < GB_NF; j++) {
        if (x[j] == 0) {
            continue;
        }
        for (int k = 0; k < GB_NF; k++) {
            f->a[j][k] += x[j] * x[k];
        }
        f->b[j] += x[j] * y;
        f->sx[j] += x[j];
    }
    f->yy += y * y;
    f->sy += y;
    f->n++;
}

static inline double gb_abs(double v)
{
    return v < 0 ? -v : v;
}

/*
 * (A + ridge diag(A)) beta = b over the columns that ever moved. A column
 * that is zero in every segment gets beta 0 and stays out of the system.
 * Returns the number of columns solved, or -1 on a zero pivot.
 */
static inline int gb_fit_solve(const GbFit *f, double *beta)
{
    int idx[GB_NF], m = 0;
    double M[GB_NF][GB_NF + 1], x[GB_NF];

    for (int j = 0; j < GB_NF; j++) {
        beta[j] = 0;
        if (f->a[j][j] > 0) { /* GB_MUT_ZEROSKIP */
            idx[m++] = j;
        }
    }
    for (int i = 0; i < m; i++) {
        for (int k = 0; k < m; k++) {
            M[i][k] = f->a[idx[i]][idx[k]];
        }
        M[i][i] += GB_RIDGE * f->a[idx[i]][idx[i]]; /* GB_MUT_RIDGE */
        M[i][m] = f->b[idx[i]];
    }
    for (int c = 0; c < m; c++) {
        int p = c;
        for (int i = c + 1; i < m; i++) {
            if (gb_abs(M[i][c]) > gb_abs(M[p][c])) {
                p = i;
            }
        }
        if (M[p][c] == 0) {
            return -1;
        }
        if (p != c) {
            for (int k = 0; k <= m; k++) {
                double t = M[c][k];
                M[c][k] = M[p][k];
                M[p][k] = t;
            }
        }
        for (int i = c + 1; i < m; i++) {
            double r = M[i][c] / M[c][c];
            for (int k = c; k <= m; k++) {
                M[i][k] -= r * M[c][k];
            }
        }
    }
    for (int i = m - 1; i >= 0; i--) {
        double s = M[i][m];
        for (int k = i + 1; k < m; k++) {
            s -= M[i][k] * x[k];
        }
        x[i] = s / M[i][i];
    }
    for (int i = 0; i < m; i++) {
        beta[idx[i]] = x[i];
    }
    return m;
}

/* Centred R^2 of beta on the un-ridged sums: 1 - SSE / sum (y - mean)^2 */
static inline double gb_fit_r2(const GbFit *f, const double *beta)
{
    if (f->n < 2) {
        return 0;
    }
    double sse = f->yy;
    for (int j = 0; j < GB_NF; j++) {
        sse -= 2 * beta[j] * f->b[j];
        for (int k = 0; k < GB_NF; k++) {
            sse += beta[j] * f->a[j][k] * beta[k];
        }
    }
    double syy = f->yy - f->sy * f->sy / f->n; /* GB_MUT_CENTER */
    if (syy <= 0) {
        return 0;
    }
    return 1 - sse / syy;
}

/*
 * share[j]: feature j's part of the time per draw command, beta_j times its
 * total over the total commands. fx[j]: the feature's mean per command. A
 * feature whose fx sits at 0 or 1 in every segment cannot be told from cmd.
 */
static inline void gb_fit_shares(const GbFit *f, const double *beta,
                                 double *share, double *fx)
{
    double nc = f->sx[GB_F_CMD];
    for (int j = 0; j < GB_NF; j++) {
        share[j] = nc > 0 ? beta[j] * f->sx[j] / nc : 0;
        fx[j] = nc > 0 ? f->sx[j] / nc : 0;
    }
}

/* us per draw command, 0.5 us bins, the last bin open-ended */
#define GB_HBINS 256
#define GB_HBIN_US 0.5

static inline void gb_hist_add(double *h, double us_per_cmd, double w)
{
    int b = (int)(us_per_cmd / GB_HBIN_US);
    if (b < 0) {
        b = 0;
    }
    if (b >= GB_HBINS) {
        b = GB_HBINS - 1;
    }
    h[b] += w;
}

/* The first bin whose cumulative weight reaches p of the total, as its middle */
static inline double gb_hist_pct(const double *h, double p)
{
    double tot = 0, cum = 0;
    for (int i = 0; i < GB_HBINS; i++) {
        tot += h[i];
    }
    if (tot <= 0) {
        return 0;
    }
    for (int i = 0; i < GB_HBINS; i++) {
        cum += h[i];
        if (cum >= p * tot) { /* GB_MUT_PCT */
            return (i + 0.5) * GB_HBIN_US;
        }
    }
    return (GB_HBINS - 0.5) * GB_HBIN_US;
}

/* Median of v[0..n), sorting v in place */
static inline double gb_median(double *v, int n)
{
    if (n <= 0) {
        return 0;
    }
    for (int i = 1; i < n; i++) {
        double t = v[i];
        int j = i - 1;
        while (j >= 0 && v[j] > t) {
            v[j + 1] = v[j];
            j--;
        }
        v[j + 1] = t;
    }
    return n & 1 ? v[n / 2] : (v[n / 2 - 1] + v[n / 2]) / 2;
}

/*
 * The render mode out/in implies. A stamp inside a GMEM pass is replayed in
 * every tile and the last tile's value lands, while the stamps outside the
 * pass bracket binning, every tile and the loads and stores: so out/in is
 * about 1 for sysmem or one tile and about n for n even tiles. 's' cannot
 * tell sysmem from one tile; only a u_trace or TU_DEBUG arm can.
 */
static inline char gb_rep_mode(double rep)
{
    if (rep <= 0) {
        return '-';
    }
    if (rep < 1.3) {
        return 's';
    }
    if (rep < 1.6) {
        return 'u';
    }
    return 't';
}

/* VkAttachmentLoadOp / VkAttachmentStoreOp as one letter */
static inline char gb_load_ch(uint32_t op)
{
    return op == 0 ? 'L' : op == 1 ? 'C' : op == 2 ? 'D' : '?';
}

static inline char gb_store_ch(uint32_t op)
{
    return op == 0 ? 'S' : op == 1 ? 'D' : '?';
}

#define GB_REP_MAX 1024
#define GB_KG_MAX 24

/* One window's sums; gb_win_format turns them into the line, per flip */
typedef struct GbWin {
    uint32_t fl, cb, k, wfi;
    double s;
    /* M: the passes on the frame's largest depth surface */
    uint32_t mp;
    double mcmd, min_ms, mout_ms;
    double rep[GB_REP_MAX];
    uint32_t nrep;
    double drain[GB_REP_MAX];
    uint32_t ndrain;
    /* O: every other pass that went through begin_render_pass */
    uint32_t op;
    double ocmd, oin_ms, oout_ms;
    GbFit fit;
    double hist[GB_HBINS];
    /* the window's largest M pass */
    uint32_t cfmt, zfmt, w, h;
    uint32_t ld[3], st[3];
    /* M passes whose begin_state asked for LOAD (colour, zeta) */
    uint32_t mreqc, mreqz;
    /* host-side counts */
    uint64_t pbind, pchg, dub, dtx, push_b, ubo_b, nv, cmd;
    int mhz, busy;
    uint32_t drop;
    int kg_state; /* 0 off, -errno on failure, else counters read */
    const char *kg_name[GB_KG_MAX];
    double kg_val[GB_KG_MAX];
    int pq; /* VK_KHR_performance_query exposed */
} GbWin;

#define GB_PUT(...)                                                    \
    do {                                                               \
        int n_ = snprintf(buf + o, o < cap ? cap - o : 0, __VA_ARGS__); \
        if (n_ > 0) {                                                  \
            o += (size_t)n_;                                           \
        }                                                              \
    } while (0)

/* The line, without the tag. Returns the length written (truncated at cap). */
static inline size_t gb_win_format(GbWin *w, char *buf, size_t cap)
{
    size_t o = 0;
    double fl = w->fl ? w->fl : 1;
    double beta[GB_NF], share[GB_NF], fx[GB_NF];
    int solved = gb_fit_solve(&w->fit, beta);
    double r2 = solved > 0 ? gb_fit_r2(&w->fit, beta) : 0;
    double mrep = w->min_ms > 0 ? w->mout_ms / w->min_ms : 0;
    double repmax = 0;

    if (solved < 0) {
        memset(beta, 0, sizeof(beta));
    }
    gb_fit_shares(&w->fit, beta, share, fx);
    for (uint32_t i = 0; i < w->nrep; i++) {
        repmax = w->rep[i] > repmax ? w->rep[i] : repmax;
    }

    GB_PUT("fl=%u s=%.2f cb=%u K=%u wfi=%u", w->fl, w->s, w->cb, w->k, w->wfi);
    GB_PUT(" mp=%.2f mcmd=%.0f min=%.2f mout=%.2f mrep=%.2f mrepmed=%.2f"
           " mrepmax=%.2f mode=%c",
           w->mp / fl, w->mcmd / fl, w->min_ms / fl, w->mout_ms / fl, mrep,
           gb_median(w->rep, (int)w->nrep), repmax, gb_rep_mode(mrep));
    GB_PUT(" mus=%.2f muso=%.2f p50=%.2f p90=%.2f drain=%.1f",
           w->mcmd > 0 ? w->min_ms * 1000 / w->mcmd : 0,
           w->mcmd > 0 ? w->mout_ms * 1000 / w->mcmd : 0,
           gb_hist_pct(w->hist, 0.5), gb_hist_pct(w->hist, 0.9),
           gb_median(w->drain, (int)w->ndrain));
    GB_PUT(" op=%.2f ocmd=%.0f oin=%.2f oout=%.2f", w->op / fl, w->ocmd / fl,
           w->oin_ms / fl, w->oout_ms / fl);
    GB_PUT(" fn=%u r2=%.3f fit=%s", w->fit.n, r2,
           solved < 0 ? "sing" : w->fit.n < 4 * GB_NF ? "few" : "ok");
    GB_PUT(" b=");
    for (int j = 0; j < GB_NF; j++) {
        GB_PUT("%s%s:%.3f", j ? "," : "", gb_fname[j], beta[j]);
    }
    GB_PUT(" sh=");
    for (int j = 0; j < GB_NF; j++) {
        GB_PUT("%s%s:%.3f", j ? "," : "", gb_fname[j], share[j]);
    }
    GB_PUT(" fx=");
    for (int j = 0; j < GB_NF; j++) {
        GB_PUT("%s%s:%.3f", j ? "," : "", gb_fname[j], fx[j]);
    }
    GB_PUT(" fmt=c%u/z%u wh=%ux%u ld=c%c/z%c/s%c st=c%c/z%c/s%c"
           " mreqc=%u/%u mreqz=%u/%u",
           w->cfmt, w->zfmt, w->w, w->h, gb_load_ch(w->ld[0]),
           gb_load_ch(w->ld[1]), gb_load_ch(w->ld[2]), gb_store_ch(w->st[0]),
           gb_store_ch(w->st[1]), gb_store_ch(w->st[2]), w->mreqc, w->mp,
           w->mreqz, w->mp);
    GB_PUT(" pbind=%.1f pchg=%.1f dub=%.1f dtx=%.1f pushB=%.0f uboK=%.1f"
           " nvK=%.1f cmd=%.1f",
           w->pbind / fl, w->pchg / fl, w->dub / fl, w->dtx / fl,
           w->push_b / fl, w->ubo_b / 1024.0 / fl, w->nv / 1000.0 / fl,
           w->cmd / fl);
    GB_PUT(" mhz=%d busy=%d drop=%u kg=", w->mhz, w->busy, w->drop);
    if (w->kg_state == 0) {
        GB_PUT("off");
    } else if (w->kg_state < 0) {
        GB_PUT("err%d", -w->kg_state);
    } else {
        for (int i = 0; i < w->kg_state && i < GB_KG_MAX; i++) {
            GB_PUT("%s%s:%.1f", i ? "," : "", w->kg_name[i],
                   w->kg_val[i] / 1000.0 / fl);
        }
    }
    GB_PUT(" perfquery=%s", w->pq ? "exposed" : "unavailable");
    return o < cap ? o : (cap ? cap - 1 : 0);
}

#undef GB_PUT

#endif
