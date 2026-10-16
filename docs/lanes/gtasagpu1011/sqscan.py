import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fdread
import numpy as np

def square(d):
    """Map the shadow's UV [0,1]^2 square on its flat triangle to screen.
    Returns (coef, z, M, off) or None."""
    if not d.get("cm") or not d.get("v"):
        return None
    cm = [[fdread.hf(x) for x in r.split()] for r in d["cm"]]
    M = np.array(cm[0:4]); off = cm[5][:2] if len(cm) > 5 else [0, 0]
    vs = []
    for e in d["v"]:
        if len(e) < 4 or not e[3]:
            return None
        pos = [fdread.hf(x) for x in e[1].split()]
        uv = [fdread.hf(x) for x in e[3].split()]
        vs.append((pos, uv))
    for t in range(len(vs) // 3):
        T = vs[3*t:3*t+3]
        if max(p[2] for p, _ in T) - min(p[2] for p, _ in T) < 0.05:
            A = np.array([[uv[0], uv[1], 1.0] for _, uv in T])
            if abs(np.linalg.det(A)) < 1e-9:
                continue
            P = np.array([[p[0], p[1]] for p, _ in T])
            return np.linalg.solve(A, P), T[0][0][2], M, off
    return None

def onscreen(sq, W=640, H=480, n=41):
    coef, z, M, off = sq
    g = np.linspace(0, 1, n); pts = []
    for u in g:
        for v in g:
            xy = np.array([u, v, 1.0]) @ coef
            c = M @ np.array([xy[0], xy[1], z, 1.0])
            if c[3] > 0:
                sx, sy = c[0]/c[3]+off[0], c[1]/c[3]+off[1]
                if 0 <= sx < W and 0 <= sy < H:
                    pts.append((sx, sy))
    return pts

if __name__ == "__main__":
    session, draws, frames, shaders = fdread.load(sys.argv[1])
    sh = sys.argv[2] if len(sys.argv) > 2 else "7f12c419"
    cons = [d for d in draws if d.get("shader", "").startswith(sh)]
    print("consumers", len(cons))
    for d in cons:
        sq = square(d)
        if sq is None:
            print("f%d n%d: no square (no v/uv words)" % (d["f"], d["n"])); continue
        pts = onscreen(sq)
        if pts:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            print("f%d n%d: %d/1681 on screen, box %d,%d-%d,%d" % (d["f"], d["n"], len(pts), min(xs), min(ys), max(xs), max(ys)))
        else:
            print("f%d n%d: 0/1681 on screen" % (d["f"], d["n"]))
