"""#315: score candidate BRDF-stage inputs against the refuted arm's capture.

lane.pshqueue's #315 arm (fix at e3b13f5b45, result
1790395945-arms-pshqueue-fix-1882785) rendered the brdf315 hunk. This models,
per wedge pixel, the volume texel the hunk would sample under each reading of
what t0/t1 hold when the BRDF stage reads them, and counts whole-texel
agreement with the capture and with the golden.

  fields : t.r = whole theta field (high 16), t.g = whole phi field (low 16),
           what brdf315 fitted against (psh.c at fab230935e)
  bytes16: t = (b2, b1, b0, b3)/255, #283's rewrite (a5b4141064), so
           t.r = theta & 255, t.g = phi >> 8

Usage: python3 arm_model.py [fix_capture_dir]
"""
import sys

import numpy as np
from PIL import Image

FIX = (sys.argv[1] if len(sys.argv) > 1 else
       "/home/justin/hakux-work/dispatch/results/1790395945-arms-pshqueue-fix-1882785/captures1")
del sys.argv[1:]  # brdf_fit reads argv[1] as its golden dir at import

sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/brdf315")
import brdf_fit as F  # noqa: E402
TESTS = F.TESTS


def texel_of(img, m):
    return np.rint(img[m][:, :3].astype(float) * 63 / 255).astype(int)


def rule(s, t, r):
    """Nearest texel of the 64^3 volume; REPEAT on all three axes."""
    return np.stack([np.floor(np.asarray(v) * 64).astype(int) % 64 for v in (s, t, r)], 1)


def main():
    gold_img = np.array(Image.open(f"{F.GOLDEN}/{TESTS[0]}.png").convert("RGBA"))
    m = F.wedge_mask(gold_img)
    ys, xs = np.nonzero(m)
    rows, keep = [], []
    for px, py in zip(xs, ys):
        hit = F.raster_attrs(px + 0.5, py + 0.5)
        keep.append(hit is not None)
        if hit is None:
            continue
        te, pe, _ = F.face_texel(hit[1])
        tl, pl, _ = F.face_texel(hit[2])
        rows.append((te, pe, tl, pl))
    keep = np.array(keep)
    te, pe, tl, pl = np.array(rows).T
    n = len(te)

    cands = {
        "fields": rule(te / 65535, tl / 65535, (pl / 65535 - pe / 65535) % 1.0),
        "bytes16": rule((te & 255) / 255, (tl & 255) / 255,
                        ((pl >> 8) / 255 - (pe >> 8) / 255) % 1.0),
    }
    gold = texel_of(gold_img, m)[keep]
    print(f"modelled wedge px: {n} of {m.sum()}")
    print(f"light texel: theta {tl[0]:#06x} phi {pl[0]:#06x} (constant: {len(set(tl)) == 1 and len(set(pl)) == 1})")
    for t in TESTS:
        cap_img = np.array(Image.open(f"{FIX}/Texture_BRDF::{t}.png").convert("RGBA"))
        cap = texel_of(cap_img, m)[keep]
        print(f"{t}: capture distinct texels {len({tuple(r) for r in cap})}, golden {len({tuple(r) for r in gold})}")
        for name, idx in cands.items():
            for ref_name, ref in (("capture", cap), ("golden", gold)):
                exact = (idx == ref).all(1)
                per_axis = [(idx[:, a] == ref[:, a]).mean() * 100 for a in range(3)]
                within = (abs(idx - ref) <= 1).all(1).sum()
                print(f"   {name:8s} vs {ref_name:7s}: whole-texel exact {exact.sum():3d}/{n}, "
                      f"within1 {within:3d}/{n}, per axis s/t/r "
                      + "/".join(f"{p:5.1f}%" for p in per_axis))
        dcap = (cap != gold).any(1).sum()
        print(f"   capture != golden (as texel index) on {dcap}/{n} modelled px")


if __name__ == "__main__":
    main()
