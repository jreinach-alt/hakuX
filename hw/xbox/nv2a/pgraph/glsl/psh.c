/*
 * QEMU Geforce NV2A pixel shader translation
 *
 * Copyright (c) 2013 espes
 * Copyright (c) 2015 Jannik Vogel
 * Copyright (c) 2020-2025 Matt Borgerson
 *
 * Based on:
 * Cxbx, PixelShader.cpp
 * Copyright (c) 2004 Aaron Robinson <caustik@caustik.com>
 *                    Kingofc <kingofc@freenet.de>
 * Xeon, XBD3DPixelShader.cpp
 * Copyright (c) 2003 _SF_
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 or
 * (at your option) version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, see <http://www.gnu.org/licenses/>.
 */

#include "qemu/osdep.h"
#include "hw/xbox/nv2a/debug.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#include "ui/xemu-settings.h"
#include "../prim_rewrite.h"
#include "psh.h"

DEF_UNIFORM_INFO_ARR(PshUniform, PSH_UNIFORM_DECL_X)

// TODO: https://github.com/xemu-project/xemu/issues/2260
//   Investigate how color keying is handled for components with no alpha or
//   only alpha.
static uint32_t get_colorkey_mask(unsigned int color_format)
{
    switch (color_format) {
    case NV097_SET_TEXTURE_FORMAT_COLOR_SZ_X1R5G5B5:
    case NV097_SET_TEXTURE_FORMAT_COLOR_SZ_X8R8G8B8:
    case NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_X1R5G5B5:
    case NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_X8R8G8B8:
        return 0x00FFFFFF;

    default:
        return 0xFFFFFFFF;
    }
}

static uint32_t get_color_key_mask_for_texture(PGRAPHState *pg, int i)
{
    assert(i < NV2A_MAX_TEXTURES);
    uint32_t fmt = pgraph_reg_r(pg, NV_PGRAPH_TEXFMT0 + i * 4);
    unsigned int color_format = GET_MASK(fmt, NV_PGRAPH_TEXFMT0_COLOR);
    return get_colorkey_mask(color_format);
}

/*
 * How many window clip rectangles the fragment shader has to test. A
 * rectangle that covers the whole surface clips nothing and is left out, so
 * the count depends on the surface size as well as the sixteen registers.
 * The GL renderer clips with glScissor and its shader tests none.
 *
 * pgraph_glsl_check_shader_state_dirty compares this rather than listing the
 * registers: a guest that set its rectangles and nothing else used to draw
 * with the previous shader, unclipped -- every inclusive Window clip test.
 */
/*
 * Whether the 32x32 stipple pattern masks this draw. It only ever reaches
 * filled polygons: with the pattern set to all zeroes the Stipple tests
 * golden loses every triangle, quad and polygon and keeps its points and
 * its line loop untouched, the way OpenGL's polygon stipple behaves.
 *
 * The primitive is taken through the same rewrite the geometry stage uses
 * rather than read raw. Both renderers reuse a shader state whose only
 * refreshed primitive field is that rewritten mode, so anything derived
 * from the raw mode goes stale: two raw modes that rewrite alike have to
 * answer alike, and this way they do. The enable and the polygon mode are
 * both SETUPRASTER bits outside the dynamic mask, so a change to either
 * brings the state back here.
 */
bool pgraph_glsl_polygon_stipple_enabled(PGRAPHState *pg)
{
    uint32_t setupraster = pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER);

    if (!GET_MASK(setupraster, NV_PGRAPH_SETUPRASTER_STIPPLEENABLE)) {
        return false;
    }

    enum ShaderPolygonMode front_mode = (enum ShaderPolygonMode)GET_MASK(
        setupraster, NV_PGRAPH_SETUPRASTER_FRONTFACEMODE);
    if (front_mode != POLY_MODE_FILL) {
        return false;
    }

    return pgraph_prim_rewrite_get_output_mode(
               (enum ShaderPrimitiveMode)pg->primitive_mode, front_mode) ==
           PRIM_TYPE_TRIANGLES;
}

int pgraph_glsl_window_clip_count(PGRAPHState *pg)
{
    if (g_config.display.renderer == CONFIG_DISPLAY_RENDERER_OPENGL) {
        return 0;
    }
    unsigned int sw = pg->surface_shape.clip_width;
    unsigned int sh = pg->surface_shape.clip_height;
    int count = 0;
    for (int i = 0; i < 8; i++) {
        uint32_t x = pgraph_reg_r(pg, NV_PGRAPH_WINDOWCLIPX0 + i * 4);
        uint32_t y = pgraph_reg_r(pg, NV_PGRAPH_WINDOWCLIPY0 + i * 4);
        unsigned int x_min = GET_MASK(x, NV_PGRAPH_WINDOWCLIPX0_XMIN);
        unsigned int x_max = GET_MASK(x, NV_PGRAPH_WINDOWCLIPX0_XMAX) + 1;
        unsigned int y_min = GET_MASK(y, NV_PGRAPH_WINDOWCLIPY0_YMIN);
        unsigned int y_max = GET_MASK(y, NV_PGRAPH_WINDOWCLIPY0_YMAX) + 1;
        bool trivial = (x_min == 0 && y_min == 0 &&
                        x_max >= sw && y_max >= sh);
        if (!trivial) {
            count++;
        }
    }
    return count;
}

void pgraph_glsl_set_psh_state(PGRAPHState *pg, PshState *state)
{
    state->window_clip_exclusive = pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER) &
                                   NV_PGRAPH_SETUPRASTER_WINDOWCLIPTYPE;
    state->window_clip_count = pgraph_glsl_window_clip_count(pg);

    state->combiner_control = pgraph_reg_r(pg, NV_PGRAPH_COMBINECTL);
    state->shader_stage_program = pgraph_reg_r(pg, NV_PGRAPH_SHADERPROG);
    state->other_stage_input = pgraph_reg_r(pg, NV_PGRAPH_SHADERCTL);
    state->final_inputs_0 = pgraph_reg_r(pg, NV_PGRAPH_COMBINESPECFOG0);
    state->final_inputs_1 = pgraph_reg_r(pg, NV_PGRAPH_COMBINESPECFOG1);

    state->alpha_test = pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) &
                        NV_PGRAPH_CONTROL_0_ALPHATESTENABLE;
    state->alpha_func = (enum PshAlphaFunc)GET_MASK(
        pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0), NV_PGRAPH_CONTROL_0_ALPHAFUNC);

    state->point_sprite = pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER) &
                          NV_PGRAPH_SETUPRASTER_POINTSMOOTHENABLE;

    state->shadow_depth_func =
        (enum PshShadowDepthFunc)GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_SHADOWCTL),
                                          NV_PGRAPH_SHADOWCTL_SHADOW_ZFUNC);
    state->z_perspective = pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) &
                           NV_PGRAPH_CONTROL_0_Z_PERSPECTIVE_ENABLE;
    state->noperspective = !(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) &
                             NV_PGRAPH_CONTROL_0_TEXTUREPERSPECTIVE);

    state->smooth_shading = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_3),
                                     NV_PGRAPH_CONTROL_3_SHADEMODE) ==
                            NV_PGRAPH_CONTROL_3_SHADEMODE_SMOOTH;
    state->two_side_light = pgraph_reg_r(pg, NV_PGRAPH_CSV0_C) &
                            NV_PGRAPH_CSV0_C_TWO_SIDE_LIGHT_EN;
    state->stipple = pgraph_glsl_polygon_stipple_enabled(pg);
    state->fog_enable = pgraph_reg_r(pg, NV_PGRAPH_CONTROL_3) &
                        NV_PGRAPH_CONTROL_3_FOGENABLE;
    state->fog_mode = (enum VshFogMode)GET_MASK(
        pgraph_reg_r(pg, NV_PGRAPH_CONTROL_3), NV_PGRAPH_CONTROL_3_FOG_MODE);

    state->depth_clipping =
        GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_ZCOMPRESSOCCLUDE),
                 NV_PGRAPH_ZCOMPRESSOCCLUDE_ZCLAMP_EN) ==
        NV_PGRAPH_ZCOMPRESSOCCLUDE_ZCLAMP_EN_CULL;

    /* Depth needed flag — used by VK for depth output in fragment shader.
     * GL handles depth via fixed-function pipeline. */
    if (g_config.display.renderer != CONFIG_DISPLAY_RENDERER_OPENGL) {
        uint32_t ctl0 = pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0);
        bool depth_test = ctl0 & NV_PGRAPH_CONTROL_0_ZENABLE;
        bool depth_write = !!(ctl0 & NV_PGRAPH_CONTROL_0_ZWRITEENABLE);
        state->depth_needed = depth_test || depth_write ||
                              state->depth_clipping;
    }

    int num_stages =
        psh_num_combiner_stages(pgraph_reg_r(pg, NV_PGRAPH_COMBINECTL));
    for (int i = 0; i < num_stages; i++) {
        state->rgb_inputs[i] =
            pgraph_reg_r(pg, NV_PGRAPH_COMBINECOLORI0 + i * 4);
        state->rgb_outputs[i] =
            pgraph_reg_r(pg, NV_PGRAPH_COMBINECOLORO0 + i * 4);
        state->alpha_inputs[i] =
            pgraph_reg_r(pg, NV_PGRAPH_COMBINEALPHAI0 + i * 4);
        state->alpha_outputs[i] =
            pgraph_reg_r(pg, NV_PGRAPH_COMBINEALPHAO0 + i * 4);
    }

    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 4; j++) {
            state->compare_mode[i][j] =
                (pgraph_reg_r(pg, NV_PGRAPH_SHADERCLIPMODE) >> (4 * i + j)) & 1;
        }

        uint32_t ctl_0 = pgraph_reg_r(pg, NV_PGRAPH_TEXCTL0_0 + i * 4);
        /*
         * A stage whose descriptor cannot be decoded gets the binder's dummy
         * texture (vk/texture.c, gl/texture.c), so the shader must not sample
         * it: dim_tex[] would be left at 0 and the mode would emit a sample
         * of a texture that is not there.  Clear only that case.  A 1D
         * texture counts as undecodable for this purpose -- see
         * pgraph_is_texture_descriptor_decodable().
         *
         * Do NOT clear the mode merely because the stage is inactive or
         * disabled.  PS_TEXTUREMODES_PASSTHRU (0x04) is reported inactive by
         * pgraph_is_texture_stage_active() precisely because it needs no
         * texture, but it still has shader logic to emit — clearing it to
         * PS_TEXTUREMODES_NONE breaks Pixel shader::Passthru.
         */
        bool decodable = pgraph_is_texture_descriptor_decodable(pg, i);
        bool enabled = pgraph_is_texture_stage_active(pg, i) &&
                       (ctl_0 & NV_PGRAPH_TEXCTL0_0_ENABLE) && decodable;
        if (!enabled) {
            if (!decodable && (ctl_0 & NV_PGRAPH_TEXCTL0_0_ENABLE)) {
                state->shader_stage_program &= ~(0x1Fu << (i * 5));
            }
            continue;
        }

        state->alphakill[i] = ctl_0 & NV_PGRAPH_TEXCTL0_0_ALPHAKILLEN;
        state->colorkey_mode[i] = ctl_0 & NV_PGRAPH_TEXCTL0_0_COLORKEYMODE;

        uint32_t tex_fmt = pgraph_reg_r(pg, NV_PGRAPH_TEXFMT0 + i * 4);
        state->dim_tex[i] = GET_MASK(tex_fmt, NV_PGRAPH_TEXFMT0_DIMENSIONALITY);

        unsigned int color_format = GET_MASK(tex_fmt, NV_PGRAPH_TEXFMT0_COLOR);
        BasicColorFormatInfo f = pgraph_get_color_format_info(color_format);
        state->rect_tex[i] = f.linear;
        state->tex_x8y24[i] =
            color_format ==
                NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_DEPTH_X8_Y24_FIXED ||
            color_format ==
                NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_DEPTH_X8_Y24_FLOAT;
        /* A float depth texture holds the NV2A encoding, not a value (see
         * the F16/F24 cases in psh_convert). The shadow comparison decodes
         * it; a fixed-point one it just scales. */
        state->tex_depth_float[i] =
            color_format ==
                NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_DEPTH_X8_Y24_FLOAT ||
            color_format ==
                NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_DEPTH_Y16_FLOAT;

        uint32_t border_source =
            GET_MASK(tex_fmt, NV_PGRAPH_TEXFMT0_BORDER_SOURCE);
        bool cubemap = GET_MASK(tex_fmt, NV_PGRAPH_TEXFMT0_CUBEMAPENABLE);
        state->tex_cubemap[i] = cubemap;
        {
            uint32_t a = pgraph_reg_r(pg, NV_PGRAPH_TEXADDRESS0 + i * 4);
            state->addr_border[i] =
                (GET_MASK(a, NV_PGRAPH_TEXADDRESS0_ADDRU) == NV_PGRAPH_TEXADDRESS0_ADDRU_BORDER ? 1 : 0) |
                (GET_MASK(a, NV_PGRAPH_TEXADDRESS0_ADDRV) == NV_PGRAPH_TEXADDRESS0_ADDRU_BORDER ? 2 : 0) |
                (GET_MASK(a, NV_PGRAPH_TEXADDRESS0_ADDRP) == NV_PGRAPH_TEXADDRESS0_ADDRU_BORDER ? 4 : 0);
        }
        state->border_logical_size[i][0] = 0.0f;
        state->border_logical_size[i][1] = 0.0f;
        state->border_logical_size[i][2] = 0.0f;
        if (border_source != NV_PGRAPH_TEXFMT0_BORDER_SOURCE_COLOR) {
            if (!f.linear) {
                // The actual texture will be (at least) double the reported
                // size and shifted by a 4 texel border but texture coordinates
                // will still be relative to the reported size.
                unsigned int reported_width =
                    1 << GET_MASK(tex_fmt, NV_PGRAPH_TEXFMT0_BASE_SIZE_U);
                unsigned int reported_height =
                    1 << GET_MASK(tex_fmt, NV_PGRAPH_TEXFMT0_BASE_SIZE_V);
                unsigned int reported_depth =
                    1 << GET_MASK(tex_fmt, NV_PGRAPH_TEXFMT0_BASE_SIZE_P);

                state->border_logical_size[i][0] = reported_width;
                state->border_logical_size[i][1] = reported_height;
                state->border_logical_size[i][2] = reported_depth;

                if (reported_width < 8) {
                    state->border_inv_real_size[i][0] = 0.0625f;
                } else {
                    state->border_inv_real_size[i][0] =
                        1.0f / (reported_width * 2.0f);
                }
                if (reported_height < 8) {
                    state->border_inv_real_size[i][1] = 0.0625f;
                } else {
                    state->border_inv_real_size[i][1] =
                        1.0f / (reported_height * 2.0f);
                }
                if (reported_depth < 8) {
                    state->border_inv_real_size[i][2] = 0.0625f;
                } else {
                    state->border_inv_real_size[i][2] =
                        1.0f / (reported_depth * 2.0f);
                }
            } else {
                NV2A_UNIMPLEMENTED(
                    "Border source texture with linear %d cubemap %d", f.linear,
                    cubemap);
            }
        }

        /* Textures whose channels reach the shader already signed, so it must
         * not remap them again.
         *
         * Signedness belongs in the sampler, before filtering: the bump maps
         * hold 0x7f and 0x80 in adjacent quadrants, neighbouring values
         * unsigned but +127 and -128 signed. Converting after the fetch makes
         * every boundary saturate to +/-1 instead of sweeping through zero,
         * which is what the Vulkan path did -- this was set for OpenGL only. */
        uint32_t sign_filter = pgraph_reg_r(pg, NV_PGRAPH_TEXFILTER0 + i * 4);
        const uint32_t any_signed = NV_PGRAPH_TEXFILTER0_ASIGNED |
                                    NV_PGRAPH_TEXFILTER0_RSIGNED |
                                    NV_PGRAPH_TEXFILTER0_GSIGNED |
                                    NV_PGRAPH_TEXFILTER0_BSIGNED;
        /* R6G5B5 used to need a renderer-specific exception here, because GL
         * stored it in an SNORM image while Vulkan did not. Both now convert it
         * to unsigned RGBA8 and take signedness from the sampler, so the rule
         * is the same one every other format follows. */
        /* The sampler signs the whole texel or nothing (the image format
         * is SNORM or UNORM), so it is used only when every channel is
         * flagged.  A partial set of flags -- Texture_signed_component_tests
         * sweeps all sixteen -- is applied per channel after the fetch,
         * exact for nearest filtering, off only across a 0x7f/0x80 step
         * under linear filtering. */
        state->snorm_tex[i] =
            (sign_filter & any_signed) == any_signed &&
            pgraph_color_format_has_signed_variant(color_format);
        state->tex_signed[i] = sign_filter & any_signed;
        state->shadow_map[i] = f.depth;

        uint32_t filter = pgraph_reg_r(pg, NV_PGRAPH_TEXFILTER0 + i * 4);
        unsigned int min_filter = GET_MASK(filter, NV_PGRAPH_TEXFILTER0_MIN);
        enum ConvolutionFilter kernel = CONVOLUTION_FILTER_DISABLED;
        /* FIXME: We do not distinguish between min and mag when
         * performing convolution. Just use it if specified for min (common AA
         * case).
         */
        if (min_filter == NV_PGRAPH_TEXFILTER0_MIN_CONVOLUTION_2D_LOD0) {
            int k = GET_MASK(filter, NV_PGRAPH_TEXFILTER0_CONVOLUTION_KERNEL);
            assert(k == NV_PGRAPH_TEXFILTER0_CONVOLUTION_KERNEL_QUINCUNX ||
                   k == NV_PGRAPH_TEXFILTER0_CONVOLUTION_KERNEL_GAUSSIAN_3);
            kernel = (enum ConvolutionFilter)k;
        }

        state->conv_tex[i] = kernel;
    }

    state->surface_zeta_format = pg->surface_shape.zeta_format;
    unsigned int z_format = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER),
                                     NV_PGRAPH_SETUPRASTER_Z_FORMAT);

    switch (pg->surface_shape.zeta_format) {
    case NV097_SET_SURFACE_FORMAT_ZETA_Z16:
        state->depth_format =
            z_format ? DEPTH_FORMAT_F16 : DEPTH_FORMAT_D16;
        break;
    case NV097_SET_SURFACE_FORMAT_ZETA_Z24S8:
        state->depth_format =
            z_format ? DEPTH_FORMAT_F24 : DEPTH_FORMAT_D24;
        break;
    default:
        fprintf(stderr, "Unknown zeta surface format: 0x%x\n",
                pg->surface_shape.zeta_format);
        assert(false);
        break;
    }
}

