#!/usr/bin/env python3
"""Confirm framedump_check.py can tell the two arms apart.

A checker that says NOT SERIALISED is worth nothing until something has made
it say SERIALISED, so this builds both dumps and asserts each verdict.  The
serialising dump is the mutant: it is exactly what the Debug Capture path
writes -- one draw per command buffer, one submit per draw.

    docs/lanes/diagdump77/framedump_check_selftest.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(HERE, "framedump_check.py")


def write_dump(path, *, serialised, frames=3, draws=40, merge=False,
               trailer=True):
    recs = [{
        "t": "session", "schema": 1, "id": 1758240000, "armed_by": "marker",
        "spec": "3", "frames": frames, "images": True, "cap_mb": 96,
        "wall": 1758240000, "uptime_ms": 9000, "draw_merge": merge,
        "draw_reorder": False, "surface_scale": 1, "submit_frames": 3,
        "per_draw_finish": False, "also_diag": False, "driver": "selftest",
    }]
    submits = 100
    for f in range(frames):
        first = submits
        for n in range(draws):
            if serialised:
                # A finish before every draw: the command buffer never holds
                # more than the draw being recorded, and each draw submits.
                cb_draws = 0
                submits += 1
            else:
                cb_draws = n
            recs.append({
                "t": "draw", "f": f, "n": n, "kind": "draw_arrays",
                "count": 12, "cb": 1, "cb_draws": cb_draws,
                "submits": submits, "vkframe": f % 3, "in_rp": 1,
                "dq": 0, "dq_active": 0, "rw": 0, "rw_active": 0,
                "prim": 4, "shader": "%016x" % (n * 7), "pipeline": "0x1",
                "color": None, "tex": [],
            })
        if not serialised:
            submits += 1  # the flip's own submission
        recs.append({
            "t": "frame", "f": f, "draws": draws,
            "submits_in_frame": submits - first, "submits": submits,
            "nv2a_frame": 1000 + f, "image": "framedump_1_f%03d.ppm" % f,
            "w": 640, "h": 480, "diag_active": 1 if serialised else 0,
            "wall": 1758240001 + f,
        })
    if trailer:
        recs.append({"t": "end", "why": "all frames dumped", "frames": frames,
                     "draws": frames * draws, "bytes": 123456,
                     "wall": 1758240010})

    with open(path, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def run(path):
    p = subprocess.run([sys.executable, CHECK, path], capture_output=True,
                       text=True)
    return p.returncode, p.stdout


def main():
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        live = os.path.join(tmp, "live.jsonl")
        ser = os.path.join(tmp, "serialised.jsonl")
        write_dump(live, serialised=False)
        write_dump(ser, serialised=True)

        rc, out = run(live)
        if rc != 0 or "NOT SERIALISED by cb_draws" not in out \
                or "NOT SERIALISED by submits" not in out:
            failures.append("live dump was not recognised as finish-free:\n"
                            + out)

        rc, out = run(ser)
        if rc != 1 or "SERIALISED: no command buffer" not in out \
                or "SERIALISED by submits" not in out:
            failures.append("the serialising mutant did not trip the check:\n"
                            + out)

        # A truncated dump must be called out rather than silently scored on
        # fewer frames -- a short dump reads as a clean one otherwise.
        cut = os.path.join(tmp, "cut.jsonl")
        write_dump(cut, serialised=False, trailer=False)
        rc, out = run(cut)
        if "NO TRAILER" not in out:
            failures.append("a truncated dump was not reported:\n" + out)

        # And the scope note, which is what stops a merge-off dump being read
        # as evidence about merging.
        rc, out = run(live)
        if "SCOPE: draw_merge was OFF" not in out:
            failures.append("merge-off dump carried no scope note:\n" + out)
        merged = os.path.join(tmp, "merged.jsonl")
        write_dump(merged, serialised=False, merge=True)
        rc, out = run(merged)
        if "SCOPE: draw_merge was OFF" in out:
            failures.append("merge-on dump still claimed merge was off:\n"
                            + out)

    for f in failures:
        print("FAIL " + f)
    print("framedump_check selftest: %s" % ("FAILED" if failures else "ok"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
