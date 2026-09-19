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
               trailer=True, header_finish=None, schema=2, img_sync=0,
               drop_cb=False):
    # header_finish defaults to the truth for this arm.  Passing it explicitly
    # builds a dump whose header contradicts its own draw records, which is
    # what the disagreement check exists to catch.
    if header_finish is None:
        header_finish = serialised
    recs = [{
        "t": "session", "schema": schema, "id": 1758240000, "armed_by": "marker",
        "spec": "3", "frames": frames, "images": True, "cap_mb": 96,
        "wall": 1758240000, "uptime_ms": 9000, "draw_merge": merge,
        "draw_reorder": False, "surface_scale": 1, "submit_frames": 3,
        "per_draw_finish": header_finish, "also_diag": serialised,
        "driver": "selftest",
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
            rec = {
                "t": "draw", "f": f, "n": n, "kind": "draw_arrays",
                "count": 12, "cb": 1, "cb_draws": cb_draws,
                "submits": submits, "vkframe": f % 3, "in_rp": 1,
                "dq": 0, "dq_active": 0, "rw": 0, "rw_active": 0,
                "prim": 4, "shader": "%016x" % (n * 7), "pipeline": "0x1",
                "color": None, "tex": [],
            }
            if drop_cb:
                # The shape a build predating the falsifier columns, or a file
                # that is not a frame dump at all, would have.
                del rec["cb_draws"]
            recs.append(rec)
        if not serialised:
            submits += 1  # the flip's own submission
        frame = {
            "t": "frame", "f": f, "draws": draws,
            "submits_in_frame": submits - first, "submits": submits,
            "nv2a_frame": 1000 + f, "image": "framedump_1_f%03d.ppm" % f,
            "w": 640, "h": 480, "diag_active": 1 if serialised else 0,
            "wall": 1758240001 + f,
        }
        if img_sync is not None:
            frame["img_sync"] = img_sync
        recs.append(frame)
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

        # Neither honest arm may raise the disagreement check, or it would fire
        # on every real dump and mean nothing.
        for name, path in (("live", live), ("serialised", ser)):
            if "INSTRUMENT DISAGREES" in run(path)[1]:
                failures.append("the %s arm is self-consistent but was "
                                "reported as disagreeing" % name)

        # The header lying about the run is its own mutant: this is the shape
        # the field had when it was a bare `false` literal, so a dump that
        # serialised would still have claimed it did not.  Without this, the
        # disagreement check is a branch nothing has ever taken.
        liar = os.path.join(tmp, "liar.jsonl")
        write_dump(liar, serialised=True, header_finish=False)
        rc, out = run(liar)
        if rc != 1 or "INSTRUMENT DISAGREES WITH ITSELF" not in out:
            failures.append("a header contradicting its own draw records was "
                            "not caught:\n" + out)

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

        # A correct live dump of a scene that is barely drawing -- a loading
        # screen, a pause menu, the tail of a title that stopped issuing
        # geometry, all of which `afterNN` can land on.  One draw per frame
        # degrades BOTH columns at once, so the checker used to report
        # SERIALISED (the falsification of the instrument's whole thesis) and
        # then call the instrument self-contradictory, from a dump that
        # behaved correctly.  It must refuse instead, on its own status.
        thin = os.path.join(tmp, "thin.jsonl")
        write_dump(thin, serialised=False, frames=30, draws=1)
        rc, out = run(thin)
        if rc != 3 or "INSUFFICIENT SAMPLE" not in out:
            failures.append("a one-draw-per-frame live dump did not get the "
                            "insufficient-sample refusal:\n" + out)
        if "SERIALISED" in out or "INSTRUMENT DISAGREES" in out:
            failures.append("the refused dump still carried a verdict:\n"
                            + out)

        # The other leg of the refusal: frames drew enough, but there are not
        # enough draws in the whole dump to rest anything on.
        short = os.path.join(tmp, "short.jsonl")
        write_dump(short, serialised=False, frames=3, draws=5)
        rc, out = run(short)
        if rc != 3 or "INSUFFICIENT SAMPLE" not in out:
            failures.append("a 15-draw dump did not get the "
                            "insufficient-sample refusal:\n" + out)

        # ...and the refusal must not swallow a dump that CAN be read: the
        # serialising mutant is the case where a wrongly-drawn threshold would
        # hide the falsifier firing.
        rc, out = run(ser)
        if "INSUFFICIENT SAMPLE" in out:
            failures.append("the serialising mutant was refused for sample "
                            "size:\n" + out)

        # The images are a separate claim.  A schema-1 dump's PPMs are one
        # completed download behind the records they are filed under, and a
        # schema-2 record that names an image without naming the fence it
        # waited on cannot show that it was written after one.
        old = os.path.join(tmp, "schema1.jsonl")
        write_dump(old, serialised=False, schema=1, img_sync=None)
        rc, out = run(old)
        if "IMAGES: schema 1" not in out:
            failures.append("a schema-1 dump's images were not flagged as "
                            "lagging their records:\n" + out)
        blind = os.path.join(tmp, "blind.jsonl")
        write_dump(blind, serialised=False, schema=2, img_sync=None)
        rc, out = run(blind)
        if rc != 1 or "no img_sync" not in out:
            failures.append("a schema-2 image with no img_sync was accepted:\n"
                            + out)

        # The column every verdict rests on, absent.
        nocb = os.path.join(tmp, "nocb.jsonl")
        write_dump(nocb, serialised=False, drop_cb=True)
        rc, out = run(nocb)
        if rc != 1 or "no draw record carries cb_draws" not in out:
            failures.append("a dump with no cb_draws column was not "
                            "reported:\n" + out)

    for f in failures:
        print("FAIL " + f)
    print("framedump_check selftest: %s" % ("FAILED" if failures else "ok"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
