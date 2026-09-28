/*
 * Geforce NV2A PGRAPH GLSL Shader Generator: register-combiner ubershader
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

#include "qemu/osdep.h"
#include "hw/xbox/nv2a/debug.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#include "psh-uber.h"

#ifdef __ANDROID__
#include <android/log.h>
#endif

/*
 * The family template: the smallest combiner program for which psh.c
 * declares both r0 and r1 (it declares a temporary only once a combiner
 * names it) and enables the final combiner, so the text the splice replaces
 * has a fixed shape:
 *
 *   stage 0 rgb: ab = A * B with A = r0, B = r1, written to r0
 *   final:       G = r0.a; A..F zero
 *
 * The values are what psh.c's parser reads: input bytes are reg | chan | map,
 * an output word is cd | ab << 4 | muxsum << 8 | flags << 12.
 */
#define UBER_TPL_COMBINER_CONTROL 0x00000001u
#define UBER_TPL_RGB_INPUTS0 ((uint32_t)PS_REGISTER_R0 << 24 | \
                              (uint32_t)PS_REGISTER_R1 << 16)
#define UBER_TPL_RGB_OUTPUTS0 ((uint32_t)PS_REGISTER_R0 << 4)
#define UBER_TPL_FINAL_INPUTS_1 ((uint32_t)(PS_REGISTER_R0 | \
                                            PS_CHANNEL_ALPHA) << 8)

bool pgraph_glsl_psh_uber_enabled(void)
{
    static int enabled = -1;

    if (enabled < 0) {
        const char *e = getenv("HAKUX_PSH_UBER");
        enabled = e ? (atoi(e) != 0) : HAKUX_PSH_UBER_DEFAULT;
        /*
         * The runtime reader for an arm: a B arm without this line in its
         * log did not run the ubershader, whatever its ref says. Silent on a
         * default build with the variable unset. On Android it goes out
         * under hakuX-perf as well, because a title soak's logcat keeps that
         * tag and drops hakuX-stderr (soak_title.sh's LOGCAT_SPEC).
         */
        if (enabled || e) {
            fprintf(stderr, "psh-uber: %s (HAKUX_PSH_UBER=%s, build default "
                    "%d)\n", enabled ? "ON, forcing the combiner ubershader"
                                     : "off", e ? e : "unset",
                    HAKUX_PSH_UBER_DEFAULT);
#ifdef __ANDROID__
            __android_log_print(ANDROID_LOG_INFO, "hakuX-perf",
                                "psh-uber: %s (HAKUX_PSH_UBER=%s, build "
                                "default %d)", enabled ? "ON" : "off",
                                e ? e : "unset", HAKUX_PSH_UBER_DEFAULT);
#endif
        }
    }
    return enabled;
}

bool pgraph_glsl_psh_uber_covers(const PshState *state)
{
    return state->final_inputs_0 || state->final_inputs_1;
}

static void set_template(PshState *s)
{
    s->combiner_control = UBER_TPL_COMBINER_CONTROL;
    memset(s->rgb_inputs, 0, sizeof(s->rgb_inputs));
    memset(s->rgb_outputs, 0, sizeof(s->rgb_outputs));
    memset(s->alpha_inputs, 0, sizeof(s->alpha_inputs));
    memset(s->alpha_outputs, 0, sizeof(s->alpha_outputs));
    s->rgb_inputs[0] = UBER_TPL_RGB_INPUTS0;
    s->rgb_outputs[0] = UBER_TPL_RGB_OUTPUTS0;
    s->final_inputs_0 = 0;
    s->final_inputs_1 = UBER_TPL_FINAL_INPUTS_1;
}

void pgraph_glsl_psh_uber_family(const PshState *state, PshState *family)
{
    *family = *state;
    set_template(family);
}

bool pgraph_glsl_psh_uber_is_family(const PshState *state)
{
    PshState t = *state;
    set_template(&t);
    return memcmp(&t, state, sizeof(t)) == 0;
}

