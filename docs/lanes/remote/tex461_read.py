#!/usr/bin/env python3
"""Read #461's texture-bind count: the txh[], txu[] and txr[] lines.

    tex461_read.py FILE... [--window A,B]
    tex461_read.py --selftest

A perflog build (NV2A_PERF_LOG) from the #461 count commit onward prints three
lines on hakuX-stall every 60 FINISHES: a finish at a flip stall or at a present
(opt_stats_log_and_reset() in vk/draw.c). Each counts the same 60 finishes.

A FINISH IS NOT A GUEST FLIP. A flip ends with one flip-stall finish and a
present adds another, so 60 finishes are fewer than 60 flips: Crimson Skies'
pair-1 soaks ran 1.47 and 1.38 finishes per flip. Figures "per finish" are what
the lines count. When the input carries hakuX-pace lines (one per 60 flips, with
the flips counted in v0..v4), the report adds the totals per guest flip, which
is the unit a frame rate and the phase line's ms/frame use. #461's R5 and F3
figures were per finish.

The three lines:

  txh[]  content hashes and KiB, by the first reason that applies:
           new   a new cache node          rb   a node rebuilt (format, pad alpha)
           srf   a draw-dirty surface over the texture, downloaded first
           mk    a mark: the per-draw poll or an aliasing write
           memo  this flip's earlier dirty verdict; no fresh bitmap test
           bit   a fresh bitmap hit, no surface over the texture
           bov   a fresh bitmap hit, a surface over the texture
           oth   none of them: must be 0
         eq   found bindings whose hash compared equal: the hash bought nothing
         rep  hashes of a node already hashed in the same flip
  txu[]  uploads (n) and their guest KiB, by cause (new, rb, chg: content
         changed, oth: a replacement), then the KiB each decode path read:
         lin (linear copy), bc (native BC copy), s3tc (CPU decompress),
         pal (palette), cvt (other conversion), swz (unswizzle only)
  txr[]  create_texture calls, bind calls / those that ran the loop, surface
         downloads a bind started directly (dl, with KiB) and through its range
         scans (sc scans, scdl downloads), images made (img, pool hits),
         surface-to-texture copies (s2tc), and direct binds made where the
         view changed (s2td; a bind that reuses the bound view is not counted)

IDENTITIES, checked on every 60-frame group, because a hash and its upload
happen in one create_texture() call and the counters reset between groups:
  I1  oth == 0
  I2  txh new == txu new, and txh rb == txu rb
  I3  txh (srf+mk+memo+bit+bov) == eq + txu chg
  I4  txu n == new + rb + chg + oth
A violation means the instrument is wrong, not the title.

--window A,B keeps lines from A to B seconds after the first hakuX-perf line
(or the first line, if there is none); it needs logcat timestamps. Lines
already cut to a window, as the host posts them, need no --window. The cut is
docs/testing/phase_read_split.py's THE WINDOW, so this reader and that one
read a soak's lines over the same window: logcat stamps carry no year, and
that is where the year a stamp is read in is decided.
"""
import argparse
import contextlib
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "testing"))
from phase_read_split import window_lines  # noqa: E402

TXH = ["new", "rb", "srf", "mk", "memo", "bit", "bov", "oth", "eq", "rep"]
TXU_CAUSE = ["new", "rb", "chg", "oth"]
TXK = ["lin", "bc", "s3tc", "pal", "cvt", "swz"]
FOUND = ["srf", "mk", "memo", "bit", "bov"]

RE_TXH = re.compile(r"txh\[" + " ".join(r"%s(\d+)/(\d+)K" % n for n in TXH) + r"\]")
RE_TXU = re.compile(r"txu\[n(\d+)/(\d+)K " + " ".join(r"%s(\d+)" % n for n in TXU_CAUSE) +
                    " " + " ".join(r"%s(\d+)K" % n for n in TXK) + r"\]")
RE_TXR = re.compile(r"txr\[ct(\d+) bt(\d+)/(\d+) dl(\d+)/(\d+)K sc(\d+) scdl(\d+) "
                    r"img(\d+) pool(\d+) s2tc(\d+) s2td(\d+)\]")
