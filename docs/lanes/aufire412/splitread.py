#!/usr/bin/env python3
"""Per-frame cost split of a perflog title soak over a time window (lane.aufire412, #412).

    splitread.py <logcat.txt> --window A,B      (seconds since the first hakuX line)

The perflog build prints, every 60th guest frame: gfps (hakuX-perf), the phase
line (hakuX-phase), the CPU line (hakuX-cpu) and the workload line (xemu-work,
the LAST frame's counters, not a 60-frame mean). hakuX-stall prints
RPBreaks/Finish per 60 flips. Over the window this prints the median of each field
and then:

  busy      1 - Ri/G. Renderer busy share (hakuX-perf).
  draws     DA+IE+IB+IA per frame (xemu-work, last frame of each 60).
  us/draw   (Tot - Idle - Fin) * 1000 / draws: renderer-thread CPU time per
            draw, excluding waits. Upper bound on recording cost per draw,
            because Tot - Idle - Fin also holds Surf/Tex/Shd/Flip.
  wait      Fin (Sub + Fen). For a pfifo-thread non-deferred finish the wait is
            in Sub (qemu_event_wait), not Fen (blinx372c).
  floor     max(Tot - Idle - Fin, GPU): the renderer's own floor if every
            wait goes and its CPU and GPU work stay the same. cap = 1000/floor
            is a renderer-side ceiling; the guest (Idle) bounds it separately.

Median of each field, not the field of a median line. Every value is a
per-frame EMA or a last-frame count as the build prints it.
"""
import argparse
import re
import statistics
import sys
from datetime import datetime

TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\w/([\w-]+)\s*\(\s*\d+\):\s?(.*)$")
NUM = re.compile(r"([A-Za-z]+):([\d.]+)")
GFPS = re.compile(r"gfps=(\d+) G:([\d.]+).*?Vpf:([\d.]+) Ri:([\d.]+)")
FIN = re.compile(r"Finish:(\d+)\((.*?)\)")
SD = re.compile(r"sd\[(.*?)\]")


def phase(body):
    # "Fin:1.0(Sub:0.9 Fen:0.1)" and "Pipe:0.1(Tx:..." parse as flat keys;
    # Idle's Fr/St and GPU's R/X too. The keys are unique on the line.
    left, _, right = body.partition("|")
    d = {k: float(v) for k, v in NUM.findall(left)}
    r = {k: float(v) for k, v in NUM.findall(right)}
    d["Tot"] = r.get("Tot", float("nan"))
    d["GPU"] = r.get("GPU", float("nan"))
    for k in ("R", "X", "RP", "Pre", "Post", "MxG"):
        if k in r:
            d["G" + k] = r[k]
    return d


def work(body):
    d = {}
    for k, v in re.findall(r"(\w+):(\d+)(?=\s|$)", body):
        d[k] = int(v)
    m = re.search(r"QS:(\d+)/(\d+)", body)
    if m:
        d["QS"], d["QSaux"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"Fin:(.*)$", body)
    if m:
        for k, v in re.findall(r"([A-Za-z]+)(\d+)", m.group(1)):
            d["fin_" + k] = int(v)
    d["draws"] = sum(d.get(k, 0) for k in ("DA", "IE", "IB", "IA"))
    return d


def cpu(body):
    return {("cpu_" + k): float(v) for k, v in NUM.findall(body)}


def stall(body):
    d = {}
    m = re.search(r"RPBreaks:(\d+)", body)
    if m:
        d["RPBreaks"] = int(m.group(1))
    m = FIN.search(body)
    if m:
        d["Finish"] = int(m.group(1))
        for k, v in re.findall(r"([A-Za-z]+)(\d+)", m.group(2)):
            d["fin_" + k] = int(v)
    m = SD.search(body)
    if m:
        for k, v in re.findall(r"([A-Za-z]+)(\d+)", m.group(1)):
            d["sd_" + k] = int(v)
    return d


