/*
 * psh-differ -- find pixel-shader state the generator does not look at.
 *
 * pgraph_glsl_gen_psh() turns a PshState into GLSL and reads nothing else, so
 * it can be called directly. Change one field of the state, generate again,
 * and compare the two shaders. If the text is identical, that field made no
 * difference to what the GPU will run: either the emulator does not implement
 * it, or it is inert in that configuration.
 *
 * The distinction matters, so the run does not stop at "identical". Each probe
 * lands in one of four buckets:
 *
 *   changed  the emitted GLSL differs -- the state reaches the shader
 *   unimpl   identical, but the generator logged NV2A_UNIMPLEMENTED -- a
 *            known gap, already written down in the source
 *   same     identical and silent -- nothing in the generator looks at it
 *   abort    the generator asserted -- reachable state that kills the frame
 *
 * "same" under every baseline is the interesting one. It is not proof the
 * field is dead: a field can be inert in every configuration tried here and
 * live in one that was not. Add a baseline rather than trusting the absence.
 *
 * Copyright (c) 2026 hakuX contributors
 * SPDX-License-Identifier: GPL-2.0-or-later
 */

#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#include "ui/xemu-settings.h"
#include "psh.h"

#include <glib/gstdio.h>

#include <fcntl.h>
#include <getopt.h>
#include <sys/wait.h>
#include <unistd.h>

/* Referenced by the carved-out half of psh.c; see shim/ui/xemu-settings.h. */
PshDifferConfig g_config;

/* ------------------------------------------------------------------ */
/* NV2A_UNIMPLEMENTED capture                                          */

static GString *unimpl;

void psh_differ_record_unimpl(const char *fmt, ...)
{
    va_list ap;
    if (unimpl->len) {
        g_string_append(unimpl, "; ");
    }
    va_start(ap, fmt);
    g_string_append_vprintf(unimpl, fmt, ap);
    va_end(ap);
}

/* ------------------------------------------------------------------ */
/* Generating                                                          */

typedef struct {
    char *glsl;
    char *unimpl;    /* NV2A_UNIMPLEMENTED text, or NULL if it stayed quiet */
} Emitted;

static void emitted_free(Emitted *e)
{
    g_free(e->glsl);
    g_free(e->unimpl);
    e->glsl = NULL;
    e->unimpl = NULL;
}

static Emitted emit(const PshState *state, GenPshGlslOptions opts)
{
    Emitted out = { NULL, NULL };
    MString *m;

    g_string_truncate(unimpl, 0);
    m = pgraph_glsl_gen_psh(state, opts);
    out.glsl = g_strdup(mstring_get_str(m));
    mstring_unref(m);
    if (unimpl->len) {
        out.unimpl = g_strdup(unimpl->str);
    }
    return out;
}

static uint64_t hash64(const char *s)
{
    uint64_t h = UINT64_C(0xcbf29ce484222325);

    for (; *s; s++) {
        h ^= (unsigned char)*s;
        h *= UINT64_C(0x100000001b3);
    }
    return h;
}

/* ------------------------------------------------------------------ */
/* The state fields, and how to vary each one                          */

typedef enum {
    K_BITS,   /* register shadow: flip each of 32 bits in turn */
    K_BOOL,
    K_INT,    /* sweep lo..hi inclusive */
    K_UINT,
    K_FLOAT,  /* try 0.0 and 64.0 */
} Kind;

typedef struct {
    const char *name;
    size_t off;
    Kind kind;
    int lo, hi;
} Field;

static const float float_probes[] = { 0.0f, 64.0f };

#define F(nm, kind, lo, hi) { #nm, offsetof(PshState, nm), kind, lo, hi }
#define F4(nm, kind, lo, hi) \
    F(nm[0], kind, lo, hi), F(nm[1], kind, lo, hi), \
    F(nm[2], kind, lo, hi), F(nm[3], kind, lo, hi)
#define F8(nm, kind, lo, hi) \
    F4(nm, kind, lo, hi), \
    F(nm[4], kind, lo, hi), F(nm[5], kind, lo, hi), \
    F(nm[6], kind, lo, hi), F(nm[7], kind, lo, hi)
#define F4x4(nm) \
    F4(nm[0], K_BOOL, 0, 1), F4(nm[1], K_BOOL, 0, 1), \
    F4(nm[2], K_BOOL, 0, 1), F4(nm[3], K_BOOL, 0, 1)
#define F4x3(nm) \
    F(nm[0][0], K_FLOAT, 0, 0), F(nm[0][1], K_FLOAT, 0, 0), F(nm[0][2], K_FLOAT, 0, 0), \
    F(nm[1][0], K_FLOAT, 0, 0), F(nm[1][1], K_FLOAT, 0, 0), F(nm[1][2], K_FLOAT, 0, 0), \
    F(nm[2][0], K_FLOAT, 0, 0), F(nm[2][1], K_FLOAT, 0, 0), F(nm[2][2], K_FLOAT, 0, 0), \
    F(nm[3][0], K_FLOAT, 0, 0), F(nm[3][1], K_FLOAT, 0, 0), F(nm[3][2], K_FLOAT, 0, 0)

