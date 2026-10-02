/*
 * Host check for #569's uber vertex stage (glsl/vsh-uber.c): generates, for
 * a set of vertex states, the specialised shader (vsh.c) and the family's
 * uber shader, each with a dump of every output appended, and the uniform
 * block both read (the uber layout, of which the specialised block is a
 * prefix -- BUILD.md 2.1). vsrender runs each pair on lavapipe over the same
 * vertices; vshcheck.sh compares the dumps bit for bit.
 *
 *   vshhost --out DIR [--keys shader_module_keys.bin --keyrec N --keyoff N]
 *           [--random N] [--seed S] [--prefix 0|1]
 *
 * States: every distinct vertex state in a key file (a title's own), then N
 * seeded random ones, fixed function and programs alternating. A state the
 * uber stage refuses (pgraph_glsl_vsh_uber_covers) is counted, not written.
 *
 * DIR/manifest: one line per pair, "id label compressed_mask".
 */
#include "qemu/osdep.h"
#include "vsh.h"
#include "vsh-uber.h"

static uint32_t rng = 0x569abcu;
static int mutate;
static uint32_t rnd(void)
{
    rng ^= rng << 13;
    rng ^= rng >> 17;
    rng ^= rng << 5;
    return rng;
}
static float frand(float lo, float hi)
{
    return lo + (hi - lo) * (rnd() & 0xFFFFFF) / (float)0x1000000;
}
static int irand(int n) { return rnd() % n; }

/* std140 for VshUniforms' element types */
static size_t type_align(enum UniformElementType t, size_t count)
{
    size_t a;
    switch (t) {
    case UniformElementType_vec2: case UniformElementType_ivec2: a = 8; break;
    case UniformElementType_vec3: case UniformElementType_vec4:
    case UniformElementType_ivec4: case UniformElementType_mat2: a = 16; break;
    default: a = 4; break;
    }
    return count > 1 ? 16 : a;
}
static size_t type_size(enum UniformElementType t)
{
    switch (t) {
    case UniformElementType_vec2: case UniformElementType_ivec2: return 8;
    case UniformElementType_vec3: return 12;
    case UniformElementType_vec4: case UniformElementType_ivec4:
    case UniformElementType_mat2: return 16;
    default: return 4;
    }
}

/* The uber block's bytes: random values in each member, the uber uniform at
 * the end. Returns the size. */
static size_t build_ubo(const VshState *s, uint8_t *buf, size_t cap)
{
    size_t off = 0;
    memset(buf, 0, cap);
    for (int i = 0; i < VshUniform__COUNT; i++) {
        const UniformInfo *info = &VshUniformInfo[i];
        if (i == VshUniform_inlineValue && !s->uniform_attrs) {
            continue;
        }
        size_t al = type_align(info->type, info->count);
        off = (off + al - 1) & ~(al - 1);
        size_t esz = type_size(info->type);
        size_t stride = info->count > 1 ? ((esz + 15) & ~15) : esz;
        for (size_t e = 0; e < info->count; e++) {
            float *f = (float *)(buf + off + e * stride);
            for (size_t k = 0; k < esz / 4; k++) {
                float v = frand(-1.5f, 1.5f);
                if (i == VshUniform_ltc1 || i == VshUniform_ltctxa ||
                    i == VshUniform_ltctxb || i == VshUniform_material_alpha ||
                    i == VshUniform_material_alpha_back ||
                    i == VshUniform_pointParams) {
                    v = frand(0.f, 1.f);
                }
                if (i == VshUniform_ltc1 && k == 0) {
                    v = frand(0.f, 4.f); /* light range */
                }
                f[k] = v;
            }
        }
        if (i == VshUniform_surfaceSize) {
            float *f = (float *)(buf + off);
            f[0] = 640.f;
            f[1] = 480.f;
        }
        if (i == VshUniform_clipRange) {
            float *f = (float *)(buf + off);
            f[0] = 0.f;
            f[1] = irand(2) ? 16777215.f : 3.0e38f;
        }
        if (i == VshUniform_ringPhase) {
            float *f = (float *)(buf + off);
            f[0] = irand(3) ? (float)irand(6) : -1.f;
        }
        off += info->count > 1 ? stride * info->count : esz;
    }
    off = (off + 15) & ~(size_t)15;
    uint32_t ub[VSH_UBER_VEC4S * 4];
    pgraph_glsl_vsh_uber_values(s, true, ub);
    if (mutate) {
        /* the check must see a wrong uniform: a flag in fixed function, every
         * slot's input A swizzle in a program */
        if (s->is_fixed_function) {
            ub[0] ^= VSH_UBER_F_SPECULAR | VSH_UBER_F_FOG;
        } else {
            for (int k = 0; k < s->programmable.program_length; k++) {
                ub[(VSH_UBER_PROG_BASE + k) * 4 + 1] ^= 0x1B;
            }
        }
    }
    memcpy(buf + off, ub, sizeof(ub));
    off += sizeof(ub);
    assert(off <= cap);
    return off;
}

