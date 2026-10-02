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

#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#include "vsh-uber.h"
#include "vsh-ff.h"
#include "vsh-prog.h"

/*
 * See vsh-uber.h. Every block below names the specialised generator code it
 * replays; a change there needs the same change here, and the host check in
 * docs/lanes/uberspike569/host (vshuber) is what catches a miss.
 */

/* vsh-uber.h's flags as literals, for the GLSL text below */
#define VSH_UBER_F_LIGHTING_V 2
#define VSH_UBER_F_FOG_V 4
#define VSH_UBER_F_SPECULAR_V 8
#define VSH_UBER_F_SEPARATE_SPECULAR_V 16
#define VSH_UBER_F_IGNORE_SPECULAR_ALPHA_V 32
#define VSH_UBER_F_TWO_SIDE_V 64
#define VSH_UBER_F_POINT_PARAMS_V 128
#define VSH_UBER_F_NORMALIZE_V 256
#define VSH_UBER_F_LOCAL_EYE_V 512
#define VSH_UBER_F_FOG_CARRIED_V 1024
#define VSH_UBER_F_SKIN_MIX_V 2048
QEMU_BUILD_BUG_ON(VSH_UBER_F_LIGHTING_V != VSH_UBER_F_LIGHTING);
QEMU_BUILD_BUG_ON(VSH_UBER_F_FOG_V != VSH_UBER_F_FOG);
QEMU_BUILD_BUG_ON(VSH_UBER_F_SPECULAR_V != VSH_UBER_F_SPECULAR);
QEMU_BUILD_BUG_ON(VSH_UBER_F_SEPARATE_SPECULAR_V !=
                  VSH_UBER_F_SEPARATE_SPECULAR);
QEMU_BUILD_BUG_ON(VSH_UBER_F_IGNORE_SPECULAR_ALPHA_V !=
                  VSH_UBER_F_IGNORE_SPECULAR_ALPHA);
QEMU_BUILD_BUG_ON(VSH_UBER_F_TWO_SIDE_V != VSH_UBER_F_TWO_SIDE);
QEMU_BUILD_BUG_ON(VSH_UBER_F_POINT_PARAMS_V != VSH_UBER_F_POINT_PARAMS);
QEMU_BUILD_BUG_ON(VSH_UBER_F_NORMALIZE_V != VSH_UBER_F_NORMALIZE);
QEMU_BUILD_BUG_ON(VSH_UBER_F_LOCAL_EYE_V != VSH_UBER_F_LOCAL_EYE);
QEMU_BUILD_BUG_ON(VSH_UBER_F_FOG_CARRIED_V != VSH_UBER_F_FOG_CARRIED);
QEMU_BUILD_BUG_ON(VSH_UBER_F_SKIN_MIX_V != VSH_UBER_F_SKIN_MIX);

/* The program walk the specialised translator does (vsh-prog.c decode_token),
 * refusing what it would not compile. */
static int uber_c_index(uint8_t c_reg)
{
    return ((((c_reg >> 5) & 7) - 3) * 32) + (c_reg & 31) + VSH_D3DSCM_CORRECTION;
}

static bool uber_input_ok(const uint32_t *t, VshFieldName mux_field,
                          int reg)
{
    switch (vsh_get_field(t, mux_field)) {
    case PARAM_R:
        return reg <= 12;
    case PARAM_V:
        return true;
    case PARAM_C:
        /* A constant index past the file is a compile error in the
         * specialised text; an A0-relative one is resolved at run time. */
        if (vsh_get_field(t, FLD_A0X)) {
            return true;
        }
        return uber_c_index(vsh_get_field(t, FLD_CONST)) <
               NV2A_VERTEXSHADER_CONSTANTS;
    default:
        return false;
    }
}

static bool uber_program_ok(const ProgrammableVshState *prog)
{
    static const bool mac_a[14] = { 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 };
    static const bool mac_b[14] = { 0, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0 };
    static const bool mac_c[14] = { 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0 };

    for (int slot = 0; slot < prog->program_length; slot++) {
        const uint32_t *t = prog->program_data[slot];
        int mac = vsh_get_field(t, FLD_MAC);
        int ilu = vsh_get_field(t, FLD_ILU);
        if (mac > MAC_ARL) {
            return false;
        }
        if (mac != MAC_NOP || ilu != ILU_NOP) {
            bool paired = mac != MAC_NOP && ilu != ILU_NOP;
            int c_reg = (vsh_get_field(t, FLD_C_R_HIGH) << 2) |
                        vsh_get_field(t, FLD_C_R_LOW);
            if ((mac_c[mac] || ilu != ILU_NOP) &&
                !uber_input_ok(t, FLD_C_MUX, c_reg)) {
                return false;
            }
            if (mac_a[mac] &&
                !uber_input_ok(t, FLD_A_MUX, vsh_get_field(t, FLD_A_R))) {
                return false;
            }
            if (mac_b[mac] &&
                !uber_input_ok(t, FLD_B_MUX, vsh_get_field(t, FLD_B_R))) {
                return false;
            }
            int out_r = vsh_get_field(t, FLD_OUT_R);
            int mac_mask = vsh_get_field(t, FLD_OUT_MAC_MASK);
            if (paired && out_r == 1) {
                mac_mask = 0;
            }
            if (mac != MAC_NOP && mac != MAC_ARL && mac_mask && out_r > 12) {
                return false;
            }
            if (!paired && ilu != ILU_NOP &&
                vsh_get_field(t, FLD_OUT_ILU_MASK) && out_r > 12) {
                return false;
            }
            bool mac_out = mac != MAC_NOP &&
                           vsh_get_field(t, FLD_OUT_MUX) == OMUX_MAC;
            bool ilu_out = ilu != ILU_NOP &&
                           vsh_get_field(t, FLD_OUT_MUX) == OMUX_ILU;
            if ((mac_out || ilu_out) && vsh_get_field(t, FLD_OUT_O_MASK)) {
                if (mac_out && mac == MAC_ARL) {
                    return false;
                }
                if (vsh_get_field(t, FLD_OUT_ORB) == OUTPUT_O) {
                    int o = vsh_get_field(t, FLD_OUT_ADDRESS) & 0xF;
                    if (o == 1 || o == 2 || o >= 13) {
                        return false;
                    }
                }
            }
        }
        if (vsh_get_field(t, FLD_FINAL)) {
            return true;
        }
    }
    return false; /* no FINAL: the specialised translator asserts */
}

static bool uber_writes_constants(const ProgrammableVshState *prog)
{
    for (int slot = 0; slot < prog->program_length; slot++) {
        const uint32_t *t = prog->program_data[slot];
        if (pgraph_glsl_vsh_token_constant_write(t) >= 0) {
            return true;
        }
        if (vsh_get_field(t, FLD_FINAL)) {
            break;
        }
    }
    return false;
}

