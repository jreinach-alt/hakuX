/*
 * gen: hakuX's real shader generators on the host, GLSL -> SPIR-V with the
 * device's glslang options, for a fixed catalogue of shader states.
 *
 *   gen <outdir> [--no-opt-flag]
 *
 * Writes <outdir>/<stage>_<name>.{glsl,spv} and <outdir>/manifest.txt (one
 * pipeline per line, vkharness's format).
 *
 * The generator sources are hw/xbox/nv2a/pgraph/glsl/*.c, carved (carve_all.py)
 * so nothing reads PGRAPHState, and optionally patched by a variant
 * (variants/*.sh). The GLSL options are vk/shaders.c:862-902's. The glslang
 * call is vk/glsl.c:195-289's: Vulkan 1.3 / SPIR-V 1.6 (Turnip reports 1.4,
 * vk/glsl.c:183), validate on, optimizer requested -- which is a no-op in a
 * glslang built with ENABLE_OPT=OFF, as the Android build's is.
 */
#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#include "ui/xemu-settings.h"
#include "shaders.h"

#include <glslang/Include/glslang_c_interface.h>
#include <sys/stat.h>

PshDifferConfig g_config;
void psh_differ_record_unimpl(const char *fmt, ...) { (void)fmt; }

#include "resource_limits.inc"   /* extracted from vk/glsl.c at build time */

static int g_disable_opt;

static size_t compile(glslang_stage_t stage, const char *src, const char *path)
{
    const glslang_input_t input = {
        .language = GLSLANG_SOURCE_GLSL,
        .stage = stage,
        .client = GLSLANG_CLIENT_VULKAN,
        .client_version = GLSLANG_TARGET_VULKAN_1_3,
        .target_language = GLSLANG_TARGET_SPV,
        .target_language_version = GLSLANG_TARGET_SPV_1_6,
        .code = src,
        .default_version = 460,
        .default_profile = GLSLANG_NO_PROFILE,
        .messages = GLSLANG_MSG_DEFAULT_BIT,
        .resource = &resource_limits,
    };
    glslang_shader_t *sh = glslang_shader_create(&input);
    if (!glslang_shader_preprocess(sh, &input) || !glslang_shader_parse(sh, &input)) {
        fprintf(stderr, "%s: %s\n", path, glslang_shader_get_info_log(sh));
        exit(1);
    }
    glslang_program_t *pr = glslang_program_create();
    glslang_program_add_shader(pr, sh);
    if (!glslang_program_link(pr, GLSLANG_MSG_SPV_RULES_BIT | GLSLANG_MSG_VULKAN_RULES_BIT)) {
        fprintf(stderr, "%s: link: %s\n", path, glslang_program_get_info_log(pr));
        exit(1);
    }
    glslang_spv_options_t o = { .validate = true, .disable_optimizer = g_disable_opt };
    glslang_program_SPIRV_generate_with_options(pr, stage, &o);
    const char *msg = glslang_program_SPIRV_get_messages(pr);
    if (msg && *msg) fprintf(stderr, "%s: %s\n", path, msg);
    size_t n = glslang_program_SPIRV_get_size(pr);
    uint32_t *w = g_malloc(n * 4);
    glslang_program_SPIRV_get(pr, w);
    g_file_set_contents(path, (const char *)w, n * 4, NULL);
    g_free(w);
    glslang_program_delete(pr);
    glslang_shader_delete(sh);
    return n * 4;
}

static const char *g_out;

static char *emit(const char *stage, const char *name, glslang_stage_t gs, MString *m)
{
    char *gp = g_strdup_printf("%s/%s_%s.glsl", g_out, stage, name);
    char *sp = g_strdup_printf("%s/%s_%s.spv", g_out, stage, name);
    g_file_set_contents(gp, mstring_get_str(m), -1, NULL);
    gint64 t0 = g_get_monotonic_time();
    size_t bytes = compile(gs, mstring_get_str(m), sp);
    gint64 t1 = g_get_monotonic_time();
    /* the glslang (and, in an ENABLE_OPT build, spirv-opt) time, for C1 */
    fprintf(stderr, "%-5s %-22s glsl %6zu B  spv %7zu B  glslang %7.1f ms\n", stage, name,
            strlen(mstring_get_str(m)), bytes, (t1 - t0) / 1000.0);
    mstring_unref(m);
    g_free(gp);
    return sp;
}