static const Field fields[] = {
    F(combiner_control,     K_BITS, 0, 0),
    F(shader_stage_program, K_BITS, 0, 0),
    F(other_stage_input,    K_BITS, 0, 0),
    F(final_inputs_0,       K_BITS, 0, 0),
    F(final_inputs_1,       K_BITS, 0, 0),

    F8(rgb_inputs,    K_BITS, 0, 0),
    F8(rgb_outputs,   K_BITS, 0, 0),
    F8(alpha_inputs,  K_BITS, 0, 0),
    F8(alpha_outputs, K_BITS, 0, 0),

    F(point_sprite, K_BOOL, 0, 1),
    F4(rect_tex,    K_BOOL, 0, 1),
    F4(snorm_tex,   K_BOOL, 0, 1),
    F4x4(compare_mode),
    F4(alphakill,   K_BOOL, 0, 1),
    F4(colorkey_mode, K_INT, COLOR_KEY_NONE, COLOR_KEY_DISCARD),
    F4(conv_tex,    K_INT, CONVOLUTION_FILTER_DISABLED, CONVOLUTION_FILTER_GAUSSIAN),
    F4(tex_x8y24,   K_BOOL, 0, 1),
    F4(dim_tex,     K_INT, 1, 3),
    F4(tex_cubemap, K_BOOL, 0, 1),
    F4x3(border_logical_size),
    F4x3(border_inv_real_size),
    F4(shadow_map,  K_BOOL, 0, 1),
    F4(tex_depth_float, K_BOOL, 0, 1),

    F(shadow_depth_func, K_INT, SHADOW_DEPTH_FUNC_NEVER, SHADOW_DEPTH_FUNC_ALWAYS),
    F(alpha_test,        K_BOOL, 0, 1),
    F(alpha_func,        K_INT, ALPHA_FUNC_NEVER, ALPHA_FUNC_ALWAYS),

    F(window_clip_exclusive, K_BOOL, 0, 1),
    F(window_clip_count,     K_INT, 0, 8),

    F(smooth_shading, K_BOOL, 0, 1),
    F(depth_clipping, K_BOOL, 0, 1),
    F(z_perspective,  K_BOOL, 0, 1),
    F(depth_needed,   K_BOOL, 0, 1),

    /* Only Z16 and Z24S8 exist; anything else asserts in set_psh_state. */
    F(surface_zeta_format, K_UINT, NV097_SET_SURFACE_FORMAT_ZETA_Z16,
                                   NV097_SET_SURFACE_FORMAT_ZETA_Z24S8),
    F(depth_format, K_INT, DEPTH_FORMAT_D24, DEPTH_FORMAT_F16),
};

#define NFIELDS ARRAY_SIZE(fields)

/* The table indexes fields by byte offset and writes them through a cast, so
 * the enums had better be int-sized. */
_Static_assert(sizeof(((PshState *)0)->conv_tex[0]) == sizeof(int), "enum size");
_Static_assert(sizeof(((PshState *)0)->alpha_func) == sizeof(int), "enum size");
_Static_assert(sizeof(((PshState *)0)->depth_format) == sizeof(int), "enum size");

static int field_nprobes(const Field *f)
{
    switch (f->kind) {
    case K_BITS:  return 32;
    case K_BOOL:  return 2;
    case K_INT:
    case K_UINT:  return f->hi - f->lo + 1;
    case K_FLOAT: return ARRAY_SIZE(float_probes);
    }
    g_assert_not_reached();
}

/* Applies probe n to state. Returns false when the probe is a no-op against
 * this baseline -- the field already holds that value, so there is nothing to
 * learn from it. */
static bool field_apply(const Field *f, PshState *state, int n, char *label,
                        size_t label_size)
{
    char *p = (char *)state + f->off;

    switch (f->kind) {
    case K_BITS: {
        uint32_t *v = (uint32_t *)p;
        snprintf(label, label_size, "%s#%d", f->name, n);
        *v ^= UINT32_C(1) << n;
        return true;
    }
    case K_BOOL: {
        bool *v = (bool *)p;
        snprintf(label, label_size, "%s=%d", f->name, n);
        if (*v == (bool)n) {
            return false;
        }
        *v = n;
        return true;
    }
    case K_INT: {
        int *v = (int *)p;
        snprintf(label, label_size, "%s=%d", f->name, f->lo + n);
        if (*v == f->lo + n) {
            return false;
        }
        *v = f->lo + n;
        return true;
    }
    case K_UINT: {
        unsigned int *v = (unsigned int *)p;
        snprintf(label, label_size, "%s=%d", f->name, f->lo + n);
        if (*v == (unsigned int)(f->lo + n)) {
            return false;
        }
        *v = f->lo + n;
        return true;
    }
    case K_FLOAT: {
        float *v = (float *)p;
        snprintf(label, label_size, "%s=%g", f->name, float_probes[n]);
        if (*v == float_probes[n]) {
            return false;
        }
        *v = float_probes[n];
        return true;
    }
    }
    g_assert_not_reached();
}

/* ------------------------------------------------------------------ */
/* Baselines                                                           */

static uint32_t ci(uint8_t a, uint8_t b, uint8_t c, uint8_t d)
{
    return ((uint32_t)a << 24) | ((uint32_t)b << 16) | ((uint32_t)c << 8) | d;
}

static uint32_t co(int ab, int cd, int muxsum, int flags)
{
    return (cd & 0xF) | ((ab & 0xF) << 4) | ((muxsum & 0xF) << 8) |
           ((uint32_t)flags << 12);
}

static uint32_t stage_program(int s0, int s1, int s2, int s3)
{
    return (uint32_t)s0 | ((uint32_t)s1 << 5) | ((uint32_t)s2 << 10) |
           ((uint32_t)s3 << 15);
}

static void common_tail(PshState *s)
{
    s->smooth_shading = true;
    s->depth_needed = true;
    s->z_perspective = true;
    s->surface_zeta_format = NV097_SET_SURFACE_FORMAT_ZETA_Z24S8;
    s->depth_format = DEPTH_FORMAT_D24;
    s->final_inputs_0 = ci(PS_REGISTER_ZERO, PS_REGISTER_ZERO,
                           PS_REGISTER_ZERO, PS_REGISTER_R0);
    s->final_inputs_1 = ci(PS_REGISTER_ZERO, PS_REGISTER_ZERO,
                           PS_REGISTER_ZERO, 0);
}

