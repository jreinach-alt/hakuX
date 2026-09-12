/*
 * Geforce NV2A PGRAPH Vulkan Renderer
 *
 * Copyright (c) 2024 Matt Borgerson
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

#ifndef HW_XBOX_NV2A_PGRAPH_VK_CONSTANTS_H
#define HW_XBOX_NV2A_PGRAPH_VK_CONSTANTS_H

#include "hw/xbox/nv2a/nv2a_regs.h"
#include "hw/xbox/nv2a/pgraph/vsh_regs.h"
#include <vulkan/vulkan.h>

static const VkFilter pgraph_texture_min_filter_vk_map[] = {
    0,
    VK_FILTER_NEAREST,
    VK_FILTER_LINEAR,
    VK_FILTER_NEAREST,
    VK_FILTER_LINEAR,
    VK_FILTER_NEAREST,
    VK_FILTER_LINEAR,
    VK_FILTER_LINEAR,
};

static const VkFilter pgraph_texture_mag_filter_vk_map[] = {
    0,
    VK_FILTER_NEAREST,
    VK_FILTER_LINEAR,
    0,
    VK_FILTER_LINEAR /* TODO: Convolution filter... */
};

static const VkSamplerAddressMode pgraph_texture_addr_vk_map[] = {
    0,
    VK_SAMPLER_ADDRESS_MODE_REPEAT,
    VK_SAMPLER_ADDRESS_MODE_MIRRORED_REPEAT,
    VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
    VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_BORDER,
    VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE, /* Approximate GL_CLAMP */
};

static const VkBlendFactor pgraph_blend_factor_vk_map[] = {
    VK_BLEND_FACTOR_ZERO,
    VK_BLEND_FACTOR_ONE,
    VK_BLEND_FACTOR_SRC_COLOR,
    VK_BLEND_FACTOR_ONE_MINUS_SRC_COLOR,
    VK_BLEND_FACTOR_SRC_ALPHA,
    VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA,
    VK_BLEND_FACTOR_DST_ALPHA,
    VK_BLEND_FACTOR_ONE_MINUS_DST_ALPHA,
    VK_BLEND_FACTOR_DST_COLOR,
    VK_BLEND_FACTOR_ONE_MINUS_DST_COLOR,
    VK_BLEND_FACTOR_SRC_ALPHA_SATURATE,
    0,
    VK_BLEND_FACTOR_CONSTANT_COLOR,
    VK_BLEND_FACTOR_ONE_MINUS_CONSTANT_COLOR,
    VK_BLEND_FACTOR_CONSTANT_ALPHA,
    VK_BLEND_FACTOR_ONE_MINUS_CONSTANT_ALPHA,
};

static const VkBlendOp pgraph_blend_equation_vk_map[] = {
    VK_BLEND_OP_SUBTRACT,
    VK_BLEND_OP_REVERSE_SUBTRACT,
    VK_BLEND_OP_ADD,
    VK_BLEND_OP_MIN,
    VK_BLEND_OP_MAX,
    VK_BLEND_OP_REVERSE_SUBTRACT,
    VK_BLEND_OP_ADD,
};

/* FIXME
static const GLenum pgraph_blend_logicop_map[] = {
    GL_CLEAR,
    GL_AND,
    GL_AND_REVERSE,
    GL_COPY,
    GL_AND_INVERTED,
    GL_NOOP,
    GL_XOR,
    GL_OR,
    GL_NOR,
    GL_EQUIV,
    GL_INVERT,
    GL_OR_REVERSE,
    GL_COPY_INVERTED,
    GL_OR_INVERTED,
    GL_NAND,
    GL_SET,
};
*/

static const VkCullModeFlags pgraph_cull_face_vk_map[] = {
    0,
    VK_CULL_MODE_FRONT_BIT,
    VK_CULL_MODE_BACK_BIT,
    VK_CULL_MODE_FRONT_AND_BACK,
};

static const VkCompareOp pgraph_depth_func_vk_map[] = {
    VK_COMPARE_OP_NEVER,
    VK_COMPARE_OP_LESS,
    VK_COMPARE_OP_EQUAL,
    VK_COMPARE_OP_LESS_OR_EQUAL,
    VK_COMPARE_OP_GREATER,
    VK_COMPARE_OP_NOT_EQUAL,
    VK_COMPARE_OP_GREATER_OR_EQUAL,
    VK_COMPARE_OP_ALWAYS,
};