struct InputInfo {
    int reg, mod, chan;
};

struct InputVarInfo {
    struct InputInfo a, b, c, d;
};

struct FCInputInfo {
    struct InputInfo a, b, c, d, e, f, g;
    bool v1r0_sum, clamp_sum, inv_v1, inv_r0, enabled;
};

struct OutputInfo {
    int ab, cd, muxsum, flags, ab_op, cd_op, muxsum_op,
        mapping, ab_alphablue, cd_alphablue;
};

struct PSStageInfo {
    struct InputVarInfo rgb_input, alpha_input;
    struct OutputInfo rgb_output, alpha_output;
    int c0, c1;
};

struct PixelShader {
    GenPshGlslOptions opts;
    const PshState *state;

    int num_stages, flags;
    struct PSStageInfo stage[8];
    struct FCInputInfo final_input;
    int tex_modes[4], input_tex[4], dot_map[4];
    bool tex_unusable[4];

    MString *varE, *varF;
    MString *code;
    int cur_stage;

    int num_var_refs;
    char var_refs[32][32];
    int num_const_refs;
    char const_refs[32][32];
};

static void add_var_ref(struct PixelShader *ps, const char *var)
{
    int i;
    for (i=0; i<ps->num_var_refs; i++) {
        if (strcmp((char*)ps->var_refs[i], var) == 0) return;
    }
    strcpy((char*)ps->var_refs[ps->num_var_refs++], var);
}

static void add_const_ref(struct PixelShader *ps, const char *var)
{
    int i;
    for (i=0; i<ps->num_const_refs; i++) {
        if (strcmp((char*)ps->const_refs[i], var) == 0) return;
    }
    strcpy((char*)ps->const_refs[ps->num_const_refs++], var);
}

static MString* get_var(struct PixelShader *ps, int reg, bool is_dest)
{
    /*
     * Register codes arrive as guest data out of NV_PGRAPH_COMBINE*I0..7 and
     * nothing validates them on the way in, so every value of the 4-bit field
     * has to produce *something*. The policy (issue #26): an encoding the
     * hardware reserves or a use it forbids never aborts the generator. A
     * reserved source reads as zero, a read-only destination discards, and
     * each is logged once so the unknown is on record. What silicon does with
     * these is not established; this is a claim about not dying, not about
     * being right.
     */
    bool final_combiner = ps->cur_stage == 8;
    if (is_dest) {
        switch (reg) {
        case PS_REGISTER_C0:
        case PS_REGISTER_C1:
        case PS_REGISTER_FOG:
        case PS_REGISTER_V1R0_SUM:
        case PS_REGISTER_EF_PROD:
            /* Emitting the register name here produced an assignment to a
             * uniform or an expression -- a shader that generates, caches,
             * and then fails to compile, which the differ cannot see. */
            NV2A_UNIMPLEMENTED("combiner stage %d writes read-only register "
                               "0x%x; discarded", ps->cur_stage, reg);
            return mstring_from_str("");
        default:
            break;
        }
    }

    switch (reg) {
    case PS_REGISTER_DISCARD:
        if (is_dest) {
            return mstring_from_str("");
        } else {
            return mstring_from_str("vec4(0.0)");
        }
        break;
    case PS_REGISTER_C0:
        if (ps->flags & PS_COMBINERCOUNT_UNIQUE_C0 || ps->cur_stage == 8) {
            MString *reg_name = mstring_from_fmt("c0_%d", ps->cur_stage);
            add_const_ref(ps, mstring_get_str(reg_name));
            return reg_name;
        } else {  // Same c0
            add_const_ref(ps, "c0_0");
            return mstring_from_str("c0_0");
        }
        break;
    case PS_REGISTER_C1:
        if (ps->flags & PS_COMBINERCOUNT_UNIQUE_C1 || ps->cur_stage == 8) {
            MString *reg_name = mstring_from_fmt("c1_%d", ps->cur_stage);
            add_const_ref(ps, mstring_get_str(reg_name));
            return reg_name;
        } else {  // Same c1
            add_const_ref(ps, "c1_0");
            return mstring_from_str("c1_0");
        }
        break;
    case PS_REGISTER_FOG:
        return mstring_from_str("pFog");
    case PS_REGISTER_V0:
        return mstring_from_str("v0");
    case PS_REGISTER_V1:
        return mstring_from_str("v1");
    case PS_REGISTER_T0:
        return mstring_from_str("t0");
    case PS_REGISTER_T1:
        return mstring_from_str("t1");
    case PS_REGISTER_T2:
        return mstring_from_str("t2");
    case PS_REGISTER_T3:
        return mstring_from_str("t3");
    case PS_REGISTER_R0:
        add_var_ref(ps, "r0");
        return mstring_from_str("r0");
    case PS_REGISTER_R1:
        add_var_ref(ps, "r1");
        return mstring_from_str("r1");
    case PS_REGISTER_V1R0_SUM:
        add_var_ref(ps, "r0");
        if (ps->final_input.clamp_sum) {
            return mstring_from_fmt(
                    "clamp(vec4(%s.rgb + %s.rgb, 0.0), 0.0, 1.0)",
                    ps->final_input.inv_v1 ? "(1.0 - v1)" : "v1",
                    ps->final_input.inv_r0 ? "(1.0 - r0)" : "r0");
        } else {
            return mstring_from_fmt(
                    "vec4(%s.rgb + %s.rgb, 0.0)",
                    ps->final_input.inv_v1 ? "(1.0 - v1)" : "v1",
                    ps->final_input.inv_r0 ? "(1.0 - r0)" : "r0");
        }
    case PS_REGISTER_EF_PROD:
        if (!final_combiner) {
            /* E and F only exist in the final combiner; varE/varF are NULL
             * before it, and this dereferenced them. */
            NV2A_UNIMPLEMENTED("combiner stage %d reads EF_PROD, which only "
                               "the final combiner defines; reads as zero",
                               ps->cur_stage);
            return mstring_from_str("vec4(0.0)");
        }
        return mstring_from_fmt("vec4(%s * %s, 0.0)",
                                mstring_get_str(ps->varE),
                                mstring_get_str(ps->varF));
    default:
        /* 0x6 and 0x7 are unassigned in PS_REGISTER. */
        NV2A_UNIMPLEMENTED("combiner stage %d uses reserved register 0x%x; "
                           "reads as zero", ps->cur_stage, reg);
        return mstring_from_str(is_dest ? "" : "vec4(0.0)");
    }
}

static MString* get_input_var(struct PixelShader *ps, struct InputInfo in, bool is_alpha)
{
    MString *reg = get_var(ps, in.reg, false);

    if (!is_alpha) {
        switch (in.chan) {
        case PS_CHANNEL_RGB:
            mstring_append(reg, ".rgb");
            break;
        case PS_CHANNEL_ALPHA:
            mstring_append(reg, ".aaa");
            break;
        default:
            assert(false);
            break;
        }
    } else {
        switch (in.chan) {
        case PS_CHANNEL_BLUE:
            mstring_append(reg, ".b");
            break;
        case PS_CHANNEL_ALPHA:
            mstring_append(reg, ".a");
            break;
        default:
            assert(false);
            break;
        }
    }

    MString *res;
    switch (in.mod) {
    case PS_INPUTMAPPING_UNSIGNED_IDENTITY:
        res = mstring_from_fmt("max(%s, 0.0)", mstring_get_str(reg));
        break;
    case PS_INPUTMAPPING_UNSIGNED_INVERT:
        res = mstring_from_fmt("(1.0 - clamp(%s, 0.0, 1.0))", mstring_get_str(reg));
        break;
    case PS_INPUTMAPPING_EXPAND_NORMAL:
        res = mstring_from_fmt("(2.0 * max(%s, 0.0) - 1.0)", mstring_get_str(reg));
        break;
    case PS_INPUTMAPPING_EXPAND_NEGATE:
        res = mstring_from_fmt("(-2.0 * max(%s, 0.0) + 1.0)", mstring_get_str(reg));
        break;
    case PS_INPUTMAPPING_HALFBIAS_NORMAL:
        res = mstring_from_fmt("(max(%s, 0.0) - 0.5)", mstring_get_str(reg));
        break;
    case PS_INPUTMAPPING_HALFBIAS_NEGATE:
        res = mstring_from_fmt("(-max(%s, 0.0) + 0.5)", mstring_get_str(reg));
        break;
    case PS_INPUTMAPPING_SIGNED_IDENTITY:
        mstring_ref(reg);
        res = reg;
        break;
    case PS_INPUTMAPPING_SIGNED_NEGATE:
        res = mstring_from_fmt("-%s", mstring_get_str(reg));
        break;
    default:
        assert(false);
        break;
    }

    mstring_unref(reg);
    return res;
}

static MString* get_output(MString *reg, int mapping)
{
    /*
     * The mapping is two fields, not an enum: bit 3 subtracts 0.5, bits 4-5
     * pick a scale of x1, x2, x4 or x0.5. The six PS_COMBINEROUTPUT_* names
     * are the six combinations D3D exposes; 0x28 (bias, x4) and 0x38 (bias,
     * x0.5) are the other two, and the switch this replaces asserted on them.
     * Decoding the fields separately gives every one of the eight a meaning
     * -- the one a fixed function unit would give it -- and produces the
     * same text as before for the six that were named. The two new ones are
     * unverified against silicon; no golden exercises them.
     */
    static const char *scale[4] = { NULL, " * 2.0", " * 4.0", " / 2.0" };
    bool bias = mapping & PS_COMBINEROUTPUT_BIAS;
    const char *sc = scale[(mapping >> 4) & 3];

    if (!bias && !sc) {
        mstring_ref(reg);
        return reg;
    }
    MString *base = bias ? mstring_from_fmt("(%s - 0.5)", mstring_get_str(reg))
                         : NULL;
    if (!sc) {
        return base;
    }
    MString *res = mstring_from_fmt("(%s%s)",
                                    base ? mstring_get_str(base)
                                         : mstring_get_str(reg),
                                    sc);
    if (base) {
        mstring_unref(base);
    }
    return res;
}

static MString* add_stage_code(struct PixelShader *ps,
                               struct InputVarInfo input,
                               struct OutputInfo output,
                               const char *write_mask, bool is_alpha)
{
    MString *ret = mstring_new();

    bool ab_needed = (output.ab != PS_REGISTER_DISCARD) ||
                     (output.muxsum != PS_REGISTER_DISCARD);
    bool cd_needed = (output.cd != PS_REGISTER_DISCARD) ||
                     (output.muxsum != PS_REGISTER_DISCARD);

    if (!ab_needed && !cd_needed) {
        return ret;
    }

    MString *a = ab_needed ? get_input_var(ps, input.a, is_alpha) : NULL;
    MString *b = ab_needed ? get_input_var(ps, input.b, is_alpha) : NULL;
    MString *c = cd_needed ? get_input_var(ps, input.c, is_alpha) : NULL;
    MString *d = cd_needed ? get_input_var(ps, input.d, is_alpha) : NULL;

    const char *caster = "";
    if (strlen(write_mask) == 3) {
        caster = "vec3";
    }

    MString *ab;
    if (!ab_needed) {
        ab = mstring_from_str("0.0");
    } else if (output.ab_op == PS_COMBINEROUTPUT_AB_DOT_PRODUCT) {
        ab = mstring_from_fmt("dot(%s, %s)",
                              mstring_get_str(a), mstring_get_str(b));
    } else {
        ab = mstring_from_fmt("(%s * %s)",
                              mstring_get_str(a), mstring_get_str(b));
    }

    MString *cd;
    if (!cd_needed) {
        cd = mstring_from_str("0.0");
    } else if (output.cd_op == PS_COMBINEROUTPUT_CD_DOT_PRODUCT) {
        cd = mstring_from_fmt("dot(%s, %s)",
                              mstring_get_str(c), mstring_get_str(d));
    } else {
        cd = mstring_from_fmt("(%s * %s)",
                              mstring_get_str(c), mstring_get_str(d));
    }

    MString *ab_mapping = get_output(ab, output.mapping);
    MString *cd_mapping = get_output(cd, output.mapping);
    MString *ab_dest = get_var(ps, output.ab, true);
    MString *cd_dest = get_var(ps, output.cd, true);
    MString *muxsum_dest = get_var(ps, output.muxsum, true);

    bool assign_ab = false;
    bool assign_cd = false;
    bool assign_muxsum = false;

    if (mstring_get_length(ab_dest)) {
        mstring_append_fmt(ps->code, "ab.%s = clamp(%s(%s), -1.0, 1.0);\n",
                           write_mask, caster, mstring_get_str(ab_mapping));
        assign_ab = true;
    } else {
        mstring_unref(ab_dest);
        mstring_ref(ab_mapping);
        ab_dest = ab_mapping;
    }

    if (mstring_get_length(cd_dest)) {
        mstring_append_fmt(ps->code, "cd.%s = clamp(%s(%s), -1.0, 1.0);\n",
                           write_mask, caster, mstring_get_str(cd_mapping));
        assign_cd = true;
    } else {
        mstring_unref(cd_dest);
        mstring_ref(cd_mapping);
        cd_dest = cd_mapping;
    }

    MString *muxsum = NULL;
    MString *muxsum_mapping = NULL;

    if (output.muxsum != PS_REGISTER_DISCARD) {
        if (output.muxsum_op == PS_COMBINEROUTPUT_AB_CD_SUM) {
            muxsum = mstring_from_fmt("(%s + %s)", mstring_get_str(ab),
                                      mstring_get_str(cd));
        } else {
            muxsum = mstring_from_fmt("((%s) ? %s(%s) : %s(%s))",
                                      (ps->flags & PS_COMBINERCOUNT_MUX_MSB) ?
                                          "r0.a >= 0.5" :
                                          "(uint(r0.a * 255.0) & 1u) == 1u",
                                      caster, mstring_get_str(cd), caster,
                                      mstring_get_str(ab));
        }

        muxsum_mapping = get_output(muxsum, output.mapping);
        if (mstring_get_length(muxsum_dest)) {
            mstring_append_fmt(ps->code, "mux_sum.%s = clamp(%s(%s), -1.0, 1.0);\n",
                               write_mask, caster, mstring_get_str(muxsum_mapping));
            assign_muxsum = true;
        }
    }

    if (assign_ab) {
        mstring_append_fmt(ret, "%s.%s = ab.%s;\n",
                           mstring_get_str(ab_dest), write_mask, write_mask);

        if (!is_alpha && output.flags & PS_COMBINEROUTPUT_AB_BLUE_TO_ALPHA) {
            mstring_append_fmt(ret, "%s.a = ab.b;\n",
                               mstring_get_str(ab_dest));
        }
    }
    if (assign_cd) {
        mstring_append_fmt(ret, "%s.%s = cd.%s;\n",
                           mstring_get_str(cd_dest), write_mask, write_mask);

        if (!is_alpha && output.flags & PS_COMBINEROUTPUT_CD_BLUE_TO_ALPHA) {
            mstring_append_fmt(ret, "%s.a = cd.b;\n",
                               mstring_get_str(cd_dest));
        }
    }
    if (assign_muxsum) {
        mstring_append_fmt(ret, "%s.%s = mux_sum.%s;\n",
                           mstring_get_str(muxsum_dest), write_mask, write_mask);
    }

    if (a) mstring_unref(a);
    if (b) mstring_unref(b);
    if (c) mstring_unref(c);
    if (d) mstring_unref(d);
    mstring_unref(ab);
    mstring_unref(cd);
    mstring_unref(ab_mapping);
    mstring_unref(cd_mapping);
    mstring_unref(ab_dest);
    mstring_unref(cd_dest);
    mstring_unref(muxsum_dest);
    if (muxsum) mstring_unref(muxsum);
    if (muxsum_mapping) mstring_unref(muxsum_mapping);

    return ret;
}

static void add_final_stage_code(struct PixelShader *ps, struct FCInputInfo final)
{
    ps->varE = get_input_var(ps, final.e, false);
    ps->varF = get_input_var(ps, final.f, false);

    MString *a = get_input_var(ps, final.a, false);
    MString *b = get_input_var(ps, final.b, false);
    MString *c = get_input_var(ps, final.c, false);
    MString *d = get_input_var(ps, final.d, false);
    MString *g = get_input_var(ps, final.g, true);

    mstring_append_fmt(ps->code, "fragColor.rgb = %s + mix(vec3(%s), vec3(%s), vec3(%s));\n",
                       mstring_get_str(d), mstring_get_str(c),
                       mstring_get_str(b), mstring_get_str(a));
    mstring_append_fmt(ps->code, "fragColor.a = %s;\n", mstring_get_str(g));

    mstring_unref(a);
    mstring_unref(b);
    mstring_unref(c);
    mstring_unref(d);
    mstring_unref(g);

    mstring_unref(ps->varE);
    mstring_unref(ps->varF);
    ps->varE = ps->varF = NULL;
}

/* NV097_SET_DOT_RGBMAPPING packs 4-bit nibbles; the hardware defines eight
 * modes. Anything above indexes past dotmap_funcs[]. */
static int dotmap_index(struct PixelShader *ps, int i)
{
    int m = ps->dot_map[i];
    if (m >= 8) {
        NV2A_UNIMPLEMENTED("dot mapping mode %d on stage %d; using "
                           "ZERO_TO_ONE", m, i);
        return 0;
    }
    return m;
}