/* Nothing enabled: no combiner stages, no textures. The floor. */
static void bl_off(PshState *s)
{
    memset(s, 0, sizeof(*s));
    s->surface_zeta_format = NV097_SET_SURFACE_FORMAT_ZETA_Z24S8;
}

/* One stage sampling one 2D texture, with an alpha test. What most draws do. */
static void bl_basic(PshState *s)
{
    memset(s, 0, sizeof(*s));
    s->combiner_control = 1;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_NONE,
                                            PS_TEXTUREMODES_NONE,
                                            PS_TEXTUREMODES_NONE);
    s->dim_tex[0] = 2;
    s->rgb_inputs[0] = ci(PS_REGISTER_T0, PS_REGISTER_V0,
                          PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->rgb_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                           PS_REGISTER_DISCARD, 0);
    s->alpha_inputs[0] = ci(PS_REGISTER_T0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->alpha_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                             PS_REGISTER_DISCARD, 0);
    s->alpha_test = true;
    s->alpha_func = ALPHA_FUNC_GREATER;
    common_tail(s);
}

/* All eight combiner stages live, so the stage registers past the first are
 * not inert merely because num_stages excluded them. */
static void bl_stages(PshState *s)
{
    int i;

    memset(s, 0, sizeof(*s));
    s->combiner_control = 8 | ((PS_COMBINERCOUNT_MUX_MSB |
                                PS_COMBINERCOUNT_UNIQUE_C0 |
                                PS_COMBINERCOUNT_UNIQUE_C1) << 8);
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_PROJECT2D);
    for (i = 0; i < 4; i++) {
        s->dim_tex[i] = 2;
    }
    for (i = 0; i < 8; i++) {
        uint8_t t = PS_REGISTER_T0 + (i & 3);
        s->rgb_inputs[i] = ci(t, PS_REGISTER_V0 | PS_INPUTMAPPING_EXPAND_NORMAL,
                              PS_REGISTER_C0, PS_REGISTER_C1);
        s->rgb_outputs[i] = co(PS_REGISTER_R0, PS_REGISTER_R1, PS_REGISTER_T0,
                               PS_COMBINEROUTPUT_AB_CD_MUX |
                               PS_COMBINEROUTPUT_SHIFTLEFT_1);
        s->alpha_inputs[i] = ci(t | PS_CHANNEL_ALPHA,
                                PS_REGISTER_V1 | PS_CHANNEL_ALPHA,
                                PS_REGISTER_C0 | PS_CHANNEL_ALPHA,
                                PS_REGISTER_C1 | PS_CHANNEL_ALPHA);
        s->alpha_outputs[i] = co(PS_REGISTER_R0, PS_REGISTER_R1,
                                 PS_REGISTER_DISCARD,
                                 PS_COMBINEROUTPUT_BIAS);
    }
    common_tail(s);
}

/* The texture modes that are not a plain 2D fetch: bump mapping, the dot
 * product family, and their dot-mapping and input-texture wiring. */
static void bl_textures(PshState *s)
{
    int i;

    memset(s, 0, sizeof(*s));
    s->combiner_control = 4;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_BUMPENVMAP_LUM,
                                            PS_TEXTUREMODES_DOT_ST,
                                            PS_TEXTUREMODES_DOT_STR_3D);
    s->dim_tex[0] = 2;
    s->dim_tex[1] = 2;
    s->dim_tex[2] = 2;
    s->dim_tex[3] = 3;

    /* dot_map[1..3] in nibbles 0..2; input_tex[2] and [3] at bits 16 and 20. */
    s->other_stage_input = PS_DOTMAPPING_MINUS1_TO_1_D3D |
                           (PS_DOTMAPPING_MINUS1_TO_1_GL << 4) |
                           (PS_DOTMAPPING_HILO_1 << 8) |
                           (1u << 16) | (2u << 20);

    for (i = 0; i < 4; i++) {
        uint8_t t = PS_REGISTER_T0 + i;
        s->alphakill[i] = true;
        s->rect_tex[i] = (i & 1) != 0;
        s->snorm_tex[i] = (i & 1) == 0;
        s->rgb_inputs[i] = ci(t, PS_REGISTER_V0, PS_REGISTER_ZERO,
                              PS_REGISTER_ZERO);
        s->rgb_outputs[i] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                               PS_REGISTER_DISCARD, 0);
        s->alpha_inputs[i] = ci(t | PS_CHANNEL_ALPHA,
                                PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                                PS_REGISTER_ZERO, PS_REGISTER_ZERO);
        s->alpha_outputs[i] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                                 PS_REGISTER_DISCARD, 0);
    }
    s->conv_tex[0] = CONVOLUTION_FILTER_QUINCUNX;
    s->colorkey_mode[0] = COLOR_KEY_KILL_ALPHA;
    s->colorkey_mode[1] = COLOR_KEY_DISCARD;
    common_tail(s);
}

/* Everything that hangs off the surface rather than the combiners: shadow
 * comparison, window clipping, texture borders, point sprites. */