static const VkCompareOp pgraph_stencil_func_vk_map[] = {
    VK_COMPARE_OP_NEVER,
    VK_COMPARE_OP_LESS,
    VK_COMPARE_OP_EQUAL,
    VK_COMPARE_OP_LESS_OR_EQUAL,
    VK_COMPARE_OP_GREATER,
    VK_COMPARE_OP_NOT_EQUAL,
    VK_COMPARE_OP_GREATER_OR_EQUAL,
    VK_COMPARE_OP_ALWAYS,
};

static const VkStencilOp pgraph_stencil_op_vk_map[] = {
    0,
    VK_STENCIL_OP_KEEP,
    VK_STENCIL_OP_ZERO,
    VK_STENCIL_OP_REPLACE,
    VK_STENCIL_OP_INCREMENT_AND_CLAMP,
    VK_STENCIL_OP_DECREMENT_AND_CLAMP,
    VK_STENCIL_OP_INVERT,
    VK_STENCIL_OP_INCREMENT_AND_WRAP,
    VK_STENCIL_OP_DECREMENT_AND_WRAP,
};

static const VkPolygonMode pgraph_polygon_mode_vk_map[] = {
    [POLY_MODE_FILL] = VK_POLYGON_MODE_FILL,
    [POLY_MODE_POINT] = VK_POLYGON_MODE_POINT,
    [POLY_MODE_LINE] = VK_POLYGON_MODE_LINE,
};

typedef struct VkColorFormatInfo {
    VkFormat vk_format;
    VkComponentMapping component_map;
} VkColorFormatInfo;

/*
 * ONE OF FOUR TABLES THAT MUST AGREE, WITH NOTHING ENFORCING IT.
 *
 *   pgraph/texture.c        kelvin_color_format_info_map  guest-side layout
 *   pgraph/vk/constants.h   kelvin_color_format_vk_map    host format, Vulkan
 *   pgraph/gl/constants.h   kelvin_color_format_gl_map    host format, GL
 *   pgraph/vk/texture_dump.c                              host format, again
 *
 * Adding or changing a format means touching all four. They are indexed by
 * the same NV097_SET_TEXTURE_FORMAT_COLOR_* constant and sized [66], so a
 * missing row is a zero row rather than a compile error.
 *
 * docs/testing/nv2a_index.py query symbol <the format> lists every site.
 */
/*
 * A row marked "Converted" is not the guest format: pgraph_convert_texture_data
 * has already rewritten the pixels and this is the format of the RESULT. The
 * conversion and this entry must agree about signedness as well as layout -
 * SZ_R6G5B5 converts to plain unsigned RGBA8 and lands in a UNORM image here.
 * It used to convert to signed bytes and land in an SNORM image, which the
 * fragment shader then had to know not to remap again; signedness is a sampler
 * property on this hardware, so it is applied by texture_wants_snorm() now and
 * the conversion no longer has an opinion. See glsl/psh.c snorm_tex and
 * docs/investigations/nv2a-sweep-2026-09.md.
 */