/* A dump of every output, appended to both shaders: 13 uvec4 a vertex. */
static const char dump_decl[] =
    "layout(set = 2, binding = 0, std430) buffer UbDump { uvec4 ubd[]; };\n"
    "void ubDump() {\n"
    "  int b = gl_VertexIndex * 16;\n"
    "  ubd[b + 0] = floatBitsToUint(vtxD0);\n"
    "  ubd[b + 1] = floatBitsToUint(vtxD1);\n"
    "  ubd[b + 2] = floatBitsToUint(vtxB0);\n"
    "  ubd[b + 3] = floatBitsToUint(vtxB1);\n"
    "  ubd[b + 4] = floatBitsToUint(vec4(vtxFog, vtxFogSpecial, triMZ, vtxPointSize));\n"
    "  ubd[b + 5] = floatBitsToUint(vtxT0);\n"
    "  ubd[b + 6] = floatBitsToUint(vtxT1);\n"
    "  ubd[b + 7] = floatBitsToUint(vtxT2);\n"
    "  ubd[b + 8] = floatBitsToUint(vtxT3);\n"
    "  ubd[b + 9] = floatBitsToUint(vtxPos0);\n"
    "  ubd[b + 10] = floatBitsToUint(gl_Position);\n"
    "  ubd[b + 11] = floatBitsToUint(vec4(gl_PointSize, 0.0, 0.0, 0.0));\n"
    "}\n";

static void write_with_dump(const char *path, const char *glsl)
{
    const char *m = strstr(glsl, "void main() {");
    const char *end = strrchr(glsl, '}');
    assert(m && end && end > m);
    FILE *f = fopen(path, "w");
    fwrite(glsl, 1, m - glsl, f);
    fputs(dump_decl, f);
    fwrite(m, 1, end - m, f);
    fputs("  ubDump();\n}\n", f);
    fclose(f);
}

static void random_common(VshState *s)
{
    s->surface_scale_factor = 1 + irand(2);
    s->smooth_shading = irand(4) != 0;
    s->noperspective = irand(5) == 0;
    s->compressed_attrs = irand(6) == 0 ? (1 << (2 + irand(10))) : 0;
    s->uniform_attrs = irand(4) ? (rnd() & 0xFFFF) & ~s->compressed_attrs : 0;
    s->swizzle_attrs = irand(3) == 0 ? (rnd() & 0xFFFF) &
                                           ~(s->compressed_attrs | s->uniform_attrs)
                                     : 0;
    s->fog_enable = irand(2);
    s->foggen = s->fog_enable ? irand(5) : 0;
    s->lighting = irand(2);
    if (s->lighting) {
        for (int i = 0; i < NV2A_MAX_LIGHTS; i++) {
            s->light[i] = irand(3) ? LIGHT_OFF : irand(4);
        }
    }
    s->normalization = irand(2);
    s->local_eye = irand(3) == 0;
    enum MaterialColorSource *src[] = {
        &s->emission_src, &s->ambient_src, &s->diffuse_src, &s->specular_src,
        &s->back_emission_src, &s->back_ambient_src, &s->back_diffuse_src,
        &s->back_specular_src,
    };
    for (int i = 0; i < 8; i++) {
        *src[i] = irand(3);
    }
    s->specular_enable = irand(2);
    s->separate_specular = irand(2);
    s->ignore_specular_alpha = irand(2);
    s->two_side_light = irand(3) == 0;
    s->point_params_enable = irand(4) == 0;
    s->point_size = irand(3) ? frand(0.f, 8.f) : 1.f;
    s->z_perspective = irand(2);
}

