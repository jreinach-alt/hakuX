/*
 * Geforce NV2A PGRAPH GLSL Shader Generator
 *
 * Copyright (c) 2015 espes
 * Copyright (c) 2015 Jannik Vogel
 * Copyright (c) 2020-2025 Matt Borgerson
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
#include "common.h"
#include "vsh-ff.h"

static void append_skinning_code(MString *str, bool mix, unsigned int count,
                                 const char *type, const char *output,
                                 const char *input, const char *matrix,
                                 const char *swizzle)
{
    if (count == 0) {
        mstring_append_fmt(str, "%s %s = (%s * %s0).%s;\n",
                           type, output, input, matrix, swizzle);
    } else {
        mstring_append_fmt(str, "%s %s = %s(0.0);\n", type, output, type);
        if (mix) {
            /* Generated final weight (like GL_WEIGHT_SUM_UNITY_ARB) */
            mstring_append(str, "{\n"
                                "  float weight_i;\n"
                                "  float weight_n = 1.0;\n");
            int i;
            for (i = 0; i < count; i++) {
                if (i < (count - 1)) {
                    char c = "xyzw"[i];
                    mstring_append_fmt(str, "  weight_i = weight.%c;\n"
                                            "  weight_n -= weight_i;\n",
                                       c);
                } else {
                    mstring_append(str, "  weight_i = weight_n;\n");
                }
                mstring_append_fmt(str, "  %s += (%s * %s%d).%s * weight_i;\n",
                                   output, input, matrix, i, swizzle);
            }
            mstring_append(str, "}\n");
        } else {
            /* Individual weights */
            int i;
            for (i = 0; i < count; i++) {
                char c = "xyzw"[i];
                mstring_append_fmt(str, "%s += (%s * %s%d).%s * weight.%c;\n",
                                   output, input, matrix, i, swizzle, c);
            }
        }
    }
}


/*
 * Everything the light loop reads, whichever vertex path runs it.
 *
 * LIGHTING_ENABLE, the light enables, the light and material registers and
 * the transform registers the lighting unit takes its eye-space geometry
 * from are all the same registers under a vertex program as under fixed
 * function, so both paths emit this once and share the loop below.
 */
static void append_lighting_header(MString *header)
{
    mstring_append(header,
"\n"
GLSL_DEFINE(modelViewMat0, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_MMAT0))
GLSL_DEFINE(modelViewMat1, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_MMAT1))
GLSL_DEFINE(modelViewMat2, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_MMAT2))
GLSL_DEFINE(modelViewMat3, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_MMAT3))
"\n"
GLSL_DEFINE(invModelViewMat0, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_IMMAT0))
GLSL_DEFINE(invModelViewMat1, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_IMMAT1))
GLSL_DEFINE(invModelViewMat2, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_IMMAT2))
GLSL_DEFINE(invModelViewMat3, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_IMMAT3))
"\n"
GLSL_DEFINE(eyePosition, GLSL_C(NV_IGRAPH_XF_XFCTX_EYEP))
"\n"
"#define lightAmbientColor(i) "
    "lt(ltctxb[" stringify(NV_IGRAPH_XF_LTCTXB_L0_AMB) " + (i)*6].xyz)\n"
"#define lightDiffuseColor(i) "
    "lt(ltctxb[" stringify(NV_IGRAPH_XF_LTCTXB_L0_DIF) " + (i)*6].xyz)\n"
"#define lightSpecularColor(i) "
    "lt(ltctxb[" stringify(NV_IGRAPH_XF_LTCTXB_L0_SPC) " + (i)*6].xyz)\n"
"#define lightBackAmbientColor(i) "
    "lt(ltctxb[" stringify(NV_IGRAPH_XF_LTCTXB_L0_BAMB) " + (i)*6].xyz)\n"
"#define lightBackDiffuseColor(i) "
    "lt(ltctxb[" stringify(NV_IGRAPH_XF_LTCTXB_L0_BDIF) " + (i)*6].xyz)\n"
"#define lightBackSpecularColor(i) "
    "lt(ltctxb[" stringify(NV_IGRAPH_XF_LTCTXB_L0_BSPC) " + (i)*6].xyz)\n"
"\n"
"#define lightSpotFalloff(i) "
    "ltctxa[" stringify(NV_IGRAPH_XF_LTCTXA_L0_K) " + (i)*2].xyz\n"
"#define lightSpotDirection(i) "
    "ltctxa[" stringify(NV_IGRAPH_XF_LTCTXA_L0_SPT) " + (i)*2]\n"
"\n"
"#define lightLocalRange(i) "
    "ltc1[" stringify(NV_IGRAPH_XF_LTC1_r0) " + (i)].x\n"