static bool uber_sources_ok(const VshState *s)
{
    const enum MaterialColorSource src[8] = {
        s->emission_src, s->ambient_src, s->diffuse_src, s->specular_src,
        s->back_emission_src, s->back_ambient_src, s->back_diffuse_src,
        s->back_specular_src,
    };
    for (int i = 0; i < 8; i++) {
        if (src[i] > MATERIAL_COLOR_SRC_SPECULAR) {
            return false;
        }
    }
    return true;
}

bool pgraph_glsl_vsh_uber_covers(const VshState *s)
{
    if (s->compressed_attrs & (s->uniform_attrs | s->swizzle_attrs)) {
        return false;
    }
    if (s->lighting && !uber_sources_ok(s)) {
        return false;
    }
    if (!s->is_fixed_function) {
        return uber_program_ok(&s->programmable);
    }
    if (s->fixed_function.skinning > SKINNING_4WEIGHTS4MATRICES) {
        return false;
    }
    if (s->fog_enable && s->foggen > FOGGEN_FOG_X) {
        return false;
    }
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 4; j++) {
            enum VshTexgen g = s->fixed_function.texgen[i][j];
            if (g > TEXGEN_REFLECTION_MAP ||
                (g == TEXGEN_SPHERE_MAP && j >= 2) ||
                ((g == TEXGEN_REFLECTION_MAP || g == TEXGEN_NORMAL_MAP) &&
                 j >= 3)) {
                return false;
            }
        }
    }
    return true;
}

void pgraph_glsl_vsh_uber_family(const VshState *s, VshState *f)
{
    memset(f, 0, sizeof(*f));
    f->surface_scale_factor = s->surface_scale_factor;
    f->compressed_attrs = s->compressed_attrs;
    f->uniform_attrs = s->uniform_attrs ? 1 : 0;
    f->smooth_shading = s->smooth_shading;
    f->noperspective = s->noperspective;
    f->aa_offset_x = s->aa_offset_x;
    f->programmable.program_length =
        !s->is_fixed_function && uber_writes_constants(&s->programmable);
}

/* The value a "%f" literal in the specialised text parses to. */
static float uber_printed_float(float v)
{
    char buf[64];
    snprintf(buf, sizeof(buf), "%f", v);
    return (float)strtod(buf, NULL);
}

void pgraph_glsl_vsh_uber_values(const VshState *s, bool vulkan,
                                 uint32_t out[VSH_UBER_VEC4S * 4])
{
    memset(out, 0, VSH_UBER_VEC4S * 4 * sizeof(uint32_t));

    uint32_t flags = 0;
    flags |= s->is_fixed_function ? VSH_UBER_F_FIXED_FUNCTION : 0;
    flags |= s->lighting ? VSH_UBER_F_LIGHTING : 0;
    flags |= s->fog_enable ? VSH_UBER_F_FOG : 0;
    flags |= s->specular_enable ? VSH_UBER_F_SPECULAR : 0;
    flags |= s->separate_specular ? VSH_UBER_F_SEPARATE_SPECULAR : 0;
    flags |= s->ignore_specular_alpha ? VSH_UBER_F_IGNORE_SPECULAR_ALPHA : 0;
    flags |= s->two_side_light ? VSH_UBER_F_TWO_SIDE : 0;
    flags |= s->point_params_enable ? VSH_UBER_F_POINT_PARAMS : 0;
    flags |= s->normalization ? VSH_UBER_F_NORMALIZE : 0;
    flags |= s->local_eye ? VSH_UBER_F_LOCAL_EYE : 0;

    /* vsh.c's fog block under a program: the carried coordinate for RADIAL
     * (#41), and on Vulkan for a program that never writes oFog (#42) */
    if (!s->is_fixed_function && s->fog_enable &&
        (pgraph_glsl_vsh_carries_ff_radial_fog(s) ||
         (vulkan &&
          pgraph_glsl_vsh_fog_write(s).kind == VSH_FOG_WRITE_NONE))) {
        flags |= VSH_UBER_F_FOG_CARRIED;
    }

    unsigned int skin_count = 0;
    if (s->is_fixed_function) {
        /* vsh-ff.c's skinning table */
        static const struct { bool mix; unsigned int count; } skin[] = {
            [SKINNING_OFF] = { false, 0 },
            [SKINNING_1WEIGHTS] = { true, 2 },
            [SKINNING_2WEIGHTS2MATRICES] = { false, 2 },
            [SKINNING_2WEIGHTS] = { true, 3 },
            [SKINNING_3WEIGHTS3MATRICES] = { false, 3 },
            [SKINNING_3WEIGHTS] = { true, 4 },
            [SKINNING_4WEIGHTS4MATRICES] = { false, 4 },
        };
        skin_count = skin[s->fixed_function.skinning].count;
        flags |= skin[s->fixed_function.skinning].mix ? VSH_UBER_F_SKIN_MIX : 0;
    }

    uint32_t texmat = 0;
    uint32_t texgen[2] = { 0, 0 };
    if (s->is_fixed_function) {
        for (int i = 0; i < 4; i++) {
            texmat |= s->fixed_function.texture_matrix_enable[i] ? 1u << i : 0;
            for (int j = 0; j < 4; j++) {
                texgen[i >> 1] |= (uint32_t)s->fixed_function.texgen[i][j]
                                  << (16 * (i & 1) + 3 * j);
            }
        }
    }

    out[0] = flags;
    out[1] = s->uniform_attrs | (uint32_t)s->swizzle_attrs << 16;
    out[2] = (s->fog_enable ? (uint32_t)s->foggen : 0) | skin_count << 8 |
             texmat << 16;
    out[3] = s->is_fixed_function ? 0 : s->programmable.program_length;

    uint32_t num_lights = 0, list = 0, types = 0, srcs = 0;
    if (s->lighting) {
        for (int i = 0; i < NV2A_MAX_LIGHTS; i++) {
            types |= (uint32_t)s->light[i] << (2 * i);
            if (s->light[i] != LIGHT_OFF) {
                list |= (uint32_t)i << (4 * num_lights++);
            }
        }
        srcs = s->emission_src | s->ambient_src << 2 | s->diffuse_src << 4 |
               s->specular_src << 6 | s->back_emission_src << 8 |
               s->back_ambient_src << 10 | s->back_diffuse_src << 12 |
               s->back_specular_src << 14;
    }
    out[4] = num_lights;
    out[5] = list;
    out[6] = types;
    out[7] = srcs;

    /* The point size the specialised text prints, for each path */
    float pt = s->is_fixed_function ? MAX(1.f, s->point_size) :
               (s->point_size <= 0.f ? 1.f : s->point_size);
    float ptv = uber_printed_float(pt);
    memcpy(&out[8], &ptv, sizeof(ptv));
    out[9] = texgen[0];
    out[10] = texgen[1];
    out[11] = 16; /* texgen trip count: uniform, so it is not unrolled */

    if (!s->is_fixed_function) {
        memcpy(&out[VSH_UBER_PROG_BASE * 4], s->programmable.program_data,
               s->programmable.program_length * VSH_TOKEN_SIZE *
                   sizeof(uint32_t));
    }
}

