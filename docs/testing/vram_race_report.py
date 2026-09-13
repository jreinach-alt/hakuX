#!/usr/bin/env python3
"""Read #54's VRAM read-race probe off a soak's logcat, and judge its legs.

    vram_race_report.py RESULTDIR [RESULTDIR ...]
    vram_race_report.py --arm-a DIR,DIR --arm-b DIR,DIR

The probe (hw/xbox/nv2a/pgraph/vk/draw.c) appends five fields to the
hakuX-perf pacing line and this reads them back:

    Vr:raced/copies         vertex-range copies out of guest VRAM whose range
                            was dirty again when the copy returned
    Tr:raced/uploads/windows begin_pre_draw windows; `uploads` consumed a
                            dirty bit for a bound texture inside the window,
                            `raced` means it was set again by the time the
                            window closed -- the guest writing the texture
                            while the upload read it

    Xd:n                    the impossible row; must be exactly 0

Why the numbers are cumulative and this takes the LAST line rather than a
mean: a rate wants one denominator, and a soak's early lines are all boot.

Two things this deliberately refuses to do.

**The cost statistic is the gfps LINE COUNT, not a percentile.** The pacing
line fires once per 60 guest frames, so its count over a fixed-duration soak
is guest frames rendered in fixed wall time -- one monotone scalar, and
exactly the throughput the cost question asks about. Percentiles are printed
and are not part of any verdict, for two separate reasons. A median gfps
measures how busy the device is: the series is bimodal (ceiling 29-31, floor
5-20) and the median tracks occupancy, which moved 80% -> 16-32% across one
evening. And a p90 is no better on a real title, because the series is not
stationary -- DOA3 over one 150 s soak runs through logos, attract, an FMV
and a collapse (21, 39, .., 59, 59, .., 8, .., 3), so the 59s that set p90
are the logo and a percentile picks whichever phase sits at that rank.

**It refuses a cost comparison whose arms ran on different handhelds or
different titles.** #64's cost leg lost its control because four soaks ran
across two handhelds and nothing recorded which; device_label and title are
in every result.json, so the check is free.
"""
import json
import os
import re
import sys

PERF = re.compile(
    r"gfps=(?P<gfps>-?\d+)\s+G:(?P<g>[\d.]+)\("
    r"(?P<gmin>[\d.]+)-(?P<gmax>[\d.]+)\)")
TQ = re.compile(r"\bTq:(?P<tq>[\d.]+)")
PROBE = re.compile(
    r"\bVr:(?P<vr>\d+)/(?P<vc>\d+)\s+"
    r"Tr:(?P<tr>\d+)/(?P<tu>\d+)/(?P<tb>\d+)\s+"
    # Tl existed only in the first, mis-placed bracket (ref ae0283fe2d) and is
    # accepted so those runs still read as the negative control for it.
    r"(?:Tl:(?P<tl>\d+)\s+)?Xd:(?P<xd>\d+)")
MB = re.compile(r"mb_emitted=(?P<mb>\d+)")


def pct(vals, p):
    """Linear-interpolated percentile. Nearest-rank would quantise a 20-line
    soak into 5% steps, which is coarser than the effect being looked for."""
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def read_result(d):
    meta = {}
    rj = os.path.join(d, "result.json")
    if os.path.exists(rj):
        meta = json.load(open(rj))
    logs = [os.path.join(d, f) for f in sorted(os.listdir(d))
            if f.startswith("logcat") and f.endswith(".txt")]
    gfps, gms, tqs, probe, mb = [], [], [], None, None
    lines = 0
    for lg in logs:
        for line in open(lg, errors="replace"):
            m = MB.search(line)
            if m and "hakuX-build" in line:
                mb = int(m.group("mb"))
            m = PERF.search(line)
            if not m:
                continue
            lines += 1
            gfps.append(int(m.group("gfps")))
            gms.append(float(m.group("g")))
            t = TQ.search(line)
            if t:
                tqs.append(float(t.group("tq")))
            p = PROBE.search(line)
            if p:
                # Cumulative: the last line seen wins.
                probe = {k: (int(v) if v is not None else None)
                         for k, v in p.groupdict().items()}
    return {
        "dir": os.path.basename(d), "meta": meta, "perf_lines": lines,
        "gfps": gfps, "gms": gms, "tq": tqs, "probe": probe, "mb": mb,
        "logs": len(logs),
    }


