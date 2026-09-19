#!/usr/bin/env python3
"""#50: which Blend captures actually RACE, which only differ BY DEVICE, and
which only differ BETWEEN DISC COMPOSITIONS.

Run with no arguments.  It discovers every result on disk for one binary, one
suite, and reports every capture that ever showed more than one value, with
its value on every single run -- never a mean, never a pooled rate.  The
withdrawn 7.7% was a pooled rate; this file exists so the replacement is not
one too.

WHAT CHANGED, AND WHY THE PREVIOUS ANSWER WAS THE WRONG SHAPE
-------------------------------------------------------------
The first version of this script hardcoded three run directories, asserted
`(apk_sha, disc_id)` equal across them, and reported "5 of 1,673 captures
differ; 4 of the 5 outliers are the SAME RUN (blendstack-A) -- instability is
RUN-SCOPED".  That conclusion was recorded in nv2a_issues.toml as
`blocker_tested`.

It does not follow from the data, because of a variable the comparison did not
name: **blendstack-A is the only nova run**.  B and thor2 are both thor.  So
"4 of 5 outliers are in run A" and "4 of 5 outliers are on the only nova run"
are the same sentence about that data, and the run-scoped reading was one of
two equally supported ones.  devices.sh had already flagged exactly this --
"#50's pair was split across the two handhelds by a scheduler fallthrough,
five of 1,673 captures moved, and nothing here can say whether that is the
disc or the devices" -- and the nv2a_issues entry did not carry the caveat.

That is the same error class the entry already withdrew a rate for: pooling
runs that differ in a variable nothing in the comparison names.  It was the
disc composition the first time and the device the second.  So this script
now refuses to state a shape without splitting on the device, and prints the
device on every row.

THE THREE CONTROLS, all of which this file now takes
----------------------------------------------------
1. BINARY.  Every pooled run must carry one apk_sha.  (The original had this.)

2. DEVICE.  Runs are grouped by `device_serial`, never merged across devices.
   A capture is called a RACE only on the evidence of ONE device disagreeing
   with ITSELF.  A capture where each device is internally constant and the
   devices differ is a DEVICE difference, and saying otherwise is the bug
   above.

3. COMPOSITION -- keyed on the CAPTURE SET, not on disc_id.  disc_id is not
   sufficient here and this is not hypothetical: the 1-test and 5-test
   narrowed runs used for #50's earlier survey are on disk carrying
   `iso:85b525/Blend tests`, byte-identical to the full 1,673-capture disc's
   id, because they predate the fix (63db4e4211) that folded only_tests into
   disc_id.  That fix is PROSPECTIVE.  Any analysis of these artefacts that
   keys on disc_id alone re-commits the exact pooling error #50 withdrew a
   rate for -- it would happily average a 1-capture run against a 1,673-
   capture one.  So composition here is `frozenset(scored keys)`, which cannot
   lie about what ran.

THE INSTRUMENT: capture bytes, with the score column as a cross-check
--------------------------------------------------------------------
The primary reading is sha256 of the capture PNG.  The `differing` column is
a scalar projection of an image: two different framebuffers can share a
differing-pixel count, so a count-only comparison can report stability that
is not there (and cannot distinguish "unchanged" from "wrong replaced by
equally-wrong").

Both are read and disagreements are reported.  On the three runs the original
script used, the two instruments name the SAME five captures -- so the count
was not hiding anything in THAT data.  That is a measured statement about
those runs, not a general licence to use the count; the check is cheap and
stays.

WHAT WOULD FALSIFY THE READING THIS PRODUCES
--------------------------------------------
- A capture called RACE would be refuted by that device never disagreeing
  with itself once more runs exist on it; the classification is recomputed
  from whatever runs are on disk, so it moves on its own.
- A capture called DEVICE would be refuted by either device disagreeing with
  itself on a later run.
- "The devices differ at all" would be refuted by the DEVICE set coming back
  empty once both devices have runs.
Each of those outcomes is reachable from the same code path; none is forced.
"""
import csv, os, sys, json, hashlib, collections

RESULTS = os.environ.get("HAKUX_RESULTS", "/home/justin/hakux-work/dispatch/results")
APK = "b0cba34acef7"          # the one binary all of #50's full-disc work used
SUITE = "Blend_tests"


