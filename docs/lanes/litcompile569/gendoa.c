/*
 * gendoa: regenerate a title's shader modules from the device's
 * shader_module_keys.bin, with hakuX's real GLSL generators on the host.
 *
 *   gendoa <shader_module_keys.bin> <outdir>
 *
 * Each record is a raw ShaderModuleCacheKey (vk/renderer.h), written by
 * shader_module_key_persist() (vk/shaders.c). For each one this writes
 * <outdir>/<k>_<xxh3(glsl)>.{glsl,spv}, k = vs/gs/fs, and a line on stdout:
 *   <k> <xxh3 as %016lx> <lit 0/1> <fixed_function 0/1> <glsl bytes> <spv bytes>
 * The device's spv_cache names each file %016lx of XXH3_64bits(glsl)
 * (vk/glsl.c), so a regenerated file with a device file's name has
 * byte-identical GLSL, and the .spv pair checks glslang too.
 *
 * Built by build_gendoa.sh against the generator of a given tree, with
 * turnipcost569's carve (gen/carve_all.py) and glslang (gen.c's compile()).
 */
#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#include "ui/xemu-settings.h"
#include "shaders.h"

#include <glslang/Include/glslang_c_interface.h>
#define XXH_INLINE_ALL
#include <xxhash.h>

PshDifferConfig g_config;
void psh_differ_record_unimpl(const char *fmt, ...) { (void)fmt; }

#include "resource_limits.inc"

/* vk/renderer.h's ShaderModuleCacheKey; VkShaderStageFlagBits is a 32-bit enum. */
typedef struct ShaderModuleCacheKey {
    uint32_t kind;
    union {
        struct { VshState state; GenVshGlslOptions glsl_opts; } vsh;
        struct { GeomState state; GenGeomGlslOptions glsl_opts; } geom;
        struct { PshState state; GenPshGlslOptions glsl_opts; } psh;
    };
} ShaderModuleCacheKey;

enum { STAGE_VERTEX = 0x1, STAGE_GEOMETRY = 0x8, STAGE_FRAGMENT = 0x10 };

/* gen.c's compile(), verbatim in its options (vk/glsl.c's). */
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
    glslang_spv_options_t o = { .validate = true, .disable_optimizer = false };
    glslang_program_SPIRV_generate_with_options(pr, stage, &o);
    size_t n = glslang_program_SPIRV_get_size(pr);
    uint32_t *w = g_malloc(n * 4);
    glslang_program_SPIRV_get(pr, w);
    g_file_set_contents(path, (const char *)w, n * 4, NULL);
    g_free(w);
    glslang_program_delete(pr);
    glslang_shader_delete(sh);
    return n * 4;
}

int main(int argc, char **argv)
{
    if (argc < 3) {
        fprintf(stderr, "usage: gendoa <shader_module_keys.bin> <outdir>\n");
        return 2;
    }
    gchar *data;
    gsize len;
    if (!g_file_get_contents(argv[1], &data, &len, NULL)) {
        fprintf(stderr, "cannot read %s\n", argv[1]);
        return 1;
    }
    if (len % sizeof(ShaderModuleCacheKey)) {
        fprintf(stderr, "%zu bytes is not a whole number of %zu-byte keys\n",
                (size_t)len, sizeof(ShaderModuleCacheKey));
        return 1;
    }
    size_t n = len / sizeof(ShaderModuleCacheKey);
    fprintf(stderr, "%zu keys of %zu bytes\n", n, sizeof(ShaderModuleCacheKey));
    g_config.display.renderer = CONFIG_DISPLAY_RENDERER_VULKAN;
    g_mkdir_with_parents(argv[2], 0755);
    glslang_initialize_process();

    const ShaderModuleCacheKey *keys = (const ShaderModuleCacheKey *)data;
    for (size_t i = 0; i < n; i++) {
        const ShaderModuleCacheKey *k = &keys[i];
        MString *m;
        const char *tag;
        glslang_stage_t st;
        int lit = 0, ff = 0;
        switch (k->kind) {
        case STAGE_VERTEX:
            m = pgraph_glsl_gen_vsh(&k->vsh.state, k->vsh.glsl_opts);
            tag = "vs"; st = GLSLANG_STAGE_VERTEX;
            ff = k->vsh.state.is_fixed_function;
            lit = ff && k->vsh.state.lighting;
            break;
        case STAGE_GEOMETRY:
            m = pgraph_glsl_gen_geom(&k->geom.state, k->geom.glsl_opts);
            tag = "gs"; st = GLSLANG_STAGE_GEOMETRY;
            break;
        case STAGE_FRAGMENT:
            m = pgraph_glsl_gen_psh(&k->psh.state, k->psh.glsl_opts);
            tag = "fs"; st = GLSLANG_STAGE_FRAGMENT;
            break;
        default:
            fprintf(stderr, "key %zu: kind 0x%x\n", i, k->kind);
            return 1;
        }
        const char *glsl = mstring_get_str(m);
        uint64_t h = XXH3_64bits(glsl, strlen(glsl));
        char *gp = g_strdup_printf("%s/%s_%016" PRIx64 ".glsl", argv[2], tag, h);
        char *sp = g_strdup_printf("%s/%s_%016" PRIx64 ".spv", argv[2], tag, h);
        g_file_set_contents(gp, glsl, -1, NULL);
        size_t sb = compile(st, glsl, sp);
        printf("%s %016" PRIx64 " %d %d %zu %zu\n", tag, h, lit, ff, strlen(glsl), sb);
        mstring_unref(m);
        g_free(gp);
        g_free(sp);
    }
    glslang_finalize_process();
    return 0;
}