static void random_ff(VshState *s)
{
    memset(s, 0, sizeof(*s));
    random_common(s);
    s->is_fixed_function = true;
    FixedFunctionVshState *ff = &s->fixed_function;
    ff->skinning = irand(3) ? SKINNING_OFF : irand(7);
    for (int i = 0; i < 4; i++) {
        ff->texture_matrix_enable[i] = irand(3) == 0;
        for (int j = 0; j < 4; j++) {
            int g = irand(2) ? TEXGEN_DISABLE : irand(6);
            if (g == TEXGEN_SPHERE_MAP && j >= 2) g = TEXGEN_EYE_LINEAR;
            if ((g == TEXGEN_REFLECTION_MAP || g == TEXGEN_NORMAL_MAP) && j >= 3)
                g = TEXGEN_OBJECT_LINEAR;
            ff->texgen[i][j] = g;
        }
    }
}

static uint32_t put(uint32_t w, int start, int len, uint32_t v)
{
    uint32_t m = ((len == 32) ? 0xFFFFFFFFu : ((1u << len) - 1)) << start;
    return (w & ~m) | ((v << start) & m);
}

/* One random slot the specialised translator compiles. */
static void random_slot(uint32_t t[4], bool writes_c, bool last)
{
    memset(t, 0, 16);
    int mac = irand(5) ? irand(14) : 0;
    int ilu = irand(3) ? 0 : irand(8);
    if (!mac && !ilu) mac = 1 + irand(12);
    t[1] = put(t[1], 21, 4, mac);
    t[1] = put(t[1], 25, 3, ilu);
    bool a0x = irand(6) == 0;
    int cidx = a0x ? 10 + irand(160) : irand(192);
    t[1] = put(t[1], 13, 8, cidx);
    t[1] = put(t[1], 9, 4, irand(16));
    t[1] = put(t[1], 8, 1, irand(2));
    t[1] = put(t[1], 0, 8, rnd() & 0xFF);
    t[2] = put(t[2], 28, 4, irand(13));
    t[2] = put(t[2], 26, 2, 1 + irand(3));
    t[2] = put(t[2], 25, 1, irand(2));
    t[2] = put(t[2], 17, 8, rnd() & 0xFF);
    t[2] = put(t[2], 13, 4, irand(13));
    t[2] = put(t[2], 11, 2, 1 + irand(3));
    t[2] = put(t[2], 10, 1, irand(2));
    t[2] = put(t[2], 2, 8, rnd() & 0xFF);
    int creg = irand(13);
    t[2] = put(t[2], 0, 2, creg >> 2);
    t[3] = put(t[3], 30, 2, creg & 3);
    t[3] = put(t[3], 28, 2, 1 + irand(3));
    t[3] = put(t[3], 24, 4, irand(16));
    t[3] = put(t[3], 20, 4, irand(13));
    t[3] = put(t[3], 16, 4, irand(16));
    int omux = irand(2);
    if (mac == 13) omux = 1; /* an ARL routed to an output is refused */
    t[3] = put(t[3], 2, 1, omux);
    t[3] = put(t[3], 12, 4, irand(3) ? rnd() & 0xF : 0);
    bool orb_c = writes_c && irand(3) == 0;
    t[3] = put(t[3], 11, 1, orb_c ? 0 : 1);
    static const int oregs[] = { 0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 0, 5 };
    int addr = orb_c ? (irand(8) ? irand(192) : 192 + irand(60))
                     : oregs[irand(ARRAY_SIZE(oregs))];
    t[3] = put(t[3], 3, 8, addr);
    t[3] = put(t[3], 1, 1, a0x);
    t[3] = put(t[3], 0, 1, last);
}

static void random_prog(VshState *s)
{
    memset(s, 0, sizeof(*s));
    random_common(s);
    s->is_fixed_function = false;
    bool writes_c = irand(4) == 0;
    int n = 1 + irand(24);
    s->programmable.program_length = n;
    for (int i = 0; i < n; i++) {
        random_slot(s->programmable.program_data[i], writes_c, i == n - 1);
    }
}

