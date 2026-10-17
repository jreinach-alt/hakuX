"""Which frame of a run's video shows each dump frame? Silhouette alignment (#939, M2b).

usage: vidmap.py DUMP.jsonl RAM.bin VIDEO.mp4 OUTDIR [every=N] [vstep=S] [vw=1280] [vh=960]

Run 13 (Turnip) dumped `gd` with noimages, so bandfit.py has no pixels of its
own for it; its 60 s video does. The dump carries each frame's constants, so
each frame's ring silhouette can be drawn from the vertex records in RAM.bin
(n4 and n5, culled as bandfit.py culls them). The camera moves through the
menu, so the silhouette names the frame. Steps:

  1. a 160x120 silhouette mask for every dump frame;
  2. video frames every vstep seconds (default 0.5), 160x120 luminance, the
     FPS counter's corner blanked;
  3. per sampled video frame, the dump frame whose mask correlates best;
  4. a line t_video = t0 + f * k fitted to those matches, refitted once
     without matches more than 0.5 s off it;
  5. for every Nth dump frame (default 5) inside the video, the video frame
     the line names, written 640x480 as a P6 PPM, and OUTDIR/map.tsv
     (frame, video time, video frame index, ppm).

bandfit.py images=OUTDIR/map.tsv fits against those frames. vidmap.log keeps
the matches and the fit; a fit whose residuals are not small next to the
silhouette's own frame-to-frame change says the mapping cannot be trusted.
The RAM image need not be this run's: the ring's records, strips and textures
are at the same addresses with the same bytes on every run (M1).
"""
import os
import struct
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "x1port1012", "tools"))
import gdread as g  # noqa: E402

dump, ramf, video, out = sys.argv[1:5]
opt = dict(a.split("=", 1) for a in sys.argv[5:])
EVERY = int(opt.get("every", 5))
VSTEP = float(opt.get("vstep", 0.5))
VW, VH = int(opt.get("vw", 1280)), int(opt.get("vh", 960))
os.makedirs(out, exist_ok=True)
log = open(os.path.join(out, "vidmap.log"), "w")


def say(s):
    print(s, flush=True)
    log.write(s + "\n")
    log.flush()


ram = open(ramf, "rb").read()
# as bandfit.py: (index count, records, nvert, strip)
DRAWS = {
    "n4": (864, 0x3d6840, 290, list(range(290))),
    "n5": (4362, 0x3cfb80, 870, list(struct.unpack_from("<1456H", ram, 0x3dc8f8))),
}
REC = np.dtype([("p", "<f4", 3), ("n", "<i4"), ("b", "<i4"), ("t", "<i4"),
                ("uv", "<i2", 2), ("bi", "u1", 2), ("bw", "<i2")])


def verts(addr, nv):
    rec = np.frombuffer(ram[addr:addr + nv * 32], dtype=REC)
    V0 = np.concatenate([rec["p"].astype(np.float64), np.ones((nv, 1))], 1)
    return V0, rec["bi"].astype(np.float64), np.maximum(rec["bw"] / 32767.0, -1)


def tris_of(strip):
    t = []
    for k in range(len(strip) - 2):
        a, b, c = strip[k], strip[k + 1], strip[k + 2]
        if a == b or b == c or a == c:
            continue
        t.append((a, b, c) if k % 2 == 0 else (b, a, c))
    return np.array(t)


def screen(C, V0, V5, V6):
    """bandfit.py's vp(), position only."""
    a0 = np.floor(V5[:, 0] * C[7, 3]).astype(int)
    a1 = np.floor(V5[:, 1] * C[7, 3]).astype(int)
    a1 = np.where(a1 + 62 < 192, a1, 0)
    w0, w1 = V6[:, None], (1 - V6)[:, None]
    rows = [w0 * C[a0 + 60 + k] + w1 * C[a1 + 60 + k] for k in range(3)]
    R10 = np.stack([np.sum(V0 * r, 1) for r in rows], 1)
    P = np.stack([np.sum(np.concatenate([R10, np.ones((len(V0), 1))], 1) * C[k], 1) for k in range(4)], 1)
    return P[:, 0] / P[:, 3] * C[58, 0] + C[59, 0], P[:, 1] / P[:, 3] * C[58, 1] + C[59, 1], P[:, 3]


SW, SH = 160, 120
session, draws, frames, skips, shaders = g.load(dump)
for d in draws:
    for k in ("f", "n", "count"):
        d[k] = int(d[k])
allf = sorted(int(f) for f in frames)
st = g.replay(draws, set(allf))
geo = {k: verts(v[1], v[2]) for k, v in DRAWS.items()}
tris = {k: tris_of(v[3]) for k, v in DRAWS.items()}

