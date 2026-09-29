/*
 * Host test of nv2a_profile_shader_keydiff() (pgraph/profile.c), #569 P1.
 * Built by keydiff_test.py with the desktop build's flags. The script cuts
 * the function and its enum out of profile.c into keydiff_fn.inc; this file
 * gives it the real ShaderState and a stand-in for the two stats it writes.
 *
 * Each case changes one field in the middle of its class (not the first
 * or last member), so a class whose compare misses a member fails here.
 */
#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/glsl/shaders.h"

static struct {
    struct {
        unsigned int keydiff[9];
        uint64_t instr_ns;
    } shader_stats;
} g_nv2a_stats;
typedef __typeof__(g_nv2a_stats.shader_stats) ShaderPipelineStats;

static int64_t nv2a_clock_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

#include "keydiff_fn.inc"

static int fails;

static void expect(const char *name, const ShaderState *a, const ShaderState *b,
                   unsigned int want)
{
    ShaderPipelineStats before = g_nv2a_stats.shader_stats;
    nv2a_profile_shader_keydiff(a, b);
    unsigned int got = 0;
    for (int i = 0; i < 9; i++) {
        unsigned int d = g_nv2a_stats.shader_stats.keydiff[i] - before.keydiff[i];
        if (d > 1) {
            got |= 1u << 31;
        }
        got |= d << i;
    }
    printf("%-4s %-40s want %03x got %03x\n", got == want ? "ok" : "FAIL", name,
           want, got);
    fails += got != want;
}

int main(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    static ShaderState base, x;
    memset(&base, 0, sizeof(base));
    base.vsh.is_fixed_function = false;
    base.vsh.programmable.program_length = 3;
    base.vsh.programmable.program_data[1][2] = 0x1234;

#define CASE(name, stmt, want) \
    do { x = base; stmt; expect(name, &base, &x, want); } while (0)

    CASE("identical", (void)0, 1u << SHADER_KEYDIFF_NONE);
    {
        ShaderPipelineStats before = g_nv2a_stats.shader_stats;
        nv2a_profile_shader_keydiff(NULL, &base);
        int d = g_nv2a_stats.shader_stats.keydiff[SHADER_KEYDIFF_NOPREV] -
                before.keydiff[SHADER_KEYDIFF_NOPREV];
        printf("%-4s %-40s\n", d == 1 ? "ok" : "FAIL", "NULL prev counts NOPREV");
        fails += d != 1;
    }
    CASE("vp word", x.vsh.programmable.program_data[1][2] = 7,
         1u << SHADER_KEYDIFF_VP);
    CASE("vp length", x.vsh.programmable.program_length = 4,
         1u << SHADER_KEYDIFF_VP);
    CASE("prog -> ff", x.vsh.is_fixed_function = true,
         1u << SHADER_KEYDIFF_VP);
    CASE("vsh lighting (shared)", x.vsh.lighting = true,
         1u << SHADER_KEYDIFF_FF);
    CASE("vsh specular_src (shared)", x.vsh.specular_src = 2,
         1u << SHADER_KEYDIFF_FF);
    CASE("vsh point_params[3]", x.vsh.point_params[3] = 1.5f,
         1u << SHADER_KEYDIFF_FL);
    CASE("psh border size", x.psh.border_logical_size[2][1] = 64.f,
         1u << SHADER_KEYDIFF_FL);
    CASE("combiner rgb_inputs[4]", x.psh.rgb_inputs[4] = 0x0a0b0c0d,
         1u << SHADER_KEYDIFF_CB);
    CASE("combiner final_inputs_1", x.psh.final_inputs_1 = 3,
         1u << SHADER_KEYDIFF_CB);
    CASE("tex dim_tex[2]", x.psh.dim_tex[2] = 3, 1u << SHADER_KEYDIFF_TX);
    CASE("tex compare_mode[1][2]", x.psh.compare_mode[1][2] = true,
         1u << SHADER_KEYDIFF_TX);
    CASE("tex stage program", x.psh.shader_stage_program = 0x21,
         1u << SHADER_KEYDIFF_TX);
    CASE("psh alpha_test (other)", x.psh.alpha_test = true,
         1u << SHADER_KEYDIFF_PO);
    CASE("psh window_clip_count", x.psh.window_clip_count = 2,
         1u << SHADER_KEYDIFF_PO);
    CASE("two classes", (x.psh.rgb_outputs[1] = 5, x.psh.tex_cubemap[0] = 1),
         (1u << SHADER_KEYDIFF_CB) | (1u << SHADER_KEYDIFF_TX));

    base.vsh.is_fixed_function = true;
    memset(&base.vsh.programmable, 0, sizeof(base.vsh.programmable));
    CASE("ff texgen[2][1]", x.vsh.fixed_function.texgen[2][1] = 1,
         1u << SHADER_KEYDIFF_FF);
    CASE("ff identical", (void)0, 1u << SHADER_KEYDIFF_NONE);

    /* The inputs are left as they were: the compare works on copies */
    x = base;
    x.psh.rgb_inputs[4] = 9;
    ShaderState keep = x;
    nv2a_profile_shader_keydiff(&base, &x);
    int same = !memcmp(&keep, &x, sizeof(x));
    printf("%-4s inputs untouched\n", same ? "ok" : "FAIL");
    fails += !same;

    printf("instr_ns total %llu over the calls\n",
           (unsigned long long)g_nv2a_stats.shader_stats.instr_ns);
    printf("%s\n", fails ? "FAILED" : "PASSED");
    return fails ? 1 : 0;
}
