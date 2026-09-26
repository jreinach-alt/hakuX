/* Emit vsh-ff.c's GLSL (header and body) for one fixed-function VshState.
 * Adapted from docs/lanes/shadetie224/vshemit/emit.c.
 * argv: skinning lighting */
#include "qemu/osdep.h"
#include "common.h"
#include "vsh-ff.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    VshState st;
    memset(&st, 0, sizeof(st));
    st.fixed_function.skinning = argc > 1 ? atoi(argv[1]) : SKINNING_OFF;
    st.lighting = argc > 2 ? atoi(argv[2]) : 0;
    st.light[0] = st.lighting ? LIGHT_INFINITE : LIGHT_OFF;
    st.emission_src = st.ambient_src = st.diffuse_src = st.specular_src =
        MATERIAL_COLOR_SRC_MATERIAL;
    MString *h = mstring_new(), *b = mstring_new();
    pgraph_glsl_gen_vsh_ff(&st, h, b);
    printf("//HEADER\n%s\n//BODY\n%s\n", mstring_get_str(h),
           mstring_get_str(b));
    return 0;
}