/* Modes that leave a dot product behind for a later stage to consume. */
static bool mode_defines_dot(enum PS_TEXTUREMODES mode)
{
    switch (mode) {
    case PS_TEXTUREMODES_DOTPRODUCT:
    case PS_TEXTUREMODES_DOT_ST:
    case PS_TEXTUREMODES_DOT_ZW:
    case PS_TEXTUREMODES_DOT_RFLCT_DIFF:
    case PS_TEXTUREMODES_DOT_RFLCT_SPEC:
    case PS_TEXTUREMODES_DOT_STR_3D:
    case PS_TEXTUREMODES_DOT_STR_CUBE:
        return true;
    default:
        return false;
    }
}

/*
 * Emit what an inconsistent stage produces: a zero texel, and a zero dot
 * product if the mode would have defined one, so a later stage that names it
 * still compiles.
 */
static void emit_stage_as_none(MString *vars, int i, enum PS_TEXTUREMODES mode,
                               const char *why)
{
    if (mode_defines_dot(mode)) {
        mstring_append_fmt(vars, "float dot%d = 0.0;\n", i);
    }
    mstring_append_fmt(vars, "vec4 t%d = vec4(0.0); /* stage %d: %s */\n",
                       i, i, why);
}

/*
 * NV_texture_shader calls a stage *inconsistent* when it sits where its
 * inputs cannot exist -- DOT_ST needs a dot product from the stage before it,
 * DOT_RFLCT_SPEC needs two, a dependent read needs a texel -- or when the
 * feeding stages are not the modes that produce those inputs, and specifies
 * that an inconsistent stage behaves as NONE. The stage program is guest
 * data, so every combination is reachable, and before this the generator
 * either asserted on the first kind or emitted a reference to an undefined
 * dot%d on the second, which is a shader that generates, caches, and fails
 * to compile. Both now behave as NONE and are logged once per mode.
 */
static bool stage_consistent(struct PixelShader *ps, MString *vars, int i,
                             int lo, int hi, int dots_needed, const char *mode)
{
    const char *why = NULL;
    if (i < lo || i > hi) {
        why = "mode not valid in this stage";
    } else {
        for (int k = 1; k <= dots_needed; k++) {
            if (!mode_defines_dot(ps->tex_modes[i - k])) {
                why = "feeding stage produces no dot product";
                break;
            }
        }
    }
    if (!why) {
        return true;
    }
    NV2A_UNIMPLEMENTED("%s in texture stage %d: %s; treated as NONE",
                       mode, i, why);
    emit_stage_as_none(vars, i, ps->tex_modes[i], why);
    return false;
}

/*
 * Whether DOT_STR_3D's stage resolves to a samplerCube. get_sampler_type()
 * and the fetch have to agree on this or the shader will not compile, so both
 * ask here rather than each spelling the condition out.
 */
static bool dot_str_3d_is_cube(const struct PixelShader *ps, int i)
{
    const struct PshState *state = ps->state;
    return state->tex_cubemap[i] && !state->shadow_map[i] &&
           !(state->tex_x8y24[i] && ps->opts.vulkan);
}

static const char *get_sampler_type(struct PixelShader *ps, enum PS_TEXTUREMODES mode, int i)
{
    const char *sampler2D = "sampler2D";
    const char *sampler3D = "sampler3D";
    const char *samplerCube = "samplerCube";
    const struct PshState *state = ps->state;
    int dim = state->dim_tex[i];

    // FIXME: Cleanup
    switch (mode) {
    default:
    case PS_TEXTUREMODES_NONE:
        return NULL;

    case PS_TEXTUREMODES_PROJECT2D:
        if (state->shadow_map[i] && dim != 2) {
            /* psh_append_shadowmap() samples a 2D projection. */
            NV2A_UNIMPLEMENTED("%dD shadow map on stage %d", dim, i);
            ps->tex_unusable[i] = true;
            return NULL;
        }
        if (dim == 2) {
            if (state->tex_x8y24[i] && ps->opts.vulkan) {
                return "usampler2D";
            }
            if (state->tex_cubemap[i]) {
                return samplerCube;
            }
            return sampler2D;
        }
        if (dim == 3) {
            if (state->tex_x8y24[i] && ps->opts.vulkan) {
                NV2A_UNIMPLEMENTED("3D depth texture on stage %d", i);
                ps->tex_unusable[i] = true;
                return NULL;
            }
            return sampler3D;
        }
        NV2A_UNIMPLEMENTED("%dD texture in mode %d on stage %d", dim, mode, i);
        ps->tex_unusable[i] = true;
        return NULL;

    case PS_TEXTUREMODES_BUMPENVMAP:
    case PS_TEXTUREMODES_BUMPENVMAP_LUM:
    case PS_TEXTUREMODES_DOT_ST:
        if (state->shadow_map[i]) {
            /* A depth format bound to a bump or dot stage: sample it as a
             * colour texture rather than stop. */
            NV2A_UNIMPLEMENTED("shadow map in mode %d on stage %d; sampled "
                               "as colour", mode, i);
        }
        if (dim == 2) return sampler2D;
        if (dim == 3 && mode != PS_TEXTUREMODES_DOT_ST) return sampler3D;
        NV2A_UNIMPLEMENTED("%dD texture in mode %d on stage %d", dim, mode, i);
        ps->tex_unusable[i] = true;
        return NULL;

    case PS_TEXTUREMODES_DOT_STR_3D:
        /*
         * A cubemap-flagged stage gets a VK_IMAGE_VIEW_TYPE_CUBE view, so
         * declaring sampler2D here is VUID-vkCmdDrawIndexed-viewType-07752:
         * the fetch is undefined, and undefined is what it looked like --
         * Texture_cubemap's six DotSTR3D_* captures differed from themselves
         * between two runs of one binary, one of them by 42,554 px, while the
         * other 71 captures in the suite were byte-identical. Every other
         * cube-capable mode below already checks this flag.
         *
         * PROJECT3D is deliberately NOT folded in here despite sharing the
         * rest of this logic: it emits textureProj(), which has no cube form,
         * so returning samplerCube for it would trade a wrong result for a
         * shader that does not compile. It carries the same latent violation
         * and wants its own fix.
         */
        if (dot_str_3d_is_cube(ps, i)) {
            return samplerCube;
        }
        /* fallthrough */
    case PS_TEXTUREMODES_PROJECT3D:
        if (state->tex_x8y24[i] && ps->opts.vulkan) {
            return "usampler2D";
        }
        if (state->shadow_map[i]) {
            if (dim != 2) {
                NV2A_UNIMPLEMENTED("%dD shadow map on stage %d", dim, i);
                ps->tex_unusable[i] = true;
                return NULL;
            }
            return sampler2D;
        }
        if (dim != 2 && dim != 3) {
            NV2A_UNIMPLEMENTED("%dD texture in mode %d on stage %d", dim, mode, i);
            ps->tex_unusable[i] = true;
            return NULL;
        }
        return dim == 2 ? sampler2D : sampler3D;

    case PS_TEXTUREMODES_CUBEMAP:
    case PS_TEXTUREMODES_DOT_RFLCT_DIFF:
    case PS_TEXTUREMODES_DOT_RFLCT_SPEC:
    case PS_TEXTUREMODES_DOT_RFLCT_SPEC_CONST:
    case PS_TEXTUREMODES_DOT_STR_CUBE:
        if (state->shadow_map[i]) {
            NV2A_UNIMPLEMENTED("shadow map in mode %d on stage %d; sampled "
                               "as colour", mode, i);
        }
        if (dim != 2) {
            NV2A_UNIMPLEMENTED("%dD texture in cube mode %d on stage %d",
                               dim, mode, i);
            ps->tex_unusable[i] = true;
            return NULL;
        }
        if (state->tex_cubemap[i]) {
            return samplerCube;
        }
        return sampler2D;

    case PS_TEXTUREMODES_DPNDNT_AR:
    case PS_TEXTUREMODES_DPNDNT_GB:
        if (state->shadow_map[i]) {
            NV2A_UNIMPLEMENTED("shadow map in mode %d on stage %d; sampled "
                               "as colour", mode, i);
        }
        if (dim != 2) {
            NV2A_UNIMPLEMENTED("%dD texture in dependent mode %d on stage %d",
                               dim, mode, i);
            ps->tex_unusable[i] = true;
            return NULL;
        }
        return sampler2D;
    }
}

static const char *shadow_comparison_map[] = {
    [SHADOW_DEPTH_FUNC_LESS] = "<",
    [SHADOW_DEPTH_FUNC_EQUAL] = "==",
    [SHADOW_DEPTH_FUNC_LEQUAL] = "<=",
    [SHADOW_DEPTH_FUNC_GREATER] = ">",
    [SHADOW_DEPTH_FUNC_NOTEQUAL] = "!=",
    [SHADOW_DEPTH_FUNC_GEQUAL] = ">=",
};

static void psh_append_shadowmap(const struct PixelShader *ps, int i, bool compare_z, MString *vars)
{
    if (ps->state->shadow_depth_func == SHADOW_DEPTH_FUNC_NEVER) {
        mstring_append_fmt(vars, "vec4 t%d = vec4(0.0);\n", i);
        return;
    }

    if (ps->state->shadow_depth_func == SHADOW_DEPTH_FUNC_ALWAYS) {
        mstring_append_fmt(vars, "vec4 t%d = vec4(1.0);\n", i);
        return;
    }

    g_autofree gchar *normalize_tex_coords = g_strdup_printf("norm%d", i);
    const char *tex_remap = ps->state->rect_tex[i] ? normalize_tex_coords : "";

    const char *comparison = shadow_comparison_map[ps->state->shadow_depth_func];

    bool extract_msb_24b = ps->state->tex_x8y24[i] && ps->opts.vulkan;

    mstring_append_fmt(
        vars, "%svec4 t%d_depth%s = textureProj(texSamp%d, %s(pT%d.xyw));\n",
        extract_msb_24b ? "u" : "", i, extract_msb_24b ? "_raw" : "", i,
        tex_remap, i);

    if (extract_msb_24b) {
    mstring_append_fmt(vars,
                           "vec4 t%d_depth = vec4(float(t%d_depth_raw.x >> 8) "
                           "/ 16777215.0, 1.0, 0.0, 0.0);\n",
                           i, i);
    }

    if (compare_z && ps->state->tex_depth_float[i]) {
        /*
         * The texture holds the float depth encoding, normalised by the host
         * UNORM format. Recover the integer and decode it -- the inverse of
         * convert_f16_to_float / convert_f24_to_float in pgraph/util.h --
         * instead of scaling by f16_max, which assumed the texture held a
         * linear value. It never did for a texture read from guest memory,
         * and since psh_convert started storing the encoding it does not for
         * a rendered depth surface either (issue #30).
         */
        if (extract_msb_24b) {
            mstring_append_fmt(vars, "uint t%d_enc = t%d_depth_raw.x >> 8;\n",
                               i, i);
        } else {
            mstring_append_fmt(
                vars, "uint t%d_enc = uint(roundEven(t%d_depth.x * %s));\n",
                i, i, ps->state->tex_x8y24[i] ? "16777215.0" : "65535.0");
        }
        if (ps->state->tex_x8y24[i]) {
            mstring_append_fmt(
                vars,
                "float t%d_z = uintBitsToFloat(t%d_enc << 7);\n"
                "pT%d.z = clamp(pT%d.z / pT%d.w, 0.0, 1e30);\n" /* f24_max */
                "pT%d.z = uintBitsToFloat(floatBitsToUint(pT%d.z) & 0xFFFFFF80u);\n",
                i, i, i, i, i, i, i);
        } else {
            /* NOTE: the reference is quantised onto the F16 grid below with a
             * flush-to-zero threshold of 2^-7, where the depth *write* in
             * psh_convert now uses 2^-6 -- an F16 exponent field of zero means
             * zero, so the lowest binade has no representation. The two want
             * the same grid. Left alone deliberately: this is the
             * `Texture shadow comparator` cell (#30) with its own goldens, and
             * only the lowest binade of a reference depth can differ, so it is
             * a separate measurement rather than a free ride on this one. */
            mstring_append_fmt(
                vars,
                "float t%d_z = t%d_enc == 0u ? 0.0\n"
                "           : uintBitsToFloat((t%d_enc << 11) + 0x3C000000u);\n"
                "pT%d.z = clamp(pT%d.z / pT%d.w, 0.0, 511.9375);\n" /* f16_max */
                "pT%d.z = floatBitsToUint(pT%d.z) < 0x3C000000u ? 0.0\n"
                "       : uintBitsToFloat(((floatBitsToUint(pT%d.z)\n"
                "                           - 0x3C000000u) & 0xFFFFF800u)\n"
                "                         + 0x3C000000u);\n",
                i, i, i, i, i, i, i, i, i);
        }
        mstring_append_fmt(vars, "vec4 t%d = vec4(t%d_z %s pT%d.z ? 1.0 : 0.0);\n",
                           i, i, comparison, i);
        return;
    }

    // Depth.y != 0 indicates 24 bit; depth.z != 0 indicates float.
    if (compare_z) {
        mstring_append_fmt(
            vars,
            "float t%d_max_depth;\n"
            "if (t%d_depth.y > 0.0) {\n"
            "  t%d_max_depth = 16777215.0;\n"
            "} else {\n"
            "  t%d_max_depth = t%d_depth.z > 0.0 ? 511.9375 : 65535.0;\n"
            "}\n"
            "t%d_depth.x *= t%d_max_depth;\n"
            "pT%d.z = clamp(pT%d.z / pT%d.w, 0.0, t%d_max_depth);\n"
            "pT%d.z = t%d_max_depth > 512.0 ? floor(pT%d.z) : pT%d.z;\n"
            "vec4 t%d = vec4(t%d_depth.x %s pT%d.z ? 1.0 : 0.0);\n",
            i, i, i, i, i,
            i, i, i, i, i, i,
            i, i, i, i,
            i, i, comparison, i);
    } else {
        mstring_append_fmt(
            vars,
            "vec4 t%d = vec4(t%d_depth.x %s 0.0 ? 1.0 : 0.0);\n",
            i, i, comparison);
    }
}

// Adjust the s, t coordinates in the given VAR to account for the 4 texel
// border supported by the hardware.
static void apply_border_adjustment(const struct PixelShader *ps, MString *vars, int tex_index, const char *var_template)
{
    int i = tex_index;
    if (ps->state->border_logical_size[i][0] == 0.0f) {
        return;
    }

    char var_name[32] = {0};
    snprintf(var_name, sizeof(var_name), var_template, i);

    if (ps->state->tex_cubemap[i]) {
        mstring_append_fmt(
            vars,
            "%s.xyz = remapBorderCube(%s.xyz, vec2(%f, %f), vec2(%f, %f));\n",
            var_name, var_name,
            ps->state->border_logical_size[i][0], ps->state->border_logical_size[i][1],
            ps->state->border_inv_real_size[i][0], ps->state->border_inv_real_size[i][1]);
        return;
    }

    mstring_append_fmt(
        vars,
        "vec3 t%dLogicalSize = vec3(%f, %f, %f);\n"
        "%s.xyz = (%s.xyz * t%dLogicalSize + vec3(4.0, 4.0, 4.0)) * vec3(%f, %f, %f);\n",
        i, ps->state->border_logical_size[i][0], ps->state->border_logical_size[i][1], ps->state->border_logical_size[i][2],
        var_name, var_name, i, ps->state->border_inv_real_size[i][0], ps->state->border_inv_real_size[i][1], ps->state->border_inv_real_size[i][2]);
}

static void apply_convolution_filter(const struct PixelShader *ps, MString *vars, int tex)
{
    assert(ps->state->dim_tex[tex] == 2);

    g_autofree gchar *normalize_tex_coords = g_strdup_printf("norm%d", tex);
    const char *tex_remap = ps->state->rect_tex[tex] ? normalize_tex_coords : "";

    static const float offsets[9][2] = {
        {-1,-1},{0,-1},{1,-1},{-1,0},{0,0},{1,0},{-1,1},{0,1},{1,1}
    };
    static const char *weights[9] = {
        "1.0/16.0","2.0/16.0","1.0/16.0",
        "2.0/16.0","4.0/16.0","2.0/16.0",
        "1.0/16.0","2.0/16.0","1.0/16.0"
    };

    mstring_append_fmt(vars,
        "vec4 t%d;\n"
        "{\n"
        "vec2 convTexelSize = 1.0 / vec2(textureSize(texSamp%d, 0));\n"
        "vec3 convBase = %s(pT%d.xyw);\n",
        tex, tex, tex_remap, tex);
    mstring_append_fmt(vars, "t%d = ", tex);
    for (int i = 0; i < 9; i++) {
        mstring_append_fmt(vars,
            "%stextureProj(texSamp%d, convBase + vec3(vec2(%.1f,%.1f)*convTexelSize, 0.0)) * %s",
            i > 0 ? "\n  + " : "",
            tex, offsets[i][0], offsets[i][1], weights[i]);
    }
    mstring_append(vars, ";\n}\n");
}

static void define_colorkey_comparator(MString *preflight)
{
    // clang-format off
    mstring_append(
        preflight,
        "bool check_color_key(vec4 texel, uint color_key, uint color_key_mask) {\n"
        "    uvec4 c = uvec4(texel * 255.0 + 0.5);\n"
        "    uint color = (c.a << 24) | (c.r << 16) | (c.g << 8) | c.b;\n"
        "    return (color & color_key_mask) == (color_key & color_key_mask);\n"
        "}\n");
    // clang-format on
}



/*
 * One channel of a bump environment map's input texture, signed the way
 * the hardware signs it. The filter register flags each channel on its
 * own: a flagged channel is two's complement per texel and then filtered
 * (the Bump map goldens sweep through zero across a 0x7f/0x80 boundary),
 * an unflagged one is filtered unsigned and the eight-bit result is then
 * read as two's complement (the same boundary is a hard step). The sampler
 * can only be signed as a whole, so with a mix of flags the unflagged
 * channels are rebuilt from a gather of the signed texels; that path
 * filters at the base level only.
 */
