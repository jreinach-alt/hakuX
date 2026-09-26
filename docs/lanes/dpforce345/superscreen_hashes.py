"""Hash every GeometrySuperscreen_* capture in the dispatch results and print,
per run dir, its ref/device and which captures differ from the modal image.

Used to decide whether the dpforce345 arm's six Vertex_shader_rounding_tests
movers are this hunk or device nondeterminism.
"""
import collections
import glob
import hashlib
import json
import os
import sys

D = sys.argv[1] if len(sys.argv) > 1 else "/home/justin/hakux-work/dispatch/results"


def h(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


runs = []
counts = collections.defaultdict(collections.Counter)
for d in sorted(os.listdir(D)):
    ps = glob.glob(os.path.join(D, d, "captures*", "**", "*GeometrySuperscreen_*.png"), recursive=True)
    if not ps:
        continue
    try:
        with open(os.path.join(D, d, "result.json")) as f:
            r = json.load(f)
    except Exception:
        r = {}
    caps = {}
    for p in ps:
        n = os.path.basename(p).split("GeometrySuperscreen_")[1][:-4]
        caps[n] = h(p)
        counts[n][caps[n]] += 1
    runs.append((d, r, caps))

modal = {n: c.most_common(1)[0][0] for n, c in counts.items()}
print("captures:", len(modal), "runs:", len(runs))
for d, r, caps in runs:
    off = sorted(n for n, x in caps.items() if x != modal[n])
    print(d[:52].ljust(52), str(r.get("ref"))[:10], r.get("device_label"), str(r.get("apk_sha"))[:10],
          "%d/%d off:" % (len(off), len(caps)), " ".join(off))
