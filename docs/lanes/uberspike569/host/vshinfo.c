/*
 * Print VshState's field offsets as JSON, from this tree's glsl/vsh.h, for
 * keys_coverage.py's vertex read. The key's vsh.state offset (4) and record size
 * come from keylayout.json (keyinfo.c); this needs only the glsl header, so it
 * builds against psh_differ's shim.
 */
#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/glsl/vsh.h"

#define F(field) \
    printf("  \"%s\": [%zu, %zu],\n", #field, \
           offsetof(VshState, field), sizeof(((VshState *)0)->field))

int main(void)
{
    printf("{\n");
    printf("  \"size\": %zu,\n", sizeof(VshState));
    F(surface_scale_factor);
    F(compressed_attrs);
    F(uniform_attrs);
    F(swizzle_attrs);
    F(fog_enable);
    F(foggen);
    F(lighting);
    F(light);
    F(normalization);
    F(local_eye);
    F(emission_src);
    F(ambient_src);
    F(diffuse_src);
    F(specular_src);
    F(back_emission_src);
    F(back_ambient_src);
    F(back_diffuse_src);
    F(back_specular_src);
    F(specular_enable);
    F(separate_specular);
    F(ignore_specular_alpha);
    F(two_side_light);
    F(point_params_enable);
    F(point_size);
    F(point_params);
    F(smooth_shading);
    F(z_perspective);
    F(noperspective);
    F(aa_offset_x);
    F(is_fixed_function);
    printf("  \"program\": [%zu, %zu],\n", offsetof(VshState, programmable),
           sizeof(ProgrammableVshState));
    printf("  \"end\": 0\n}\n");
    return 0;
}
