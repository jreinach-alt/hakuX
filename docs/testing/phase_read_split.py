#!/usr/bin/env python3
"""
Lever (a)'s ceiling: what share of the PFIFO thread's busy time happens AFTER
the draw's guest-memory reads, and is therefore work the #44 guarantee does not
require the guest to be held for.

Decomposition, derived from the source and verified by an exact identity:

    BUSY  = Surf + Draw + Fin
    Draw  = Vtx + Syn + Prw + Pipe + Desc + Setup + Cmd + unclassified
    Pipe  = Tx + Sh + Lu + Shd          (Shd/shader_compile nests here)

  `Tex` and `Shd` are ALSO printed as top-level terms and `Tot` adds them a
  second time, so Tot double-counts them; BUSY above avoids that.

  READ  (guarantee applies): Surf, Syn, Tx  [+Vtx, Prw conservatively]
    Syn  sync_vertex_ram_buffer   reads guest vertex RAM
    Tx   pipe_bind_tex            fast_hash(vram) + get_texture_layout(vram)
    Surf surface_update           pgraph_vk_upload_surface_data reads guest mem
  POST  (no guest read): Sh, Lu, Shd, Desc, Setup, Cmd, Fin
  UNCLASSIFIED: draw_dispatch time inside no sub-phase.
"""
import re, sys, statistics as st

FIELDS = ["Surf", "Tex", "Shd", "Draw", "Vtx", "Syn", "Prw", "Pipe", "Tx", "Sh",
          "Lu", "Desc", "Setup", "Cmd", "Fin", "Sub", "Fen", "Flip", "Idle",
          "Fr", "St", "Tot"]
READ_CORE = ["Surf", "Syn", "Tx"]
READ_AMBIG = ["Vtx", "Prw"]
POST = ["Sh", "Lu", "Shd", "Desc", "Setup", "Cmd", "Fin"]


# A logcat line can be truncated mid-write at the end of a capture. A missing
# field defaulted to 0.0 would silently shrink BUSY and inflate every share, so
# a line that does not carry all of these is DROPPED and counted, never used.
REQUIRED = ["Surf", "Draw", "Fin", "Vtx", "Syn", "Prw", "Pipe", "Tx", "Sh",
            "Lu", "Desc", "Setup", "Cmd", "Idle", "Tot"]

n_malformed = 0


def parse(path):
    global n_malformed
    out = []
    for line in open(path, errors="replace"):
        if "hakuX-phase" not in line:
            continue
        d = {}
        for f in FIELDS:
            m = re.search(r"(?<![A-Za-z])" + re.escape(f) + r":(-?[\d.]+)", line)
            if m:
                d[f] = float(m.group(1))
        missing = [f for f in REQUIRED if f not in d]
        if missing:
            n_malformed += 1
            print("  SKIPPED a truncated phase line, missing %s" % ",".join(missing))
            continue
        for f in FIELDS:
            d.setdefault(f, 0.0)
        out.append(d)
    return out


def analyse(name, rows):
    print("\n=== %s: %d samples ===" % (name, len(rows)))
    if not rows:
        return
    busy, read_c, read_g, post, unc, idle = [], [], [], [], [], []
    ident = []
    for d in rows:
        b = d["Surf"] + d["Draw"] + d["Fin"]
        sub = (d["Vtx"] + d["Syn"] + d["Prw"] + d["Pipe"] + d["Desc"]
               + d["Setup"] + d["Cmd"])
        u = d["Draw"] - sub
        rg = sum(d[k] for k in READ_CORE)
        rc = rg + sum(d[k] for k in READ_AMBIG)
        p = sum(d[k] for k in POST)
        busy.append(b); read_c.append(rc); read_g.append(rg)
        post.append(p); unc.append(u); idle.append(d["Idle"])
        ident.append(abs((rc + p + u) - b))
    def m(xs):
        return st.mean(xs)
    print("  identity  READ_cons + POST + UNCLASSIFIED == BUSY :"
          " worst residual %.2f ms, mean %.3f ms" % (max(ident), m(ident)))
    print()
    print("  BUSY (pfifo thread)        %7.2f ms/frame" % m(busy))
    print("  Idle (waiting for work)    %7.2f ms/frame" % m(idle))
    print()
    tb = m(busy)
    print("  READ  conservative         %7.2f ms  %5.1f%% of busy" % (m(read_c), m(read_c)/tb*100))
    print("  READ  generous             %7.2f ms  %5.1f%% of busy" % (m(read_g), m(read_g)/tb*100))
    print("  POST-READ                  %7.2f ms  %5.1f%% of busy" % (m(post), m(post)/tb*100))
    print("  UNCLASSIFIED (in Draw)     %7.2f ms  %5.1f%% of busy" % (m(unc), m(unc)/tb*100))
    print()
    lo = m(post) / tb * 100
    hi = (m(post) + m(unc)) / tb * 100
    print("  >>> lever (a) CEILING = POST / BUSY")
    print("      all unclassified is READ-side  : %5.1f%%" % lo)
    print("      all unclassified is POST-side  : %5.1f%%" % hi)
    print("      => ceiling is in [%.0f%%, %.0f%%]" % (lo, hi))
    return lo, hi


allrows = []
per = []
for p in sys.argv[1:]:
    rows = parse(p)
    r = analyse(p.split("/")[-1], rows)
    if r:
        per.append(r)
    allrows += rows
if len(sys.argv) > 2:
    analyse("POOLED", allrows)
    print("\n  per-run reproducibility of the ceiling bracket:")
    for (lo, hi), p in zip(per, sys.argv[1:]):
        print("    %-14s [%.1f%%, %.1f%%]" % (p.split("/")[-1], lo, hi))

# WHAT THIS READER CANNOT SEE, so a zero from it is never read as a finding:
# it needs `hakuX-phase`, which only an NV2A_PERF_LOG build emits
# (`./gradlew assembleDebug -Pperflog=true`). A stock APK produces NO lines at
# all, which is indistinguishable from a title that did no work -- so no
# samples is an ERROR here, not an answer.
if n_malformed:
    print("\nWARNING: dropped %d truncated phase line(s)" % n_malformed)
if not allrows:
    print("\nNO PHASE LINES FOUND. This reader needs an NV2A_PERF_LOG build"
          " (-Pperflog=true); a stock APK emits none. Not a measurement.")
    sys.exit(2)
