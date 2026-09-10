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
 * SZ_R6G5B5 converts to signed bytes and lands in an SNORM image here, which
 * the fragment shader must then NOT remap again. See glsl/psh.c snorm_tex and
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
        VK_FORMAT_R8G8B8_SNORM, // Converted
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
     * track the ramp exactly. */
    [NV097_SET_TEXTURE_FORMAT_COLOR_SZ_Y16] = {
        VK_FORMAT_R16_UNORM,
        { VK_COMPONENT_SWIZZLE_ONE, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_R, VK_COMPONENT_SWIZZLE_ONE }
    },
    /* Two 16-bit channels holding R and B.  Component order mirrors SZ_R8B8,
     * which is the same channel layout at 8 bits. */
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
} SurfaceFormatInfo;

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
        // FIXME: Force alpha to zero
        2,
        VK_FORMAT_A1R5G5B5_UNORM_PACK16,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
    },
    /* The _O1 twin of the entry above: same layout, the X bit reads back as
     * one instead of zero. Was `unimplemented color surface format 0x2` and
     * abort(), five tests into Blend surface (issue #28). */
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X1R5G5B5_O1R5G5B5] =
    {
        // FIXME: Force alpha to one
        2,
        VK_FORMAT_A1R5G5B5_UNORM_PACK16,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
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
        // FIXME: Force alpha to zero
        4,
        VK_FORMAT_B8G8R8A8_UNORM,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
    },
    /* The _O8 twin of X8R8G8B8_Z8R8G8B8: the X byte reads back as ones instead
     * of zeros. Was `unimplemented color surface format 0x5` and abort(), six
     * tests into Blend surface (issue #28). With this every colour surface
     * format the hardware defines, 0x1 to 0xA, has an entry. */
    [NV097_SET_SURFACE_FORMAT_COLOR_LE_X8R8G8B8_O8R8G8B8] =
    {
        // FIXME: Force alpha to one
        4,
        VK_FORMAT_B8G8R8A8_UNORM,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT,
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

// FIXME: Actually support stored float format

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