void pgraph_glsl_psh_uber_comb_values(PGRAPHState *pg,
                                      uint32_t out[PSH_UBER_COMB_VEC4S * 4])
{
    memset(out, 0, PSH_UBER_COMB_VEC4S * 4 * sizeof(uint32_t));

    uint32_t ctl = pgraph_reg_r(pg, NV_PGRAPH_COMBINECTL);
    int num_stages = psh_num_combiner_stages(ctl);
    for (int i = 0; i < num_stages; i++) {
        out[i * 4 + 0] = pgraph_reg_r(pg, NV_PGRAPH_COMBINECOLORI0 + i * 4);
        out[i * 4 + 1] = pgraph_reg_r(pg, NV_PGRAPH_COMBINECOLORO0 + i * 4);
        out[i * 4 + 2] = pgraph_reg_r(pg, NV_PGRAPH_COMBINEALPHAI0 + i * 4);
        out[i * 4 + 3] = pgraph_reg_r(pg, NV_PGRAPH_COMBINEALPHAO0 + i * 4);
    }
    out[8 * 4 + 0] = pgraph_reg_r(pg, NV_PGRAPH_COMBINESPECFOG0);
    out[8 * 4 + 1] = pgraph_reg_r(pg, NV_PGRAPH_COMBINESPECFOG1);
    out[8 * 4 + 2] = ctl;
}

/*
 * The interpreter. Every expression is the text psh.c's get_input_var(),
 * get_output(), add_stage_code() and add_final_stage_code() emit for the same
 * register values, in the same evaluation order:
 *
 *   - a stage computes all of its rgb and alpha results from the registers
 *     as they stood before the stage, then writes rgb (ab, ab's blue-to-
 *     alpha, cd, cd's blue-to-alpha, mux/sum) and then alpha;
 *   - a result is clamp(mapping(x), -1, 1); mux/sum takes the UNMAPPED
 *     products and maps their combination;
 *   - a read-only or reserved destination is not written, a reserved source
 *     reads zero, EF_PROD reads zero outside the final combiner;
 *   - V1R0_SUM reads v1 and r0 as they stand, with the final combiner's
 *     complement and clamp flags, in every stage.
 *
 * SAME VALUES IS NOT ENOUGH; THE EXPRESSIONS MUST HAVE THE SAME SHAPE. The
 * first version computed each product once, chose dot or mul with a select,
 * and mapped the result in a switch. Every op was psh.c's op, and on
 * lavapipe 69 of 548 random programs still came out one ulp away in places,
 * two of them in the 8-bit result: psh.c writes `(a * b) - 0.5` as one
 * expression, which a compiler may contract into one fma, and a select
 * between the multiply and the subtract forbids it. A one-ulp move is a
 * one-LSB move wherever the value sits on a rounding boundary, and the BIAS
 * and HALFBIAS mappings put combiner values on exactly those (k + 0.5)/255
 * boundaries. So a stage half branches (uniformly) on its SHAPE -- which of
 * ab, cd and mux/sum it writes, and whether ab and cd are dot products --
 * and each leaf is add_stage_code()'s text with the operands as variables
 * (gen_half() below). A product's uses, and so what may be contracted, are
 * then the specialised shader's.
 *
 * Only the mapping stays branchless, as ((x - bias) * scale), because that
 * is exact against psh.c's text whatever a compiler contracts: bias is 0.0 or
 * 0.5 and fma(a, b, -0.0) is round(a * b); scale is 1, 2, 4 or 0.5 and
 * scaling by a power of two is exact (to psh.c's own `/ 2.0` too).
 */