def describe(r):
    m = r["meta"]
    print(f"=== {r['dir']}")
    print(f"    title={m.get('title','?')!r} device={m.get('device_label','?')} "
          f"ref={m.get('ref','?')} apk={m.get('apk_sha','?')} "
          f"seconds={m.get('seconds','?')}")
    print(f"    hakuX-perf lines: {r['perf_lines']}   mb_emitted={r['mb']}")
    if not r["gfps"]:
        print("    NO PERF LINES -- nothing measurable in this run")
        return
    print(f"    gfps  p90={pct(r['gfps'],90):.1f} max={max(r['gfps'])} "
          f"[median={pct(r['gfps'],50):.1f} = occupancy, not a cost read]")
    print(f"    G ms  p10={pct(r['gms'],10):.1f} min={min(r['gms']):.1f} "
          f"[median={pct(r['gms'],50):.1f}]")
    if r["tq"]:
        print(f"    Tq    median={pct(r['tq'],50):.0f}  (control: the probe "
              f"adds no test-and-clear, so this must not move)")
    p = r["probe"]
    if p is None:
        print("    PROBE FIELDS ABSENT -- this is the no-probe arm, or the "
              "pacing line was truncated")
        return
    print(f"    probe Vr={p['vr']}/{p['vc']}"
          + (f" = {p['vr']/p['vc']:.3e}" if p["vc"] else " (denominator 0)"))
    print(f"          Tr={p['tr']}/{p['tu']}/{p['tb']}"
          + (f"  raced/uploads = {p['tr']/p['tu']:.3e}" if p["tu"]
             else "  (uploads 0)"))
    print(f"          Xd={p['xd']}"
          + ("  <-- IMPOSSIBLE ROW NON-ZERO; every other leg is void"
             if p["xd"] else "  (impossible row reads zero, as required)"))


def legs(bs):
    print("\n--- legs, arm B ---")
    probes = [r["probe"] for r in bs if r["probe"]]
    ok = True

    xd = sum(p["xd"] for p in probes)
    print(f"L1 impossible row Xd total = {xd} "
          f"-> {'PASS' if xd == 0 else 'FAIL -- instrument indicted'}")
    ok &= xd == 0

    zb = sum(1 for p in probes if p["tb"] == 0)
    zv = sum(1 for p in probes if p["vc"] == 0)
    # tex_uploads is the denominator leg 3 divides by, and a thin one is the
    # tell for the window being in the wrong place rather than for a quiet
    # device: the mis-placed bracket at ref ae0283fe2d gave 950 of 487,013
    # windows and reported a rate of zero over it, which reads exactly like
    # leg 3's decisive "closes on evidence" outcome.
    thin = sum(1 for p in probes if p["tu"] < 5000)
    print(f"L2 path live: runs with tex_windows==0 = {zb}, "
          f"runs with vtx_copies==0 = {zv}, "
          f"runs with tex_uploads<5000 = {thin} "
          f"-> {'PASS' if zb == 0 and zv == 0 and thin == 0 else 'FAIL -- not '
              'measured, which is not the same as zero races'}")
    ok &= zb == 0 and zv == 0 and thin == 0
    if thin:
        print("   L3/L4/L5 below are NOT MEASURED while L2 fails.")

    tr = sum(p["tr"] for p in probes)
    tu = sum(p["tu"] for p in probes)
    if tu:
        rate = tr / tu
        verdict = ("#54 GAINS A TARGET" if rate >= 1e-4
                   else "#54 CLOSES on evidence")
        print(f"L3 rate Tr/tex_uploads = {tr}/{tu} = {rate:.3e} -> {verdict}")
        if tr == 0:
            # A zero is not a rate until it carries what it rules out. 3/N is
            # the one-sided 95% Poisson bound for zero events in N trials, and
            # it is the difference between "never happens" and "not seen in
            # this many chances" -- which is the whole of #54's dispute.
            print(f"   zero over {tu} windows bounds the rate at <= "
                  f"{3.0/tu:.2e} (one-sided 95%), not at 0")
    else:
        print("L3 rate: no uploads observed -- not measured")

    vr = sum(p["vr"] for p in probes)
    vc = sum(p["vc"] for p in probes)
    if vc:
        if vr == 0:
            print(f"   vertex site: zero over {vc} copies bounds that rate at "
                  f"<= {3.0/vc:.2e} (one-sided 95%)")
    if vc and tu:
        vrate, trate = vr / vc, tr / tu
        print(f"L4 vertex {vrate:.3e} < texture {trate:.3e} -> "
              f"{'PASS' if vrate < trate else 'INVERTED -- the target list changes'}")

    pos = sum(1 for p in probes if p["tr"] > 0)
    print(f"L5 #44 skew: runs with Tr>0 = {pos} of {len(probes)} -> "
          f"{'PASS -- Tr is a FLOOR on the skew rate' if pos >= 1 else 'FAIL'}")
    return ok