/* ---- vertex programs -------------------------------------------------- */
static int load_vshinc(const char *path, ProgrammableVshState *p)
{
    char *txt;
    if (!g_file_get_contents(path, &txt, NULL, NULL)) {
        fprintf(stderr, "missing %s\n", path);
        exit(1);
    }
    int n = 0;
    const char *s = txt;
    while ((s = strstr(s, "0x"))) {
        uint32_t v = strtoul(s, (char **)&s, 16);
        p->program_data[n / 4][n % 4] = v;
        n++;
    }
    g_free(txt);
    p->program_length = n / 4;
    return n / 4;
}

/* ---- vertex states ---------------------------------------------------- */
static void vs_common(VshState *v)
{
    memset(v, 0, sizeof(*v));
    v->surface_scale_factor = 1;
    v->smooth_shading = true;
    v->z_perspective = false;
    v->specular_enable = false;
}

static void vs_ff_unlit(VshState *v)
{
    vs_common(v);
    v->is_fixed_function = true;
}

static void vs_ff_lit2(VshState *v)
{
    vs_common(v);
    v->is_fixed_function = true;
    v->lighting = true;
    v->light[0] = LIGHT_INFINITE;
    v->light[1] = LIGHT_LOCAL;
    v->normalization = true;
    v->specular_enable = true;
    v->separate_specular = true;
    v->diffuse_src = MATERIAL_COLOR_SRC_DIFFUSE;
    v->fog_enable = true;
    v->foggen = FOGGEN_RADIAL;
    v->fixed_function.texture_matrix_enable[0] = true;
}

static void vs_ff_skin_texgen(VshState *v)
{
    vs_ff_lit2(v);
    v->fixed_function.skinning = SKINNING_2WEIGHTS;
    v->fixed_function.texgen[1][0] = TEXGEN_SPHERE_MAP;
    v->fixed_function.texgen[1][1] = TEXGEN_SPHERE_MAP;
}

static const char *g_vsh_dir;

static void vs_prog(VshState *v, const char *file)
{
    vs_common(v);
    v->is_fixed_function = false;
    char *p = g_strdup_printf("%s/%s", g_vsh_dir, file);
    load_vshinc(p, &v->programmable);
    g_free(p);
}

/* ---- pixel states (psh_differ's baselines, plus two game-shaped ones) -- */
static uint32_t ci(uint8_t a, uint8_t b, uint8_t c, uint8_t d)
{
    return ((uint32_t)a << 24) | ((uint32_t)b << 16) | ((uint32_t)c << 8) | d;
}
static uint32_t co(int ab, int cd, int muxsum, int flags)
{
    return (cd & 0xF) | ((ab & 0xF) << 4) | ((muxsum & 0xF) << 8) | ((uint32_t)flags << 12);
}
static uint32_t stage_program(int s0, int s1, int s2, int s3)
{
    return (uint32_t)s0 | ((uint32_t)s1 << 5) | ((uint32_t)s2 << 10) | ((uint32_t)s3 << 15);
}
static void ps_tail(PshState *s)
{
    s->smooth_shading = true;
    s->depth_needed = true;
    s->surface_zeta_format = NV097_SET_SURFACE_FORMAT_ZETA_Z24S8;
    s->depth_format = DEPTH_FORMAT_D24;
    s->final_inputs_0 = ci(PS_REGISTER_ZERO, PS_REGISTER_ZERO, PS_REGISTER_ZERO, PS_REGISTER_R0);
    s->final_inputs_1 = ci(PS_REGISTER_ZERO, PS_REGISTER_ZERO, PS_REGISTER_ZERO, 0);
    for (int i = 0; i < 4; i++) {
        s->tex_aniso[i] = 1;
    }
}
static void ps_modulate(PshState *s, int stage, uint8_t t)
{
    s->rgb_inputs[stage] = ci(t, PS_REGISTER_V0, PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->rgb_outputs[stage] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD, PS_REGISTER_DISCARD, 0);
    s->alpha_inputs[stage] = ci(t | PS_CHANNEL_ALPHA, PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                                PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->alpha_outputs[stage] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD, PS_REGISTER_DISCARD, 0);
}

static void ps_vertexcolor(PshState *s)   /* no texture, one stage */
{
    memset(s, 0, sizeof(*s));
    s->combiner_control = 1;
    s->rgb_inputs[0] = ci(PS_REGISTER_V0, PS_REGISTER_ZERO | PS_INPUTMAPPING_UNSIGNED_INVERT,
                          PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->rgb_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD, PS_REGISTER_DISCARD, 0);
    s->alpha_inputs[0] = ci(PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_ZERO | PS_CHANNEL_ALPHA | PS_INPUTMAPPING_UNSIGNED_INVERT,
                            PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->alpha_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD, PS_REGISTER_DISCARD, 0);
    ps_tail(s);
}