"\n"
GLSL_DEFINE(eyeDirection, GLSL_LTCTXA(NV_IGRAPH_XF_LTCTXA_EYED) ".xyz")
"#define sceneAmbientColor lt(" GLSL_LTCTXA(NV_IGRAPH_XF_LTCTXA_FR_AMB) ".xyz)\n"
"#define materialEmissionColor lt(" GLSL_LTCTXA(NV_IGRAPH_XF_LTCTXA_CM_COL) ".xyz)\n"
"#define backSceneAmbientColor lt(" GLSL_LTCTXA(NV_IGRAPH_XF_LTCTXA_BR_AMB) ".xyz)\n"
"#define backMaterialEmissionColor lt(" GLSL_LTCTXA(NV_IGRAPH_XF_LTCTXA_BCM_COL) ".xyz)\n"
"\n"
);

    /* The lighting unit works on floats with a 13-bit fraction: the
     * Celsius transform model (envytools, xf_s2lt) rounds every value it
     * takes in to the nearest such float, adding half a unit at bit 9
     * before dropping the low ten bits, except that a value whose bits 10
     * to 17 are all set is dropped without the half unit. lt() brings the
     * registers, the vertex colours and the transform unit's outputs to
     * that precision on their way in. */
    mstring_append(header,
        "uint ltBits(uint u) {\n"
        "  if (((u >> 10) & 0xFFu) != 0xFFu) u += 0x200u;\n"
        "  return u & 0xFFFFFC00u;\n"
        "}\n"
        "float lt(float x) { return uintBitsToFloat(ltBits(floatBitsToUint(x))); }\n"
        "vec3 lt(vec3 v) { return vec3(lt(v.x), lt(v.y), lt(v.z)); }\n"
        "vec4 lt(vec4 v) { return vec4(lt(v.x), lt(v.y), lt(v.z), lt(v.w)); }\n");

    /* The lighting unit's own arithmetic, bit for bit: envytools'
     * pgraph_celsius_lt_mul, _lts_mul, _lt_add3, _lts_add and _lt_rcp
     * (nvhw/pgraph_celsius_xfrm.c), which hwtest checks against the
     * hardware. Every operand carries a 14-bit mantissa; a multiply keeps the
     * top 14 bits of the product, an add aligns and sums in fixed point and
     * drops what falls off, both towards zero; the reciprocal is a 64-entry
     * table and one Newton step. NV2A keeps the Celsius lighting unit's
     * register file (LTCTXA/B, LTC0-3), and the rounding lt() models on
     * the way in is xf_s2lt from the same file.
     *
     * Float32 arithmetic after lt() was the approximation, and #224 is where
     * it shows: Shade model's normal 3 lands one float32 ulp under the
     * 13-bit step that gives silicon's blue 60, and rounding the normal to
     * lift it (lt(N) alone) lifts Lighting range Directional's specular over
     * its own step, 203 -> 204. This arithmetic gives all nine Shade model
     * colours, 203 for Directional, and 127 for five 0.1 ambients
     * (Lighting accumulation Directional-5) -- none of them fitted
     * (docs/lanes/shadetie224/price.py --three). */
    mstring_append(header,
        "const uint ltRcpLut[64] = uint[64](\n"
        "  0x7Fu, 0x7Du, 0x7Bu, 0x79u, 0x77u, 0x75u, 0x74u, 0x72u,\n"
        "  0x70u, 0x6Fu, 0x6Du, 0x6Cu, 0x6Bu, 0x69u, 0x68u, 0x67u,\n"
        "  0x65u, 0x64u, 0x63u, 0x62u, 0x60u, 0x5Fu, 0x5Eu, 0x5Du,\n"
        "  0x5Cu, 0x5Bu, 0x5Au, 0x59u, 0x58u, 0x57u, 0x56u, 0x55u,\n"
        "  0x54u, 0x54u, 0x53u, 0x52u, 0x51u, 0x50u, 0x4Fu, 0x4Fu,\n"
        "  0x4Eu, 0x4Du, 0x4Cu, 0x4Cu, 0x4Bu, 0x4Au, 0x4Au, 0x49u,\n"
        "  0x48u, 0x48u, 0x47u, 0x46u, 0x46u, 0x45u, 0x45u, 0x44u,\n"
        "  0x43u, 0x43u, 0x42u, 0x42u, 0x41u, 0x41u, 0x40u, 0x40u);\n"
        "const uint LT_NAN = 0x7FFFFC00u;\n"
        "const uint LT_INF = 0x7F800000u;\n"
        /* Index of the highest set bit of a nonzero value (no findMSB in
         * GLSL ES 3.00). */
        "int ltMsb(uint u) {\n"
        "  int n = 0;\n"
        "  if (u >= 0x10000u) { u >>= 16; n += 16; }\n"
        "  if (u >= 0x100u) { u >>= 8; n += 8; }\n"
        "  if (u >= 0x10u) { u >>= 4; n += 4; }\n"
        "  if (u >= 0x4u) { u >>= 2; n += 2; }\n"
        "  if (u >= 0x2u) { n += 1; }\n"
        "  return n;\n"
        "}\n"
        "uint ltShr(uint m, int sh) {\n"
        "  return sh >= 32 ? 0u : (sh >= 0 ? m >> uint(sh) : m << uint(-sh));\n"
        "}\n"
        "bool ltIsNan(uint x) { return (x & 0x7F800000u) == 0x7F800000u && (x & 0x7FFFFFu) != 0u; }\n"
        "bool ltIsInf(uint x) { return (x & 0x7FFFFFFFu) == 0x7F800000u; }\n"
        /* fp32_mkfin(s, e, m << 10, FP_RZ | FP_FTZ), m normalised to bit 13 */
        "float ltMk(uint s, int e, uint m) {\n"
        "  if (m == 0u || e <= 0) return uintBitsToFloat(s << 31);\n"
        "  if (e >= 255) return uintBitsToFloat(s << 31 | 0x7F7FFFFFu);\n"
        "  return uintBitsToFloat(s << 31 | uint(e) << 23 | (m & 0x1FFFu) << 10);\n"
        "}\n"
        "float ltMulCore(float fa, float fb, bool signedInf) {\n"
        "  uint a = floatBitsToUint(fa), b = floatBitsToUint(fb);\n"
        "  uint s = (a ^ b) >> 31;\n"
        "  int ea = int(a >> 23 & 0xFFu), eb = int(b >> 23 & 0xFFu);\n"
        "  uint ma = (a >> 10 & 0x1FFFu) | 0x2000u, mb = (b >> 10 & 0x1FFFu) | 0x2000u;\n"
        "  if ((ea == 255 && ma > 0x2000u) || (eb == 255 && mb > 0x2000u))\n"
        "    return uintBitsToFloat(LT_NAN);\n"
        "  if (ea == 0 || eb == 0) return 0.0;\n"
        "  if (ea == 255 || eb == 255)\n"
        "    return uintBitsToFloat(signedInf ? (s << 31 | LT_INF) : LT_INF);\n"
        "  int e = ea + eb - 127;\n"
        "  if (signedInf && e >= 255) return uintBitsToFloat(s << 31 | LT_INF);\n"
        "  uint m = (ma * mb) >> 13;\n"
        "  if (m > 0x3FFFu) { m >>= 1; e++; }\n"
        "  if (e <= 0) return uintBitsToFloat(s << 31);\n"
        "  if (e >= 255) { e = 254; m = 0x1FFFu; }\n"
        "  return uintBitsToFloat(s << 31 | uint(e) << 23 | (m & 0x1FFFu) << 10);\n"
        "}\n"
        "float ltM(float a, float b) { return ltMulCore(a, b, false); }\n"
        "float ltsM(float a, float b) { return ltMulCore(a, b, true); }\n"
        "vec3 ltVM(vec3 a, vec3 b) { return vec3(ltM(a.x, b.x), ltM(a.y, b.y), ltM(a.z, b.z)); }\n"
        "float ltA3(float x0, float x1, float x2) {\n"
        "  uint v[3] = uint[3](floatBitsToUint(x0), floatBitsToUint(x1), floatBitsToUint(x2));\n"
        "  bool pinf = false, ninf = false;\n"
        "  for (int i = 0; i < 3; i++) {\n"
        "    if (ltIsNan(v[i])) return uintBitsToFloat(LT_NAN);\n"
        "  }\n"
        "  for (int i = 0; i < 3; i++) {\n"
        "    if (ltIsInf(v[i])) { if ((v[i] >> 31) != 0u) ninf = true; else pinf = true; }\n"
        "  }\n"
        "  if (pinf && ninf) return uintBitsToFloat(LT_NAN);\n"
        "  if (pinf || ninf) return uintBitsToFloat(LT_INF);\n"
        "  int er = 0;\n"
        "  int e[3];\n"
        "  uint m[3];\n"
        "  for (int i = 0; i < 3; i++) {\n"
        "    e[i] = int(v[i] >> 23 & 0xFFu);\n"
        "    m[i] = ((v[i] & 0x7FFFFFu) | (e[i] != 0 ? 0x800000u : 0u)) >> 10;\n"
        "    er = max(er, e[i] + 2);\n"
        "  }\n"
        "  int r = 0;\n"
        "  for (int i = 0; i < 3; i++) {\n"
        "    int f = int(ltShr(m[i], er - e[i] - 7));\n"
        "    r += (v[i] >> 31) != 0u ? -f : f;\n"
        "  }\n"
        "  if (r == 0) return 0.0;\n"
        "  uint s = r < 0 ? 1u : 0u;\n"
        "  uint u = uint(abs(r));\n"
        "  int sh = 20 - ltMsb(u);\n"
        "  u <<= uint(sh);\n"
        "  er -= sh;\n"
        "  u >>= 7u;\n"
        "  if (er >= 255) { er = 254; u = 0x3FFFu; }\n"
        "  return ltMk(s, er, u);\n"
        "}\n"
        "float ltA(float a, float b) { return ltA3(a, b, 0.0); }\n"
        "vec3 ltVA(vec3 a, vec3 b) { return vec3(ltA(a.x, b.x), ltA(a.y, b.y), ltA(a.z, b.z)); }\n"
        "float ltDp(vec3 a, vec3 b) { return ltA3(ltM(a.x, b.x), ltM(a.y, b.y), ltM(a.z, b.z)); }\n"
        "float ltsA(float fa, float fb) {\n"
        "  uint a = floatBitsToUint(fa), b = floatBitsToUint(fb);\n"
        "  if (ltIsNan(a) || ltIsNan(b)) return uintBitsToFloat(LT_NAN);\n"
        "  if (ltIsInf(a) || ltIsInf(b)) {\n"
        "    if (ltIsInf(a) && ltIsInf(b) && (a >> 31) != (b >> 31)) return uintBitsToFloat(LT_NAN);\n"
        "    return uintBitsToFloat(LT_INF);\n"
        "  }\n"
        "  int ea = int(a >> 23 & 0xFFu), eb = int(b >> 23 & 0xFFu);\n"
        "  uint ma = ea != 0 ? ((a & 0x7FFFFFu) >> 10) | 0x2000u : 0u;\n"
        "  uint mb = eb != 0 ? ((b & 0x7FFFFFu) >> 10) | 0x2000u : 0u;\n"
        "  int er = max(ea, eb) + 1;\n"
        "  int fa2 = int(ltShr(ma, er - ea - 1)), fb2 = int(ltShr(mb, er - eb - 1));\n"
        "  int r = ((a >> 31) != 0u ? -fa2 : fa2) + ((b >> 31) != 0u ? -fb2 : fb2);\n"
        "  if (r == 0) return 0.0;\n"
        "  uint s = r < 0 ? 1u : 0u;\n"
        "  uint u = uint(abs(r));\n"
        "  int sh = 14 - ltMsb(u);\n"
        "  u <<= uint(sh);\n"
        "  er -= sh;\n"
        "  u >>= 1u;\n"
        "  return ltMk(s, er, u);\n"
        "}\n"
        "float ltR(float fx) {\n"
        "  uint x = floatBitsToUint(fx);\n"
        "  if (ltIsNan(x)) return uintBitsToFloat(LT_NAN);\n"
        "  uint sx = x >> 31;\n"
        "  int ex = int(x >> 23 & 0xFFu);\n"
        "  if (ex == 0) return uintBitsToFloat(LT_INF);\n"
        "  if (ltIsInf(x)) return 0.0;\n"
        "  int er = 0xFD - ex;\n"
        "  uint f = ((x & 0x7FFFFFu) + 0x800000u) >> 10;\n"
        "  uint s0 = ltRcpLut[f >> 7 & 0x3Fu];\n"
        "  uint s1 = (((1u << 21) - s0 * f) * s0 >> 14) << 11;\n"
        "  uint fr = s1 - 0x800000u;\n"
        "  if (er <= 0) return uintBitsToFloat(sx << 31);\n"
        "  return uintBitsToFloat(sx << 31 | uint(er) << 23 | (fr & 0x7FFFFFu));\n"
        "}\n");
}