static void bl_surface(PshState *s)
{
    int i, j;

    memset(s, 0, sizeof(*s));
    s->combiner_control = 2;
    /* PROJECT3D on the first two stages: that is the only shadow path that
     * compares against a reference depth, and so the only one that has to
     * decode a float depth texture. PROJECT2D compares against zero. */
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT3D,
                                            PS_TEXTUREMODES_PROJECT3D,
                                            PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_PROJECT2D);
    for (i = 0; i < 4; i++) {
        uint8_t t = PS_REGISTER_T0 + i;
        s->dim_tex[i] = 2;
        s->shadow_map[i] = true;
        for (j = 0; j < 4; j++) {
            s->compare_mode[i][j] = ((i + j) & 1) != 0;
        }
        s->rgb_inputs[i & 1] = ci(t, PS_REGISTER_V0, PS_REGISTER_ZERO,
                                  PS_REGISTER_ZERO);
        s->rgb_outputs[i & 1] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                                   PS_REGISTER_DISCARD, 0);
        s->alpha_inputs[i & 1] = ci(t | PS_CHANNEL_ALPHA,
                                    PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                                    PS_REGISTER_ZERO, PS_REGISTER_ZERO);
        s->alpha_outputs[i & 1] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                                     PS_REGISTER_DISCARD, 0);
    }
    s->shadow_depth_func = SHADOW_DEPTH_FUNC_LEQUAL;
    s->tex_x8y24[0] = true;
    /* [0] is a 24-bit float depth texture, [1] a 16-bit one; 2 and 3 stay
     * fixed-point so both shadow paths are generated. */
    s->tex_depth_float[0] = true;
    s->tex_depth_float[1] = true;

    s->border_logical_size[0][0] = 64.0f;
    s->border_logical_size[0][1] = 64.0f;
    s->border_logical_size[0][2] = 1.0f;
    s->border_inv_real_size[0][0] = 1.0f / 66.0f;
    s->border_inv_real_size[0][1] = 1.0f / 66.0f;
    s->border_inv_real_size[0][2] = 1.0f;

    s->window_clip_count = 4;
    s->window_clip_exclusive = true;
    s->point_sprite = true;
    s->depth_clipping = true;
    common_tail(s);
}

/* Clip planes. compare_mode[][] is read here and nowhere else. */
static void bl_clipplane(PshState *s)
{
    int i, j;

    memset(s, 0, sizeof(*s));
    s->combiner_control = 2;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_CLIPPLANE,
                                            PS_TEXTUREMODES_CLIPPLANE,
                                            PS_TEXTUREMODES_CLIPPLANE,
                                            PS_TEXTUREMODES_CLIPPLANE);
    for (i = 0; i < 4; i++) {
        s->dim_tex[i] = 2;
        for (j = 0; j < 4; j++) {
            s->compare_mode[i][j] = ((i ^ j) & 1) != 0;
        }
    }
    s->rgb_inputs[0] = ci(PS_REGISTER_T0, PS_REGISTER_V0, PS_REGISTER_ZERO,
                          PS_REGISTER_ZERO);
    s->rgb_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                           PS_REGISTER_DISCARD, 0);
    s->alpha_inputs[0] = ci(PS_REGISTER_T0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->alpha_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                             PS_REGISTER_DISCARD, 0);
    common_tail(s);
}

/* Four-texel texture borders. apply_border_adjustment() runs only when the
 * texture is not a shadow map, so this cannot share the surface baseline. */
static void bl_border(PshState *s)
{
    int i;

    memset(s, 0, sizeof(*s));
    s->combiner_control = 2;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_PROJECT3D,
                                            PS_TEXTUREMODES_PROJECT2D);
    for (i = 0; i < 4; i++) {
        s->dim_tex[i] = 2;
        s->border_logical_size[i][0] = 32.0f;
        s->border_logical_size[i][1] = 32.0f;
        s->border_logical_size[i][2] = 1.0f;
        s->border_inv_real_size[i][0] = 1.0f / 40.0f;
        s->border_inv_real_size[i][1] = 1.0f / 40.0f;
        s->border_inv_real_size[i][2] = 1.0f;
    }
    s->rgb_inputs[0] = ci(PS_REGISTER_T0, PS_REGISTER_T1, PS_REGISTER_T2,
                          PS_REGISTER_T3);
    s->rgb_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                           PS_REGISTER_DISCARD, 0);
    s->alpha_inputs[0] = ci(PS_REGISTER_T0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->alpha_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                             PS_REGISTER_DISCARD, 0);
    common_tail(s);
}

/* Bump mapping. snorm_tex[] is read through input_tex[], not by stage index,
 * so the wiring in other_stage_input decides which entries are reachable at
 * all: a texture can only feed a later stage. */
static void bl_bumpenv(PshState *s)
{
    int i;

    memset(s, 0, sizeof(*s));
    s->combiner_control = 2;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_BUMPENVMAP,
                                            PS_TEXTUREMODES_BUMPENVMAP_LUM,
                                            PS_TEXTUREMODES_BUMPENVMAP);
    /* input_tex[2] = 1, input_tex[3] = 2 */
    s->other_stage_input = (1u << 16) | (2u << 20);
    for (i = 0; i < 4; i++) {
        s->dim_tex[i] = 2;
        s->snorm_tex[i] = (i & 1) == 0;
    }
    s->rgb_inputs[0] = ci(PS_REGISTER_T0, PS_REGISTER_T1, PS_REGISTER_T2,
                          PS_REGISTER_T3);
    s->rgb_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                           PS_REGISTER_DISCARD, 0);
    s->alpha_inputs[0] = ci(PS_REGISTER_T0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->alpha_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                             PS_REGISTER_DISCARD, 0);
    common_tail(s);
}

/* The modes none of the others reach: cube maps, passthrough, and the
 * dependent AR/GB lookups. */
static void bl_misc(PshState *s)
{
    int i;

    memset(s, 0, sizeof(*s));
    s->combiner_control = 2;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_CUBEMAP,
                                            PS_TEXTUREMODES_PASSTHRU,
                                            PS_TEXTUREMODES_DPNDNT_AR,
                                            PS_TEXTUREMODES_DPNDNT_GB);
    s->other_stage_input = (0u << 16) | (0u << 20);
    for (i = 0; i < 4; i++) {
        s->dim_tex[i] = 2;
        s->tex_cubemap[i] = i == 0;
    }
    s->rgb_inputs[0] = ci(PS_REGISTER_T0, PS_REGISTER_T1, PS_REGISTER_T2,
                          PS_REGISTER_T3);
    s->rgb_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                           PS_REGISTER_DISCARD, 0);
    s->alpha_inputs[0] = ci(PS_REGISTER_T0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->alpha_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD,
                             PS_REGISTER_DISCARD, 0);
    common_tail(s);
}

