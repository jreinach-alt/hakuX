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

#ifndef HW_XBOX_NV2A_PGRAPH_GLSL_VSH_FF_H
#define HW_XBOX_NV2A_PGRAPH_GLSL_VSH_FF_H

#include "qemu/mstring.h"
#include "vsh.h"

void pgraph_glsl_gen_vsh_ff(const VshState *state, MString *header,
                            MString *body);

void pgraph_glsl_append_vsh_prog_lighting(const VshState *state,
                                          MString *header, MString *body);

/* The header pgraph_glsl_gen_vsh_ff() appends: the attribute and register
 * names, the fixed-function z helpers (ff*) and the lighting unit's
 * arithmetic (lt*). For #569's uber vertex stage (glsl/vsh-uber.c). */
void pgraph_glsl_append_vsh_ff_header(MString *header);

#endif