static void append_bump_channel(const struct PixelShader *ps, MString *vars,
                                int i, int k, int comp, uint32_t flag_bit,
                                bool luminance, const char *name,
                                bool gather_ok)
{
    static const char chan[] = "rgba";
    bool flagged = ps->state->tex_signed[k] & flag_bit;
    bool snorm = ps->state->snorm_tex[k];
    const char *c = &chan[comp];

    if (flagged && snorm) {
        /* The sampler signed and filtered it. */
        if (luminance) {
            mstring_append_fmt(vars, "float %s = sign3_to_0_to_1(bump_snorm(t%d.%c));\n", name, k, *c);
        } else {
            mstring_append_fmt(vars, "float %s = bump_snorm(t%d.%c);\n", name, k, *c);
        }
    } else if (flagged && gather_ok) {
        /* Signed on a format the sampler holds unsigned. */
        if (luminance) {
            mstring_append_fmt(vars, "float %s = sign3_to_0_to_1(bump_signed_gather(textureGather(texSamp%d, bumpUV%d, %d), bumpF%d));\n",
                               name, k, i, comp, i);
        } else {
            mstring_append_fmt(vars, "float %s = bump_signed_gather(textureGather(texSamp%d, bumpUV%d, %d), bumpF%d);\n",
                               name, k, i, comp, i);
        }
    } else if (!flagged && snorm && gather_ok) {
        /* Unsigned next to a signed sibling: back to bytes, filtered
         * unsigned, then read as two's complement. */
        if (luminance) {
            mstring_append_fmt(vars, "float %s = bump_unsigned_gather(textureGather(texSamp%d, bumpUV%d, %d), bumpF%d);\n",
                               name, k, i, comp, i);
        } else {
            mstring_append_fmt(vars, "float %s = bump_signed(bump_unsigned_gather(textureGather(texSamp%d, bumpUV%d, %d), bumpF%d));\n",
                               name, k, i, comp, i);
        }
    } else if (snorm) {
        /* No way to rebuild the unsigned value: take the signed one. */
        if (luminance) {
            mstring_append_fmt(vars, "float %s = sign3_to_0_to_1(bump_snorm(t%d.%c));\n", name, k, *c);
        } else {
            mstring_append_fmt(vars, "float %s = bump_snorm(t%d.%c);\n", name, k, *c);
        }
    } else {
        /* Unsigned sampler, filtered unsigned; the offsets are then read as
         * two's complement (a flagged channel lands here only when the
         * input mode gives the gather nothing to work with). */
        if (luminance) {
            mstring_append_fmt(vars, "float %s = bump_unsigned(t%d.%c);\n", name, k, *c);
        } else {
            mstring_append_fmt(vars, "float %s = bump_signed(t%d.%c);\n", name, k, *c);
        }
    }
}

/* The gather path above needs the input stage's sampling position; it is
 * only available for a plain projective 2D input. Emits bumpUV/bumpF for
 * stage i from texture k and says whether it could. */
static bool append_bump_coords(const struct PixelShader *ps, MString *vars, int i, int k)
{
    if (ps->tex_modes[k] != PS_TEXTUREMODES_PROJECT2D ||
        ps->state->dim_tex[k] != 2 || ps->state->tex_cubemap[k] ||
        ps->state->conv_tex[k] != CONVOLUTION_FILTER_DISABLED) {
        return false;
    }
    if (ps->state->rect_tex[k]) {
        mstring_append_fmt(vars, "vec2 bumpUV%d = norm%d(pT%d.xy / pT%d.w);\n", i, k, k, k);
    } else {
        mstring_append_fmt(vars, "vec2 bumpUV%d = pT%d.xy / pT%d.w;\n", i, k, k);
    }
    mstring_append_fmt(vars,
                       "vec2 bumpF%d = fract(bumpUV%d * vec2(textureSize(texSamp%d, 0)) - 0.5);\n",
                       i, i, k);
    return true;
}

/*
 * The fog factor, applied to the interpolated fog coordinate here rather
 * than at the vertices: the Fog suite's exp captures shade smoothly across
 * a triangle spanning depths 50 to 200, where a factor interpolated from the
 * vertices gives a flatter gradient. What the hardware makes of the fog
 * parameters, read off the Fog param goldens (coordinate swept from -1.4 in
 * 0.01 steps at multipliers of +-2, +-1, +-0.5, +-0.25, and the bias swept
 * from 1.0 in 0.005 steps with the multiplier at 0):
 *
 *   linear      f = bias + m d - 1
 *   linear_abs  f = bias + m |d| - 1
 *   exp         f = 2^(16 x)        with x = bias + m d - 1.5
 *   exp_abs     f = 2^(-16 |x|)
 *   exp2        f = 2^(-32 x^2)
 *   exp2_abs    f = 2^(-32 x^2)
 *
 * The bias enters the exponent, and for exp2 the bias sweep is a Gaussian
 * about 1.5, not an exponential, so bias and distance combine before the
 * square. The _abs modes take the magnitude of the distance for linear and
 * of the exponent for exp; exp2's is already even. With D3D's parameters
 * (bias 1.5, m = -density / (2 ln 256) or -density / (2 sqrt(ln 256))) exp
 * reduces to e^(-density d) and exp2 to e^(-(density d)^2).
 *
 * An infinite or NaN coordinate (flagged by the vertex shader, since the
 * value itself cannot be interpolated) and a NaN factor take a fixed
 * result: 1 for linear, linear_abs and exp, 0 for the rest.
 *
 * The factor reaches the combiner as eight bits, and the hardware truncates
 * rather than rounds: with the linear sweeps' diffuse of (0, 0, 1) and fog
 * colour of (1, 0, 0) the captures hold exactly floor(255 f) in blue and
 * 255 minus that in red. A guard of 1/32 of a step absorbs the hardware's
 * own arithmetic noise: with it 2550 of the 2560 linear quads match,
 * without it 2524, and rounding to nearest gets 2124. The exponential
 * modes truncate too, but what they truncate is the hardware's own
 * approximation of 2^x, which sits above the true value by up to a step
 * at small factors and is not modelled here; until it is, rounding the
 * exact exponential lands closer to the captures than truncating it
 * (2352 of 2560 exp quads against 2154), so only the linear modes truncate.
 */
static void append_fog_factor(const struct PixelShader *ps, MString *vars,
                              const char *lin)
{
    if (!ps->state->fog_enable) {
        mstring_append(vars, "vec4 pFog = vec4(fogColor.rgb, 1.0);\n");
        return;
    }

    const char *factor;
    const char *special;
    switch (ps->state->fog_mode) {
    case FOG_MODE_LINEAR:
        factor = "fogParam.x + fogCoord * fogParam.y - 1.0";
        special = "1.0";
        break;
    case FOG_MODE_LINEAR_ABS:
        factor = "fogParam.x + abs(fogCoord) * fogParam.y - 1.0";
        special = "1.0";
        break;
    case FOG_MODE_EXP:
        factor = "exp2(16.0 * fogX)";
        special = "1.0";
        break;
    case FOG_MODE_EXP_ABS:
        factor = "exp2(-16.0 * abs(fogX))";
        special = "0.0";
        break;
    case FOG_MODE_EXP2:
    case FOG_MODE_EXP2_ABS:
        factor = "exp2(-32.0 * fogX * fogX)";
        special = "0.0";
        break;
    default:
        assert(!"Invalid fog mode");
        factor = "1.0";
        special = "1.0";
        break;
    }

    mstring_append_fmt(vars,
                       "float fogCoord = vtxFog%s;\n"
                       "float fogX = fogParam.x + fogCoord * fogParam.y - 1.5;\n"
                       "float fogFactor = %s;\n"
                       "if (vtxFogSpecial > 0.5 || isnan(fogFactor)) {\n"
                       "  fogFactor = %s;\n"
                       "}\n"
                       "fogFactor = clamp(fogFactor, 0.0, 1.0);\n",
                       lin, factor, special);
    if (ps->state->fog_mode == FOG_MODE_LINEAR ||
        ps->state->fog_mode == FOG_MODE_LINEAR_ABS) {
        mstring_append(vars,
                       "fogFactor = floor(fogFactor * 255.0 + 0.03125) / 255.0;\n");
    }
    mstring_append(vars, "vec4 pFog = vec4(fogColor.rgb, fogFactor);\n");
}

/* Does a later stage read stage i's texel as raw bytes (a bump map or a
 * dot-product input)?  Those paths apply the channel signs themselves. */
static bool stage_consumed_raw(const struct PixelShader *ps, int i)
{
    for (int j = i + 1; j < 4; j++) {
        if (ps->input_tex[j] != i) {
            continue;
        }
        switch (ps->tex_modes[j]) {
        case PS_TEXTUREMODES_BUMPENVMAP:
        case PS_TEXTUREMODES_BUMPENVMAP_LUM:
        case PS_TEXTUREMODES_DOTPRODUCT:
        case PS_TEXTUREMODES_DOT_ST:
        case PS_TEXTUREMODES_DOT_ZW:
        case PS_TEXTUREMODES_DOT_RFLCT_DIFF:
        case PS_TEXTUREMODES_DOT_RFLCT_SPEC:
        case PS_TEXTUREMODES_DOT_RFLCT_SPEC_CONST:
        case PS_TEXTUREMODES_DOT_STR_3D:
        case PS_TEXTUREMODES_DOT_STR_CUBE:
        case PS_TEXTUREMODES_DPNDNT_AR:
        case PS_TEXTUREMODES_DPNDNT_GB:
            return true;
        default:
            break;
        }
    }
    return false;
}

