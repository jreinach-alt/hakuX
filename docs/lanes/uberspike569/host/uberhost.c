/*
 * Host checks for the #569 P6 combiner ubershader (glsl/psh-uber.c).
 *
 * For every psh_differ baseline and a seeded set of random combiner programs
 * on top of each, it generates the specialised shader (psh.c) and the family
 * ubershader (psh-uber.c), and:
 *
 *   1. SPLICE: removes the combiner block from the specialised text and the
 *      interpreter from the uber text, and requires what is left to be
 *      byte-identical. That is the claim the design rests on -- nothing in
 *      psh.c outside the combiner block reads the combiner fields -- checked
 *      on generated text rather than by reading.
 *   2. DUMP: writes each pair (spec_N.frag, uber_N.frag) and the combiner
 *      uniform the ubershader would be staged with (comb_N.bin, 36 x u32)
 *      for glslang and for the lavapipe render check (render.c).
 *
 *   uberhost --out DIR [--per-baseline N] [--seed S]
 *
 * Exit 0 when every covered state passes SPLICE.
 */

#define main psh_differ_main
#include "differ.c"
#undef main

#include "psh-uber.h"

static uint32_t rng_state;

static uint32_t rnd(void)
{
    rng_state ^= rng_state << 13;
    rng_state ^= rng_state >> 17;
    rng_state ^= rng_state << 5;
    return rng_state;
}

static uint32_t pick(const uint8_t *v, int n)
{
    return v[rnd() % n];
}

/* A source byte: reg | chan | map. Reserved 6 and 7 now and then; EF_PROD
 * only where the caller allows it (psh.c dereferences NULL for EF_PROD read
 * by E or F, so no guest can use that and it is not generated). */
static uint8_t rand_input(bool allow_ef)
{
    static const uint8_t regs[] = { 0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13,
                                    14, 15, 4, 8, 12, 12, 13, 6 };
    uint8_t reg;
    do {
        reg = pick(regs, ARRAY_SIZE(regs));
    } while (!allow_ef && reg == 15);
    return reg | (rnd() & 0x10) | (rnd() & 0xE0);
}

static uint32_t rand_inputs(void)
{
    return ci(rand_input(true), rand_input(true), rand_input(true),
              rand_input(true));
}

static uint8_t rand_dest(void)
{
    static const uint8_t dests[] = { 0, 0, 0, 4, 5, 8, 9, 10, 11, 12, 12, 12,
                                     13, 13, 1, 3, 14, 7 };
    return pick(dests, ARRAY_SIZE(dests));
}

static uint32_t rand_output(void)
{
    static const uint8_t maps[] = { 0x00, 0x00, 0x08, 0x10, 0x18, 0x20, 0x28,
                                    0x30, 0x38 };
    int flags = (rnd() & 7) | pick(maps, ARRAY_SIZE(maps)) | (rnd() & 0xC0);
    return co(rand_dest(), rand_dest(), rand_dest(), flags);
}

static void randomise_combiners(PshState *s)
{
    int n = rnd() % 9;
    uint32_t flags = 0;
    if (rnd() & 1) flags |= PS_COMBINERCOUNT_MUX_MSB;
    if (rnd() & 1) flags |= PS_COMBINERCOUNT_UNIQUE_C0;
    if (rnd() & 1) flags |= PS_COMBINERCOUNT_UNIQUE_C1;
    s->combiner_control = n | (flags << 8);

    memset(s->rgb_inputs, 0, sizeof(s->rgb_inputs));
    memset(s->rgb_outputs, 0, sizeof(s->rgb_outputs));
    memset(s->alpha_inputs, 0, sizeof(s->alpha_inputs));
    memset(s->alpha_outputs, 0, sizeof(s->alpha_outputs));
    for (int i = 0; i < n; i++) {
        s->rgb_inputs[i] = rand_inputs();
        s->rgb_outputs[i] = rand_output();
        s->alpha_inputs[i] = rand_inputs();
        s->alpha_outputs[i] = rand_output();
    }
    do {
        s->final_inputs_0 = rand_inputs();
        s->final_inputs_1 = ci(rand_input(false), rand_input(false),
                               rand_input(true), 0) |
                            (rnd() & 0xE0);
    } while (!s->final_inputs_0 && !s->final_inputs_1);
}

