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

static const char *vertex_color_scale(enum MaterialColorSource src)
{
    switch (src) {
    case MATERIAL_COLOR_SRC_DIFFUSE: return "ltDiffuse.xyz * ";
    case MATERIAL_COLOR_SRC_SPECULAR: return "ltSpecular.xyz * ";
    default: return "";
    }
}

/* Emits the lighting of one face into its two colour outputs. */
static void append_lighting(const VshState *state, MString *body,
                            const struct LightingSide *side)
{
    const char *alpha_source = "diffuse.a";
    if (side->diffuse_src == MATERIAL_COLOR_SRC_MATERIAL) {
        alpha_source = side->material_alpha;
    } else if (side->diffuse_src == MATERIAL_COLOR_SRC_SPECULAR) {
        alpha_source = "specular.a";
    }

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
        mstring_append_fmt(body, "  %s.rgb += %s * %s;\n",
                           side->diffuse_out, scaled, side->factor);
    }
    mstring_append_fmt(body, "  %s = vec4(0.0, 0.0, 0.0, specular.a);\n",
                       side->specular_out);

    mstring_append_fmt(body, "  {\n  vec3 N = %s;\n", side->normal);
    if (state->fixed_function.local_eye) {
        mstring_append(body,
            "  vec3 VPeye = normalize(eyePosition.xyz / eyePosition.w - tPosition.xyz / tPosition.w);\n"
        );
    }

    for (int i = 0; i < NV2A_MAX_LIGHTS; i++) {
        if (state->fixed_function.light[i] == LIGHT_OFF) {
            continue;
        }

        mstring_append_fmt(body, "  /* Light %d */ {\n", i);

        if (state->fixed_function.light[i] == LIGHT_LOCAL
                || state->fixed_function.light[i] == LIGHT_SPOT) {

            /* The lighting unit's reciprocal of zero is infinity, and
             * its multiply gives zero for zero times anything, so a light
             * with all three attenuation values at zero lights every
             * channel its colour is nonzero in and none it is zero in
             * (the Lighting spotlight AtFixed 0/0/0 golden). A large
             * finite value has the same effect in GLSL, where zero times
             * infinity would be NaN. Without a local eye the half vector
             * is built from the eye direction register, not from a zero
             * vector. */
            mstring_append_fmt(body,
                "  vec3 tPos = tPosition.xyz/tPosition.w;\n"
                "  vec3 VP = lightLocalPosition[%d] - tPos;\n"
                "  float d = length(VP);\n"
                "  if (d <= lightLocalRange(%d)) {\n"  /* FIXME: Double check that range is inclusive */
                "    VP = normalize(VP);\n"
                "    float attDen = lightLocalAttenuation[%d].x\n"
                "                   + lightLocalAttenuation[%d].y * d\n"
                "                   + lightLocalAttenuation[%d].z * d * d;\n"
                "    float attenuation = attDen == 0.0 ? FLOAT_MAX : 1.0 / attDen;\n"
                "    vec3 halfVector = normalize(VP + %s);\n"
                "    float nDotVP = max(0.0, dot(N, VP));\n"
                "    float nDotHV = max(0.0, dot(N, halfVector));\n",
                i, i, i, i, i,
                state->fixed_function.local_eye ? "VPeye" : "eyeDirection"
            );
        }

        switch(state->fixed_function.light[i]) {
        case LIGHT_INFINITE:

            /* lightLocalRange will be 1e+30 here */

            /* The direction register is used as it is, like the half
             * vector register: D3D normalises before writing it, and
             * with an unnormalised one the diffuse scales by its length
             * (the Specular ControlFlags_FF golden lights its quads with
             * (1, 0, 1) and their diffuse is that of a unit vector times
             * the square root of two, saturating on one side). */
            mstring_append_fmt(body,
                "  {\n"
                "    float attenuation = 1.0;\n"
                "    vec3 lightDirection = lightInfiniteDirection[%d];\n"
                "    float nDotVP = max(0.0, dot(N, lightDirection));\n",
                i);
            if (state->fixed_function.local_eye) {
                mstring_append(body,
                    "    float nDotHV = max(0.0, dot(N, normalize(lightDirection + VPeye)));\n"
                );
            } else {
                mstring_append_fmt(body,
                    "    float nDotHV = max(0.0, dot(N, lightInfiniteHalfVector[%d]));\n",
                    i
                );
            }
            break;
        case LIGHT_LOCAL:
            /* Everything done already */
            break;
        case LIGHT_SPOT:
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
             * reproduce. */
            mstring_append_fmt(body,
                "    vec4 spotDir = lightSpotDirection(%d);\n"
                "    vec3 spotK = lightSpotFalloff(%d);\n"
                "    float spotX = min(dot(spotDir.xyz, VP) + spotDir.w, 1.0);\n"
                "    float spotN = spotX + spotK.x;\n"
                "    float spotD = spotX * spotK.y + spotK.z;\n"
                "    float spotS = spotD == 0.0 ? FLOAT_MAX : spotN / spotD;\n"
                "    attenuation = spotN <= 0.0 ? 0.0 : ltMul(attenuation, spotS);\n",
                i, i);
            break;
        default:
            assert(false);
            break;
        }

        /* The specular power is not a pow(). The lighting unit evaluates
         * a rational function of the half-vector dot product with three
         * coefficients, S = (x + k0) / (x k1 + k2), zero once the
         * numerator goes negative; that is the form D3D's specular
         * tables are fitted to and the Specular goldens follow. Which
         * three depends on the half vector: an infinite light seen by a
         * non-local eye has its half vector precomputed and normalised,
         * and uses the first triple on x = N.H; everything else builds
         * the half vector per vertex and uses the second triple, fitted
         * for half the power, on x = (N.H)^2, which is what falls out of
         * the unnormalised sum without a square root. */
        bool half_precomputed = state->fixed_function.light[i] == LIGHT_INFINITE &&
                                !state->fixed_function.local_eye;
        mstring_append_fmt(body,
            "    float pf;\n"
            "    if (nDotVP == 0.0 || nDotHV == 0.0) {\n"
            "      pf = 0.0;\n"
            "    } else {\n"
            "      pf = specularFactor(%s, specularParams[%d]);\n"
            "    }\n"
            "    vec3 lightAmbient = ltMul(%s(%d), attenuation);\n"
            "    vec3 lightDiffuse = ltMul(%s(%d), ltMul(attenuation, nDotVP));\n"
            "    vec3 lightSpecular = ltMul(%s(%d), ltMul(attenuation, pf));\n",
            half_precomputed ? "nDotHV" : "nDotHV * nDotHV",
            side->specular_params + (half_precomputed ? 0 : 1),
            side->ambient_color, i, side->diffuse_color, i,
            side->specular_color, i);

        mstring_append_fmt(body,
                           "    %s.xyz += %slightAmbient;\n"
                           "    %s.xyz += %slightDiffuse;\n"
                           "    %s.xyz += %slightSpecular;\n",
                           side->diffuse_out, vertex_color_scale(side->ambient_src),
                           side->diffuse_out, vertex_color_scale(side->diffuse_src),
                           side->specular_out, vertex_color_scale(side->specular_src));

        mstring_append(body, "  }\n"
                             "  }\n");
    }
    mstring_append(body, "  }\n");
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

    /* See the light loop below for what these model. The lighting unit's
     * multiply gives zero for zero times anything, its reciprocal of zero
     * is infinity, and nothing is clamped before the colour sum. FLOAT_MAX
     * stands in for that infinity so that a zero factor stays zero in GLSL
     * instead of becoming NaN, and every product is held to it so that two
     * of them multiplied together cannot overflow past it. */
    /* The lighting unit works on floats with a 13-bit fraction: the
     * Celsius transform model converts every value it takes in by
     * dropping the low ten bits of the float32 fraction, and its multiply
     * and add truncate towards zero as well. lt() drops the registers and
     * the vertex colours to that precision on their way in; the arithmetic
     * that follows is still float32, so the last count can still differ.
     * Five lights with an ambient of 0.1 sum to 127 on the hardware, not
     * 128 (Lighting accumulation Directional-5), which no rounding of the
     * float32 sum produces. */
    mstring_append(header,
        "float lt(float x) { return uintBitsToFloat(floatBitsToUint(x) & 0xFFFFFC00u); }\n"
        "vec3 lt(vec3 v) { return uintBitsToFloat(floatBitsToUint(v) & 0xFFFFFC00u); }\n"
        "vec4 lt(vec4 v) { return uintBitsToFloat(floatBitsToUint(v) & 0xFFFFFC00u); }\n"
        "float specularFactor(float x, vec3 k) {\n"
        "  float n = x + k.x;\n"
        "  float d = x * k.y + k.z;\n"
        "  if (n <= 0.0) return 0.0;\n"
        "  return d == 0.0 ? FLOAT_MAX : n / d;\n"
        "}\n"
        "float ltMul(float a, float b) {\n"
        "  return (a == 0.0 || b == 0.0) ? 0.0 : clamp(a * b, -FLOAT_MAX, FLOAT_MAX);\n"
        "}\n"
        "vec3 ltMul(vec3 c, float s) {\n"
        "  return mix(clamp(c * s, vec3(-FLOAT_MAX), vec3(FLOAT_MAX)), vec3(0.0),\n"
        "             equal(c, vec3(0.0)));\n"
        "}\n");

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

    if (state->fixed_function.normalization) {
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

    if (!state->fixed_function.lighting) {
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
            .emission_src = state->fixed_function.emission_src,
            .ambient_src = state->fixed_function.ambient_src,
            .diffuse_src = state->fixed_function.diffuse_src,
            .specular_src = state->fixed_function.specular_src,
        };
        append_lighting(state, body, &front);

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
                .emission_src = state->fixed_function.back_emission_src,
                .ambient_src = state->fixed_function.back_ambient_src,
                .diffuse_src = state->fixed_function.back_diffuse_src,
                .specular_src = state->fixed_function.back_specular_src,
            };
            append_lighting(state, body, &back);
        }
    }

    /* The lit specular only leaves the unit on its own output with both
     * SPECULAR_ENABLE and SEPARATE_SPECULAR set. Otherwise it is folded
     * into the diffuse, with SPECULAR_ENABLE off as much as with
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
    if (state->fixed_function.lighting &&
        (!state->specular_enable || !state->separate_specular)) {
        mstring_append(body,
                       "  oD0.xyz += oD1.xyz;\n"
                       "  oB0.xyz += oB1.xyz;\n");
    }
    if (!state->specular_enable) {
        mstring_append(body, "  oD1 = vec4(0.0, 0.0, 0.0, 1.0);\n");
        mstring_append(body, "  oB1 = vec4(0.0, 0.0, 0.0, 1.0);\n");
    } else {
        if (!state->separate_specular) {
            mstring_append(body, "  oD1 = specular;\n");
            if (state->fixed_function.lighting) {
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
        switch(state->fixed_function.foggen) {
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
            if (state->fixed_function.foggen == FOGGEN_ABS_PLANAR) {
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
    "  oPos.w = clampAwayZeroInf(oPos.w);\n"
    "  oPos.xy /= oPos.w;\n"
    "  oPos.xy += c[" stringify(NV_IGRAPH_XF_XFCTX_VPOFF) "].xy;\n"
    "  oPos.xy = roundScreenCoords(oPos.xy);\n"
    "  vec4 vtxPos = vec4(oPos.xy, oPos.z / oPos.w, oPos.w);\n"
    "  oPos.z = oPos.z / clipRange.y;\n"
    "  oPos.xy = (2.0 * oPos.xy - surfaceSize) / surfaceSize;\n"
    "  oPos.xy *= oPos.w;\n"
    );

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