masks, mf = [], []
for f in allf:
    im = Image.new("L", (SW, SH), 0)
    dr = ImageDraw.Draw(im)
    got = 0
    for d in draws:
        if d["f"] != f:
            continue
        for k, v in DRAWS.items():
            if d["count"] != v[0] or (f, d["n"]) not in st:
                continue
            C = np.array([g.f32(w) for w in st[(f, d["n"])]["c"]], dtype=np.float64).reshape(192, 4)
            SX, SY, PW = screen(C, *geo[k])
            got += 1
            for a, b, c in tris[k]:
                if min(PW[a], PW[b], PW[c]) <= 0:
                    continue
                area = (SX[b] - SX[a]) * (SY[c] - SY[a]) - (SX[c] - SX[a]) * (SY[b] - SY[a])
                if area <= 0:      # bandfit's "neg" cull
                    continue
                dr.polygon([(SX[i] / 4, SY[i] / 4) for i in (a, b, c)], fill=255)
    if got:
        masks.append(np.asarray(im, dtype=np.float64).ravel() / 255)
        mf.append(f)
M = np.array(masks)
mf = np.array(mf)
cov = M.mean(1)
step = np.abs(np.diff(M, axis=0)).mean(1)
say(f"masks: {len(mf)} frames {mf[0]}..{mf[-1]}, ring coverage {cov.min():.3f}..{cov.max():.3f}, "
    f"mean frame-to-frame change {step.mean():.4f} of the screen")
Mz = (M - M.mean(1, keepdims=True)) / (M.std(1, keepdims=True) + 1e-9)

blank = np.ones((SH, SW), bool)
blank[:int(SH * 45 / 960) + 1, :int(SW * 130 / 1280) + 1] = False   # the FPS counter
blank = blank.ravel()


def frames_gray(w, h, fps=None):
    vf = (f"fps={fps}," if fps else "") + f"scale={w}:{h}:flags=area,format=gray"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-vf", vf, "-f", "rawvideo", "-"],
                         stdout=subprocess.PIPE)
    n = w * h
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, dtype=np.uint8).reshape(h, w)
    p.wait()


tv, best, score = [], [], []
for i, fr in enumerate(frames_gray(SW, SH, fps=1 / VSTEP)):
    v = fr.astype(np.float64).ravel()
    v = np.where(blank, v, v[blank].mean())
    v = (v - v.mean()) / (v.std() + 1e-9)
    r = Mz @ v / len(v)
    j = int(np.argmax(r))
    tv.append(i * VSTEP)
    best.append(mf[j])
    score.append(r[j])
    say(f"video {i * VSTEP:6.2f} s  best frame {mf[j]:4d}  r {r[j]:.3f}  (next best >30 frames away: "
        f"{np.max(np.where(np.abs(mf - mf[j]) > 30, r, -1)):.3f})")
tv, best, score = np.array(tv), np.array(best, dtype=np.float64), np.array(score)
# only samples inside the dump's span, not pinned to its ends, are evidence
use = (best > mf[0] + 2) & (best < mf[-1] - 2)
for it in range(2):
    k, t0 = np.polyfit(best[use], tv[use], 1)
    res = tv - (t0 + k * best)
    if it == 0:
        use &= np.abs(res) < 0.5
say(f"fit: t_video = {t0:.3f} + {k:.5f} * f  ({1 / k:.2f} dump frames per video second), "
    f"{use.sum()} samples, residual rms {np.sqrt(np.mean(res[use] ** 2)):.3f} s, max {np.max(np.abs(res[use])):.3f} s")

nvid = int(round(59.94 * 60))
need = {}
for f in mf[::1]:
    if f % EVERY:
        continue
    t = t0 + k * f
    n = int(round(t * 60000 / 1001))
    if 0 <= n < nvid:
        need.setdefault(n, []).append((f, t))
mp = open(os.path.join(out, "map.tsv"), "w")
mp.write("frame\tt_video\tvideo_frame\tppm\n")
for n, fr in enumerate(frames_gray(640, 480)):
    if n in need:
        rgb = np.repeat(fr[:, :, None], 3, 2)
        path = os.path.join(out, f"v{n:05d}.ppm")
        with open(path, "wb") as fo:
            fo.write(b"P6\n640 480\n255\n" + rgb.tobytes())
        for f, t in need[n]:
            mp.write(f"{f}\t{t:.3f}\t{n}\t{path}\n")
mp.close()
say(f"wrote {sum(len(v) for v in need.values())} frames to map.tsv")