RE_PACE = re.compile(r"hakuX-pace.*?v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+)")


def flips(lines):
    """The guest flips the hakuX-pace lines among these lines count."""
    return sum(sum(int(x) for x in m.groups()) for m in map(RE_PACE.search, lines) if m)


def parse(lines, window=None):
    """Group the three lines of each 60-frame block. Returns (groups, dropped)."""
    if window:
        lines = window_lines(lines, window)
    groups, cur, dropped = [], {}, 0
    for l in lines:
        kind = "txh" if "txh[" in l else "txu" if "txu[" in l else "txr" if "txr[" in l else None
        if not kind:
            continue
        m = {"txh": RE_TXH, "txu": RE_TXU, "txr": RE_TXR}[kind].search(l)
        if not m:
            dropped += 1        # truncated mid-write: counted, never used
            continue
        v = [int(x) for x in m.groups()]
        if kind == "txh":
            cur = {"txh": {n: (v[2 * i], v[2 * i + 1]) for i, n in enumerate(TXH)}}
        elif kind == "txu" and "txh" in cur and "txu" not in cur:
            cur["txu"] = {"n": v[0], "kib": v[1], **dict(zip(TXU_CAUSE, v[2:6])),
                          "k": dict(zip(TXK, v[6:12]))}
        elif kind == "txr" and "txu" in cur:
            cur["txr"] = dict(zip(["ct", "bt", "btl", "dl", "dlkib", "sc", "scdl",
                                   "img", "pool", "s2tc", "s2td"], v))
            groups.append(cur)
            cur = {}
        else:
            dropped += 1        # out of order: a lost line split a group
            cur = {}
    return groups, dropped


def identities(g):
    h, u = g["txh"], g["txu"]
    bad = []
    if h["oth"][0]:
        bad.append("I1 oth=%d" % h["oth"][0])
    if h["new"][0] != u["new"] or h["rb"][0] != u["rb"]:
        bad.append("I2 txh new/rb %d/%d vs txu %d/%d" % (h["new"][0], h["rb"][0], u["new"], u["rb"]))
    found = sum(h[n][0] for n in FOUND)
    if found != h["eq"][0] + u["chg"]:
        bad.append("I3 found %d vs eq %d + chg %d" % (found, h["eq"][0], u["chg"]))
    if u["n"] != sum(u[c] for c in TXU_CAUSE):
        bad.append("I4 n %d vs causes %d" % (u["n"], sum(u[c] for c in TXU_CAUSE)))
    return bad


def pct(a, b):
    return "%5.1f%%" % (100.0 * a / b) if b else "   n/a"