typedef void (*BaselineFn)(PshState *);

static const struct {
    const char *name;
    BaselineFn fn;
} baselines[] = {
    { "off",      bl_off },
    { "basic",    bl_basic },
    { "stages",   bl_stages },
    { "textures", bl_textures },
    { "surface",  bl_surface },
    { "clipplane", bl_clipplane },
    { "border",   bl_border },
    { "bumpenv",  bl_bumpenv },
    { "misc",     bl_misc },
};

static const struct {
    const char *name;
    GenPshGlslOptions opts;
    int renderer;
} renderers[] = {
    { "gl",   { false, false, 0,   0, 0, 0 }, CONFIG_DISPLAY_RENDERER_OPENGL },
    { "vk",   { true,  false, 0,   1, 0, 2 }, CONFIG_DISPLAY_RENDERER_VULKAN },
    { "gles", { false, true,  320, 0, 0, 0 }, CONFIG_DISPLAY_RENDERER_OPENGL },
};

/* ------------------------------------------------------------------ */
/* Running the probes                                                  */

#define O_CHANGED (1u << 0)
#define O_UNIMPL  (1u << 1)
#define O_SAME    (1u << 2)
#define O_ABORT   (1u << 3)

typedef struct {
    const Field *field;
    int n;
    char label[96];
    unsigned int seen;   /* union of O_* over every scenario */
    int scenarios;       /* scenarios where the probe was not a no-op */
    char *unimpl;        /* first NV2A_UNIMPLEMENTED text, if any */
} Probe;

static const char *probe_status(const Probe *p)
{
    if (!p->scenarios) {
        return "skipped";
    }
    if (p->seen & O_CHANGED) {
        return "changed";
    }
    if (p->seen & O_UNIMPL) {
        return "unimpl";
    }
    if (p->seen & O_ABORT) {
        return "abort";
    }
    return "same";
}

static Probe *build_probes(size_t *count)
{
    size_t total = 0, i, k = 0;
    Probe *probes;
    PshState zero;

    for (i = 0; i < NFIELDS; i++) {
        total += field_nprobes(&fields[i]);
    }
    probes = g_new0(Probe, total);
    memset(&zero, 0, sizeof(zero));
    for (i = 0; i < NFIELDS; i++) {
        int n, np = field_nprobes(&fields[i]);
        for (n = 0; n < np; n++) {
            PshState s = zero;
            probes[k].field = &fields[i];
            probes[k].n = n;
            /* field_apply names the probe whether or not it changes anything,
             * so the labels are known before any generation happens. */
            field_apply(&fields[i], &s, n, probes[k].label,
                        sizeof(probes[k].label));
            k++;
        }
    }
    *count = total;
    return probes;
}

/*
 * A bad PshState does not always fail politely. Some values trip an assert;
 * some -- a combiner stage count above eight, say -- run off the end of an
 * array and corrupt whatever follows before anything notices. Neither can be
 * caught in-process and recovered from honestly.
 *
 * So the probes run in a forked child that reports one small record per probe
 * down a pipe. If the child dies, it dies alone: the parent knows which probe
 * it was working on, records that it aborted, and starts a fresh child on the
 * next one.
 */

#define REC_BASELINE UINT32_MAX

typedef struct {
    uint32_t index;
    uint32_t status;   /* an O_* bit, or 0 for "the baseline already has it" */
    char unimpl[192];
} Rec;

static void write_rec(int fd, const Rec *r)
{
    const char *p = (const char *)r;
    size_t left = sizeof(*r);

    while (left) {
        ssize_t n = write(fd, p, left);
        if (n <= 0) {
            if (n < 0 && errno == EINTR) {
                continue;
            }
            _exit(2);
        }
        p += n;
        left -= n;
    }
}

static bool read_rec(int fd, Rec *r)
{
    char *p = (char *)r;
    size_t left = sizeof(*r);

    while (left) {
        ssize_t n = read(fd, p, left);
        if (n == 0) {
            return false;
        }
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            return false;
        }
        p += n;
        left -= n;
    }
    return true;
}

static void child_run(size_t bl, size_t rd, const Probe *probes,
                      size_t nprobes, size_t start, int fd)
{
    PshState base_state;
    Emitted base;
    uint64_t base_hash;
    size_t i;
    Rec r;

    g_config.display.renderer = renderers[rd].renderer;
    baselines[bl].fn(&base_state);
    base = emit(&base_state, renderers[rd].opts);
    base_hash = hash64(base.glsl);

    memset(&r, 0, sizeof(r));
    r.index = REC_BASELINE;
    r.status = O_SAME;
    if (base.unimpl) {
        g_strlcpy(r.unimpl, base.unimpl, sizeof(r.unimpl));
    }
    write_rec(fd, &r);

    for (i = start; i < nprobes; i++) {
        PshState s = base_state;
        char label[sizeof(probes[i].label)];
        Emitted e;

        memset(&r, 0, sizeof(r));
        r.index = i;
        if (!field_apply(probes[i].field, &s, probes[i].n, label,
                         sizeof(label))) {
            write_rec(fd, &r);
            continue;
        }
        e = emit(&s, renderers[rd].opts);
        if (hash64(e.glsl) != base_hash) {
            r.status = O_CHANGED;
        } else if (e.unimpl &&
                   (!base.unimpl || strcmp(e.unimpl, base.unimpl))) {
            r.status = O_UNIMPL;
            g_strlcpy(r.unimpl, e.unimpl, sizeof(r.unimpl));
        } else {
            r.status = O_SAME;
        }
        emitted_free(&e);
        write_rec(fd, &r);
    }
    emitted_free(&base);
}

