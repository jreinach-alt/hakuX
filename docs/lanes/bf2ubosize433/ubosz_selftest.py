#!/usr/bin/env python3
"""Host check of the #433 ubosz counter (vk/shaders.c), no device, no NDK.

Cuts the counter block out of hw/xbox/nv2a/pgraph/vk/shaders.c exactly as it
is in the tree (from the '#433 (lane.bf2ubosize433)' comment to its '#endif'),
compiles it with the host cc against stub types, drives upload sequences whose
answer is known in advance, and checks the printed line field by field.

    docs/lanes/bf2ubosize433/ubosz_selftest.py     # rc 0 = every case matches

The counter's printing is the device's (__android_log_print on hakuX-stall);
here it is routed to stdout.
"""
import os, re, subprocess, sys, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SRC = os.path.join(ROOT, 'hw/xbox/nv2a/pgraph/vk/shaders.c')

text = open(SRC).read()
start = text.index('#if NV2A_PERF_LOG\n/*\n * #433 (lane.bf2ubosize433)')
end = text.index('#endif\n\nvoid pgraph_vk_update_descriptor_sets', start)
block = text[start + len('#if NV2A_PERF_LOG\n'):end]

STUBS = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define __ANDROID__ 1
#define ANDROID_LOG_INFO 4
#define __android_log_print(prio, tag, ...) \
    (printf("%s: ", tag), printf(__VA_ARGS__), printf("\n"))
#define NV2A_VERTEXSHADER_CONSTANTS 192
#define DIV_ROUND_UP(n, d) (((n) + (d) - 1) / (d))
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define g_realloc realloc
static size_t g_strlcpy(char *d, const char *s, size_t n)
{
    size_t l = strlen(s);
    if (n) { size_t c = l < n - 1 ? l : n - 1; memcpy(d, s, c); d[c] = 0; }
    return l;
}
typedef void *VkDescriptorSet;
typedef struct ShaderUniform {
    const char *name; size_t dim_v, dim_a, align, stride, offset;
} ShaderUniform;
typedef struct ShaderUniformLayout {
    ShaderUniform *uniforms; size_t num_uniforms, total_size; void *allocation;
} ShaderUniformLayout;
typedef struct { ShaderUniformLayout uniforms; } Info;
typedef struct ShaderBinding {
    struct { Info *upload_info; } vsh;
    struct { Info *module_info; } psh;
} ShaderBinding;
typedef struct { ShaderBinding *shader_binding; } PGRAPHVkState;
typedef struct PGRAPHState {
    PGRAPHVkState *vk_renderer_state;
    uint32_t vsh_constants[NV2A_VERTEXSHADER_CONSTANTS][4];
} PGRAPHState;
'''

DRIVER = r'''
/* VS layout: c[192] at 0, clipRange vec4 at 3072, fogParam float at 3088
 * (total 3092 -> 194 chunks, the last one partial). PS layout: consts[9]. */
static ShaderUniform vu[] = {
    { "c", 4, 192, 16, 16, 0 }, { "clipRange", 4, 1, 16, 0, 3072 },
    { "fogParam", 1, 1, 4, 0, 3088 },
};
static ShaderUniform pu[] = { { "consts", 4, 9, 16, 16, 0 } };
static uint8_t vmem[2][3092], pmem[2][144];
static Info vi[2], pi[2];
static ShaderBinding b[2];
static PGRAPHVkState r;
static PGRAPHState pg;

static void setup(void)
{
    for (int k = 0; k < 2; k++) {
        vi[k].uniforms = (ShaderUniformLayout){ vu, 3, 3092, vmem[k] };
        pi[k].uniforms = (ShaderUniformLayout){ pu, 1, 144, pmem[k] };
        b[k].vsh.upload_info = &vi[k];
        b[k].psh.module_info = &pi[k];
    }
    pg.vk_renderer_state = &r;
}

/* What pgraph_vk_update_shader_uniforms does: the constants into the
 * binding's VS layout, then the upload. */
static void upload(int k, int site)
{
    r.shader_binding = &b[k];
    memcpy(vmem[k], pg.vsh_constants, sizeof(pg.vsh_constants));
    pgraph_vk_ubosz_note_upload(&pg, site);
}

static void bump(int row) { pg.vsh_constants[row][0]++; }

