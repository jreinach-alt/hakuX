#!/usr/bin/env python3
"""What a wide line actually covers, and what is left over once it does.

`line_coverage.py` answers "is the width arriving" from a lit-pixel count.  Once
the answer is yes, the next question is a different one: *what shape* is being
laid down, and of the pixels still wrong, how many are the shape and how many
are something else.  A differing-pixel total cannot tell those apart, and for
`Line_width` they point at opposite conclusions -- the width is right and the
issue is which of several overlapping wide edges ends up on top.

Three measurements, all on the `Line width` suite:

  --edge        The one axis-aligned segment in the test (the quad strip's left
                edge, vertical at screen x=160) gives the coverage rule exactly:
                which columns light up for each requested width.  Silicon lights
                exactly W columns centred on the pixel CENTRE nearest the line;
                we light exactly W centred on the vertex itself.  They coincide
                at even widths and sit one pixel apart at odd ones.

  --footprint   Fits a footprint model to the isolated QUADS primitive at the
                bottom left, where nothing else is drawn.  Candidates: a
                perpendicular rectangle (butt), square caps, and bevel / miter /
                round joins.  Both renderers are butt rectangles of exactly the
                requested width; no cap or join model improves the fit.

  --classify    Splits the residual into classes that cannot be read off a
                differing-pixel count: golden-only ink, ours-only ink, and
                colour on ink both agree about -- the last bucketed by
                magnitude, because a full palette-sized delta means a different
                edge won the overlap while a small one is interpolation.

    line_footprint.py --captures <dir> [--edge] [--footprint] [--classify]

`--captures` takes a directory of `<Suite>::<test>.png`.  Goldens default to
~/goldens/results.  See docs/investigations/line-width-residual.md.
"""
import argparse
import os
import re
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("line_footprint.py needs numpy and pillow")

SUITE = "Line_width"
# The suite clears to 0xFF202224 and draws on it.  Anything further than a
# couple of steps from the clear colour is ink.
BG = np.array([0x20, 0x22, 0x24])
INK = 8

# The test draws at (framebuffer * 0.25, framebuffer * 0.10) = (160, 48).
OX, OY = 160.0, 48.0

# The QUADS primitive, the last thing the test draws and the only one with a
# region of its own -- nothing else reaches y > 366.
QUAD = [(0.0, 350.0), (60.0, 340.0), (58.5, 425.4), (12.75, 407.5)]
QUAD_BOX = (366, 480, 90, 300)  # y0, y1, x0, x1

# The quad strip's left edge: vertical, from (160, 287) to (160, 168).  Row 230
# crosses it far from either end.
EDGE_ROW = 230
EDGE_X = 160

NAME = re.compile(r"Line_(\d+)\.(\d)$")


def load(path):
    return np.asarray(Image.open(path).convert("RGBA")).astype(np.int16)


def ink(img):
    return np.abs(img[:, :, :3] - BG).max(axis=2) > INK


def captures(capture_dir, golden_dir):
    """(width, test, golden, ours) for every Line_* capture present in both."""
    gdir = os.path.join(golden_dir, SUITE)
    for f in sorted(os.listdir(gdir)):
        if not f.endswith(".png"):
            continue
        test = f[:-4]
        m = NAME.match(test)
        if not m:
            continue
        ours = os.path.join(capture_dir, f"{SUITE}::{test}.png")
        if not os.path.exists(ours):
            continue
        width = int(m.group(1)) + int(m.group(2)) / 8.0
        yield width, test, load(os.path.join(gdir, f)), load(ours)


def lit_run(mask, row, through):
    """The contiguous lit run on `row` containing column `through`."""
    xs = np.where(mask[row])[0]
    if not len(xs):
        return None
    start = prev = xs[0]
    runs = []
    for x in xs[1:]:
        if x != prev + 1:
            runs.append((start, prev))
            start = x
        prev = x
    runs.append((start, prev))
    for a, b in runs:
        if a <= through <= b:
            return a, b
    return None


