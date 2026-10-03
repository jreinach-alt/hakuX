#!/usr/bin/env python3
# Compare a screencap region against a reference crop. Used by route.sh's
# `waitfor`/`press-until` steps (see route.sh's grammar comment).
#
#   waitfor_match.py <frame.png> <ref.png> <x,y,w,h> <threshold>
#
# Crops <frame.png> to the given region, downscales both the crop and the
# reference to a small fixed size in grayscale, and scores the mean absolute
# pixel difference (0-255 scale). Prints "<score> MATCH" and exits 0 if
# score <= threshold, else prints "<score> NOMATCH" and exits 1. Exits 2 on
# a usage or image-read error (treated as "not yet" by the caller, not a
# route failure by itself -- a single bad screencap should not abort a
# route that a moment later would have matched).
import sys

from PIL import Image
import numpy as np

CMP_SIZE = (64, 48)


def region_score(frame_path, ref_path, box):
    frame = Image.open(frame_path).convert("RGB")
    x, y, w, h = box
    region = frame.crop((x, y, x + w, y + h)).convert("L").resize(CMP_SIZE)
    ref = Image.open(ref_path).convert("L").resize(CMP_SIZE)
    a = np.asarray(region, dtype=np.int16)
    b = np.asarray(ref, dtype=np.int16)
    return float(np.abs(a - b).mean())


def main(argv):
    if len(argv) != 5:
        print("usage: waitfor_match.py <frame.png> <ref.png> <x,y,w,h> <threshold>", file=sys.stderr)
        return 2
    frame_path, ref_path, region_arg, threshold_arg = argv[1:5]
    try:
        x, y, w, h = (int(v) for v in region_arg.split(","))
        threshold = float(threshold_arg)
    except ValueError:
        print(f"waitfor_match.py: bad region/threshold: {region_arg!r} {threshold_arg!r}", file=sys.stderr)
        return 2
    try:
        score = region_score(frame_path, ref_path, (x, y, w, h))
    except Exception as exc:
        print(f"waitfor_match.py: {exc}", file=sys.stderr)
        return 2
    match = score <= threshold
    print(f"{score:.3f} {'MATCH' if match else 'NOMATCH'}")
    return 0 if match else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
