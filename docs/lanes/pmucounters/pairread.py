#!/usr/bin/env python3
"""The report-wait pair (NOTES 3f): every pre-registered measure, per arm.

  pairread.py <logcat or result dir> [...] [--after REGEX]

Window: from the route's `mark gameplay` to the end of the log.

Per arm:
  mechanism  [occl804] config wait=, the `[occl804] f=` lines and how many
             have q>0, and the fw= ms/frame of every call site whose symbol
             is pgraph_vk_process_pending_reports_internal (a run numbers its
             sites in first-use order, so one symbol can hold two numbers:
             ctx=none and ctx=rep);
  measures   frames/wall fps and the share of pace windows >= 29.7 fps
             (hakuX-pace); vCPU on-CPU and off-CPU ms/frame ([tlb68], off =
             wall less on-CPU); and from [hakuX-ft1] (frame-weighted): lw (the
             DMA_PUT store's pfifo.lock wait), vblk, vrq, vw by reason, the
             PFIFO thread's fence wait (pw fence) and the top fw= sites.
Then the same frametrace fields by fps bin of each [hakuX-ft1] line.
"""
import os
import re
import sys
from collections import defaultdict

PACE = re.compile(r"hakuX-pace\(\s*\d+\): f=(\d+) .* ms=([\d.]+)")
TLB = re.compile(r"\[tlb68\] w=\d+ dt=(\d+) cpu=(\d+)")
OCFG = re.compile(r"\[occl804\] config log=(\d+) after_s=\d+ wait=(\d+)")
OF = re.compile(r"\[occl804\] f=\d+ wait=(\d+) procs=\d+ q=(\d+) qnz=\d+ "
                r"pend=(\d+)")
SITE = re.compile(r"\[hakuX-ft1\] site #(\d+) row=(\w) ctx=(\w+) "
                  r"reason=(\w+) .* sym=(\S+)")
FT = re.compile(r"\[hakuX-ft1\] n=(\d+) rt_ms=(\d+) ")
FIELD = re.compile(r" (lw|vblk|vrq|vrun)=([\d.]+)")
VEC = re.compile(r" (vw|pw)=([\d.,]+)")
FW = re.compile(r" fw=(\S+)")
W = ["bql", "pfl", "pgl", "halt", "idle", "fence", "submit", "rthr", "dl",
     "oth"]
REP = "pgraph_vk_process_pending_reports_internal"
BINS = [(0, 24, "< 24"), (24, 27, "24-27"), (27, 29, "27-29"),
        (29, 29.7, "29-29.7"), (29.7, 1e9, ">= 29.7")]


def binname(fps):
    for lo, hi, name in BINS:
        if lo <= fps < hi:
            return name
    return "?"


def new_acc():
    return {"n": 0, "lw": 0.0, "vblk": 0.0, "vrq": 0.0, "vrun": 0.0,
            "vw": [0.0] * len(W), "pw": [0.0] * len(W),
            "fw": defaultdict(float)}


def add(acc, n, fields, vecs, fw):
    acc["n"] += n
    for k, v in fields.items():
        acc[k] += v * n
    for k in ("vw", "pw"):
        for i, v in enumerate(vecs.get(k, [])[:len(W)]):
            acc[k][i] += v * n
    for site, ms in fw:
        acc["fw"][site] += ms * n


def read(path, after):
    if os.path.isdir(path):
        path = os.path.join(path, "logcat.txt")
    sites = {}
    started = False
    r = {"cfg": None, "of": 0, "of_q": 0, "of_wait": set(), "frames": 0,
         "pace_ms": 0.0, "win": [], "dt": 0, "cpu": 0, "all": new_acc(),
         "bins": defaultdict(new_acc), "sites": sites, "path": path,
         "ft_bad": 0}
    prev_f, prev_rt = None, None
    for line in open(path, errors="replace"):
        m = SITE.search(line)
        if m:
            sites[m.group(1)] = (m.group(2), m.group(3), m.group(5))
            continue
        m = OCFG.search(line)
        if m:
            r["cfg"] = (int(m.group(1)), int(m.group(2)))
            continue
        if not started:
            started = re.search(after, line) is not None
            continue
        m = PACE.search(line)
        if m:
            f, ms = int(m.group(1)), float(m.group(2))
            if prev_f is not None and ms > 0 and f >= prev_f:
                r["frames"] += f - prev_f
                r["pace_ms"] += ms
                r["win"].append((f - prev_f) * 1000.0 / ms)
            prev_f = f
            continue
        m = TLB.search(line)
        if m:
            r["dt"] += int(m.group(1))
            r["cpu"] += int(m.group(2))
            continue
        m = OF.search(line)
        if m:
            r["of"] += 1
            r["of_wait"].add(int(m.group(1)))
            if int(m.group(2)) > 0:
                r["of_q"] += 1
            continue
        m = FT.search(line)
        if m:
            n, rt = int(m.group(1)), int(m.group(2))
            fields = {k: float(v) for k, v in FIELD.findall(line)}
            vecs = {k: [float(x) for x in v.split(",")]
                    for k, v in VEC.findall(line)}
            fw = []
            mf = FW.search(line)
            if mf:
                for item in mf.group(1).split(","):
                    head, _, val = item.partition(":")
                    site = head.rpartition("#")[2]
                    try:
                        fw.append((site, float(val.split("/")[0])))
                    except ValueError:
                        pass
            # a 1 s summary cannot hold more than ~1 s of one thread's time
            # (waits.py's guard: fpstelemetry1008's run has one line booking
            # 40 s of lock wait)
            if n > 0 and (fields.get("vrun", 0) +
                          sum(vecs.get("vw", []))) * n > 2500:
                r["ft_bad"] += 1
                prev_rt = rt
                continue
            if n > 0:
                add(r["all"], n, fields, vecs, fw)
                if prev_rt is not None and rt > prev_rt:
                    fps = n * 1000.0 / (rt - prev_rt)
                    add(r["bins"][binname(fps)], n, fields, vecs, fw)
            prev_rt = rt
    return r


