#!/usr/bin/env python3
"""Score the clip_top = 4 console run with wbuf_anchor_recover.py, unchanged.

    python3 docs/lanes/xbox/score_clipf04.py --goldens <fetched root>

The tool lists `ClipF` at clip_top 32, 35, 128 and 224. This adds 4 exactly as
the tool defines those -- (FLOOR, 150, ct, "FloorQuad"): the same floor quad,
clip_left 150, the unclipped FloorQuad ZS0 as its plane -- and then runs the
tool's own main(). No line of the tool is edited; it is not this lane's file.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "testing"))
import wbuf_anchor_recover as w  # noqa: E402

w.PRIMS["ClipF-150-004"] = (w.FLOOR, 150, 4, "FloorQuad")
# _QUADS is built from PRIMS at import; without this, --selectors would read
# second_of_quad False on this quad's second triangle.
w._QUADS.add("ClipF-150-004")
sys.exit(w.main())