int main(int argc, char **argv)
{
    const char *out = NULL, *keys = NULL;
    int nrand = 0, keyrec = 0, keyoff = 0, keykind_off = 0, vkind = 0;
    int prefix = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--out")) out = argv[++i];
        else if (!strcmp(argv[i], "--keys")) keys = argv[++i];
        else if (!strcmp(argv[i], "--keyrec")) keyrec = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--keyoff")) keyoff = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--vkind")) vkind = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--random")) nrand = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--seed")) rng = strtoul(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "--prefix")) prefix = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--mutate")) mutate = 1;
        else { fprintf(stderr, "vshhost: unknown %s\n", argv[i]); return 2; }
    }
    if (!out) {
        fprintf(stderr, "vshhost --out DIR ...\n");
        return 2;
    }
    g_mkdir_with_parents(out, 0755);

    GArray *states = g_array_new(FALSE, TRUE, sizeof(VshState));
    GPtrArray *labels = g_ptr_array_new();
    if (keys) {
        gchar *data;
        gsize len;
        if (!g_file_get_contents(keys, &data, &len, NULL) || !keyrec ||
            len % keyrec) {
            fprintf(stderr, "vshhost: cannot read %s as %d-byte records\n",
                    keys, keyrec);
            return 1;
        }
        int n = 0;
        for (gsize o = 0; o < len; o += keyrec) {
            uint32_t kind;
            memcpy(&kind, data + o + keykind_off, 4);
            if (kind != (uint32_t)vkind) continue;
            VshState s;
            memcpy(&s, data + o + keyoff, sizeof(s));
            bool dup = false;
            for (guint j = 0; j < states->len && !dup; j++) {
                dup = !memcmp(&g_array_index(states, VshState, j), &s,
                              sizeof(s));
            }
            if (dup) continue;
            g_array_append_val(states, s);
            g_ptr_array_add(labels, g_strdup_printf("key%d%s", n++,
                            s.is_fixed_function ? "ff" : "prog"));
        }
        g_free(data);
    }
    for (int i = 0; i < nrand; i++) {
        VshState s;
        if (i & 1) random_prog(&s); else random_ff(&s);
        g_array_append_val(states, s);
        g_ptr_array_add(labels, g_strdup_printf("rand%d%s", i,
                        s.is_fixed_function ? "ff" : "prog"));
    }

    GenVshGlslOptions opts = {
        .vulkan = true,
        .prefix_outputs = prefix,
        .use_push_constants_for_uniform_attrs = false,
        .ubo_binding = 0,
        .ubo_set = 1,
        .vertex_push_offset = 16,
    };
    char *mpath = g_strdup_printf("%s/manifest", out);
    FILE *man = fopen(mpath, "w");
    int written = 0, refused = 0;
    static uint8_t ubo[65536];
    for (guint i = 0; i < states->len; i++) {
        VshState *s = &g_array_index(states, VshState, i);
        if (!pgraph_glsl_vsh_uber_covers(s)) {
            refused++;
            fprintf(stderr, "refused %s\n", (char *)labels->pdata[i]);
            continue;
        }
        VshState fam;
        pgraph_glsl_vsh_uber_family(s, &fam);
        MString *spec = pgraph_glsl_gen_vsh(s, opts);
        MString *uber = pgraph_glsl_gen_vsh_uber(&fam, opts);
        char *p = g_strdup_printf("%s/spec_%d.vert", out, written);
        write_with_dump(p, mstring_get_str(spec));
        g_free(p);
        p = g_strdup_printf("%s/uber_%d.vert", out, written);
        write_with_dump(p, mstring_get_str(uber));
        g_free(p);
        size_t n = build_ubo(s, ubo, sizeof(ubo));
        p = g_strdup_printf("%s/ubo_%d.bin", out, written);
        g_file_set_contents(p, (const char *)ubo, n, NULL);
        g_free(p);
        fprintf(man, "%d %s %u\n", written, (char *)labels->pdata[i],
                s->compressed_attrs);
        mstring_unref(spec);
        mstring_unref(uber);
        written++;
    }
    fclose(man);
    printf("vshhost: %d pairs written, %d refused, to %s\n", written, refused,
           out);
    return 0;
}
