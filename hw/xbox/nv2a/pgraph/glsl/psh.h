/*
 * Geforce NV2A PGRAPH GLSL Shader Generator
 *
 * Copyright (c) 2013 espes
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

#ifndef HW_XBOX_NV2A_PGRAPH_GLSL_PSH_H
#define HW_XBOX_NV2A_PGRAPH_GLSL_PSH_H

#include "common.h"
#include "hw/xbox/nv2a/pgraph/psh_regs.h"
#include "hw/xbox/nv2a/pgraph/vsh_regs.h"

typedef struct PGRAPHState PGRAPHState;

enum PshDepthFormat {
    DEPTH_FORMAT_D24,
    DEPTH_FORMAT_D16,
    DEPTH_FORMAT_F24,
    DEPTH_FORMAT_F16,
};

typedef struct PshState {
    uint32_t combiner_control;
    uint32_t shader_stage_program;
    uint32_t other_stage_input;
    uint32_t final_inputs_0;
    uint32_t final_inputs_1;

    uint32_t rgb_inputs[8], rgb_outputs[8];
    uint32_t alpha_inputs[8], alpha_outputs[8];

    bool point_sprite;
    bool rect_tex[4];
    bool snorm_tex[4];
    /* The texel holds two real 16-bit fields, so a HILO dot mapping reads
     * each field whole instead of rebuilding it from two bytes. */
    bool tex_hilo16[4];
    /* The view swizzle drives component 0 from a literal rather than from
     * stored data, so a TEXFILTER sign flag on it has nothing to sign. */
    bool tex_comp0_const[4];
    uint32_t tex_signed[4]; /* NV_PGRAPH_TEXFILTER0_[ARGB]SIGNED bits */
    bool compare_mode[4][4];
    bool alphakill[4];
    int colorkey_mode[4];
    enum ConvolutionFilter conv_tex[4];
    bool tex_x8y24[4];
    int dim_tex[4];
    bool tex_cubemap[4];
    /* NV_PGRAPH_TEXADDRESSn axes in BORDER mode: 1 U, 2 V, 4 P */
    uint8_t addr_border[4];

    float border_logical_size[4][3];
    float border_inv_real_size[4][3];

    bool shadow_map[4];
    bool tex_depth_float[4];
    enum PshShadowDepthFunc shadow_depth_func;

    bool alpha_test;
    enum PshAlphaFunc alpha_func;

    /*
     * #43's signed fold is deliberately NOT a field here, and the reason is a
     * defect this file caused once already.
     *
     * It was `bool signed_blend_fold`, set from NV_PGRAPH_BLEND. But
     * pgraph_glsl_check_shader_state_dirty() decides whether to rebuild
     * ShaderState from a FIXED register list, and NV_PGRAPH_BLEND is not in
     * it. So a guest that changes blending without touching any watched
     * register keeps the cached shader -- and blend_tests.cpp's DrawQuad does
     * exactly that, calling SetBlend(false) for its RGB half between two
     * blended alpha draws. The folded shader was then reused on a draw with
     * blending OFF, where green 0xCC = 204 sits above the sign bit, got masked
     * to f1 = 0, and went to the framebuffer unblended: DrawAlphaStack's ring
     * 0 measured G 204 -> 0 against a golden of 204 on all 11,280 px.
     *
     * A cache key must not depend on an input the invalidation does not watch.
     * Adding NV_PGRAPH_BLEND to that list would fix this instance and leave the
     * class open for the next field, so the fold rides the `signedBlendPass`
     * uniform ALONE -- computed from the live register every time uniforms are
     * staged, where nothing can be stale.
     */

    bool window_clip_exclusive;
    int window_clip_count;

    bool smooth_shading;
    bool two_side_light;
    bool stipple;
    bool fog_enable;
    enum VshFogMode fog_mode;
    bool depth_clipping;
    bool z_perspective;
    bool noperspective; /* SET_CONTROL0 texture perspective off */
    bool depth_needed;

    unsigned int surface_zeta_format;
    enum PshDepthFormat depth_format;
} PshState;

int pgraph_glsl_window_clip_count(PGRAPHState *pg);
bool pgraph_glsl_polygon_stipple_enabled(PGRAPHState *pg);
void pgraph_glsl_set_psh_state(PGRAPHState *pg, PshState *state);