static const VkColorFormatInfo kelvin_color_format_vk_map[66] = {
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_Y8] = {
        VK_FORMAT_R8_UNORM,
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_ONE },
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_AY8] = {
        VK_FORMAT_R8_UNORM,
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A1R5G5B5] = {
        VK_FORMAT_A1R5G5B5_UNORM_PACK16,
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_X1R5G5B5] = {
        VK_FORMAT_A1R5G5B5_UNORM_PACK16,
        { VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_ONE },
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A4R4G4B4] = {
        VK_FORMAT_A4R4G4B4_UNORM_PACK16,
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R5G6B5] = {
        VK_FORMAT_R5G6B5_UNORM_PACK16,
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8R8G8B8] = {
        VK_FORMAT_B8G8R8A8_UNORM,
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_X8R8G8B8] = {
        VK_FORMAT_B8G8R8A8_UNORM,
        { VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_ONE },
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_I8_A8R8G8B8] = {
        VK_FORMAT_B8G8R8A8_UNORM, // Converted
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_L_DXT1_A1R5G5B5] = {
        VK_FORMAT_R8G8B8A8_UNORM, // Converted
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_L_DXT23_A8R8G8B8] = {
        VK_FORMAT_R8G8B8A8_UNORM, // Converted
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_L_DXT45_A8R8G8B8] = {
        VK_FORMAT_R8G8B8A8_UNORM, // Converted
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A1R5G5B5] = {
        VK_FORMAT_A1R5G5B5_UNORM_PACK16,
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_R5G6B5] = {
        VK_FORMAT_R5G6B5_UNORM_PACK16,
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8] = {
        VK_FORMAT_B8G8R8A8_UNORM,
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_Y8] = {
        VK_FORMAT_R8_UNORM,
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_ONE, }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_G8B8] = {
        VK_FORMAT_R8G8_UNORM,
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_G, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_G, }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8] = {
        VK_FORMAT_R8_UNORM,
        { VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_R },
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8Y8] = {
        VK_FORMAT_R8G8_UNORM,
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_G }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_AY8] = {
        VK_FORMAT_R8_UNORM,
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_X1R5G5B5] = {
        VK_FORMAT_A1R5G5B5_UNORM_PACK16,
        { VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_ONE },
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A4R4G4B4] = {
        VK_FORMAT_A4R4G4B4_UNORM_PACK16,
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_X8R8G8B8] = {
        VK_FORMAT_B8G8R8A8_UNORM,
        { VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_ONE },
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8] = {
        VK_FORMAT_R8_UNORM,
        { VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_R }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8Y8] = {
        VK_FORMAT_R8G8_UNORM,
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_G }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R6G5B5] = {
        VK_FORMAT_R8G8B8A8_UNORM, // Converted
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_G8B8] = {
        VK_FORMAT_R8G8_UNORM,
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_G, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_G }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R8B8] = {
        VK_FORMAT_R8G8_UNORM,
        { VK_COMPONENT_SWIZZLE_G, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_G }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LC_IMAGE_CR8YB8CB8YA8] = {
        VK_FORMAT_R8G8B8A8_UNORM, // Converted
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LC_IMAGE_YB8CR8YA8CB8] = {
        VK_FORMAT_R8G8B8A8_UNORM, // Converted
    },

    /* Additional information is passed to the pixel shader via the swizzle:
     * RED: The depth value.
     * GREEN: 0 for 16-bit, 1 for 24 bit
     * BLUE: 0 for fixed, 1 for float
     */
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_DEPTH_Y16_FIXED] = {
        VK_FORMAT_R16_UNORM, // FIXME
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_ZERO, VK_COMPONENT_SWIZZLE_ZERO, VK_COMPONENT_SWIZZLE_ZERO },
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_DEPTH_X8_Y24_FIXED] = {
        // FIXME
        // {GL_DEPTH_COMPONENT, GL_DEPTH_STENCIL, GL_UNSIGNED_INT_24_8, {GL_RED, GL_ONE, GL_ZERO, GL_ZERO}},
        VK_FORMAT_R32_UINT,
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_ZERO,  VK_COMPONENT_SWIZZLE_ZERO },
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_DEPTH_X8_Y24_FLOAT] = {
        // FIXME
        // {GL_DEPTH_COMPONENT, GL_DEPTH_STENCIL, GL_UNSIGNED_INT_24_8, {GL_RED, GL_ONE, GL_ZERO, GL_ZERO}},
        VK_FORMAT_R32_UINT,
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_ZERO,  VK_COMPONENT_SWIZZLE_ZERO },
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_DEPTH_Y16_FIXED] = {
        VK_FORMAT_R16_UNORM, // FIXME
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_ZERO, VK_COMPONENT_SWIZZLE_ZERO, VK_COMPONENT_SWIZZLE_ZERO },
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_DEPTH_Y16_FLOAT] = {
        VK_FORMAT_R16_UNORM, // FIXME
        { VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_ZERO, VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_ZERO },
    },
    /* Hardware forces red to 1.0 for Y16 and puts the luminance in green
     * and blue only -- unlike Y8/AY8/A8Y8, which replicate to all three.
     * Measured: TexFmt_Y16 golden has R=255 across the quad while G and B
     * track the ramp exactly.
     *
     * PINNED, measured 2026-09-12, like SZ_R16B16 below: TexFmt_Y16 and
     * _Y16_L are 0 differing px of 307,200, and inside the quad the golden
     * holds 188 distinct green and blue values against 2 in red. #10's Y16
     * bump class cannot be addressed from this row: one 16-bit channel has a
     * single value to give a bump stage that wants two, and splitting it into
     * hi/lo bytes means a different VkFormat, which would move the 188-value
     * ramp this row is exact on. Stage-aware, or not here. */
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_Y16] = {
        VK_FORMAT_R16_UNORM,
        { VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_ONE }
    },
    /* Two 16-bit channels holding R and B.  Component order mirrors SZ_R8B8,
     * which is the same channel layout at 8 bits.
     *
     * PINNED, measured 2026-09-12 -- read this before retargeting issue #10's
     * R16B16 class here. Texture_format renders these formats as a colour
     * lookup and we are bit-exact: TexFmt_R16B16 and _R16B16_L are 0
     * differing px of 307,200. Inside the drawn quad that golden holds 157
     * distinct red values, 64 green, 64 blue and 50 alpha, so all four
     * components are live ramps, not constants, and every one of them is
     * reproduced exactly. There is no free component here.
     *
     * That matters because BUMPENVMAP_LUM takes its luminance from component
     * 0, which this map feeds from the B16 field. "Take the luminance from
     * the other channel" therefore cannot be done in this table: component 0
     * is also the colour path's red, with 157 values pinned to it. Any fix
     * for the R16B16 bump class has to be stage-aware, which this table is
     * not -- it is indexed by texture format alone. */
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R16B16] = {
        VK_FORMAT_R16G16_UNORM,
        { VK_COMPONENT_SWIZZLE_G, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_G }
    },
    /* Hardware forces red to 1.0 for Y16 and puts the luminance in green
     * and blue only -- unlike Y8/AY8/A8Y8, which replicate to all three.
     * Measured: TexFmt_Y16 golden has R=255 across the quad while G and B
     * track the ramp exactly. */
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_Y16] = {
        VK_FORMAT_R16_UNORM,
        { VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_ONE }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_R16B16] = {
        VK_FORMAT_R16G16_UNORM,
        { VK_COMPONENT_SWIZZLE_G, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_G }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8B8G8R8] = {
        VK_FORMAT_R8G8B8A8_UNORM,
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_B8G8R8A8] = {
        VK_FORMAT_R8G8B8A8_UNORM,
        { VK_COMPONENT_SWIZZLE_G, VK_COMPONENT_SWIZZLE_B, VK_COMPONENT_SWIZZLE_A, VK_COMPONENT_SWIZZLE_R }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R8G8B8A8] = {
        VK_FORMAT_R8G8B8A8_UNORM,
        { VK_COMPONENT_SWIZZLE_A, VK_COMPONENT_SWIZZLE_B, VK_COMPONENT_SWIZZLE_G, VK_COMPONENT_SWIZZLE_R }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8B8G8R8] = {
        VK_FORMAT_R8G8B8A8_UNORM,
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_B8G8R8A8] = {
        VK_FORMAT_R8G8B8A8_UNORM,
        { VK_COMPONENT_SWIZZLE_G, VK_COMPONENT_SWIZZLE_B, VK_COMPONENT_SWIZZLE_A, VK_COMPONENT_SWIZZLE_R }
    },
    [NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_R8G8B8A8] = {
        VK_FORMAT_R8G8B8A8_UNORM,
        { VK_COMPONENT_SWIZZLE_A, VK_COMPONENT_SWIZZLE_B, VK_COMPONENT_SWIZZLE_G, VK_COMPONENT_SWIZZLE_R }
    },
};