static MString* psh_convert(struct PixelShader *ps)
{
    MString *preflight = mstring_new();

    /*
     * A texture coordinate that is mathematically on an exact texel boundary
     * reaches the sampler a few ULP either side of it: it is fp32 interpolated
     * across the primitive and then divided by w and by the texture size.
     * Which side it lands on decides which texel `floor` picks, so a boundary
     * the guest placed exactly on a pixel centre renders a texel over
     * depending on nothing but host arithmetic.  Measured on one such
     * boundary, the centre column of Texture_render_target: hardware,
     * lavapipe and Adreno resolve these ties three different ways and in both
     * directions, and three Adreno drivers from two vendors agree with each
     * other, so this is our arithmetic meeting a different FP unit rather than
     * driver variance.
     *
     * Bias the coordinate up by a fraction of a texel large enough to cover
     * that noise (2^-18 of the texture, about fifteen times the fp32 error on
     * an interpolated coordinate) and far below any subtexel position a guest
     * can express: 0.001 texels on a 256 texture.  A coordinate exactly on a
     * boundary then lands on it; one genuinely below stays below.
     *
     * Both axes are biased, but they rest on different arguments and the v
     * half is the weaker one.  Hardware's u-ties resolve up in every quad
     * measured, so biasing u moves us onto its answer.  Its v-ties do not:
     * they go down at texels 40, 80 and 120 and up at 160, 200 and 240 on one
     * quad, and down at texel 128 on a quad whose u-tie at the same value
     * goes up -- the signature of a rasteriser accumulating u along the
     * scanline and v between scanlines.  There is no v rule to move onto, so
     * v was shipped at b844a486 on a narrower case: the hosts disagree in v
     * and a bias at least makes them agree, which the device lane confirmed.
     *
     * v is not free, and its cost is larger than that commit recorded.  It
     * charged 285 px across 179 lighting and material captures, isolated
     * pixels at checkerboard cell corners where a u-tie and a v-tie coincide
     * and the diagonal texel is the other colour.  Measured since against the
     * bump disc, which was not in that sweep, v also costs Bump_env_lum
     * 3,910 px.  The change is still net positive -- Point_params gains
     * 12,027 px -- but by roughly 7,800 rather than 11,700.
     * docs/investigations/edge-defect.md carries the measurements.
     */
    mstring_append(preflight,
                   "const vec2 texelTieBias = vec2(1.0 / 262144.0, 1.0 / 262144.0);\n");
    pgraph_glsl_get_vtx_header(preflight, ps->opts.vulkan,
                             ps->state->smooth_shading,
                             ps->state->noperspective, true, false, false);

    if (ps->opts.vulkan) {
        if (ps->opts.ubo_set > 0) {
            mstring_append_fmt(
                preflight,
                "layout(location = 0) out vec4 fragColor;\n"
                "layout(set = %d, binding = %d, std140) uniform PshUniforms {\n",
                ps->opts.ubo_set, ps->opts.ubo_binding);
        } else {
            mstring_append_fmt(
                preflight,
                "layout(location = 0) out vec4 fragColor;\n"
                "layout(binding = %d, std140) uniform PshUniforms {\n",
                ps->opts.ubo_binding);
        }
    } else {
        mstring_append_fmt(preflight,
                           "layout(location = 0) out vec4 fragColor;\n");
    }

    const char *u = ps->opts.vulkan ? "" : "uniform ";
    for (int i = 0; i < ARRAY_SIZE(PshUniformInfo); i++) {
        const UniformInfo *info = &PshUniformInfo[i];
        const char *type_str = uniform_element_type_to_str[info->type];
        if (info->count == 1) {
            mstring_append_fmt(preflight, "%s%s %s;\n", u, type_str,
                               info->name);
        } else {
            mstring_append_fmt(preflight, "%s%s %s[%zd];\n", u, type_str,
                               info->name, info->count);
        }
    }

    for (int i = 0; i < 9; i++) {
        for (int j = 0; j < 2; j++) {
            mstring_append_fmt(preflight, "#define c%d_%d consts[%d]\n", j, i, i*2+j);
        }
    }

    if (ps->opts.vulkan) {
        mstring_append(preflight, "};\n");
    }

    const char *dotmap_funcs[] = {
        "dotmap_zero_to_one",
        "dotmap_minus1_to_1_d3d",
        "dotmap_minus1_to_1_gl",
        "dotmap_minus1_to_1",
        "dotmap_hilo_1",
        "dotmap_hilo_hemisphere_d3d",
        "dotmap_hilo_hemisphere_gl",
        "dotmap_hilo_hemisphere",
    };

    mstring_append_fmt(preflight,
        "float sign1(float x) {\n"
        "    float xf = float(x) * 255.0;\n"
        "    return (xf - 128.0) / 127.0;\n"
        "}\n"
        "float sign2(float x) {\n"
        "    float xf = float(x) * 255.0;\n"
        "    if (xf >= 128.0) return (xf - 255.5) / 127.5;\n"
        "               else return (xf + 0.5) / 127.5;\n"
        "}\n"
        "float sign3(float x) {\n"
        "    float xf = float(x) * 255.0;\n"
        "    if (xf >= 128.0) return (xf - 256.0) / 127.0;\n"
        "               else return xf / 127.0;\n"
        "}\n"
        /* A texture channel flagged signed in NV_PGRAPH_TEXFILTER, as the
         * combiner receives it: two's complement over 127.5, so 0x7f is
         * 254/255 and 0x80 clamps to -1.  Not the dot-mapping rules above,
         * which divide by 127. */
        "float signed_channel(float x) {\n"
        "    float xf = float(x) * 255.0;\n"
        "    if (xf >= 128.0) xf -= 256.0;\n"
        "    return xf / 127.5;\n"
        "}\n"
        "float sign3_to_0_to_1(float x) {\n"
        "    if (x >= 0.0) return x/2.0;\n"
        "           else return 1.0+x/2.0;\n"
        "}\n"
        /* The bump environment map reads its offsets as two's complement bytes
         * over 128, not 127: the Bump map goldens' checkerboard phase sits a
         * texel and a half behind the /127 reading, which is 127/128 of the
         * way. What it reads is the filtered value rounded back to eight bits,
         * signed or not: the Bump env lum goldens step through 1, 2, 3 across
         * a 0x01/0x03 tent whichever way the channel is flagged, where an
         * unrounded sweep drifts. bump_signed takes an unsigned channel after
         * filtering; bump_snorm a channel the sampler already signed over 127;
         * bump_unsigned a luminance channel left unsigned. */
        "float bump_signed(float x) {\n"
        "    float xf = round(float(x) * 255.0);\n"
        "    if (xf >= 128.0) return (xf - 256.0) / 128.0;\n"
        "               else return xf / 128.0;\n"
        "}\n"
        "float bump_snorm(float x) {\n"
        "    return round(x * 127.0) / 128.0;\n"
        "}\n"
        "float bump_unsigned(float x) {\n"
        "    return round(x * 255.0) / 255.0;\n"
        "}\n"
        /* A flagged channel of a texture the sampler cannot hold signed (the
         * 16-bit formats): each texel two's complement first, then filtered,
         * the way the sampler does it for the formats it can sign. */
        "float bump_signed_gather(vec4 g, vec2 f) {\n"
        "    vec4 sg = vec4(bump_signed(g.x), bump_signed(g.y), bump_signed(g.z), bump_signed(g.w));\n"
        "    float v = mix(mix(sg.w, sg.z, f.x), mix(sg.x, sg.y, f.x), f.y);\n"
        "    return round(v * 128.0) / 128.0;\n"
        "}\n"
        /* A channel the filter register leaves unsigned while a sibling is
         * signed: the sampler holds the whole texture signed, so the four
         * texels come back over 127 (with -128 clamped to -1) and are turned
         * back into their bytes, filtered as the unsigned values they are,
         * and only then read as two's complement. The filtered value is an
         * eight-bit one on the hardware (a 0x7f/0x80 boundary steps at the
         * midpoint of the tent, not at its end), so it is rounded back to a
         * byte. g is a textureGather result, f the bilinear weights. */
        "float bump_unsigned_gather(vec4 g, vec2 f) {\n"
        "    vec4 b = round(g * 127.0);\n"
        "    b += vec4(lessThan(b, vec4(0.0))) * 256.0;\n"
        "    b = mix(b, vec4(128.0), vec4(equal(g, vec4(-1.0))));\n"
        "    vec4 u = b / 255.0;\n"
        "    float v = mix(mix(u.w, u.z, f.x), mix(u.x, u.y, f.x), f.y);\n"
        "    return round(v * 255.0) / 255.0;\n"
        "}\n"
        "vec3 dotmap_zero_to_one(vec4 col) {\n"
        "    return col.rgb;\n"
        "}\n"
        "vec3 dotmap_minus1_to_1_d3d(vec4 col) {\n"
        "    return vec3(sign1(col.r),sign1(col.g),sign1(col.b));\n"
        "}\n"
        "vec3 dotmap_minus1_to_1_gl(vec4 col) {\n"
        "    return vec3(sign2(col.r),sign2(col.g),sign2(col.b));\n"
        "}\n"
        "vec3 dotmap_minus1_to_1(vec4 col) {\n"
        "    return vec3(sign3(col.r),sign3(col.g),sign3(col.b));\n"
        "}\n"
        "vec3 dotmap_hilo_1(vec4 col) {\n"
        "    uint hi_i = uint(col.a * float(0xff)) << 8\n"
        "              | uint(col.r * float(0xff));\n"
        "    uint lo_i = uint(col.g * float(0xff)) << 8\n"
        "              | uint(col.b * float(0xff));\n"
        "    float hi_f = float(hi_i) / float(0xffff);\n"
        "    float lo_f = float(lo_i) / float(0xffff);\n"
        "    return vec3(hi_f, lo_f, 1.0);\n"
        "}\n"
        "vec3 dotmap_hilo_hemisphere_d3d(vec4 col) {\n"
        "    return col.rgb;\n" // FIXME
        "}\n"
        "vec3 dotmap_hilo_hemisphere_gl(vec4 col) {\n"
        "    return col.rgb;\n" // FIXME
        "}\n"
        /* Signed HILO with the hemisphere completion of NV_texture_shader:
         * the two 16-bit components are two's complement over 32767 (the
         * 8-bit MINUS1_TO_1 rule, sign3, at 16 bits) and the third is
         * sqrt(1 - hi^2 - lo^2).  The D3D and GL variants are rejected by
         * the hardware (Texture_cubemap skips them: invalid data error),
         * so only this one can be checked. */
        "vec3 dotmap_hilo_hemisphere(vec4 col) {\n"
        "    uint hi_i = uint(col.a * float(0xff)) << 8\n"
        "              | uint(col.r * float(0xff));\n"
        "    uint lo_i = uint(col.g * float(0xff)) << 8\n"
        "              | uint(col.b * float(0xff));\n"
        "    float hi_f = (hi_i >= 0x8000u ? float(hi_i) - 65536.0 : float(hi_i)) / 32767.0;\n"
        "    float lo_f = (lo_i >= 0x8000u ? float(lo_i) - 65536.0 : float(lo_i)) / 32767.0;\n"
        "    return vec3(hi_f, lo_f, sqrt(max(0.0, 1.0 - hi_f * hi_f - lo_f * lo_f)));\n"
        "}\n"
        "const float[9] gaussian3x3 = float[9](\n"
        "    1.0/16.0, 2.0/16.0, 1.0/16.0,\n"
        "    2.0/16.0, 4.0/16.0, 2.0/16.0,\n"
        "    1.0/16.0, 2.0/16.0, 1.0/16.0);\n"
        "const vec2[9] convolution3x3 = vec2[9](\n"
        "    vec2(-1.0,-1.0),vec2(0.0,-1.0),vec2(1.0,-1.0),\n"
        "    vec2(-1.0, 0.0),vec2(0.0, 0.0),vec2(1.0, 0.0),\n"
        "    vec2(-1.0, 1.0),vec2(0.0, 1.0),vec2(1.0, 1.0));\n"
        /* A bordered cube face is a 2n-square image with the n-square
         * interior at (4,4), like a bordered 2D texture.  A cube lookup is by
         * direction, so the step onto the interior happens on the face the
         * direction selects: project to that face, remap (s,t) the 2D way,
         * and rebuild a direction on the same face.  Face conventions are
         * the Vulkan/GL ones. */
        "vec3 remapBorderCube(vec3 d, vec2 logical, vec2 invReal) {\n"
        "    vec3 a = abs(d);\n"
        "    vec2 st; int face;\n"
        "    if (a.x >= a.y && a.x >= a.z) {\n"
        "        face = d.x > 0.0 ? 0 : 1;\n"
        "        st = vec2(d.x > 0.0 ? -d.z : d.z, -d.y) / a.x;\n"
        "    } else if (a.y >= a.z) {\n"
        "        face = d.y > 0.0 ? 2 : 3;\n"
        "        st = vec2(d.x, d.y > 0.0 ? d.z : -d.z) / a.y;\n"
        "    } else {\n"
        "        face = d.z > 0.0 ? 4 : 5;\n"
        "        st = vec2(d.z > 0.0 ? d.x : -d.x, -d.y) / a.z;\n"
        "    }\n"
        "    st = ((st * 0.5 + 0.5) * logical + 4.0) * invReal * 2.0 - 1.0;\n"
        "    if (face == 0) return vec3(1.0, -st.y, -st.x);\n"
        "    if (face == 1) return vec3(-1.0, -st.y, st.x);\n"
        "    if (face == 2) return vec3(st.x, 1.0, st.y);\n"
        "    if (face == 3) return vec3(st.x, -1.0, -st.y);\n"
        "    if (face == 4) return vec3(st.x, -st.y, 1.0);\n"
        "    return vec3(-st.x, -st.y, -1.0);\n"
        "}\n"
        "vec2 remapCubeTo2D(vec3 texCoord) {\n"
        "    vec2 uv;\n"
        "    vec3 absTexCoord = abs(texCoord);\n"
        "    if (absTexCoord.x > absTexCoord.y && absTexCoord.x > absTexCoord.z) {\n"
        "        if (texCoord.x > 0.0) {\n"
        "            // +X: Right\n"
        "            uv = vec2(-texCoord.z, texCoord.y);\n"
        "        } else {\n"
        "            // -X: Left\n"
        "            uv = vec2(texCoord.z, texCoord.y);\n"
        "        }\n"
        "        uv /= absTexCoord.x;\n"
        "    }\n"
        "    else if (absTexCoord.y > absTexCoord.x && absTexCoord.y > absTexCoord.z) {\n"
        "        if (texCoord.y > 0.0) {\n"
        "            // +Y: Top\n"
        "            uv = vec2(texCoord.x, -texCoord.z);\n"
        "        } else {\n"
        "            // -Y: Bottom\n"
        "            uv = vec2(texCoord.x, texCoord.z);\n"
        "        }\n"
        "        uv /= absTexCoord.y;\n"
        "    }\n"
        "    else {\n"
        "        if (texCoord.z > 0.0) {\n"
        "            // +Z: Front\n"
        "            uv = vec2(texCoord.x, texCoord.y);\n"
        "        } else {\n"
        "            // -Z: Back\n"
        "            uv = vec2(-texCoord.x, texCoord.y);\n"
        "        }\n"
        "        uv /= absTexCoord.z;\n"
        "    }\n"
        "    return uv;\n"
        "}\n"
        "\n"
        "vec3 remap2DToCube(vec3 texCoord2DProjective) {\n"
        "    vec2 st = (texCoord2DProjective.xy / texCoord2DProjective.z);"
        "    return normalize(vec3(1.0, st.y, -st.x));"
        "}\n"
        );

    if (ps->state->depth_needed) {
        mstring_append(preflight,
            "float kahan_det(vec2 a, vec2 b) {\n"
            "    precise float cd = a.y*b.x;\n"
            "    precise float err = fma(-a.y, b.x, cd);\n"
            "    precise float res = fma(a.x, b.y, -cd) + err;\n"
            "    return res;\n"
            "}\n"
            "float area(vec2 a, vec2 b, vec2 c) {\n"
            "    return kahan_det(b - a, c - a);\n"
            "}\n");
        if (ps->state->z_perspective) {
            /*
             * Slope-scaled polygon offset under w-buffering.  The hardware
             * evaluates it once per primitive, as the difference in w between
             * two adjacent pixel centres, stepping along the axis of the
             * larger 1/w gradient from the first pixel the rasteriser covers
             * (the top-most row of the triangle clipped to the window, at
             * the column nearest the top vertex).  Wall/Roof/Floor in
             * W_buffering reproduce to the unit; applying the factor per
             * pixel to w^2, as before, varied 30x across one quad.  Small
             * unclipped triangles pick a reference on a 4-pixel grid instead;
             * see docs/investigations/wbuffer-slope-offset.md.
             */
            mstring_append(preflight,
                "float wbufSlopeStep(vec4 p0, vec4 p1, vec4 p2, vec4 clip) {\n"
                "    vec2 d1 = p1.xy - p0.xy, d2 = p2.xy - p0.xy;\n"
                "    float det = d1.x * d2.y - d2.x * d1.y;\n"
                "    if (det == 0.0) return 0.0;\n"
                /* 1/w differences as (w0-w1)/(w0*w1): 1/w1 - 1/w0 cancels to
                 * nothing in float32 once w is in the millions (LargeZ). */
                "    vec2 b = vec2((p0.w - p1.w) / (p0.w * p1.w), (p0.w - p2.w) / (p0.w * p2.w));\n"
                "    float pa = (b.x * d2.y - b.y * d1.y) / det;\n"
                "    float pb = (d1.x * b.y - d2.x * b.x) / det;\n"
                "    float xtop = (p0.y <= p1.y && p0.y <= p2.y) ? p0.x : (p1.y <= p2.y ? p1.x : p2.x);\n"
                "    vec2 poly[8];\n"
                "    int n = 3;\n"
                "    poly[0] = p0.xy; poly[1] = p1.xy; poly[2] = p2.xy;\n"
                "    for (int side = 0; side < 4; side++) {\n"
                "        vec2 kept[8];\n"
                "        int m = 0;\n"
                "        for (int i = 0; i < n; i++) {\n"
                "            vec2 a = poly[i], b = poly[(i + 1) % n];\n"
                "            float da = side == 0 ? a.x - clip.x : side == 1 ? clip.z - a.x : side == 2 ? a.y - clip.y : clip.w - a.y;\n"
                "            float db = side == 0 ? b.x - clip.x : side == 1 ? clip.z - b.x : side == 2 ? b.y - clip.y : clip.w - b.y;\n"
                "            if (da >= 0.0) kept[m++] = a;\n"
                "            if ((da >= 0.0) != (db >= 0.0)) kept[m++] = mix(a, b, da / (da - db));\n"
                "        }\n"
                "        n = m;\n"
                "        if (n == 0) return 0.0;\n"
                "        for (int i = 0; i < n; i++) poly[i] = kept[i];\n"
                "    }\n"
                "    float ymin = poly[0].y;\n"
                "    for (int i = 1; i < n; i++) ymin = min(ymin, poly[i].y);\n"
                "    float r = ceil(ymin - 0.5);\n"
                "    float c = 0.0;\n"
                "    bool found = false;\n"
                "    for (int k = 0; k < 4 && !found; k++) {\n"
                "        float yc = r + 0.5, lo = 1e30, hi = -1e30;\n"
                "        for (int i = 0; i < n; i++) {\n"
                "            vec2 a = poly[i], b = poly[(i + 1) % n];\n"
                "            if ((a.y <= yc) != (b.y <= yc)) {\n"
                "                float x = a.x + (b.x - a.x) * (yc - a.y) / (b.y - a.y);\n"
                "                lo = min(lo, x); hi = max(hi, x);\n"
                "            } else if (a.y == yc && b.y == yc) {\n"
                "                lo = min(lo, min(a.x, b.x)); hi = max(hi, max(a.x, b.x));\n"
                "            }\n"
                "        }\n"
                "        float first = ceil(lo - 0.5), last = ceil(hi - 0.5) - 1.0;\n"
                "        if (hi > lo && last >= first) {\n"
                "            c = clamp(floor(xtop), first, last);\n"
                "            found = true;\n"
                "        } else {\n"
                "            r += 1.0;\n"
                "        }\n"
                "    }\n"
                "    if (!found) return 0.0;\n"
                /* The pair is the 2x2 pixel quad holding the anchor: a clip
                 * edge at column 159 measures the pair (158,159), a vertex at
                 * 637.31 the pair (636,637). */
                "    c = 2.0 * floor(c * 0.5);\n"
                "    r = 2.0 * floor(r * 0.5);\n"
                "    float step = abs(pa) >= abs(pb) ? pa : pb;\n"
                "    float i1 = 1.0 / p0.w + pa * (c + 0.5 - p0.x) + pb * (r + 0.5 - p0.y);\n"
                "    float i2 = i1 + step;\n"
                "    if (i1 <= 0.0 || i2 <= 0.0) return 0.0;\n"
                "    return abs(step) / (i1 * i2);\n"
                "}\n");
        }
    }

    MString *clip = mstring_new();

    if (ps->state->stipple) {
        /*
         * The pattern is a 32x32 bitmap of screen pixels, in unscaled
         * surface coordinates. Each word holds one row as four bytes,
         * leftmost byte first and most significant bit leftmost within a
         * byte, so the pixel at x takes bit (x & 31) ^ 7. The rows run
         * bottom up: the top row of the Stipple tests square, which sits
         * at a multiple of 32, shows the last word of the pattern.
         */
        mstring_append(clip,
            "/*  Polygon stipple */\n"
            "{\n"
            "  ivec2 sxy = ivec2(gl_FragCoord.xy) / surfaceScale;\n"
            "  int srow = 31 - (sxy.y & 31);\n"
            "  int sword = stipplePattern[srow >> 2][srow & 3];\n"
            "  if (((sword >> ((sxy.x & 31) ^ 7)) & 1) == 0) {\n"
            "    discard;\n"
            "  }\n"
            "}\n");
    }

    int wc_count = ps->state->window_clip_count;

    if (wc_count > 0) {
        mstring_append_fmt(clip, "/*  Window-clip (%slusive, %d regions) */\n",
                           ps->state->window_clip_exclusive ? "Exc" : "Inc",
                           wc_count);
        if (!ps->state->window_clip_exclusive) {
            mstring_append(clip, "bool clipContained = false;\n");
        }
        mstring_append(clip, "vec2 coord = gl_FragCoord.xy - 0.5;\n");

        if (wc_count == 1) {
            mstring_append(clip,
                "{\n"
                "  bool outside = any(bvec4(\n"
                "      lessThan(coord, vec2(clipRegion[0].xy)),\n"
                "      greaterThanEqual(coord, vec2(clipRegion[0].zw))));\n"
                "  if (!outside) {\n");
            if (ps->state->window_clip_exclusive) {
                mstring_append(clip, "    discard;\n");
            } else {
                mstring_append(clip, "    clipContained = true;\n");
            }
            mstring_append(clip, "  }\n"
                                 "}\n");
        } else {
            mstring_append_fmt(clip,
                "for (int i = 0; i < %d; i++) {\n"
                "  bool outside = any(bvec4(\n"
                "      lessThan(coord, vec2(clipRegion[i].xy)),\n"
                "      greaterThanEqual(coord, vec2(clipRegion[i].zw))));\n"
                "  if (!outside) {\n", wc_count);
            if (ps->state->window_clip_exclusive) {
                mstring_append(clip, "    discard;\n");
            } else {
                mstring_append(clip, "    clipContained = true;\n"
                                     "    break;\n");
            }
            mstring_append(clip, "  }\n"
                                 "}\n");
        }

        if (!ps->state->window_clip_exclusive) {
            mstring_append(clip, "if (!clipContained) {\n"
                                 "  discard;\n"
                                 "}\n");
        }
    }

    if (ps->state->depth_needed) {
        if (ps->state->z_perspective) {
            /*
             * The slope offset's reference pixel is found on the triangle
             * clipped to the window.  clipRegion is in scaled surface pixels,
             * vtxPos is not.  Region 0 is the one guests set; the other seven
             * usually hold their reset value and count as regions too, so the
             * count does not say whether region 0 is the clip.  An exclusive
             * clip has no single "first pixel"; leave the triangle unclipped.
             */
            const char *wclip =
                !ps->state->window_clip_exclusive ?
                    "vec4(clipRegion[0]) / vec4(vec2(surfaceScale), vec2(surfaceScale))" :
                    "vec4(-1e9, -1e9, 1e9, 1e9)";
            mstring_append_fmt(
                clip,
                "vec2 unscaled_xy = gl_FragCoord.xy / vec2(surfaceScale);\n"
                "precise float bc0 = area(unscaled_xy, vtxPos1.xy, vtxPos2.xy);\n"
                "precise float bc1 = area(unscaled_xy, vtxPos2.xy, vtxPos0.xy);\n"
                "precise float bc2 = area(unscaled_xy, vtxPos0.xy, vtxPos1.xy);\n"
                "bc0 /= vtxPos0.w;\n"
                "bc1 /= vtxPos1.w;\n"
                "bc2 /= vtxPos2.w;\n"
                "float inv_bcsum = 1.0 / (bc0 + bc1 + bc2);\n"
                "if (isinf(inv_bcsum)) {\n"
                "  inv_bcsum = 0.0;\n"
                "}\n"
                "bc1 *= inv_bcsum;\n"
                "bc2 *= inv_bcsum;\n"
                "precise float zhi = floor(vtxPos0.w);\n"
                "precise float zlo = (vtxPos0.w - zhi) + (bc1*(vtxPos1.w - vtxPos0.w) + bc2*(vtxPos2.w - vtxPos0.w));\n"
                "precise float zvalue = zhi + zlo;\n"
                "if (zvalue > 0.0) {\n"
                "  float zslopeofs = depthFactor != 0.0 ? depthFactor * wbufSlopeStep(vtxPos0, vtxPos1, vtxPos2, %s) : 0.0;\n"
                "  zlo += depthOffset;\n"
                "  zlo += zslopeofs;\n"
                "  zvalue = zhi + zlo;\n"
                "} else {\n"
                "  zvalue = uintBitsToFloat(0x7F7FFFFFu);\n"
                "  zhi = 0.0; zlo = zvalue;\n"
                "}\n"
                "if (isnan(zvalue)) {\n"
                "  zvalue = uintBitsToFloat(0x7F7FFFFFu);\n"
                "  zhi = 0.0; zlo = zvalue;\n"
                "}\n"
                "precise float zfloor = zhi + floor(zlo);\n", wclip);
        } else {
            mstring_append(
                clip,
                "vec2 unscaled_xy = gl_FragCoord.xy / vec2(surfaceScale);\n"
                "precise float bc0 = area(unscaled_xy, vtxPos1.xy, vtxPos2.xy);\n"
                "precise float bc1 = area(unscaled_xy, vtxPos2.xy, vtxPos0.xy);\n"
                "precise float bc2 = area(unscaled_xy, vtxPos0.xy, vtxPos1.xy);\n"
                "float inv_bcsum = 1.0 / (bc0 + bc1 + bc2);\n"
                "if (isinf(inv_bcsum)) {\n"
                "  inv_bcsum = 0.0;\n"
                "}\n"
                "bc1 *= inv_bcsum;\n"
                "bc2 *= inv_bcsum;\n"
                /*
                 * Hardware keeps the depth fraction in fixed point; a float32
                 * cannot, because a guest depth word runs to 2^24 where the
                 * ULP is a whole unit. Keeping the base vertex's integer part
                 * aside (#32) fixed the half of that which came from adding
                 * the base in, but not the half that comes from the
                 * interpolated delta: on the Depth buffer big quad the delta
                 * itself reaches 5.6M, where the ULP is already 0.5, so the
                 * products bc*(dz) have no room for a fraction either. floor()
                 * then lands one *above* hardware -- never below, because the
                 * base fraction being added in is positive -- and no amount of
                 * splitting afterwards recovers it, the bits are gone at the
                 * multiply.
                 *
                 * So the delta is carried as an unevaluated sum: each product
                 * keeps the bits it dropped (fma against the rounded product,
                 * the kahan_det trick above), the two are added with a
                 * two-sum, and the floor is taken on the pair rather than on
                 * the rounded head. Only the head's integer part is large;
                 * once it is set aside with zhi, what remains is order 1 and
                 * a float32 holds its fraction exactly.
                 *
                 * Modelled over the four quad geometries this suite draws,
                 * against the same interpolation in double, that is exact on
                 * 100% of samples where the old form managed 56-99%. Measured
                 * on all 784 Depth buffer goldens it is worth rather less:
                 * D24's differing pixels go 309,710 to 233,112, a quarter of
                 * them. So this removes the float32 error and something else
                 * accounts for the remaining three quarters -- most likely
                 * where the depth is sampled rather than how it is summed,
                 * since what is left is still capped at exactly one unit.
                 * Issue #16, #32.
                 */
                "precise float zhi = floor(vtxPos0.z);\n"
                "precise float zd1 = vtxPos1.z - vtxPos0.z;\n"
                "precise float zd2 = vtxPos2.z - vtxPos0.z;\n"
                "precise float zp1 = bc1*zd1;\n"
                "precise float zp2 = bc2*zd2;\n"
                "precise float zt1 = fma(bc1, zd1, -zp1);\n"
                "precise float zt2 = fma(bc2, zd2, -zp2);\n"
                "precise float zdh = zp1 + zp2;\n"
                "precise float zbv = zdh - zp1;\n"
                "precise float zav = zdh - zbv;\n"
                "precise float zdt = ((zp1 - zav) + (zp2 - zbv)) + (zt1 + zt2);\n"
                "precise float zdn = floor(zdh);\n"
                "precise float zbase = zhi + zdn;\n"
                "precise float zrem = ((vtxPos0.z - zhi) + (zdh - zdn)) + zdt;\n"
                "zrem += depthOffset;\n"
                "zrem += depthFactor*triMZ;\n"
                /*
                 * zvalue keeps its original association. Only the fixed point
                 * formats read zfloor; F16 and F24 take the *bit pattern* of
                 * zvalue, and rebuilding it through the split above moves its
                 * low bits. Measured: splitting zvalue too costs F24 3,686,518
                 * channels and takes its worst error from 12,585 depth units
                 * to 6,727,533, against the 79,522 channels the split wins on
                 * D24. The split belongs to the floor, not to the value.
                 */
                "precise float zlo = (vtxPos0.z - zhi) + (bc1*(vtxPos1.z - vtxPos0.z) + bc2*(vtxPos2.z - vtxPos0.z));\n"
                "zlo += depthOffset;\n"
                "zlo += depthFactor*triMZ;\n"
                "precise float zvalue = zhi + zlo;\n"
                "precise float zfloor = zbase + floor(zrem);\n");
        }

        if (ps->state->depth_clipping) {
            mstring_append(
                clip, "if (zvalue < clipRange.z || clipRange.w < zvalue) {\n"
                      "  discard;\n"
                      "}\n");
        } else {
            mstring_append(
                clip, "zvalue = clamp(zvalue, clipRange.z, clipRange.w);\n"
                      "zfloor = clamp(zfloor, clipRange.z, clipRange.w);\n");
        }
    }

    MString *vars = mstring_new();
    /* With two-sided lighting on, a back-facing fragment takes the back
     * colour outputs; with it off the front outputs serve both faces and
     * the back ones are never looked at (Lighting Two Sided golden). */
    if (ps->state->two_side_light) {
        mstring_append(vars, "vec4 pD0 = gl_FrontFacing ? vtxD0 : vtxB0;\n");
        mstring_append(vars, "vec4 pD1 = gl_FrontFacing ? vtxD1 : vtxB1;\n");
    } else {
        mstring_append(vars, "vec4 pD0 = vtxD0;\n");
        mstring_append(vars, "vec4 pD1 = vtxD1;\n");
    }
    mstring_append(vars, "vec4 pB0 = vtxB0;\n");
    mstring_append(vars, "vec4 pB1 = vtxB1;\n");
    append_fog_factor(ps, vars, "");
    mstring_append(vars, "vec4 pT0 = vtxT0;\n");
    mstring_append(vars, "vec4 pT1 = vtxT1;\n");
    mstring_append(vars, "vec4 pT2 = vtxT2;\n");
    if (ps->state->point_sprite) {
        if (ps->state->rect_tex[3]) {
            /* gl_PointCoord is 0..1 and the stage's remap scales it to the
             * linear texture's size on sampling, which is plausibly what the
             * hardware does too; it only asserted because nobody had checked. */
            NV2A_UNIMPLEMENTED("point sprite over a linear texture on stage 3");
        }
        mstring_append(vars, "vec4 pT3 = vec4(gl_PointCoord, 1.0, 1.0);\n");
    } else {
        mstring_append(vars, "vec4 pT3 = vtxT3;\n");
    }
    mstring_append(vars, "\n");
    mstring_append(vars, "vec4 v0 = pD0;\n");
    mstring_append(vars, "vec4 v1 = pD1;\n");
    mstring_append(vars, "vec4 ab;\n");
    mstring_append(vars, "vec4 cd;\n");
    mstring_append(vars, "vec4 mux_sum;\n");

    ps->code = mstring_new();

    bool color_key_comparator_defined = false;

    for (int i = 0; i < 4; i++) {

        const char *sampler_type = get_sampler_type(ps, ps->tex_modes[i], i);
        if (ps->tex_unusable[i]) {
            /* get_sampler_type() found a dimensionality or format it has no
             * sampler for; every path below would sample it. */
            emit_stage_as_none(vars, i, ps->tex_modes[i],
                               "no sampler for this texture");
            continue;
        }

        g_autofree gchar *normalize_tex_coords = g_strdup_printf("norm%d", i);
        const char *tex_remap = ps->state->rect_tex[i] ? normalize_tex_coords : "";

        const char *dotmap_func = dotmap_funcs[dotmap_index(ps, i)];
        if (dotmap_index(ps, i) > 3) {
            NV2A_UNIMPLEMENTED("Dot Mapping mode %s", dotmap_func);
        }

        switch (ps->tex_modes[i]) {
        case PS_TEXTUREMODES_NONE:
            mstring_append_fmt(vars, "vec4 t%d = vec4(0.0, 0.0, 0.0, 1.0); /* PS_TEXTUREMODES_NONE */\n",
                               i);
            break;
        case PS_TEXTUREMODES_PROJECT2D: {
            if (ps->state->shadow_map[i]) {
                psh_append_shadowmap(ps, i, false, vars);
            } else {
                apply_border_adjustment(ps, vars, i, "pT%d");
                bool convolve = ps->state->conv_tex[i] == CONVOLUTION_FILTER_GAUSSIAN ||
                                ps->state->conv_tex[i] == CONVOLUTION_FILTER_QUINCUNX;
                if (convolve && (ps->state->dim_tex[i] != 2 ||
                                 ps->state->tex_cubemap[i])) {
                    /* textureProj has no cube form; the filter tap loop
                     * would not compile against a samplerCube. */
                    NV2A_UNIMPLEMENTED("convolution filter on a %dD%s texture, "
                                       "stage %d; sampled unfiltered",
                                       ps->state->dim_tex[i],
                                       ps->state->tex_cubemap[i] ? " cube" : "", i);
                    convolve = false;
                }
                if (convolve) {
                    apply_convolution_filter(ps, vars, i);
                } else {
                    if (ps->state->dim_tex[i] == 2) {
                        if (ps->state->tex_cubemap[i]) {
                            mstring_append_fmt(
                                vars,
                                "vec4 t%d = texture(texSamp%d, remap2DToCube(%s(pT%d.xyw)));\n",
                                i, i, tex_remap, i);
                        } else {
                            /* texelTieBias: see the note by its definition.
                             * Scaled by w so that textureProj's own divide
                             * leaves exactly the bias behind. */
                            mstring_append_fmt(
                                vars,
                                "vec4 t%d = textureProj(texSamp%d,\n"
                                "    vec3(%s(pT%d.xy) + texelTieBias * pT%d.w, pT%d.w));\n",
                                i, i, tex_remap, i, i, i);
                        }
                    } else if (ps->state->dim_tex[i] == 3) {
                        mstring_append_fmt(vars, "vec4 t%d = textureProj(texSamp%d, vec4(pT%d.xy, 0.0, pT%d.w));\n",
                                           i, i, i, i);
                    } else {
                        mstring_append_fmt(vars, "vec4 t%d = vec4(0.0); /* %dD texture */\n",
                                           i, ps->state->dim_tex[i]);
                    }
                }
                /*
                 * A BORDER axis replaces the texel with the border colour
                 * register, verbatim, whatever the texture's format.  The
                 * sampler's custom border colour goes through the image
                 * view's component mapping and the format's channel set,
                 * which turned 0x33FF22CC into opaque white on A8 and green
                 * on BGRA (Texture_border_color).  Decide it here instead.
                 */
                if ((ps->state->addr_border[i] & 3) &&
                    ps->state->dim_tex[i] == 2 && !ps->state->tex_cubemap[i] &&
                    !ps->state->shadow_map[i]) {
                    mstring_append_fmt(vars,
                        "{\n"
                        "  vec2 bc = %s(pT%d.xy) / pT%d.w;\n"
                        "  if ((%s && (bc.x < 0.0 || bc.x > 1.0)) ||\n"
                        "      (%s && (bc.y < 0.0 || bc.y > 1.0))) {\n"
                        "    t%d = borderColor[%d];\n"
                        "  }\n"
                        "}\n",
                        tex_remap, i, i,
                        (ps->state->addr_border[i] & 1) ? "true" : "false",
                        (ps->state->addr_border[i] & 2) ? "true" : "false",
                        i, i);
                }
            }
            break;
        }
        case PS_TEXTUREMODES_PROJECT3D:
            if (ps->state->shadow_map[i]) {
                psh_append_shadowmap(ps, i, true, vars);
            } else {
                apply_border_adjustment(ps, vars, i, "pT%d");
                mstring_append_fmt(vars, "vec4 t%d = textureProj(texSamp%d, %s(pT%d.xyzw));\n",
                                   i, i, tex_remap, i);
            }
            break;
        case PS_TEXTUREMODES_CUBEMAP:
            apply_border_adjustment(ps, vars, i, "pT%d");
            if (!ps->state->tex_cubemap[i]) {
                mstring_append_fmt(vars,
                    "pT%d.xy = remapCubeTo2D(pT%d.xyz);\n",
                    i, i);
            }
            mstring_append_fmt(vars,
                "vec4 t%d = texture(texSamp%d, pT%d.xy%s);\n",
                i, i, i, ps->state->tex_cubemap[i] ? "z" : "");
            break;
        case PS_TEXTUREMODES_PASSTHRU:
            if (ps->state->border_logical_size[i][0] != 0.0f) {
                /* Passthru samples nothing, so the border has nothing to
                 * adjust; it only mattered because this used to assert. */
                NV2A_UNIMPLEMENTED("border texture on passthru stage %d", i);
            }
            mstring_append_fmt(vars, "vec4 t%d = pT%d;\n", i, i);
            break;
        case PS_TEXTUREMODES_CLIPPLANE: {
            int j;
            mstring_append_fmt(vars, "vec4 t%d = vec4(0.0); /* PS_TEXTUREMODES_CLIPPLANE */\n",
                               i);
            for (j = 0; j < 4; j++) {
                mstring_append_fmt(vars, "  if(pT%d.%c %s 0.0) { discard; };\n",
                                   i, "xyzw"[j],
                                   ps->state->compare_mode[i][j] ? ">=" : "<");
            }
            break;
        }
        case PS_TEXTUREMODES_BUMPENVMAP:
            if (!stage_consistent(ps, vars, i, 1, 3, 0, "PS_TEXTUREMODES_BUMPENVMAP")) break;

            {
                int k = ps->input_tex[i];
                bool gather_ok = append_bump_coords(ps, vars, i, k);
                char sname[16], tname[16];
                snprintf(sname, sizeof(sname), "bumpS%d", i);
                snprintf(tname, sizeof(tname), "bumpT%d", i);
                append_bump_channel(ps, vars, i, k, 2, NV_PGRAPH_TEXFILTER0_BSIGNED, false, sname, gather_ok);
                append_bump_channel(ps, vars, i, k, 1, NV_PGRAPH_TEXFILTER0_GSIGNED, false, tname, gather_ok);
                mstring_append_fmt(vars, "vec2 dsdt%d = vec2(%s, %s);\n", i, sname, tname);
            }

            mstring_append_fmt(vars, "dsdt%d = bumpMat[%d] * dsdt%d;\n", i, i, i);

            /* Border adjustment applies to the perturbed coordinate just as
             * it does to every other sampling mode. BUMPENVMAP and
             * BUMPENVMAP_LUM were the only two of eleven that skipped it. */
            mstring_append_fmt(vars, "vec3 bumpST%d = vec3(pT%d.xy + dsdt%d, pT%d.z);\n",
                               i, i, i, i);
            apply_border_adjustment(ps, vars, i, "bumpST%d");
            if (ps->state->dim_tex[i] == 2) {
                mstring_append_fmt(vars, "vec4 t%d = texture(texSamp%d, %s(bumpST%d.xy));\n",
                    i, i, tex_remap, i);
            } else if (ps->state->dim_tex[i] == 3) {
                // FIXME: Does hardware pass through the r/z coordinate or is it 0?
                mstring_append_fmt(vars, "vec4 t%d = texture(texSamp%d, bumpST%d.xyz);\n",
                    i, i, i);
            } else {
                mstring_append_fmt(vars, "vec4 t%d = vec4(0.0); /* %dD texture */\n",
                                   i, ps->state->dim_tex[i]);
            }
            break;
        case PS_TEXTUREMODES_BUMPENVMAP_LUM:
            if (!stage_consistent(ps, vars, i, 1, 3, 0, "PS_TEXTUREMODES_BUMPENVMAP_LUM")) break;

            {
                int k = ps->input_tex[i];
                bool gather_ok = append_bump_coords(ps, vars, i, k);
                char sname[16], tname[16], lname[16];
                snprintf(sname, sizeof(sname), "bumpS%d", i);
                snprintf(tname, sizeof(tname), "bumpT%d", i);
                snprintf(lname, sizeof(lname), "bumpL%d", i);
                append_bump_channel(ps, vars, i, k, 2, NV_PGRAPH_TEXFILTER0_BSIGNED, false, sname, gather_ok);
                append_bump_channel(ps, vars, i, k, 1, NV_PGRAPH_TEXFILTER0_GSIGNED, false, tname, gather_ok);
                append_bump_channel(ps, vars, i, k, 0, NV_PGRAPH_TEXFILTER0_RSIGNED, true, lname, gather_ok);
                mstring_append_fmt(vars, "vec3 dsdtl%d = vec3(%s, %s, %s);\n", i, sname, tname, lname);
            }

            mstring_append_fmt(vars, "dsdtl%d.st = bumpMat[%d] * dsdtl%d.st;\n",
                               i, i, i);

            mstring_append_fmt(vars, "vec3 bumpSTL%d = vec3(pT%d.xy + dsdtl%d.st, pT%d.z);\n",
                               i, i, i, i);
            apply_border_adjustment(ps, vars, i, "bumpSTL%d");
            if (ps->state->dim_tex[i] == 2) {
                mstring_append_fmt(vars, "vec4 t%d = texture(texSamp%d, %s(bumpSTL%d.xy));\n",
                    i, i, tex_remap, i);
            } else if (ps->state->dim_tex[i] == 3) {
                // FIXME: Does hardware pass through the r/z coordinate or is it 0?
                mstring_append_fmt(vars, "vec4 t%d = texture(texSamp%d, bumpSTL%d.xyz);\n",
                    i, i, i);
            } else {
                mstring_append_fmt(vars, "vec4 t%d = vec4(0.0); /* %dD texture */\n",
                                   i, ps->state->dim_tex[i]);
            }

            /* The luminance scales the colour and leaves the alpha alone: the
             * Bump env lum goldens blend their half-alpha checkerboard over
             * the clear colour with exactly the texture's alpha, whatever the
             * luminance does to the colour. */
            mstring_append_fmt(vars, "t%d.rgb *= bumpScale[%d] * dsdtl%d.p + bumpOffset[%d];\n",
                i, i, i, i);
            break;
        case PS_TEXTUREMODES_BRDF:
            if (!stage_consistent(ps, vars, i, 2, 3, 2, "PS_TEXTUREMODES_BRDF")) break;
            mstring_append_fmt(vars, "vec4 t%d = vec4(0.0); /* PS_TEXTUREMODES_BRDF */\n",
                               i);
            NV2A_UNIMPLEMENTED("PS_TEXTUREMODES_BRDF");
            break;
        case PS_TEXTUREMODES_DOT_ST:
            if (!stage_consistent(ps, vars, i, 2, 3, 1, "PS_TEXTUREMODES_DOT_ST")) break;
            mstring_append_fmt(vars, "/* PS_TEXTUREMODES_DOT_ST */\n");
            mstring_append_fmt(vars,
               "float dot%d = dot(pT%d.xyz, %s(t%d));\n"
               "vec2 dotST%d = vec2(dot%d, dot%d);\n",
                i, i, dotmap_func, ps->input_tex[i], i, i-1, i);

            apply_border_adjustment(ps, vars, i, "dotST%d");
            mstring_append_fmt(vars, "vec4 t%d = texture(texSamp%d, %s(dotST%d));\n",
                i, i, tex_remap, i);
            break;
        case PS_TEXTUREMODES_DOT_ZW:
            if (!stage_consistent(ps, vars, i, 2, 3, 1, "PS_TEXTUREMODES_DOT_ZW")) break;
            mstring_append_fmt(vars, "/* PS_TEXTUREMODES_DOT_ZW */\n");
            mstring_append_fmt(vars, "float dot%d = dot(pT%d.xyz, %s(t%d));\n",
                i, i, dotmap_func, ps->input_tex[i]);
            mstring_append_fmt(vars, "vec4 t%d = vec4(0.0);\n", i);
            // FIXME: mstring_append_fmt(vars, "gl_FragDepth = t%d.x;\n", i);
            break;
        case PS_TEXTUREMODES_DOT_RFLCT_DIFF:
            if (!stage_consistent(ps, vars, i, 2, 2, 1, "PS_TEXTUREMODES_DOT_RFLCT_DIFF")) break;
            mstring_append_fmt(vars, "/* PS_TEXTUREMODES_DOT_RFLCT_DIFF */\n");
            mstring_append_fmt(vars, "float dot%d = dot(pT%d.xyz, %s(t%d));\n",
                i, i, dotmap_func, ps->input_tex[i]);
            mstring_append_fmt(vars, "float dot%d_n = dot(pT%d.xyz, %s(t%d));\n",
                i, i+1, dotmap_funcs[dotmap_index(ps, i+1)], ps->input_tex[i+1]);
            mstring_append_fmt(vars, "vec3 n_%d = vec3(dot%d, dot%d, dot%d_n);\n",
                i, i-1, i, i);
            apply_border_adjustment(ps, vars, i, "n_%d");
            if (!ps->state->tex_cubemap[i]) {
                mstring_append_fmt(vars,
                    "n_%d.xy = remapCubeTo2D(n_%d);\n", i, i);
            }
            mstring_append_fmt(vars,
                "vec4 t%d = texture(texSamp%d, n_%d%s);\n",
                i, i, i, ps->state->tex_cubemap[i] ? "" : ".xy");
            break;
        case PS_TEXTUREMODES_DOT_RFLCT_SPEC:
            if (!stage_consistent(ps, vars, i, 3, 3, 2, "PS_TEXTUREMODES_DOT_RFLCT_SPEC")) break;
            mstring_append_fmt(vars, "/* PS_TEXTUREMODES_DOT_RFLCT_SPEC */\n");
            mstring_append_fmt(vars, "float dot%d = dot(pT%d.xyz, %s(t%d));\n",
                i, i, dotmap_func, ps->input_tex[i]);
            mstring_append_fmt(vars, "vec3 n_%d = vec3(dot%d, dot%d, dot%d);\n",
                i, i-2, i-1, i);
            mstring_append_fmt(vars, "vec3 e_%d = vec3(pT%d.w, pT%d.w, pT%d.w);\n",
                i, i-2, i-1, i);
            mstring_append_fmt(vars, "vec3 rv_%d = 2.0*n_%d*dot(n_%d,e_%d)/dot(n_%d,n_%d) - e_%d;\n",
                               i, i, i, i, i, i, i);
            apply_border_adjustment(ps, vars, i, "rv_%d");
            if (!ps->state->tex_cubemap[i]) {
                mstring_append_fmt(vars,
                    "rv_%d.xy = remapCubeTo2D(rv_%d);\n", i, i);
            }
            mstring_append_fmt(vars,
                "vec4 t%d = texture(texSamp%d, rv_%d%s);\n",
                i, i, i, ps->state->tex_cubemap[i] ? "" : ".xy");
            break;
        case PS_TEXTUREMODES_DOT_STR_3D:
            if (!stage_consistent(ps, vars, i, 3, 3, 2, "PS_TEXTUREMODES_DOT_STR_3D")) break;
            mstring_append_fmt(vars, "/* PS_TEXTUREMODES_DOT_STR_3D */\n");
            mstring_append_fmt(vars,
               "float dot%d = dot(pT%d.xyz, %s(t%d));\n"
               "vec3 dotSTR%d = vec3(dot%d, dot%d, dot%d);\n",
                i, i, dotmap_func, ps->input_tex[i],
                i, i-2, i-1, i);

            apply_border_adjustment(ps, vars, i, "dotSTR%d");
            if (dot_str_3d_is_cube(ps, i)) {
                /* The whole direction goes in, as DOT_STR_CUBE does with its
                 * own triple; a cubemap is never rect_tex, so no remap. */
                mstring_append_fmt(vars,
                    "vec4 t%d = texture(texSamp%d, dotSTR%d);\n", i, i, i);
            } else {
                mstring_append_fmt(vars,
                    "vec4 t%d = texture(texSamp%d, %s(dotSTR%d%s));\n",
                    i, i, tex_remap, i,
                    ps->state->dim_tex[i] == 2 ? ".xy" : "");
            }
            break;
        case PS_TEXTUREMODES_DOT_STR_CUBE:
            if (!stage_consistent(ps, vars, i, 3, 3, 2, "PS_TEXTUREMODES_DOT_STR_CUBE")) break;
            mstring_append_fmt(vars, "/* PS_TEXTUREMODES_DOT_STR_CUBE */\n");
            mstring_append_fmt(vars, "float dot%d = dot(pT%d.xyz, %s(t%d));\n",
                i, i, dotmap_func, ps->input_tex[i]);
            mstring_append_fmt(vars, "vec3 dotSTR%dCube = vec3(dot%d, dot%d, dot%d);\n",
                               i, i-2, i-1, i);
            apply_border_adjustment(ps, vars, i, "dotSTR%dCube");
            if (!ps->state->tex_cubemap[i]) {
                mstring_append_fmt(vars,
                    "dotSTR%dCube.xy = remapCubeTo2D(dotSTR%dCube);\n",
                    i, i);
            }
            mstring_append_fmt(vars,
                "vec4 t%d = texture(texSamp%d, dotSTR%dCube%s);\n",
                i, i, i, ps->state->tex_cubemap[i] ? "" : ".xy");
            break;
        case PS_TEXTUREMODES_DPNDNT_AR:
            if (!stage_consistent(ps, vars, i, 1, 3, 0, "PS_TEXTUREMODES_DPNDNT_AR")) break;
            if (ps->state->rect_tex[i]) {
                /* The dependent coordinate is a colour in 0..1; what the
                 * hardware does with it against a linear (unnormalised)
                 * texture is not established. Keep drawing. */
                NV2A_UNIMPLEMENTED("dependent AR read from a linear texture, "
                                   "stage %d", i);
            }
            mstring_append_fmt(vars, "vec2 t%dAR = t%d.ar;\n", i, ps->input_tex[i]);
            apply_border_adjustment(ps, vars, i, "t%dAR");
            mstring_append_fmt(vars, "vec4 t%d = texture(texSamp%d, %s(t%dAR));\n",
                i, i, tex_remap, i);
            break;
        case PS_TEXTUREMODES_DPNDNT_GB:
            if (!stage_consistent(ps, vars, i, 1, 3, 0, "PS_TEXTUREMODES_DPNDNT_GB")) break;
            if (ps->state->rect_tex[i]) {
                /* The dependent coordinate is a colour in 0..1; what the
                 * hardware does with it against a linear (unnormalised)
                 * texture is not established. Keep drawing. */
                NV2A_UNIMPLEMENTED("dependent GB read from a linear texture, "
                                   "stage %d", i);
            }
            mstring_append_fmt(vars, "vec2 t%dGB = t%d.gb;\n", i, ps->input_tex[i]);
            apply_border_adjustment(ps, vars, i, "t%dGB");
            mstring_append_fmt(vars, "vec4 t%d = texture(texSamp%d, %s(t%dGB));\n",
                i, i, tex_remap, i);
            break;
        case PS_TEXTUREMODES_DOTPRODUCT:
            if (!stage_consistent(ps, vars, i, 1, 2, 0, "PS_TEXTUREMODES_DOTPRODUCT")) break;
            mstring_append_fmt(vars, "/* PS_TEXTUREMODES_DOTPRODUCT */\n");
            mstring_append_fmt(vars, "float dot%d = dot(pT%d.xyz, %s(t%d));\n",
                i, i, dotmap_func, ps->input_tex[i]);
            mstring_append_fmt(vars, "vec4 t%d = vec4(0.0);\n", i);
            break;
        case PS_TEXTUREMODES_DOT_RFLCT_SPEC_CONST:
            /* DOT_RFLCT_SPEC with the eye vector taken from
             * NV097_SET_EYE_VECTOR instead of the w of the three stages'
             * coordinates. Every Texture cubemap::DotReflectConst_* capture
             * was blank while this was a zero texel. */
            if (!stage_consistent(ps, vars, i, 3, 3, 2, "PS_TEXTUREMODES_DOT_RFLCT_SPEC_CONST")) break;
            mstring_append_fmt(vars, "/* PS_TEXTUREMODES_DOT_RFLCT_SPEC_CONST */\n");
            mstring_append_fmt(vars, "float dot%d = dot(pT%d.xyz, %s(t%d));\n",
                i, i, dotmap_func, ps->input_tex[i]);
            mstring_append_fmt(vars, "vec3 n_%d = vec3(dot%d, dot%d, dot%d);\n",
                i, i-2, i-1, i);
            mstring_append_fmt(vars, "vec3 e_%d = eyeVec.xyz;\n", i);
            mstring_append_fmt(vars, "vec3 rv_%d = 2.0*n_%d*dot(n_%d,e_%d)/dot(n_%d,n_%d) - e_%d;\n",
                               i, i, i, i, i, i, i);
            apply_border_adjustment(ps, vars, i, "rv_%d");
            if (!ps->state->tex_cubemap[i]) {
                mstring_append_fmt(vars,
                    "rv_%d.xy = remapCubeTo2D(rv_%d);\n", i, i);
            }
            mstring_append_fmt(vars,
                "vec4 t%d = texture(texSamp%d, rv_%d%s);\n",
                i, i, i, ps->state->tex_cubemap[i] ? "" : ".xy");
            break;
        default:
            /* Five bits per stage in NV097_SET_SHADER_STAGE_PROGRAM; the
             * hardware defines 0x00..0x12. */
            NV2A_UNIMPLEMENTED("texture mode 0x%x on stage %d; zero texel",
                               ps->tex_modes[i], i);
            mstring_append_fmt(vars, "vec4 t%d = vec4(0.0); /* unknown mode 0x%x */\n",
                               i, ps->tex_modes[i]);
            break;
        }

        if (sampler_type != NULL) {
            if (ps->opts.vulkan) {
                mstring_append_fmt(preflight, "layout(binding = %d) ",
                                   ps->opts.tex_binding + i);
            }
            mstring_append_fmt(preflight, "uniform %s texSamp%d;\n",
                               sampler_type, i);

            /* Channels flagged signed on a texture the sampler holds
             * unsigned: two's complement over 127, the SNORM reading.  A
             * texel a later bump or dot-product stage consumes is left as
             * bytes; those stages sign their inputs themselves. */
            if (ps->state->tex_signed[i] && !stage_consumed_raw(ps, i)) {
                if (ps->state->snorm_tex[i]) {
                    /* The sampler signed it over 127; the hardware's scale
                     * is 127.5 (a 0x7f texel reaches the combiner as
                     * 254/255: Texture_signed_component_tests, every
                     * flagged block one step under full). */
                    mstring_append_fmt(vars, "t%d *= 127.0 / 127.5;\n", i);
                } else {
                    static const struct { uint32_t bit; char c; } chan[] = {
                        { NV_PGRAPH_TEXFILTER0_RSIGNED, 'r' },
                        { NV_PGRAPH_TEXFILTER0_GSIGNED, 'g' },
                        { NV_PGRAPH_TEXFILTER0_BSIGNED, 'b' },
                        { NV_PGRAPH_TEXFILTER0_ASIGNED, 'a' },
                    };
                    for (int c = 0; c < 4; c++) {
                        if (ps->state->tex_signed[i] & chan[c].bit) {
                            mstring_append_fmt(vars, "t%d.%c = signed_channel(t%d.%c);\n",
                                               i, chan[c].c, i, chan[c].c);
                        }
                    }
                }
            }

            /* As this means a texture fetch does happen, do alphakill */
            if (ps->state->alphakill[i]) {
                mstring_append_fmt(vars, "if (t%d.a == 0.0) { discard; };\n",
                                   i);
            }

            enum PS_COLORKEYMODE color_key_mode = ps->state->colorkey_mode[i];
            if (color_key_mode != COLOR_KEY_NONE) {
                if (!color_key_comparator_defined) {
                    define_colorkey_comparator(preflight);
                    color_key_comparator_defined = true;
                }

                // clang-format off
                mstring_append_fmt(
                    vars,
                    "if (check_color_key(t%d, colorKey[%d], colorKeyMask[%d])) {\n",
                    i, i, i);
                // clang-format on

                switch (color_key_mode) {
                case COLOR_KEY_DISCARD:
                    mstring_append(vars, "  discard;\n");
                    break;

                case COLOR_KEY_KILL_ALPHA:
                    mstring_append_fmt(vars, "  t%d.a = 0.0;\n", i);
                    break;

                case COLOR_KEY_KILL_COLOR_AND_ALPHA:
                    mstring_append_fmt(vars, "  t%d = vec4(0.0);\n", i);
                    break;

                default:
                    assert(!"Unhandled key mode.");
                }

                mstring_append(vars, "}\n");
            }

            if (ps->state->rect_tex[i]) {
                mstring_append_fmt(preflight,
                "vec2 norm%d(vec2 coord) {\n"
                "    return coord / (vec2(textureSize(texSamp%d, 0)) / texScale[%d]);\n"
                "}\n",
                i, i, i);
                mstring_append_fmt(preflight,
                "vec3 norm%d(vec3 coord) {\n"
                "    return vec3(norm%d(coord.xy), coord.z);\n"
                "}\n",
                i, i);
                mstring_append_fmt(preflight,
                "vec4 norm%d(vec4 coord) {\n"
                "    return vec4(norm%d(coord.xy), 0, coord.w);\n"
                "}\n",
                i, i);
            }
        }
    }

    for (int i = 0; i < ps->num_stages; i++) {
        ps->cur_stage = i;
        mstring_append_fmt(ps->code, "// Stage %d\n", i);
        MString* color = add_stage_code(ps, ps->stage[i].rgb_input, ps->stage[i].rgb_output, "rgb", false);
        MString* alpha = add_stage_code(ps, ps->stage[i].alpha_input, ps->stage[i].alpha_output, "a", true);

        mstring_append(ps->code, mstring_get_str(color));
        mstring_append(ps->code, mstring_get_str(alpha));
        mstring_unref(color);
        mstring_unref(alpha);
    }

    if (ps->final_input.enabled) {
        ps->cur_stage = 8;
        mstring_append(ps->code, "// Final Combiner\n");
        add_final_stage_code(ps, ps->final_input);
    }

    if (ps->state->alpha_test && ps->state->alpha_func != ALPHA_FUNC_ALWAYS) {
        if (ps->state->alpha_func == ALPHA_FUNC_NEVER) {
            mstring_append(ps->code, "discard;\n");
        } else {
            const char* alpha_op;
            switch (ps->state->alpha_func) {
            case ALPHA_FUNC_LESS: alpha_op = "<"; break;
            case ALPHA_FUNC_EQUAL: alpha_op = "=="; break;
            case ALPHA_FUNC_LEQUAL: alpha_op = "<="; break;
            case ALPHA_FUNC_GREATER: alpha_op = ">"; break;
            case ALPHA_FUNC_NOTEQUAL: alpha_op = "!="; break;
            case ALPHA_FUNC_GEQUAL: alpha_op = ">="; break;
            default:
                assert(false);
                break;
            }
            mstring_append_fmt(ps->code,
                               "int fragAlpha = int(round(fragColor.a * 255.0));\n"
                               "if (!(fragAlpha %s alphaRef)) discard;\n",
                               alpha_op);
        }
    }

    for (int i = 0; i < ps->num_var_refs; i++) {
        mstring_append_fmt(vars, "vec4 %s = vec4(0);\n", ps->var_refs[i]);
        if (strcmp(ps->var_refs[i], "r0") == 0) {
            if (ps->tex_modes[0] != PS_TEXTUREMODES_NONE) {
                mstring_append(vars, "r0.a = t0.a;\n");
            } else {
                mstring_append(vars, "r0.a = 1.0;\n");
            }
        }
    }

    if (ps->state->depth_needed) {
        /*
         * zvalue is in the guest's depth units -- vtxPos.w for W buffering,
         * vtxPos.z otherwise -- and what lands in the host depth buffer has to
         * be something the readback can turn back into the guest's 24 or 16 bit
         * depth word.
         *
         * For the float formats that means storing the *encoding*, not the
         * decoded value. Normalising the value itself by clipRange.y, which is
         * f24_max = 1e30 for F24, is what the default case below used to do,
         * and it destroys the buffer: a realistic zvalue of 325 lands at 3e-28
         * and every drawn pixel reads back as zero. Measured against hardware
         * on W buffering, where silicon has 0x874500 (f24 for 325.0) and this
         * had 0x000000.
         *
         * The encoding is safe to store because IEEE-754 bit patterns of
         * non-negative floats are monotonic in the value, so depth comparisons
         * still order correctly, and it costs no precision -- 24 bits of guest
         * depth in 24 bits of host depth. It also makes the readback in
         * surface-compute.c correct as it already stands, and makes the clear
         * path identical for fixed and float, which is the tell that this is
         * the representation the rest of the pipeline already assumed.
         *
         * Both 24 bit cases then have to agree with how the host image stores
         * what they write. A 24 bit unorm image scales by 0xFFFFFF, so dividing
         * by 2^24 lands half a unit low and the extra ULP is what pulls it back
         * onto the right integer. A float image stores exactly what it is
         * given, so the same ULP would push it a whole unit high -- and
         * dividing by 2^24 there is not an approximation at all, every guest
         * depth word being exactly representable. Getting this backwards costs
         * one unit of depth over the whole surface; it showed up as a cleared
         * Z24S8 buffer reading back 0x800008 where silicon has 0x800007,
         * because the product lands right on the truncation boundary near
         * z = 2^23 and the smallest disagreement in the GPU's rounding flips
         * it.
         */
        const char *z24_open =
            ps->opts.float_depth_storage ? "" : "uintBitsToFloat(floatBitsToUint(";
        const char *z24_close = ps->opts.float_depth_storage ? "" : ") + 1u)";

        switch (ps->state->depth_format) {
        case DEPTH_FORMAT_D16:
            mstring_append(
                ps->code,
                "gl_FragDepth = zfloor / 65535.0;\n");
            break;
        case DEPTH_FORMAT_D24:
            mstring_append_fmt(
                ps->code, "gl_FragDepth = %szfloor / 16777216.0%s;\n",
                z24_open, z24_close);
            break;
        case DEPTH_FORMAT_F24:
            /* convert_f24_to_float in pgraph/util.h, inverted: f24 is the top
             * 24 bits of the float32, rebuilt with (f24 << 7). Normalised like
             * D24 above, so the pack shader recovers it unchanged. */
            mstring_append_fmt(
                ps->code,
                "uint zf24 = min(floatBitsToUint(max(zvalue, 0.0)) >> 7,\n"
                "                0xFFFFFFu);\n"
                "gl_FragDepth = %sfloat(zf24) / 16777216.0%s;\n",
                z24_open, z24_close);
            break;
        case DEPTH_FORMAT_F16:
            /* convert_f16_to_float, inverted: f16 is (f16 << 11) + 0x3C000000.
             * F16 lives on a Z16 surface, which is D16_UNORM on every host, so
             * it needs none of the Z24S8 scale dance -- 65535.0 is the
             * format's own scale.
             *
             * The flush-to-zero threshold is 2^-6, not the 2^-7 the bias
             * suggests. Read the encoding as a float: the top four bits of the
             * 16 are an exponent field added to 0x3C000000's exponent, and the
             * low twelve are the mantissa. Exponent field zero -- every
             * encoding below 0x1000 -- means *zero*, which is what
             * convert_f16_to_float already says in its `f16 == 0` case, so the
             * whole lowest binade [2^-7, 2^-6) has no representation. Encoding
             * it as 1..4095 writes values hardware never produces.
             *
             * Bracketed on the 392 test Depth buffer oracle rather than
             * reasoned from the bias: over the 49 `z16 FZy` depth captures
             * silicon's smallest rasterised encoding is 4098, across 1,897,792
             * pixels, with none below 4096; and at the 192,864 pixels where
             * silicon writes 0 our encodings run 15 to 4094. 4094 below, 4098
             * above, and 4096 is a binade boundary and not a fitted constant.
             * Those 192,864 pixels are 97.9% of this cell's error; the rest of
             * the surface, big quad included, is already bit-identical, which
             * is what says the encoding itself is right. Issue #16, #52. */
            mstring_append(
                ps->code,
                "uint zbits = floatBitsToUint(max(zvalue, 0.0));\n"
                "uint zf16 = zbits < 0x3C800000u ? 0u\n"
                "          : min((zbits - 0x3C000000u) >> 11, 0xFFFFu);\n"
                "gl_FragDepth = float(zf16) / 65535.0;\n");
            break;
        default:
            mstring_append(ps->code,
                           "gl_FragDepth = zvalue / clipRange.y;\n");
            break;
        }
    }

    MString *final = mstring_new();
    pgraph_glsl_append_version(final, ps->opts.vulkan, ps->opts.gles,
                               ps->opts.gles_version);
    mstring_append(final, mstring_get_str(preflight));
    mstring_append(final, "void main() {\n");
    mstring_append(final, mstring_get_str(clip));
    mstring_append(final, mstring_get_str(vars));
    mstring_append(final, mstring_get_str(ps->code));
    mstring_append(final, "}\n");

    mstring_unref(preflight);
    mstring_unref(vars);
    mstring_unref(ps->code);

    return final;
}