def runs_for(apk):
    """Every scored run on disk built from `apk`, one record per scoresN.tsv.

    A request with --runs N produces N runs under ONE result directory, all on
    one device with one scorer -- so the run, not the request, is the unit.
    """
    out = []
    for d in sorted(os.listdir(RESULTS)):
        rdir = os.path.join(RESULTS, d)
        rj = os.path.join(rdir, "result.json")
        if not os.path.exists(rj):
            continue
        try:
            meta = json.load(open(rj))
        except Exception:
            continue
        if meta.get("apk_sha") != apk:
            continue
        for n in range(1, 33):
            tsv = os.path.join(rdir, "scores%d.tsv" % n)
            if not os.path.exists(tsv):
                continue
            rows = {}
            with open(tsv) as f:
                for r in csv.DictReader(f, delimiter="\t"):
                    if r["suite"] != SUITE:
                        continue
                    rows[r["test"]] = r
            if not rows:
                continue
            out.append(dict(
                rdir=rdir,
                name="%s#%d" % (meta.get("requester") or d, n),
                device=meta.get("device_label") or "?",
                serial=meta.get("device_serial") or "?",
                scorer=meta.get("scorer_rev") or "(absent)",
                disc_id=meta.get("disc_id"),
                capdir=os.path.join(rdir, "captures%d" % n),
                rows=rows,
                keys=frozenset(rows),
            ))
    return out


def capture_hash(run, test):
    p = os.path.join(run["capdir"], "%s::%s.png" % (SUITE, test))
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def classify(runs, keys):
    """Split every capture that ever moved into RACE / DEVICE / (stable).

    RACE needs one device to disagree with itself.  Nothing else does, and in
    particular a disagreement BETWEEN devices does not, which is the whole
    correction this function exists to make.

    CLASSIFIED ON THE CAPTURE BYTES, DISPLAYED WITH THE COUNTS.  The
    `differing` column is produced by score_sweep.py, and `scorer_rev` is NOT
    constant across the runs on disk -- the three original full-disc runs
    carry (absent), 4a6a98dce4 and 027fa3d552.  Classifying on that column
    would make a scorer change look like a device difference or a race, which
    is this file's own error class one level down.  The PNG is what the
    device produced and no scorer touches it, so the split is taken there.

    The counts are still printed, because they are the numbers #50 is written
    in and a reader has to be able to check one against the other.  Where the
    two instruments disagree the row is flagged rather than silently resolved.
    """
    race, device, stable, mismatch = [], [], [], []
    for t in sorted(keys):
        per_dev = collections.OrderedDict()      # device -> [count, ...]
        hash_dev = collections.OrderedDict()     # device -> [hash, ...]
        for r in runs:
            per_dev.setdefault(r["device"], []).append(int(r["rows"][t]["differing"]))
            hash_dev.setdefault(r["device"], []).append(capture_hash(r, t))
        # if any capture is missing from disk, fall back to the count for that
        # capture and say so rather than dropping it
        have_all = all(h is not None for v in hash_dev.values() for h in v)
        basis = hash_dev if have_all else per_dev
        within = {d: set(v) for d, v in basis.items()}
        allv = set()
        for v in basis.values():
            allv |= set(v)
        if have_all:
            moved_count = len(set(x for v in per_dev.values() for x in v)) > 1
            moved_hash = len(allv) > 1
            if moved_count != moved_hash:
                mismatch.append((t, moved_count, moved_hash))
        rec = (t, per_dev, hash_dev, have_all)
        if any(len(v) > 1 for v in within.values()):
            race.append(rec)
        elif len(allv) > 1:
            device.append(rec)
        else:
            stable.append(t)
    return race, device, stable, mismatch


def show(title, items, runs):
    print()
    print("=== %s: %d" % (title, len(items)))
    for t, per_dev, hash_dev, have_all in items:
        print("  %-24s%s" % (t, "" if have_all else "   (no PNGs; counts only)"))
        for dev, vals in per_dev.items():
            hv = hash_dev.get(dev) or []
            basis = hv if have_all else vals
            flag = "  <-- disagrees with itself" if len(set(basis)) > 1 else ""
            print("      %-6s counts %s%s" % (dev, vals, flag))
            if have_all:
                print("      %-6s bytes  %s" % ("", [h[:8] for h in hv]))


