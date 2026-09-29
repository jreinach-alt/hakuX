#!/usr/bin/env python3
"""Show where two render.c targets differ: rawdiff.py A.raw B.raw [N]."""
import struct
import sys

a = open(sys.argv[1], "rb").read()
b = open(sys.argv[2], "rb").read()
n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
fa = struct.unpack("<%df" % (len(a) // 4), a)
fb = struct.unpack("<%df" % (len(b) // 4), b)
diff = []
for p in range(len(fa) // 4):
    va, vb = fa[4 * p:4 * p + 4], fb[4 * p:4 * p + 4]
    if a[16 * p:16 * p + 16] != b[16 * p:16 * p + 16]:
        diff.append((p, va, vb))
chan = [0, 0, 0, 0]
maxd = [0.0] * 4
for p, va, vb in diff:
    for c in range(4):
        if va[c] != vb[c] and not (va[c] != va[c] and vb[c] != vb[c]):
            chan[c] += 1
            if va[c] == va[c] and vb[c] == vb[c]:
                maxd[c] = max(maxd[c], abs(va[c] - vb[c]))
print("%d px differ; per channel %s; max |d| %s" % (len(diff), chan,
      ["%.3g" % x for x in maxd]))
for p, va, vb in diff[:n]:
    print("(%2d,%2d) spec %s uber %s" % (p % 64, p // 64,
          ["%.9g" % x for x in va], ["%.9g" % x for x in vb]))