struct LightingSide {
    const char *normal;
    const char *diffuse_out;
    const char *specular_out;
    const char *ambient_color;
    const char *diffuse_color;
    const char *specular_color;
    const char *constant;
    const char *factor;
    const char *material_alpha;
    int specular_params;
    /* The lit specular is added to the diffuse output light by light
     * instead of leaving on its own (SPECULAR_ENABLE or SEPARATE_SPECULAR
     * clear). */
    bool fold_specular;
    enum MaterialColorSource emission_src;
    enum MaterialColorSource ambient_src;
    enum MaterialColorSource diffuse_src;
    enum MaterialColorSource specular_src;
};

/* The vertex colour a colour material selector names, and the factor it
 * puts in front of a light's term. */
static const char *vertex_color_rgb(enum MaterialColorSource src)
{
    switch (src) {
    case MATERIAL_COLOR_SRC_DIFFUSE: return "ltDiffuse.rgb";
    case MATERIAL_COLOR_SRC_SPECULAR: return "ltSpecular.rgb";
    default: return NULL;
    }
}

/* Adds one light's term to an output, through the lighting unit's multiply
 * by the vertex colour when a selector names one. */
static void append_light_term(MString *body, const char *out,
                              enum MaterialColorSource src, const char *term)
{
    const char *vc = vertex_color_rgb(src);
    if (vc) {
        mstring_append_fmt(body, "    %s.xyz = ltVA(%s.xyz, ltVM(%s, %s));\n",
                           out, out, term, vc);
    } else {
        mstring_append_fmt(body, "    %s.xyz = ltVA(%s.xyz, %s);\n",
                           out, out, term);
    }
}

/* Emits the lighting of one face into its two colour outputs. */
/* oD0 and oD1 before any light is added: the constant term the colour
 * material selectors build. Shared with the programmable path, which reaches
 * the same registers by different names for the vertex colours. */
static void append_lighting_constant(MString *body,
                                     const struct LightingSide *side,
                                     const char *diffuse_a,
                                     const char *specular_a)
{
    /* SET_SCENE_AMBIENT_COLOR is a constant term and SET_MATERIAL_EMISSION
     * a factor applied to one vertex colour; the emission and ambient
     * source selectors pick that colour and whether the constant term
     * survives. Every Material_color_source golden fits this to the
     * byte:
     *
     *   emission   ambient    oD0 before the lights are added
     *   material   material   SCENE_AMBIENT
     *   vertex E   material   SCENE_AMBIENT + E * MATERIAL_EMISSION
     *   material   vertex A   SCENE_AMBIENT + A * MATERIAL_EMISSION
     *   vertex E   vertex A   E + A * MATERIAL_EMISSION
     *
     * and each light's ambient colour is scaled by A when the ambient
     * comes from a vertex colour. That is what D3D relies on: it
     * programs the constant term with the material emission plus the
     * scene ambient times the material ambient, and the factor with the
     * scene ambient (or one), which is where the register names come
     * from. The previous code scaled the ambient source by the factor
     * unconditionally and then added the emission source, which only
     * matches the last two rows. */
    const char *alpha_source = diffuse_a;
    if (side->diffuse_src == MATERIAL_COLOR_SRC_MATERIAL) {
        alpha_source = side->material_alpha;
    } else if (side->diffuse_src == MATERIAL_COLOR_SRC_SPECULAR) {
        alpha_source = specular_a;
    }

    const char *constant = side->constant;
    const char *scaled = NULL;
    if (side->ambient_src != MATERIAL_COLOR_SRC_MATERIAL) {
        scaled = vertex_color_rgb(side->ambient_src);
        if (side->emission_src != MATERIAL_COLOR_SRC_MATERIAL) {
            constant = vertex_color_rgb(side->emission_src);
        }
    } else if (side->emission_src != MATERIAL_COLOR_SRC_MATERIAL) {
        scaled = vertex_color_rgb(side->emission_src);
    }
    mstring_append_fmt(body, "  %s = vec4(%s, %s);\n",
                       side->diffuse_out, constant, alpha_source);
    if (scaled) {
        mstring_append_fmt(body, "  %s.rgb = ltVA(%s.rgb, ltVM(%s, %s));\n",
                           side->diffuse_out, side->diffuse_out, scaled,
                           side->factor);
    }
    mstring_append_fmt(body, "  %s = vec4(0.0, 0.0, 0.0, %s);\n",
                       side->specular_out, specular_a);
}