static void ps_basic(PshState *s)   /* one 2D texture x diffuse, alpha test */
{
    memset(s, 0, sizeof(*s));
    s->combiner_control = 1;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D, 0, 0, 0);
    s->dim_tex[0] = 2;
    ps_modulate(s, 0, PS_REGISTER_T0);
    s->alpha_test = true;
    s->alpha_func = ALPHA_FUNC_GREATER;
    ps_tail(s);
}

static void ps_game2(PshState *s)   /* two textures, specular add, fog */
{
    memset(s, 0, sizeof(*s));
    s->combiner_control = 2;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_PROJECT2D, 0, 0);
    s->dim_tex[0] = s->dim_tex[1] = 2;
    ps_modulate(s, 0, PS_REGISTER_T0);
    s->rgb_inputs[1] = ci(PS_REGISTER_R0, PS_REGISTER_T1, PS_REGISTER_V1,
                          PS_REGISTER_ZERO | PS_INPUTMAPPING_UNSIGNED_INVERT);
    s->rgb_outputs[1] = co(PS_REGISTER_DISCARD, PS_REGISTER_DISCARD, PS_REGISTER_R0, 0);
    s->alpha_inputs[1] = ci(PS_REGISTER_R0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_ZERO | PS_CHANNEL_ALPHA | PS_INPUTMAPPING_UNSIGNED_INVERT,
                            PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->alpha_outputs[1] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD, PS_REGISTER_DISCARD, 0);
    s->fog_enable = true;
    s->fog_mode = FOG_MODE_LINEAR;
    s->alpha_test = true;
    s->alpha_func = ALPHA_FUNC_GEQUAL;
    ps_tail(s);
    s->final_inputs_0 = ci(PS_REGISTER_FOG | PS_CHANNEL_ALPHA, PS_REGISTER_R0,
                           PS_REGISTER_FOG, PS_REGISTER_ZERO);
}

static void ps_stages8(PshState *s)   /* psh_differ bl_stages */
{
    memset(s, 0, sizeof(*s));
    s->combiner_control = 8 | ((PS_COMBINERCOUNT_MUX_MSB | PS_COMBINERCOUNT_UNIQUE_C0 |
                                PS_COMBINERCOUNT_UNIQUE_C1) << 8);
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D, PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_PROJECT2D, PS_TEXTUREMODES_PROJECT2D);
    for (int i = 0; i < 4; i++) s->dim_tex[i] = 2;
    for (int i = 0; i < 8; i++) {
        uint8_t t = PS_REGISTER_T0 + (i & 3);
        s->rgb_inputs[i] = ci(t, PS_REGISTER_V0 | PS_INPUTMAPPING_EXPAND_NORMAL,
                              PS_REGISTER_C0, PS_REGISTER_C1);
        s->rgb_outputs[i] = co(PS_REGISTER_R0, PS_REGISTER_R1, PS_REGISTER_T0,
                               PS_COMBINEROUTPUT_AB_CD_MUX | PS_COMBINEROUTPUT_SHIFTLEFT_1);
        s->alpha_inputs[i] = ci(t | PS_CHANNEL_ALPHA, PS_REGISTER_V1 | PS_CHANNEL_ALPHA,
                                PS_REGISTER_C0 | PS_CHANNEL_ALPHA, PS_REGISTER_C1 | PS_CHANNEL_ALPHA);
        s->alpha_outputs[i] = co(PS_REGISTER_R0, PS_REGISTER_R1, PS_REGISTER_DISCARD,
                                 PS_COMBINEROUTPUT_BIAS);
    }
    ps_tail(s);
}

static void ps_bumpenv(PshState *s)   /* psh_differ bl_bumpenv */
{
    memset(s, 0, sizeof(*s));
    s->combiner_control = 2;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D, PS_TEXTUREMODES_BUMPENVMAP,
                                            PS_TEXTUREMODES_BUMPENVMAP_LUM,
                                            PS_TEXTUREMODES_BUMPENVMAP);
    s->other_stage_input = (1u << 16) | (2u << 20);
    for (int i = 0; i < 4; i++) {
        s->dim_tex[i] = 2;
        s->snorm_tex[i] = (i & 1) == 0;
    }
    s->rgb_inputs[0] = ci(PS_REGISTER_T0, PS_REGISTER_T1, PS_REGISTER_T2, PS_REGISTER_T3);
    s->rgb_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD, PS_REGISTER_DISCARD, 0);
    s->alpha_inputs[0] = ci(PS_REGISTER_T0 | PS_CHANNEL_ALPHA, PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->alpha_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD, PS_REGISTER_DISCARD, 0);
    ps_tail(s);
}

