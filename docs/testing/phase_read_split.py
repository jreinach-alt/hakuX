#!/usr/bin/env python3
"""
Lever (a)'s ceiling: what share of the PFIFO thread's busy time happens AFTER
the draw's guest-memory reads, and is therefore work the #44 guarantee does not
require the guest to be held for.

    phase_read_split.py [--window A,B] LOGCAT...
    phase_read_split.py --selftest

Every figure is a mean over the file's hakuX-phase lines, or over those
stamped A to B seconds after the first hakuX-perf line with --window (see
THE WINDOW below the docstring).

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

  So do not compare a span across that fix without allowing for it:
  - the children of Draw and Pipe (Pipe, Tx, Setup, ...) read lower on a new
    line, by the nested finish no longer counted in them;
  - Draw, and with it BUSY, reads higher on a title that clears through the
    fall-through path, by that clear's pre-draw and recording, which sat
    outside Draw before.
  Neither change is the title's.

  TEXTURE BINDS (new lines only): Tx + FTx is every pgraph_vk_bind_textures
  call, and the only route to a texture upload or content hash. So
    binds = TxH (content hash) + Tex (upload) + rest (lookups, descriptors)
  where rest holds no finish time: Tx, FTx and Tex are all exclusive of
  finish, and TxH's fast_hash() cannot reach one.
"""
import argparse, re, sys, statistics as st
from datetime import datetime

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

# THE WINDOW (--window A,B). A soak's registered figures are read "A to B s
# after the first hakuX-perf line", its timeline's origin (the first stamped
# line when there is no hakuX-perf line). `logcat -v time` stamps carry no
# year:
# - A stamp is read in a leap year only when a 29 February stamp is in the
#   input, and in a common year otherwise. A fixed leap year would read a
#   common year's 28 February to 1 March as two days, and silently drop a
#   window across that midnight. A fixed common year cannot parse 29 February.
# - A stamp more than half a year from the origin is read in the neighbouring
#   year, so a window may cross New Year.
# - A 29 February that the neighbouring year does not have is outside every
#   window: it is more than half a year from the origin in the year it parses
#   in, so it cannot lie in a window a few minutes long.
# tex461_read.py and pair461_read.py (docs/lanes/remote/) import this, so a
# soak's lines are cut to one window by one rule.
RE_TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d(?:\.\d+)?)")
EPOCH = datetime(2000, 1, 1)
HALF_YEAR = 183 * 86400.0


def stamp(text, year=2001):
    """The stamp opening `text` ("MM-DD HH:MM:SS[.fff]") as seconds since
    2000 when read in `year`. None when there is no stamp, or when its date
    does not exist in `year`."""
    m = RE_TS.match(text)
    if not m:
        return None
    fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in m.group(1) else "%Y-%m-%d %H:%M:%S"
    try:
        t = datetime.strptime("%d-%s" % (year, m.group(1)), fmt)
    except ValueError:
        return None
    return (t - EPOCH).total_seconds()


class Clock:
    """Seconds since a window's origin, for any stamp read with THE WINDOW's
    rules. t0 is None when no line carries a stamp."""

    def __init__(self, lines):
        self.year = 2001
        if any(l.startswith("02-29") and RE_TS.match(l) for l in lines):
            self.year = 2000
        stamped = [l for l in lines if stamp(l, self.year) is not None]
        first = next((l for l in stamped if "hakuX-perf" in l),
                     stamped[0] if stamped else None)
        self.t0 = stamp(first, self.year) if first is not None else None

    def since(self, text):
        if self.t0 is None:
            return None
        t = stamp(text, self.year)
        if t is not None and abs(t - self.t0) > HALF_YEAR:   # New Year between
            t = stamp(text, self.year + (1 if t < self.t0 else -1))
        return None if t is None else t - self.t0


def window_lines(lines, window):
    """The lines stamped window[0] to window[1] s after the origin."""
    c = Clock(lines)
    if c.t0 is None:
        sys.exit("--window needs logcat timestamps, and these lines have none")
    out = []
    for l in lines:
        s = c.since(l)
        if s is not None and window[0] <= s <= window[1]:
            out.append(l)
    return out


