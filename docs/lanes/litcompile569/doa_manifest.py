#!/usr/bin/env python3
"""A|B vkharness manifest over a title's own vertex modules.

    doa_manifest.py <A.tsv> <A outdir> <B.tsv> <B outdir> > manifest

The .tsv files and outdirs are gendoa's, from one shader_module_keys.bin with
two generators. Each key row pairs by position, so A's and B's module i are
the same state. One pipeline per distinct A vertex module: VS + the title's
triangle geometry stage when the VS writes prefixed (v_) outputs, as
vk/shaders.c builds it, + the title's first fragment module. The fragment and
geometry modules are A's on both sides (B1 does not touch them; gendoa showed
them byte-identical). Names: <lit|ff|prog>-<changed|same>-<A hash>.
"""
import re
import sys

ra = [l.split() for l in open(sys.argv[1])]
rb = [l.split() for l in open(sys.argv[3])]
da, db = sys.argv[2], sys.argv[4]
assert len(ra) == len(rb) and all(a[0] == b[0] for a, b in zip(ra, rb))
spv = lambda d, r: "%s/%s_%s.spv" % (d, r[0], r[1])
fs = next(spv(da, r) for r in ra if r[0] == "fs")
gtri = None
for r in ra:
    if r[0] == "gs" and re.search(r"layout\(triangles\) in;", open(spv(da, r)[:-4] + ".glsl").read()):
        gtri = spv(da, r)
assert gtri
seen = set()
for a, b in zip(ra, rb):
    if a[0] != "vs" or a[1] in seen:
        continue
    seen.add(a[1])
    kind = "lit" if a[2] == "1" else ("ff" if a[3] == "1" else "prog")
    same = "same" if open(spv(da, a), "rb").read() == open(spv(db, b), "rb").read() else "changed"
    pfx = "v_vtxD0" in open(spv(da, a)[:-4] + ".glsl").read()
    tail = [fs] + ([gtri] if pfx else [])
    name = "%s-%s-%s%s" % (kind, same, a[1], "+gtri" if pfx else "+nogs")
    print(" ".join(["A|" + name, spv(da, a)] + tail))
    print(" ".join(["B|" + name, spv(db, b)] + tail))