def read(path):
    t0 = None
    rows = {"gfps": [], "phase": [], "cpu": [], "work": [], "stall": []}
    for line in open(path, errors="replace"):
        m = TS.match(line)
        if not m:
            continue
        tag, body = m.group(2), m.group(3)
        if not tag.startswith(("hakuX", "xemu")):
            continue
        t = datetime.strptime("2026-" + m.group(1), "%Y-%m-%d %H:%M:%S.%f").timestamp()
        if t0 is None:
            t0 = t
        t -= t0
        if tag == "hakuX-perf" and body.startswith("gfps="):
            g = GFPS.search(body)
            if g:
                gf, G, vpf, ri = int(g[1]), float(g[2]), float(g[3]), float(g[4])
                rows["gfps"].append((t, {"gfps": gf, "G": G, "Vpf": vpf, "Ri": ri,
                                         "busy": 1 - ri / G if G else float("nan")}))
        elif tag == "hakuX-phase":
            rows["phase"].append((t, phase(body)))
        elif tag == "hakuX-cpu":
            rows["cpu"].append((t, cpu(body)))
        elif tag == "xemu-work":
            rows["work"].append((t, work(body)))
        elif tag == "hakuX-stall" and body.startswith("RPBreaks"):
            rows["stall"].append((t, stall(body)))
    return rows


def med(rows, key):
    v = [d[key] for _, d in rows if key in d]
    return statistics.median(v) if v else float("nan")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logcat")
    ap.add_argument("--window", required=True, help="A,B seconds since the first hakuX line")
    a = ap.parse_args(argv)
    lo, hi = (float(x) for x in a.window.split(","))
    allrows = read(a.logcat)
    w = {k: [r for r in v if lo <= r[0] <= hi] for k, v in allrows.items()}
    counts = {k: len(v) for k, v in w.items()}
    print("window %.0f-%.0f s: lines %s" % (lo, hi, counts))
    if not w["gfps"]:
        sys.exit("no gfps lines in the window")
    if not w["phase"]:
        print("NO phase lines: not a perflog build, or the tag was filtered. Split unreadable.")
    g = w["gfps"]
    fps = 60.0 * (len(g) - 1) / (g[-1][0] - g[0][0]) if len(g) > 1 else float("nan")
    print("fps (gfps-line cadence) %.2f  G %.1f  Vpf %.2f  Ri %.1f  busy %.0f%%" % (
        fps, med(g, "G"), med(g, "Vpf"), med(g, "Ri"), 100 * med(g, "busy")))
    if w["phase"]:
        keys = ["Surf", "Tex", "Shd", "Draw", "Vtx", "Syn", "Prw", "Pipe", "Tx", "Sh", "Lu",
                "Desc", "Setup", "Cmd", "Fin", "Sub", "Fen", "Flip", "Idle", "Fr", "St",
                "Tot", "GPU", "GR", "GX", "GRP", "GPre", "GPost", "GMxG"]
        print("phase (ms/frame, median): " + " ".join("%s:%.1f" % (k, med(w["phase"], k)) for k in keys))
    if w["cpu"]:
        print("cpu: " + " ".join("%s:%.1f" % (k[4:], med(w["cpu"], k)) for k in sorted(w["cpu"][0][1])))
    if w["work"]:
        wk = w["work"]
        keys = ["draws", "BE", "DA", "IE", "IB", "IA", "Clr", "QS", "QSaux", "PGen", "PBnd", "PNd", "RP",
                "SGen", "SBnd", "SNd", "UBOd", "UBOn", "TexU", "fin_Vbd", "fin_Sc", "fin_Sd", "fin_Bs",
                "fin_Fbd", "fin_Pr", "fin_Fl", "fin_Flu", "fin_St"]
        print("work (last frame of 60, median): " + " ".join("%s:%g" % (k, med(wk, k)) for k in keys))
    if w["stall"]:
        st = w["stall"]
        keys = sorted({k for _, d in st for k in d})
        print("stall (per 60 flips, median): " + " ".join("%s:%g" % (k, med(st, k)) for k in keys))
    if w["phase"] and w["work"]:
        tot, idle, fin, gpu = (med(w["phase"], k) for k in ("Tot", "Idle", "Fin", "GPU"))
        draws = med(w["work"], "draws")
        busy_cpu = tot - idle - fin
        floor = max(busy_cpu, gpu)
        print("renderer CPU (Tot-Idle-Fin) %.1f ms; draws %.0f; us/draw <= %.1f; wait (Fin) %.1f ms; "
              "GPU %.1f ms; floor %.1f ms -> cap %.1f fps if every wait goes" % (
                  busy_cpu, draws, 1000 * busy_cpu / draws if draws else float("nan"),
                  fin, gpu, floor, 1000 / floor if floor else float("nan")))


