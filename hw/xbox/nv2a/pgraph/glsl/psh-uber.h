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

/*
 * #569 P6, a spike: a Dolphin-style ubershader for the pixel combiners.
 *
 * One fragment shader per FAMILY interprets the eight general combiner stages
 * and the final combiner from a uniform (`ubComb`), so every PshState that
 * differs only in its combiner registers shares one module and one pipeline.
 * Everything that is not the combiners -- the texture shader, fog, alpha test,
 * clipping, depth output, the #43/#59/#285 epilogue -- is psh.c's own output
 * for the family, unmodified: the generator asks psh.c for the family's
 * template shader and replaces only its combiner block (see psh-uber.c).
 *
 * A family is a PshState with the combiner fields (combiner_control,
 * rgb/alpha inputs and outputs, final_inputs_0/1) replaced by one fixed
 * template program. Nothing else in psh.c reads those fields (checked by
 * reading every use in psh_convert; the host differ in
 * docs/lanes/uberspike569 checks it by diffing generated text), so the family
 * template's non-combiner text is the specialised shader's.
 *
 * DEBUG ONLY, DEFAULT OFF. HAKUX_PSH_UBER=1 in the environment (the Android
 * env_vars pref) forces the ubershader for every draw it covers. With the
 * switch off nothing here is reached: no key carries the uber flag, and
 * psh.c's output is unchanged.
 */

#ifndef HW_XBOX_NV2A_PGRAPH_GLSL_PSH_UBER_H
#define HW_XBOX_NV2A_PGRAPH_GLSL_PSH_UBER_H

#include "psh.h"

/*
 * The build's default for the switch, which the environment overrides either
 * way. 0 in every shipped build. The pgraph arms compare refs rather than
 * environments, so the E leg's B ref is a commit that sets this to 1; see
 * docs/lanes/uberspike569/NOTES.md.
 */
#ifndef HAKUX_PSH_UBER_DEFAULT
#define HAKUX_PSH_UBER_DEFAULT 0
#endif

/* The uniform the interpreter reads: 9 uvec4, std140. Element i < 8 is stage
 * i's (rgb_inputs, rgb_outputs, alpha_inputs, alpha_outputs); element 8 is
 * (final_inputs_0, final_inputs_1, combiner_control, 0). */
#define PSH_UBER_COMB_NAME "ubComb"
#define PSH_UBER_COMB_VEC4S 9

/* Whether the switch is on: read once, from HAKUX_PSH_UBER, else the build
 * default. Logs its reading once. */
bool pgraph_glsl_psh_uber_enabled(void);

/*
 * Whether the ubershader can draw this state exactly as psh.c would. The one
 * refusal: a disabled final combiner (both final-input words zero), where
 * psh.c never writes fragColor and the output is undefined, so there is
 * nothing to match.
 */
bool pgraph_glsl_psh_uber_covers(const PshState *state);

/* The family of a covered state: the state with its combiner fields replaced
 * by the template. */
void pgraph_glsl_psh_uber_family(const PshState *state, PshState *family);

/* Whether a state is a family (its combiner fields are the template). */
bool pgraph_glsl_psh_uber_is_family(const PshState *state);

/*
 * The live combiner registers as the interpreter's uniform, 9 x uvec4, read
 * the way pgraph_glsl_set_psh_state() reads them. From the registers at
 * staging time and not from the binding, whose state is the family's.
 */
void pgraph_glsl_psh_uber_comb_values(PGRAPHState *pg,
                                      uint32_t out[PSH_UBER_COMB_VEC4S * 4]);

/*
 * The family's ubershader. NULL if psh.c's template output does not have the
 * shape the splice expects, which is a generator change psh-uber.c has not
 * caught up with; the caller then keeps the specialised path.
 */
MString *pgraph_glsl_gen_psh_uber(const PshState *family,
                                  GenPshGlslOptions opts);

#endif
