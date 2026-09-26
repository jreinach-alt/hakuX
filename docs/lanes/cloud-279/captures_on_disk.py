#!/usr/bin/env python3
"""#279: date every DotZW/DotST capture on disk and score it against silicon.

DotZW is scored on the decoded depth word under the quad; DotST (the
control, same stage-1/2 dot-product interpolation) on raw RGB over the
whole frame.

Usage: captures_on_disk.py GOLDEN_DIR RESULTS_DIR [RESULTS_DIR ...]
"""
import glob
import json
import os
import sys
import time

import numpy as np
from PIL import Image

import dotzw_fit as f


def ref_of(run_dir):
    for name in ("request.json", "meta.json"):
        p = os.path.join(run_dir, name)
        if os.path.exists(p):
            try:
                j = json.load(open(p))
            except ValueError:
                continue
            for k in ("ref", "apk_sha", "sha", "b_ref"):
                if k in j:
                    return f"{k}={str(j[k])[:12]}"
    return "ref=?"


def main():
    gdir = sys.argv[1]
    gold_zw = f.decode_depth(os.path.join(gdir, "Pixel_shader", "DotZW.png"))
    gold_st = np.asarray(Image.open(os.path.join(gdir, "Pixel_shader", "DotST.png"))
                         .convert("RGB"), dtype=np.int64)
    rows = []
    for rdir in sys.argv[2:]:
        for zw in glob.glob(os.path.join(rdir, "*", "captures*", "Pixel_shader::DotZW.png")) + \
                glob.glob(os.path.join(rdir, "*", "*", "*", "Pixel_shader::DotZW.png")):
            run = zw.split(os.sep)
            run_dir = os.path.dirname(os.path.dirname(zw))
            d = f.decode_depth(zw)
            exact_zw = np.mean(d == gold_zw) * 100
            st_path = os.path.join(os.path.dirname(zw), "Pixel_shader::DotST.png")
            st = "n/a"
            if os.path.exists(st_path):
                c = np.asarray(Image.open(st_path).convert("RGB"), dtype=np.int64)
                st = f"{int(np.sum(np.any(c != gold_st, axis=-1)))} px differ"
            rows.append((os.path.getmtime(zw), run_dir, ref_of(run_dir),
                         len(np.unique(d)), exact_zw, st))
    for mt, run_dir, ref, nuniq, ex, st in sorted(rows):
        print(f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(mt))}  "
              f"{os.path.relpath(run_dir, '/home/justin/hakux-work'):60s} {ref:18s} "
              f"DotZW distinct depths {nuniq:6d} exact {ex:6.2f}%  DotST {st}")


if __name__ == "__main__":
    main()
