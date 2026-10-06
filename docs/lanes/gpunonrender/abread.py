#!/usr/bin/env python3
"""Read one perflog soak for lane.gpunonrender: [sdcall] waits by caller,
hakuX-stall finishes, hakuX-perf gfps/G, xemu-gpu Tot/Rnd/Xfr and the xemu-xfr
categories, over a window of the logcat.

    abread.py <request-id> [--from HH:MM:SS[.f]] [--until HH:MM:SS[.f]]

Per-frame values are window sums divided by the window's [sdcall] frames.
Lines are de-duplicated on (timestamp, body): the perflog build logs some
lines under two tags.
"""
import os, re, statistics as st, sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
args = sys.argv[1:]
rid = args[0]
t_from = t_until = None
if "--from" in args:
    t_from = args[args.index("--from") + 1]
if "--until" in args:
    t_until = args[args.index("--until") + 1]


def tsec(hms):
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


lo = tsec(t_from) if t_from else -1
hi = tsec(t_until) if t_until else 1e9

sd_frames = 0
sd = {}          # caller -> [fin, fence, pre, dl, ms]
spl = [0] * 5    # def, up, dl, kB, cmpl
why = {}
su_upl = 0
fin_tot = 0
fin_parts = {}
gfps = []
G = []
gpu = {"Tot": [], "Rnd": [], "Xfr": []}
xfr = {}         # cat -> [medians], n
xfr_n = {}
sites = {}
rp = {}          # XFR rp line: in/out/nr_out/res_out window means, n
rp_inrp = set()
seen = set()
first = last = None

for line in open(os.path.join(D, rid, "logcat.txt"), errors="replace"):
    m = re.match(r"\d\d-\d\d (\d\d:\d\d:\d\d\.\d+) \w/([\w-]+)\s*\(\s*\d+\): (.*)", line)
    if not m:
        continue
    ts, tag, body = m.groups()
    t = tsec(ts)
    if t < lo or t > hi:
        continue
    key = (ts, body)
    if key in seen:
        continue
    seen.add(key)
    if body.startswith("[surf413]") or body.startswith("[sdcall]") and tag != "hakuX":
        continue
    if body.startswith("[sdcall]"):
        first = first or ts
        last = ts
        fm = re.search(r"frames=(\d+)", body)
        sd_frames += int(fm.group(1))
        for c, a, b, p, d, ms in re.findall(
                r"(\w+)=fin(\d+)/fence(\d+)/pre(\d+)/dl(\d+)/([\d.]+)ms", body):
            v = sd.setdefault(c, [0, 0, 0, 0, 0.0])
            for i, x in enumerate((a, b, p, d)):
                v[i] += int(x)
            v[4] += float(ms)
        s = re.search(r"spl=def(\d+)/up(\d+)/dl(\d+)/(\d+)kB/cmpl(\d+)", body)
        if s:
            for i, x in enumerate(s.groups()):
                spl[i] += int(x)
        u = re.search(r"su_upl=(\d+)", body)
        if u:
            su_upl += int(u.group(1))
        w = re.search(r"why=(\S+)", body)
        if w:
            for k, x in re.findall(r"([a-z]+)(\d+)", w.group(1)):
                why[k] = why.get(k, 0) + int(x)
    elif tag == "hakuX-stall" and body.startswith("RPBreaks"):
        f = re.search(r"Finish:(\d+)\(([^)]*)\)", body)
        if f:
            fin_tot += int(f.group(1))
            for k, x in re.findall(r"([A-Za-z]+)(\d+)", f.group(2)):
                fin_parts[k] = fin_parts.get(k, 0) + int(x)
    elif tag == "hakuX-perf" and body.startswith("gfps="):
        gfps.append(int(re.match(r"gfps=(\d+)", body).group(1)))
        g = re.search(r"G:([\d.]+)", body)
        if g:
            G.append(float(g.group(1)))
    elif body.startswith("xemu-xfr XFR rp"):
        for k, med, mean, p90 in re.findall(
                r"(in|out|nr_out|res_out) ([\d.-]+) ([\d.-]+) ([\d.-]+)", body):
            rp.setdefault(k, []).append(float(mean))
        n = re.search(r" n([\d.]+) inrp(\d)", body)
        if n:
            rp.setdefault("n", []).append(float(n.group(1)))
            rp_inrp.add(n.group(2))
    elif body.startswith("xemu-xfr XFR sites"):
        for name, ms, n in re.findall(r"(\w+@\d+) ([\d.]+) n([\d.]+)", body):
            sites.setdefault(name, []).append((float(ms), float(n)))
    elif body.startswith("xemu-xfr XFR nr"):
        for cat, med, mean, p90 in re.findall(
                r"(\w+) ([\d.]+) ([\d.]+) ([\d.]+)", body[len("xemu-xfr XFR "):]):
            xfr.setdefault(cat, []).append(float(mean))
        for cat, n in re.findall(r"(\w+) [\d.]+ [\d.]+ [\d.]+ n([\d.]+)", body):
            xfr_n.setdefault(cat, []).append(float(n))
    elif tag == "xemu-gpu" and "Tot" in body:
        for k in gpu:
            g = re.search(k + r"[:= ]+([\d.]+)", body)
            if g:
                gpu[k].append(float(g.group(1)))

