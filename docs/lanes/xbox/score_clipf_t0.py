#!/usr/bin/env python3
"""Score the clip_top 8 / 12 / 16 / 64 console run with wbuf_anchor_recover.py, unchanged.

    python3 docs/lanes/xbox/score_clipf_t0.py --goldens <fetched root>

Adds the new ClipF variants -- and 4, from the previous run -- to the tool's
PRIMS table exactly as it defines 32/35/128/224 (the floor quad, clip_left
150, the unclipped FloorQuad ZS0 as its plane), then runs the tool's own
main(). No line of the tool is edited.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "testing"))
import wbuf_anchor_recover as w  # noqa: E402

for ct in (4, 8, 12, 16, 64):
    w.PRIMS["ClipF-150-%03d" % ct] = (w.FLOOR, 150, ct, "FloorQuad")
sys.exit(w.main())