/*
 * The program interpreter: vsh-prog.c decode_token, one slot at a time, in
 * its statement order. Each statement re-reads its inputs, as the text does,
 * so an unpaired unit's constant write is visible to its own register write.
 */
static const char uber_prog_glsl[] =
"vec4 ubR[12];\n"
"vec4 ubO[16];\n"
"vec4 ubV[16];\n"
"\n"
"vec4 ubSwz(vec4 v, uint s) {\n"
"  return vec4(v[(s >> 6) & 3u], v[(s >> 4) & 3u], v[(s >> 2) & 3u], v[s & 3u]);\n"
"}\n"
"vec4 ubReadR(uint r) { return r == 12u ? oPos : ubR[min(r, 11u)]; }\n"
"int ubCIndex(uvec4 t) {\n"
"  uint cf = bitfieldExtract(t.y, 13, 8);\n"
"  int i = (int((cf >> 5) & 7u) - 3) * 32 + int(cf & 31u) + 96;\n"
"  if (bitfieldExtract(t.w, 1, 1) != 0u) { i += A0; }\n"
"  return clamp(i, 0, 191);\n"
"}\n"
"vec4 ubFetch(uvec4 t, uint mux, uint reg, uint neg, uint swz) {\n"
"  vec4 v;\n"
"  if (mux == 1u) { v = ubReadR(reg); }\n"
"  else if (mux == 2u) { v = ubV[bitfieldExtract(t.y, 9, 4)]; }\n"
"  else { v = UB_CFILE[ubCIndex(t)]; }\n"
"  v = ubSwz(v, swz);\n"
"  return neg != 0u ? -v : v;\n"
"}\n"
"vec4 ubFetchA(uvec4 t) {\n"
"  return ubFetch(t, bitfieldExtract(t.z, 26, 2), bitfieldExtract(t.z, 28, 4),\n"
"                 bitfieldExtract(t.y, 8, 1), bitfieldExtract(t.y, 0, 8));\n"
"}\n"
"vec4 ubFetchB(uvec4 t) {\n"
"  return ubFetch(t, bitfieldExtract(t.z, 11, 2), bitfieldExtract(t.z, 13, 4),\n"
"                 bitfieldExtract(t.z, 25, 1), bitfieldExtract(t.z, 17, 8));\n"
"}\n"
/* RCP, RCC, RSQ, EXP and LOG read input C's x swizzle in every lane */
"vec4 ubFetchC(uvec4 t) {\n"
"  uint swz = bitfieldExtract(t.z, 2, 8);\n"
"  uint ilu = bitfieldExtract(t.y, 25, 3);\n"
"  if (ilu >= 2u && ilu <= 6u) { uint x = (swz >> 6) & 3u; swz = x << 6 | x << 4 | x << 2 | x; }\n"
"  return ubFetch(t, bitfieldExtract(t.w, 28, 2),\n"
"                 bitfieldExtract(t.z, 0, 2) << 2 | bitfieldExtract(t.w, 30, 2),\n"
"                 bitfieldExtract(t.z, 10, 1), swz);\n"
"}\n"
"vec4 ubMac(uvec4 t, uint mac) {\n"
"  vec4 a = ubFetchA(t);\n"
"  vec4 b = ubFetchB(t);\n"
"  vec4 cc = ubFetchC(t);\n"
"  switch (mac) {\n"
"  case 1u: return _MOV(a);\n"
"  case 2u: return _MUL(a, b);\n"
"  case 3u: return _ADD(a, cc);\n"
"  case 4u: return _MAD(a, b, cc);\n"
"  case 5u: return _DP3(a, b);\n"
"  case 6u: return _DPH(a, b);\n"
"  case 7u: return _DP4(a, b);\n"
"  case 8u: return _DST(a, b);\n"
"  case 9u: return _MIN(a, b);\n"
"  case 10u: return _MAX(a, b);\n"
"  case 11u: return _SLT(a, b);\n"
"  case 12u: return _SGE(a, b);\n"
"  }\n"
"  return vec4(0.0);\n"
"}\n"
"vec4 ubIlu(uvec4 t, uint ilu) {\n"
"  vec4 cc = ubFetchC(t);\n"
"  switch (ilu) {\n"
"  case 1u: return _MOV(cc);\n"
"  case 2u: return _RCP(cc.x);\n"
"  case 3u: return _RCC(cc.x);\n"
"  case 4u: return _RSQ(cc.x);\n"
"  case 5u: return _EXP(cc.x);\n"
"  case 6u: return _LOG(cc.x);\n"
"  case 7u: return _LIT(cc);\n"
"  }\n"
"  return vec4(0.0);\n"
"}\n"
/* mask_str's bits: x 8, y 4, z 2, w 1 */
"vec4 ubMask(vec4 d, vec4 v, uint m) {\n"
"  return mix(d, v, bvec4((m & 8u) != 0u, (m & 4u) != 0u, (m & 2u) != 0u, (m & 1u) != 0u));\n"
"}\n"
/* fog_mask_str: the masked components land from x up */
"uint ubFogMask(uint m) {\n"
"  uint n = uint(bitCount(m));\n"
"  return n == 0u ? 0u : (n == 1u ? 8u : (n == 2u ? 12u : (n == 3u ? 14u : 15u)));\n"
"}\n"
"void ubWriteR(uint r, vec4 v, uint m) {\n"
"  if (r == 12u) { oPos = ubMask(oPos, v, m); } else { ubR[r] = ubMask(ubR[r], v, m); }\n"
"}\n"
"void ubWriteO(uint o, vec4 v, uint m) {\n"
"  if (o == 0u) { oPos = ubMask(oPos, v, m); }\n"
"  else { ubO[o] = ubMask(ubO[o], v, o == 5u ? ubFogMask(m) : m); }\n"
"}\n"
"void ubSlot(uvec4 t) {\n"
"  uint mac = bitfieldExtract(t.y, 21, 4);\n"
"  uint ilu = bitfieldExtract(t.y, 25, 3);\n"
"  if (mac == 0u && ilu == 0u) { return; }\n"
"  bool paired = mac != 0u && ilu != 0u;\n"
"  uint outMux = bitfieldExtract(t.w, 2, 1);\n"
"  uint oMask = bitfieldExtract(t.w, 12, 4);\n"
"  uint orb = bitfieldExtract(t.w, 11, 1);\n"
"  uint oAddr = bitfieldExtract(t.w, 3, 8);\n"
"  uint outR = bitfieldExtract(t.w, 20, 4);\n"
"  uint macMask = bitfieldExtract(t.w, 24, 4);\n"
"  if (paired && outR == 1u) { macMask = 0u; }\n"
"  uint iluMask = bitfieldExtract(t.w, 16, 4);\n"
"  uint oposPend = 0u;\n"
"  int cTmpIdx = -1;\n"
"  int ci = (int((oAddr >> 5) & 7u) - 3) * 32 + int(oAddr & 31u) + 96;\n"
"  bool cOk = ci >= 0 && ci < 192;\n"
"  if (mac != 0u && outMux == 0u && oMask != 0u) {\n"
"    vec4 v = ubMac(t, mac);\n"
"    if (orb == 0u) {\n"
"      UB_CWRITE_MAC\n"
"    } else if ((oAddr & 15u) == 0u && (paired || macMask > 0u)) {\n"
"      _opos_tmp = ubMask(_opos_tmp, v, oMask);\n"
"      oposPend = oMask;\n"
"    } else {\n"
"      ubWriteO(oAddr & 15u, v, oMask);\n"
"    }\n"
"  }\n"
"  if (mac == 13u) {\n"
"    int addr = _ARL(ubFetchA(t).x);\n"
"    if (paired) { _temp_addr = addr; } else { A0 = addr; }\n"
"  } else if (mac != 0u && macMask > 0u) {\n"
"    vec4 v = ubMac(t, mac);\n"
"    if (paired) { _temp_vec = ubMask(_temp_vec, v, macMask); }\n"
"    else { ubWriteR(outR, v, macMask); }\n"
"  }\n"
"  if (ilu != 0u && outMux == 1u && oMask != 0u) {\n"
"    vec4 v = ubIlu(t, ilu);\n"
"    if (orb == 0u) {\n"
"      UB_CWRITE_ILU\n"
"    } else if ((oAddr & 15u) == 0u && iluMask > 0u) {\n"
"      _opos_tmp = ubMask(_opos_tmp, v, oMask);\n"
"      oposPend = oMask;\n"
"    } else {\n"
"      ubWriteO(oAddr & 15u, v, oMask);\n"
"    }\n"
"  }\n"
"  if (ilu != 0u && iluMask > 0u) {\n"
"    ubWriteR(paired ? 1u : outR, ubIlu(t, ilu), iluMask);\n"
"  }\n"
"  UB_CWRITE_SUFFIX\n"
"  if (paired) {\n"
"    if (mac == 13u) { A0 = _temp_addr; }\n"
"    else if (macMask > 0u) { ubWriteR(outR, _temp_vec, macMask); }\n"
"  }\n"
"  if (oposPend != 0u) { oPos = ubMask(oPos, _opos_tmp, oposPend); }\n"
"}\n"
"void ubProgram() {\n"
"  for (int i = 0; i < 12; i++) { ubR[i] = vec4(0.0); }\n"
"  for (int i = 0; i < 16; i++) { ubO[i] = vec4(0.0, 0.0, 0.0, 1.0); }\n"
"  uint n = ubVsh[0].w;\n"
"  for (uint pc = 0u; pc < n; pc++) {\n"
"    uvec4 t = ubVsh[" stringify(VSH_UBER_PROG_BASE) " + pc];\n"
"    ubSlot(t);\n"
"    if (bitfieldExtract(t.w, 0, 1) != 0u) { break; }\n"
"  }\n"
"  oD0 = ubO[3]; oD1 = ubO[4]; oFog = ubO[5]; oPts = ubO[6];\n"
"  oB0 = ubO[7]; oB1 = ubO[8];\n"
"  oT0 = ubO[9]; oT1 = ubO[10]; oT2 = ubO[11]; oT3 = ubO[12];\n"
/* vsh-prog.c's epilogue */
"  oPos.xy = roundScreenCoords(oPos.xy);\n"
"  oPos.w = clampAwayZeroInf(oPos.w);\n"
"  vtxPos = oPos;\n"
"  oPos.xy = (2.0 * oPos.xy - surfaceSize) / surfaceSize;\n"
"  oPos.z = oPos.z / clipRange.y;\n"
"  oPos.xyz *= oPos.w;\n"
"}\n";