def parse(path, window=None):
    lines = open(path, errors="replace").read().splitlines()
    return parse_lines(window_lines(lines, window) if window else lines)


def parse_lines(lines):
    global n_malformed, n_old, n_new
    out = []
    for line in lines:
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


SAMPLE = """\
12-31 23:59:58.000 I/hakuX-perf( 1): gfps=30 G:33.3
12-31 23:59:59.000 I/hakuX-phase( 1): Surf:1.0 Tex:0.5 TxH:0.2 Shd:0.0 Draw:10.0 [Vtx:1.0 Syn:1.0 Prw:0.5 Pipe:2.0(Tx:1.0 Sh:0.5 Lu:0.2) Desc:1.0 Setup:1.0 Cmd:1.0 Sfp:1.0 Mfp:0.5 FTx:0.5] Fin:2.0(Sub:1.0 Fen:0.5) Flip:0.1 Idle:5.0(Fr:3.0 St:2.0) | Tot:18.6 GPU:9.0(R:8.0 X:1.0 RP:4 Pre:0.1 Post:0.1 MxG:1.0 g:1/0/0) ms
01-01 00:00:01.000 I/hakuX-phase( 1): Surf:2.0 Tex:0.5 TxH:0.2 Shd:0.0 Draw:10.0 [Vtx:1.0 Syn:1.0 Prw:0.5 Pipe:2.0(Tx:1.0 Sh:0.5 Lu:0.2) Desc:1.0 Setup:1.0 Cmd:1.0 Sfp:1.0 Mfp:0.5 FTx:0.5] Fin:2.0(Sub:1.0 Fen:0.5) Flip:0.1 Idle:5.0(Fr:3.0 St:2.0) | Tot:19.6 GPU:9.0(R:8.0 X:1.0 RP:4 Pre:0.1 Post:0.1 MxG:1.0 g:1/0/0) ms
"""


def selftest():
    ok = True
    lines = SAMPLE.splitlines()
    # the window keeps the phase line one second after the origin only
    keep = parse_lines(window_lines(lines, (0.5, 1.5)))
    ok &= len(keep) == 1 and keep[0]["Surf"] == 1.0
    # across New Year: the line after midnight is 3 s after the origin
    keep = parse_lines(window_lines(lines, (2.5, 3.5)))
    ok &= len(keep) == 1 and keep[0]["Surf"] == 2.0
    # across the end of February, in a leap year and in a common one
    for a, b in (("02-28", "03-01"), ("02-29", "03-01")):
        s2 = SAMPLE.replace("12-31", a).replace("01-01", b)
        keep = parse_lines(window_lines(s2.splitlines(), (2.5, 3.5)))
        ok &= len(keep) == 1 and keep[0]["Surf"] == 2.0
    # a 29 February more than half a year from the origin, re-read in a
    # common neighbouring year: outside the window, not a ValueError
    s3 = SAMPLE.replace("01-01 00:00:01", "02-29 00:00:01")
    keep = parse_lines(window_lines(s3.splitlines(), (0.0, 1e9)))
    ok &= len(keep) == 1 and keep[0]["Surf"] == 1.0
    # the origin is the first hakuX-perf line, not the first line
    s4 = "12-31 23:59:50.000 I/other( 1): x\n" + SAMPLE
    keep = parse_lines(window_lines(s4.splitlines(), (0.5, 1.5)))
    ok &= len(keep) == 1 and keep[0]["Surf"] == 1.0
    print("selftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--window", help="A,B seconds after the first hakuX-perf line")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.files:
        ap.error("no input")
    w = tuple(float(x) for x in a.window.split(",")) if a.window else None
    if w:
        print("window: %g to %g s after the first hakuX-perf line" % w)
    allrows = []
    per = []
    for p in a.files:
        rows = parse(p, w)
        r = analyse(p.split("/")[-1], rows)
        if r:
            per.append(r)
        allrows += rows
    if len(a.files) > 1:
        analyse("POOLED", allrows)
        print("\n  per-run reproducibility of the ceiling bracket:")
        for (lo, hi), p in zip(per, a.files):
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
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