static void append_lighting(const VshState *state, MString *body,
                            const struct LightingSide *side,
                            const char *diffuse_a, const char *specular_a)
{
    append_lighting_constant(body, side, diffuse_a, specular_a);

    /* The normal and the eye vector enter the lighting unit rounded
     * (xf_s2lt), as the light registers do. */
    mstring_append_fmt(body, "  {\n  vec3 N = lt(%s);\n", side->normal);
    if (state->local_eye) {
        mstring_append(body,
            "  vec3 ltEye = lt(normalize(eyePosition.xyz / eyePosition.w - tPosition.xyz / tPosition.w));\n"
        );
    } else {
        mstring_append(body, "  vec3 ltEye = lt(eyeDirection);\n");
    }

    for (int i = 0; i < NV2A_MAX_LIGHTS; i++) {
        if (state->light[i] == LIGHT_OFF) {
            continue;
        }

        mstring_append_fmt(body, "  /* Light %d */ {\n", i);

        if (state->light[i] == LIGHT_LOCAL
                || state->light[i] == LIGHT_SPOT) {

            /* The lighting unit's reciprocal of zero is infinity, and
             * its multiply gives zero for zero times anything, so a light
             * with all three attenuation values at zero lights every
             * channel its colour is nonzero in and none it is zero in
             * (the Lighting spotlight AtFixed 0/0/0 golden). ltR() and
             * ltM() do exactly that. The light vector, its distance and
             * its square come from the transform unit, which works in
             * float32, and are rounded on the way in. */
            mstring_append_fmt(body,
                "  vec3 tPos = tPosition.xyz/tPosition.w;\n"
                "  vec3 VP = lightLocalPosition[%d] - tPos;\n"
                "  float d = length(VP);\n"
                "  if (d <= lightLocalRange(%d)) {\n"  /* FIXME: Double check that range is inclusive */
                "    vec3 lv = lt(normalize(VP));\n"
                "    float ca = ltR(ltDp(vec3(1.0, lt(d), lt(d * d)),\n"
                "                        lt(lightLocalAttenuation[%d])));\n",
                i, i, i);
        } else {
            /* The direction register is used as it is, like the half
             * vector register: D3D normalises before writing it, and
             * with an unnormalised one the diffuse scales by its length
             * (the Specular ControlFlags_FF golden lights its quads with
             * (1, 0, 1) and their diffuse is that of a unit vector times
             * the square root of two, saturating on one side). */
            mstring_append_fmt(body,
                "  {\n"
                "    vec3 lv = lt(lightInfiniteDirection[%d]);\n"
                "    float ca = 1.0;\n",
                i);
        }

        if (state->light[i] == LIGHT_SPOT) {
            /* The spot direction register holds the axis scaled so that
             * x = dot(dir, VP) + w runs from 0 at the outer cone to 1 at
             * the inner one, and the three falloff values feed the same
             * rational evaluator the lighting unit uses for the specular
             * power: S = (x + k0) / (x k1 + k2), zero once the numerator
             * goes negative. That is the form D3D's falloff tables are
             * fitted to (S(1) = 1 for every table entry), and it holds
             * across the Lighting spotlight goldens: with (0, 1, 0) the
             * cone is lit flat, with (0, -0.4946, 1.4946) linearly, and
             * the ten falloff sweeps follow it to a step. The previous
             * linear ramp ignored the falloff values altogether. Inside
             * the inner cone x is held at 1.
             *
             * The factor is not clamped. It scales the attenuation that
             * both the diffuse and the specular term are multiplied by,
             * so with all three falloff values at zero the reciprocal of
             * zero saturates both of them across the whole cone (the
             * FoFixed 0/0/0 golden is flat magenta from a red diffuse and
             * a half-blue specular), which a factor held at one cannot
             * reproduce. envytools does not model the spot factor
             * ("XXX spotlight"), so it stays float32 and is rounded into
             * the unit's attenuation multiply. */
            mstring_append_fmt(body,
                "    vec4 spotDir = lightSpotDirection(%d);\n"
                "    vec3 spotK = lightSpotFalloff(%d);\n"
                "    float spotX = min(dot(spotDir.xyz, normalize(VP)) + spotDir.w, 1.0);\n"
                "    float spotN = spotX + spotK.x;\n"
                "    float spotD = spotX * spotK.y + spotK.z;\n"
                "    float spotS = spotD == 0.0 ? FLOAT_MAX : spotN / spotD;\n"
                "    ca = spotN <= 0.0 ? 0.0 : ltM(ca, lt(spotS));\n",
                i, i);
        }

        /* pgraph_celsius_lt_full, one light. A negative N.L zeroes both the
         * diffuse and the specular term. The specular power is not a
         * pow(): the unit evaluates a rational function with three
         * coefficients, S = (x + k0) / (x k1 + k2), zero once the
         * numerator goes negative; that is the form D3D's specular tables
         * are fitted to and the Specular goldens follow. An infinite light
         * seen by a non-local eye uses its precomputed half vector and the
         * first triple on x = N.H. Everything else builds the half vector
         * per vertex, H = eye + light unnormalised, and evaluates the
         * second triple homogeneously, (s^2 + k0 |H|^2) / (s^2 k1 +
         * |H|^2 k2) with s = N.H, which is x = (N.H)^2 / |H|^2 without a
         * square root. A numerator past the pole is not clamped: the
         * factor goes negative, the separate output clamps it away and the
         * fold subtracts it from the ambient (Lighting control's sphere
         * and cylinder, whose normals are longer than one). */
        bool half_precomputed = state->light[i] == LIGHT_INFINITE &&
                                !state->local_eye;
        mstring_append_fmt(body,
            "    vec3 k = lt(specularParams[%d]);\n"
            "    bool zero = false;\n"
            "    float cd = ltDp(N, lv);\n"
            "    if (cd < 0.0) { zero = true; cd = 0.0; }\n"
            "    cd = ltM(ca, cd);\n",
            side->specular_params + (half_precomputed ? 0 : 1));
        if (half_precomputed) {
            mstring_append_fmt(body,
                "    float s = ltDp(N, lt(lightInfiniteHalfVector[%d]));\n"
                "    float t = ltsA(s, k.x);\n"
                "    if (t < 0.0) zero = true;\n"
                "    float b = ltsA(ltsM(s, k.y), k.z);\n",
                i);
        } else {
            mstring_append(body,
                "    vec3 hi = ltVA(ltEye, lv);\n"
                "    float hd = ltDp(hi, hi);\n"
                "    float s = ltDp(N, hi);\n"
                "    if (s < 0.0) zero = true;\n"
                "    float ss = ltsM(s, s);\n"
                "    float t = ltsA(ss, ltsM(hd, k.x));\n"
                "    if (t < 0.0) zero = true;\n"
                "    float b = ltsA(ltsA(ltsM(ss, k.y), 0.0), ltsM(hd, k.z));\n");
        }
        mstring_append_fmt(body,
            "    float cs = zero ? 0.0 : ltM(ca, ltsM(t, ltR(b)));\n"
            "    vec3 lightAmbient = ltVM(vec3(ca), %s(%d));\n"
            "    vec3 lightDiffuse = ltVM(vec3(cd), %s(%d));\n"
            "    vec3 lightSpecular = ltVM(vec3(cs), %s(%d));\n",
            side->ambient_color, i, side->diffuse_color, i,
            side->specular_color, i);

        append_light_term(body, side->diffuse_out, side->ambient_src,
                          "lightAmbient");
        append_light_term(body, side->diffuse_out, side->diffuse_src,
                          "lightDiffuse");
        append_light_term(body,
                          side->fold_specular ? side->diffuse_out
                                              : side->specular_out,
                          side->specular_src, "lightSpecular");

        mstring_append(body, "  }\n"
                             "  }\n");
    }
    mstring_append(body, "  }\n");
}