/* A constant write, for a family whose programs write constants (c_rw). */
#define UBER_CWRITE_MAC                                              \
    "if (cOk) { if (paired) { _c_rw_tmp = ubMask(_c_rw_tmp, v, oMask); " \
    "cTmpIdx = ci; } else { c_rw[ci] = ubMask(c_rw[ci], v, oMask); } }"
#define UBER_CWRITE_ILU \
    "if (cOk) { c_rw[ci] = ubMask(c_rw[ci], v, oMask); }"
#define UBER_CWRITE_SUFFIX \
    "if (cTmpIdx >= 0) { c_rw[cTmpIdx] = ubMask(c_rw[cTmpIdx], _c_rw_tmp, oMask); }"

/*
 * The lighting unit, one face: vsh-ff.c append_lighting_constant and
 * append_lighting, with the side's registers and the light list read at run
 * time. The light loop's trip count is a uniform, so it stays one body.
 */
static const char uber_light_glsl[] =
"vec3 ubVc(uint src, vec4 ltD, vec4 ltS) { return src == 1u ? ltD.rgb : ltS.rgb; }\n"
"void ubTerm(inout vec4 o, uint src, vec3 term, vec4 ltD, vec4 ltS) {\n"
"  if (src != 0u) { o.xyz = ltVA(o.xyz, ltVM(term, ubVc(src, ltD, ltS))); }\n"
"  else { o.xyz = ltVA(o.xyz, term); }\n"
"}\n"
"void ubLightSide(bool back, vec3 nrm, inout vec4 dOut, inout vec4 sOut,\n"
"                 float diffA, float specA, vec4 ltD, vec4 ltS, vec4 tPos4,\n"
"                 bool fold) {\n"
"  uint srcs = (ubVsh[1].w >> (back ? 8 : 0)) & 0xFFu;\n"
"  uint esrc = srcs & 3u, asrc = (srcs >> 2) & 3u;\n"
"  uint dsrc = (srcs >> 4) & 3u, ssrc = (srcs >> 6) & 3u;\n"
"  float alpha = diffA;\n"
"  if (dsrc == 0u) { alpha = back ? material_alpha_back : material_alpha; }\n"
"  else if (dsrc == 2u) { alpha = specA; }\n"
"  vec3 cterm = back ? backSceneAmbientColor : sceneAmbientColor;\n"
"  bool scaledOn = false;\n"
"  vec3 scaled = vec3(0.0);\n"
"  if (asrc != 0u) {\n"
"    scaledOn = true; scaled = ubVc(asrc, ltD, ltS);\n"
"    if (esrc != 0u) { cterm = ubVc(esrc, ltD, ltS); }\n"
"  } else if (esrc != 0u) {\n"
"    scaledOn = true; scaled = ubVc(esrc, ltD, ltS);\n"
"  }\n"
"  dOut = vec4(cterm, alpha);\n"
"  if (scaledOn) {\n"
"    dOut.rgb = ltVA(dOut.rgb, ltVM(scaled, back ? backMaterialEmissionColor : materialEmissionColor));\n"
"  }\n"
"  sOut = vec4(0.0, 0.0, 0.0, specA);\n"
"  vec3 N = lt(nrm);\n"
"  bool localEye = (ubVsh[0].x & " stringify(VSH_UBER_F_LOCAL_EYE_V) "u) != 0u;\n"
"  vec3 ltEye;\n"
"  if (localEye) {\n"
"    ltEye = lt(normalize(eyePosition.xyz / eyePosition.w - tPos4.xyz / tPos4.w));\n"
"  } else {\n"
"    ltEye = lt(eyeDirection);\n"
"  }\n"
"  int nl = int(ubVsh[1].x);\n"
"  for (int k = 0; k < nl; k++) {\n"
"    int i = int((ubVsh[1].y >> (4 * k)) & 7u);\n"
"    uint type = (ubVsh[1].z >> (2 * i)) & 3u;\n"
"    vec3 lv;\n"
"    float ca;\n"
"    vec3 VP = vec3(0.0);\n"
"    if (type == 2u || type == 3u) {\n"
"      vec3 tPos = tPos4.xyz/tPos4.w;\n"
"      VP = lightLocalPosition[i] - tPos;\n"
"      float d = length(VP);\n"
"      if (!(d <= lightLocalRange(i))) { continue; }\n"
"      lv = lt(normalize(VP));\n"
"      ca = ltR(ltDp(vec3(1.0, lt(d), lt(d * d)),\n"
"                    lt(lightLocalAttenuation[i])));\n"
"    } else {\n"
"      lv = lt(lightInfiniteDirection[i]);\n"
"      ca = 1.0;\n"
"    }\n"
"    if (type == 3u) {\n"
"      vec4 spotDir = lightSpotDirection(i);\n"
"      vec3 spotK = lightSpotFalloff(i);\n"
"      float spotX = min(dot(spotDir.xyz, normalize(VP)) + spotDir.w, 1.0);\n"
"      float spotN = spotX + spotK.x;\n"
"      float spotD = spotX * spotK.y + spotK.z;\n"
"      float spotS = spotD == 0.0 ? FLOAT_MAX : spotN / spotD;\n"
"      ca = spotN <= 0.0 ? 0.0 : ltM(ca, lt(spotS));\n"
"    }\n"
"    bool halfPre = type == 1u && !localEye;\n"
"    vec3 k3 = lt(specularParams[(back ? 2 : 0) + (halfPre ? 0 : 1)]);\n"
"    bool zero = false;\n"
"    float cd = ltDp(N, lv);\n"
"    if (cd < 0.0) { zero = true; cd = 0.0; }\n"
"    cd = ltM(ca, cd);\n"
"    float t;\n"
"    float b;\n"
"    if (halfPre) {\n"
"      float s = ltDp(N, lt(lightInfiniteHalfVector[i]));\n"
"      t = ltsA(s, k3.x);\n"
"      if (t < 0.0) zero = true;\n"
"      b = ltsA(ltsM(s, k3.y), k3.z);\n"
"    } else {\n"
"      vec3 hi = ltVA(ltEye, lv);\n"
"      float hd = ltDp(hi, hi);\n"
"      float s = ltDp(N, hi);\n"
"      if (s < 0.0) zero = true;\n"
"      float ss = ltsM(s, s);\n"
"      t = ltsA(ss, ltsM(hd, k3.x));\n"
"      if (t < 0.0) zero = true;\n"
"      b = ltsA(ltsA(ltsM(ss, k3.y), 0.0), ltsM(hd, k3.z));\n"
"    }\n"
"    float cs = zero ? 0.0 : ltM(ca, ltsM(t, ltR(b)));\n"
"    vec3 lightAmbient = ltVM(vec3(ca), back ? lightBackAmbientColor(i) : lightAmbientColor(i));\n"
"    vec3 lightDiffuse = ltVM(vec3(cd), back ? lightBackDiffuseColor(i) : lightDiffuseColor(i));\n"
"    vec3 lightSpecular = ltVM(vec3(cs), back ? lightBackSpecularColor(i) : lightSpecularColor(i));\n"
"    ubTerm(dOut, asrc, lightAmbient, ltD, ltS);\n"
"    ubTerm(dOut, dsrc, lightDiffuse, ltD, ltS);\n"
"    if (fold) { ubTerm(dOut, ssrc, lightSpecular, ltD, ltS); }\n"
"    else { ubTerm(sOut, ssrc, lightSpecular, ltD, ltS); }\n"
"  }\n"
"}\n";

