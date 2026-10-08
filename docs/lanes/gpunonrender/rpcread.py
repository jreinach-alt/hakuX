#!/usr/bin/env python3
"""Read the render-pass census (xemu-xfr XFR rpc lines) of one perflog soak
for lane.gpunonrender, over a window of the logcat.

    rpcread.py <request-id> [--from HH:MM:SS[.f]] [--until HH:MM:SS[.f]]

Each xemu-xfr line covers 60 command-buffer readbacks and gives per-CB means,
so a line's value x 60 is its window total. Totals are divided by the
[sdcall] frames of the same span for per-frame values. Prints the census
groups (all passes, then the passes read as GMEM), the instrument legs K1-K4
and the decision legs S and B of docs/lanes/gpunonrender/NOTES.md.
"""
import os, re, sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
args = sys.argv[1:]
rid = args[0]
t_from = args[args.index("--from") + 1] if "--from" in args else None
t_until = args[args.index("--until") + 1] if "--until" in args else None
MS_PER_MIB = 0.043      # C16 control: one 1 MiB buffer copy, read + write
GROUPS = ["all", "lclr", "lunif", "zdead", "clronly", "any"]


def tsec(hms):
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


lo = tsec(t_from) if t_from else -1
hi = tsec(t_until) if t_until else 1e9

tot = {0: {}, 1: {}}    # mode -> key -> window total
rp_n = 0.0
wins = {0: 0, 1: 0}
frames = 0
inl_hit = inl_miss = 0
late_dead = late_live = 0
seen = set()
for line in open(os.path.join(D, rid, "logcat.txt"), errors="replace"):
    m = re.match(r"\d\d-\d\d (\d\d:\d\d:\d\d\.\d+)", line)
    if not m:
        continue
    t = tsec(m.group(1))
    if t < lo or t > hi:
        continue
    body = line[line.find(": ") + 2:].strip() if ": " in line else line
    key = (m.group(1), body)
    if key in seen:
        continue
    seen.add(key)
    if "XFR rpc" in line:
        mode = 1 if "XFR rpc g " in line else 0
        wins[mode] += 1
        d = tot[mode]
        for g in GROUPS:
            mm = re.search(r" %s ([\d.]+) ([\d.]+) ([\d.]+)" % g, line)
            if mm:
                for k, v in zip(("n", "ms", "mb"), mm.groups()):
                    d[(g, k)] = d.get((g, k), 0) + float(v) * 60
        for k in ("ldMB", "stMB", "in", "draws", "paired", "zlive", "zpend"):
            mm = re.search(r" %s ([\d.]+)" % k, line)
            if mm:
                d[k] = d.get(k, 0) + float(mm.group(1)) * 60
        mm = re.search(r" late (\d+)/(\d+)", line)
        if mm:
            late_dead += int(mm.group(1))
            late_live += int(mm.group(2))
    elif "XFR rp in" in line:
        mm = re.search(r" n([\d.]+) inrp", line)
        if mm:
            rp_n += float(mm.group(1)) * 60
    elif "[sdcall] frames=" in line:
        frames += int(re.search(r"frames=(\d+)", line).group(1))
    elif "hakuX-stall" in line and "RPBreaks:" in line:
        mm = re.search(r"InlClr:(\d+)/(\d+)", line)
        if mm:
            inl_hit += int(mm.group(1))
            inl_miss += int(mm.group(2))

cbs = wins[0] * 60
if not cbs or not frames:
    sys.exit("no XFR rpc lines or no [sdcall] frames in the window")
print("%s  windows %d (%d CBs), [sdcall] frames %d, CBs/frame %.2f" %
      (rid, wins[0], cbs, frames, cbs / frames))
a, g = tot[0], tot[1]
print("%-8s %21s   %21s" % ("", "every pass", "passes read as GMEM"))
print("%-8s %6s %8s %6s   %6s %8s %6s   (per frame)" %
      ("group", "n", "ms", "MiB", "n", "ms", "MiB"))
for grp in GROUPS:
    print("%-8s %6.2f %8.2f %6.2f   %6.2f %8.2f %6.2f" % (
        grp, a.get((grp, "n"), 0) / frames, a.get((grp, "ms"), 0) / frames,
        a.get((grp, "mb"), 0) / frames, g.get((grp, "n"), 0) / frames,
        g.get((grp, "ms"), 0) / frames, g.get((grp, "mb"), 0) / frames))
for k in ("ldMB", "stMB", "in", "draws"):
    print("%-8s %22.2f   %22.2f" % (k, a.get(k, 0) / frames, g.get(k, 0) / frames))
print("zlive %.2f zpend %.2f per frame; late dead/live %d/%d" % (
    a.get("zlive", 0) / frames, a.get("zpend", 0) / frames, late_dead,
    late_live))
gms = g.get(("all", "ms"), 0)
gin = g.get("in", 0)
gn = g.get(("all", "n"), 0)
if gn:
    print("GMEM passes: out - in %.2f ms per frame, %.3f ms per pass, %.1f draws"
          " per pass" % ((gms - gin) / frames, (gms - gin) / gn,
                         g.get("draws", 0) / gn))

print("\ninstrument legs")
k1 = abs(a.get(("all", "n"), 0) - rp_n) / cbs
print("  K1 rpc all n vs XFR rp n, per CB: |%.3f| <= 0.05  %s" %
      (k1, "PASS" if k1 <= 0.05 else "FAIL"))
co = a.get(("clronly", "n"), 0) / frames
miss = inl_miss / frames
print("  K2 clronly %.2f vs inline-clear misses %.2f per frame (hits %.2f):"
      " |diff| <= 0.3  %s" % (co, miss, inl_hit / frames,
                               "PASS" if abs(co - miss) <= 0.3 else "FAIL"))
gco = g.get(("clronly", "n"), 0) / frames
print("  K3 g clronly %.2f <= 0.1 x clronly %.2f  %s" %
      (gco, co, "PASS" if gco <= 0.1 * co + 1e-9 else "FAIL"))
k4 = abs(a.get("paired", 0) - a.get(("all", "n"), 0)) / cbs
print("  K4 paired vs all n, per CB: |%.3f| <= 0.1  %s" %
      (k4, "PASS" if k4 <= 0.1 else "FAIL"))

print("\ndecision legs")
share = g.get(("any", "ms"), 0) / max(a.get(("all", "ms"), 0), 1e-9)
print("  S  g any ms / all ms = %.1f%% >= 30%%  %s" %
      (100 * share, "HOLDS" if share >= 0.30 else "fails"))
bms = g.get(("any", "mb"), 0) / frames * MS_PER_MIB
print("  B  g any %.2f MiB/frame x %.3f = %.2f ms/frame >= 1.0  %s" % (
    g.get(("any", "mb"), 0) / frames, MS_PER_MIB, bms,
    "HOLDS" if bms >= 1.0 else "fails"))