def report(name, groups, dropped, n_flips=0):
    print("\n=== %s: %d groups of 60 finishes%s ===" % (
        name, len(groups), ", %d line(s) dropped" % dropped if dropped else ""))
    if not groups:
        return 0
    viol = 0
    for i, g in enumerate(groups):
        bad = identities(g)
        if bad:
            viol += 1
            if viol <= 5:
                print("  IDENTITY VIOLATION in group %d: %s" % (i, "; ".join(bad)))
    print("  identities I1-I4: %s" % ("all hold" if not viol else "%d group(s) violate" % viol))

    k = len(groups)
    hn = {n: sum(g["txh"][n][0] for g in groups) for n in TXH}
    hk = {n: sum(g["txh"][n][1] for g in groups) for n in TXH}
    reasons = [n for n in TXH if n not in ("eq", "rep")]
    tn, tk = sum(hn[n] for n in reasons), sum(hk[n] for n in reasons)
    print("\n  CONTENT HASHES   %d (%.1f per finish), %d KiB (%.1f KiB per finish)" % (
        tn, tn / (60.0 * k), tk, tk / (60.0 * k)))
    for n in reasons:
        print("    %-5s %8d  %10d KiB  %s of KiB" % (n, hn[n], hk[n], pct(hk[n], tk)))
    fn, fk = sum(hn[n] for n in FOUND), sum(hk[n] for n in FOUND)
    print("    found bindings hashed: %d, of which equal (eq) %d = %s by count, %s by KiB" % (
        fn, hn["eq"], pct(hn["eq"], fn), pct(hk["eq"], fk)))
    print("    repeats within a flip (rep): %d = %s of hashes, %s of KiB" % (
        hn["rep"], pct(hn["rep"], tn), pct(hk["rep"], tk)))

    un = sum(g["txu"]["n"] for g in groups)
    uk = sum(g["txu"]["kib"] for g in groups)
    kk = {n: sum(g["txu"]["k"][n] for g in groups) for n in TXK}
    kt = sum(kk.values())
    print("\n  UPLOADS          %d (%.2f per finish), %d guest KiB" % (un, un / (60.0 * k), uk))
    print("    by cause: " + "  ".join("%s %d" % (c, sum(g["txu"][c] for g in groups)) for c in TXU_CAUSE))
    print("    KiB by decode path (%d KiB read):" % kt)
    for n in TXK:
        print("      %-5s %10d KiB  %s" % (n, kk[n], pct(kk[n], kt)))
    dec = kk["s3tc"] + kk["pal"] + kk["cvt"] + kk["swz"]
    print("    through a CPU decode other than a plain copy: %s (s3tc+pal+cvt+swz); "
          "%s without unswizzle" % (pct(dec, kt), pct(dec - kk["swz"], kt)))

    r = {n: sum(g["txr"][n] for g in groups) for n in groups[0]["txr"]}
    print("\n  THE REST OF A BIND, per finish")
    print("    create_texture %.1f   bind calls %.1f (ran the loop %.1f)" % (
        r["ct"] / (60.0 * k), r["bt"] / (60.0 * k), r["btl"] / (60.0 * k)))
    print("    surface downloads: direct %.2f (%d KiB total), by range scan %.2f of %.1f scans" % (
        r["dl"] / (60.0 * k), r["dlkib"], r["scdl"] / (60.0 * k), r["sc"] / (60.0 * k)))
    print("    images made %.2f (pool hits %.2f)   s2t copies %.2f, direct binds made "
          "(the view changed) %.2f" % (
        r["img"] / (60.0 * k), r["pool"] / (60.0 * k), r["s2tc"] / (60.0 * k), r["s2td"] / (60.0 * k)))
    print("    downloads + images per create_texture call: %.3f" % (
        (r["dl"] + r["scdl"] + r["img"]) / float(r["ct"]) if r["ct"] else float("nan")))

    if n_flips:
        f = float(n_flips)
        print("\n  PER GUEST FLIP (%d flips on hakuX-pace; %.2f finishes per flip)" % (
            n_flips, 60.0 * k / f))
        print("    content hashes %.1f, %.0f KiB; by reason: %s" % (
            tn / f, tk / f, "  ".join("%s %.1f/%.0fK" % (n, hn[n] / f, hk[n] / f)
                                      for n in reasons if hn[n])))
        print("    uploads %.2f   create_texture %.1f   bind calls %.1f" % (
            un / f, r["ct"] / f, r["bt"] / f))
    return viol


SAMPLE = """\
09-27 05:00:01.000 I/hakuX-perf( 1): gfps=30
09-27 05:00:02.000 I/hakuX-stall( 1): txh[new2/64K rb0/0K srf0/0K mk1/16K memo5/80K bit1/16K bov0/0K oth0/0K eq6/96K rep5/80K]
09-27 05:00:02.000 I/hakuX-stall( 1): txu[n3/96K new2 rb0 chg1 oth0 lin0K bc32K s3tc0K pal16K cvt0K swz48K]
09-27 05:00:02.000 I/hakuX-stall( 1): txr[ct40 bt90/30 dl0/0K sc3 scdl0 img2 pool1 s2tc0 s2td1]
09-27 05:00:04.000 I/hakuX-stall( 1): txh[new0/0K rb0/0K srf0/0K mk0/0K memo2/32K bit0/0K bov0/0K oth0/0K eq2/32K rep2/32K]
09-27 05:00:04.000 I/hakuX-stall( 1): txu[n0/0K new0 rb0 chg0 oth0 lin0K bc0K s3tc0K pal0K cvt0K swz0K]
09-27 05:00:04.000 I/hakuX-stall( 1): txr[ct12 bt70/12 dl0/0K sc0 scdl0 img0 pool0 s2tc0 s2td0]
"""


