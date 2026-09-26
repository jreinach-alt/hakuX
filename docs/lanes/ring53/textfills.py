#!/usr/bin/env python3
"""Count the pb_fill (clear-rect) calls pb_draw_text_screen issues for a text.

    textfills.py [--pbkit PATH] 'L0_FF' 'L1_FF' ...

Replicates pbkit_print.c's loop exactly, including that a run reaching the
glyph's last column is never filled. Each argument is one pb_print'ed line.
"""
import argparse
import re

PBKIT = "/home/justin/nxdk_pgraph_tests/third_party/nxdk/lib/pbkit/pbkit_print.c"


def load_font(path):
    s = open(path).read()
    body = s[s.index("systemFont[] ="):]
    body = body[body.index("{") + 1:body.index("};")]
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"//[^\n]*", "", body)
    return [int(t, 0) for t in re.findall(r"0x[0-9a-fA-F]+|\d+", body)]


def fills(font, text):
    n = 0
    for c in text.encode():
        if c in (0x20, 0x09):
            continue
        for l in range(8):
            x1 = x2 = -1
            for k in range(8):
                if font[c * 8 + l] & (0x80 >> k):
                    if x1 >= 0:
                        x2 = k
                    else:
                        x1 = k
                else:
                    if x2 >= 0:
                        n += 1
                        x1 = x2 = -1
                    elif x1 >= 0:
                        n += 1
                        x1 = -1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pbkit", default=PBKIT)
    ap.add_argument("text", nargs="+")
    a = ap.parse_args()
    font = load_font(a.pbkit)
    for t in a.text:
        f = fills(font, t)
        print("%-24r fills %4d  mod6 %d" % (t, f, f % 6))


if __name__ == "__main__":
    main()