/* Forks a child, drains its records, and returns the index the child died on,
 * or nprobes if it finished. Sets *saw_baseline when the child got far enough
 * to generate the unmodified baseline. */
static size_t drain_child(size_t bl, size_t rd, Probe *probes, size_t nprobes,
                          size_t start, bool verbose, bool *saw_baseline,
                          bool *clean)
{
    size_t expect = start;
    int fds[2], st;
    pid_t pid;
    Rec r;

    if (pipe(fds)) {
        perror("psh-differ: pipe");
        exit(1);
    }
    pid = fork();
    if (pid < 0) {
        perror("psh-differ: fork");
        exit(1);
    }
    if (pid == 0) {
        close(fds[0]);
        if (!verbose) {
            /* A crashing child prints its own obituary; only wanted with -v. */
            int null = open("/dev/null", O_WRONLY);
            if (null >= 0) {
                dup2(null, STDERR_FILENO);
            }
        }
        child_run(bl, rd, probes, nprobes, start, fds[1]);
        _exit(0);
    }

    close(fds[1]);
    while (read_rec(fds[0], &r)) {
        if (r.index == REC_BASELINE) {
            *saw_baseline = true;
            if (verbose && r.unimpl[0]) {
                fprintf(stderr, "psh-differ: baseline %s/%s already warns: %s\n",
                        baselines[bl].name, renderers[rd].name, r.unimpl);
            }
            continue;
        }
        if (r.index >= nprobes) {
            break;
        }
        if (r.status) {
            probes[r.index].seen |= r.status;
            probes[r.index].scenarios++;
            if (r.status == O_UNIMPL && !probes[r.index].unimpl) {
                probes[r.index].unimpl = g_strdup(r.unimpl);
            }
        }
        expect = r.index + 1;
    }
    close(fds[0]);

    while (waitpid(pid, &st, 0) < 0 && errno == EINTR) {
        continue;
    }
    *clean = WIFEXITED(st) && WEXITSTATUS(st) == 0;
    return expect;
}

/* Runs every probe against one baseline and one renderer. Returns false and
 * leaves the results alone if the baseline itself does not generate. */
static bool run_scenario(size_t bl, size_t rd, Probe *probes, size_t nprobes,
                         bool verbose)
{
    size_t next = 0;

    while (next < nprobes) {
        bool saw_baseline = false, clean = false;
        size_t died_at = drain_child(bl, rd, probes, nprobes, next, verbose,
                                     &saw_baseline, &clean);

        if (!saw_baseline) {
            fprintf(stderr,
                    "psh-differ: baseline %s/%s does not generate. Every probe "
                    "against it would be meaningless, so it is skipped. Fix "
                    "the baseline in differ.c.\n",
                    baselines[bl].name, renderers[rd].name);
            return false;
        }
        if (died_at >= nprobes) {
            return true;
        }
        if (clean) {
            /* Finished without dying but without covering everything: the
             * pipe protocol is out of step, not the generator. */
            fprintf(stderr,
                    "psh-differ: %s/%s stopped at probe %zu of %zu without "
                    "failing. This is a bug in the differ.\n",
                    baselines[bl].name, renderers[rd].name, died_at, nprobes);
            return true;
        }
        probes[died_at].seen |= O_ABORT;
        probes[died_at].scenarios++;
        next = died_at + 1;
    }
    return true;
}

/* ------------------------------------------------------------------ */
/* Reporting                                                           */

static void report(const Probe *probes, size_t nprobes, bool list_all)
{
    size_t i = 0;
    int t_changed = 0, t_unimpl = 0, t_same = 0, t_abort = 0, t_skip = 0;

    printf("%-28s %6s %8s %7s %6s %6s %8s\n",
           "field", "probes", "changed", "unimpl", "same", "abort", "skipped");
    printf("%-28s %6s %8s %7s %6s %6s %8s\n",
           "----------------------------", "------", "--------", "-------",
           "------", "------", "--------");

    while (i < nprobes) {
        const Field *f = probes[i].field;
        int np = field_nprobes(f);
        int changed = 0, unimpl = 0, same = 0, abort_ = 0, skip = 0;
        int n;

        for (n = 0; n < np; n++) {
            const char *st = probe_status(&probes[i + n]);
            if (!strcmp(st, "changed")) {
                changed++;
            } else if (!strcmp(st, "unimpl")) {
                unimpl++;
            } else if (!strcmp(st, "abort")) {
                abort_++;
            } else if (!strcmp(st, "skipped")) {
                skip++;
            } else {
                same++;
            }
        }
        printf("%-28s %6d %8d %7d %6d %6d %8d\n", f->name, np, changed, unimpl,
               same, abort_, skip);
        t_changed += changed;
        t_unimpl += unimpl;
        t_same += same;
        t_abort += abort_;
        t_skip += skip;
        i += np;
    }

    printf("%-28s %6zu %8d %7d %6d %6d %8d\n", "TOTAL", nprobes, t_changed,
           t_unimpl, t_same, t_abort, t_skip);

    if (t_same) {
        printf("\nNo effect on the emitted GLSL, and no warning either.\n"
               "Each line is state the shader never sees. That is a bug only\n"
               "if the hardware acts on it -- check the register against\n"
               "docs/nv2a/ and the nxdk_pgraph_tests suite before filing.\n\n");
        for (i = 0; i < nprobes; i++) {
            if (strcmp(probe_status(&probes[i]), "same")) {
                continue;
            }
            printf("  %s\n", probes[i].label);
        }
    }

    if (t_unimpl) {
        printf("\nNo effect, but the generator says so out loud.\n"
               "These gaps are already written down in psh.c.\n\n");
        for (i = 0; i < nprobes; i++) {
            if (strcmp(probe_status(&probes[i]), "unimpl")) {
                continue;
            }
            printf("  %-40s %s\n", probes[i].label, probes[i].unimpl);
        }
    }

    if (t_abort) {
        printf("\nGeneration aborted. Reachable state that kills the frame\n"
               "rather than drawing it wrong.\n\n");
        for (i = 0; i < nprobes; i++) {
            if (strcmp(probe_status(&probes[i]), "abort")) {
                continue;
            }
            printf("  %s\n", probes[i].label);
        }
    }

    if (list_all && t_skip) {
        printf("\nNot exercised: the baselines already hold that value.\n\n");
        for (i = 0; i < nprobes; i++) {
            if (strcmp(probe_status(&probes[i]), "skipped")) {
                continue;
            }
            printf("  %s\n", probes[i].label);
        }
    }
}