static const char uber_glsl_prelude[] =
"vec4 ubV0, ubV1, ubT0, ubT1, ubT2, ubT3, ubR0, ubR1, ubFog;\n"
"vec3 ubE, ubF;\n"
"\n"
"vec4 ubReg(uint reg, uint stage) {\n"
"    uint cc = ubComb[8].z;\n"
"    uint fin = ubComb[8].y;\n"
"    switch (reg) {\n"
"    case 1u: return consts[(stage == 8u || (cc & 0x1000u) != 0u) ? stage * 2u : 0u];\n"
"    case 2u: return consts[(stage == 8u || (cc & 0x10000u) != 0u) ? stage * 2u + 1u : 1u];\n"
"    case 3u: return ubFog;\n"
"    case 4u: return ubV0;\n"
"    case 5u: return ubV1;\n"
"    case 8u: return ubT0;\n"
"    case 9u: return ubT1;\n"
"    case 10u: return ubT2;\n"
"    case 11u: return ubT3;\n"
"    case 12u: return ubR0;\n"
"    case 13u: return ubR1;\n"
"    case 14u:\n"
"        if ((fin & 0x80u) != 0u) {\n"
"            return clamp(vec4(((fin & 0x40u) != 0u ? (1.0 - ubV1) : ubV1).rgb +\n"
"                              ((fin & 0x20u) != 0u ? (1.0 - ubR0) : ubR0).rgb,\n"
"                              0.0), 0.0, 1.0);\n"
"        }\n"
"        return vec4(((fin & 0x40u) != 0u ? (1.0 - ubV1) : ubV1).rgb +\n"
"                    ((fin & 0x20u) != 0u ? (1.0 - ubR0) : ubR0).rgb, 0.0);\n"
"    case 15u: return stage == 8u ? vec4(ubE * ubF, 0.0) : vec4(0.0);\n"
"    default: return vec4(0.0);\n"
"    }\n"
"}\n"
"\n"
"vec3 ubMap3(vec3 x, uint mod) {\n"
"    switch (mod) {\n"
"    case 0x00u: return max(x, 0.0);\n"
"    case 0x20u: return (1.0 - clamp(x, 0.0, 1.0));\n"
"    case 0x40u: return (2.0 * max(x, 0.0) - 1.0);\n"
"    case 0x60u: return (-2.0 * max(x, 0.0) + 1.0);\n"
"    case 0x80u: return (max(x, 0.0) - 0.5);\n"
"    case 0xa0u: return (-max(x, 0.0) + 0.5);\n"
"    case 0xc0u: return x;\n"
"    default: return -x;\n"
"    }\n"
"}\n"
"\n"
"float ubMap1(float x, uint mod) {\n"
"    switch (mod) {\n"
"    case 0x00u: return max(x, 0.0);\n"
"    case 0x20u: return (1.0 - clamp(x, 0.0, 1.0));\n"
"    case 0x40u: return (2.0 * max(x, 0.0) - 1.0);\n"
"    case 0x60u: return (-2.0 * max(x, 0.0) + 1.0);\n"
"    case 0x80u: return (max(x, 0.0) - 0.5);\n"
"    case 0xa0u: return (-max(x, 0.0) + 0.5);\n"
"    case 0xc0u: return x;\n"
"    default: return -x;\n"
"    }\n"
"}\n"
"\n"
/*
 * A dot product whose operands psh.c spells `.aaa` (or reads from the ZERO
 * register) has three equal lanes, and the specialised shader's compiler
 * knows it: after CSE its dot is p + p + p, where this interpreter, choosing
 * .aaa or .rgb at run time, would compute fma(x, y, fma(x, y, p)) -- a
 * different rounding (lavapipe: 422 px of one 4096 px render one LSB off).
 * Handing the compiler vec3(x) gives it the same knowledge.
 */
"float ubDot(vec3 a, vec3 b, bool ar, bool br) {\n"
"    if (ar && br) return dot(vec3(a.x), vec3(b.x));\n"
"    if (ar) return dot(vec3(a.x), b);\n"
"    if (br) return dot(a, vec3(b.x));\n"
"    return dot(a, b);\n"
"}\n"
"\n"
"bool ubRep(uint b) {\n"
"    return (b & 0x10u) != 0u || (b & 0xFu) == 0u;\n"
"}\n"
"\n"
"vec3 ubInRgb(uint b, uint stage) {\n"
"    vec4 r = ubReg(b & 0xFu, stage);\n"
"    return ubMap3((b & 0x10u) != 0u ? r.aaa : r.rgb, b & 0xE0u);\n"
"}\n"
"\n"
"float ubInA(uint b, uint stage) {\n"
"    vec4 r = ubReg(b & 0xFu, stage);\n"
"    return ubMap1((b & 0x10u) != 0u ? r.a : r.b, b & 0xE0u);\n"
"}\n"
"\n"
/* v0, v1, t0-t3, r0, r1: the destinations get_var() does not discard. */
"bool ubWritable(uint reg) {\n"
"    return ((0x3F30u >> reg) & 1u) != 0u;\n"
"}\n"
"\n"
"void ubWriteRgb(uint reg, vec3 v) {\n"
"    switch (reg) {\n"
"    case 4u: ubV0.rgb = v; break;\n"
"    case 5u: ubV1.rgb = v; break;\n"
"    case 8u: ubT0.rgb = v; break;\n"
"    case 9u: ubT1.rgb = v; break;\n"
"    case 10u: ubT2.rgb = v; break;\n"
"    case 11u: ubT3.rgb = v; break;\n"
"    case 12u: ubR0.rgb = v; break;\n"
"    case 13u: ubR1.rgb = v; break;\n"
"    default: break;\n"
"    }\n"
"}\n"
"\n"
"void ubWriteA(uint reg, float v) {\n"
"    switch (reg) {\n"
"    case 4u: ubV0.a = v; break;\n"
"    case 5u: ubV1.a = v; break;\n"
"    case 8u: ubT0.a = v; break;\n"
"    case 9u: ubT1.a = v; break;\n"
"    case 10u: ubT2.a = v; break;\n"
"    case 11u: ubT3.a = v; break;\n"
"    case 12u: ubR0.a = v; break;\n"
"    case 13u: ubR1.a = v; break;\n"
"    default: break;\n"
"    }\n"
"}\n"
"\n";