/* The lighting under a program: vsh-ff.c pgraph_glsl_append_vsh_prog_lighting */
static const char uber_prog_lighting_glsl[] =
"void ubProgLighting() {\n"
"  uint f = ubVsh[0].x;\n"
"  vec4 rV0 = v0, rV2 = v2, rV3 = v3, rV4 = v4;\n"
"  if (ringPhase >= 0.0) {\n"
"    int ringSlot = 6 * ((int(ringPhase) + ringVertexIndex) % 6);\n"
"    rV0 = ringInput[ringSlot + 0];\n"
"    rV2 = ringInput[ringSlot + 1];\n"
"    rV3 = ringInput[ringSlot + 2];\n"
"    rV4 = ringInput[ringSlot + 3];\n"
"  }\n"
"  {\n"
"  vec4 ltDiffuse = lt(rV3);\n"
"  vec4 ltSpecular = lt(rV4);\n"
"  vec4 tPosition = rV0 * modelViewMat0;\n"
"  vec3 tNormal = (vec4(rV2.xyz, 0.0) * invModelViewMat0).xyz;\n"
"  if ((f & " stringify(VSH_UBER_F_NORMALIZE_V) "u) != 0u) { tNormal = normalize(tNormal); }\n"
"  bool fold = (f & " stringify(VSH_UBER_F_SPECULAR_V) "u) == 0u ||\n"
"              (f & " stringify(VSH_UBER_F_SEPARATE_SPECULAR_V) "u) == 0u;\n"
"  ubLightSide(false, tNormal, oD0, oD1, v3.a, v4.a, ltDiffuse, ltSpecular, tPosition, fold);\n"
"  if ((f & " stringify(VSH_UBER_F_TWO_SIDE_V) "u) != 0u) {\n"
"    ubLightSide(true, -tNormal, oB0, oB1, v3.a, v4.a, ltDiffuse, ltSpecular, tPosition, fold);\n"
"  }\n"
"  }\n"
"  if ((f & " stringify(VSH_UBER_F_SPECULAR_V) "u) != 0u &&\n"
"      (f & " stringify(VSH_UBER_F_SEPARATE_SPECULAR_V) "u) == 0u) {\n"
"    oD1 = v4;\n"
"    if ((f & " stringify(VSH_UBER_F_TWO_SIDE_V) "u) != 0u) { oB1 = v8; }\n"
"  }\n"
"}\n";