/*
 * The colour outputs under a vertex program.
 *
 * LIGHTING_ENABLE does not only switch the lighting arithmetic on: it switches
 * which source feeds oD0 and oD1, and that gate survives a programmable vertex
 * shader. Measured on the Specular goldens, where the three ControlFlags_VS
 * captures differ only in this register and whether a light is enabled:
 * silicon renders three different images 85,922 pixels apart, and with
 * lighting on and no light its output is the material constant term with the
 * specular zeroed -- grey, with no dependence on the vertex colour the program
 * wrote. Silicon's fixed function and programmable renders of that state agree
 * on 83,512 of those 85,922 pixels, so the same block produces both.
 *
 * The whole block runs, not just its constant term, and it runs on the fixed
 * function transform registers. The lit Specular ControlFlags_VS golden pins
 * the arithmetic: over the lit quads its per-light term (the capture minus the
 * no-light capture, which cancels the background blend) takes exactly the two
 * values the ControlFlags_FF golden's does -- 51.7 and 42.6 in red, against
 * our own fixed function path's 51.67 and 42.61 -- and its mean over that
 * region is (31.18, 4.55, 15.82) against our fixed function's (31.43, 4.84,
 * 16.07). So the light colours, the material selectors, the specular
 * evaluator and the eye-space normal the transform registers give are all the
 * same ones. A vertex program does not hand its own transform to this unit
 * and silicon does not ask it to.
 *
 * What is *not* modelled is which vertex each of those values lands on.
 * Fitting the four corner values of every lit quad, the fixed function golden
 * assigns them by the normal's x sign in every quad, while the programmable
 * golden assigns them differently in every quad -- and in four of the eight
 * lit quads the assignment is not a permutation of the vertex stream at all
 * (three corners take one value and one takes the other, where the four
 * normals can only give two of each). A skew of the normal stream cannot
 * produce that, and the per-vertex colours land on the same corners in both
 * goldens, so it is the lighting unit's own per-vertex input that is skewed.
 * The skew varies between quads that differ only in SET_LIGHT_CONTROL and
 * screen position, which no register state explains, so it is left alone
 * here deliberately: the values are right and the assignment is not.
 *
 * (An earlier note here said the test drives the program's own model matrix
 * per draw while modelViewMat0 sits at the XDK default. That is wrong:
 * specular_tests.cpp calls neither MatrixRotate nor GetModelMatrix, and its
 * SetupVertexShader calls LookAt once for the whole capture.)
 */
void pgraph_glsl_append_vsh_prog_lighting(const VshState *state,
                                          MString *header, MString *body)
{
    append_lighting_header(header);

    mstring_append(body, "  {\n"
                         "  vec4 ltDiffuse = lt(v3);\n"
                         "  vec4 ltSpecular = lt(v4);\n");

    /* The eye-space geometry the lighting unit works in, built from the
     * fixed function transform registers with no skinning: a vertex program
     * owns the weights attribute, so there is no weighted transform for this
     * unit to follow. This is what the fixed function stage emits for
     * SKINNING_OFF. */
    mstring_append(
        body, "  vec4 tPosition = v0 * modelViewMat0;\n"
              "  vec3 tNormal = (vec4(v2.xyz, 0.0) * invModelViewMat0).xyz;\n");
    if (state->normalization) {
        mstring_append(body, "  tNormal = normalize(tNormal);\n");
    }

    struct LightingSide front = {
        .normal = "tNormal",
        .diffuse_out = "oD0",
        .specular_out = "oD1",
        .ambient_color = "lightAmbientColor",
        .diffuse_color = "lightDiffuseColor",
        .specular_color = "lightSpecularColor",
        .constant = "sceneAmbientColor",
        .factor = "materialEmissionColor",
        .material_alpha = "material_alpha",
        .specular_params = 0,
        .fold_specular = !state->specular_enable || !state->separate_specular,
        .emission_src = state->emission_src,
        .ambient_src = state->ambient_src,
        .diffuse_src = state->diffuse_src,
        .specular_src = state->specular_src,
    };
    append_lighting(state, body, &front, "v3.a", "v4.a");

    if (state->two_side_light) {
        struct LightingSide back = {
            .normal = "-tNormal",
            .diffuse_out = "oB0",
            .specular_out = "oB1",
            .ambient_color = "lightBackAmbientColor",
            .diffuse_color = "lightBackDiffuseColor",
            .specular_color = "lightBackSpecularColor",
            .constant = "backSceneAmbientColor",
            .factor = "backMaterialEmissionColor",
            .material_alpha = "material_alpha_back",
            .specular_params = 2,
            .fold_specular = !state->specular_enable || !state->separate_specular,
            .emission_src = state->back_emission_src,
            .ambient_src = state->back_ambient_src,
            .diffuse_src = state->back_diffuse_src,
            .specular_src = state->back_specular_src,
        };
        append_lighting(state, body, &back, "v3.a", "v4.a");
    }
    mstring_append(body, "  }\n");

    /*
     * The lit colour output mux, the same one the fixed function stage
     * applies (see the comment on it in pgraph_glsl_gen_vsh_ff): with
     * SEPARATE_SPECULAR clear, or SPECULAR_ENABLE clear, the lit specular is
     * folded into the diffuse output, and the specular output carries a
     * vertex colour instead of the lighting unit's own.
     *
     * That mux is not bypassed by a vertex program either, and the goldens
     * say so exactly. In Specular's ControlFlagsNoLight_VS the whole residual
     * sits in the SPECULAR_ENABLE-on specular row, and all of it in the two
     * SEPARATE_SPECULAR-off columns: 8,560 of 8,560 and 8,480 of 8,480
     * pixels, where silicon's image is bit-identical to its own lighting-off
     * image (ControlFlagsLightDisable_VS agrees with it on every pixel of
     * both quads). Emitting this took that capture to 10,510 px, the value
     * predicted for it to the pixel.
     *
     * Which vertex colour is per side, and that is where the first attempt
     * was wrong: the front takes the front specular, the back takes the
     * *back* specular. The fixed function stage uses the front colour for
     * both -- its comment in pgraph_glsl_gen_vsh_ff says so and the
     * Specular_back ControlFlags_FF golden holds it up -- but a vertex
     * program does not. Measured in Specular_back's ControlFlagsNoLight_VS,
     * row y 285-364 column x 472-577, where the quad is one flat colour per
     * corner and nothing else is in play:
     *
     *   silicon (golden)                   (247, 8, 0)  = the back specular
     *   our lighting-off path, oB1 = v8    (247, 8, 0)  -- matches
     *   oB1 = v4 (the fixed function rule) (  0, 0, 255)
     *   silicon's own ControlFlagsNoLight_FF, and ours
     *                                      (  0, 0, 255) -- so FF really
     *                                                      does take v4
     *
     * Emitting v4 here moved all 17,040 px of those two quads and left every
     * one of them wrong; v8 puts them on the lighting-off image the golden
     * is bit-identical to.
     *
     * This cannot distinguish "the back specular attribute" from "whatever
     * the program last wrote to oB1", because this program writes
     * `mov oBackSpecular, iBackSpecular` and the two are the same value. The
     * same ambiguity sits on the front. The per-side vertex colour is taken
     * as the model because it is the shape the fixed function mux already
     * has; a program that writes something other than the vertex specular to
     * oD1/oB1 while LIGHTING_ENABLE and SEPARATE_SPECULAR-off are both set
     * would separate them, and no capture in the corpus does that.
     *
     * SPECULAR_ENABLE clear and ALPHA_FROM_MATERIAL_SPECULAR are already
     * applied to both paths on the way out to the fragment stage (vsh.c), so
     * only the fold and the substitution belong here. The back outputs are
     * only touched when two-sided lighting put the lit values there;
     * otherwise they still hold what the program wrote.
     *
     * Not fixed here, and not to be confused with this: under lighting our
     * back-face alpha in the ALPHA_FROM_MATERIAL_SPECULAR columns is a
     * per-draw constant 199 (material_alpha_back) where silicon's varies per
     * vertex, 191 upward, exactly as our own lighting-off output does. It is
     * independent of oB1 -- it does not move when oB1 does -- so it is not
     * this mux, and it is why Specular_back's ControlFlagsNoLight_VS keeps
     * 8,480 px in the SEPARATE_SPECULAR-on column that never moved for
     * either attempt.
     */
    if (state->specular_enable && !state->separate_specular) {
        mstring_append(body, "  oD1 = v4;\n");
        if (state->two_side_light) {
            mstring_append(body, "  oB1 = v8;\n");
        }
    }
}