def selftest():
    import tempfile, os
    lines = [
        "09-26 05:17:35.968 I/hakuX-perf(1): gfps=15 G:62.0(30.0-73.0) D:16.7(16.7-16.7) S:4.9 J:4.4 Df:46 Vd:0.0 Ul:N Vpf:3.70 Ri:8.0 Tq:0",
        "09-26 05:17:36.968 I/hakuX-phase(1): Surf:2.0 Tex:1.0 Shd:0.0 Draw:40.0 [Vtx:5.0 Syn:1.0 Prw:0.0 Pipe:10.0(Tx:3.0 Sh:2.0 Lu:1.0) Desc:4.0 Setup:3.0 Cmd:9.0] Fin:6.0(Sub:5.0 Fen:1.0) Flip:0.0 Idle:8.0(Fr:6.0 St:2.0) | Tot:62.0 GPU:20.0(R:18.0 X:2.0 RP:4 Pre:0.0 Post:0.1 MxG:0.0 g:0/0/0) ms",
        "09-26 05:17:36.968 I/xemu-work(1): BE:2000 DA:1500 IE:500 IB:0 IA:0 Clr:3 QS:4/0 PGen:0 PBnd:300 PNd:1700 RP:4 SGen:0 SBnd:1 SNd:0 UBOd:1900 UBOn:100 TexU:2 S2T:0/0 GBU:1/1/0/0/0 Fin:Vbd0 Sc0 Sd0 Bs0 Fbd0 Pr0 Fl1 Flu0 St0",
        "09-26 05:17:36.968 I/hakuX-cpu(1): CPU: K:3 W:0.4K M:115(Fh:139 Ni:1) Push:0.8ms [Pull:0.8(Lk:0.0 Mth:0.7 Fst:0.0)] SpH:138% TbH:98.9%",
        "09-26 05:17:36.968 I/hakuX-stall(1): RPBreaks:195 Finish:73(vtx0 sc0 sd9 buf0 fb0 pres2 flip58 flu1 stl3 stlDef58 stlBat0) InlClr:0/68 PreDL:28 sd[ev0 noCb0 dl1 cDef8 cDefC0 pDl0 dDl0] dlSrc[defFb0 ppdFb0 dirtyIf1] dif[ovl1 ovlSh0 exp11 expSh0 blt1 flu0 dds0 oth0]",
        "09-26 05:17:37.968 I/hakuX-perf(1): gfps=15 G:62.0(30.0-73.0) D:16.7(16.7-16.7) S:4.9 J:4.4 Df:46 Vd:0.0 Ul:N Vpf:3.70 Ri:8.0 Tq:0",
    ]
    fd, p = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    r = read(p)
    os.unlink(p)
    ph = r["phase"][0][1]
    assert ph["Tot"] == 62.0 and ph["GPU"] == 20.0 and ph["Sub"] == 5.0 and ph["Fen"] == 1.0, ph
    assert ph["Draw"] == 40.0 and ph["Cmd"] == 9.0 and ph["GR"] == 18.0 and ph["Idle"] == 8.0, ph
    wk = r["work"][0][1]
    assert wk["draws"] == 2000 and wk["PBnd"] == 300 and wk["QS"] == 4 and wk["fin_Sd"] == 0, wk
    st = r["stall"][0][1]
    assert st["fin_sd"] == 9 and st["sd_cDef"] == 8 and st["RPBreaks"] == 195 and st["fin_stlDef"] == 58, st
    assert abs(r["gfps"][0][1]["busy"] - (1 - 8 / 62)) < 1e-9
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        main()