def report_edge(rows):
    """Which columns a vertical line of each width lights, measured and modelled.

    A line of width W centred at cx lights the columns whose centre falls in
    [cx - W/2, cx + W/2).  cx = 160.0 is the vertex; cx = 160.5 is the centre of
    the pixel the vertex falls in.
    """
    def model(cx, w):
        lo = int(np.ceil(cx - w / 2 - 0.5))
        hi = int(np.ceil(cx + w / 2 - 0.5)) - 1
        return lo, hi

    print(f"{'test':<14}{'width':>8} | {'golden':>12}{'px':>4} | {'ours':>12}{'px':>4}"
          f" | {'cx=160.0':>12}{'cx=160.5':>12}")
    gv = gc = ov = oc = total = 0
    for w, t, g, o in rows:
        # Below 2 the device's own limits decide the width, not the register
        # (lineWidthRange[0] = 1.0, lineWidthGranularity = 0.5 on Adreno 740);
        # above 48 the run merges with the neighbouring primitive's ink.
        if w < 3 or w > 48:
            continue
        rg = lit_run(ink(g), EDGE_ROW, EDGE_X)
        ro = lit_run(ink(o), EDGE_ROW, EDGE_X)
        if not rg or not ro:
            continue
        mv, mc = model(160.0, w), model(160.5, w)
        total += 1
        gv += rg == mv
        gc += rg == mc
        ov += ro == mv
        oc += ro == mc
        print(f"{t:<14}{w:8.3f} | {rg[0]:5d}..{rg[1]:<5d}{rg[1]-rg[0]+1:4d}"
              f" | {ro[0]:5d}..{ro[1]:<5d}{ro[1]-ro[0]+1:4d}"
              f" | {mv[0]:5d}..{mv[1]:<6d}{mc[0]:5d}..{mc[1]:<6d}")
    if total:
        print(f"\n  over {total} widths the register is honoured at (3.0 .. 48.0):")
        print(f"    golden matches cx=160.0, the vertex        {gv}/{total}")
        print(f"    golden matches cx=160.5, the pixel centre  {gc}/{total}")
        print(f"    ours   matches cx=160.0, the vertex        {ov}/{total}")
        print(f"    ours   matches cx=160.5, the pixel centre  {oc}/{total}")


def _quad_fields():
    y0, y1, x0, x1 = QUAD_BOX
    yy, xx = np.mgrid[y0:y1, x0:x1]
    return xx + 0.5, yy + 0.5


def _quad_segments():
    v = [(x + OX, y + OY) for x, y in QUAD]
    return v, [(v[i], v[(i + 1) % 4]) for i in range(4)]


def footprint(w, cap="butt", join=None):
    """Coverage of the QUADS outline under one footprint model."""
    px, py = _quad_fields()
    verts, segs = _quad_segments()
    h = w / 2.0
    out = np.zeros(px.shape, dtype=bool)
    for (ax, ay), (bx, by) in segs:
        ex, ey = bx - ax, by - ay
        length = np.hypot(ex, ey)
        ux, uy = ex / length, ey / length
        dx, dy = px - ax, py - ay
        along = dx * ux + dy * uy
        across = dx * (-uy) + dy * ux
        end = h if cap == "square" else 0.0
        out |= (np.abs(across) <= h) & (along >= -end) & (along <= length + end)
    if join == "round":
        for vx, vy in verts:
            out |= ((px - vx) ** 2 + (py - vy) ** 2) <= h * h
    elif join in ("bevel", "miter"):
        out |= _join_wedges(w, join)
    return out


def _join_wedges(w, kind):
    px, py = _quad_fields()
    verts, _ = _quad_segments()
    h = w / 2.0
    out = np.zeros(px.shape, dtype=bool)

    def tri(p0, p1, p2):
        def side(a, b):
            return (px - a[0]) * (b[1] - a[1]) - (py - a[1]) * (b[0] - a[0])
        s0, s1, s2 = side(p0, p1), side(p1, p2), side(p2, p0)
        return ((s0 >= 0) & (s1 >= 0) & (s2 >= 0)) | \
               ((s0 <= 0) & (s1 <= 0) & (s2 <= 0))

    n = len(verts)
    for i in range(n):
        vp, v, vn = verts[i - 1], verts[i], verts[(i + 1) % n]
        d0 = np.array(v) - np.array(vp)
        d0 = d0 / np.hypot(*d0)
        d1 = np.array(vn) - np.array(v)
        d1 = d1 / np.hypot(*d1)
        n0 = np.array([-d0[1], d0[0]])
        n1 = np.array([-d1[1], d1[0]])
        sgn = -1.0 if d0[0] * d1[1] - d0[1] * d1[0] > 0 else 1.0
        a = np.array(v) + sgn * h * n0
        b = np.array(v) + sgn * h * n1
        if kind == "bevel":
            out |= tri(v, a, b)
            continue
        try:
            ts = np.linalg.solve(np.array([[d0[0], -d1[0]], [d0[1], -d1[1]]]), b - a)
            m = a + ts[0] * d0
            if np.hypot(*(m - np.array(v))) <= 4 * h:
                out |= tri(v, a, m)
                out |= tri(v, m, b)
            else:
                out |= tri(v, a, b)
        except np.linalg.LinAlgError:
            out |= tri(v, a, b)
    return out