def cost(a_runs, b_runs):
    print("\n--- leg 6, cost ---")
    for name, runs in (("A (no probe)", a_runs), ("B (probe)", b_runs)):
        if not runs:
            print(f"{name}: no runs")
            return
    devs = {r["meta"].get("device_label") for r in a_runs + b_runs}
    titles = {r["meta"].get("title") for r in a_runs + b_runs}
    if len(devs) != 1 or len(titles) != 1:
        print(f"REFUSED: arms span devices {devs} / titles {titles}. "
              "A cost read across two handhelds is what #64 lost.")
        return
    print(f"device={devs.pop()} title={titles.pop()!r}")
    stats = (("guest frames (gfps lines x 60)", None, None),
             ("p90 gfps", "gfps", 90), ("p10 G ms", "gms", 10))
    for stat, key, p in stats:
        if key is None:
            av = [r["perf_lines"] * 60 for r in a_runs if r["perf_lines"]]
            bv = [r["perf_lines"] * 60 for r in b_runs if r["perf_lines"]]
        else:
            av = [pct(r[key], p) for r in a_runs if r[key]]
            bv = [pct(r[key], p) for r in b_runs if r[key]]
        if not av or not bv:
            print(f"{stat}: missing an arm")
            continue
        sa = max(av) - min(av) if len(av) > 1 else float("nan")
        sb = max(bv) - min(bv) if len(bv) > 1 else float("nan")
        floor = max(sa, sb)
        ma, mb_ = sum(av) / len(av), sum(bv) / len(bv)
        d = mb_ - ma
        det = "below the noise floor" if abs(d) <= floor else "ABOVE the floor"
        print(f"{stat}: A={[round(x,2) for x in av]} (spread {sa:.2f})  "
              f"B={[round(x,2) for x in bv]} (spread {sb:.2f})")
        tag = "" if key is None else "   [advisory: see module docstring]"
        print(f"          delta {d:+.2f} ({100*d/ma:+.1f}%), floor {floor:.2f} "
              f"-> {det}{tag}")


def main():
    args = sys.argv[1:]
    a_dirs, b_dirs, plain = [], [], []
    i = 0
    while i < len(args):
        if args[i] == "--arm-a":
            a_dirs = args[i + 1].split(","); i += 2
        elif args[i] == "--arm-b":
            b_dirs = args[i + 1].split(","); i += 2
        else:
            plain.append(args[i]); i += 1
    if not (a_dirs or b_dirs):
        b_dirs = plain
    a = [read_result(d) for d in a_dirs]
    b = [read_result(d) for d in b_dirs]
    for r in a + b:
        describe(r)
    if b:
        legs(b)
    if a and b:
        cost(a, b)


if __name__ == "__main__":
    main()