#define PSH_UNIFORM_DECL_X(S, DECL) \
    DECL(S, alphaRef, int, 1)       \
    DECL(S, borderColor, vec4, 4)   \
    DECL(S, bumpMat, mat2, 4)       \
    DECL(S, bumpOffset, float, 4)   \
    DECL(S, bumpScale, float, 4)    \
    DECL(S, clipRange, vec4, 1)     \
    DECL(S, clipRegion, ivec4, 8)   \
    DECL(S, colorKey, uint, 4)      \
    DECL(S, colorKeyMask, uint, 4)  \
    DECL(S, consts, vec4, 18)       \
    DECL(S, depthFactor, float, 1)  \
    DECL(S, depthOffset, float, 1)  \
    DECL(S, eyeVec, vec4, 1)        \
    DECL(S, fogColor, vec4, 1)      \
    DECL(S, fogParam, vec2, 1)      \
    DECL(S, signedBlendPass, int, 1) \
    DECL(S, stipplePattern, ivec4, 8) \
    DECL(S, surfaceScale, ivec2, 1) \
    DECL(S, texScale, float, 4)

DECL_UNIFORM_TYPES(PshUniform, PSH_UNIFORM_DECL_X)

/*
 * The register file has eight combiner stages: NV_PGRAPH_COMBINEALPHAI0 and
 * NV_PGRAPH_COMBINEALPHAO0 sit 0x20 apart, and every array here is sized for
 * eight. The stage count arrives in the low byte of NV097_SET_COMBINER_CONTROL
 * as guest data, and nothing masks it on the way in, so a count of 0xFF walked
 * the loops in psh.c and shaders.c past the end of those arrays.
 *
 * What the hardware does with a count above eight is not known. Not indexing
 * past the registers that exist is the part that is.
 */
#define PSH_MAX_COMBINER_STAGES 8

static inline int psh_num_combiner_stages(uint32_t combiner_control)
{
    return MIN(combiner_control & 0xFF, PSH_MAX_COMBINER_STAGES);
}

typedef struct GenPshGlslOptions {
    bool vulkan;
    /* See PGRAPHState::zeta_stored_as_float. */
    bool float_depth_storage;
    bool gles;
    int gles_version;
    int ubo_binding;
    int ubo_set;
    int tex_binding;
} GenPshGlslOptions;

MString *pgraph_glsl_gen_psh(const PshState *state, GenPshGlslOptions opts);

void pgraph_glsl_set_psh_uniform_values(PGRAPHState *pg,
                                        const PshUniformLocs locs,
                                        PshUniformValues *values);

/*
 * #43's signed-blend pass selector: SIGNED_BLEND_PASS_LOW keeps the channels
 * whose source byte is below 128 and zeroes the rest, SIGNED_BLEND_PASS_HIGH
 * keeps 256 - S on the others and zeroes the low ones. Zero is an exact
 * identity for the blend op each pass carries, which is what lets the two
 * passes compose into a discontinuous map, and lets all four channels ride one
 * pass with no write mask and no discard.
 *
 * This is renderer state, not guest state -- a draw does not know which of its
 * two passes it is -- so it is deliberately NOT in PshState, where it would
 * split the shader cache for no reason. The renderer sets it immediately
 * before staging uniforms for each pass, on the thread that owns the draw.
 */
enum {
    /*
     * NONE is the value every ordinary draw stages, and it must be 0 so that a
     * shader whose uniform was never written behaves as an unfolded draw.
     */
    SIGNED_BLEND_PASS_NONE = 0,
    SIGNED_BLEND_PASS_LOW = 1,
    SIGNED_BLEND_PASS_HIGH = 2,
};

void pgraph_glsl_set_signed_blend_pass(int pass);
int pgraph_glsl_get_signed_blend_pass(void);

/*
 * How many times each half was STAGED into a uniform buffer. A pass being
 * requested and a pass's uniform reaching the GPU are different events, and
 * #43's ring-0 regression cannot be told from an arithmetic error without
 * separating them.
 */
void pgraph_glsl_get_signed_blend_staged(unsigned long *low,
                                         unsigned long *high);

#endif