/*
 * The fixed-function transform: vsh-ff.c pgraph_glsl_gen_vsh_ff after its
 * header. The skinning, texgen and light loops have uniform trip counts.
 */
static const char uber_ff_glsl_a[] =
"mat4 ubMat4(int base) { return mat4(c[base], c[base + 1], c[base + 2], c[base + 3]); }\n"
"void ubFF() {\n"
"  uint f = ubVsh[0].x;\n"
"  int skinCount = int((ubVsh[0].z >> 8) & 7u);\n"
"  bool skinMix = (f & " stringify(VSH_UBER_F_SKIN_MIX_V) "u) != 0u;\n"
"  vec4 tPosition;\n"
"  vec3 tNormal;\n"
/* append_skinning_code. With weights the specialised text starts from zero
 * and adds each term; the compiler folds the first add away, so the first
 * term is assigned here. */
"  if (skinCount == 0) {\n"
"    tPosition = (position * modelViewMat0).xyzw;\n"
"    tNormal = (vec4(normal, 0.0) * invModelViewMat0).xyz;\n"
"  } else {\n"
"    float weight_n = 1.0;\n"
"    for (int i = 0; i < skinCount; i++) {\n"
"      float weight_i;\n"
"      if (skinMix) {\n"
"        if (i < skinCount - 1) { weight_i = weight[i]; weight_n -= weight_i; }\n"
"        else { weight_i = weight_n; }\n"
"      } else {\n"
"        weight_i = weight[i];\n"
"      }\n"
"      vec4 term = (position * ubMat4(" stringify(NV_IGRAPH_XF_XFCTX_MMAT0) " + 8 * i)).xyzw * weight_i;\n"
"      tPosition = i == 0 ? term : tPosition + term;\n"
"    }\n"
"    weight_n = 1.0;\n"
"    for (int i = 0; i < skinCount; i++) {\n"
"      float weight_i;\n"
"      if (skinMix) {\n"
"        if (i < skinCount - 1) { weight_i = weight[i]; weight_n -= weight_i; }\n"
"        else { weight_i = weight_n; }\n"
"      } else {\n"
"        weight_i = weight[i];\n"
"      }\n"
"      vec3 term = (vec4(normal, 0.0) * ubMat4(" stringify(NV_IGRAPH_XF_XFCTX_IMMAT0) " + 8 * i)).xyz * weight_i;\n"
"      tNormal = i == 0 ? term : tNormal + term;\n"
"    }\n"
"  }\n"
"  if ((f & " stringify(VSH_UBER_F_NORMALIZE_V) "u) != 0u) { tNormal = normalize(tNormal); }\n"
/* texgen, stage by stage, component by component */
"  vec4 ubT[4] = vec4[4](oT0, oT1, oT2, oT3);\n"
"  vec4 texIn[4] = vec4[4](texture0, texture1, texture2, texture3);\n"
"  int ntg = int(ubVsh[2].w);\n"
"  for (int k = 0; k < ntg; k++) {\n"
"    int s = k >> 2;\n"
"    int comp = k & 3;\n"
"    uint mode = ((s < 2 ? ubVsh[2].y : ubVsh[2].z) >> (16 * (s & 1) + 3 * comp)) & 7u;\n"
"    int pl = " stringify(NV_IGRAPH_XF_XFCTX_TG0MAT) " + 8 * s + comp;\n"
"    float v;\n"
"    if (mode == 1u) {\n"
"      v = dot(c[pl], tPosition);\n"
"    } else if (mode == 2u) {\n"
"      v = dot(c[pl], position);\n"
"    } else if (mode == 3u) {\n"
"      vec3 u = normalize(tPosition.xyz);\n"
"      vec3 r = reflect(u, tNormal);\n"
"      float invM = 1.0 / (2.0 * length(r + vec3(0.0, 0.0, 1.0)));\n"
"      v = r[comp] * invM + 0.5;\n"
"    } else if (mode == 5u) {\n"
"      vec3 u = normalize(tPosition.xyz);\n"
"      vec3 r = reflect(u, tNormal);\n"
"      v = r[comp];\n"
"    } else if (mode == 4u) {\n"
"      v = tNormal[comp];\n"
"    } else {\n"
"      v = texIn[s][comp];\n"
"    }\n"
"    ubT[s][comp] = v;\n"
"  }\n"
"  uint texmat = (ubVsh[0].z >> 16) & 15u;\n"
"  if ((texmat & 1u) != 0u) { ubT[0] = ubT[0] * texMat0; }\n"
"  if ((texmat & 2u) != 0u) { ubT[1] = ubT[1] * texMat1; }\n"
"  if ((texmat & 4u) != 0u) { ubT[2] = ubT[2] * texMat2; }\n"
"  if ((texmat & 8u) != 0u) { ubT[3] = ubT[3] * texMat3; }\n"
"  oT0 = ubT[0]; oT1 = ubT[1]; oT2 = ubT[2]; oT3 = ubT[3];\n"
/* lighting */
"  bool lighting = (f & " stringify(VSH_UBER_F_LIGHTING_V) "u) != 0u;\n"
"  bool specEn = (f & " stringify(VSH_UBER_F_SPECULAR_V) "u) != 0u;\n"
"  bool sepSpec = (f & " stringify(VSH_UBER_F_SEPARATE_SPECULAR_V) "u) != 0u;\n"
"  if (!lighting) {\n"
"    oD0 = diffuse;\n"
"    oD1 = specular;\n"
"    oB0 = vec4(0.0, 0.0, 0.0, 1.0);\n"
"    oB1 = vec4(0.0, 0.0, 0.0, 1.0);\n"
"  } else {\n"
"    vec4 ltDiffuse = lt(diffuse);\n"
"    vec4 ltSpecular = lt(specular);\n"
"    bool fold = !specEn || !sepSpec;\n"
"    ubLightSide(false, tNormal, oD0, oD1, diffuse.a, specular.a, ltDiffuse, ltSpecular, tPosition, fold);\n"
"    if ((f & " stringify(VSH_UBER_F_TWO_SIDE_V) "u) != 0u) {\n"
"      ubLightSide(true, -tNormal, oB0, oB1, diffuse.a, specular.a, ltDiffuse, ltSpecular, tPosition, fold);\n"
"    }\n"
"  }\n"
"  if (!specEn) {\n"
"    oD1 = vec4(0.0, 0.0, 0.0, 1.0);\n"
"    oB1 = vec4(0.0, 0.0, 0.0, 1.0);\n"
"  } else {\n"
"    if (!sepSpec) {\n"
"      oD1 = specular;\n"
"      if (lighting) { oB1 = specular; }\n"
"    }\n"
"    if ((f & " stringify(VSH_UBER_F_IGNORE_SPECULAR_ALPHA_V) "u) != 0u) {\n"
"      oD1.a = 1.0;\n"
"      oB1.a = 1.0;\n"
"    }\n"
"  }\n"
"  if ((f & " stringify(VSH_UBER_F_FOG_V) "u) != 0u) {\n"
"    uint foggen = ubVsh[0].z & 7u;\n"
"    if (foggen == 0u) {\n"
"      fogDistance = clamp(specular.a, 0.0, 1.0);\n"
"    } else if (foggen == 1u) {\n"
"      fogDistance = length(tPosition.xyz);\n"
"    } else if (foggen == 2u || foggen == 3u) {\n"
"      fogDistance = dot(fogPlane.xyz, tPosition.xyz) + fogPlane.w;\n"
"      if (foggen == 3u) { fogDistance = abs(fogDistance); }\n"
"    } else {\n"
"      fogDistance = fogCoord;\n"
"    }\n"
"  }\n"
"  if (skinCount == 0) { tPosition = position; }\n"
/* The composite transform, verbatim */
"  oPos = tPosition * compositeMat;\n"
"  if (any(isinf(tPosition)) || any(isnan(tPosition))) {\n"
"    mat4 cm = compositeMat;\n"
"    for (int j = 0; j < 4; j++) {\n"
"      vec4 p = tPosition * cm[j];\n"
"      for (int i = 0; i < 4; i++) {\n"
"        if (tPosition[i] == 0.0 || cm[j][i] == 0.0) { p[i] = 0.0; }\n"
"      }\n"
"      oPos[j] = p.x + p.y + p.z + p.w;\n"
"    }\n"
"  }\n"
"  oPos.w = clampAwayZeroInf(oPos.w);\n"
"  vec2 hPos = oPos.xy;\n"
"  vec2 scrPos = oPos.xy / oPos.w + c[" stringify(NV_IGRAPH_XF_XFCTX_VPOFF) "].xy;\n"
"  oPos.xy = roundScreenCoords(scrPos);\n"
"  vtxPos = vec4(oPos.xy, oPos.z / oPos.w, oPos.w);\n"
"  oPos.z = oPos.z / clipRange.y;\n"
"  oPos.xy = (2.0 * oPos.xy - surfaceSize) / surfaceSize;\n"
"  oPos.xy *= oPos.w;\n"
"  bvec2 carry = not(lessThan(abs(scrPos), vec2(524288.0)));\n"
"  oPos.xy = mix(oPos.xy, 2.0 * hPos / surfaceSize\n"
"      + (2.0 * c[" stringify(NV_IGRAPH_XF_XFCTX_VPOFF) "].xy / surfaceSize - 1.0) * oPos.w,\n"
"      carry);\n"
"  if (clipRange.y <= 16777216.0\n"
"      && !(any(isinf(tPosition)) || any(isnan(tPosition)))) {\n"
"    vtxPos.z = ffScreenZ(tPosition);\n"
"  }\n"
"  if ((f & " stringify(VSH_UBER_F_POINT_PARAMS_V) "u) != 0u) {\n"
"    float d_e = length(position * modelViewMat0);\n"
"    float ptMinSize = min(pointParams[7], 63.875);\n"
"    float ptMaxSize = min(pointParams[3] + ptMinSize, 63.875);\n"
"    oPts.x = 1.0 / sqrt(pointParams[0] + pointParams[1] * d_e + pointParams[2] * d_e * d_e) + pointParams[6];\n";
/* + "    oPts.x = clamp(...) * float(scale);\n  } else {\n    oPts.x = ... * float(scale);\n  }\n}\n" */


