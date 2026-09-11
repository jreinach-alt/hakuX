/*
 * Geforce NV2A PGRAPH GLSL Shader Generator
 *
 * Copyright (c) 2024-2025 Matt Borgerson
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

#include "common.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"

#define DECL_UNIFORM_ELEMENT_NAME(type) #type,
const char *uniform_element_type_to_str[] = {
    UNIFORM_ELEMENT_TYPE_X(DECL_UNIFORM_ELEMENT_NAME)
};

MString *pgraph_glsl_get_vtx_header(MString *out, bool location, bool smooth,
                                    bool noperspective, bool in, bool prefix,
                                    bool array)
{
    /*
     * SET_CONTROL0 can turn texture perspective off, and the hardware then
     * interpolates colours and texture coordinates linearly in screen
     * space (Texture_perspective: tex_*_pers_n).  GLSL's noperspective is
     * exactly that; only the Vulkan path gets it, GLES would need
     * GL_NV_shader_noperspective_interpolation.
     */
    const char *smooth_s = (noperspective && location) ? "noperspective " : "";
    const char *flat_s = "flat ";
    const char *qualifier_s = smooth ? smooth_s : flat_s;
    const char *in_out_s = in ? "in" : "out";
    const char *float_s = "float";
    const char *vec4_s = "vec4";
    const char *prefix_s = prefix ? "v_" : "";
    const char *suffix_s = array ? "[]" : "";
    const struct {
        const char *qualifier, *type, *name;
    } attr[] = {
        { qualifier_s, vec4_s,  "vtxD0"  },
        { qualifier_s, vec4_s,  "vtxD1"  },
        { qualifier_s, vec4_s,  "vtxB0"  },
        { qualifier_s, vec4_s,  "vtxB1"  },
        { smooth_s,    float_s, "vtxFog" },
        { flat_s,      float_s, "vtxFogSpecial" },
        { smooth_s,    vec4_s,  "vtxT0"  },
        { smooth_s,    vec4_s,  "vtxT1"  },
        { smooth_s,    vec4_s,  "vtxT2"  },
        { smooth_s,    vec4_s,  "vtxT3"  },
        { flat_s,      vec4_s,  "vtxPos0" },
        { flat_s,      vec4_s,  "vtxPos1" },
        { flat_s,      vec4_s,  "vtxPos2" },
        { flat_s,      float_s, "triMZ"  },
        { smooth_s,    float_s, "vtxPointSize" },
    };

    for (int i = 0; i < ARRAY_SIZE(attr); i++) {
        if (location) {
            mstring_append_fmt(out, "layout(location = %d) ", i);
        }
        mstring_append_fmt(out, "%s%s %s %s%s%s;\n", attr[i].qualifier,
                           in_out_s, attr[i].type, prefix_s, attr[i].name,
                           suffix_s);
    }

    return out;
}

void pgraph_glsl_append_version(MString *out, bool vulkan, bool gles,
                                int gles_version)
{
    if (vulkan) {
        mstring_append(out, "#version 450\n\n");
        return;
    }

    if (gles) {
        int version = gles_version ? gles_version : 300;
        mstring_append_fmt(out, "#version %d es\n\n", version);
        mstring_append(out,
                       "precision highp float;\n"
                       "precision highp int;\n"
                       "precision highp sampler2D;\n"
                       "precision highp sampler3D;\n"
                       "precision highp samplerCube;\n"
                       "precision highp usampler2D;\n"
                       "\n");
        return;
    }

    mstring_append(out, "#version 400\n\n");
}

void pgraph_glsl_set_clip_range_uniform_value(PGRAPHState *pg, float clipRange[4])
{
    float zmax;
    switch (pg->surface_shape.zeta_format) {
    case NV097_SET_SURFACE_FORMAT_ZETA_Z16:
        zmax = pg->surface_shape.z_format ? f16_max : (float)0xFFFF;
        break;
    case NV097_SET_SURFACE_FORMAT_ZETA_Z24S8:
        /*
         * clipRange.y is what the vertex shaders divide oPos.z by, so for the
         * fixed point format it is the scale the depth word is stored at, and
         * it has to agree with the host image -- 2^24 for a float one. See
         * PGRAPHState::zeta_stored_as_float; dividing by 0xFFFFFF and reading
         * back at 2^24 is worth a whole unit of depth over most of the range.
         */
        zmax = pg->surface_shape.z_format ?
                   f24_max :
                   (float)(pg->zeta_stored_as_float ? 0x1000000 : 0xFFFFFF);
        break;
    default:
        assert(0);
    }

    uint32_t zclip_min = pgraph_reg_r(pg, NV_PGRAPH_ZCLIPMIN);
    uint32_t zclip_max = pgraph_reg_r(pg, NV_PGRAPH_ZCLIPMAX);

    clipRange[0] = 0;
    clipRange[1] = zmax;
    clipRange[2] = *(float *)&zclip_min;
    clipRange[3] = *(float *)&zclip_max;
}
