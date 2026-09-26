#include "qemu/osdep.h"
#include "common.h"
#include "vsh-ff.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
/* argv: light0 light1 local_eye sep_spec spec_enable two_side [vc] [prog] */
int main(int argc, char **argv)
{
    VshState st;
    memset(&st, 0, sizeof(st));
    st.lighting = true;
    st.light[0] = argc > 1 ? atoi(argv[1]) : LIGHT_INFINITE;
    st.light[1] = argc > 2 ? atoi(argv[2]) : LIGHT_OFF;
    st.local_eye = argc > 3 ? atoi(argv[3]) : 0;
    st.separate_specular = argc > 4 ? atoi(argv[4]) : 1;
    st.specular_enable = argc > 5 ? atoi(argv[5]) : 1;
    st.two_side_light = argc > 6 ? atoi(argv[6]) : 0;
    st.emission_src = st.ambient_src = st.diffuse_src = st.specular_src =
        MATERIAL_COLOR_SRC_MATERIAL;
    if (argc > 7 && atoi(argv[7])) {
        st.diffuse_src = MATERIAL_COLOR_SRC_DIFFUSE;
        st.ambient_src = MATERIAL_COLOR_SRC_SPECULAR;
        st.emission_src = MATERIAL_COLOR_SRC_DIFFUSE;
        st.specular_src = MATERIAL_COLOR_SRC_SPECULAR;
    }
    MString *h = mstring_new(), *b = mstring_new();
    if (argc > 8 && atoi(argv[8]))
        pgraph_glsl_append_vsh_prog_lighting(&st, h, b);
    else
        pgraph_glsl_gen_vsh_ff(&st, h, b);
    printf("//HEADER\n%s\n//BODY\n%s\n", mstring_get_str(h), mstring_get_str(b));
    return 0;
}