static const char uber_glsl_run[] =
"vec4 ubRun() {\n"
"    uint n = min(ubComb[8].z & 0xFFu, 8u);\n"
"    for (uint s = 0u; s < n; s++) {\n"
"        ubStage(s);\n"
"    }\n"
"    uint f0 = ubComb[8].x, f1 = ubComb[8].y;\n"
"    ubE = ubInRgb(f1 >> 24, 8u);\n"
"    ubF = ubInRgb((f1 >> 16) & 0xFFu, 8u);\n"
"    vec3 fa = ubInRgb(f0 >> 24, 8u);\n"
"    vec3 fb = ubInRgb((f0 >> 16) & 0xFFu, 8u);\n"
"    vec3 fc = ubInRgb((f0 >> 8) & 0xFFu, 8u);\n"
"    vec3 fd = ubInRgb(f0 & 0xFFu, 8u);\n"
"    float fg = ubInA((f1 >> 8) & 0xFFu, 8u);\n"
"    return vec4(fd + mix(vec3(fc), vec3(fb), vec3(fa)), fg);\n"
"}\n"
"\n";

/*
 * One leaf of a stage half: add_stage_code()'s compute lines for one shape,
 * operands a, b, c, d (vec3 for rgb, float for alpha), results into the
 * half's O-variables. The mapping is "((x - bias) * sc)"; see above.
 */
static void gen_leaf(MString *o, const char *p, bool rgb, int ms, bool ab_w,
                     bool cd_w, bool ab_dot, bool cd_dot, const char *ind)
{
    const char *cast = rgb ? "vec3" : "";
    char ab[64], cd[64];
    if (rgb) {
        snprintf(ab, sizeof(ab), ab_dot ? "ubDot(ra, rb, raRep, rbRep)"
                                        : "(ra * rb)");
        snprintf(cd, sizeof(cd), cd_dot ? "ubDot(rc, rd, rcRep, rdRep)"
                                        : "(rc * rd)");
    } else {
        snprintf(ab, sizeof(ab), ab_dot ? "dot(aa, ab)" : "(aa * ab)");
        snprintf(cd, sizeof(cd), cd_dot ? "dot(ac, ad)" : "(ac * ad)");
    }

    if (ab_w) {
        mstring_append_fmt(o, "%s%sabO = clamp(%s(((%s - %sbias) * %ssc)), "
                           "-1.0, 1.0);\n", ind, p, cast, ab, p, p);
    }
    if (cd_w) {
        mstring_append_fmt(o, "%s%scdO = clamp(%s(((%s - %sbias) * %ssc)), "
                           "-1.0, 1.0);\n", ind, p, cast, cd, p, p);
    }
    if (ms == 1) {
        mstring_append_fmt(o, "%s%smsO = clamp(%s((((%s + %s) - %sbias) * "
                           "%ssc)), -1.0, 1.0);\n", ind, p, cast, ab, cd, p, p);
    } else if (ms == 2) {
        char sel[160];
        snprintf(sel, sizeof(sel), "((muxCd) ? %s(%s) : %s(%s))", cast, cd,
                 cast, ab);
        mstring_append_fmt(o, "%s%smsO = clamp(%s(((%s - %sbias) * %ssc)), "
                           "-1.0, 1.0);\n", ind, p, cast, sel, p, p);
    }
}

