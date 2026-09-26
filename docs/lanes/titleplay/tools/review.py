#!/usr/bin/env python3
"""Pull finished title runs into a private copy, judge them, and summarise.

    review.py <ids-file> [--out DIR] [--reviewed id=yes|no ...]

<ids-file> is queue.py's output (request id first on each line). A run is
copied from $DISPATCH_DIR/results/<id> to <out>/<id> (default scratch/runs)
once it has DONE or ERROR, so the verdict and contact sheet are written to
the copy and never into the dispatcher's result directory. Prints one line
per run: state, device, marks, frames, fps median and share, first failure,
and a 30 s fps timeline over the whole run (so menus and play can be told
apart), and the path of the contact sheet to look at.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VERDICT = os.path.join(HERE, "..", "..", "..", "testing", "title_verdict.py")
sys.path.insert(0, os.path.dirname(VERDICT))
import title_verdict as tv  # noqa: E402

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")

ap = argparse.ArgumentParser()
ap.add_argument("ids")
ap.add_argument("--out", default="scratch/runs")
ap.add_argument("--reviewed", action="append", default=[])
ap.add_argument("--refresh", action="store_true", help="copy again even if present")
a = ap.parse_args()
reviewed = dict(r.split("=", 1) for r in a.reviewed)

ids = [ln.split("\t")[0].split()[0] for ln in open(a.ids) if ln.strip() and not ln.startswith("#")]
os.makedirs(a.out, exist_ok=True)
for rid in ids:
    src = os.path.join(D, "results", rid)
    dst = os.path.join(a.out, rid)
    where = "queued"
    if os.path.exists(os.path.join(D, "running", rid + ".req")):
        where = "running"
    if not os.path.isdir(src) or not (os.path.exists(os.path.join(src, "DONE"))
                                      or os.path.exists(os.path.join(src, "ERROR"))):
        print(f"{rid}: {where}")
        continue
    if a.refresh or not os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)
    if os.path.exists(os.path.join(dst, "ERROR")):
        print(f"{rid}: ERROR {open(os.path.join(dst, 'ERROR')).read().strip()[:160]}")
        continue
    cmd = [sys.executable, VERDICT, dst]
    short = rid.rsplit("-", 1)[-1]
    rv = reviewed.get(rid) or reviewed.get(short)
    if rv:
        cmd += ["--reviewed-gameplay", rv]
    subprocess.run(cmd, capture_output=True, text=True)
    v = json.load(open(os.path.join(dst, "verdict.json")))
    lc, _, _ = tv.parse_logcat(os.path.join(dst, "logcat.txt"))
    perf = [t for t, lv, tag, msg in lc if tag == "hakuX-perf" and tv.PERF.search(msg)]
    marks = [(t, msg[5:].strip()) for t, lv, tag, msg in lc
             if tag == "hakuX-route" and msg.startswith("mark ")]
    t0 = lc[0][0] if lc else 0
    # 30 s buckets of guest frames: 60 per perf line.
    tl = {}
    for t in perf:
        b = int((t - t0) // 30)
        tl[b] = tl.get(b, 0) + 60
    nb = max(tl) + 1 if tl else 0
    timeline = " ".join("%d" % round(tl.get(b, 0) / 30.0) for b in range(nb))
    mk = " ".join("%s@%ds" % (lab, t - t0) for t, lab in marks)
    frames = len(os.listdir(os.path.join(dst, "route-frames"))) if os.path.isdir(os.path.join(dst, "route-frames")) else 0
    print(f"{rid}: {v['device']} booted={v['booted']} reached={v['reached_gameplay']} by={v['gameplay_by']} "
          f"med={v.get('fps_window_median')} min={v.get('fps_window_min')} share30={v['fps_ok_share']} "
          f"crash={v['crash']} hang={v['hang']} audio={v['audio_starve_share']} scale={v['surface_scale']}\n"
          f"    marks: {mk}\n    frames={frames} sheet={dst}/contact.png\n"
          f"    fps/30s: {timeline}\n    first fail: {v['failing']}")
    if v["crash_detail"]:
        print(f"    crash: {v['crash_detail']}")
