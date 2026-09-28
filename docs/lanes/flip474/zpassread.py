#!/usr/bin/env python3
"""Is the ZPASS report one value in every ZPass_pixel_count capture of a run?

    python3 zpassread.py bands <capture.png>
    python3 zpassread.py same <ref capture.png> <band top y>:<value chars> <result dir> [...]

The guest prints `.report: 0x<hex> (<dec>) ...` in a fixed-width font, so the
value's glyphs sit at fixed columns. `bands` lists the text rows of one
capture (top y, bottom y) so the `.report` row of a capture whose value was
read by eye can be named. `same` then takes that row of REF and, in every
ZPass capture of each run, looks for the row whose `.report:` glyphs match
REF's, and says whether the value glyphs beside it match REF's too. It reads
no digits: the answer is "the value REF shows" or "another value".

Needs PIL. Exits 2 without it rather than printing nothing.
"""
import os
import sys

try:
    from PIL import Image
except ImportError:
    print("zpassread: PIL is not installed; nothing was read")
    sys.exit(2)

PREFIX = (16, 108)   # ".report:" columns
VALUE = (108, 264)   # the default value columns; `same` narrows them
VALUE_W = list(VALUE)
TEXT_X = (16, 420)
H = 18               # glyph rows compared


def load(p):
    img = Image.open(p).convert("RGB")
    px = img.load()
    w, h = img.size
    return [[1 if min(px[x, y]) > 200 else 0 for x in range(w)]
            for y in range(h)]


def block(g, y0, x0, x1):
    return tuple(tuple(g[y][x0:x1]) for y in range(y0, y0 + H))


def bands(g):
    out, start = [], None
    for y in range(len(g)):
        has = any(g[y][TEXT_X[0]:TEXT_X[1]])
        if has and start is None:
            start = y
        elif not has and start is not None:
            out.append((start, y - 1))
            start = None
    return out


def main():
    if sys.argv[1] == "bands":
        for b in bands(load(sys.argv[2])):
            print(b)
        return
    ref = load(sys.argv[2])
    y_ref, _, nchar = sys.argv[3].partition(":")
    y_ref = int(y_ref)
    # The value and the blank cell after it, at 10 px a character, so that
    # what a test prints after the value ("=? n" or "[PASS]") is not compared.
    value = (VALUE[0], 110 + 10 * (int(nchar) + 1) - 2) if nchar else VALUE
    rp, rv = block(ref, y_ref, *PREFIX), block(ref, y_ref, *value)
    VALUE_W[:] = value
    if not any(any(r) for r in rp) or not any(any(r) for r in rv):
        print("zpassread: REF has no text at that row")
        sys.exit(2)
    for run in sys.argv[4:]:
        d = os.path.join(run, "captures1")
        names = sorted(f for f in os.listdir(d)
                       if f.startswith("ZPass_pixel_count::")
                       and f.endswith(".png") and "_ZB" not in f)
        same, other, norow = [], [], []
        for f in names:
            g = load(os.path.join(d, f))
            rows = [y for y in range(60, 320) if block(g, y, *PREFIX) == rp]
            if not rows:
                norow.append(f)
            elif any(block(g, y, *VALUE_W) == rv for y in rows):
                same.append(f)
            else:
                other.append(f)
        print("%s: captures=%d value-as-REF=%d another-value=%d "
              "no-.report-row=%d" % (os.path.basename(run.rstrip("/")),
                                     len(names), len(same), len(other),
                                     len(norow)))
        for f in other:
            print("     another value:", f)
        for f in norow:
            print("     no row:", f)


if __name__ == "__main__":
    main()