static void parse_input(struct InputInfo *var, int value)
{
    var->reg = value & 0xF;
    var->chan = value & 0x10;
    var->mod = value & 0xE0;
}

static void parse_combiner_inputs(uint32_t value,
                                struct InputInfo *a, struct InputInfo *b,
                                struct InputInfo *c, struct InputInfo *d)
{
    parse_input(d, value & 0xFF);
    parse_input(c, (value >> 8) & 0xFF);
    parse_input(b, (value >> 16) & 0xFF);
    parse_input(a, (value >> 24) & 0xFF);
}

static void parse_combiner_output(uint32_t value, struct OutputInfo *out)
{
    out->cd = value & 0xF;
    out->ab = (value >> 4) & 0xF;
    out->muxsum = (value >> 8) & 0xF;
    int flags = value >> 12;
    out->flags = flags;
    out->cd_op = flags & 1;
    out->ab_op = flags & 2;
    out->muxsum_op = flags & 4;
    out->mapping = flags & 0x38;
    out->ab_alphablue = flags & 0x80;
    out->cd_alphablue = flags & 0x40;
}

MString *pgraph_glsl_gen_psh(const PshState *state, GenPshGlslOptions opts)
{
    int i;
    struct PixelShader ps;
    memset(&ps, 0, sizeof(ps));

    ps.opts = opts;
    ps.state = state;

    ps.num_stages = psh_num_combiner_stages(state->combiner_control);
    if ((state->combiner_control & 0xFF) > PSH_MAX_COMBINER_STAGES) {
        NV2A_UNIMPLEMENTED("%d combiner stages, the hardware has %d",
                           state->combiner_control & 0xFF,
                           PSH_MAX_COMBINER_STAGES);
    }
    ps.flags = state->combiner_control >> 8;
    for (i = 0; i < 4; i++) {
        ps.tex_modes[i] = (state->shader_stage_program >> (i * 5)) & 0x1F;
    }

    ps.dot_map[0] = 0;
    ps.dot_map[1] = (state->other_stage_input >> 0) & 0xf;
    ps.dot_map[2] = (state->other_stage_input >> 4) & 0xf;
    ps.dot_map[3] = (state->other_stage_input >> 8) & 0xf;

    ps.input_tex[0] = -1;
    ps.input_tex[1] = 0;
    ps.input_tex[2] = (state->other_stage_input >> 16) & 0xF;
    ps.input_tex[3] = (state->other_stage_input >> 20) & 0xF;
    for (i = 0; i < ps.num_stages; i++) {
        parse_combiner_inputs(state->rgb_inputs[i],
            &ps.stage[i].rgb_input.a, &ps.stage[i].rgb_input.b,
            &ps.stage[i].rgb_input.c, &ps.stage[i].rgb_input.d);
        parse_combiner_inputs(state->alpha_inputs[i],
            &ps.stage[i].alpha_input.a, &ps.stage[i].alpha_input.b,
            &ps.stage[i].alpha_input.c, &ps.stage[i].alpha_input.d);

        parse_combiner_output(state->rgb_outputs[i], &ps.stage[i].rgb_output);
        parse_combiner_output(state->alpha_outputs[i], &ps.stage[i].alpha_output);
    }

    struct InputInfo blank;
    ps.final_input.enabled = state->final_inputs_0 || state->final_inputs_1;
    if (ps.final_input.enabled) {
        parse_combiner_inputs(state->final_inputs_0,
                              &ps.final_input.a, &ps.final_input.b,
                              &ps.final_input.c, &ps.final_input.d);
        parse_combiner_inputs(state->final_inputs_1,
                              &ps.final_input.e, &ps.final_input.f,
                              &ps.final_input.g, &blank);
        int flags = state->final_inputs_1 & 0xFF;
        ps.final_input.clamp_sum = flags & PS_FINALCOMBINERSETTING_CLAMP_SUM;
        ps.final_input.inv_v1 = flags & PS_FINALCOMBINERSETTING_COMPLEMENT_V1;
        ps.final_input.inv_r0 = flags & PS_FINALCOMBINERSETTING_COMPLEMENT_R0;
    }

    return psh_convert(&ps);
}