def main():
    runs = runs_for(APK)
    if not runs:
        print("no runs on disk for apk %s" % APK)
        return 2

    # COMPOSITION FIRST.  Group by the capture set actually scored, because
    # disc_id cannot be trusted to differ on these artefacts (see the header).
    bycomp = collections.OrderedDict()
    for r in runs:
        bycomp.setdefault(r["keys"], []).append(r)

    print("=== COMPOSITIONS ON DISK for apk %s, suite %s" % (APK, SUITE))
    print("(grouped by the capture SET scored, not by disc_id -- the narrowed")
    print(" discs carry the full disc's disc_id, see this file's header)")
    for keys, rs in sorted(bycomp.items(), key=lambda kv: -len(kv[0])):
        ids = sorted(set(r["disc_id"] for r in rs))
        print("  %5d captures  %2d run(s)  devices=%s  disc_id=%s"
              % (len(keys), len(rs),
                 sorted(set(r["device"] for r in rs)), ids))

    full = max(bycomp, key=len)
    fruns = bycomp[full]
    print()
    print("=== THE FULL DISC: %d captures, %d runs" % (len(full), len(fruns)))
    for r in fruns:
        print("  %-34s device=%-5s serial=%-9s scorer=%s"
              % (r["name"], r["device"], r["serial"], r["scorer"]))
    devs = collections.Counter(r["device"] for r in fruns)
    print("  runs per device: %s" % dict(devs))
    if len(devs) > 1 and min(devs.values()) < 2:
        print("  WARNING: a device with a single run cannot disagree with itself,")
        print("  so nothing it alone shows can be called a race. That is exactly")
        print("  how 'instability is RUN-SCOPED' was read off one nova run.")

    scorers = sorted(set(r["scorer"] for r in fruns))
    if len(scorers) > 1:
        print("  scorer_rev is NOT constant across these runs: %s" % scorers)
        print("  -> the split below is taken on the capture BYTES, which no")
        print("     scorer touches; the counts are printed alongside to check.")

    race, device, stable, mismatch = classify(fruns, full)
    print()
    print("  moved at all: %d of %d   (race %d, device-only %d, stable %d)"
          % (len(race) + len(device), len(full), len(race), len(device), len(stable)))
    if mismatch:
        print("  INSTRUMENTS DISAGREE on %d capture(s): %s"
              % (len(mismatch), [m[0] for m in mismatch[:10]]))
        print("  (capture, count-says-moved, bytes-say-moved) -- trust the bytes")
        for m in mismatch[:10]:
            print("     %-24s count=%s bytes=%s" % m)

    show("RACE -- one device disagrees with ITSELF, same binary, same disc",
         race, fruns)
    show("DEVICE ONLY -- each device internally constant, devices differ",
         device, fruns)

    # CROSS-CHECK: capture bytes vs the score column, on the movers plus a
    # sample of the "stable" set.  A capture the count calls stable and the
    # bytes call unstable is the failure mode the count cannot see.
    movers = [r[0] for r in race] + [r[0] for r in device]
    print()
    print("=== INSTRUMENT CROSS-CHECK (sha256 of the capture PNG)")
    missing = 0
    byte_unstable = []
    for t in sorted(full):
        hs = [capture_hash(r, t) for r in fruns]
        if any(h is None for h in hs):
            missing += 1
            continue
        if len(set(hs)) > 1:
            byte_unstable.append(t)
    print("  captures whose BYTES differ across the full-disc runs: %d"
          % len(byte_unstable))
    print("  captures whose COUNT differs across the full-disc runs: %d"
          % len(movers))
    disagree = set(byte_unstable) ^ set(movers)
    if disagree:
        print("  INSTRUMENTS DISAGREE on: %s" % sorted(disagree))
        print("  A count-stable, byte-unstable capture is a real move the")
        print("  differing column cannot see. Trust the bytes.")
    else:
        print("  the two instruments name the same set -- the count hid nothing here")
    if missing:
        print("  (%d captures had no PNG on disk in some run; not compared)" % missing)

    # THE OTHER COMPOSITIONS, for the movers only, printed SEPARATELY and
    # never pooled: this is the between-composition axis, and mixing it into
    # the run-to-run one is the withdrawn 7.7%.
    print()
    print("=== THE SAME CAPTURES ON NARROWED DISCS (a different composition --")
    print("    these values are NOT poolable with the full-disc ones above)")
    for keys, rs in sorted(bycomp.items(), key=lambda kv: -len(kv[0])):
        if keys is full:
            continue
        print("  -- %d-capture disc, %d runs, devices=%s"
              % (len(keys), len(rs), sorted(set(r["device"] for r in rs))))
        for t in sorted(set(movers) & set(keys)):
            per_dev = collections.OrderedDict()
            for r in rs:
                per_dev.setdefault(r["device"], []).append(int(r["rows"][t]["differing"]))
            for dev, vals in per_dev.items():
                fullvals = collections.OrderedDict()
                for r in fruns:
                    fullvals.setdefault(r["device"], []).append(int(r["rows"][t]["differing"]))
                same = fullvals.get(dev)
                note = ""
                if same is not None:
                    # A COMPOSITION EFFECT NEEDS THE TWO SETS TO BE DISJOINT.
                    # Merely "not equal" is not enough: a racing capture reads
                    # {98304, 76032} on the full disc and 76032 when narrowed,
                    # which is unequal but is just the race not firing -- the
                    # narrowed value is one the full disc also produces. Only
                    # a value the full disc NEVER produces on this device is
                    # evidence that narrowing changed the result.
                    if set(vals).isdisjoint(same):
                        note = ("   <-- COMPOSITION: %s never reads any of %s "
                                "on the full disc (reads %s)" % (dev, sorted(set(vals)), same))
                    elif set(vals) != set(same):
                        note = ("   (within the full disc's %s for %s -- overlapping, "
                                "so no composition effect shown)" % (same, dev))
                print("     %-24s %-6s %s%s" % (t, dev, vals, note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
