/*
 * Emits the pixel shader for Texture_BRDF's stage wiring (CUBEMAP, CUBEMAP,
 * BRDF on a 3D texture; R16B16 cube texels point-sampled, so tex_bytes16 is
 * set on the two feeding stages) for each renderer, so it can be compiled
 * with glslc and read for the BRDF lookup.  Links the psh-differ's objects:
 *
 *   make -C docs/testing/psh_differ
 *   cc -std=gnu11 -Idocs/testing/psh_differ/shim -Iinclude -I. \
 *      -Ihw/xbox/nv2a/pgraph/glsl $(pkg-config --cflags glib-2.0) \
 *      -o <out>/gen-brdf docs/lanes/pshaniso284/gen_brdf.c \
 *      docs/testing/psh_differ/build/psh.o docs/testing/psh_differ/build/common.o \
 *      $(pkg-config --libs glib-2.0) -lm
 *   <out>/gen-brdf <out>
 */
#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#include "ui/xemu-settings.h"
#include "psh.h"

PshDifferConfig g_config;

void psh_differ_record_unimpl(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    fprintf(stderr, "unimplemented: ");
    vfprintf(stderr, fmt, ap);
    fprintf(stderr, "\n");
    va_end(ap);
}

static uint32_t ci(uint8_t a, uint8_t b, uint8_t c, uint8_t d)
{
    return ((uint32_t)a << 24) | ((uint32_t)b << 16) | ((uint32_t)c << 8) | d;
}

int main(int argc, char **argv)
{
    static const struct {
        const char *name;
        GenPshGlslOptions opts;
        int renderer;
    } rs[] = {
        { "gl",   { false, false, false, 0,   0, 0, 0 }, CONFIG_DISPLAY_RENDERER_OPENGL },
        { "vk",   { true,  false, false, 0,   1, 0, 2 }, CONFIG_DISPLAY_RENDERER_VULKAN },
        { "gles", { false, false, true,  320, 0, 0, 0 }, CONFIG_DISPLAY_RENDERER_OPENGL },
    };
    const char *dir = argc > 1 ? argv[1] : ".";

    for (size_t r = 0; r < G_N_ELEMENTS(rs); r++) {
        PshState s;
        memset(&s, 0, sizeof(s));
        s.combiner_control = 1;
        s.shader_stage_program = PS_TEXTUREMODES_CUBEMAP |
                                 (PS_TEXTUREMODES_CUBEMAP << 5) |
                                 (PS_TEXTUREMODES_BRDF << 10);
        for (int i = 0; i < 2; i++) {
            s.dim_tex[i] = 2;
            s.tex_cubemap[i] = true;
            s.tex_hilo16[i] = true;
            s.tex_bytes16[i] = true;
            s.tex_aniso[i] = 1;
        }
        s.dim_tex[2] = 3;
        s.tex_aniso[2] = 1;
        s.rgb_inputs[0] = ci(PS_REGISTER_T2, PS_REGISTER_ZERO | PS_INPUTMAPPING_UNSIGNED_INVERT,
                             PS_REGISTER_ZERO, PS_REGISTER_ZERO);
        s.rgb_outputs[0] = PS_REGISTER_R0 << 4 | PS_REGISTER_DISCARD |
                           (PS_REGISTER_DISCARD << 8);
        s.smooth_shading = true;
        s.depth_needed = true;
        s.z_perspective = true;
        s.surface_zeta_format = NV097_SET_SURFACE_FORMAT_ZETA_Z24S8;
        s.depth_format = DEPTH_FORMAT_D24;
        s.final_inputs_0 = ci(PS_REGISTER_ZERO, PS_REGISTER_ZERO,
                              PS_REGISTER_ZERO, PS_REGISTER_R0);

        g_config.display.renderer = rs[r].renderer;
        MString *m = pgraph_glsl_gen_psh(&s, rs[r].opts);
        gchar *path = g_strdup_printf("%s/brdf-%s.frag", dir, rs[r].name);
        g_file_set_contents(path, mstring_get_str(m), -1, NULL);
        printf("%s\n", path);
        g_free(path);
        mstring_unref(m);
    }
    return 0;
}
