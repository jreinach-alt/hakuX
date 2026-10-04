#!/usr/bin/env python3
"""pair_hitch.py <result-dir> [--boot-mark gameplay|play|booted]

Reads one dispatch result's logcat with hitch_report.py's own hitch finder
and splits the scored window at a fixed 120 s from the mark, so a pre/post
pre-build pair can be read for first-120s vs whole-window hitches without
re-deriving hitch_report's HITCH_MS/classification rules.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "testing"))
import hitch_report as hr
import title_verdict as tv


def read(rdir, mark_label="gameplay"):
    lc, _gaps, _open = tv.parse_logcat(os.path.join(rdir, "logcat.txt"))
    marks = [(t, msg[5:].strip()) for t, lv, tag, msg in lc
             if tag == "hakuX-route" and msg.startswith("mark ")]
    byl = {lab: t for t, lab in marks}
    mark_t = byl.get(mark_label)
    soak_end = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "soak end"]
    end_t = soak_end[-1] if soak_end else (lc[-1][0] if lc else None)
    if mark_t is None or end_t is None:
        return dict(rdir=rdir, error="no mark %r or no end" % mark_label, marks=marks)
    hs = hr.find_hitches(lc, mark_t, end_t)
    first120 = [h for h in hs if h["off_s"] < 120.0]
    whole = hs
    def summarize(hh):
        aligned = sum(1 for h in hh if h["class"] in ("shader", "both"))
        return dict(n=len(hh), worst_ms=round(max((h["max_ms"] for h in hh), default=0.0), 1),
                    shader_aligned=aligned,
                    classes={c: sum(1 for h in hh if h["class"] == c) for c in
                             ("shader", "texture", "both", "unexplained")})
    return dict(rdir=os.path.basename(rdir), mark=mark_label, scored_s=round(end_t - mark_t, 1),
                first120=summarize(first120), whole=summarize(whole))


if __name__ == "__main__":
    rdir = sys.argv[1]
    mark = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--boot-mark" else \
           (sys.argv[2] if len(sys.argv) > 2 else "gameplay")
    print(json.dumps(read(rdir, mark), indent=2))