/* Remove [from, through the end of the line holding `last` after it). */
static bool cut_block(GString *g, const char *from_a, const char *from_b,
                      const char *after, const char *last)
{
    char *start = strstr(g->str, from_a);
    if (!start && from_b) {
        start = strstr(g->str, from_b);
    }
    if (!start) {
        return false;
    }
    char *a = strstr(start, after);
    char *l = a ? strstr(a, last) : NULL;
    char *e = l ? strchr(l, '\n') : NULL;
    if (!e) {
        return false;
    }
    g_string_erase(g, start - g->str, e + 1 - start);
    return true;
}

/* Remove from `from` to `to`, `to` itself included or not. */
static bool cut_range(GString *g, const char *from, const char *to,
                      bool inclusive)
{
    char *s = strstr(g->str, from);
    char *e = s ? strstr(s, to) : NULL;
    if (!e) {
        return false;
    }
    if (inclusive) {
        e += strlen(to);
    }
    g_string_erase(g, s - g->str, e - s);
    return true;
}

static void drop_all(GString *g, const char *needle)
{
    char *p;
    while ((p = strstr(g->str, needle))) {
        g_string_erase(g, p - g->str, strlen(needle));
    }
}

static void drop_temps(GString *g)
{
    drop_all(g, "vec4 r0 = vec4(0);\nr0.a = t0.a;\n");
    drop_all(g, "vec4 r0 = vec4(0);\nr0.a = 1.0;\n");
    drop_all(g, "vec4 r1 = vec4(0);\n");
}

static void comb_from_state(const PshState *s, uint32_t out[36])
{
    memset(out, 0, 36 * sizeof(uint32_t));
    int n = psh_num_combiner_stages(s->combiner_control);
    for (int i = 0; i < n; i++) {
        out[i * 4 + 0] = s->rgb_inputs[i];
        out[i * 4 + 1] = s->rgb_outputs[i];
        out[i * 4 + 2] = s->alpha_inputs[i];
        out[i * 4 + 3] = s->alpha_outputs[i];
    }
    out[32] = s->final_inputs_0;
    out[33] = s->final_inputs_1;
    out[34] = s->combiner_control;
}

static void write_file(const char *dir, const char *pfx, int id,
                       const char *ext, const void *data, size_t len)
{
    char *path = g_strdup_printf("%s/%s_%04d.%s", dir, pfx, id, ext);
    g_file_set_contents(path, data, len, NULL);
    g_free(path);
}

static const char *only_baseline;
static uint32_t comb_in[36];
static bool comb_given;