static void write_json(const char *path, const Probe *probes, size_t nprobes)
{
    FILE *f = fopen(path, "w");
    size_t i;

    if (!f) {
        fprintf(stderr, "psh-differ: cannot write %s: %s\n", path,
                strerror(errno));
        exit(1);
    }
    fprintf(f, "{\n  \"probes\": [\n");
    for (i = 0; i < nprobes; i++) {
        g_autofree char *label = g_strescape(probes[i].label, NULL);
        g_autofree char *msg =
            probes[i].unimpl ? g_strescape(probes[i].unimpl, NULL) : NULL;
        fprintf(f, "    {\"probe\": \"%s\", \"field\": \"%s\", "
                   "\"status\": \"%s\", \"scenarios\": %d, \"aborts\": %s",
                label, probes[i].field->name, probe_status(&probes[i]),
                probes[i].scenarios,
                (probes[i].seen & O_ABORT) ? "true" : "false");
        if (msg) {
            fprintf(f, ", \"unimplemented\": \"%s\"", msg);
        }
        fprintf(f, "}%s\n", i + 1 < nprobes ? "," : "");
    }
    fprintf(f, "  ]\n}\n");
    fclose(f);
}

/* ------------------------------------------------------------------ */
/* Showing one probe                                                   */

static void print_diff(const char *a, const char *b)
{
    g_auto(GStrv) la = g_strsplit(a, "\n", -1);
    g_auto(GStrv) lb = g_strsplit(b, "\n", -1);
    guint na = g_strv_length(la), nb = g_strv_length(lb);
    guint head = 0, tail = 0, i;

    while (head < na && head < nb && !strcmp(la[head], lb[head])) {
        head++;
    }
    while (tail < na - head && tail < nb - head &&
           !strcmp(la[na - 1 - tail], lb[nb - 1 - tail])) {
        tail++;
    }

    if (head == na && head == nb) {
        printf("  (identical)\n");
        return;
    }
    if (head) {
        printf("  ... %u identical line%s\n", head, head == 1 ? "" : "s");
    }
    for (i = head; i < na - tail; i++) {
        printf("- %s\n", la[i]);
    }
    for (i = head; i < nb - tail; i++) {
        printf("+ %s\n", lb[i]);
    }
    if (tail) {
        printf("  ... %u identical line%s\n", tail, tail == 1 ? "" : "s");
    }
}

/* Generates the pair in a child, for the same reason the sweep does, and
 * hands the text back through files rather than a pipe so --dump-dir gets
 * them for free. */
static bool emit_pair(size_t bl, size_t rd, const Field *field, int n,
                      const char *dir, int *signo)
{
    int st;
    pid_t pid = fork();

    if (pid < 0) {
        perror("psh-differ: fork");
        exit(1);
    }
    if (pid == 0) {
        PshState base_state, s;
        Emitted base, probe;
        char label[96];
        g_autofree char *pa = g_strdup_printf("%s/base.frag", dir);
        g_autofree char *pb = g_strdup_printf("%s/probe.frag", dir);
        g_autofree char *pu = g_strdup_printf("%s/unimplemented.txt", dir);

        g_config.display.renderer = renderers[rd].renderer;
        baselines[bl].fn(&base_state);
        s = base_state;
        field_apply(field, &s, n, label, sizeof(label));
        base = emit(&base_state, renderers[rd].opts);
        probe = emit(&s, renderers[rd].opts);
        g_file_set_contents(pa, base.glsl, -1, NULL);
        g_file_set_contents(pb, probe.glsl, -1, NULL);
        g_file_set_contents(pu, probe.unimpl ? probe.unimpl : "", -1, NULL);
        _exit(0);
    }

    while (waitpid(pid, &st, 0) < 0 && errno == EINTR) {
        continue;
    }
    if (WIFSIGNALED(st)) {
        *signo = WTERMSIG(st);
        return false;
    }
    if (!WIFEXITED(st) || WEXITSTATUS(st)) {
        *signo = -1;
        return false;
    }
    *signo = 0;
    return true;
}

