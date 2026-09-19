#!/usr/bin/env python3
"""#50: the per-RUN shape of the full-disc race, across ten fresh runs.

`fulldisc_instability_50.py` answers "which captures ever moved, and did a
device disagree with ITSELF".  This answers the next question, which is the
one the withdrawn 7.7% rate got wrong by collapsing it: **on which run did
each mover depart, and how many captures departed per run.**

The brief is explicit that the deliverable is a table, not a rate.  So this
prints one row per RUN with the captures that departed on it, and one row per
CAPTURE with its value on every run.  There is no mean anywhere in the file.

WHAT "DEPARTED" MEANS HERE, and why it is not "differs from the golden"
-----------------------------------------------------------------------
Nearly every Blend capture differs from hardware -- that is issue #50 itself,
1,567 of 1,568 wrong.  The quantity this file is about is different: a capture
departing from *what the same device produced on its other runs of the same
binary and the same disc*.  So the reference is the MODAL capture hash for
that (capture, device), and a departure is a run whose bytes are not the mode.

A capture with no mode -- every run different, or a 3/3 split -- is reported
separately and never silently assigned one.  On this data there are none, and
the check stays because its absence is what makes "the odd run" meaningful.

THE THREE TESTS THIS RUNS ON THE 21 EVENTS
-------------------------------------------
1. DIRECTION.  Does the departing run render MORE wrong than the mode, or
   less?  Measured as pixels matching the golden over the moved mask, both
   ways.  "The odd run is always the wrong one" was asserted on 5 events;
   21 is enough for it to fail.

2. CONTENT.  Is the deposited content grey (R==G==B), as it was on all five
   of the earlier movers?  Same measurement, wider sample.

3. THE CLOCK EXCURSION.  The guest progress log carries ~-24,500 ms durations
   on 2.3-2.6% of tests, evenly spaced in wall clock.  On the single event
   available before, the excursion landed on the run that was RIGHT, so it
   was rejected.  With 21 events that rejection can be made properly: under
   independence ~0.5 of 21 events would coincide with an excursion, so a
   handful of coincidences would be a real signal and zero is a real
   refutation.  The expected count is printed next to the observed one so
   the reader is not asked to do that arithmetic in their head.

   Note the regex: `(-?\\d+)ms`.  Dropping the minus sign is how these rows
   were nearly missed the first time -- they simply did not match, and a log
   that silently omits 2.5% of its rows looks exactly like a complete one.
"""
import os, re, csv, json, sys, glob, hashlib, collections

R = os.environ.get("HAKUX_RESULTS", "/home/justin/hakux-work/dispatch/results")
G = os.environ.get("GOLDENS", "/home/justin/goldens/results")
APK = "b0cba34acef7"
SUITE = "Blend_tests"
FULL = 1673


def load_runs():
    """Every full-disc scored run on disk for the one binary, in time order."""
    out = []
    for d in sorted(os.listdir(R)):
        rj = os.path.join(R, d, "result.json")
        if not os.path.exists(rj):
            continue
        try:
            meta = json.load(open(rj))
        except Exception:
            continue
        if meta.get("apk_sha") != APK:
            continue
        for n in range(1, 33):
            tsv = os.path.join(R, d, "scores%d.tsv" % n)
            if not os.path.exists(tsv):
                continue
            rows = {}
            with open(tsv) as f:
                for r in csv.DictReader(f, delimiter="\t"):
                    if r["suite"] == SUITE:
                        rows[r["test"]] = r
            if len(rows) != FULL:          # composition control: full disc only
                continue
            out.append(dict(name="%s#%d" % (meta.get("requester") or d, n),
                            device=meta.get("device_label") or "?",
                            capdir=os.path.join(R, d, "captures%d" % n),
                            rows=rows))
    return out


def h(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:8]


def hashes(run):
    cd = run["capdir"]
    out = {}
    for t in run["rows"]:
        p = os.path.join(cd, "%s::%s.png" % (SUITE, t))
        out[t] = h(p) if os.path.exists(p) else None
    return out


def progress(run):
    """test -> (index, duration_ms) from the guest's own log."""
    p = os.path.join(run["capdir"], "pgraph_progress_log.txt")
    order, dur = [], {}
    if not os.path.exists(p):
        return {}, []
    for line in open(p, errors="replace"):
        line = line.strip()
        m = re.match(r"Starting \[(\d+)/\d+\] Blend tests::(.*)", line)
        if m:
            order.append(m.group(2))
            continue
        m = re.match(r"Completed \[(\d+)/\d+\] '(.*)' in (-?\d+)ms", line)
        if m:
            dur[m.group(2)] = int(m.group(3))
    return dur, order


