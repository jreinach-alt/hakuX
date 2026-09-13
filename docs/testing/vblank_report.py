#!/usr/bin/env python3
"""Summarise the guest-visible VBLANK timing lines out of a soak logcat.

    vblank_report.py <logcat.txt> [...]

Reads the `vbl` and `vblmode` lines that hw/xbox/nv2a/nv2a.c emits under the
hakuX-perf tag every two seconds and answers the four questions the corpus
cannot: what period we deliver against what we intended, how that
distribution is shaped, how many VBLANK assertions the guest never saw
because PCRTC coalesced them, and whether anything reads PCRTC_RASTER.

Windows are split on the deferral count, because the adaptive deferral in
nv2a_vblank_timer_cb is the thing under suspicion and a pooled mean over both
populations would hide it. That is the same trap as reporting a mean for
jitter: two regimes averaged look like one mildly wrong regime.
"""
import re
import sys

VBL = re.compile(
    r"vbl n=(?P<n>\d+) win=(?P<win>\d+)ms want=(?P<want>\d+) got=(?P<got>\d+) "
    r"drift=(?P<drift>[-+]?\d+) rate=(?P<rate>[\d.]+)Hz "
    r"p1=(?P<p1>\d+) p50=(?P<p50>\d+) p90=(?P<p90>\d+) p99=(?P<p99>\d+) "
    r"min=(?P<min>\d+) max=(?P<max>\d+) "
    r"src\(tmr=(?P<tmr>\d+) smp=(?P<smp>\d+) gfx=(?P<gfx>\d+)\) "
    r"coal=(?P<coal>\d+) def=(?P<def>\d+) rast=(?P<rast>\d+)/(?P<rastmax>\d+)")

MODE = re.compile(
    r"vblmode want=(?P<want>\d+) derived=(?P<derived>\d+) "
    r"\(vtotal=(?P<vtotal>\d+) htotal=(?P<htotal>\d+) pixclk=(?P<pixclk>\d+) "
    r"vpll=(?P<vpll>[0-9a-f]+) m=(?P<m>\d+) n=(?P<n>\d+) p=(?P<p>\d+)\) "
    r"cr00=(?P<cr00>[0-9a-f]+) cr06=(?P<cr06>[0-9a-f]+) "
    r"cr07=(?P<cr07>[0-9a-f]+) cr25=(?P<cr25>[0-9a-f]+) "
    r"cr2d=(?P<cr2d>[0-9a-f]+) msr=(?P<msr>[0-9a-f]+) vd=(?P<vd>\d+) "
    r"il=(?P<il>[0-9a-f]+) res=(?P<res>\d+x\d+)")

NTSC_TRUE_NS = 16683333    # 60000/1001 fields per second
PAL_TRUE_NS = 20000000


def pct(rows, key):
    """Sample median of a per-window field, plus its extremes."""
    vals = sorted(int(r[key]) for r in rows)
    if not vals:
        return (0, 0, 0)
    return (vals[0], vals[len(vals) // 2], vals[-1])


def describe(label, rows):
    if not rows:
        print("  %-22s (no windows)" % label)
        return
    want = int(rows[0]["want"])
    got = [int(r["got"]) for r in rows]
    mean = sum(got) // len(got)
    lo, med, hi = pct(rows, "p99")
    _, p50med, _ = pct(rows, "p50")
    mn = min(int(r["min"]) for r in rows)
    mx = max(int(r["max"]) for r in rows)
    total = sum(int(r["n"]) for r in rows)
    coal = sum(int(r["coal"]) for r in rows)
    defs = sum(int(r["def"]) for r in rows)
    span = sum(int(r["win"]) for r in rows)
    print("  %-22s %3d windows, %5d assertions over %6.1f s" %
          (label, len(rows), total, span / 1000.0))
    print("      mean interval      %9d ns  (want %d, %+d ns, %+.2f%%)" %
          (mean, want, mean - want, (mean - want) * 100.0 / want))
    print("      delivered rate     %9.3f Hz   against %.3f Hz intended" %
          (total * 1000.0 / span if span else 0, 1e9 / want))
    print("      p50 of windows     %9d ns" % p50med)
    print("      p99 across windows %9d ns  (worst window %d)" % (med, hi))
    print("      min / max          %9d / %d ns" % (mn, mx))
    print("      coalesced          %9d  (%.2f%% of assertions the guest "
          "never saw)" % (coal, coal * 100.0 / total if total else 0))
    print("      deferred           %9d  (%.1f%% of assertions)" %
          (defs, defs * 100.0 / total if total else 0))
    # Clock error against the real standard, not against our own constant.
    ref = NTSC_TRUE_NS if want < 18000000 else PAL_TRUE_NS
    drift_s_per_min = (mean - ref) / float(ref) * 60.0
    print("      against %d ns standard: %+.3f s drift per minute of play"
          % (ref, drift_s_per_min))


def main():
    vbl, mode = [], []
    for path in sys.argv[1:]:
        with open(path, errors="replace") as fh:
            for line in fh:
                m = VBL.search(line)
                if m:
                    vbl.append(m.groupdict())
                    continue
                m = MODE.search(line)
                if m:
                    mode.append(m.groupdict())
    if not vbl:
        sys.exit("no vbl lines found in %s" % ", ".join(sys.argv[1:]))

    print("mode, as programmed by the guest")
    seen = set()
    for m in mode:
        key = tuple(sorted(m.items()))
        if key in seen:
            continue
        seen.add(key)
        derived = int(m["derived"])
        want = int(m["want"])
        print("  res=%s vd=%s il=%s vtotal=%s htotal=%s pixclk=%s "
              "vpll=%s(m=%s n=%s p=%s)" %
              (m["res"], m["vd"], m["il"], m["vtotal"], m["htotal"],
               m["pixclk"], m["vpll"], m["m"], m["n"], m["p"]))
        print("      we return %d ns; the CRTC/VPLL derivation says %d ns "
              "(%s)" % (want, derived,
                        "%+.4f%%" % ((derived - want) * 100.0 / want)
                        if want else "n/a"))
        print("      true NTSC is %d ns; our constant is %+d ns (%+.1f ppm)"
              % (NTSC_TRUE_NS, want - NTSC_TRUE_NS,
                 (want - NTSC_TRUE_NS) * 1e6 / NTSC_TRUE_NS))
    print()

    src = {k: sum(int(r[k]) for r in vbl) for k in ("tmr", "smp", "gfx")}
    print("assertion sources: timer=%d simple=%d gfx_update=%d" %
          (src["tmr"], src["smp"], src["gfx"]))
    rast = sum(int(r["rast"]) for r in vbl)
    rastmax = max(int(r["rastmax"]) for r in vbl)
    print("PCRTC_RASTER reads: %d total, %d most in one period" %
          (rast, rastmax))
    print()

    print("interval distribution")
    describe("all windows", vbl)
    print()
    describe("def == 0", [r for r in vbl if int(r["def"]) == 0])
    print()
    describe("def 1..20", [r for r in vbl if 0 < int(r["def"]) <= 20])
    print()
    describe("def > 20", [r for r in vbl if int(r["def"]) > 20])


if __name__ == "__main__":
    main()
