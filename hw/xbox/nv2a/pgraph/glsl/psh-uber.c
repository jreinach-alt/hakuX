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
 * The interpreter. It computes what psh.c's get_input_var(), get_output(),
 * add_stage_code() and add_final_stage_code() emit for the same register
 * values, in the same order:
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
 * WHY IT IS BUILT FOR FEW BRANCHES (C leg, docs/lanes/uberspike569 NOTES 5):
 * Turnip's compile time is set by control flow, not arithmetic. The first
 * two designs read and wrote registers through 16-way switches and chose
 * mappings by switch; inlined eight times per stage they took 4.3-4.9 s
 * (one straight-line stage body) and 7.8-9.8 s (a stage branched on its
 * shape) of host Turnip for the fragment stage alone, against 19-24 ms for
 * the specialised shader. Here the register file is an array indexed by the
 * register code (ir3 addresses it relatively), and both mappings are
 * arithmetic: 292-345 ms.
 *
 * The arithmetic is exact against psh.c's text for every value, whatever a
 * compiler contracts:
 *   - input mapping as base * k + o, where base is max(x, 0), clamp(x, 0, 1)
 *     or x and (k, o) is (1, 0), (-1, 1), (2, -1), (-2, 1), (1, -0.5),
 *     (-1, 0.5), (1, 0), (-1, 0): multiplying by +-1 or +-2 is exact, so each
 *     is one rounding of the same sum psh.c writes;
 *   - output mapping as (x - bias) * scale, with bias 0 or 0.5 and scale 1,
 *     2, 4 or 0.5: fma(a, b, -0.0) is round(a * b) and scaling by a power of
 *     two is exact.
 * What it cannot match is the specialised compiler's knowledge: psh.c's
 * shader has compile-time constants (ZERO-register inputs, pFog with fog
 * off) and CSE-visible equalities (.aaa lanes, one register read twice) that
 * license NIR's inexact rewrites -- reassociation above all. On lavapipe
 * that leaves one-ulp differences, a few of them on an 8-bit rounding
 * boundary (NOTES 4.1). The fix for that is exact arithmetic on both paths,
 * not more interpreter.
 */
static const char uber_glsl_prelude[] =
"vec4 ubV0, ubV1, ubT0, ubT1, ubT2, ubT3, ubR0, ubR1, ubFog;\n"
"vec3 ubE, ubF;\n"
"vec4 ubRf[16];\n"
"const float ubMapK[8] = float[](1.0, -1.0, 2.0, -2.0, 1.0, -1.0, 1.0, -1.0);\n"
"const float ubMapO[8] = float[](0.0, 1.0, -1.0, 1.0, -0.5, 0.5, 0.0, 0.0);\n"
"const float ubScale[4] = float[](1.0, 2.0, 4.0, 0.5);\n"
"\n"
/* v0, v1, t0-t3, r0, r1: the destinations get_var() does not discard. An
 * unwritable one is sent to slot 6, a reserved register that reads zero and
 * is zeroed again after every stage's writes. */
"uint ubDest(uint reg) {\n"
"    return ((0x3F30u >> reg) & 1u) != 0u ? reg : 6u;\n"
"}\n"
"\n"
"vec3 ubIn3(uint b) {\n"
"    vec4 r = ubRf[b & 0xFu];\n"
"    vec3 x = (b & 0x10u) != 0u ? r.aaa : r.rgb;\n"
"    uint m = (b >> 5) & 7u;\n"
"    vec3 base = m == 1u ? clamp(x, 0.0, 1.0) : (m >= 6u ? x : max(x, 0.0));\n"
"    return base * ubMapK[m] + ubMapO[m];\n"
"}\n"
"\n"
"float ubIn1(uint b) {\n"
"    vec4 r = ubRf[b & 0xFu];\n"
"    float x = (b & 0x10u) != 0u ? r.a : r.b;\n"
"    uint m = (b >> 5) & 7u;\n"
"    float base = m == 1u ? clamp(x, 0.0, 1.0) : (m >= 6u ? x : max(x, 0.0));\n"
"    return base * ubMapK[m] + ubMapO[m];\n"
"}\n"
"\n"
/* The registers that are functions of the stage or of other registers:
 * c0/c1 (per stage under UNIQUE_C0/C1, stage 8 always its own), V1R0_SUM
 * from v1 and r0 as they stand, and EF_PROD, defined only in the final
 * combiner. */