def runs_of(ix):
    """[3,4,5,9,10] -> [(3,3),(9,2)] -- contiguous runs as (start, length).

    The bounding box of a mask says nothing about whether the mask fills it.
    These runs are what separates "a block of rows" from "rows scattered
    through a range", and on this data the two readings differ for 10 of the
    22 events -- so the distinction is load-bearing, not pedantry.
    """
    out = []
    for v in (int(x) for x in ix):
        if out and v == out[-1][0] + out[-1][1]:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return [(a, b) for a, b in out]


def main():
    runs = load_runs()
    if not runs:
        print("no full-disc runs on disk for apk %s" % APK)
        return 2
    print("=== %d full-disc runs, apk %s" % (len(runs), APK))
    H = {r["name"]: hashes(r) for r in runs}
    bydev = collections.OrderedDict()
    for r in runs:
        bydev.setdefault(r["device"], []).append(r)
    for d, rs in bydev.items():
        print("  %-5s %d runs: %s" % (d, len(rs), [r["name"] for r in rs]))

    # ---- departures from the per-(capture, device) modal bytes ------------
    events = collections.defaultdict(list)     # run name -> [capture, ...]
    per_capture = []
    nomode = []
    for dev, rs in bydev.items():
        for t in sorted(rs[0]["rows"]):
            vals = [H[r["name"]][t] for r in rs]
            if len(set(vals)) == 1:
                continue
            c = collections.Counter(vals)
            top, n_top = c.most_common(1)[0]
            if n_top <= len(vals) / 2.0:
                nomode.append((dev, t, vals))
                continue
            odd = [r["name"] for r, v in zip(rs, vals) if v != top]
            for o in odd:
                events[o].append(t)
            per_capture.append((t, dev, odd, vals,
                                [int(r["rows"][t]["differing"]) for r in rs]))

    print()
    print("=== DEPARTURES PER RUN  (a departure is a run whose capture bytes")
    print("    are not that device's modal bytes for that capture)")
    for r in runs:
        ev = sorted(events.get(r["name"], []))
        print("  %-22s %-5s  %d departure(s)%s"
              % (r["name"], r["device"], len(ev), ("  " + ", ".join(ev)) if ev else ""))
    tot = sum(len(v) for v in events.values())
    print("  total departures: %d over %d runs, %d distinct captures"
          % (tot, len(runs), len(set(t for v in events.values() for t in v))))
    if nomode:
        print("  NO MODAL VALUE on %d capture(s) -- not assigned an odd run: %s"
              % (len(nomode), [x[1] for x in nomode]))
    else:
        print("  every moving capture had a clear modal value (no 50/50 splits),")
        print("  which is what makes 'the odd run' a well-defined thing to say")

    print()
    print("=== PER CAPTURE, every run's value  (no mean, no pooled rate)")
    for t, dev, odd, vals, counts in sorted(per_capture):
        print("  %-24s %-5s odd=%s" % (t, dev, ",".join(odd)))
        print("      bytes  %s" % vals)
        print("      counts %s" % counts)

    # ---- the three tests on the events ------------------------------------
    try:
        import numpy as np
        from PIL import Image
    except Exception as e:
        print("\n(no numpy/PIL: skipping content tests -- %s)" % e)
        return 0

    def rgba(p):
        return np.asarray(Image.open(p).convert("RGBA"), dtype=np.uint8)

    byname = {r["name"]: r for r in runs}
    print()
    print("=== DIRECTION AND CONTENT OF EACH DEPARTURE")
    print("  'golden RGB' columns count, over the moved mask only, how many")
    print("  pixels each side matches hardware on -- so a departure that is")
    print("  a CORRECTION would show odd > mode.")
    print()
    print("  %-24s %-6s %7s %6s %7s %9s %9s %6s %-17s"
          % ("capture", "run", "moved", "a-only", "grey%", "odd==gold",
             "mode==gold", "idx", "rows/cols moved"))
    worse = better = neither = 0
    grey_rows = []
    idx_by_run = collections.defaultdict(list)
    boxes = []
    shapes = []
    for t, dev, odd, vals, counts in sorted(per_capture):
        rs = bydev[dev]
        c = collections.Counter(H[r["name"]][t] for r in rs)
        top = c.most_common(1)[0][0]
        good = next(r for r in rs if H[r["name"]][t] == top)
        gp = os.path.join(G, SUITE, "%s.png" % t)
        gl = rgba(gp) if os.path.exists(gp) else None
        for o in odd:
            b = rgba(os.path.join(byname[o]["capdir"], "%s::%s.png" % (SUITE, t)))
            g = rgba(os.path.join(good["capdir"], "%s::%s.png" % (SUITE, t)))
            mask = np.any(b[:, :, :3] != g[:, :, :3], axis=2)
            anym = np.any(b != g, axis=2)
            n = int(mask.sum())
            aonly = int(anym.sum()) - n
            bs = b[mask]
            grey = int(((bs[:, 0] == bs[:, 1]) & (bs[:, 1] == bs[:, 2])).sum())
            gm = bm = -1
            if gl is not None and n:
                gm = int(np.all(g[mask][:, :3] == gl[mask][:, :3], axis=1).sum())
                bm = int(np.all(bs[:, :3] == gl[mask][:, :3], axis=1).sum())
                if bm < gm:
                    worse += 1
                elif bm > gm:
                    better += 1
                else:
                    neither += 1
            pct = 100.0 * grey / max(1, n)
            grey_rows.append(pct)
            _, order = progress(byname[o])
            ix = order.index(t) + 1 if t in order else -1
            idx_by_run[o].append((ix, t))
            ys, xs = np.nonzero(mask)
            box = "r%d-%d c%d-%d" % (ys.min(), ys.max(), xs.min(), xs.max()) if n else "-"
            boxes.append((int(ys.min()), int(ys.max())) if n else (-1, -1))
            if n:
                perrow = mask.sum(axis=1)
                touched = np.nonzero(perrow)[0]
                widths = perrow[touched]
                shapes.append(dict(
                    t=t, run=o,
                    r0=int(touched[0]), r1=int(touched[-1]),
                    nrows=int(len(touched)),
                    contiguous=bool(len(touched) == touched[-1] - touched[0] + 1),
                    wmax=int(widths.max()), wfirst=int(widths[0]),
                    wlast=int(widths[-1]),
                    nfull=int((widths == widths.max()).sum()),
                    rowruns=runs_of(touched),
                    colruns=runs_of(np.nonzero(mask.any(axis=0))[0])))
            print("  %-24s %-6s %7d %6d %6.1f%% %9d %9d %6d %-17s"
                  % (t, o.split("#")[-1] if "-" not in o else o[-8:], n, aonly,
                     pct, bm, gm, ix, box))
    print()
    print("  DIRECTION: odd matches hardware on FEWER px than the mode on %d"
          " event(s), MORE on %d, equal on %d." % (worse, better, neither))
    if better:
        print("  -> 'the odd run is always the wrong one', recorded on 5 events,")
        print("     does NOT hold at 22.  Read those rows before reusing it.")
    if grey_rows:
        print("  CONTENT: grey share of the moved pixels ranges %.1f%%-%.1f%%"
              % (min(grey_rows), max(grey_rows)))
        print("    below 10%%: %d event(s); above 50%%: %d of %d"
              % (sum(1 for p in grey_rows if p < 10),
                 sum(1 for p in grey_rows if p >= 50), len(grey_rows)))

    # ---- do the departures cluster in run order? --------------------------
    #
    # A trigger that is periodic in TIME would put a run's departures near
    # each other in test index; one that is per-test-independent would
    # scatter them.  This is the cheapest discriminator available offline and
    # it needs no new device time, so it is worth printing even though it can
    # only ever be suggestive at these counts.
    print()
    print("=== WHERE IN THE RUN, and do departures cluster?")
    for o in sorted(idx_by_run):
        ixs = sorted(i for i, _ in idx_by_run[o])
        gaps = [b - a for a, b in zip(ixs, ixs[1:])]
        print("  %-22s indices %s%s"
              % (o, ixs, ("   gaps %s" % gaps) if gaps else ""))
    allix = sorted(i for v in idx_by_run.values() for i, _ in v)
    if allix:
        print("  all %d departures span index %d-%d of %d; spread over the disc"
              % (len(allix), min(allix), max(allix), FULL))
    if boxes and all(b[0] >= 0 for b in boxes):
        print("  moved-pixel row extent, every event: r%d-%d"
              % (min(b[0] for b in boxes), max(b[1] for b in boxes)))
        print("  (#50's stack is 64x256; a band confined to those rows is the")
        print("   stack region and not a whole-framebuffer event)")

    # ---- the shape of the corrupted band ----------------------------------
    #
    # A bounding box can say "rows 112-303" while the moved pixels inside it
    # are scattered.  These columns separate the two: `rows` is the number of
    # DISTINCT rows touched and `contig` says whether they are consecutive,
    # so "a prefix of the band" is a measurement rather than a reading of the
    # box.  `w-last` against `w-max` is the one that would show a transfer
    # stopped MID-ROW.
    print()
    print("=== SHAPE OF EACH CORRUPTED BAND")
    print("  %-24s %-22s %5s %5s %6s %6s %6s %6s"
          % ("capture", "run", "r0", "r1", "rows", "contig", "w-max", "w-last"))
    for s in shapes:
        print("  %-24s %-22s %5d %5d %6d %6s %6d %6d"
              % (s["t"], s["run"], s["r0"], s["r1"], s["nrows"],
                 "yes" if s["contiguous"] else "NO", s["wmax"], s["wlast"]))
    if shapes:
        r0s = sorted(set(s["r0"] for s in shapes))
        print("  first moved row, over all %d events: %s" % (len(shapes), r0s))
        print("  heights: %s" % sorted(set(s["nrows"] for s in shapes)))
        print("  all contiguous: %s   any partial last row (w-last < w-max): %s"
              % (all(s["contiguous"] for s in shapes),
                 [s["t"] for s in shapes if s["wlast"] < s["wmax"]] or "none"))
        print()
        print("  the runs themselves, (start,length) -- rows then columns:")
        for s in shapes:
            print("    %-24s rows %s" % (s["t"], s["rowruns"]))
            print("    %-24s cols %s" % ("", s["colruns"]))
        rl = sorted(set(l for s in shapes for _, l in s["rowruns"]))
        cl = sorted(set(l for s in shapes for _, l in s["colruns"]))
        cs = sorted(set(a for s in shapes for a, _ in s["colruns"]))
        print("  distinct row-run lengths:    %s" % rl)
        print("  distinct column-run lengths: %s" % cl)
        print("  distinct column-run starts:  %s" % cs)

    # ---- is the wrong block a copy of the OTHER block in the same image? --
    #
    # A door the earlier whole-image search could not open.  That search
    # compared candidate images to the moved pixels AT THE SAME POSITION, so
    # a block copied from elsewhere WITHIN the image is invisible to it.  The
    # two 64-wide columns at x=16 and x=560 are the obvious pair to try:
    # "the blit read the wrong column" is a mechanism that would produce
    # exactly this geometry.
    #
    # The control is the mode's own two columns.  If left==right already on
    # the run that is RIGHT, then left==right on the odd run says nothing --
    # the test simply draws the same thing twice.  That baseline is printed
    # on every row and is the whole reason this can come back negative.
    print()
    print("=== IS THE CORRUPT BLOCK A COPY OF THE OTHER BLOCK? (x=16 vs x=560)")
    print("  %-24s %-22s %8s %8s" % ("capture", "run", "odd L==R", "mode L==R"))
    hits = 0
    for s in shapes:
        if s["colruns"][:1] != [(16, 64)] or (560, 64) not in s["colruns"]:
            continue
        t, o = s["t"], s["run"]
        dev = next(r["device"] for r in runs if r["name"] == o)
        rs = bydev[dev]
        c = collections.Counter(H[r["name"]][t] for r in rs)
        good = next(r for r in rs if H[r["name"]][t] == c.most_common(1)[0][0])
        b = rgba(os.path.join(byname[o]["capdir"], "%s::%s.png" % (SUITE, t)))
        g = rgba(os.path.join(good["capdir"], "%s::%s.png" % (SUITE, t)))
        sl = slice(s["r0"], s["r1"] + 1)
        def eq(im1, im2):
            a1, a2 = im1[sl, 16:80, :3], im2[sl, 560:624, :3]
            return 100.0 * float(np.all(a1 == a2, axis=2).mean())
        ob, mb = eq(b, b), eq(g, g)
        hits += 1 if ob > mb + 1.0 else 0
        print("  %-24s %-22s %7.1f%% %7.1f%%" % (t, o, ob, mb))
    print("  events where the odd run's two columns agree MORE than the")
    print("  mode's do: %d -- a block copy would make this large." % hits)

    # ---- the clock excursion ----------------------------------------------
    print()
    print("=== THE CLOCK EXCURSION, tested against the departures")
    hit = tot_ev = 0
    exp = 0.0
    for r in runs:
        ev = events.get(r["name"], [])
        if not ev:
            continue
        dur, order = progress(r)
        if not dur:
            print("  %-22s no progress log on disk" % r["name"])
            continue
        bad = {t for t, v in dur.items() if v < 0}
        frac = len(bad) / float(max(1, len(dur)))
        for t in sorted(ev):
            tot_ev += 1
            exp += frac
            mark = "  <-- COINCIDES" if t in bad else ""
            hit += 1 if t in bad else 0
            print("  %-22s %-24s dur=%8s ms   (run has %d/%d negative, %.2f%%)%s"
                  % (r["name"], t, dur.get(t, "?"), len(bad), len(dur),
                     100 * frac, mark))
    if tot_ev:
        print("  coincidences: %d of %d departures; expected under independence"
              " %.2f" % (hit, tot_ev, exp))
        if hit == 0:
            print("  -> the excursion does not select the departing tests. It is")
            print("     not the mechanism, and this is now a %d-event refutation"
                  % tot_ev)
            print("     rather than the 1-event one recorded before.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