def report_footprint(rows):
    y0, y1, x0, x1 = QUAD_BOX
    models = [("butt", "butt", None), ("butt+bevel", "butt", "bevel"),
              ("butt+miter", "butt", "miter"), ("butt+round", "butt", "round"),
              ("squarecap", "square", None)]
    print(f"{'test':<14}{'width':>7}{'ref':>8} | {'model':<12}{'err':>7}"
          f"{'missing':>9}{'extra':>7}{'% of ink':>10}")
    for w, t, g, o in rows:
        if w not in (4.0, 8.0, 16.0, 32.0, 56.0, 63.0):
            continue
        for ref, label in ((ink(g)[y0:y1, x0:x1], "golden"),
                           (ink(o)[y0:y1, x0:x1], "ours")):
            scored = []
            for name, cap, join in models:
                m = footprint(w, cap, join)
                miss = int((ref & ~m).sum())
                extra = int((m & ~ref).sum())
                scored.append((miss + extra, name, miss, extra))
            scored.sort()
            first = True
            for err, name, miss, extra in scored:
                head = f"{t:<14}{w:7.1f}{label:>8} | " if first else f"{'':<14}{'':>7}{'':>8} | "
                first = False
                print(head + f"{name:<12}{err:7d}{miss:9d}{extra:7d}"
                             f"{100 * err / max(1, ref.sum()):10.2f}")


def report_classify(rows):
    print(f"{'test':<14}{'width':>8}{'struct ch':>11} | {'gold-only':>10}"
          f"{'ours-only':>10}{'colour':>9} | {'|d| 2-8':>9}{'9-32':>8}"
          f"{'33-96':>8}{'>96':>8}")
    tot = np.zeros(7, dtype=np.int64)
    for w, t, g, o in rows:
        lg, lo = ink(g), ink(o)
        d = np.abs(g - o)
        worst = d.max(axis=2)
        struct = worst > 1
        gold_only = int((struct & lg & ~lo).sum())
        ours_only = int((struct & lo & ~lg).sum())
        shared = struct & lg & lo
        v = worst[shared]
        bins = [int(((v >= 2) & (v <= 8)).sum()), int(((v > 8) & (v <= 32)).sum()),
                int(((v > 32) & (v <= 96)).sum()), int((v > 96).sum())]
        ch = int((d > 1).sum())
        tot += [ch, gold_only, ours_only, int(shared.sum())] + bins[:3]
        print(f"{t:<14}{w:8.3f}{ch:11d} | {gold_only:10d}{ours_only:10d}"
              f"{int(shared.sum()):9d} | {bins[0]:9d}{bins[1]:8d}{bins[2]:8d}{bins[3]:8d}")
    px = tot[1] + tot[2] + tot[3]
    if not px:
        return
    print(f"\n  structural channels {tot[0]:,} over {px:,} structural pixels")
    print(f"    golden-only ink (we under-cover) {tot[1]:9,}  {100*tot[1]/px:5.1f}%")
    print(f"    ours-only ink   (we over-cover)  {tot[2]:9,}  {100*tot[2]/px:5.1f}%")
    print(f"    colour on ink both agree about   {tot[3]:9,}  {100*tot[3]/px:5.1f}%")
    print("  A colour delta larger than a third of the range is a different edge "
          "winning\n  the overlap, not an interpolation error.")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--captures", required=True,
                    help="directory of <Suite>::<test>.png")
    ap.add_argument("--goldens", default=os.path.expanduser("~/goldens/results"))
    ap.add_argument("--edge", action="store_true",
                    help="coverage rule from the one axis-aligned segment")
    ap.add_argument("--footprint", action="store_true",
                    help="fit a footprint model on the isolated QUADS primitive")
    ap.add_argument("--classify", action="store_true",
                    help="split the residual into coverage and colour classes")
    args = ap.parse_args()

    if not (args.edge or args.footprint or args.classify):
        args.edge = args.footprint = args.classify = True

    rows = list(captures(args.captures, args.goldens))
    if not rows:
        sys.exit(f"no {SUITE} Line_* captures matched in {args.captures}")

    if args.edge:
        print("== coverage rule, from the vertical quad-strip edge ==")
        report_edge(rows)
        print()
    if args.footprint:
        print("== footprint model, on the isolated QUADS primitive ==")
        report_footprint(rows)
        print()
    if args.classify:
        print("== residual classes ==")
        report_classify(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
