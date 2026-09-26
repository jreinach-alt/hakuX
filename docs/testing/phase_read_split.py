#!/usr/bin/env python3
"""
Lever (a)'s ceiling: what share of the PFIFO thread's busy time happens AFTER
the draw's guest-memory reads, and is therefore work the #44 guarantee does not
require the guest to be held for.

Decomposition, derived from the source and verified by an exact identity:

    BUSY  = Surf + Draw + Fin
    Draw  = Vtx + Syn + Prw + Pipe + Desc + Setup + Cmd
            + Sfp + Mfp + FTx + unclassified
    Pipe  = Tx + Sh + Lu + Shd + rest   (Shd/shader_compile nests here; rest
                                         is create_clear_pipeline() and the
                                         pipeline-cache save, no child span)

  `Tex` and `Shd` are ALSO printed as top-level terms and `Tot` adds them a
  second time, so Tot double-counts them; BUSY above avoids that. `TxH` is
  printed beside `Tex` and, like it, nests in Tx and FTx.

  READ  (guarantee applies): Surf, Syn, Tx, FTx  [+Vtx, Prw conservatively]
    Syn  sync_vertex_ram_buffer   reads guest vertex RAM
    Tx   pipe_bind_tex            fast_hash(vram) + get_texture_layout(vram)
    FTx  the fast paths' pgraph_vk_bind_textures, the same reads as Tx
    Surf surface_update           pgraph_vk_upload_surface_data reads guest mem
  POST  (no guest read): Sh, Lu, Shd, Desc, Setup, Cmd, Fin, Sfp, Mfp,
        Pipe's rest
    Sfp, Mfp  the super-fast and medium-fast paths, hit or miss, less FTx
  UNCLASSIFIED: draw_dispatch time inside no sub-phase.

  Sfp, Mfp, FTx and TxH are printed only by builds from #426's instrument
  fix onward. On an older line they are absent: the fast paths' time is then
  inside UNCLASSIFIED, and FTx's reads with it. The reader says which it saw.
  The same fix made every child of Draw and Pipe exclusive of finish, and
  timed the fall-through clear as Draw. On an older line a finish nested in a
  child is counted there and again in Fin, and a clear's children sit outside
  Draw, so UNCLASSIFIED can go negative there.

  TEXTURE BINDS (new lines only): Tx + FTx is every pgraph_vk_bind_textures
  call, and the only route to a texture upload or content hash. So
    binds = TxH (content hash) + Tex (upload) + rest (lookups, descriptors)
  where rest also carries any finish nested in a Tx bind, since Tx is not
  exclusive of finish and Tex and FTx are.
"""
import re, sys, statistics as st

FIELDS = ["Surf", "Tex", "Shd", "Draw", "Vtx", "Syn", "Prw", "Pipe", "Tx", "Sh",
          "Lu", "Desc", "Setup", "Cmd", "Fin", "Sub", "Fen", "Flip", "Idle",
          "Fr", "St", "Tot", "Sfp", "Mfp", "FTx", "TxH"]
READ_CORE = ["Surf", "Syn", "Tx", "FTx"]
READ_AMBIG = ["Vtx", "Prw"]
POST = ["Sh", "Lu", "Shd", "Desc", "Setup", "Cmd", "Fin", "Sfp", "Mfp"]
DRAW_SUB = ["Vtx", "Syn", "Prw", "Pipe", "Desc", "Setup", "Cmd",
            "Sfp", "Mfp", "FTx"]
# Printed only from #426's instrument fix onward; absent is legitimate on an
# older line, so they are not REQUIRED, and a line is counted as old or new.
NEW_FIELDS = ["Sfp", "Mfp", "FTx", "TxH"]


# A logcat line can be truncated mid-write at the end of a capture. A missing
# field defaulted to 0.0 would silently shrink BUSY and inflate every share, so
# a line that does not carry all of these is DROPPED and counted, never used.
REQUIRED = ["Surf", "Draw", "Fin", "Vtx", "Syn", "Prw", "Pipe", "Tx", "Sh",
            "Lu", "Desc", "Setup", "Cmd", "Idle", "Tot"]

n_malformed = 0
n_old = 0
n_new = 0


def parse(path):
    global n_malformed, n_old, n_new
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
        # The new fields print before Fin and Tot, so a line that reached Tot
        # carries all of them or none; some but not all is a parse fault.
        have = [f for f in NEW_FIELDS if f in d]
        if have and len(have) != len(NEW_FIELDS):
            n_malformed += 1
            print("  SKIPPED a phase line with only %s of %s"
                  % (",".join(have), ",".join(NEW_FIELDS)))
            continue
        d["_new"] = bool(have)
        n_new += d["_new"]
        n_old += not d["_new"]
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
        sub = sum(d[k] for k in DRAW_SUB)
        u = d["Draw"] - sub
        rg = sum(d[k] for k in READ_CORE)
        rc = rg + sum(d[k] for k in READ_AMBIG)
        pipe_rest = d["Pipe"] - (d["Tx"] + d["Sh"] + d["Lu"] + d["Shd"])
        p = sum(d[k] for k in POST) + pipe_rest
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
    new = [d for d in rows if d["_new"]]
    if len(new) != len(rows):
        print("\n  %d of %d lines predate Sfp/Mfp/FTx: their fast paths are"
              " in UNCLASSIFIED" % (len(rows) - len(new), len(rows)))
    if new:
        binds = m([d["Tx"] + d["FTx"] for d in new])
        print("\n  TEXTURE BINDS (Tx + FTx), %d new-format lines" % len(new))
        print("    binds                    %7.2f ms/frame" % binds)
        if binds > 0:
            for k, lab in (("TxH", "content hash (TxH)"),
                           ("Tex", "upload (Tex)")):
                v = m([d[k] for d in new])
                print("    %-24s %7.2f ms  %5.1f%% of binds" % (lab, v, v/binds*100))
            rest = m([d["Tx"] + d["FTx"] - d["TxH"] - d["Tex"] for d in new])
            print("    %-24s %7.2f ms  %5.1f%% of binds"
                  % ("rest (lookup, desc.)", rest, rest/binds*100))
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