static void ps_dotprod(PshState *s)   /* psh_differ bl_textures, minus the extras */
{
    memset(s, 0, sizeof(*s));
    s->combiner_control = 4;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_DOTPRODUCT,
                                            PS_TEXTUREMODES_DOT_ST,
                                            PS_TEXTUREMODES_PROJECT2D);
    s->dim_tex[0] = s->dim_tex[1] = s->dim_tex[2] = s->dim_tex[3] = 2;
    s->other_stage_input = PS_DOTMAPPING_MINUS1_TO_1_D3D |
                           (PS_DOTMAPPING_MINUS1_TO_1_D3D << 4) | (0u << 16) | (0u << 20);
    for (int i = 0; i < 4; i++) ps_modulate(s, i, PS_REGISTER_T0 + (i == 2 ? 2 : 0));
    ps_tail(s);
}

static void ps_border(PshState *s)   /* psh_differ bl_border */
{
    memset(s, 0, sizeof(*s));
    s->combiner_control = 2;
    s->shader_stage_program = stage_program(PS_TEXTUREMODES_PROJECT2D, PS_TEXTUREMODES_PROJECT2D,
                                            PS_TEXTUREMODES_PROJECT3D, PS_TEXTUREMODES_PROJECT2D);
    for (int i = 0; i < 4; i++) {
        s->dim_tex[i] = 2;
        s->addr_border[i] = 3;
        s->border_logical_size[i][0] = 32.0f;
        s->border_logical_size[i][1] = 32.0f;
        s->border_logical_size[i][2] = 1.0f;
        s->border_inv_real_size[i][0] = 1.0f / 40.0f;
        s->border_inv_real_size[i][1] = 1.0f / 40.0f;
        s->border_inv_real_size[i][2] = 1.0f;
    }
    s->rgb_inputs[0] = ci(PS_REGISTER_T0, PS_REGISTER_T1, PS_REGISTER_T2, PS_REGISTER_T3);
    s->rgb_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD, PS_REGISTER_DISCARD, 0);
    s->alpha_inputs[0] = ci(PS_REGISTER_T0 | PS_CHANNEL_ALPHA, PS_REGISTER_V0 | PS_CHANNEL_ALPHA,
                            PS_REGISTER_ZERO, PS_REGISTER_ZERO);
    s->alpha_outputs[0] = co(PS_REGISTER_R0, PS_REGISTER_DISCARD, PS_REGISTER_DISCARD, 0);
    ps_tail(s);
}

static void ps_aniso(PshState *s)   /* basic with a 4-probe anisotropic stage (#284) */
{
    ps_basic(s);
    s->tex_aniso[0] = 4;
}

/* ---- catalogue -------------------------------------------------------- */
typedef struct { const char *name; void (*fn)(VshState *); const char *prog; } VsCase;
typedef struct { const char *name; void (*fn)(PshState *); } PsCase;

static const VsCase vs_cases[] = {
    { "ff_unlit",       vs_ff_unlit, NULL },
    { "ff_lit2",        vs_ff_lit2, NULL },
    { "ff_skin_texgen", vs_ff_skin_texgen, NULL },
    { "prog_pass",      NULL, "passthrough.vshinc" },
    { "prog_proj",      NULL, "projection_vertex_shader_no_lighting.vshinc" },
    { "prog_ffapprox",  NULL, "fixed_function_approximation_shader.vshinc" },
    { "prog_skin4_a0",  NULL, "skin4_a0.vshinc" },
    { "prog_aa_cwrite", NULL, "americas_army_shader.vshinc" },
};
static const PsCase ps_cases[] = {
    { "vcolor",  ps_vertexcolor },
    { "basic",   ps_basic },
    { "game2",   ps_game2 },
    { "aniso4",  ps_aniso },
    { "dotprod", ps_dotprod },
    { "bumpenv", ps_bumpenv },
    { "border",  ps_border },
    { "stages8", ps_stages8 },
};

