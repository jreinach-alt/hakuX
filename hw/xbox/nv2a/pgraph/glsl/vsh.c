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
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#ifdef __ANDROID__
#include <android/log.h>
#endif
#include "vsh.h"
#include "vsh-ff.h"
#include "vsh-prog.h"

DEF_UNIFORM_INFO_ARR(VshUniform, VSH_UNIFORM_DECL_X)

static void set_fixed_function_vsh_state(PGRAPHState *pg,
                                         FixedFunctionVshState *state)
{
    state->skinning = (enum VshSkinning)GET_MASK(
        pgraph_reg_r(pg, NV_PGRAPH_CSV0_D), NV_PGRAPH_CSV0_D_SKIN);

    for (int i = 0; i < 4; i++) {
        state->texture_matrix_enable[i] = pg->texture_matrix_enable[i];
    }

    for (int i = 0; i < 4; i++) {
        unsigned int reg = (i < 2) ? NV_PGRAPH_CSV1_A : NV_PGRAPH_CSV1_B;
        for (int j = 0; j < 4; j++) {
            unsigned int masks[] = {
                (i % 2) ? NV_PGRAPH_CSV1_A_T1_S : NV_PGRAPH_CSV1_A_T0_S,
                (i % 2) ? NV_PGRAPH_CSV1_A_T1_T : NV_PGRAPH_CSV1_A_T0_T,
                (i % 2) ? NV_PGRAPH_CSV1_A_T1_R : NV_PGRAPH_CSV1_A_T0_R,
                (i % 2) ? NV_PGRAPH_CSV1_A_T1_Q : NV_PGRAPH_CSV1_A_T0_Q
            };
            state->texgen[i][j] =
                (enum VshTexgen)GET_MASK(pgraph_reg_r(pg, reg), masks[j]);
        }
    }


}

static void set_programmable_vsh_state(PGRAPHState *pg,
                                       ProgrammableVshState *prog)
{
    int program_start = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_C),
                                 NV_PGRAPH_CSV0_C_CHEOPS_PROGRAM_START);

    prog->program_length = 0;
    for (int i = program_start; i < NV2A_MAX_TRANSFORM_PROGRAM_LENGTH; i++) {
        uint32_t *cur_token = (uint32_t *)&pg->program_data[i];
        memcpy(&prog->program_data[prog->program_length], cur_token,
               VSH_TOKEN_SIZE * sizeof(uint32_t));
        prog->program_length++;

        if (vsh_get_field(cur_token, FLD_FINAL)) {
            break;
        }
    }
}

void pgraph_glsl_set_vsh_state(PGRAPHState *pg, VshState *vsh)
{
    bool vertex_program = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_D),
                                   NV_PGRAPH_CSV0_D_MODE) == 2;

    bool fixed_function = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_D),
                                   NV_PGRAPH_CSV0_D_MODE) == 0;

    assert(vertex_program || fixed_function);

    vsh->surface_scale_factor = pg->surface_scale_factor; // FIXME

    vsh->compressed_attrs = pg->compressed_attrs;
    vsh->uniform_attrs = pg->uniform_attrs;
    vsh->swizzle_attrs = pg->swizzle_attrs;

    vsh->specular_enable = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_C),
                                    NV_PGRAPH_CSV0_C_SPECULAR_ENABLE);
    vsh->separate_specular = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_C),
                                      NV_PGRAPH_CSV0_C_SEPARATE_SPECULAR);
    vsh->ignore_specular_alpha =
        !GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_C),
                  NV_PGRAPH_CSV0_C_ALPHA_FROM_MATERIAL_SPECULAR);
    vsh->two_side_light = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_C),
                                   NV_PGRAPH_CSV0_C_TWO_SIDE_LIGHT_EN);

    vsh->z_perspective = pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) &
                         NV_PGRAPH_CONTROL_0_Z_PERSPECTIVE_ENABLE;
    vsh->noperspective = !(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) &
                           NV_PGRAPH_CONTROL_0_TEXTUREPERSPECTIVE);

    vsh->point_params_enable = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_D),
                                        NV_PGRAPH_CSV0_D_POINTPARAMSENABLE);
    vsh->point_size = pgraph_reg_r(pg, NV_PGRAPH_POINTSIZE) / 8.0f;
    if (vsh->point_params_enable) {
        for (int i = 0; i < 8; i++) {
            vsh->point_params[i] = pg->point_params[i];
        }
    }

    vsh->smooth_shading = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_3),
                                   NV_PGRAPH_CONTROL_3_SHADEMODE) ==
                          NV_PGRAPH_CONTROL_3_SHADEMODE_SMOOTH;

    vsh->fog_enable =
        pgraph_reg_r(pg, NV_PGRAPH_CONTROL_3) & NV_PGRAPH_CONTROL_3_FOGENABLE;
    vsh->emission_src = (enum MaterialColorSource)GET_MASK(
        pgraph_reg_r(pg, NV_PGRAPH_CSV0_C), NV_PGRAPH_CSV0_C_EMISSION);
    vsh->ambient_src = (enum MaterialColorSource)GET_MASK(
        pgraph_reg_r(pg, NV_PGRAPH_CSV0_C), NV_PGRAPH_CSV0_C_AMBIENT);
    vsh->diffuse_src = (enum MaterialColorSource)GET_MASK(
        pgraph_reg_r(pg, NV_PGRAPH_CSV0_C), NV_PGRAPH_CSV0_C_DIFFUSE);
    vsh->specular_src = (enum MaterialColorSource)GET_MASK(
        pgraph_reg_r(pg, NV_PGRAPH_CSV0_C), NV_PGRAPH_CSV0_C_SPECULAR);
    vsh->back_emission_src =
        (enum MaterialColorSource)((pg->color_material_back >> 0) & 3);
    vsh->back_ambient_src =
        (enum MaterialColorSource)((pg->color_material_back >> 2) & 3);
    vsh->back_diffuse_src =
        (enum MaterialColorSource)((pg->color_material_back >> 4) & 3);
    vsh->back_specular_src =
        (enum MaterialColorSource)((pg->color_material_back >> 6) & 3);
    vsh->lighting =
        GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_C), NV_PGRAPH_CSV0_C_LIGHTING);
    vsh->normalization = pgraph_reg_r(pg, NV_PGRAPH_CSV0_C) &
                         NV_PGRAPH_CSV0_C_NORMALIZATION_ENABLE;
    vsh->local_eye =
        GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_C), NV_PGRAPH_CSV0_C_LOCALEYE);
    if (vsh->lighting) {
        for (int i = 0; i < NV2A_MAX_LIGHTS; i++) {
            vsh->light[i] =
                (enum VshLight)GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CSV0_D),
                                        NV_PGRAPH_CSV0_D_LIGHT0 << (i * 2));
        }
    }
    if (vsh->fog_enable) {
        vsh->foggen = (enum VshFoggen)GET_MASK(
            pgraph_reg_r(pg, NV_PGRAPH_CSV0_D), NV_PGRAPH_CSV0_D_FOGGENMODE);
    }

    vsh->is_fixed_function = fixed_function;
    if (fixed_function) {
        set_fixed_function_vsh_state(pg, &vsh->fixed_function);
    } else {
        set_programmable_vsh_state(pg, &vsh->programmable);
    }
}

