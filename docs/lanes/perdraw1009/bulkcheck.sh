#!/usr/bin/env bash
# HAKUX_UNI_BULK's byte-identity check, on the host: shaders.c's
# uniform_copy_bulk (extracted from the file as it stands, not a copy) against
# glsl.h's uniform_copy, over std140 layouts of random members plus the shapes
# VshUniform/PshUniform declare (vec4[192], vec3[8], float[8], mat2[4] as
# reflection reports it, single vec2/vec4/int), each copied with the count
# apply_uniform_updates passes. Every case starts both allocations from the
# same random fill and compares them whole.
#
#   docs/lanes/perdraw1009/bulkcheck.sh        -> "OK <cases>" or the first mismatch
#   SHADERS_C=<a mutant copy> bulkcheck.sh       -> must print MISMATCH
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/qemu"
cat > "$tmp/qemu/osdep.h" <<'EOF'
#include <stddef.h>
#define ROUND_UP(n, d) (((n) + (d) - 1) & -(0 ? (n) : (d)))
EOF
python3 - "${SHADERS_C:-$root/hw/xbox/nv2a/pgraph/vk/shaders.c}" > "$tmp/bulk.inc" <<'EOF'
import re, sys
s = open(sys.argv[1]).read()
out = []
for name in ("uniform_copy_element", "uniform_copy_bulk"):
    m = re.search(r"^static (?:inline )?void " + name + r"\(.*?^\}\n", s, re.S | re.M)
    if not m:
        sys.exit("not found in shaders.c: " + name)
    out.append(m.group(0))
print("\n".join(out))
EOF
cat > "$tmp/check.c" <<'EOF'
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "glsl.h"
#include "bulk.inc"

static unsigned rnd(void) { return (unsigned)rand(); }

static int run_case(ShaderUniform *mem, int n, int which, size_t value_size,
                    size_t count, size_t total_override)
{
    ShaderUniformLayout a = { .uniforms = mem, .num_uniforms = n };
    if (!total_override) {
        uniform_std140(&a);
    } else {
        a.total_size = total_override;
    }
    ShaderUniformLayout b = a;
    a.allocation = malloc(a.total_size);
    b.allocation = malloc(b.total_size);
    for (size_t i = 0; i < a.total_size; i++) {
        ((unsigned char *)a.allocation)[i] = rnd();
    }
    memcpy(b.allocation, a.allocation, a.total_size);
    uint32_t *vals = malloc(count * value_size + 16);
    for (size_t i = 0; i < count; i++) {
        vals[i] = rnd();
    }
    uniform_copy(&a, which + 1, vals, value_size, count);
    uniform_copy_bulk(&b, which + 1, vals, value_size, count);
    int bad = memcmp(a.allocation, b.allocation, a.total_size) != 0;
    if (bad) {
        fprintf(stderr, "MISMATCH member %d dim_v %zu dim_a %zu stride %zu count %zu\n",
                which, mem[which].dim_v, mem[which].dim_a, mem[which].stride, count);
    }
    free(a.allocation); free(b.allocation); free(vals);
    return bad;
}

int main(void)
{
    srand(433);
    int cases = 0;
    /* random std140 blocks: every member copied in full, as apply_uniform_updates does */
    for (int t = 0; t < 2000; t++) {
        int n = 1 + rnd() % 12;
        ShaderUniform mem[12];
        for (int i = 0; i < n; i++) {
            mem[i] = (ShaderUniform){ .name = "u", .dim_v = 1 + rnd() % 4,
                                      .dim_a = (rnd() % 3) ? 1 + rnd() % 200 : 1 };
        }
        int which = rnd() % n;
        if (run_case(mem, n, which, 4, mem[which].dim_v * mem[which].dim_a, 0)) return 1;
        cases++;
    }
    /* the declared shapes, with reflection's strides */
    struct { size_t dim_v, dim_a, stride; } shapes[] = {
        { 4, 192, 16 }, { 3, 8, 16 }, { 1, 8, 16 }, { 4, 36, 16 }, { 3, 4, 16 },
        { 2, 8, 16 },   /* mat2[4]: dim_a 4x2 columns, stride 32/2 */
        { 4, 1, 0 }, { 2, 1, 0 }, { 1, 1, 0 }, { 4, 139, 16 }, { 4, 9, 16 },
        { 4, 18, 16 }, { 1, 4, 16 },
    };
    for (size_t k = 0; k < sizeof(shapes) / sizeof(shapes[0]); k++) {
        ShaderUniform mem[1] = { { .name = "u", .dim_v = shapes[k].dim_v,
                                   .dim_a = shapes[k].dim_a,
                                   .stride = shapes[k].stride, .offset = 0 } };
        size_t total = shapes[k].stride ? shapes[k].stride * shapes[k].dim_a
                                        : 4 * shapes[k].dim_v;
        if (run_case(mem, 1, 0, 4, shapes[k].dim_v * shapes[k].dim_a, total)) return 1;
        cases++;
    }
    printf("OK %d\n", cases);
    return 0;
}
EOF
cc -O1 -std=gnu11 -I "$tmp" -I "$root/hw/xbox/nv2a/pgraph/vk" -o "$tmp/check" "$tmp/check.c"
"$tmp/check"