def per(acc, key):
    return acc[key] / acc["n"] if acc["n"] else float("nan")


def rep_ms(r, acc):
    return sum(ms for s, ms in acc["fw"].items()
               if r["sites"].get(s, ("", "", ""))[2].startswith(REP)) / \
        acc["n"] if acc["n"] else float("nan")


def site_name(r, s):
    row, ctx, sym = r["sites"].get(s, ("?", "?", "?"))
    return "#%s %s.%s %s" % (s, row, ctx, sym)


def main(argv):
    after = r"hakuX-route.*mark gameplay"
    paths = []
    i = 0
    while i < len(argv):
        if argv[i] == "--after":
            after = argv[i + 1]
            i += 2
            continue
        paths.append(argv[i])
        i += 1
    if not paths:
        print(__doc__)
        return 2
    runs = [read(p, after) for p in paths]
    print("| arm | occl config (log, wait) | occl f= lines (q>0) | "
          "reports site ms/frame | frames/wall fps | share >= 29.7 | "
          "on-CPU | off-CPU | lw | vblk | vrq | PFIFO fence |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in runs:
        fr = r["frames"]
        wall = r["pace_ms"] / fr if fr else float("nan")
        on = r["cpu"] / r["dt"] * wall if r["dt"] else float("nan")
        share = (sum(1 for x in r["win"] if x >= 29.7) / len(r["win"])
                 if r["win"] else float("nan"))
        a = r["all"]
        print("| %s | %s | %d (%d) | %.2f | %.2f | %.2f | %.1f | %.1f | "
              "%.2f | %.2f | %.2f | %.2f |" % (
                  os.path.basename(os.path.dirname(r["path"])) or r["path"],
                  "%d, %d" % r["cfg"] if r["cfg"] else "none",
                  r["of"], r["of_q"], rep_ms(r, a),
                  fr * 1000.0 / r["pace_ms"] if r["pace_ms"] else 0, share,
                  on, wall - on, per(a, "lw"), per(a, "vblk"),
                  per(a, "vrq"), a["pw"][5] / a["n"] if a["n"] else 0))
    for r in runs:
        a = r["all"]
        print("\n## %s (%d frametrace frames; %d impossible lines "
              "dropped)" % (r["path"], a["n"], r["ft_bad"]))
        if not a["n"]:
            continue
        print("vw (ms/frame): " + ", ".join(
            "%s %.2f" % (W[k], a["vw"][k] / a["n"]) for k in range(len(W))
            if a["vw"][k] / a["n"] >= 0.05))
        top = sorted(a["fw"].items(), key=lambda kv: -kv[1])[:8]
        print("fw top sites (ms/frame): " + "; ".join(
            "%s %.2f" % (site_name(r, s), ms / a["n"]) for s, ms in top))
        top3 = [s for s, _ in top[:3]]
        print("| fps bin | frames | lw | vblk | vw pgl | vw bql | "
              "PFIFO fence | reports sites | vrun | " +
              " | ".join("site #%s" % s for s in top3) + " |")
        print("|---" * (9 + len(top3)) + "|")
        for _, _, name in BINS:
            b = r["bins"].get(name)
            if not b or not b["n"]:
                continue
            print("| %s | %d | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f | "
                  "%.2f | " % (name, b["n"], per(b, "lw"), per(b, "vblk"),
                               b["vw"][2] / b["n"], b["vw"][0] / b["n"],
                               b["pw"][5] / b["n"], rep_ms(r, b),
                               per(b, "vrun")) +
                  " | ".join("%.2f" % (b["fw"][s] / b["n"]) for s in top3) +
                  " |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
