#!/usr/bin/env python3
"""Shrink a combiner program whose specialised and uber renders differ.

    reduce.py BASELINE COMB_BIN [--want float|8bit]

Greedy delta debugging over comb_N.bin's 36 words: drop stages, send outputs
to DISCARD, set inputs to ZERO, one field at a time, keeping every change
after which the two renders still differ. Prints the minimal program and
both shaders' combiner code.
"""
import argparse
import os
import struct
import subprocess
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_check  # noqa: E402

OUT = os.path.join(HERE, "build", "reduce")


def differs(baseline, words, want):
    subprocess.run([os.path.join(HERE, "build", "uberhost"), "--out", OUT,
                    "--baseline", baseline, "--comb",
                    ",".join("0x%x" % w for w in words)],
                   check=True, capture_output=True)
    args = types.SimpleNamespace(dir=OUT, glslang=render_check.main.__defaults__
                                 if False else GLSLANG, mutant=False)
    i, status, msg = render_check.check(args, 0)
    if status not in ("ok", "DIFF"):
        return False, msg
    f8 = int(msg.split("8-bit-diff ")[1].split()[0])
    ff = int(msg.split("float-diff ")[1].split()[0])
    return (f8 if want == "8bit" else ff) > 0, msg


def candidates(w):
    n = w[34] & 0xFF
    if n > 0:
        # one stage fewer, dropping the last
        c = list(w)
        c[34] = (w[34] & ~0xFF) | (n - 1)
        for j in range(4):
            c[(n - 1) * 4 + j] = 0
        yield "stages %d" % (n - 1), c
    for s in range(min(n, 8)):
        for half, (iw, ow) in (("rgb", (0, 1)), ("alpha", (2, 3))):
            o = w[s * 4 + ow]
            for name, sh in (("ab", 4), ("cd", 0), ("ms", 8)):
                if (o >> sh) & 0xF:
                    c = list(w)
                    c[s * 4 + ow] = o & ~(0xF << sh)
                    yield "s%d %s %s->discard" % (s, half, name), c
            for name, sh in (("flags", 12),):
                if o >> sh:
                    c = list(w)
                    c[s * 4 + ow] = o & 0xFFF
                    yield "s%d %s flags->0" % (s, half), c
            iv = w[s * 4 + iw]
            for k, sh in enumerate((24, 16, 8, 0)):
                if (iv >> sh) & 0xFF:
                    c = list(w)
                    c[s * 4 + iw] = iv & ~(0xFF << sh)
                    yield "s%d %s in%s->0" % (s, half, "abcd"[k]), c
    for wi, names in ((32, "ABCD"), (33, "EFG")):
        for k, sh in enumerate((24, 16, 8, 0)[:len(names)]):
            if (w[wi] >> sh) & 0xFF:
                c = list(w)
                c[wi] = w[wi] & ~(0xFF << sh)
                if c[32] or c[33]:
                    yield "final %s->0" % names[k], c
    if w[33] & 0xFF:
        c = list(w)
        c[33] = w[33] & ~0xFF
        yield "final flags->0", c
    if w[34] & ~0xFF:
        c = list(w)
        c[34] = w[34] & 0xFF
        yield "cc flags->0", c


def main():
    global GLSLANG
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline")
    ap.add_argument("comb")
    ap.add_argument("--want", default="float", choices=("float", "8bit"))
    ap.add_argument("--glslang",
                    default="/home/justin/hakux-work/turnipfork-glslang/install/bin/glslangValidator")
    a = ap.parse_args()
    GLSLANG = a.glslang
    os.makedirs(os.path.join(HERE, "build", "render"), exist_ok=True)
    w = list(struct.unpack("<36I", open(a.comb, "rb").read()))
    ok, msg = differs(a.baseline, w, a.want)
    print("start:", msg)
    if not ok:
        return 1
    changed = True
    while changed:
        changed = False
        for label, c in candidates(w):
            ok, msg = differs(a.baseline, c, a.want)
            if ok:
                print("keep: %-28s %s" % (label, msg))
                w = c
                changed = True
                break
    print("minimal:", ",".join("0x%x" % x for x in w))
    differs(a.baseline, w, a.want)
    for kind in ("spec", "uber"):
        print("---- %s" % kind)
    txt = open(os.path.join(OUT, "spec_0000.frag")).read()
    print(txt[txt.index("// Stage 0") if "// Stage 0" in txt else txt.index("// Final Combiner"):
              txt.index("fragColor.a = ")])
    return 0


GLSLANG = None
if __name__ == "__main__":
    sys.exit(main())