MString *pgraph_glsl_gen_vsh_uber(const VshState *family,
                                  GenVshGlslOptions opts)
{
    assert(opts.vulkan);
    bool c_rw = family->programmable.program_length != 0;

    /* VshUniforms exactly as vsh.c declares it for this family, then ours */
    MString *uniforms = mstring_new();
    for (int i = 0; i < VshUniform__COUNT; i++) {
        const UniformInfo *info = &VshUniformInfo[i];
        const char *type_str = uniform_element_type_to_str[info->type];
        if (i == VshUniform_inlineValue &&
            (!family->uniform_attrs ||
             opts.use_push_constants_for_uniform_attrs)) {
            continue;
        }
        if (info->count == 1) {
            mstring_append_fmt(uniforms, "%s %s;\n", type_str, info->name);
        } else {
            mstring_append_fmt(uniforms, "%s %s[%zd];\n", type_str, info->name,
                               info->count);
        }
    }
    mstring_append_fmt(uniforms, "uvec4 " VSH_UBER_NAME "[%d];\n",
                       VSH_UBER_VEC4S);

    MString *out = mstring_new();
    pgraph_glsl_append_version(out, opts.vulkan, opts.gles, opts.gles_version);
    if (opts.use_push_constants_for_uniform_attrs) {
        /* All sixteen: the one GPL layout carries the whole range */
        mstring_append_fmt(out,
            "layout(push_constant) uniform PushConstants {\n"
            "    layout(offset = %d) vec4 inlineValue[%d];\n"
            "};\n\n",
            opts.vertex_push_offset, NV2A_VERTEXSHADER_ATTRIBUTES);
    }
    if (opts.ubo_set > 0) {
        mstring_append_fmt(out,
            "layout(set = %d, binding = %d, std140) uniform VshUniforms {\n"
            "%s};\n\n", opts.ubo_set, opts.ubo_binding,
            mstring_get_str(uniforms));
    } else {
        mstring_append_fmt(out,
            "layout(binding = %d, std140) uniform VshUniforms {\n"
            "%s};\n\n", opts.ubo_binding, mstring_get_str(uniforms));
    }
    mstring_unref(uniforms);

    mstring_append(out, pgraph_glsl_vsh_common_header());
    pgraph_glsl_get_vtx_header(out, opts.vulkan, family->smooth_shading,
                               family->noperspective, false,
                               opts.prefix_outputs, false);
    if (opts.prefix_outputs) {
        mstring_append(out,
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
                       "#define vtxPointSize v_vtxPointSize\n");
    }
    mstring_append(out, "\n");

    /* Every attribute is an input; a uniform one is selected at run time,
     * and its location may have no vertex attribute behind it, which only
     * leaves the unselected value undefined. */
    for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
        if (family->compressed_attrs & (1 << i)) {
            mstring_append_fmt(out, "layout(location = %d) in int v%d_cmp;\n",
                               i, i);
        } else {
            mstring_append_fmt(out, "layout(location = %d) in vec4 v%d_in;\n",
                               i, i);
        }
        mstring_append_fmt(out, "vec4 v%d;\n", i);
    }
    mstring_append(out, "\n");

    mstring_append(out, pgraph_glsl_vsh_prog_helpers());
    pgraph_glsl_append_vsh_ff_header(out);
    mstring_append(out,
                   "#define ringVertexIndex gl_VertexIndex\n"
                   "vec4 vtxPos;\n"
                   "float fogDistance;\n");
    if (c_rw) {
        mstring_append(out,
                       "vec4 c_rw[" stringify(NV2A_VERTEXSHADER_CONSTANTS) "];\n"
                       "vec4 _c_rw_oob;\n"
                       "vec4 _c_rw_tmp;\n"
                       "#define UB_CFILE c_rw\n"
                       "#define UB_CWRITE_MAC " UBER_CWRITE_MAC "\n"
                       "#define UB_CWRITE_ILU " UBER_CWRITE_ILU "\n"
                       "#define UB_CWRITE_SUFFIX " UBER_CWRITE_SUFFIX "\n");
    } else {
        mstring_append(out,
                       "#define UB_CFILE c\n"
                       "#define UB_CWRITE_MAC\n"
                       "#define UB_CWRITE_ILU\n"
                       "#define UB_CWRITE_SUFFIX\n");
    }
    mstring_append(out, uber_prog_glsl);
    mstring_append(out, uber_light_glsl);
    mstring_append(out, uber_prog_lighting_glsl);
    mstring_append(out, uber_ff_glsl_a);
    mstring_append_fmt(out,
        "    oPts.x = clamp(oPts.x * pointParams[3] + pointParams[7], ptMinSize, ptMaxSize) * float(%d);\n"
        "  } else {\n"
        "    oPts.x = uintBitsToFloat(ubVsh[2].x) * float(%d);\n"
        "  }\n"
        "}\n\n",
        family->surface_scale_factor, family->surface_scale_factor);

    /* main: vsh.c pgraph_glsl_gen_vsh's body */
    mstring_append(out,
                   "void main() {\n"
                   "  uint f = ubVsh[0].x;\n"
                   "  uint ubUA = ubVsh[0].y & 0xFFFFu;\n"
                   "  uint ubSW = ubVsh[0].y >> 16;\n");
    for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
        if (family->compressed_attrs & (1 << i)) {
            mstring_append_fmt(out, "  v%d = decompress_11_11_10(v%d_cmp);\n",
                               i, i);
            continue;
        }
        bool has_inline = opts.use_push_constants_for_uniform_attrs ||
                          family->uniform_attrs;
        if (has_inline) {
            mstring_append_fmt(out,
                "  v%d = ((ubUA >> %d) & 1u) != 0u ? "
                "inlineValue[bitCount(ubUA & %uu)] : v%d_in;\n",
                i, i, (1u << i) - 1, i);
        } else {
            mstring_append_fmt(out, "  v%d = v%d_in;\n", i, i);
        }
        mstring_append_fmt(out,
            "  if (((ubSW >> %d) & 1u) != 0u) { v%d = v%d.bgra; }\n", i, i, i);
    }
    mstring_append(out,
        "  ubV = vec4[16](v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11,\n"
        "                 v12, v13, v14, v15);\n");
    if (c_rw) {
        mstring_append(out, "  c_rw = c;\n");
    }
    mstring_append_fmt(out,
        "  if ((f & %du) != 0u) {\n"
        "    ubFF();\n"
        "  } else {\n"
        "    ubProgram();\n"
        "    if ((f & %du) == 0u) {\n"
        "      oPts.x = uintBitsToFloat(ubVsh[2].x) * float(%d);\n"
        "    }\n"
        "    if ((f & %du) != 0u) {\n"
        "      ubProgLighting();\n"
        "    }\n"
        "  }\n",
        VSH_UBER_F_FIXED_FUNCTION, VSH_UBER_F_POINT_PARAMS,
        family->surface_scale_factor, VSH_UBER_F_LIGHTING);

    /* vsh.c's fog block and output assignments */
    mstring_append_fmt(out,
        "  float fogSpecial = 0.0;\n"
        "  if ((f & %du) == 0u) {\n"
        "    oFog = vec4(1.0);\n"
        "  } else {\n"
        "    if ((f & %du) == 0u) {\n"
        "      fogDistance = (f & %du) != 0u ? carriedFogCoord : oFog.x;\n"
        "    }\n"
        "    if (isnan(fogDistance)) {\n"
        "      fogSpecial = 1.0;\n"
        "      oFog = vec4(0.0);\n"
        "    } else if (isinf(fogDistance)) {\n"
        "      fogSpecial = 2.0;\n"
        "      oFog = vec4(0.0);\n"
        "    } else {\n"
        "      oFog = vec4(fogDistance);\n"
        "    }\n"
        "  }\n",
        VSH_UBER_F_FOG, VSH_UBER_F_FIXED_FUNCTION, VSH_UBER_F_FOG_CARRIED);
    mstring_append(out, "\n"
        "  vtxD0 = colorPrecision(clamp(NaNToSignedOne(oD0), 0.0, 1.0));\n"
        "  vtxB0 = colorPrecision(clamp(NaNToSignedOne(oB0), 0.0, 1.0));\n"
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
        "  gl_PointSize = oPts.x;\n");
    mstring_append_fmt(out,
        "  if ((f & %du) != 0u) {\n"
        "    vtxD1 = colorPrecision(clamp(NaNToSignedOne(oD1), 0.0, 1.0));\n"
        "    vtxB1 = colorPrecision(clamp(NaNToSignedOne(oB1), 0.0, 1.0));\n"
        "    if ((f & %du) != 0u) {\n"
        "      vtxD1.w = 1.0;\n"
        "      vtxB1.w = 1.0;\n"
        "    }\n"
        "  } else {\n"
        "    vtxD1 = vec4(0.0, 0.0, 0.0, 1.0);\n"
        "    vtxB1 = vec4(0.0, 0.0, 0.0, 1.0);\n"
        "  }\n"
        "  gl_Position = oPos;\n",
        VSH_UBER_F_SPECULAR, VSH_UBER_F_IGNORE_SPECULAR_ALPHA);
    if (family->aa_offset_x != 0.0f) {
        mstring_append_fmt(out,
            "  gl_Position.x += (2.0 * %f / surfaceSize.x) * oPos.w;\n",
            family->aa_offset_x);
    }
    mstring_append(out, "}\n");

    return out;
}