int main(int argc, char **argv)
{
    setup();
    int c = atoi(argv[1]);
    if (c == 1) {
        /* 101 uploads, one binding, rows 0-3 changed before each after the
         * first. */
        for (int i = 0; i < 101; i++) {
            if (i) { bump(0); bump(1); bump(2); bump(3); }
            upload(0, 0);
        }
    } else if (c == 2) {
        /* 1 + 90 uploads, row i % 192 changed before upload i: the policy's
         * union grows by one per upload, so pk8 rebinds when it reaches 9
         * (every 9th), pk16 at 17. */
        upload(0, 1);
        for (int i = 1; i <= 90; i++) { bump(i % 192); upload(0, 1); }
    } else if (c == 3) {
        /* Alternating bindings: every upload is a switch; c still counts.
         * Then a PS-only change and a clipRange change on one binding. */
        for (int i = 0; i < 10; i++) { bump(5); upload(i & 1, 0); }
        upload(0, 0);              /* sw again (prev was binding 1) */
        pmem[0][20]++; upload(0, 0);   /* 1 chunk: p.consts */
        vmem[0][3076] = 1;              /* clipRange.y: re-copied? */
        r.shader_binding = &b[0];
        pgraph_vk_ubosz_note_upload(&pg, 0);  /* 1 chunk: v.clipRange */
        vmem[0][3090] = 7;
        pgraph_vk_ubosz_note_upload(&pg, 0);  /* last partial chunk */
        upload(0, 0);              /* nothing changed: lay bin 0, c bin 0 */
        /* binds: same, same, different set, different offset */
        uint32_t o[2] = { 256, 512 };
        pgraph_vk_ubosz_note_bind((void *)1, o);
        pgraph_vk_ubosz_note_bind((void *)1, o);
        pgraph_vk_ubosz_note_bind((void *)2, o);
        o[1] = 768;
        pgraph_vk_ubosz_note_bind((void *)2, o);
    }
    pgraph_vk_ubosz_log_and_reset();
    /* After a reset the window is empty. */
    pgraph_vk_ubosz_log_and_reset();
    return 0;
}
'''

# (case, [(regex, expected), ...]) on the first printed window
CASES = {
    '1': [
        (r'ubosz\[n(\d+) ', '101'), (r' d(\d+) ', '101'), (r' q(\d+) ', '0'),
        (r' sw(\d+) ', '1'),
        # 100 same-binding uploads, 4 chunks each: bin 3-4 is index 3
        (r' lay ([\d/]+) ', '0/0/0/100/0/0/0/0/0/0'), (r' lay [\d/]+ sum(\d+)', '400'),
        (r' c ([\d/]+) ', '0/0/0/100/0/0/0/0/0/0'), (r' c [\d/]+ sum(\d+)', '400'),
        (r' span ([\d/]+) ', '0/0/0/100/0/0/0/0/0/0'),
        (r' pk8 (\d+)', '0'), (r' pk16 (\d+)', '0'),
        (r'ubosz-top\[c ([^|]*)\|', '0:100 1:100 2:100 3:100 '),
        (r'\| u (.*)\]', 'v.c:400'),
    ],
    '2': [
        (r'ubosz\[n(\d+) ', '91'), (r' q(\d+) ', '91'), (r' sw(\d+) ', '1'),
        (r' lay ([\d/]+) ', '0/90/0/0/0/0/0/0/0/0'),
        (r' c ([\d/]+) ', '0/90/0/0/0/0/0/0/0/0'),
        (r' pk8 (\d+)', '10'), (r' pk16 (\d+)', '5'),
    ],
    '3': [
        (r'ubosz\[n(\d+) ', '15'), (r' sw(\d+) ', '11'),
        # same-binding: p.consts 1, clipRange 1, partial chunk 1, nothing 0
        (r' lay ([\d/]+) ', '1/3/0/0/0/0/0/0/0/0'), (r' lay [\d/]+ sum(\d+)', '3'),
        # c: 9 compared uploads changed row 5, then 5 with no change
        (r' c ([\d/]+) ', '5/9/0/0/0/0/0/0/0/0'),
        (r'ubosz-top\[c ([^|]*)\|', '5:9 '),
        (r' bind(\d+/\d+)', '4/1'),
        (r'\| u (.*)\]', 'p.consts:1 v.clipRange:1 v.fogParam:1'),  # ties: first seen first
    ],
}

fail = 0
with tempfile.TemporaryDirectory() as td:
    c = os.path.join(td, 't.c')
    open(c, 'w').write(STUBS + block + DRIVER)
    exe = os.path.join(td, 't')
    p = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-sign-compare',
                        '-fsanitize=address,undefined', '-o', exe, c],
                       capture_output=True, text=True)
    if p.returncode:
        print(p.stderr)
        sys.exit(2)
    for case, checks in CASES.items():
        out = subprocess.run([exe, case], capture_output=True, text=True)
        lines = out.stdout.splitlines()
        if out.returncode or len(lines) != 4:
            print('case %s: rc %d, %d lines\n%s%s' % (
                case, out.returncode, len(lines), out.stdout, out.stderr))
            fail += 1
            continue
        window = '\n'.join(lines[:2])
        for rx, want in checks:
            m = re.search(rx, window)
            got = m.group(1) if m else None
            ok = got == want
            fail += not ok
            print('case %s %-4s %-28s want %-24r got %r' % (
                case, 'ok' if ok else 'FAIL', rx[:28], want, got))
        empty = lines[2]
        ok = 'n0 d0 q0 sw0' in empty and 'bind0/0' in empty and lines[3].endswith('[c | u]')
        fail += not ok
        print('case %s %-4s reset leaves an empty window' % (case, 'ok' if ok else 'FAIL'))
        print('   ', lines[0])
        print('   ', lines[1])
print('FAIL' if fail else 'PASS', '(%d failed)' % fail)
sys.exit(1 if fail else 0)