int main(int argc, char **argv)
{
    const char *out = NULL;
    int per_baseline = 100;
    rng_state = 0x569u;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--out") && i + 1 < argc) {
            out = argv[++i];
        } else if (!strcmp(argv[i], "--per-baseline") && i + 1 < argc) {
            per_baseline = atoi(argv[++i]);
        } else if (!strcmp(argv[i], "--seed") && i + 1 < argc) {
            rng_state = strtoul(argv[++i], NULL, 0);
        } else if (!strcmp(argv[i], "--baseline") && i + 1 < argc) {
            only_baseline = argv[++i];
        } else if (!strcmp(argv[i], "--comb") && i + 1 < argc) {
            /* 36 comma-separated words, comb_N.bin's layout; one pair. */
            char **w = g_strsplit(argv[++i], ",", -1);
            for (int j = 0; j < 36 && w[j]; j++) {
                comb_in[j] = strtoul(w[j], NULL, 0);
            }
            g_strfreev(w);
            comb_given = true;
            per_baseline = 0;
        } else {
            fprintf(stderr, "usage: %s --out DIR [--per-baseline N] "
                            "[--seed S] [--baseline NAME] [--comb W0,..,W35]\n",
                    argv[0]);
            return 2;
        }
    }
    if (!out) {
        fprintf(stderr, "--out is required\n");
        return 2;
    }
    g_mkdir_with_parents(out, 0755);
    unimpl = g_string_new("");
    g_config.display.renderer = CONFIG_DISPLAY_RENDERER_VULKAN;

    GenPshGlslOptions opts = {
        .vulkan = true, .ubo_binding = 1, .ubo_set = 1, .tex_binding = 0,
    };

    int id = 0, pass = 0, fail = 0, uncovered = 0, nogen = 0;
    GString *manifest = g_string_new("");

    for (size_t b = 0; b < ARRAY_SIZE(baselines); b++) {
        if (only_baseline && strcmp(only_baseline, baselines[b].name)) {
            continue;
        }
        for (int k = 0; k <= per_baseline; k++) {
            PshState s;
            baselines[b].fn(&s);
            if (comb_given) {
                /* One explicit program, in comb_N.bin's layout. */
                memset(s.rgb_inputs, 0, sizeof(s.rgb_inputs));
                memset(s.rgb_outputs, 0, sizeof(s.rgb_outputs));
                memset(s.alpha_inputs, 0, sizeof(s.alpha_inputs));
                memset(s.alpha_outputs, 0, sizeof(s.alpha_outputs));
                for (int i = 0; i < 8; i++) {
                    s.rgb_inputs[i] = comb_in[i * 4 + 0];
                    s.rgb_outputs[i] = comb_in[i * 4 + 1];
                    s.alpha_inputs[i] = comb_in[i * 4 + 2];
                    s.alpha_outputs[i] = comb_in[i * 4 + 3];
                }
                s.final_inputs_0 = comb_in[32];
                s.final_inputs_1 = comb_in[33];
                s.combiner_control = comb_in[34];
            } else if (k > 0) {
                /* k == 0 is the baseline's own program. */
                randomise_combiners(&s);
                /* A random program over a baseline that discards every
                 * pixel checks nothing (render_check's drawn column):
                 * `textures` kills on stage 2's constant zero alpha, and
                 * `clipplane`'s alternating compare modes cannot all hold. */
                memset(s.alphakill, 0, sizeof(s.alphakill));
                memset(s.compare_mode, 0, sizeof(s.compare_mode));
            }
            if (!pgraph_glsl_psh_uber_covers(&s)) {
                uncovered++;
                continue;
            }
            PshState fam;
            pgraph_glsl_psh_uber_family(&s, &fam);

            MString *spec = pgraph_glsl_gen_psh(&s, opts);
            MString *uber = pgraph_glsl_gen_psh_uber(&fam, opts);
            if (!uber) {
                nogen++;
                mstring_unref(spec);
                continue;
            }

            GString *a = g_string_new(mstring_get_str(spec));
            GString *u = g_string_new(mstring_get_str(uber));
            bool ok_a = cut_block(a, "// Stage 0\n", "// Final Combiner\n",
                                  "// Final Combiner\n", "fragColor.a = ");
            drop_all(u, "uvec4 ubComb[9];\n");
            bool ok_u = cut_range(u, "vec4 ubV0, ubV1,", "void main() {\n",
                                  false) &&
                        cut_range(u, "// Combiner ubershader (#569 P6)\n",
                                  "fragColor.a = ubOut.a;\n}\n", true);
            drop_temps(a);
            drop_temps(u);
            bool same = ok_a && ok_u && !strcmp(a->str, u->str);
            if (same) {
                pass++;
            } else {
                fail++;
                if (fail <= 3) {
                    char *pa = g_strdup_printf("%s/splicefail_%04d_spec.txt", out, id);
                    char *pu = g_strdup_printf("%s/splicefail_%04d_uber.txt", out, id);
                    g_file_set_contents(pa, a->str, a->len, NULL);
                    g_file_set_contents(pu, u->str, u->len, NULL);
                    g_free(pa);
                    g_free(pu);
                }
            }

            uint32_t comb[36];
            comb_from_state(&s, comb);
            write_file(out, "spec", id, "frag", mstring_get_str(spec),
                       mstring_get_length(spec));
            write_file(out, "uber", id, "frag", mstring_get_str(uber),
                       mstring_get_length(uber));
            write_file(out, "comb", id, "bin", comb, sizeof(comb));
            g_string_append_printf(manifest,
                "%04d %s k=%d splice=%s cc=%08x fin=%08x,%08x\n", id,
                baselines[b].name, k, same ? "ok" : "FAIL",
                s.combiner_control, s.final_inputs_0, s.final_inputs_1);
            id++;

            g_string_free(a, true);
            g_string_free(u, true);
            mstring_unref(spec);
            mstring_unref(uber);
        }
    }

    char *mp = g_strdup_printf("%s/manifest.txt", out);
    g_file_set_contents(mp, manifest->str, manifest->len, NULL);
    printf("uberhost: %d pairs; SPLICE %d ok, %d FAIL; %d uncovered "
           "(final combiner off); %d not generated\n",
           id, pass, fail, uncovered, nogen);
    return fail || nogen ? 1 : 0;
}