void pgraph_glsl_gen_vsh_ff(const VshState *state, MString *header,
                            MString *body)
{
    int i, j;

    mstring_append(header,
"#define position      v0\n"
"#define weight        v1\n"
"#define normal        v2.xyz\n"
"#define diffuse       v3\n"
"#define specular      v4\n"
"#define fogCoord      v5.x\n"
"#define pointSize     v6\n"
"#define backDiffuse   v7\n"
"#define backSpecular  v8\n"
"#define texture0      v9\n"
"#define texture1      v10\n"
"#define texture2      v11\n"
"#define texture3      v12\n"
"#define reserved1     v13\n"
"#define reserved2     v14\n"
"#define reserved3     v15\n"
"\n");
    mstring_append(header,
"\n"
GLSL_DEFINE(projectionMat, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_PMAT0))
GLSL_DEFINE(compositeMat, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_CMAT0))
"\n"
GLSL_DEFINE(texPlaneS0, GLSL_C(NV_IGRAPH_XF_XFCTX_TG0MAT + 0))
GLSL_DEFINE(texPlaneT0, GLSL_C(NV_IGRAPH_XF_XFCTX_TG0MAT + 1))
GLSL_DEFINE(texPlaneR0, GLSL_C(NV_IGRAPH_XF_XFCTX_TG0MAT + 2))
GLSL_DEFINE(texPlaneQ0, GLSL_C(NV_IGRAPH_XF_XFCTX_TG0MAT + 3))
"\n"
GLSL_DEFINE(texPlaneS1, GLSL_C(NV_IGRAPH_XF_XFCTX_TG1MAT + 0))
GLSL_DEFINE(texPlaneT1, GLSL_C(NV_IGRAPH_XF_XFCTX_TG1MAT + 1))
GLSL_DEFINE(texPlaneR1, GLSL_C(NV_IGRAPH_XF_XFCTX_TG1MAT + 2))
GLSL_DEFINE(texPlaneQ1, GLSL_C(NV_IGRAPH_XF_XFCTX_TG1MAT + 3))
"\n"
GLSL_DEFINE(texPlaneS2, GLSL_C(NV_IGRAPH_XF_XFCTX_TG2MAT + 0))
GLSL_DEFINE(texPlaneT2, GLSL_C(NV_IGRAPH_XF_XFCTX_TG2MAT + 1))
GLSL_DEFINE(texPlaneR2, GLSL_C(NV_IGRAPH_XF_XFCTX_TG2MAT + 2))
GLSL_DEFINE(texPlaneQ2, GLSL_C(NV_IGRAPH_XF_XFCTX_TG2MAT + 3))
"\n"
GLSL_DEFINE(texPlaneS3, GLSL_C(NV_IGRAPH_XF_XFCTX_TG3MAT + 0))
GLSL_DEFINE(texPlaneT3, GLSL_C(NV_IGRAPH_XF_XFCTX_TG3MAT + 1))
GLSL_DEFINE(texPlaneR3, GLSL_C(NV_IGRAPH_XF_XFCTX_TG3MAT + 2))
GLSL_DEFINE(texPlaneQ3, GLSL_C(NV_IGRAPH_XF_XFCTX_TG3MAT + 3))
);

    /*
     * The fixed-function screen z truncates. Silicon's z/w is every step
     * rounded toward zero: the z-column products, their sums, w, the
     * reciprocal of w (24 bits) and the final multiply. Derived from the
     * Depth buffer fixed function goldens (#272), where the XDK composite's z
     * column has one live product, z*C22 + C32 with C32 = 6*C22 + 4: at the
     * near plane z*C22 is an exact float32 tie, round-to-nearest gives
     * z_clip 0 and truncation 8, and silicon stores 8. Held out, it lands
     * Color zeta overlap Swap (w 187) and ZetaIntoColor (w 199) on silicon's
     * words, 4 and 3 below round-to-nearest. RCP(1) is exactly 1 on silicon
     * (nxdk_vsh_tests ILU_RCP), which a constant reciprocal deficit breaks;
     * silicon's reciprocal does sit up to ~0.3 ulp low elsewhere, which
     * this does not model. docs/lanes/zdepth272/NOTES.md.
     *
     * The host rounds to nearest, so each step is taken exactly (Dekker's
     * product, Knuth's sum -- no fma, as psh.c's depth floor already
     * assumes) and stepped one ulp toward zero when the exact result lies
     * nearer zero. The reciprocal is corrected to the largest r with
     * |w|*r <= 1, which tolerates a host 1/w up to 2 ulp either way.
     */
    mstring_append(header,
"float ffRtz(float r, float e) {\n"
"  return (r != 0.0 && !isinf(r) && e != 0.0 && (e < 0.0) != (r < 0.0))\n"
"      ? uintBitsToFloat(floatBitsToUint(r) - 1u) : r;\n"
"}\n"
"vec2 ffTwoProd(float a, float b) {\n"
"  precise float p = a * b;\n"
"  precise float ca = 4097.0 * a;\n"
"  precise float ah = ca - (ca - a);\n"
"  precise float al = a - ah;\n"
"  precise float cb = 4097.0 * b;\n"
"  precise float bh = cb - (cb - b);\n"
"  precise float bl = b - bh;\n"
"  precise float e = (((ah * bh - p) + ah * bl) + al * bh) + al * bl;\n"
"  return vec2(p, e);\n"
"}\n"
"float ffMulRtz(float a, float b) {\n"
"  if (!(abs(a) < 1e34 && abs(b) < 1e34)) { return a * b; }\n"
"  vec2 pe = ffTwoProd(a, b);\n"
"  return ffRtz(pe.x, pe.y);\n"
"}\n"
"float ffAddRtz(float a, float b) {\n"
"  precise float s = a + b;\n"
"  precise float bb = s - a;\n"
"  precise float e = (a - (s - bb)) + (b - bb);\n"
"  return ffRtz(s, e);\n"
"}\n"
"float ffDotRtz(vec4 v, vec4 m) {\n"
"  float acc = ffMulRtz(v.x, m.x);\n"
"  acc = ffAddRtz(acc, ffMulRtz(v.y, m.y));\n"
"  acc = ffAddRtz(acc, ffMulRtz(v.z, m.z));\n"
"  return ffAddRtz(acc, ffMulRtz(v.w, m.w));\n"
"}\n"
"bool ffAboveOne(float w, float r) {\n"
"  vec2 pe = ffTwoProd(w, r);\n"
"  return pe.x > 1.0 || (pe.x == 1.0 && pe.y > 0.0);\n"
"}\n"
"float ffRcpRtz(float w) {\n"
"  float aw = abs(w);\n"
"  precise float r = 1.0 / aw;\n"
"  if (aw > 1e-34 && aw < 1e34) {\n"
"    for (int i = 0; i < 3; i++) {\n"
"      if (ffAboveOne(aw, r)) { r = uintBitsToFloat(floatBitsToUint(r) - 1u); }\n"
"    }\n"
"    for (int i = 0; i < 3; i++) {\n"
"      float rn = uintBitsToFloat(floatBitsToUint(r) + 1u);\n"
"      if (!ffAboveOne(aw, rn)) { r = rn; }\n"
"    }\n"
"  }\n"
"  return w < 0.0 ? -r : r;\n"
"}\n"
"float ffScreenZ(vec4 p) {\n"
"  mat4 cm = compositeMat;\n"
"  float w = clampAwayZeroInf(ffDotRtz(p, cm[3]));\n"
"  return ffMulRtz(ffDotRtz(p, cm[2]), ffRcpRtz(w));\n"
"}\n"
"\n");

    append_lighting_header(header);

    unsigned int count;
    bool mix;
    switch (state->fixed_function.skinning) {
    case SKINNING_OFF:
        mix = false; count = 0; break;
    case SKINNING_1WEIGHTS:
        mix = true; count = 2; break;
    case SKINNING_2WEIGHTS2MATRICES:
        mix = false; count = 2; break;
    case SKINNING_2WEIGHTS:
        mix = true; count = 3; break;
    case SKINNING_3WEIGHTS3MATRICES:
        mix = false; count = 3; break;
    case SKINNING_3WEIGHTS:
        mix = true; count = 4; break;
    case SKINNING_4WEIGHTS4MATRICES:
        mix = false; count = 4; break;
    default:
        assert(false);
        break;
    }
    mstring_append_fmt(body, "/* Skinning mode %d */\n",
                       state->fixed_function.skinning);

    append_skinning_code(body, mix, count, "vec4",
                         "tPosition", "position",
                         "modelViewMat", "xyzw");
    append_skinning_code(body, mix, count, "vec3",
                         "tNormal", "vec4(normal, 0.0)",
                         "invModelViewMat", "xyz");

    if (state->normalization) {
        mstring_append(body, "tNormal = normalize(tNormal);\n");
    }

    for (i = 0; i < NV2A_MAX_TEXTURES; i++) {
        mstring_append_fmt(body, "/* Texgen for stage %d */\n",
                           i);
        /* Set each component individually */
        /* FIXME: could be nicer if some channels share the same texgen */
        for (j = 0; j < 4; j++) {
            /* TODO: TexGen View Model missing! */
            char c = "xyzw"[j];
            char cSuffix = "STRQ"[j];
            switch (state->fixed_function.texgen[i][j]) {
            case TEXGEN_DISABLE:
                mstring_append_fmt(body, "oT%d.%c = texture%d.%c;\n",
                                   i, c, i, c);
                break;
            case TEXGEN_EYE_LINEAR:
                mstring_append_fmt(body, "oT%d.%c = dot(texPlane%c%d, tPosition);\n",
                                   i, c, cSuffix, i);
                break;
            case TEXGEN_OBJECT_LINEAR:
                mstring_append_fmt(body, "oT%d.%c = dot(texPlane%c%d, position);\n",
                                   i, c, cSuffix, i);
                break;
            case TEXGEN_SPHERE_MAP:
                assert(j < 2);  /* Channels S,T only! */
                mstring_append(body, "{\n");
                /* FIXME: u, r and m only have to be calculated once */
                mstring_append(body, "  vec3 u = normalize(tPosition.xyz);\n");
                //FIXME: tNormal before or after normalization? Always normalize?
                mstring_append(body, "  vec3 r = reflect(u, tNormal);\n");

                /* FIXME: This would consume 1 division fewer and *might* be
                 *        faster than length:
                 *   // [z=1/(2*x) => z=1/x*0.5]
                 *   vec3 ro = r + vec3(0.0, 0.0, 1.0);
                 *   float m = inversesqrt(dot(ro,ro))*0.5;
                 */

                mstring_append(body, "  float invM = 1.0 / (2.0 * length(r + vec3(0.0, 0.0, 1.0)));\n");
                mstring_append_fmt(body, "  oT%d.%c = r.%c * invM + 0.5;\n",
                                   i, c, c);
                mstring_append(body, "}\n");
                break;
            case TEXGEN_REFLECTION_MAP:
                assert(j < 3); /* Channels S,T,R only! */
                mstring_append(body, "{\n");
                /* FIXME: u and r only have to be calculated once, can share the one from SPHERE_MAP */
                mstring_append(body, "  vec3 u = normalize(tPosition.xyz);\n");
                mstring_append(body, "  vec3 r = reflect(u, tNormal);\n");
                mstring_append_fmt(body, "  oT%d.%c = r.%c;\n",
                                   i, c, c);
                mstring_append(body, "}\n");
                break;
            case TEXGEN_NORMAL_MAP:
                assert(j < 3); /* Channels S,T,R only! */
                mstring_append_fmt(body, "oT%d.%c = tNormal.%c;\n",
                                   i, c, c);
                break;
            default:
                assert(false);
                break;
            }
        }
    }

    for (i = 0; i < NV2A_MAX_TEXTURES; i++) {
        if (state->fixed_function.texture_matrix_enable[i]) {
            mstring_append_fmt(body,
                               "oT%d = oT%d * texMat%d;\n",
                               i, i, i);
        }
    }

    if (!state->lighting) {
        mstring_append(body, "  oD0 = diffuse;\n");
        mstring_append(body, "  oD1 = specular;\n");
        /* The back colours are not the back vertex colours: with lighting
         * off the fixed function pipeline hands a back-facing fragment
         * black with the alpha at one (Specular back
         * ControlFlagsLightDisable_FF golden). */
        mstring_append(body, "  oB0 = vec4(0.0, 0.0, 0.0, 1.0);\n");
        mstring_append(body, "  oB1 = vec4(0.0, 0.0, 0.0, 1.0);\n");
    } else {
        /* The vertex colours enter the lighting unit at its precision. */
        mstring_append(body, "  vec4 ltDiffuse = lt(diffuse);\n"
                             "  vec4 ltSpecular = lt(specular);\n");
        struct LightingSide front = {
            .normal = "tNormal",
            .diffuse_out = "oD0",
            .specular_out = "oD1",
            .ambient_color = "lightAmbientColor",
            .diffuse_color = "lightDiffuseColor",
            .specular_color = "lightSpecularColor",
            .constant = "sceneAmbientColor",
            .factor = "materialEmissionColor",
            .material_alpha = "material_alpha",
            .specular_params = 0,
            .fold_specular = !state->specular_enable || !state->separate_specular,
            .emission_src = state->emission_src,
            .ambient_src = state->ambient_src,
            .diffuse_src = state->diffuse_src,
            .specular_src = state->specular_src,
        };
        append_lighting(state, body, &front, "diffuse.a", "specular.a");

        /* Two-sided lighting lights the back face the same way with the
         * normal turned around and every register swapped for its back
         * counterpart: the back light colours, the back constant term and
         * factor (which D3D leaves at zero, so the Lighting Two Sided
         * golden shows no scene ambient on the back), the back material
         * alpha, the back specular parameters and the back colour material
         * selectors. The vertex colours a selector can pick are the same
         * front ones. */
        if (state->two_side_light) {
            struct LightingSide back = {
                .normal = "-tNormal",
                .diffuse_out = "oB0",
                .specular_out = "oB1",
                .ambient_color = "lightBackAmbientColor",
                .diffuse_color = "lightBackDiffuseColor",
                .specular_color = "lightBackSpecularColor",
                .constant = "backSceneAmbientColor",
                .factor = "backMaterialEmissionColor",
                .material_alpha = "material_alpha_back",
                .specular_params = 2,
                .fold_specular = !state->specular_enable || !state->separate_specular,
                .emission_src = state->back_emission_src,
                .ambient_src = state->back_ambient_src,
                .diffuse_src = state->back_diffuse_src,
                .specular_src = state->back_specular_src,
            };
            append_lighting(state, body, &back, "diffuse.a", "specular.a");
        }
    }

    /* The lit specular only leaves the unit on its own output with both
     * SPECULAR_ENABLE and SEPARATE_SPECULAR set. Otherwise it is folded
     * into the diffuse inside the unit, light by light (fold_specular in
     * the light loop, envytools' !spec_out), with SPECULAR_ENABLE off as
     * much as with
     * SEPARATE_SPECULAR off, and the specular output is the front vertex
     * colour, for the back face as well (Specular back ControlFlags_FF
     * golden), or, with specular disabled, black with the alpha at one.
     * The fold carries the sign: beyond the pole of the rational
     * evaluator (a normal longer than one takes N.H past it) the factor
     * is negative, the separate output clamps it away but the fold
     * subtracts it from the ambient. The Lighting control goldens show
     * both: with SEPARATE_SPECULAR off or SPECULAR_ENABLE off the
     * highlight is added to the diffuse, and on the sphere and cylinder,
     * whose normals are longer than one, the ambient disappears where the
     * highlight would be beyond the pole. */
    if (!state->specular_enable) {
        mstring_append(body, "  oD1 = vec4(0.0, 0.0, 0.0, 1.0);\n");
        mstring_append(body, "  oB1 = vec4(0.0, 0.0, 0.0, 1.0);\n");
    } else {
        if (!state->separate_specular) {
            mstring_append(body, "  oD1 = specular;\n");
            if (state->lighting) {
                mstring_append(body, "  oB1 = specular;\n");
            }
        }
        if (state->ignore_specular_alpha) {
            mstring_append(body,
                           "  oD1.a = 1.0;\n"
                           "  oB1.a = 1.0;\n");
        }
    }

    if (state->fog_enable) {
        /* From: https://www.opengl.org/registry/specs/NV/fog_distance.txt */
        switch(state->foggen) {
        case FOGGEN_SPEC_ALPHA:
            /* FIXME: Do we have to clamp here? */
            mstring_append(body, "  float fogDistance = clamp(specular.a, 0.0, 1.0);\n");
            break;
        case FOGGEN_RADIAL:
            mstring_append(body, "  float fogDistance = length(tPosition.xyz);\n");
            break;
        case FOGGEN_PLANAR:
        case FOGGEN_ABS_PLANAR:
            mstring_append(body, "  float fogDistance = dot(fogPlane.xyz, tPosition.xyz) + fogPlane.w;\n");
            if (state->foggen == FOGGEN_ABS_PLANAR) {
                mstring_append(body, "  fogDistance = abs(fogDistance);\n");
            }
            break;
        case FOGGEN_FOG_X:
            mstring_append(body, "  float fogDistance = fogCoord;\n");
            break;
        default:
            assert(!"Invalid foggen mode");
            break;
        }

    }

    /* If skinning is off the composite matrix already includes the MV matrix */
    if (state->fixed_function.skinning == SKINNING_OFF) {
        mstring_append(body, "  tPosition = position;\n");
    }

    mstring_append(body,
    "  oPos = tPosition * compositeMat;\n"
    /* nv2a's multiply gives 0 for 0 * anything (vsh-prog.c _MUL); GLSL's
     * gives NaN for 0 * inf, which a w of +-inf puts in x, y and z.  Only
     * taken for a non-finite input, so finite vertices are bit-identical.
     * compositeMat is a mat4(...) constructor macro, hence cm. */
    "  if (any(isinf(tPosition)) || any(isnan(tPosition))) {\n"
    "    mat4 cm = compositeMat;\n"
    "    for (int j = 0; j < 4; j++) {\n"
    "      vec4 p = tPosition * cm[j];\n"
    "      for (int i = 0; i < 4; i++) {\n"
    "        if (tPosition[i] == 0.0 || cm[j][i] == 0.0) { p[i] = 0.0; }\n"
    "      }\n"
    "      oPos[j] = p.x + p.y + p.z + p.w;\n"
    "    }\n"
    "  }\n"
    "  oPos.w = clampAwayZeroInf(oPos.w);\n"
    "  vec2 hPos = oPos.xy;\n"
    "  vec2 scrPos = oPos.xy / oPos.w + c[" stringify(NV_IGRAPH_XF_XFCTX_VPOFF) "].xy;\n"
    "  oPos.xy = roundScreenCoords(scrPos);\n"
    "  vec4 vtxPos = vec4(oPos.xy, oPos.z / oPos.w, oPos.w);\n"
    "  oPos.z = oPos.z / clipRange.y;\n"
    "  oPos.xy = (2.0 * oPos.xy - surfaceSize) / surfaceSize;\n"
    "  oPos.xy *= oPos.w;\n"
    /* roundScreenCoords is the identity for |pos| >= 2^19, and pos * 16
     * overflows past 2^124 (W_param ff_w_zero_inf, #223): there, carry the
     * position homogeneously, as the rasteriser receives it, instead of
     * through the divide.  The bvec mix is a select, so the unselected
     * operand may be inf or NaN. */
    "  bvec2 carry = not(lessThan(abs(scrPos), vec2(524288.0)));\n"
    "  oPos.xy = mix(oPos.xy, 2.0 * hPos / surfaceSize\n"
    "      + (2.0 * c[" stringify(NV_IGRAPH_XF_XFCTX_VPOFF) "].xy / surfaceSize - 1.0) * oPos.w,\n"
    "      carry);\n"
    );

    /* The depth the rasteriser interpolates, in silicon's arithmetic (see
     * ffScreenZ above). Only vtxPos.z: w, and so W buffering and the
     * perspective-correct varyings, are untouched, as is the GL clip z.
     *
     * Not on F24 (clipRange.y is f24_max there). Its near-plane vertex z is
     * exactly 0 under RTZ, so it passes the depth clip, and our rasteriser
     * then draws zero-depth edges that silicon does not. That took the 20
     * z24 FZy Depth buffer fixed function captures from 24 px to 403-406
     * each. docs/lanes/zrtz272/NOTES.md. */
    mstring_append(body,
    "  if (clipRange.y <= 16777216.0\n"
    "      && !(any(isinf(tPosition)) || any(isnan(tPosition)))) {\n"
    "    vtxPos.z = ffScreenZ(tPosition);\n"
    "  }\n");

    if (state->point_params_enable) {
        mstring_append(
            body,
            "  float d_e = length(position * modelViewMat0);\n"
            "  float ptMinSize = min(pointParams[7], 63.875);\n"
            "  float ptMaxSize = min(pointParams[3] + ptMinSize, 63.875);\n"
            "  oPts.x = 1.0 / sqrt(pointParams[0] + pointParams[1] * d_e + pointParams[2] * d_e * d_e) + pointParams[6];\n");
        mstring_append_fmt(body,
                           "  oPts.x = clamp(oPts.x * pointParams[3] + pointParams[7], ptMinSize, ptMaxSize) * float(%d);\n",
                           state->surface_scale_factor);
    } else {
        mstring_append_fmt(body, "  oPts.x = %f * float(%d);\n",
                           MAX(1.f, state->point_size),
                           state->surface_scale_factor);
    }
}
