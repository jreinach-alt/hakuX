/*
 * Print the layout of a persisted shader_module_keys.bin record as JSON, from
 * this tree's own headers, for keys_coverage.py. LP64 on both sides (x86_64
 * here, aarch64 on the handhelds), so the layout carries, provided the device
 * build's structs are this tree's: the reader checks the record size.
 */
#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/vk/renderer.h"

#define F(field) \
    printf("  \"%s\": [%zu, %zu],\n", #field, \
           offsetof(PshState, field), sizeof(((PshState *)0)->field))

int main(void)
{
    printf("{\n");
    printf("  \"record\": %zu,\n", sizeof(ShaderModuleCacheKey));
    printf("  \"kind\": [%zu, %zu],\n", offsetof(ShaderModuleCacheKey, kind),
           sizeof(VkShaderStageFlagBits));
    printf("  \"psh_state\": %zu,\n", offsetof(ShaderModuleCacheKey, psh.state));
    printf("  \"psh_state_size\": %zu,\n", sizeof(PshState));
    printf("  \"psh_uber\": %zu,\n", offsetof(ShaderModuleCacheKey, psh.uber));
    printf("  \"vsh_state\": %zu,\n", offsetof(ShaderModuleCacheKey, vsh.state));
    printf("  \"vsh_state_size\": %zu,\n", sizeof(VshState));
    printf("  \"fragment_kind\": %d,\n", VK_SHADER_STAGE_FRAGMENT_BIT);
    printf("  \"vertex_kind\": %d,\n", VK_SHADER_STAGE_VERTEX_BIT);
    printf("  \"geometry_kind\": %d,\n", VK_SHADER_STAGE_GEOMETRY_BIT);
    F(combiner_control);
    F(shader_stage_program);
    F(other_stage_input);
    F(final_inputs_0);
    F(final_inputs_1);
    F(rgb_inputs);
    F(rgb_outputs);
    F(alpha_inputs);
    F(alpha_outputs);
    F(color_space_convert);
    F(point_sprite);
    F(rect_tex);
    F(snorm_tex);
    F(tex_hilo16);
    F(tex_comp0_const);
    F(tex_bytes16);
    F(tex_y16);
    F(tex_aniso);
    F(tex_signed);
    F(compare_mode);
    F(alphakill);
    F(colorkey_mode);
    F(conv_tex);
    F(tex_x8y24);
    F(dim_tex);
    F(tex_cubemap);
    F(addr_border);
    F(border_logical_size);
    F(border_inv_real_size);
    F(shadow_map);
    F(tex_depth_float);
    F(shadow_depth_func);
    F(alpha_test);
    F(alpha_func);
    F(window_clip_exclusive);
    F(window_clip_count);
    F(smooth_shading);
    F(fixed_function);
    F(two_side_light);
    F(stipple);
    F(fog_enable);
    F(fog_mode);
    F(depth_clipping);
    F(cull_near_far);
    F(z_perspective);
    F(noperspective);
    F(depth_needed);
    F(surface_zeta_format);
    F(depth_format);
    printf("  \"end\": 0\n}\n");
    return 0;
}