/* Output register index of oFog, mirroring vsh-prog.c's decoder. */
#define VSH_OUTPUT_REG_FOG 5

/*
 * Map a program's constant register field onto an index into vsh_constants,
 * the same way vsh-prog.c's convert_c_register() does for the generated
 * code.  Kept in step with it by hand: that one is file-static, and
 * vsh-prog.c is the program translator rather than a shared header.
 */
static int vsh_constant_index(uint8_t c_reg)
{
    int16_t r = ((((c_reg >> 5) & 7) - 3) * 32) + (c_reg & 31);
    r += VSH_D3DSCM_CORRECTION; /* to map -96..95 to 0..191 */
    return r;
}

/* Does this instruction land a value in the fog output register? */
static bool vsh_token_writes_fog(const uint32_t *token)
{
    if (vsh_get_field(token, FLD_OUT_O_MASK) == 0) {
        return false;
    }
    if (vsh_get_field(token, FLD_OUT_ORB) != OUTPUT_O) {
        return false;
    }
    if ((vsh_get_field(token, FLD_OUT_ADDRESS) & 0xf) != VSH_OUTPUT_REG_FOG) {
        return false;
    }

    /* Only the unit the output mux selects reaches the register. */
    if (vsh_get_field(token, FLD_OUT_MUX) == OMUX_MAC) {
        return vsh_get_field(token, FLD_MAC) != MAC_NOP;
    }
    return vsh_get_field(token, FLD_ILU) != ILU_NOP;
}

/*
 * Classify a single instruction's write to oFog.
 *
 * Only a MOV copies a source component through unchanged, so only a MOV
 * leaves a value the CPU can read back.  MAC_MOV reads input A; every ILU
 * opcode reads input C.  The generated code is
 * `MOV(oFog, <mask>, <src><swizzle>)`, which expands to
 * `oFog.<mask> = _MOV(_in(src)).<mask>` (vsh-prog.c), and every non-empty
 * fog write mask begins at x -- that is the "most significant masked
 * component applies to x" rule the fog_mask_str table implements.  So
 * oFog.x receives the source component the x swizzle slot selects,
 * whatever the destination mask is.
 */
static VshFogWrite vsh_classify_fog_write(const uint32_t *token,
                                          const VshState *state)
{
    VshFogWrite w = { .kind = VSH_FOG_WRITE_COMPUTED };

    VshFieldName neg_field;
    VshParameterType param;

    if (vsh_get_field(token, FLD_OUT_MUX) == OMUX_MAC) {
        if (vsh_get_field(token, FLD_MAC) != MAC_MOV) {
            return w;
        }
        neg_field = FLD_A_NEG;
        param = (VshParameterType)vsh_get_field(token, FLD_A_MUX);
    } else {
        if (vsh_get_field(token, FLD_ILU) != ILU_MOV) {
            return w;
        }
        neg_field = FLD_C_NEG;
        param = (VshParameterType)vsh_get_field(token, FLD_C_MUX);
    }

    /* The swizzle fields sit immediately after the negate bit, x first. */
    w.component = vsh_get_field(token, neg_field + 1);
    w.negate = vsh_get_field(token, neg_field) > 0;

    switch (param) {
    case PARAM_C:
        if (vsh_get_field(token, FLD_A0X) > 0) {
            /* c[A0+n]: the index is only known once the program runs. */
            return w;
        }
        w.reg = vsh_constant_index(vsh_get_field(token, FLD_CONST));
        if (w.reg < 0 || w.reg >= NV2A_VERTEXSHADER_CONSTANTS) {
            return w;
        }
        w.kind = VSH_FOG_WRITE_CONST;
        return w;

    case PARAM_V:
        w.reg = vsh_get_field(token, FLD_V);
        if (w.reg >= NV2A_VERTEXSHADER_ATTRIBUTES) {
            return w;
        }
        /*
         * A compressed or D3D-swizzled attribute reaches the shader
         * through a conversion the stored attribute value has not had
         * applied, so its components no longer line up.
         */
        if (state->compressed_attrs & (1 << w.reg)) {
            return w;
        }
        if (state->swizzle_attrs & (1 << w.reg)) {
            return w;
        }
        w.kind = VSH_FOG_WRITE_ATTR;
        return w;

    default:
        /* A temporary register holds whatever the program computed. */
        return w;
    }
}

VshFogWrite pgraph_glsl_vsh_fog_write(const VshState *state)
{
    VshFogWrite w = { .kind = VSH_FOG_WRITE_NONE };

    if (state->is_fixed_function) {
        /*
         * The transform unit always produces a coordinate, from FOGGEN and
         * the transformed position -- never absent, never CPU-readable.
         */
        w.kind = VSH_FOG_WRITE_COMPUTED;
        return w;
    }

    const ProgrammableVshState *prog = &state->programmable;

    for (int i = 0; i < prog->program_length; i++) {
        const uint32_t *token = prog->program_data[i];

        if (vsh_token_writes_fog(token)) {
            if (w.kind != VSH_FOG_WRITE_NONE) {
                /*
                 * Two writes: the register ends up holding the later one,
                 * and which instruction that is depends on the program's
                 * flow.
                 */
                w.kind = VSH_FOG_WRITE_COMPUTED;
                return w;
            }

            w = vsh_classify_fog_write(token, state);
            if (w.kind == VSH_FOG_WRITE_COMPUTED) {
                return w;
            }
        }

        /* The program ends here, as it does for the translator. */
        if (vsh_get_field(token, FLD_FINAL)) {
            break;
        }
    }

    return w;
}

