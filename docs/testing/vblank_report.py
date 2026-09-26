#!/usr/bin/env python3
"""Summarise the guest-visible VBLANK timing lines out of a soak logcat.

    vblank_report.py <logcat.txt> [...]

Reads the `vbl`, `vblmode`, `vblfp` and `vblpll` lines that hw/xbox/nv2a/nv2a.c emits
under the
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

# The flat-panel timing generator's own raster, which counts in pixels rather
# than in the VGA CRTC's 8-dot characters. It is the second candidate for
# deriving the period after the CRTC one failed by -26.3%, and it is the only
# one left inside the NV2A: if fp_vtotal/fp_htotal read 0, the guest never
# programs them and the video standard has to come from outside the chip.
FP = re.compile(
    r"vblfp want=(?P<want>\d+) derived_fp=(?P<derived_fp>\d+) "
    r"\(fp_vtotal=(?P<fp_vtotal>\d+) fp_htotal=(?P<fp_htotal>\d+) "
    r"lines=(?P<lines>\d+) px=(?P<px>\d+)\) "
    r"vde=(?P<vde>\d+) hde=(?P<hde>\d+) vcrtc=(?P<vcrtc>\d+) "
    r"hcrtc=(?P<hcrtc>\d+) vsync=(?P<vsync>\d+) vvalid=(?P<vvalid>\d+) "
    r"hvalid=(?P<hvalid>\d+) genctl=(?P<genctl>[0-9a-f]+) "
    r"sr01=(?P<sr01>[0-9a-f]+)")

# The PLL decode calibrated against two clocks with known right answers. The
# NV2A core runs at 233 MHz and its memory at 200 MHz, and NVPLL and MPLL use
# the same crystal * N / M / 2^P that VPLL does. If those two land, the pixel
# clock is what the guest asked for; if they are off by a constant factor, so
# is the pixel clock, and every raster judged against it is off by that factor.
PLL = re.compile(
    r"vblpll xtal=(?P<xtal>\d+) nvpll=(?P<nvpll>[0-9a-f]+)"
    r"\(m=(?P<nm>\d+) n=(?P<nn>\d+) p=(?P<np>\d+)\) "
    r"core=(?P<core>\d+) stored=(?P<stored>\d+) "
    r"mpll=(?P<mpll>[0-9a-f]+)\(m=(?P<mm>\d+) n=(?P<mn>\d+) "
    r"p=(?P<mp>\d+)\) mem=(?P<mem>\d+) vpll=(?P<vpll>[0-9a-f]+) "
    r"pix=(?P<pix>\d+)")

# Phase, and the coalescing attribution. A separate line from `vbl` on
# purpose: `vbl` is parsed by an exact regex here and in vblank_ab.py, and a
# widened line stops matching rather than failing -- which reads as a soak that
# emitted nothing.
PHASE = re.compile(
    r"vblphase n=(?P<n>\d+) period=(?P<period>\d+) mean=(?P<mean>\d+) "
    r"p50=(?P<p50>\d+) p90=(?P<p90>\d+) p99=(?P<p99>\d+) "
    r"max=(?P<max>\d+) neg=(?P<neg>\d+) "
    r"nodef\(n=(?P<nodef_n>\d+) mean=(?P<nodef_mean>\d+) "
    r"max=(?P<nodef_max>\d+)\) "
    r"def\(n=(?P<def_n>\d+) mean=(?P<def_mean>\d+) "
    r"max=(?P<def_max>\d+)\) unl=(?P<unl>\d+) "
    r"coal=(?P<coal>\d+) coal_en=(?P<coal_en>\d+) "
    r"coal_short=(?P<coal_short>\d+) coal_gap=(?P<coal_gap>\d+) "
    r"en=(?P<en>\d+)")

NV2A_CORE_HZ = 233333333   # documented part speed, not a measurement of ours
NV2A_MEM_HZ = 200000000

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


def weighted(rows, n_key, sum_key_mean):
    """Re-pool a per-window mean back into a population mean.

    A mean of per-window means weights a two-assertion window the same as a
    120-assertion one. Every regime split here is uneven by construction --
    unlock mode comes and goes with the scene -- so the pooling has to carry
    the counts.
    """
    n = sum(int(r[n_key]) for r in rows)
    if not n:
        return 0, 0
    tot = sum(int(r[n_key]) * int(r[sum_key_mean]) for r in rows)
    return n, tot // n


def describe_phase(label, rows):
    """Phase: where an assertion landed against the slot it was scheduled
    into. Rate and phase are different properties; #65 fixed the rate and
    said so, and this is the other one."""
    if not rows:
        print("  %-22s (no windows)" % label)
        return
    n, mean = weighted(rows, "n", "mean")
    if not n:
        print("  %-22s (no grid-scheduled assertions)" % label)
        return
    period = int(rows[0]["period"])
    nodef_n, nodef_mean = weighted(rows, "nodef_n", "nodef_mean")
    def_n, def_mean = weighted(rows, "def_n", "def_mean")
    neg = sum(int(r["neg"]) for r in rows)
    unl = sum(int(r["unl"]) for r in rows)
    coal = sum(int(r["coal"]) for r in rows)
    coal_en = sum(int(r["coal_en"]) for r in rows)
    coal_short = sum(int(r["coal_short"]) for r in rows)
    _, coal_gap = weighted(rows, "coal", "coal_gap")
    print("  %-22s %3d windows, %5d grid-scheduled assertions" %
          (label, len(rows), n))
    print("      lateness mean      %9d ns  (%.2f%% of a %d ns period)" %
          (mean, mean * 100.0 / period, period))
    print("      lateness p50/p90/p99 %7d / %d / %d ns" %
          (max(int(r["p50"]) for r in rows),
           max(int(r["p90"]) for r in rows),
           max(int(r["p99"]) for r in rows)))
    print("      lateness max       %9d ns  (%.2fx a period)" %
          (max(int(r["max"]) for r in rows),
           max(int(r["max"]) for r in rows) / float(period)))
    print("      not deferred       %9d ns mean over %d  <- the timer's own "
          "latency" % (nodef_mean, nodef_n))
    print("      deferred           %9d ns mean over %d  <- plus the "
          "deferral hold" % (def_mean, def_n))
    print("      unlock-mode assertions %5d  (%.1f%%)" %
          (unl, unl * 100.0 / n))
    if neg:
        print("      *** neg=%d: an assertion landed BEFORE its scheduled "
              "slot, which a QEMU timer cannot do. The grid has a writer "
              "this instrument does not account for." % neg)
    else:
        print("      neg=0, as the timer semantics require")
    if coal:
        print("      coalesced          %9d, of which %d (%.0f%%) with the "
              "VBLANK interrupt UNMASKED" %
              (coal, coal_en, coal_en * 100.0 / coal))
        print("      coalesced after a short interval %d (%.0f%%), mean "
              "preceding interval %d ns" %
              (coal_short, coal_short * 100.0 / coal, coal_gap))
    else:
        print("      coalesced                  0")


def main():
    vbl, mode, fp, pll, phase = [], [], [], [], []
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
                    continue
                m = FP.search(line)
                if m:
                    fp.append(m.groupdict())
                    continue
                m = PLL.search(line)
                if m:
                    pll.append(m.groupdict())
                    continue
                m = PHASE.search(line)
                if m:
                    phase.append(m.groupdict())
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

    seen = set()
    for m in fp:
        key = tuple(sorted(m.items()))
        if key in seen:
            continue
        seen.add(key)
        want = int(m["want"])
        derived = int(m["derived_fp"])
        print("  flat-panel raster: fp_vtotal=%s fp_htotal=%s "
              "(%s lines x %s px) vde=%s hde=%s vcrtc=%s hcrtc=%s "
              "vsync=%s vvalid=%s hvalid=%s genctl=%s sr01=%s" %
              (m["fp_vtotal"], m["fp_htotal"], m["lines"], m["px"],
               m["vde"], m["hde"], m["vcrtc"], m["hcrtc"], m["vsync"],
               m["vvalid"], m["hvalid"], m["genctl"], m["sr01"]))
        if derived == 0:
            print("      the FP timing generator is NOT fully programmed "
                  "(a total reads 0); no derivation exists inside the NV2A")
        else:
            print("      the FP/VPLL derivation says %d ns (%s against the "
                  "%d ns we return, %s against true NTSC)" %
                  (derived,
                   "%+.4f%%" % ((derived - want) * 100.0 / want),
                   want,
                   "%+.4f%%" % ((derived - NTSC_TRUE_NS) * 100.0
                                / NTSC_TRUE_NS)))

    seen = set()
    for m in pll:
        key = tuple(sorted(m.items()))
        if key in seen:
            continue
        seen.add(key)
        core = int(m["core"])
        mem = int(m["mem"])
        print("  PLLs off a %d Hz crystal: core %d Hz (m=%s n=%s p=%s), "
              "memory %d Hz (m=%s n=%s p=%s), pixel %s Hz" %
              (int(m["xtal"]), core, m["nm"], m["nn"], m["np"],
               mem, m["mm"], m["mn"], m["mp"], m["pix"]))
        for what, got, want in (("core", core, NV2A_CORE_HZ),
                                ("memory", mem, NV2A_MEM_HZ)):
            if got == 0:
                print("      %s PLL never programmed by the guest; it "
                      "calibrates nothing" % what)
            else:
                print("      %s decodes %+.1f%% from the %d Hz the part "
                      "runs at" % (what, (got - want) * 100.0 / want, want))
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

    if phase:
        print()
        print("phase: lateness against the grid slot each VBLANK was "
              "scheduled into")
        describe_phase("all windows", phase)
        print()
        describe_phase("unlock active", [r for r in phase
                                         if int(r["unl"]) > 0])
        print()
        describe_phase("unlock never", [r for r in phase
                                        if int(r["unl"]) == 0])
    else:
        print()
        print("no vblphase lines: this soak predates the phase instrument")


if __name__ == "__main__":
    main()