/* The shape tree for one stage half: mux/sum kind, then which of ab and cd
 * are written, then (where a product is used at all) dot or mul. */
static void gen_half(MString *o, bool rgb)
{
    const char *p = rgb ? "r" : "a";
    for (int ms = 0; ms < 3; ms++) {
        mstring_append_fmt(o, "    %sif (%sms == %du) {\n",
                           ms ? "} else " : "", p, ms);
        for (int w = 0; w < 4; w++) {
            bool ab_w = w & 1, cd_w = w & 2;
            bool ab_used = ab_w || ms, cd_used = cd_w || ms;
            if (!ab_used && !cd_used) {
                continue;
            }
            mstring_append_fmt(o, "        if (%sabW == %s && %scdW == %s) {\n",
                               p, ab_w ? "true" : "false", p,
                               cd_w ? "true" : "false");
            for (int d = 0; d < 4; d++) {
                bool ab_dot = d & 1, cd_dot = d & 2;
                if ((ab_dot && !ab_used) || (cd_dot && !cd_used)) {
                    continue;
                }
                /* Test a dot flag only where its product is used. */
                GString *cond = g_string_new("");
                if (ab_used) {
                    g_string_append_printf(cond, "%sabDot == %s", p,
                                           ab_dot ? "true" : "false");
                }
                if (cd_used) {
                    g_string_append_printf(cond, "%s%scdDot == %s",
                                           ab_used ? " && " : "", p,
                                           cd_dot ? "true" : "false");
                }
                mstring_append_fmt(o, "            if (%s) {\n", cond->str);
                g_string_free(cond, true);
                gen_leaf(o, p, rgb, ms, ab_w, cd_w, ab_dot, cd_dot,
                         "                ");
                mstring_append(o, "            }\n");
            }
            mstring_append(o, "        }\n");
        }
    }
    mstring_append(o, "    }\n");
}

static void gen_stage_fn(MString *o)
{
    mstring_append(o,
"void ubStage(uint s) {\n"
"    uvec4 w = ubComb[s];\n"
"    bool muxCd = (ubComb[8].z & 0x100u) != 0u\n"
"                     ? ubR0.a >= 0.5\n"
"                     : (uint(ubR0.a * 255.0) & 1u) == 1u;\n"
"\n"
"    uint ro = w.y, rf = ro >> 12;\n"
"    uint rAb = (ro >> 4) & 0xFu, rCd = ro & 0xFu, rMs = (ro >> 8) & 0xFu;\n"
"    bool rabW = ubWritable(rAb), rcdW = ubWritable(rCd);\n"
"    uint rms = ubWritable(rMs) ? ((rf & 4u) != 0u ? 2u : 1u) : 0u;\n"
"    bool rabDot = (rf & 2u) != 0u, rcdDot = (rf & 1u) != 0u;\n"
"    float rbias = (rf & 8u) != 0u ? 0.5 : 0.0;\n"
"    float rsc = ((rf >> 4) & 3u) == 0u ? 1.0 : ((rf >> 4) & 3u) == 1u ? 2.0\n"
"              : ((rf >> 4) & 3u) == 2u ? 4.0 : 0.5;\n"
"    vec3 ra = ubInRgb(w.x >> 24, s);\n"
"    vec3 rb = ubInRgb((w.x >> 16) & 0xFFu, s);\n"
"    vec3 rc = ubInRgb((w.x >> 8) & 0xFFu, s);\n"
"    vec3 rd = ubInRgb(w.x & 0xFFu, s);\n"
"    bool raRep = ubRep(w.x >> 24), rbRep = ubRep((w.x >> 16) & 0xFFu);\n"
"    bool rcRep = ubRep((w.x >> 8) & 0xFFu), rdRep = ubRep(w.x & 0xFFu);\n"
"    vec3 rabO = vec3(0.0), rcdO = vec3(0.0), rmsO = vec3(0.0);\n"
"\n"
"    uint ao = w.w, af = ao >> 12;\n"
"    uint aAb = (ao >> 4) & 0xFu, aCd = ao & 0xFu, aMs = (ao >> 8) & 0xFu;\n"
"    bool aabW = ubWritable(aAb), acdW = ubWritable(aCd);\n"
"    uint ams = ubWritable(aMs) ? ((af & 4u) != 0u ? 2u : 1u) : 0u;\n"
"    bool aabDot = (af & 2u) != 0u, acdDot = (af & 1u) != 0u;\n"
"    float abias = (af & 8u) != 0u ? 0.5 : 0.0;\n"
"    float asc = ((af >> 4) & 3u) == 0u ? 1.0 : ((af >> 4) & 3u) == 1u ? 2.0\n"
"              : ((af >> 4) & 3u) == 2u ? 4.0 : 0.5;\n"
"    float aa = ubInA(w.z >> 24, s);\n"
"    float ab = ubInA((w.z >> 16) & 0xFFu, s);\n"
"    float ac = ubInA((w.z >> 8) & 0xFFu, s);\n"
"    float ad = ubInA(w.z & 0xFFu, s);\n"
"    float aabO = 0.0, acdO = 0.0, amsO = 0.0;\n"
"\n");
    gen_half(o, true);
    gen_half(o, false);
    mstring_append(o,
"\n"
"    if (rabW) {\n"
"        ubWriteRgb(rAb, rabO);\n"
"        if ((rf & 0x80u) != 0u) ubWriteA(rAb, rabO.b);\n"
"    }\n"
"    if (rcdW) {\n"
"        ubWriteRgb(rCd, rcdO);\n"
"        if ((rf & 0x40u) != 0u) ubWriteA(rCd, rcdO.b);\n"
"    }\n"
"    if (rms != 0u) ubWriteRgb(rMs, rmsO);\n"
"    if (aabW) ubWriteA(aAb, aabO);\n"
"    if (acdW) ubWriteA(aCd, acdO);\n"
"    if (ams != 0u) ubWriteA(aMs, amsO);\n"
"}\n"
"\n");
}