/*
 * #41: does this draw fog from the carried fixed-function RADIAL coordinate?
 *
 * Under a vertex program the nv2a ignores FOG_GEN_MODE and fogs from oFog.x
 * -- measured, not assumed: silicon renders SPEC_ALPHA, PLANAR, ABS_PLANAR
 * and FOG_X identically under a program, the only difference between those
 * four goldens being the printed test name.  RADIAL is the exception, and it
 * is not a distance: the coordinate silicon uses is CONSTANT across a scene
 * whose own radial distance runs 1.7 to 219.7, which is why shipping
 * length(oPos.xyz * oPos.w) here produced 255 distinct colours where the
 * golden has one (e90c3c80).
 *
 * What it is instead is the last coordinate the fixed-function radial
 * generator produced -- the same not-cleared-between-draws shape as #42, one
 * register along.  See the fog block in pgraph_glsl_gen_vsh for the
 * measurement that pins it.
 */
bool pgraph_glsl_vsh_carries_ff_radial_fog(const VshState *state)
{
    return state->fog_enable && !state->is_fixed_function &&
           state->foggen == FOGGEN_RADIAL;
}

/*
 * The coordinate the fixed-function radial generator produces for the last
 * vertex of this draw, which is the one still in the register when the next
 * draw reads it.
 *
 * vsh-ff.c computes it as length(tPosition.xyz) with
 * tPosition = v0 * modelViewMat0, so this is the same arithmetic on the CPU:
 * both ingredients are CPU-visible state.  That is the gap in the earlier
 * reading of #41, which refused the faithful fix on the grounds that "a
 * transformed vertex position is not something the CPU can read back" -- true,
 * and beside the point, because the CPU does not have to read the transform
 * back.  It has the matrix (vsh_constants, loaded by the guest) and the
 * vertex (inline_value, which tracks the draw's last vertex, the same
 * property #42's attribute case relies on), so it can do the transform
 * itself.
 *
 * GLSL_C_MAT4 builds the matrix from four consecutive constant registers as
 * mat4's COLUMNS, and v0 * M is a row-vector product, so component j is
 * dot(v0, c[MMAT0 + j]).
 */
static float ff_radial_fog_coord(PGRAPHState *pg)
{
    const float *v0 =
        pg->vertex_attributes[NV2A_VERTEX_ATTR_POSITION].inline_value;

    float eye[3];
    for (int j = 0; j < 3; j++) {
        float acc = 0.0f;
        for (int k = 0; k < 4; k++) {
            uint32_t bits = pg->vsh_constants[NV_IGRAPH_XF_XFCTX_MMAT0 + j][k];
            float m;
            memcpy(&m, &bits, sizeof(m));
            acc += v0[k] * m;
        }
        eye[j] = acc;
    }

    return sqrtf(eye[0] * eye[0] + eye[1] * eye[1] + eye[2] * eye[2]);
}