int main(int argc, char **argv)
{
    if (argc < 3) {
        fprintf(stderr, "usage: gen <outdir> <vshinc dir> [--no-opt-flag]\n");
        return 2;
    }
    g_out = argv[1];
    g_vsh_dir = argv[2];
    g_disable_opt = argc > 3 && !strcmp(argv[3], "--no-opt-flag");
    g_config.display.renderer = CONFIG_DISPLAY_RENDERER_VULKAN;
    g_mkdir_with_parents(g_out, 0755);
    glslang_initialize_process();

    GenVshGlslOptions vo = { .vulkan = true, .prefix_outputs = false,
                             .use_push_constants_for_uniform_attrs = true,
                             .ubo_binding = 0, .ubo_set = 1, .vertex_push_offset = 16 };
    GenPshGlslOptions po = { .vulkan = true, .ubo_binding = 1, .ubo_set = 1, .tex_binding = 0 };

    /*
     * Every filled-triangle draw on Vulkan carries a geometry stage
     * (pgraph_glsl_need_geom, geom.c:81: TRIANGLES, LINES and the flat-quad
     * TRIANGLES_ADJACENCY; quads, strips and fans are rewritten to one of
     * them), and its vertex shader is generated with prefixed outputs
     * (vk/shaders.c:883). So the realistic pipeline is VS' + GS + FS. The
     * unprefixed VS + FS pair is kept for the geometry stage's own leg.
     */
    GenVshGlslOptions vog = vo;
    vog.prefix_outputs = true;
    char *vs_spv[ARRAY_SIZE(vs_cases)], *vsp_spv[ARRAY_SIZE(vs_cases)];
    char *ps_spv[ARRAY_SIZE(ps_cases)];
    static VshState vst;
    for (size_t i = 0; i < ARRAY_SIZE(vs_cases); i++) {
        if (vs_cases[i].fn) vs_cases[i].fn(&vst); else vs_prog(&vst, vs_cases[i].prog);
        vs_spv[i] = emit("vs", vs_cases[i].name, GLSLANG_STAGE_VERTEX,
                         pgraph_glsl_gen_vsh(&vst, vo));
        char *pn = g_strdup_printf("%s_pfx", vs_cases[i].name);
        vsp_spv[i] = emit("vs", pn, GLSLANG_STAGE_VERTEX, pgraph_glsl_gen_vsh(&vst, vog));
    }
    PshState pst;
    for (size_t i = 0; i < ARRAY_SIZE(ps_cases); i++) {
        ps_cases[i].fn(&pst);
        ps_spv[i] = emit("fs", ps_cases[i].name, GLSLANG_STAGE_FRAGMENT,
                         pgraph_glsl_gen_psh(&pst, po));
    }
    GenGeomGlslOptions go = { .vulkan = true };
    GeomState gtri = { .primitive_mode = PRIM_TYPE_TRIANGLES, .smooth_shading = true };
    char *gs_tri = emit("gs", "tri_smooth", GLSLANG_STAGE_GEOMETRY, pgraph_glsl_gen_geom(&gtri, go));
    GeomState gadj = { .primitive_mode = PRIM_TYPE_TRIANGLES_ADJACENCY, .smooth_shading = false };
    char *gs_adj = emit("gs", "flatquad_adj", GLSLANG_STAGE_GEOMETRY, pgraph_glsl_gen_geom(&gadj, go));
    GeomState glin = { .primitive_mode = PRIM_TYPE_LINES, .smooth_shading = true };
    char *gs_lin = emit("gs", "lines", GLSLANG_STAGE_GEOMETRY, pgraph_glsl_gen_geom(&glin, go));

    char *mpath = g_strdup_printf("%s/manifest.txt", g_out);
    FILE *m = fopen(mpath, "w");
    /* The fixed set: every VS with the basic PS, every PS with ff_lit2, all
     * through the triangle GS. */
    for (size_t i = 0; i < ARRAY_SIZE(vs_cases); i++) {
        fprintf(m, "%s+basic+gtri %s %s %s\n", vs_cases[i].name, vsp_spv[i], ps_spv[1], gs_tri);
    }
    for (size_t i = 0; i < ARRAY_SIZE(ps_cases); i++) {
        if (i == 1) continue;
        fprintf(m, "ff_lit2+%s+gtri %s %s %s\n", ps_cases[i].name, vsp_spv[1], ps_spv[i], gs_tri);
    }
    /* the other geometry stages, and the same pairs with no geometry stage */
    fprintf(m, "ff_lit2+basic+gadj %s %s %s\n", vsp_spv[1], ps_spv[1], gs_adj);
    fprintf(m, "ff_lit2+basic+glines %s %s %s\n", vsp_spv[1], ps_spv[1], gs_lin);
    for (size_t i = 0; i < ARRAY_SIZE(vs_cases); i++) {
        fprintf(m, "%s+basic+nogs %s %s\n", vs_cases[i].name, vs_spv[i], ps_spv[1]);
    }
    fclose(m);
    fprintf(stderr, "manifest: %s\n", mpath);
    glslang_finalize_process();
    return 0;
}