F = max(sd_frames, 1)
print("%s window %s..%s, [sdcall] frames %d" % (rid, first, last, sd_frames))
print("gfps mean %.1f median %.1f (n %d); G ms mean %.1f" % (
    st.mean(gfps) if gfps else 0, st.median(gfps) if gfps else 0, len(gfps),
    st.mean(G) if G else 0))
print("[sdcall] per frame: caller fin fence pre dl wait-ms")
tot_ms = 0
for c, v in sorted(sd.items(), key=lambda kv: -kv[1][4]):
    tot_ms += v[4]
    print("   %-8s %6.2f %6.2f %6.2f %6.2f %7.2f" % (
        c, v[0] / F, v[1] / F, v[2] / F, v[3] / F, v[4] / F))
print("   all-callers wait %.2f ms/frame" % (tot_ms / F))
print("su_upl %.2f/frame why %s" % (su_upl / F, why))
print("spl def %.2f up %.2f dl %.2f kB %.0f cmpl %.2f per frame" % tuple(
    x / F for x in spl))
print("hakuX-stall Finish per frame %.2f %s" % (
    fin_tot / F, {k: round(v / F, 2) for k, v in fin_parts.items()}))
for k, v in gpu.items():
    if v:
        print("xemu-gpu %s mean %.2f median %.2f" % (k, st.mean(v), st.median(v)))
# xemu-xfr is per command buffer (one readback each, 60 per line); xemu-gpu is
# per guest frame. Command buffers per frame scale the one to the other.
cbpf = len(xfr.get("nr", [])) * 60 / F
print("xemu-xfr: %.2f command buffers per frame" % cbpf)
print("   %-9s %8s %8s %8s %6s" % ("cat", "ms/CB", "ms/frame", "ops/frame", "%nr"))
nr_f = st.mean(xfr["nr"]) * cbpf if xfr.get("nr") else 0
for cat, v in xfr.items():
    n = xfr_n.get(cat)
    pf = st.mean(v) * cbpf
    print("   %-9s %8.2f %8.2f %8s %5.0f%%" % (
        cat, st.mean(v), pf, "%.2f" % (st.mean(n) * cbpf) if n else "-",
        100 * pf / nr_f if nr_f else 0))
if rp:
    print("xemu-xfr rp (render span by in-pass and outer stamps; inrp %s):" %
          ",".join(sorted(rp_inrp)))
    for k in ("in", "out", "nr_out", "res_out", "n"):
        if k in rp:
            print("   %-8s %6.2f per CB  %6.2f per frame" % (
                k, st.mean(rp[k]), st.mean(rp[k]) * cbpf))
print("xemu-xfr sites (ms/frame, ops/frame; a site absent from a line counts 0):")
nl = max(len(xfr.get("nr", [])), 1)
for s, v in sorted(sites.items(), key=lambda kv: -sum(x[0] for x in kv[1])):
    print("   %-16s %6.2f n %.2f (in %d of %d lines)" % (
        s, sum(x[0] for x in v) / nl * cbpf, sum(x[1] for x in v) / nl * cbpf,
        len(v), nl))