MString *pgraph_glsl_gen_vsh(const VshState *state, GenVshGlslOptions opts)
{
    MString *uniforms = mstring_new();
    const char *u = opts.vulkan ? "" : "uniform ";
    for (int i = 0; i < ARRAY_SIZE(VshUniformInfo); i++) {
        const UniformInfo *info = &VshUniformInfo[i];
        const char *type_str = uniform_element_type_to_str[info->type];
        if (i == VshUniform_inlineValue &&
            (!state->uniform_attrs ||
             opts.use_push_constants_for_uniform_attrs)) {
            continue;
        }
        if (info->count == 1) {
            mstring_append_fmt(uniforms, "%s%s %s;\n", u, type_str,
                               info->name);
        } else {
            mstring_append_fmt(uniforms, "%s%s %s[%zd];\n", u, type_str,
                               info->name, info->count);
        }
    }

    MString *header = mstring_from_str(
        GLSL_DEFINE(fogPlane, GLSL_C(NV_IGRAPH_XF_XFCTX_FOG))
        GLSL_DEFINE(texMat0, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_T0MAT))
        GLSL_DEFINE(texMat1, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_T1MAT))
        GLSL_DEFINE(texMat2, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_T2MAT))
        GLSL_DEFINE(texMat3, GLSL_C_MAT4(NV_IGRAPH_XF_XFCTX_T3MAT))

        "\n"
        "#define FLOAT_MAX uintBitsToFloat(0x7F7FFFFFu)\n"
        "\n"
        /* A vertex colour is carried with a 13-bit fraction, the low ten
         * bits of the float dropped rather than rounded. The Point size
         * goldens pin it: the test walks a channel up in steps of 0.1,
         * and where the accumulated float lands a hair above a half count
         * the hardware still gives the lower byte -- 0.7 comes out 178 and
         * 0.9 comes out 229, which rounding the float cannot produce and
         * truncating its fraction first does, for all ten steps. */
        /* The mantissa truncation alone is only half the rule, and the
         * missing half is *where* the quantisation happens rather than how.
         *
         * Silicon quantises the vertex colour to its byte BEFORE the
         * interpolator; we were interpolating the float and quantising at the
         * fragment. On a flat region both give the same byte, which is why
         * all nineteen values that fixed the rounding rule could not see it --
         * every one of them was read from a flat golden region.
         *
         * A gradient separates them, and exactly one in the corpus is steep
         * enough to do it: Alpha_func's green band, which ramps 0.495f to
         * 0.505f across the quad. Recovering the fragment alpha per pixel by
         * inverting the blend (all 512 px of a row recover uniquely, zero
         * residual) and reading the coverage mask of AlphaFuncEqual_Enabled:
         *
         *   hardware  a8 == 127 on x 148..317  =>  slope (2.9942, 3.0296)
         *   ours      a8 == 127 on x 120..321  =>  slope (2.5222, 2.5473)
         *
         * Hardware brackets 3.0000, from byte endpoints 126 -> 129. Ours
         * brackets 2.5369, from the float endpoints. The intercept pins
         * hardware's left endpoint to 126.005..126.011, which excludes a
         * 9-bit or 10-bit carrier: it is the byte itself being interpolated.
         *
         * So snap to the byte grid here, before the interpolator sees it.
         * The truncation must still come first -- rounding the float gives
         * 0.1f -> 26 where hardware says 25 -- and the tie must go up via
         * floor(x + 0.5) rather than round(), because 0.5f's tie goes up
         * while the accumulated 0.7's goes down. Issues #38, #57. */
        "vec4 colorPrecision(vec4 c) {\n"
        "  vec4 t = uintBitsToFloat(floatBitsToUint(c) & 0xFFFFFC00u);\n"
        "  return floor(t * 255.0 + 0.5) / 255.0;\n"
        "}\n"
        "\n"
        "vec4 oPos = vec4(0.0,0.0,0.0,1.0);\n"
        "vec4 oD0 = vec4(0.0,0.0,0.0,1.0);\n"
        "vec4 oD1 = vec4(0.0,0.0,0.0,1.0);\n"
        "vec4 oB0 = vec4(0.0,0.0,0.0,1.0);\n"
        "vec4 oB1 = vec4(0.0,0.0,0.0,1.0);\n"
        "vec4 oPts = vec4(0.0,0.0,0.0,1.0);\n"
        /* oFog does not start cleared on hardware.  A program that never
         * writes it renders with the value the previous program left, so
         * this initialiser is not what such a program reads: the fog block
         * below substitutes the carried coordinate instead (#42). */
        "vec4 oFog = vec4(0.0,0.0,0.0,1.0);\n"
        "vec4 oT0 = vec4(0.0,0.0,0.0,1.0);\n"
        "vec4 oT1 = vec4(0.0,0.0,0.0,1.0);\n"
        "vec4 oT2 = vec4(0.0,0.0,0.0,1.0);\n"
        "vec4 oT3 = vec4(0.0,0.0,0.0,1.0);\n"
        "\n"
        "vec4 decompress_11_11_10(int cmp) {\n"
        "    float x = float(bitfieldExtract(cmp, 0,  11)) / 1023.0;\n"
        "    float y = float(bitfieldExtract(cmp, 11, 11)) / 1023.0;\n"
        "    float z = float(bitfieldExtract(cmp, 22, 10)) / 511.0;\n"
        "    return vec4(x, y, z, 1);\n"
        "}\n"
        "\n"
        // Clamp to range [2^(-64), 2^64] or [-2^64, -2^(-64)].
        "float clampAwayZeroInf(float t) {\n"
        "  if (t > 0.0 || floatBitsToUint(t) == 0u) {\n"
        "    t = clamp(t, uintBitsToFloat(0x1F800000u), uintBitsToFloat(0x5F800000u));\n"
        "  } else {\n"
        "    t = clamp(t, uintBitsToFloat(0xDF800000u), uintBitsToFloat(0x9F800000u));\n"
        "  }\n"
        "  return t;\n"
        "}\n"
        "\n"
        "vec4 NaNToOne(vec4 src) {\n"
        "  return mix(src, vec4(1.0), isnan(src));\n"
        "}\n"
        "vec4 NaNToValue(vec4 src, float replacement) {\n"
        "  return mix(src, vec4(replacement), isnan(src));\n"
        "}\n"
        "\n"
        /*
         * The rasteriser carries 4 fractional bits and truncates. That was
         * inherited as a guess ("appears to"); it is now measured, and three
         * alternatives are worse:
         *
         *   1/32 truncation     Texture_render_target 356 -> 2,195 px on
         *                       TexFmt_A8R8G8B8, spreading the residual from
         *                       one column to four
         *   1/8 truncation      predicts all twelve Viewport offsets and
         *                       improves those two captures 500 -> 300 px, but
         *                       costs Texture_render_target nine exact tests,
         *                       11/40 -> 2/40
         *   round half up       Blend_tests, Specular, Specular_back,
         *   at 1/16             Material_color_source and Lighting_spotlight
         *                       together 7,644,736 -> 8,464,262 px
         *
         * So the granularity is bracketed on both sides and the rounding mode
         * is settled. The one-pixel differences that remain are not this
         * constant: the checkerboard cell edges a row over in the lighting
         * suites and the centre column of Texture_render_target are texel
         * ties (an interpolated coordinate on an exact texel boundary, which
         * hardware and host break differently), and the two Viewport offsets
         * at exactly 9/16 are the fixed-function transform landing a few ULP
         * either side of the snap boundary. Changing this constant to chase
         * them makes things worse. See docs/investigations/edge-defect.md
         * and issues #11 and #4.
         */
        /*
         * Do NOT add a bias here to chase #49's two captures, and this is now
         * proved rather than advised. Both of its offsets are congruent to
         * 9/16 mod 1, so the post-offset coordinate lands exactly ON a grid
         * line, where this function is the identity and coverage is decided
         * by the last bit of the transform above it. Every rule expressible
         * here -- truncate, floor, round, any grid size, any pre- or post-snap
         * bias, any sample point -- is invariant under integer translation of
         * its input, and hardware resolves x = 120 + 9/16 and x = 320 + 9/16
         * in OPPOSITE directions, in the same quad at identical y and w. So no
         * rule on pos can match it. The best bias small enough to keep the ten
         * passing captures exact still leaves 888 of 1,396 px, fixing three
         * vertices and breaking two.
         * docs/investigations/viewport-9-16-boundary.md
         */
        "vec2 roundScreenCoords(vec2 pos) {\n"
        "  return trunc(pos * 16.0) / 16.0;\n"
        "}\n");

    pgraph_glsl_get_vtx_header(header, opts.vulkan, state->smooth_shading,
                               state->noperspective, false,
                               opts.prefix_outputs, false);

    if (opts.prefix_outputs) {
        mstring_append(header,
                       "#define vtxD0 v_vtxD0\n"
                       "#define vtxD1 v_vtxD1\n"
                       "#define vtxB0 v_vtxB0\n"
                       "#define vtxB1 v_vtxB1\n"
                       "#define vtxFog v_vtxFog\n"
                       "#define vtxFogSpecial v_vtxFogSpecial\n"
                       "#define vtxT0 v_vtxT0\n"
                       "#define vtxT1 v_vtxT1\n"
                       "#define vtxT2 v_vtxT2\n"
                       "#define vtxT3 v_vtxT3\n"
                       "#define vtxPos0 v_vtxPos0\n"
                       "#define vtxPos1 v_vtxPos1\n"
                       "#define vtxPos2 v_vtxPos2\n"
                       "#define triMZ v_triMZ\n"
                       "#define vtxPointSize v_vtxPointSize\n"
                       );
    }
    mstring_append(header, "\n");

    int num_uniform_attrs = 0;

    for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
        bool is_uniform = state->uniform_attrs & (1 << i);
        bool is_swizzled = state->swizzle_attrs & (1 << i);
        bool is_compressed = state->compressed_attrs & (1 << i);

        assert(!(is_uniform && is_compressed));
        assert(!(is_uniform && is_swizzled));

        if (is_uniform) {
            mstring_append_fmt(header, "vec4 v%d = inlineValue[%d];\n", i,
                               num_uniform_attrs);
            num_uniform_attrs += 1;
        } else {
            if (state->compressed_attrs & (1 << i)) {
                mstring_append_fmt(header,
                                   "layout(location = %d) in int v%d_cmp;\n", i, i);
            } else if (state->swizzle_attrs & (1 << i)) {
                mstring_append_fmt(header, "layout(location = %d) in vec4 v%d_sw;\n",
                                   i, i);
            } else {
                mstring_append_fmt(header, "layout(location = %d) in vec4 v%d;\n",
                                   i, i);
            }
        }
    }

    mstring_append(header, "\n");

    MString *body = mstring_from_str("void main() {\n");

    for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
        if (state->compressed_attrs & (1 << i)) {
            mstring_append_fmt(
                body, "vec4 v%d = decompress_11_11_10(v%d_cmp);\n", i, i);
        }

        if (state->swizzle_attrs & (1 << i)) {
            mstring_append_fmt(body, "vec4 v%d = v%d_sw.bgra;\n", i, i);
        }

    }

    if (state->is_fixed_function) {
        pgraph_glsl_gen_vsh_ff(state, header, body);
    } else {
        pgraph_glsl_gen_vsh_prog(
            VSH_VERSION_XVS, (uint32_t *)state->programmable.program_data,
            state->programmable.program_length, header, body);
        if (!state->point_params_enable) {
            mstring_append_fmt(body, "  oPts.x = %f * float(%d);\n",
                               state->point_size <= 0.f ? 1.f :
                                                          state->point_size,
                               state->surface_scale_factor);
        }
    
        if (state->lighting) {
            pgraph_glsl_append_vsh_prog_lighting(state, header, body);
        }
    }

    /*
     * The fog factor is not a vertex quantity on this hardware. The Fog
     * suite's exp captures shade smoothly across a triangle whose vertices
     * span depths 50 to 200, where interpolating a per-vertex factor gives a
     * different, flatter gradient; the linear captures agree either way. So
     * the vertex stage only produces the fog coordinate, and the fragment
     * shader applies the mode function to the interpolated coordinate
     * (see psh.c). An infinite or NaN coordinate is flagged separately so
     * the fragment shader can substitute the fixed result the hardware
     * gives for it, instead of interpolating the value itself.
     */
    mstring_append(body, "  float fogSpecial = 0.0;\n");
    if (!state->fog_enable) {
        /* FIXME: Is the fog still calculated / passed somehow?! */
        mstring_append(body, "  oFog = vec4(1.0);\n");
    } else {
        if (!state->is_fixed_function) {
            /* FIXME: Does foggen do something here? Let's do some tracking..
             *
             *   "RollerCoaster Tycoon" has
             *      state->vertex_program = true; state->foggen == FOGGEN_PLANAR
             *      but expects oFog.x as fogdistance?! Writes oFog.xyzw = v0.z
             */
            /*
             * Every gen mode uses oFog.x here, RADIAL included, and RADIAL is
             * the one that is not simply right. Silicon renders the other four
             * identically under a vertex program -- the only difference between
             * those Fog gen goldens is the printed test name -- and renders
             * RADIAL differently, so there is a real divergence to account for.
             *
             * It is not accounted for by computing a distance. I briefly
             * shipped length(oPos.xyz * oPos.w) here on the strength of a
             * 94.9% reduction against that golden and reverted it (e90c3c80):
             * the number was what fraction of pixels a large enough distance
             * pushes past the fog range, and the change produced 255 distinct
             * colours where the golden has one.
             *
             * That revert was written up as "the captures are saturated, so
             * every model that saturates scores alike and the corpus cannot
             * choose". THAT PART IS WRONG, and it hid the measurement. Two of
             * the six are not saturated. The suite's combiner is
             * f*(0,0,1) + (1-f)*(1,0,0), which clips at neither end, so every
             * drawn pixel carries the 8-bit fog factor -- and
             * FogGen_VS-exp-radial and FogGen_VS-exp_abs-radial hold
             * (254, 0, 1) on all 181,016 of theirs. f8 = 1, one step short of
             * the fog colour, which inverts. (A saturating fix therefore does
             * not match either: it leaves 724,064 channels of the cell's
             * 2,172,192.)
             *
             * Inverted through silicon's own exp response -- calibrated from
             * the Fog param sweeps at three multipliers, since psh.c's 2^x
             * caveat bites exactly here -- f8 = 1 means fogX in
             * (-0.5000, -0.4600), so:
             *
             *   the coordinate is in (204.06, 221.81), identical on every one
             *   of the 374 quads.
             *
             * Which kills the two obvious answers. It is NOT 200 (kFogEnd and
             * the projection far plane both are; at 200 silicon reads f8 = 2).
             * And it is not geometry: the coordinate varies by under 17.74
             * across the scene where the fixed-function radial distance over
             * the same vertices runs ~19 to ~222, so under 8.7% of it.
             *
             * #41's mechanism -- the fog mux still honouring RADIAL in program
             * mode and reading lighting intermediates a program never writes --
             * now has a measurement behind it rather than plausibility. In
             * FogGen_FF-exp-radial only 5 of 374 quads sit in that same
             * 17.74-wide window, the corners of the final row, and the last
             * quad drawn is one of them. All 30 FF tests run before all 30 VS
             * tests (name order) over an identical grid, so one stale value
             * explains one constant across all six captures.
             *
             * That reading has since been sharpened from "only 5 of 374
             * quads sit in the window" to the vertex, by reconstructing the
             * scene and checking the reconstruction against silicon's own
             * fixed-function captures: FogGen_FF-linear-radial inverts to a
             * radial distance per quad, and the model of the scene agrees
             * with it to +0.359 +/- 0.169 over the 183 quads whose interior
             * is uniform, worst 0.780 -- 0.99 of one quantisation step.  On
             * that validated geometry
             *
             *   the last vertex the fixed-function scene draws -- quad 373's
             *   fourth, at screen (368, 465) and world z 180.5 -- sits at
             *   215.93,
             *
             * inside the (204.06, 221.81) the goldens demand, and so does
             * every vertex of the final four quads (210.35 .. 219.67).  The
             * mechanism does not have to name the exact slot to predict the
             * band.
             *
             * It also excludes the other stale-value candidate.  The label
             * overlay is the last thing each test draws, so "the last
             * fixed-function vertex" could have been a text vertex rather
             * than a quad one.  It could not: the label's extent is measured
             * per capture, and the two tests that pin the coordinate are
             * preceded by labels whose right edges are 40 px apart --
             * FogGen_VS-exp-planar ends at column 216, FogGen_VS-exp_abs-
             * planar at 256.  For a text vertex to land in the band at all
             * its position vector has to be about 210 long with x dominating,
             * so 40 px of x is about 40 units of coordinate, against a band
             * 17.74 wide.  Whatever transform the overlay uses, it cannot put
             * both pinning captures in one window; the quad grid's tail does,
             * because all six VS tests draw the identical grid.
             *
             * So it is implemented, as the carried coordinate above.  Not as
             * a constant: writing 212.0 here would zero the cell and be
             * arbitrary for every guest that is not this test (a110957a with
             * a better-measured number).  The earlier refusal said the
             * faithful version needs |modelview . v| of the last vertex of
             * the last fixed-function draw, "which the CPU cannot read back
             * the way it reads back a mov oFog, c[n]".  The CPU does not have
             * to read it back: it has the matrix in vsh_constants and the
             * vertex in inline_value, so it can do the transform itself.
             * That is ff_radial_fog_coord, mirroring vsh-ff.c's
             * length(tPosition.xyz) -- and our own FF radial is worth
             * mirroring, at 2,603 px and a worst error of one against
             * FogGen_FF-linear-radial.
             *
             * Two consequences worth stating rather than discovering:
             *
             * - This makes us order-dependent here in the way hardware is.
             *   On an isolation disc holding one VS RADIAL test there is no
             *   preceding fixed-function RADIAL draw, the carried coordinate
             *   is 0, and the draw renders unfogged -- further from the
             *   golden than today's oFog.x.  The golden was captured with
             *   all 30 FF tests running first, so it is only reproducible on
             *   a disc with the same composition.  That is the same property
             *   upstream reports as "the radial generator tests change
             *   occasionally on HW" (abaire/nxdk_pgraph_tests#214).
             * - A guest that sets FOGGEN = RADIAL under a program and never
             *   draws fixed-function RADIAL now fogs with 0 rather than with
             *   oFog.x.  Hardware gives it whatever the register holds, so
             *   neither is the value; 0 is the register we model it as
             *   starting from.  RollerCoaster Tycoon, the guest the FIXME
             *   above names, sets FOGGEN_PLANAR and is untouched.
             *
             * docs/investigations/fog-vs-radial-band.md, reproduced by
             * docs/testing/fog_radial_band.py; the geometry and the two
             * eliminations by docs/testing/fog_radial_stale_vertex.py.
             */
            /*
             * #42 is the other half of that, and it is the opposite case:
             * measured, not unknown.  oFog is initialised to (0,0,0,1)
             * above, so a program that never writes it fogs with coordinate
             * 0 and we render the draw unfogged; hardware renders it with
             * whatever the previous program left in the register.  Two
             * captures pin that value and ten only bound it, which is why
             * the suite as a whole looked unfalsifiable.
             *
             * Fog_coord_vec4 CoordNotSet pins it.  Two draws write
             * oFog = (0.25, 0.95, 0.5, 0.75) from c[120], then a program
             * writing only oPos and oD0 draws the same quad.  Its final
             * combiner is f*C0 + (1 - f)*diffuse, C0 = (0.5, 0, 0.75) and
             * diffuse white -- a mix that clips at neither end, so the
             * 8-bit factor inverts straight out of the colour.  Gold holds
             * (223, 192, 239) over 30,568 px and exactly one factor in
             * 0..255 reproduces it on all three channels: 63, which is
             * trunc(0.25 * 255).  So the carried coordinate is the previous
             * program's oFog.x.  A unique solution also refutes the rest of
             * the vector and the saturating answer: oFog.y, .z and .w give
             * (134, 13, 194), (191, 128, 223) and (159, 64, 207), and a
             * coordinate large enough to clip gives (127, 0, 191).
             *
             * Fog_carryover FogCarryover pins it a second way.  Six fog
             * modes each draw one triangle with the coordinate set and one
             * without; the coordinate differs per mode (0.6 linear, 0.1
             * exp, 0.2 exp2) and the bias is chosen so the factor lands
             * inside the range, at 0.400, 0.369 and 0.412.  In all six the
             * no-coordinate triangle is bit-identical to the explicit one
             * in the same frame, 4,032 px per mode pair.  Each mode
             * function is strictly monotonic in the coordinate there, so
             * equality forces the carried coordinate to be the one the
             * neighbour set, and no single constant can be three different
             * values at once.  That kills a fixed fallback coordinate
             * without appealing to the mode formulas at all.
             *
             * The ten Carryover<Primitive> captures are the saturated ones.
             * They run exp at 0.6 for every draw, where the factor clips:
             * the explicit-coordinate primitives render full fog in gold
             * and in ours too, so the quad's full fog bounds the carried
             * coordinate and cannot pin it.  Fitting those alone is the #41
             * mistake in a new suit -- and it would regress CoordNotSet
             * from a (32, 63, 16) channel error to (96, 192, 48).
             *
             * Ruled out separately: reading the FOG_COORD vertex attribute
             * when the program is fog-silent.  It fits all eleven
             * Fog_carryover captures, because there the previous program
             * copied that attribute into oFog, but fog_tests.cpp never
             * calls SetFogCoord at all, so it cannot produce CoordNotSet's
             * 0.25.  Honouring FOGGEN here is dead by measurement already
             * (+7,449,481 channels, above), and independently: the unset
             * program does not write oD1 either, so a spec-alpha read would
             * be exactly as unwritten as oFog.
             *
             * Carried here as a CPU-side shadow, in carriedFogCoord.  The
             * faithful alternative -- keeping the value on the GPU, where
             * the vertex stage computed it -- was priced and refused: it
             * needs a vertex-stage storage buffer written by one draw and
             * read by the next, which collides with the Vulkan draw
             * reorder window, cannot name "the previous draw's last
             * vertex" (vertex invocation order is undefined), and puts a
             * read-after-write barrier between every draw in the frame.  A
             * value the CPU resolves per draw is immune to all three,
             * because each draw's uniforms are snapshotted in API order.
             *
             * The shadow is only exact when the previous program's write
             * is one the CPU can read back: `mov oFog, c[n]` or
             * `mov oFog, v[n]` (see pgraph_glsl_vsh_fog_write).  It cannot
             * follow a *computed* fog value, and does not try -- a program
             * that computes one leaves the shadow alone rather than
             * guessing.  That limit is not exercised by anything we
             * measure: both priming shaders are plain moves,
             * fog_vec4_xyzw.vsh writing `mov oFog.xyzw, #fog_value.xyzw`
             * from c[120] and passthrough.vsh writing `mov oFog, iFog`,
             * which is also why those two suites pin the value in the
             * first place.  A guest that computed a coordinate and then
             * relied on a later program inheriting it would need the GPU
             * design above; record it as a known gap rather than reading
             * this as an oversight.
             *
             * Both tests prime with a doubled draw and say why -- "one or
             * more of the vertices in the unset draw case still have
             * arbitrary values from previous operations" -- so the
             * register file is per-vertex-slot and simply not cleared.  A
             * single last-written scalar is a simplification that those
             * two tests deliberately make safe, and a guest relying on
             * more would be relying on hardware the test author calls
             * non-hermetic.  It is also why the ten Carryover<Primitive>
             * captures are expected not to move: one scalar cannot
             * reproduce a per-slot register file, and their goldens only
             * bound the value anyway.
             *
             * Vulkan only.  The GL renderer keeps the cleared initialiser
             * above: it has no per-draw hook that resolves the shadow, and
             * building one there is not worth a fog corner.  When the
             * uniform is not supplied it reads 0.0, which is exactly the
             * unfogged behaviour GL has today.
             */
            /*
             * #41 is the third case, and it takes precedence over both: with
             * FOGGEN == RADIAL the fog unit does not read oFog at all, it
             * reads the fixed-function radial generator's register -- which a
             * vertex program never drives.  So the coordinate is the last one
             * a fixed-function RADIAL draw generated, and it is carried in
             * the same uniform because the two cases cannot both apply to one
             * draw: either the mux is on the generator (RADIAL) or it is on
             * oFog (everything else).  Resolved on the CPU in
             * pgraph_glsl_set_vsh_uniform_values, so unlike #42 this half
             * works on both renderers.
             */
            if (pgraph_glsl_vsh_carries_ff_radial_fog(state)) {
                mstring_append(body,
                               "  float fogDistance = carriedFogCoord;\n");
            } else if (opts.vulkan && pgraph_glsl_vsh_fog_write(state).kind ==
                                          VSH_FOG_WRITE_NONE) {
                mstring_append(body,
                               "  float fogDistance = carriedFogCoord;\n");
            } else {
                mstring_append(body, "  float fogDistance = oFog.x;\n");
            }
        }
        mstring_append(body,
                       "  if (isinf(fogDistance) || isnan(fogDistance)) {\n"
                       "    fogSpecial = 1.0;\n"
                       "    oFog = vec4(0.0);\n"
                       "  } else {\n"
                       "    oFog = vec4(fogDistance);\n"
                       "  }\n");
    }

    mstring_append(body, "\n"
                   "  vtxD0 = colorPrecision(clamp(NaNToOne(oD0), 0.0, 1.0));\n"
                   "  vtxB0 = colorPrecision(clamp(NaNToOne(oB0), 0.0, 1.0));\n"
                   "  vtxFog = oFog.x;\n"
                   "  vtxFogSpecial = fogSpecial;\n"
                   "  vtxT0 = oT0;\n"
                   "  vtxT1 = oT1;\n"
                   "  vtxT2 = oT2;\n"
                   "  vtxT3 = oT3;\n"
                   "  vtxPos0 = vtxPos;\n"
                   "  vtxPos1 = vtxPos;\n"
                   "  vtxPos2 = vtxPos;\n"
                   "  triMZ = 0.0;\n"
                   "  vtxPointSize = oPts.x;\n"
                   "  gl_PointSize = oPts.x;\n"
    );

    if (state->specular_enable) {
        mstring_append(body,
                       "  vtxD1 = colorPrecision(clamp(NaNToOne(oD1), 0.0, 1.0));\n"
                       "  vtxB1 = colorPrecision(clamp(NaNToOne(oB1), 0.0, 1.0));\n"
        );

        if (state->ignore_specular_alpha) {
            mstring_append(body,
                           "  vtxD1.w = 1.0;\n"
                           "  vtxB1.w = 1.0;\n"
            );
        }
    } else {
        mstring_append(body,
                       "  vtxD1 = vec4(0.0, 0.0, 0.0, 1.0);\n"
                       "  vtxB1 = vec4(0.0, 0.0, 0.0, 1.0);\n"
        );
    }

    if (opts.vulkan) {
        mstring_append(body,
                   "  gl_Position = oPos;\n"
        );
    } else {
        mstring_append(body,
                   "  gl_Position = vec4(oPos.x, oPos.y, 2.0*oPos.z - oPos.w, oPos.w);\n"
        );
    }

    mstring_append(body, "}\n");

    /* Return combined header + source */
    MString *output = mstring_new();
    pgraph_glsl_append_version(output, opts.vulkan, opts.gles,
                               opts.gles_version);

    if (opts.vulkan) {
        if (num_uniform_attrs > 0 &&
            opts.use_push_constants_for_uniform_attrs) {
            if (opts.vertex_push_offset > 0) {
                mstring_append_fmt(output,
                    "layout(push_constant) uniform PushConstants {\n"
                    "    layout(offset = %d) vec4 inlineValue[%d];\n"
                    "};\n\n",
                    opts.vertex_push_offset, num_uniform_attrs);
            } else {
                mstring_append_fmt(output,
                    "layout(push_constant) uniform PushConstants {\n"
                    "    vec4 inlineValue[%d];\n"
                    "};\n\n",
                    num_uniform_attrs);
            }
        }
        if (opts.ubo_set > 0) {
            mstring_append_fmt(
                output,
                "layout(set = %d, binding = %d, std140) uniform VshUniforms {\n"
                "%s"
                "};\n\n",
                opts.ubo_set, opts.ubo_binding, mstring_get_str(uniforms));
        } else {
            mstring_append_fmt(
                output,
                "layout(binding = %d, std140) uniform VshUniforms {\n"
                "%s"
                "};\n\n",
                opts.ubo_binding, mstring_get_str(uniforms));
        }
    } else {
        mstring_append(
            output, mstring_get_str(uniforms));
    }

    mstring_append(output, mstring_get_str(header));
    mstring_unref(header);

    mstring_append(output, mstring_get_str(body));
    mstring_unref(body);

    return output;
}