typedef struct BasicSurfaceFormatInfo {
    unsigned int bytes_per_pixel;
} BasicSurfaceFormatInfo;

typedef struct SurfaceFormatInfo {
    unsigned int host_bytes_per_pixel;
    VkFormat vk_format;
    VkImageUsageFlags usage;
    VkImageAspectFlags aspect;
    /*
     * What the texture unit reads back for this format's pad bits when the
     * surface is sampled as a texture -- a *different* question from what the
     * blend unit substitutes for the missing destination alpha, which is the
     * stored alpha for both suffixes (see the _Z notes below and issue #48).
     *
     * VK_COMPONENT_SWIZZLE_IDENTITY (0) means the format has no pad bits, or
     * has some whose readback is not a constant and so cannot be expressed as
     * a swizzle -- X1A7R8G8B8 is the latter, see its entry. Only the four
     * formats whose whole alpha field is pad get an override here.
     */
    VkComponentSwizzle sampled_pad_alpha;
} SurfaceFormatInfo;

/*
 * Guest-side pixel width for every colour surface format the register can name.
 * This drives surface size and pitch arithmetic, so a missing row is not a
 * cosmetic gap -- it computes the wrong extent for guest memory. Complete even
 * where the host mapping below is an approximation.
 */
static const BasicSurfaceFormatInfo kelvin_surface_color_format_map[] = {
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X1R5G5B5_Z1R5G5B5] = { 2 },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X1R5G5B5_O1R5G5B5] = { 2 },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_R5G6B5] = { 2 },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X8R8G8B8_Z8R8G8B8] = { 4 },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X8R8G8B8_O8R8G8B8] = { 4 },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X1A7R8G8B8_Z1A7R8G8B8] = { 4 },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X1A7R8G8B8_O1A7R8G8B8] = { 4 },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_A8R8G8B8] = { 4 },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_B8] = { 1 },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_G8B8] = { 2 },
};