def selftest():
    ok = True
    g, d = parse(SAMPLE.splitlines())
    ok &= len(g) == 2 and d == 0 and not any(identities(x) for x in g)
    # positive control: a group whose found hashes exceed eq + chg must be caught
    bad = SAMPLE.replace("eq6/96K", "eq5/80K", 1)
    g2, _ = parse(bad.splitlines())
    ok &= any(b.startswith("I3") for b in identities(g2[0]))
    # a truncated line is dropped and counted, not read as zeros
    cut = SAMPLE.replace("s2td1]", "s2t", 1)
    g3, d3 = parse(cut.splitlines())
    ok &= len(g3) == 1 and d3 == 1
    # the window keeps only lines inside it
    g4, _ = parse(SAMPLE.splitlines(), window=(2.0, 2.5))
    ok &= len(g4) == 0
    g5, _ = parse(SAMPLE.splitlines(), window=(0.5, 1.5))
    ok &= len(g5) == 1
    # a window across midnight: 29 February parses, a common year's end of
    # February is one night, and New Year is too
    for first, then in (("02-29 23:59:59.000", "03-01 00:00:01.000"),
                        ("02-28 23:59:59.000", "03-01 00:00:01.000"),
                        ("12-31 23:59:59.000", "01-01 00:00:01.000")):
        s = SAMPLE.replace("09-27 05:00:01.000", first).replace("09-27 05:00:02.000", then)
        g6, _ = parse(s.splitlines(), window=(1.5, 2.5))
        ok &= len(g6) == 1
    # #480 audit LOW-2: a 29 February more than half a year from the origin
    # is re-read in the neighbouring, common year, where it does not exist.
    # It is outside the window, and must not raise: the reader before this
    # case raised ValueError here.
    s = (SAMPLE.replace("09-27 05:00:01.000", "12-31 23:59:59.000")
               .replace("09-27 05:00:02.000", "01-01 00:00:01.000")
               .replace("09-27 05:00:04.000", "02-29 00:00:01.000"))
    g7, _ = parse(s.splitlines(), window=(0.0, 1e9))
    ok &= len(g7) == 1 and g7[0]["txr"]["ct"] == 40
    # Flips come from hakuX-pace, never from the groups: 60 finishes are not
    # 60 flips. 40 flips under 2 groups of 60 finishes is 3 finishes per flip,
    # and the two groups' 11 hashes and 208 KiB are 0.275 and 5.2 per flip.
    pace = "09-27 05:00:03.000 I/hakuX-pace( 1): f=60 v0=0 v1=0 v2=30 v3=10 v4=0 vb=90 max=50.0 ms=2000.0"
    lines = (SAMPLE + pace).splitlines()
    ok &= flips(lines) == 40 and flips(SAMPLE.splitlines()) == 0
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        report("sample", parse(lines)[0], 0, flips(lines))
    ok &= "PER GUEST FLIP (40 flips on hakuX-pace; 3.00 finishes per flip)" in out.getvalue()
    ok &= "content hashes 0.3, 5 KiB" in out.getvalue()
    print("selftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--window", help="A,B seconds after the first hakuX-perf line")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.files:
        ap.error("no input")
    w = tuple(float(x) for x in a.window.split(",")) if a.window else None
    viol, total = 0, 0
    for f in a.files:
        lines = open(f, errors="replace").read().splitlines()
        if w:
            lines = window_lines(lines, w)
        groups, dropped = parse(lines)
        total += len(groups)
        viol += report(f.split("/")[-1], groups, dropped, flips(lines))
    # A stock build prints none of these lines, which is not a measurement.
    if not total:
        print("\nNO txh/txu/txr LINES. This reader needs an NV2A_PERF_LOG build "
              "(-Pperflog=true) at or after #461's count commit.")
        return 2
    return 1 if viol else 0


if __name__ == "__main__":
    sys.exit(main())