"void ubLoad(uint s) {\n"
"    uint cc = ubComb[8].z, fin = ubComb[8].y;\n"
"    ubRf[1] = consts[(s == 8u || (cc & 0x1000u) != 0u) ? s * 2u : 0u];\n"
"    ubRf[2] = consts[(s == 8u || (cc & 0x10000u) != 0u) ? s * 2u + 1u : 1u];\n"
"    vec3 v1 = (fin & 0x40u) != 0u ? (1.0 - ubRf[5]).rgb : ubRf[5].rgb;\n"
"    vec3 r0 = (fin & 0x20u) != 0u ? (1.0 - ubRf[12]).rgb : ubRf[12].rgb;\n"
"    ubRf[14] = (fin & 0x80u) != 0u ? clamp(vec4(v1 + r0, 0.0), 0.0, 1.0)\n"
"                                   : vec4(v1 + r0, 0.0);\n"
"    ubRf[15] = s == 8u ? vec4(ubE * ubF, 0.0) : vec4(0.0);\n"
"}\n"
"\n"
"void ubStage(uint s) {\n"
"    ubLoad(s);\n"
"    uvec4 w = ubComb[s];\n"
"    bool muxCd = (ubComb[8].z & 0x100u) != 0u\n"
"                     ? ubRf[12].a >= 0.5\n"
"                     : (uint(ubRf[12].a * 255.0) & 1u) == 1u;\n"
"    uint rf = w.y >> 12, af = w.w >> 12;\n"
"    float rbias = (rf & 8u) != 0u ? 0.5 : 0.0;\n"
"    float abias = (af & 8u) != 0u ? 0.5 : 0.0;\n"
"    float rsc = ubScale[(rf >> 4) & 3u], asc = ubScale[(af >> 4) & 3u];\n"
"\n"
"    vec3 ra = ubIn3(w.x >> 24), rb = ubIn3((w.x >> 16) & 0xFFu);\n"
"    vec3 rc = ubIn3((w.x >> 8) & 0xFFu), rd = ubIn3(w.x & 0xFFu);\n"
"    vec3 rab = (rf & 2u) != 0u ? vec3(dot(ra, rb)) : ra * rb;\n"
"    vec3 rcd = (rf & 1u) != 0u ? vec3(dot(rc, rd)) : rc * rd;\n"
"    vec3 rms = (rf & 4u) != 0u ? (muxCd ? rcd : rab) : rab + rcd;\n"
"    float aa = ubIn1(w.z >> 24), ab = ubIn1((w.z >> 16) & 0xFFu);\n"
"    float ac = ubIn1((w.z >> 8) & 0xFFu), ad = ubIn1(w.z & 0xFFu);\n"
"    float aab = aa * ab, acd = ac * ad;\n"
"    float ams = (af & 4u) != 0u ? (muxCd ? acd : aab) : aab + acd;\n"
"\n"
"    vec3 rabO = clamp((rab - rbias) * rsc, -1.0, 1.0);\n"
"    vec3 rcdO = clamp((rcd - rbias) * rsc, -1.0, 1.0);\n"
"    vec3 rmsO = clamp((rms - rbias) * rsc, -1.0, 1.0);\n"
"    float aabO = clamp((aab - abias) * asc, -1.0, 1.0);\n"
"    float acdO = clamp((acd - abias) * asc, -1.0, 1.0);\n"
"    float amsO = clamp((ams - abias) * asc, -1.0, 1.0);\n"
"\n"
"    uint rAb = ubDest((w.y >> 4) & 0xFu), rCd = ubDest(w.y & 0xFu);\n"
"    uint rMs = ubDest((w.y >> 8) & 0xFu);\n"
"    uint aAb = ubDest((w.w >> 4) & 0xFu), aCd = ubDest(w.w & 0xFu);\n"
"    uint aMs = ubDest((w.w >> 8) & 0xFu);\n"
"    ubRf[rAb].rgb = rabO;\n"
"    if ((rf & 0x80u) != 0u) ubRf[rAb].a = rabO.b;\n"
"    ubRf[rCd].rgb = rcdO;\n"
"    if ((rf & 0x40u) != 0u) ubRf[rCd].a = rcdO.b;\n"
"    ubRf[rMs].rgb = rmsO;\n"
"    ubRf[aAb].a = aabO;\n"
"    ubRf[aCd].a = acdO;\n"
"    ubRf[aMs].a = amsO;\n"
"    ubRf[6] = vec4(0.0);\n"
"}\n"
"\n"
"vec4 ubRun() {\n"
"    ubRf[0] = vec4(0.0); ubRf[6] = vec4(0.0); ubRf[7] = vec4(0.0);\n"
"    ubRf[3] = ubFog; ubRf[4] = ubV0; ubRf[5] = ubV1;\n"
"    ubRf[8] = ubT0; ubRf[9] = ubT1; ubRf[10] = ubT2; ubRf[11] = ubT3;\n"
"    ubRf[12] = ubR0; ubRf[13] = ubR1;\n"
"    uint n = min(ubComb[8].z & 0xFFu, 8u);\n"
"    for (uint s = 0u; s < n; s++) {\n"
"        ubStage(s);\n"
"    }\n"
"    uint f0 = ubComb[8].x, f1 = ubComb[8].y;\n"
/* E and F first, as psh.c does: EF_PROD is only defined after them. */
"    ubLoad(8u);\n"
"    ubE = ubIn3(f1 >> 24);\n"
"    ubF = ubIn3((f1 >> 16) & 0xFFu);\n"
"    ubLoad(8u);\n"
"    vec3 fa = ubIn3(f0 >> 24), fb = ubIn3((f0 >> 16) & 0xFFu);\n"
"    vec3 fc = ubIn3((f0 >> 8) & 0xFFu), fd = ubIn3(f0 & 0xFFu);\n"
"    float fg = ubIn1((f1 >> 8) & 0xFFu);\n"
"    return vec4(fd + mix(vec3(fc), vec3(fb), vec3(fa)), fg);\n"
"}\n"
"\n";

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
    g_string_append_len(out->gstr, main_fn, comb - main_fn);
    mstring_append(out, uber_glsl_call);
    mstring_append(out, comb_end);

    mstring_unref(tpl);
    return out;
}