void pgraph_glsl_set_vsh_uniform_values(PGRAPHState *pg, const VshState *state,
                                        const VshUniformLocs locs,
                                        VshUniformValues *values)
{
    if (locs[VshUniform_c] != -1) {
        QEMU_BUILD_BUG_MSG(sizeof(values->c) != sizeof(pg->vsh_constants),
                           "Uniform value size inconsistency");
        memcpy(values->c, pg->vsh_constants, sizeof(pg->vsh_constants));
    }

    /*
     * #41: a fixed-function draw with FOGGEN == RADIAL leaves its last
     * vertex's coordinate in the generator's register, where the next
     * program-mode RADIAL draw reads it.  Updated here because this is the
     * one hook both renderers take per draw, and at this point
     * inline_value already holds the draw's last vertex -- the same
     * ordering #42's attribute case is measured to rely on.
     *
     * Skinning is excluded rather than approximated: with weights the
     * fixed-function stage blends modelViewMat0..3 by the weight attribute,
     * so the single-matrix transform below would be a different value, not
     * a rounding of the right one.  Such a draw leaves the register holding
     * what it held, which is what a draw whose coordinate we cannot
     * reproduce should do.
     */
    if (state->fog_enable && state->is_fixed_function &&
        state->foggen == FOGGEN_RADIAL &&
        state->fixed_function.skinning == SKINNING_OFF) {
        pg->last_ff_radial_fog_coord = ff_radial_fog_coord(pg);
    }

    if (locs[VshUniform_carriedFogCoord] != -1) {
        if (pgraph_glsl_vsh_carries_ff_radial_fog(state)) {
            values->carriedFogCoord[0] = pg->last_ff_radial_fog_coord;
#ifdef __ANDROID__
            /*
             * One line per distinct carried coordinate, not per draw: this
             * fires on 374 draws a test and instrumentation that costs the
             * pushbuffer loop has presented as a renderer deadlock here
             * before.  It is the direct measurement of #41's mechanism --
             * the goldens pin silicon's coordinate to (204.06, 221.81), and
             * this says what ours resolves to from the same draw stream.
             */
            static float last_logged = -1.0f;
            if (pg->last_ff_radial_fog_coord != last_logged) {
                last_logged = pg->last_ff_radial_fog_coord;
                __android_log_print(ANDROID_LOG_WARN, "hakuX",
                                    "fog41: program-mode RADIAL carries "
                                    "coord=%.4f", (double)last_logged);
            }
#endif
        } else {
            /*
             * #42's carried fog coordinate is cross-draw state a renderer has
             * to keep, so it is resolved per draw by the renderer rather than
             * read out of pg here (see pgraph_vk_update_shader_uniforms).  Set
             * a defined value regardless: a renderer that does not carry it
             * gets today's unfogged behaviour, and the uniform never holds
             * stack garbage that would churn the upload hash.
             */
            values->carriedFogCoord[0] = 0.0f;
        }
    }

    if (locs[VshUniform_clipRange] != -1) {
        pgraph_glsl_set_clip_range_uniform_value(pg, values->clipRange[0]);
    }

    if (locs[VshUniform_pointParams] != -1) {
        QEMU_BUILD_BUG_MSG(sizeof(values->pointParams) !=
                               sizeof(pg->point_params),
                           "Uniform value size inconsistency");
        memcpy(values->pointParams, pg->point_params, sizeof(pg->point_params));
    }

    if (locs[VshUniform_material_alpha_back] != -1) {
        values->material_alpha_back[0] = pg->material_alpha_back;
    }
    if (locs[VshUniform_material_alpha] != -1) {
        values->material_alpha[0] = pg->material_alpha;
    }

    if (locs[VshUniform_inlineValue] != -1) {
        pgraph_get_inline_values(pg, state->uniform_attrs, values->inlineValue,
                                 NULL);
    }

    if (locs[VshUniform_surfaceSize] != -1) {
        unsigned int aa_width = 1, aa_height = 1;
        pgraph_apply_anti_aliasing_factor(pg, &aa_width, &aa_height);
        float width = (float)pg->surface_binding_dim.width / aa_width;
        float height = (float)pg->surface_binding_dim.height / aa_height;
        values->surfaceSize[0][0] = width;
        values->surfaceSize[0][1] = height;
    }

    /*
     * The lighting registers, which the programmable path needs too: with
     * LIGHTING_ENABLE set it emits the colour material constant term, and
     * that reads ltctxa. Gated on is_fixed_function alone the vertex program's
     * shader read zeros, which put a black source where silicon has grey 8 --
     * visible on Specular's ControlFlagsNoLight_VS as the golden being exactly
     * six higher than us everywhere, the blend of that 8 against the two
     * background tones.
     */
    if (state->is_fixed_function || state->lighting) {
        if (locs[VshUniform_ltctxa] != -1) {
            QEMU_BUILD_BUG_MSG(sizeof(values->ltctxa) != sizeof(pg->ltctxa),
                               "Uniform value size inconsistency");
            memcpy(values->ltctxa, pg->ltctxa, sizeof(pg->ltctxa));
        }

        if (locs[VshUniform_ltctxb] != -1) {
            QEMU_BUILD_BUG_MSG(sizeof(values->ltctxb) != sizeof(pg->ltctxb),
                               "Uniform value size inconsistency");
            memcpy(values->ltctxb, pg->ltctxb, sizeof(pg->ltctxb));
        }

        if (locs[VshUniform_ltc1] != -1) {
            QEMU_BUILD_BUG_MSG(sizeof(values->ltc1) != sizeof(pg->ltc1),
                               "Uniform value size inconsistency");
            memcpy(values->ltc1, pg->ltc1, sizeof(pg->ltc1));
        }

        if (locs[VshUniform_lightInfiniteHalfVector] != -1) {
            QEMU_BUILD_BUG_MSG(sizeof(values->lightInfiniteHalfVector) !=
                                   sizeof(pg->light_infinite_half_vector),
                               "Uniform value size inconsistency");
            memcpy(values->lightInfiniteHalfVector,
                   pg->light_infinite_half_vector,
                   sizeof(pg->light_infinite_half_vector));
        }

        if (locs[VshUniform_lightInfiniteDirection] != -1) {
            QEMU_BUILD_BUG_MSG(sizeof(values->lightInfiniteDirection) !=
                                   sizeof(pg->light_infinite_direction),
                               "Uniform value size inconsistency");
            memcpy(values->lightInfiniteDirection, pg->light_infinite_direction,
                   sizeof(pg->light_infinite_direction));
        }

        if (locs[VshUniform_lightLocalPosition] != -1) {
            QEMU_BUILD_BUG_MSG(sizeof(values->lightLocalPosition) !=
                                   sizeof(pg->light_local_position),
                               "Uniform value size inconsistency");
            memcpy(values->lightLocalPosition, pg->light_local_position,
                   sizeof(pg->light_local_position));
        }

        if (locs[VshUniform_lightLocalAttenuation] != -1) {
            QEMU_BUILD_BUG_MSG(sizeof(values->lightLocalAttenuation) !=
                                   sizeof(pg->light_local_attenuation),
                               "Uniform value size inconsistency");
            memcpy(values->lightLocalAttenuation, pg->light_local_attenuation,
                   sizeof(pg->light_local_attenuation));
        }

        if (locs[VshUniform_specularParams] != -1) {
            for (int i = 0; i < 2; i++) {
                for (int j = 0; j < 3; j++) {
                    values->specularParams[i][j] = pg->specular_params[i * 3 + j];
                    values->specularParams[2 + i][j] =
                        pg->specular_params_back[i * 3 + j];
                }
            }
        }
    }
}
