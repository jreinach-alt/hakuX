/*
 * Geforce NV2A PGRAPH GLSL Shader Generator: the uber vertex stage
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
 * #569: a Dolphin-style uber vertex shader.
 *
 * One vertex shader per FAMILY draws any vertex state of that family: the
 * fixed-function transform, texgen, skinning and lighting, or a vertex
 * program interpreted slot by slot, all read from a uniform (`ubVsh`,
 * appended to VshUniforms). Under graphics pipeline libraries a pre-raster
 * library built from it once can be fast-linked for a vertex state it has
 * never seen, so a pipeline miss draws this frame instead of waiting for a
 * specialised pre-raster compile (docs/lanes/uberspike569/BUILD.md).
 *
 * A family keeps only what the shader text must declare or bakes in:
 *   compressed_attrs      an `int` input per compressed attribute
 *   uniform_attrs != 0    whether VshUniforms carries inlineValue, which
 *                         moves no member but is part of the block
 *                         (normalised to 0 or 1)
 *   smooth_shading, noperspective   the output qualifiers
 *   surface_scale_factor, aa_offset_x   constants the text carries
 *   programmable.program_length   1 if the program writes its constant
 *                         registers (a private copy of c), else 0
 * and everything else is zero.
 *
 * EXACTNESS. The body replays the specialised generators' statements
 * (vsh.c, vsh-ff.c, vsh-prog.c) with run-time selects in place of
 * generation-time ones, through the same helper functions, so that each
 * value is computed by the same expression. docs/lanes/uberspike569/host
 * checks it by running both shaders on the same inputs and comparing every
 * output bit for bit.
 *
 * DEBUG ONLY, DEFAULT OFF: reached only under HAKUX_UBER_VS (vk/shaders.c).
 */

#ifndef HW_XBOX_NV2A_PGRAPH_GLSL_VSH_UBER_H
#define HW_XBOX_NV2A_PGRAPH_GLSL_VSH_UBER_H

#include "vsh.h"

/* The uniform the uber vertex stage reads, std140 uvec4s:
 *   [0] flags, uniform | swizzle attrs << 16, foggen | skin count << 8 |
 *       texture matrix enables << 16, program length
 *   [1] light count, light index list (4 bits each), light types by index
 *       (2 bits each), colour-material sources (front 0-7, back 8-15)
 *   [2] point size constant (float bits), texgen stages 0-1, 2-3 (3 bits a
 *       component, 16 bits a stage), texgen trip count
 *   [3..] the program's tokens */
#define VSH_UBER_NAME "ubVsh"
#define VSH_UBER_PROG_BASE 3
#define VSH_UBER_VEC4S (VSH_UBER_PROG_BASE + NV2A_MAX_TRANSFORM_PROGRAM_LENGTH)

enum {
    VSH_UBER_F_FIXED_FUNCTION = 1 << 0,
    VSH_UBER_F_LIGHTING = 1 << 1,
    VSH_UBER_F_FOG = 1 << 2,
    VSH_UBER_F_SPECULAR = 1 << 3,
    VSH_UBER_F_SEPARATE_SPECULAR = 1 << 4,
    VSH_UBER_F_IGNORE_SPECULAR_ALPHA = 1 << 5,
    VSH_UBER_F_TWO_SIDE = 1 << 6,
    VSH_UBER_F_POINT_PARAMS = 1 << 7,
    VSH_UBER_F_NORMALIZE = 1 << 8,
    VSH_UBER_F_LOCAL_EYE = 1 << 9,
    VSH_UBER_F_FOG_CARRIED = 1 << 10,
    VSH_UBER_F_SKIN_MIX = 1 << 11,
};

/* Whether the uber stage draws this state exactly as the specialised
 * generator would. It refuses what the specialised generator cannot
 * compile or asserts on (an output register it has no name for, an ARL
 * routed to an output, a register past R12, a texgen mode on a component
 * the mode has no value for, a colour-material source past SPECULAR), and
 * a compressed attribute that is also uniform or swizzled. */
bool pgraph_glsl_vsh_uber_covers(const VshState *state);

/* The family of a covered state (see above). */
void pgraph_glsl_vsh_uber_family(const VshState *state, VshState *family);

/* The live state as the uber stage's uniform. vulkan selects the carried fog
 * coordinate rule the specialised Vulkan shader applies. */
void pgraph_glsl_vsh_uber_values(const VshState *state, bool vulkan,
                                 uint32_t out[VSH_UBER_VEC4S * 4]);

/* The family's uber vertex shader. */
MString *pgraph_glsl_gen_vsh_uber(const VshState *family,
                                  GenVshGlslOptions opts);

#endif