static int show(const char *want, const char *only_baseline,
                const char *only_renderer, const char *dump_dir)
{
    size_t nprobes, i, bl, rd;
    Probe *probes = build_probes(&nprobes);
    const Field *field = NULL;
    int n = -1;
    bool found = false;
    g_autofree char *tmpdir = NULL;
    const char *dir;

    for (i = 0; i < nprobes; i++) {
        if (!strcmp(probes[i].label, want)) {
            field = probes[i].field;
            n = probes[i].n;
            break;
        }
    }
    g_free(probes);
    if (!field) {
        fprintf(stderr, "psh-differ: no probe called '%s'. Probe names look "
                        "like 'combiner_control#8' or 'alpha_func=3'; run "
                        "without --show to see them all.\n", want);
        return 2;
    }

    if (dump_dir) {
        dir = dump_dir;
        g_mkdir_with_parents(dir, 0755);
    } else {
        tmpdir = g_dir_make_tmp("psh-differ-XXXXXX", NULL);
        if (!tmpdir) {
            fprintf(stderr, "psh-differ: cannot make a temporary directory\n");
            return 1;
        }
        dir = tmpdir;
    }

    for (bl = 0; bl < ARRAY_SIZE(baselines); bl++) {
        if (only_baseline && strcmp(baselines[bl].name, only_baseline)) {
            continue;
        }
        for (rd = 0; rd < ARRAY_SIZE(renderers); rd++) {
            PshState base_state, s;
            char label[96];
            int signo = 0;
            g_autofree char *a = NULL, *b = NULL, *u = NULL;
            g_autofree char *pa = g_strdup_printf("%s/base.frag", dir);
            g_autofree char *pb = g_strdup_printf("%s/probe.frag", dir);
            g_autofree char *pu = g_strdup_printf("%s/unimplemented.txt", dir);

            if (only_renderer && strcmp(renderers[rd].name, only_renderer)) {
                continue;
            }
            baselines[bl].fn(&base_state);
            s = base_state;
            if (!field_apply(field, &s, n, label, sizeof(label))) {
                printf("=== %s / %s: baseline already holds that value\n\n",
                       baselines[bl].name, renderers[rd].name);
                continue;
            }
            found = true;
            printf("=== %s / %s\n", baselines[bl].name, renderers[rd].name);
            if (!emit_pair(bl, rd, field, n, dir, &signo)) {
                printf("  generation died (signal %d)\n\n", signo);
                continue;
            }
            if (!g_file_get_contents(pa, &a, NULL, NULL) ||
                !g_file_get_contents(pb, &b, NULL, NULL)) {
                printf("  generation produced nothing\n\n");
                continue;
            }
            print_diff(a, b);
            if (g_file_get_contents(pu, &u, NULL, NULL) && u[0]) {
                printf("  unimplemented: %s\n", u);
            }
            if (dump_dir) {
                printf("  wrote %s and %s\n", pa, pb);
            } else {
                g_unlink(pa);
                g_unlink(pb);
                g_unlink(pu);
            }
            printf("\n");
        }
    }
    if (tmpdir) {
        g_rmdir(tmpdir);
    }
    if (!found) {
        fprintf(stderr, "psh-differ: no baseline/renderer pair varied it.\n");
        return 2;
    }
    return 0;
}

/* ------------------------------------------------------------------ */

static void usage(FILE *out)
{
    size_t i;

    fprintf(out,
        "usage: psh-differ [options]\n"
        "\n"
        "Varies one field of PshState at a time and reports whether the\n"
        "generated pixel shader changes.\n"
        "\n"
        "  --baseline NAME   only this baseline (default: all)\n"
        "  --renderer NAME   only this renderer (default: all)\n"
        "  --show PROBE      print the shader diff for one probe\n"
        "  --dump-dir DIR    with --show, write both shaders here\n"
        "  --json PATH       write per-probe results as JSON\n"
        "  --all             also list probes the baselines could not vary\n"
        "  --quiet           suppress the per-field table\n"
        "  --verbose         let the crashing child processes speak\n"
        "  --help\n"
        "\nbaselines:");
    for (i = 0; i < ARRAY_SIZE(baselines); i++) {
        fprintf(out, " %s", baselines[i].name);
    }
    fprintf(out, "\nrenderers:");
    for (i = 0; i < ARRAY_SIZE(renderers); i++) {
        fprintf(out, " %s", renderers[i].name);
    }
    fprintf(out, "\n");
}

int main(int argc, char **argv)
{
    static const struct option longopts[] = {
        { "baseline", required_argument, NULL, 'b' },
        { "renderer", required_argument, NULL, 'r' },
        { "show",     required_argument, NULL, 's' },
        { "dump-dir", required_argument, NULL, 'd' },
        { "json",     required_argument, NULL, 'j' },
        { "all",      no_argument,       NULL, 'a' },
        { "quiet",    no_argument,       NULL, 'q' },
        { "verbose",  no_argument,       NULL, 'v' },
        { "help",     no_argument,       NULL, 'h' },
        { NULL, 0, NULL, 0 },
    };
    const char *only_baseline = NULL, *only_renderer = NULL;
    const char *want = NULL, *json_path = NULL, *dump_dir = NULL;
    bool list_all = false, quiet = false, verbose = false;
    size_t nprobes, bl, rd;
    Probe *probes;
    int ran = 0, c;

    while ((c = getopt_long(argc, argv, "b:r:s:d:j:aqvh", longopts, NULL)) != -1) {
        switch (c) {
        case 'b': only_baseline = optarg; break;
        case 'r': only_renderer = optarg; break;
        case 's': want = optarg; break;
        case 'd': dump_dir = optarg; break;
        case 'j': json_path = optarg; break;
        case 'a': list_all = true; break;
        case 'q': quiet = true; break;
        case 'v': verbose = true; break;
        case 'h': usage(stdout); return 0;
        default:  usage(stderr); return 2;
        }
    }

    unimpl = g_string_new("");

    if (want) {
        return show(want, only_baseline, only_renderer, dump_dir);
    }

    probes = build_probes(&nprobes);
    for (bl = 0; bl < ARRAY_SIZE(baselines); bl++) {
        if (only_baseline && strcmp(baselines[bl].name, only_baseline)) {
            continue;
        }
        for (rd = 0; rd < ARRAY_SIZE(renderers); rd++) {
            if (only_renderer && strcmp(renderers[rd].name, only_renderer)) {
                continue;
            }
            ran += run_scenario(bl, rd, probes, nprobes, verbose);
        }
    }
    if (!ran) {
        fprintf(stderr, "psh-differ: no baseline/renderer pair ran.\n");
        return 2;
    }

    if (!quiet) {
        report(probes, nprobes, list_all);
    }
    if (json_path) {
        write_json(json_path, probes, nprobes);
    }
    g_free(probes);
    return 0;
}