void pgraph_glsl_set_psh_uniform_values(PGRAPHState *pg,
                                        const PshUniformLocs locs,
                                        PshUniformValues *values)
{
    if (locs[PshUniform_consts] != -1) {
        for (int i = 0; i < 9; i++) {
            uint32_t constant[2];
            if (i == 8) {
                /* final combiner */
                constant[0] = pgraph_reg_r(pg, NV_PGRAPH_SPECFOGFACTOR0);
                constant[1] = pgraph_reg_r(pg, NV_PGRAPH_SPECFOGFACTOR1);
            } else {
                constant[0] =
                    pgraph_reg_r(pg, NV_PGRAPH_COMBINEFACTOR0 + i * 4);
                constant[1] =
                    pgraph_reg_r(pg, NV_PGRAPH_COMBINEFACTOR1 + i * 4);
            }

            for (int j = 0; j < 2; j++) {
                int idx = i * 2 + j;
                pgraph_argb_pack32_to_rgba_float(constant[j],
                                                 values->consts[idx]);
            }
        }
    }
    if (locs[PshUniform_alphaRef] != -1) {
        int alpha_ref = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0),
                                 NV_PGRAPH_CONTROL_0_ALPHAREF);
        values->alphaRef[0] = alpha_ref;
    }
    if (locs[PshUniform_colorKey] != -1) {
        values->colorKey[0] = pgraph_reg_r(pg, NV_PGRAPH_COLORKEYCOLOR0);
        values->colorKey[1] = pgraph_reg_r(pg, NV_PGRAPH_COLORKEYCOLOR1);
        values->colorKey[2] = pgraph_reg_r(pg, NV_PGRAPH_COLORKEYCOLOR2);
        values->colorKey[3] = pgraph_reg_r(pg, NV_PGRAPH_COLORKEYCOLOR3);
    }
    if (locs[PshUniform_colorKeyMask] != -1) {
       for (int i = 0; i < NV2A_MAX_TEXTURES; i++) {
            values->colorKeyMask[i] =
                get_color_key_mask_for_texture(pg, i);
        }
    }

    for (int i = 0; i < NV2A_MAX_TEXTURES; i++) {
        /* Bump luminance only during stages 1 - 3 */
        if (i > 0) {
            if (locs[PshUniform_bumpMat] != -1) {
                uint32_t m_u32[4];
                m_u32[0] = pgraph_reg_r(pg, NV_PGRAPH_BUMPMAT00 + 4 * (i - 1));
                m_u32[1] = pgraph_reg_r(pg, NV_PGRAPH_BUMPMAT01 + 4 * (i - 1));
                m_u32[2] = pgraph_reg_r(pg, NV_PGRAPH_BUMPMAT10 + 4 * (i - 1));
                m_u32[3] = pgraph_reg_r(pg, NV_PGRAPH_BUMPMAT11 + 4 * (i - 1));
                values->bumpMat[i][0] = *(float *)&m_u32[0];
                values->bumpMat[i][1] = *(float *)&m_u32[1];
                values->bumpMat[i][2] = *(float *)&m_u32[2];
                values->bumpMat[i][3] = *(float *)&m_u32[3];
            }
            if (locs[PshUniform_bumpScale] != -1) {
                uint32_t v =
                    pgraph_reg_r(pg, NV_PGRAPH_BUMPSCALE1 + (i - 1) * 4);
                values->bumpScale[i] = *(float *)&v;
            }
            if (locs[PshUniform_bumpOffset] != -1) {
                uint32_t v =
                    pgraph_reg_r(pg, NV_PGRAPH_BUMPOFFSET1 + (i - 1) * 4);
                values->bumpOffset[i] = *(float *)&v;
            }
        }
        if (locs[PshUniform_texScale] != -1) {
            values->texScale[0] = 1.0; /* Renderer will override this */
        }
    }

    if (locs[PshUniform_borderColor] != -1) {
        for (int i = 0; i < 4; i++) {
            pgraph_argb_pack32_to_rgba_float(
                pgraph_reg_r(pg, NV_PGRAPH_BORDERCOLOR0 + i * 4),
                values->borderColor[i]);
        }
    }
    if (locs[PshUniform_eyeVec] != -1) {
        for (int k = 0; k < 3; k++) {
            uint32_t bits = pgraph_reg_r(pg, NV_PGRAPH_EYEVEC0 + k * 4);
            values->eyeVec[0][k] = *(float *)&bits;
        }
        values->eyeVec[0][3] = 0.0f;
    }

    if (locs[PshUniform_fogColor] != -1) {
        uint32_t fog_color = pgraph_reg_r(pg, NV_PGRAPH_FOGCOLOR);
        values->fogColor[0][0] =
            GET_MASK(fog_color, NV_PGRAPH_FOGCOLOR_RED) / 255.0;
        values->fogColor[0][1] =
            GET_MASK(fog_color, NV_PGRAPH_FOGCOLOR_GREEN) / 255.0;
        values->fogColor[0][2] =
            GET_MASK(fog_color, NV_PGRAPH_FOGCOLOR_BLUE) / 255.0;
        values->fogColor[0][3] =
            GET_MASK(fog_color, NV_PGRAPH_FOGCOLOR_ALPHA) / 255.0;
    }

    if (locs[PshUniform_fogParam] != -1) {
        uint32_t param_0 = pgraph_reg_r(pg, NV_PGRAPH_FOGPARAM0);
        uint32_t param_1 = pgraph_reg_r(pg, NV_PGRAPH_FOGPARAM1);
        memcpy(&values->fogParam[0][0], &param_0, sizeof(float));
        memcpy(&values->fogParam[0][1], &param_1, sizeof(float));
    }

    if (locs[PshUniform_clipRange] != -1) {
        pgraph_glsl_set_clip_range_uniform_value(pg, values->clipRange[0]);
    }

    bool polygon_offset_enabled = false;
    if (pg->primitive_mode >= PRIM_TYPE_TRIANGLES) {
        uint32_t raster = pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER);
        uint32_t polygon_mode =
            GET_MASK(raster, NV_PGRAPH_SETUPRASTER_FRONTFACEMODE);

        if ((polygon_mode == NV_PGRAPH_SETUPRASTER_FRONTFACEMODE_FILL &&
             (raster & NV_PGRAPH_SETUPRASTER_POFFSETFILLENABLE)) ||
            (polygon_mode == NV_PGRAPH_SETUPRASTER_FRONTFACEMODE_LINE &&
             (raster & NV_PGRAPH_SETUPRASTER_POFFSETLINEENABLE)) ||
            (polygon_mode == NV_PGRAPH_SETUPRASTER_FRONTFACEMODE_POINT &&
             (raster & NV_PGRAPH_SETUPRASTER_POFFSETPOINTENABLE))) {
            polygon_offset_enabled = true;
        }
    }

    if (locs[PshUniform_depthOffset] != -1) {
        float zbias = 0.0f;

        if (polygon_offset_enabled) {
            uint32_t zbias_u32 = pgraph_reg_r(pg, NV_PGRAPH_ZOFFSETBIAS);
            zbias = *(float *)&zbias_u32;
        }

        values->depthOffset[0] = zbias;
    }

    if (locs[PshUniform_depthFactor] != -1) {
        float zfactor = 0.0f;

        if (polygon_offset_enabled) {
            uint32_t zfactor_u32 = pgraph_reg_r(pg, NV_PGRAPH_ZOFFSETFACTOR);
            zfactor = *(float *)&zfactor_u32;
            /* Under w-buffering the shader applies this once per primitive,
             * at the first covered pixel (wbufSlopeStep). */
        }

        values->depthFactor[0] = zfactor;
    }

    if (locs[PshUniform_stipplePattern] != -1) {
        for (int i = 0; i < 8; i++) {
            for (int j = 0; j < 4; j++) {
                values->stipplePattern[i][j] = pg->stipple_pattern[i * 4 + j];
            }
        }
    }

    if (locs[PshUniform_surfaceScale] != -1) {
        unsigned int wscale = 1, hscale = 1;
        pgraph_apply_anti_aliasing_factor(pg, &wscale, &hscale);
        pgraph_apply_scaling_factor(pg, &wscale, &hscale);
        values->surfaceScale[0][0] = wscale;
        values->surfaceScale[0][1] = hscale;
    }

    unsigned int max_gl_width = pg->surface_binding_dim.width;
    unsigned int max_gl_height = pg->surface_binding_dim.height;
    pgraph_apply_scaling_factor(pg, &max_gl_width, &max_gl_height);

    for (int i = 0; i < 8; i++) {
        uint32_t x = pgraph_reg_r(pg, NV_PGRAPH_WINDOWCLIPX0 + i * 4);
        unsigned int x_min = GET_MASK(x, NV_PGRAPH_WINDOWCLIPX0_XMIN);
        unsigned int x_max = GET_MASK(x, NV_PGRAPH_WINDOWCLIPX0_XMAX) + 1;

        uint32_t y = pgraph_reg_r(pg, NV_PGRAPH_WINDOWCLIPY0 + i * 4);
        unsigned int y_min = GET_MASK(y, NV_PGRAPH_WINDOWCLIPY0_YMIN);
        unsigned int y_max = GET_MASK(y, NV_PGRAPH_WINDOWCLIPY0_YMAX) + 1;

        pgraph_apply_anti_aliasing_factor(pg, &x_min, &y_min);
        pgraph_apply_anti_aliasing_factor(pg, &x_max, &y_max);

        pgraph_apply_scaling_factor(pg, &x_min, &y_min);
        pgraph_apply_scaling_factor(pg, &x_max, &y_max);

        values->clipRegion[i][0] = x_min;
        values->clipRegion[i][1] = y_min;
        values->clipRegion[i][2] = x_max;
        values->clipRegion[i][3] = y_max;
    }
}