static const char uber_glsl_call[] =
"// Combiner ubershader (#569 P6)\n"
"ubV0 = v0; ubV1 = v1;\n"
"ubT0 = t0; ubT1 = t1; ubT2 = t2; ubT3 = t3;\n"
"ubR0 = r0; ubR1 = r1; ubFog = pFog;\n"
"{\n"
"    vec4 ubOut = ubRun();\n"
"    fragColor.rgb = ubOut.rgb;\n"
"    fragColor.a = ubOut.a;\n"
"}\n";

MString *pgraph_glsl_gen_psh_uber(const PshState *family,
                                  GenPshGlslOptions opts)
{
    if (!opts.vulkan || !pgraph_glsl_psh_uber_is_family(family)) {
        return NULL;
    }

    MString *tpl = pgraph_glsl_gen_psh(family, opts);
    const char *s = mstring_get_str(tpl);

    /* The uniform block's close, the combiner block, and main's opening. */
    const char *block = strstr(s, "uniform PshUniforms {\n");
    const char *block_end = block ? strstr(block, "};\n") : NULL;
    const char *main_fn = strstr(s, "void main() {\n");
    const char *comb = strstr(s, "// Stage 0\n");
    const char *fin = comb ? strstr(comb, "// Final Combiner\n") : NULL;
    const char *fin_a = fin ? strstr(fin, "fragColor.a = ") : NULL;
    const char *comb_end = fin_a ? strchr(fin_a, '\n') : NULL;

    const char *next_stage = comb ? strstr(comb + 1, "// Stage ") : NULL;

    if (!block_end || !main_fn || !comb || !comb_end ||
        !(block_end < main_fn && main_fn < comb) ||
        (next_stage && next_stage < comb_end)) {
        fprintf(stderr, "psh-uber: template shader has an unexpected shape; "
                        "keeping the specialised path\n");
        mstring_unref(tpl);
        return NULL;
    }
    comb_end++;

    MString *out = mstring_new();
    g_string_append_len(out->gstr, s, block_end - s);
    mstring_append_fmt(out, "uvec4 %s[%d];\n", PSH_UBER_COMB_NAME,
                       PSH_UBER_COMB_VEC4S);
    g_string_append_len(out->gstr, block_end, main_fn - block_end);
    mstring_append(out, uber_glsl_prelude);
    gen_stage_fn(out);
    mstring_append(out, uber_glsl_run);
    g_string_append_len(out->gstr, main_fn, comb - main_fn);
    mstring_append(out, uber_glsl_call);
    mstring_append(out, comb_end);

    mstring_unref(tpl);
    return out;
}
