#!/usr/bin/env python3
"""Symbolize vkharness samples and group them by compiler pass.

    prof.py <icd.so> <samples.bin> [--manifest m.txt] [--only SUBSTR] [--top N]

Each sample is a call chain of return addresses. Frames inside the ICD are
named from its symbol table (llvm-nm; static functions included, inlined ones
fold into their caller). Two readings:

  groups   inclusive: a sample counts for every group whose function is
           anywhere on its chain (so groups nest and do not sum to 100%)
  bucket   exclusive: the INNERMOST group on the chain, so buckets sum to 100%
  leaves   the innermost ICD function of each sample (self time)
  passes   the innermost frame whose name looks like a NIR/ir3 pass entry
"""
import argparse
import bisect
import re
import struct
import subprocess
from collections import Counter

NM = "/usr/lib/llvm-18/bin/llvm-nm"

# Outer to inner. The exclusive bucket is the innermost one present.
GROUPS = [
    ("pipeline (all)", r"^tu_graphics_pipeline_create|^tu_CreateGraphicsPipelines$"),
    ("tu_compile_shaders", r"^tu_compile_shaders$"),
    ("tu_spirv_to_nir", r"^tu_spirv_to_nir"),
    ("spirv_to_nir (vtn)", r"^vk_pipeline_shader_stage_to_nir$|^spirv_to_nir$"),
    ("ir3_optimize_loop", r"^ir3_optimize_loop$"),
    ("tu_link_shaders", r"^tu_link_shaders$"),
    ("link_opts", r"^link_opts$"),
    ("tu_shader_create", r"^tu_shader_create$"),
    ("ir3_finalize_nir", r"^ir3_finalize_nir$"),
    ("ir3_nir_lower_variant", r"^ir3_nir_lower_variant$"),
    ("ir3_shader_create_variant", r"^ir3_shader_create_variant$|^ir3_shader_get_variant$"),
    ("ir3 backend (ir3_compile_shader_nir)", r"^ir3_compile_shader_nir$"),
    ("ir3 RA", r"^ir3_ra$"),
    ("ir3 sched", r"^ir3_sched$|^ir3_postsched$|^ir3_sched_add_deps$"),
]
PASS_RE = re.compile(r"^(nir_(opt|lower|split|remove|copy|inline|shrink|propagate|move|convert|algebraic|link|compact|remove_dead|opt_)\w*|"
                     r"ir3_\w+|nir_algebraic_impl|nir_\w+_impl|vtn_\w+|spirv_to_nir)$")


def symbols(so):
    out = subprocess.run([NM, "--defined-only", "-S", "-C", so],
                         capture_output=True, text=True, check=True).stdout
    syms = []
    for line in out.splitlines():
        p = line.split(None, 3)
        if len(p) == 4 and p[2] in "tTwW":
            # tu_*.cc is C++: keep the demangled name, drop the signature
            syms.append((int(p[0], 16), int(p[1], 16), p[3].split("(")[0]))
    syms.sort()
    return syms, [s[0] for s in syms]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("so")
    ap.add_argument("samples")
    ap.add_argument("--manifest")
    ap.add_argument("--only", help="keep samples of pipelines whose name contains this")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()

    syms, starts = symbols(a.so)

    def name_of(off):
        i = bisect.bisect_right(starts, off) - 1
        if i >= 0:
            s, sz, n = syms[i]
            if off < s + max(sz, 1):
                return n
        return None

    names = []
    if a.manifest:
        for line in open(a.manifest):
            if line.strip() and not line.startswith("#"):
                names.append(line.split()[0])

    data = open(a.samples, "rb").read()
    base, n = struct.unpack_from("<QQ", data, 0)
    pos = 16
    chains = []
    for _ in range(n):
        tag, = struct.unpack_from("<Q", data, pos)
        pos += 8
        k = tag & 0xffffffff
        pidx = tag >> 32
        addrs = struct.unpack_from("<%dQ" % k, data, pos)
        pos += 8 * k
        if a.only and names and a.only not in names[pidx]:
            continue
        fr = []
        for ad in addrs:
            off = ad - base - 1
            nm = name_of(off) if 0 <= off < (1 << 32) else None
            if nm:
                fr.append(nm)
        chains.append(fr)

    total = len(chains)
    inicd = [c for c in chains if c]
    print(f"samples: {total}, with an ICD frame: {len(inicd)}")
    gre = [(g, re.compile(r)) for g, r in GROUPS]
    incl = Counter()
    excl = Counter()
    for c in inicd:
        present = set()
        for g, r in gre:
            if any(r.search(f) for f in c):
                present.add(g)
        for g in present:
            incl[g] += 1
        inner = [g for g, _ in gre if g in present]
        excl[inner[-1] if inner else "(no group)"] += 1
    base_n = len(inicd) or 1
    print("\n| group | inclusive | share |\n|---|---|---|")
    for g, _ in gre:
        print(f"| {g} | {incl[g]} | {100 * incl[g] / base_n:.1f}% |")
    print("\n| innermost group (exclusive) | samples | share |\n|---|---|---|")
    for g, v in excl.most_common():
        print(f"| {g} | {v} | {100 * v / base_n:.1f}% |")

    leaves = Counter(c[0] for c in inicd)
    print(f"\n| leaf function (self) | samples | share |\n|---|---|---|")
    for f, v in leaves.most_common(a.top):
        print(f"| `{f}` | {v} | {100 * v / base_n:.1f}% |")

    passes = Counter()
    for c in inicd:
        hit = next((f for f in c if PASS_RE.match(f) and not f.startswith("ir3_optimize_loop")), None)
        passes[hit or "(none)"] += 1
    print(f"\n| innermost pass-like frame (inclusive of callees) | samples | share |\n|---|---|---|")
    for f, v in passes.most_common(a.top):
        print(f"| `{f}` | {v} | {100 * v / base_n:.1f}% |")


if __name__ == "__main__":
    main()