static const SurfaceFormatInfo kelvin_surface_color_format_vk_map[] = {
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X1R5G5B5_Z1R5G5B5] =
    {
        /*
         * Measured 2026-09-12 (issue #48): the Z/O suffix describes the pad
         * bits when the surface is sampled or displayed, NOT what the blend
         * unit substitutes for the missing alpha. For blending, a Z variant's
         * destination alpha behaves like a stored alpha -- its Blend surface
         * golden is identical to A8R8G8B8's at a fixed coordinate, and we are
         * already exact there. Forcing it to zero makes those captures worse.
         * Only the O variant needs a forced one.
         *
         * The texture unit is the other half of #48 and it does read the pad
         * bit: sampled as a texture this format's alpha is 0. Measured, see
         * sampled_pad_alpha below.
         */
        2,
        VK_FORMAT_A1R5G5B5_UNORM_PACK16,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
        VK_COMPONENT_SWIZZLE_ZERO,
    },
    /*
     * The Z and O variants differ only in what the unused bits read back as --
     * zero or one -- not in storage layout, so each shares its counterpart's
     * host format. Getting those pad bits right is a separate, smaller problem
     * than not rendering at all: this one was `unimplemented color surface
     * format 0x2` and abort(), five tests into Blend surface (issue #28).
     */
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X1R5G5B5_O1R5G5B5] =
    {
        /*
         * Issue #48: this one is real. The blend unit reads this format's
         * destination alpha as 1.0 -- solved from the goldens, where the
         * result is S * Ad with df=ZERO and hardware's output is 255 where
         * ours is S. Not yet fixed: the same captures are dominated by a
         * two-draw pairing defect, so substituting the factor alone moves no
         * number. See the issue before touching this.
         *
         * The texture unit half IS settled: sampled as a texture this format's
         * alpha reads 1.0. Measured, see sampled_pad_alpha below.
         */
        2,
        VK_FORMAT_A1R5G5B5_UNORM_PACK16,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
        VK_COMPONENT_SWIZZLE_ONE,
    },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_R5G6B5] =
    {
        2,
        VK_FORMAT_R5G6B5_UNORM_PACK16,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
    },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X8R8G8B8_Z8R8G8B8] =
    {
        /*
         * Measured 2026-09-12 (issue #48): the Z/O suffix describes the pad
         * bits when the surface is sampled or displayed, NOT what the blend
         * unit substitutes for the missing alpha. For blending, a Z variant's
         * destination alpha behaves like a stored alpha -- its Blend surface
         * golden is identical to A8R8G8B8's at a fixed coordinate, and we are
         * already exact there. Forcing it to zero makes those captures worse.
         * Only the O variant needs a forced one.
         *
         * The texture unit is the other half of #48 and it does read the pad
         * byte: sampled as a texture this format's alpha is 0. Measured, see
         * sampled_pad_alpha below.
         */
        4,
        VK_FORMAT_B8G8R8A8_UNORM,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
        VK_COMPONENT_SWIZZLE_ZERO,
    },
    /* The _O8 twin of X8R8G8B8_Z8R8G8B8: the X byte reads back as ones instead
     * of zeros. Was `unimplemented color surface format 0x5` and abort(), six
     * tests into Blend surface (issue #28). With this every colour surface
     * format the hardware defines, 0x1 to 0xA, has an entry. */
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X8R8G8B8_O8R8G8B8] =
    {
        /*
         * Issue #48: this one is real. The blend unit reads this format's
         * destination alpha as 1.0 -- solved from the goldens, where the
         * result is S * Ad with df=ZERO and hardware's output is 255 where
         * ours is S. Not yet fixed: the same captures are dominated by a
         * two-draw pairing defect, so substituting the factor alone moves no
         * number. See the issue before touching this.
         *
         * The texture unit half IS settled: sampled as a texture this format's
         * alpha reads 1.0. This is where the "S = 108" came from -- with a
         * stored swatch alpha of 34, 255*(34/255) + 85*(221/255) = 108 where
         * hardware, reading the pad byte as ones, gets 255*1 = 255. Measured,
         * see sampled_pad_alpha below.
         */
        4,
        VK_FORMAT_B8G8R8A8_UNORM,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
        VK_COMPONENT_SWIZZLE_ONE,
    },
    /*
     * X1A7R8G8B8: seven bits of alpha in 24..30 under a fixed X bit that reads
     * back as 0 (_Z) or 1 (_O). Kept as B8G8R8A8 on the host, so rendering and
     * blending are right to within the 7-bit quantisation, and a readback
     * hands the guest an 8-bit alpha where it expects X1A7 -- the X bit and
     * the alpha LSB come back wrong. That is a defect to measure; what was
     * here before was `unimplemented color surface format 0x7` and abort(),
     * which took Surface format and Blend surface out of every sweep and is
     * issue #24.
     *
     * MEASURED 2026-09-12 what the texture unit reads back here, because it is
     * the one pad format whose readback is NOT a constant and so gets no
     * sampled_pad_alpha override. Solving the alpha out of Surface format's
     * goldens -- the suite draws the surface twice, once with the sampled
     * alpha and once with alpha forced opaque, over a known checkerboard, so
     * a = (blended - background) / (opaque - background) per pixel:
     *
     *     sampled alpha = (X << 7) | (stored_alpha >> 1)
     *
     * X = 0 for _Z and 1 for _O. Over 32,755 invertible px the _O recovery
     * sits exactly 128 above the _Z recovery in all eight stored-alpha octiles
     * (127.92..128.40), and quad A -- rendered into the surface with alpha
     * forced opaque -- recovers 126.94 for _Z and 255.00 for _O.
     *
     * Scored against five rivals on the same region: truncation as above
     * 2,097/2,157 differing of 32,755 at max|delta| 1, round-to-nearest
     * 20,362/20,372, seven-bit bit-replication 32,570/16,368, mask-only
     * 16,194/32,755, a Z/O constant 32,447/16,370, and no pad handling at all
     * 32,581/16,370. So hardware truncates, and the alpha field really is
     * seven bits under the X bit rather than an eight-bit field expanded.
     * The residual is my own forward model's floor: Fmt_A8R8G8B8, which has no
     * rule to fit, scores 464 on the same measurement.
     *
     * Not implemented: this needs the stored alpha requantised to 7 bits, not
     * a component swizzle, and we store 8-bit alpha here. It is also only half
     * the capture's residual -- the other half is that 7-bit quantisation on
     * the way IN. Left as a measured negative rather than a guess.
     */
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X1A7R8G8B8_Z1A7R8G8B8] =
    {
        4,
        VK_FORMAT_B8G8R8A8_UNORM,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
    },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X1A7R8G8B8_O1A7R8G8B8] =
    {
        4,
        VK_FORMAT_B8G8R8A8_UNORM,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
    },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_A8R8G8B8] =
    {
        4,
        VK_FORMAT_B8G8R8A8_UNORM,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
    },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_B8] =
    {
        // FIXME: Map channel color
        1,
        VK_FORMAT_R8_UNORM,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
    },
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_G8B8] =
    {
        // FIXME: Map channel color
        2,
        VK_FORMAT_R8G8_UNORM,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
    },
};

static const BasicSurfaceFormatInfo kelvin_surface_zeta_format_map[] = {
    [NV097_SET_SURFACE_FORMAT_ZETA_Z16] = { 2 },
    [NV097_SET_SURFACE_FORMAT_ZETA_Z24S8] = { 4 },
};

static const SurfaceFormatInfo zeta_d16 = {
    2,
    VK_FORMAT_D16_UNORM,
    VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT,
    VK_IMAGE_ASPECT_DEPTH_BIT,
};

static const SurfaceFormatInfo zeta_d32_sfloat_s8_uint = {
    8,
    VK_FORMAT_D32_SFLOAT_S8_UINT,
    VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT,
    VK_IMAGE_ASPECT_DEPTH_BIT | VK_IMAGE_ASPECT_STENCIL_BIT,
};

static const SurfaceFormatInfo zeta_d24_unorm_s8_uint = {
    4,
    VK_FORMAT_D24_UNORM_S8_UINT,
    VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT,
    VK_IMAGE_ASPECT_DEPTH_BIT | VK_IMAGE_ASPECT_STENCIL_BIT,
};

#endif
