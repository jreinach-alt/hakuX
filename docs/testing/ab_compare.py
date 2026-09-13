#!/usr/bin/env python3
"""Compare two dispatcher result directories per capture, and judge the result
against a prediction that was written down first.

    ab_compare.py --a RESULTDIR --b RESULTDIR [--expect expect.json]
    ab_compare.py --register expect.json --a-ref SHA --b-ref SHA \
                  --must-not-move 'Blend_surface/*' --expect-value K=V ...

Every A/B on 2026-09-12 was hand-rolled and every one of them had the same
shape: queue two arms differing only in ``--ref``, then read two TSVs side by
side. This is that reading, done once and correctly, because the hand version
got four things wrong that a script cannot.

**Better/worse per capture, never totals.** The #48 blend A/B came back
-271,760 differing pixels overall, which reads as an unambiguous win. Per
capture it was 10 better, 2 worse, and one of the two worse was
``Blend_surface/DstAlpha_ARGB8`` going from bit-exact to 98,304 differing
pixels -- a capture that had been perfect and no longer was, hidden inside a
six-figure improvement. So the total is printed last, labelled advisory, and
the per-capture table is the answer.

**An arm without progress-log proof is absent, not zero.** The depth A/B on
2026-09-12 had one arm report 704 captures against the other's 1042. Averaging
those, or subtracting them, produces a number; it does not produce a
measurement. ``progress_log_proof`` false is a refusal here, and so is a
per-suite capture count that disagrees between the arms, which is the same
failure one level down: a suite that half-ran looks like a suite that improved.

**A delta inside the run-to-run band is a coin flip.** Ten runs of one
unchanged binary over ``Texture border`` (dispatch result
``1789255594-exp54-stst-correct``) give band 0 on 17 of 18 captures -- the
device is bit-reproducible almost everywhere -- and on ``2D_BorderTex_SZ``
alone give 0, 0, 0, 0, 0, 146, 181, 1847, 2352, 2430, 5640: five runs
bit-exact and five not, on the same APK. A single-run A/B on that capture has
about an even chance of showing "exact -> 5,640" or "5,640 -> exact" with
nothing whatever having changed. So with ``--runs N`` in both arms the band is
*measured* rather than assumed, and any delta no larger than the band is
classed NOISE instead of better or worse. Note the band is per capture, not
per suite: flagging the whole of ``Texture border`` as unreliable would
suppress 17 trustworthy captures to catch one.

**A prediction written after the measurement is not a prediction.** Two fixes
were rejected on 2026-09-12 because a capture on their own must-not-move list
moved, which only worked because the list existed first. ``--register`` writes
the expectations file, stamps it, and names the two refs; the comparison then
refuses an expectations file that names other refs, and reports it as
POST-HOC if the file is newer than the results it judges. The honour system
does not survive a long day.

What it deliberately does not do: it does not read PNGs, it does not score,
and it does not decide whether a mixed result should land. It says what moved.

Exit status: 0 pass, 1 fail (a prediction was violated, or a capture regressed
with no prediction on file), 2 refused (the arms are not comparable).
"""

import argparse
import csv
import datetime
import fnmatch
import glob
import hashlib
import json
import os
import statistics
import subprocess
import sys

# Captures known to move between runs of one binary. This list is a warning of
# last resort, for --runs 1 where there is no band to measure; with repeated
# runs the measured band is always preferred, because it is evidence and this
# is hearsay. 2D_BorderTex_SZ is measured above. The DotSTR3D_* family moved by
# up to 42,554 px between runs of a single binary before its undefined
# behaviour was fixed, which is why the family is listed and not just the one
# test: the instability was in shared code.
KNOWN_UNSTABLE = (
    "Texture_border/2D_BorderTex_SZ",
    "*/DotSTR3D_*",
)

TREE = os.environ.get("DISPATCH_TREE", "/home/justin/hakuX")


def die(msg, code=2):
    print("REFUSED: " + msg)
    sys.exit(code)


# --------------------------------------------------------------------------
# loading an arm


class Arm:
    """One dispatcher result directory, with its runs parsed per capture."""

    def __init__(self, path, name):
        self.path = os.path.abspath(path)
        self.name = name
        self.label = os.path.basename(self.path.rstrip("/"))
        mpath = os.path.join(self.path, "result.json")
        if not os.path.isdir(self.path):
            die("%s: no such directory %s" % (name, self.path))
        if os.path.exists(os.path.join(self.path, "ERROR")):
            err = open(os.path.join(self.path, "ERROR"),
                       errors="replace").read().strip()
            die("%s (%s) failed on the device: %s" % (name, self.label, err))
        if not os.path.exists(os.path.join(self.path, "DONE")):
            die("%s (%s) has no DONE marker: the run never finished, so its "
                "TSV is whatever had been written when it stopped"
                % (name, self.label))
        if not os.path.exists(mpath):
            die("%s (%s) has no result.json" % (name, self.label))
        self.meta = json.load(open(mpath))
        self.meta_mtime = os.path.getmtime(mpath)
        self.runs = self.meta.get("runs") or []

        # The request as it was queued. request.sh binds the prediction file
        # to the request by content hash at queue time, which is the only
        # moment at which "this was predicted in advance" is checkable.
        self.request = {}
        rpath = os.path.join(self.path, "request.json")
        if os.path.exists(rpath):
            try:
                self.request = json.load(open(rpath))
            except Exception:
                self.request = {}

        # Rows, per run, keyed by capture. The dispatcher's own run list is the
        # authority on which TSVs count: a directory can hold a rescored TSV
        # that result.json does not list.
        self.per_run = []
        for r in self.runs:
            tsv = os.path.join(self.path, r["tsv"])
            if not os.path.exists(tsv):
                die("%s (%s) lists %s in result.json but the file is missing"
                    % (name, self.label, r["tsv"]))
            rows = {}
            with open(tsv) as f:
                for row in csv.DictReader(f, delimiter="\t"):
                    if not row.get("suite"):
                        continue
                    k = (row["suite"], row["test"])
                    if k in rows:
                        die("%s (%s) %s has two rows for %s/%s; a rescored "
                            "TSV cannot be compared without knowing which "
                            "scoring is meant" % (name, self.label, r["tsv"],
                                                  k[0], k[1]))
                    rows[k] = row
            self.per_run.append(rows)

    # -- identity -----------------------------------------------------------
    @property
    def ref(self):
        return self.meta.get("ref", "")

    @property
    def apk(self):
        return self.meta.get("apk_sha", "")

    @property
    def disc(self):
        return self.meta.get("disc_id", "")

    @property
    def classifier(self):
        return self.meta.get("classifier_rev", "")

    def captures(self):
        keys = set()
        for rows in self.per_run:
            keys |= set(rows)
        return keys

    def values(self, key, col="differing"):
        """The per-run value of one column for one capture."""
        out = []
        for rows in self.per_run:
            row = rows.get(key)
            if row is not None:
                out.append(int(row[col] or 0))
        return out

    def statuses(self, key):
        return [rows[key]["status"] for rows in self.per_run if key in rows]

    def suite_counts(self):
        """Captures per suite, from run 1 -- the run the dispatcher itself
        uses for captures_vs_goldens."""
        counts = {}
        if self.per_run:
            for suite, _ in self.per_run[0]:
                counts[suite] = counts.get(suite, 0) + 1
        return counts

    def describe(self):
        proof = ["yes" if r.get("progress_log_proof") else "NO"
                 for r in self.runs]
        return [
            "%s (%s)  %s" % (self.name, "baseline" if self.name == "A"
                             else "candidate", self.label),
            "    ref %-12s apk %-14s classifier %s"
            % (self.ref or "?", self.apk or "?", self.classifier or "?"),
            "    %d run(s), %s captures, progress-log proof %s"
            % (len(self.runs),
               "/".join(str(r.get("captures", "?")) for r in self.runs),
               "/".join(proof)),
        ]


# --------------------------------------------------------------------------
# comparability: the refusals


def git_commit_epoch(ref):
    """Author epoch of a ref in the dispatch tree, or None."""
    if not ref:
        return None
    try:
        out = subprocess.run(["git", "-C", TREE, "show", "-s", "--format=%ct",
                              ref], capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    try:
        return int(out.stdout.strip())
    except ValueError:
        return None


def check_comparable(a, b, allow_same_binary=False):
    """Refuse the comparisons that are invalid, and say which. Returns the
    list of non-fatal warnings."""
    warn = []

    # 1. Proof. An arm whose log does not show the tests completing is absent,
    #    not zero: a truncated run leaves the previous image in place and reads
    #    as a pass, and file mtimes do not substitute.
    for arm in (a, b):
        if not arm.runs:
            die("%s (%s) records no runs at all -- a soak or perf request has "
                "no scores to compare. This tool compares oracle runs."
                % (arm.name, arm.label))
        bad = [i + 1 for i, r in enumerate(arm.runs)
               if not r.get("progress_log_proof")]
        if bad:
            die("%s (%s) run(s) %s have progress_log_proof false. An arm "
                "without proof is ABSENT, not zero: on 2026-09-12 two such "
                "arms reported 704 captures against the other arm's 1042. "
                "Requeue the arm; do not average it in."
                % (arm.name, arm.label, ",".join(map(str, bad))))

    # 2. Disc identity. Comparing a shared-disc number against a per-suite
    #    number reverted a working fix.
    if a.disc != b.disc:
        die("disc_id differs, so the two numbers are not of the same "
            "experiment:\n    A %s\n    B %s\nRequeue both arms with the "
            "same --suites." % (a.disc or "(none)", b.disc or "(none)"))

    # 3. Per-suite capture counts. Same failure as (1) one level down: a suite
    #    that half-ran looks like a suite that improved.
    ca, cb = a.suite_counts(), b.suite_counts()
    if ca != cb:
        lines = []
        for s in sorted(set(ca) | set(cb)):
            if ca.get(s, 0) != cb.get(s, 0):
                lines.append("    %-34s A %4d   B %4d"
                             % (s, ca.get(s, 0), cb.get(s, 0)))
        die("per-suite capture counts disagree, so the comparison is "
            "invalid:\n" + "\n".join(lines))

    # 4. Capture identity. Equal counts can still be different captures.
    ka, kb = a.captures(), b.captures()
    if ka != kb:
        only_a = sorted(ka - kb)[:6]
        only_b = sorted(kb - ka)[:6]
        die("the arms scored different captures despite matching counts:\n"
            "    only in A: %s\n    only in B: %s"
            % (", ".join("%s/%s" % k for k in only_a) or "-",
               ", ".join("%s/%s" % k for k in only_b) or "-"))

    # 5. One binary measured twice. The dispatcher caches builds by sha, so two
    #    refs that resolve to one sha silently produce one APK in both arms --
    #    and the worst outcome available here is measuring one binary twice and
    #    reporting the difference as a fix.
    if a.apk and a.apk == b.apk:
        msg = ("both arms ran APK %s, so there is no independent variable. "
               "Either the two refs resolve to the same commit, or the build "
               "cache served one binary twice." % a.apk)
        if allow_same_binary:
            warn.append("SAME BINARY: " + msg + " Continuing on "
                        "--allow-same-binary: any delta below is device "
                        "noise, which is the only thing it can be.")
        else:
            die(msg + "\nPass --allow-same-binary if the point is to measure "
                "the noise floor.")
    if a.ref and a.ref == b.ref:
        warn.append("both arms name ref %s; the arms differ only by build or "
                    "by run." % a.ref)

    # 6. A result cannot predate the commit it claims to be of.
    for arm in (a, b):
        epoch = git_commit_epoch(arm.ref)
        if epoch and arm.meta_mtime + 60 < epoch:
            die("%s (%s) is dated %s but its ref %s was committed %s. The "
                "result cannot be of that commit, so it is mislabelled or the "
                "directory was reused."
                % (arm.name, arm.label,
                   datetime.datetime.fromtimestamp(arm.meta_mtime)
                   .strftime("%Y-%m-%d %H:%M"), arm.ref,
                   datetime.datetime.fromtimestamp(epoch)
                   .strftime("%Y-%m-%d %H:%M")))

    # -- warnings ----------------------------------------------------------
    if a.classifier != b.classifier:
        warn.append("classifier_rev differs (A %s, B %s); the boundary-shift "
                    "class exists only from d0114a49, so residual splits "
                    "computed either side are not the same quantity."
                    % (a.classifier, b.classifier))
    if len(a.runs) != len(b.runs):
        warn.append("run counts differ (A %d, B %d); the noise band is taken "
                    "from whichever arm has repeats, which is weaker than a "
                    "band from both." % (len(a.runs), len(b.runs)))
    for arm in (a, b):
        part = [(s, c) for s, c in (arm.meta.get("captures_vs_goldens") or {})
                .items() if c.get("partial")]
        for s, c in sorted(part):
            warn.append("%s: %s scored %d of %d goldens -- that suite's "
                        "numbers are a FLOOR, not a score."
                        % (arm.name, s, c["scored"], c["goldens"]))
    return warn


# --------------------------------------------------------------------------
# the comparison itself


def band(vals):
    return (max(vals) - min(vals)) if len(vals) > 1 else 0


def point(vals):
    """The value to compare on. Median, not mean: on a capture that is exact
    in half its runs the mean is a figure that never actually occurred."""
    return int(statistics.median(vals)) if vals else 0


def unstable_by_name(key):
    name = "%s/%s" % key
    return any(fnmatch.fnmatch(name, pat) for pat in KNOWN_UNSTABLE)


def compare(a, b):
    rows = []
    for key in sorted(a.captures() & b.captures()):
        va, vb = a.values(key), b.values(key)
        pa, pb = point(va), point(vb)
        oa = point(a.values(key, "off_by_one"))
        ob = point(b.values(key, "off_by_one"))
        bnd = max(band(va), band(vb))
        delta = pb - pa
        if delta == 0:
            cls = "same"
        elif abs(delta) <= bnd:
            cls = "noise"
        else:
            cls = "better" if delta < 0 else "worse"
        rows.append(dict(
            key=key, suite=key[0], test=key[1],
            a=pa, b=pb, delta=delta, band=bnd,
            a_runs=va, b_runs=vb,
            a_struct=pa - oa, b_struct=pb - ob,
            cls=cls,
            from_exact=(pa == 0 and pb > 0),
            to_exact=(pa > 0 and pb == 0),
            status_a=(a.statuses(key) or [""])[0],
            status_b=(b.statuses(key) or [""])[0],
            unstable=unstable_by_name(key),
        ))
    return rows


# --------------------------------------------------------------------------
# expectations


def load_expect(path, a, b):
    exp = json.load(open(path))
    notes = []
    for k, want in (("a_ref", a.ref), ("b_ref", b.ref)):
        have = exp.get(k)
        if have and want and not (have.startswith(want)
                                  or want.startswith(have)):
            die("expectations file names %s %s but arm %s ran %s. A "
                "prediction registered for other refs is not a prediction "
                "about this measurement." % (k, have, k[0].upper(), want))
    # Preferred evidence: the sha request.sh recorded when the device work was
    # asked for. It settles both questions an mtime can only guess at -- was
    # the prediction on file before the run, and is it still the same
    # prediction. A file written on time and then widened once the numbers
    # arrived has a good mtime and a different sha.
    bound = None
    for arm in (b, a):
        want = (arm.request or {}).get("expect_sha") or ""
        named = (arm.request or {}).get("expect") or ""
        if want and named and os.path.basename(named) == os.path.basename(path):
            bound = (arm, named, want)
            break
    if bound is not None:
        arm, named, want = bound
        try:
            got = hashlib.sha256(open(path, "rb").read()).hexdigest()
        except OSError:
            got = ""
        if got == want:
            notes.append("PRE-REGISTERED: arm %s was queued at %s naming this "
                         "file, and its content still hashes to the sha "
                         "recorded then (%s). The prediction existed before "
                         "the device ran and has not been edited since."
                         % (arm.name.upper(),
                            (arm.request or {}).get("queued_utc", "?"),
                            want[:12]))
            return exp, notes
        notes.append("TAMPERED: arm %s was queued naming this file with sha "
                     "%s, but it now hashes to %s. The prediction has been "
                     "edited since the device work was asked for, so the "
                     "verdict below is worth nothing. Recover the queued "
                     "version, or re-register and re-run."
                     % (arm.name.upper(), want[:12], (got or "unreadable")[:12]))
        return exp, notes

    reason = (b.request or {}).get("no_expect") or (a.request or {}).get("no_expect")
    newest = max(a.meta_mtime, b.meta_mtime)
    try:
        when = os.path.getmtime(path)
    except OSError:
        when = None
    if when is not None and when > newest + 5:
        extra = ""
        if reason:
            extra = (" The arm was queued with --no-expect %r, so no "
                     "prediction was ever bound to it." % reason)
        notes.append("POST-HOC: %s was last written %s, after the newer arm's "
                     "result at %s. A prediction written after the "
                     "measurement is a description of it, and the verdict "
                     "below is worth nothing.%s"
                     % (os.path.basename(path),
                        datetime.datetime.fromtimestamp(when)
                        .strftime("%Y-%m-%d %H:%M"),
                        datetime.datetime.fromtimestamp(newest)
                        .strftime("%Y-%m-%d %H:%M"), extra))
    elif when is not None:
        notes.append("UNBOUND: %s predates both results, so it was not written "
                     "to fit them -- but no arm was queued naming it, so "
                     "nothing proves it is the prediction that was made. "
                     "Queue the next arm with request.sh --expect."
                     % os.path.basename(path))
    return exp, notes


def judge(exp, rows):
    """Check the prediction. Returns (failures, checks_made)."""
    fails = []
    checks = 0
    by_name = {"%s/%s" % r["key"]: r for r in rows}

    for pat in exp.get("must_not_move") or []:
        hit = [n for n in by_name if fnmatch.fnmatch(n, pat)]
        if not hit:
            fails.append("must_not_move %r matched no capture in either arm; "
                         "the guard was never actually applied" % pat)
            continue
        checks += len(hit)
        for n in sorted(hit):
            r = by_name[n]
            if r["cls"] in ("better", "worse"):
                fails.append("must not move, but moved: %-46s %9d -> %9d "
                             "(%s)" % (n, r["a"], r["b"], r["cls"]))

    for name, want in (exp.get("expect") or {}).items():
        hit = [n for n in by_name if fnmatch.fnmatch(n, name)]
        if not hit:
            fails.append("expect %r matched no capture" % name)
            continue
        for n in sorted(hit):
            checks += 1
            got = by_name[n]["b"]
            if got != int(want):
                fails.append("predicted %-46s = %d, measured %d"
                             % (n, int(want), got))

    counts = exp.get("expect_counts") or {}
    if counts:
        tally = {c: sum(1 for r in rows if r["cls"] == c)
                 for c in ("better", "worse", "same", "noise")}
        for k, want in counts.items():
            checks += 1
            if tally.get(k) != int(want):
                fails.append("predicted %s = %s, measured %s"
                             % (k, want, tally.get(k)))
    return fails, checks


def register(args):
    path = args.register
    if os.path.exists(path) and not args.force:
        die("%s already exists. Rewriting a registered prediction defeats "
            "the point of registering it; pass --force only to fix a typo "
            "before the arms have run." % path, 2)
    exp = {
        "registered_utc": datetime.datetime.now(datetime.timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "who": args.who or "",
        "issue": args.issue or "",
        "prediction": args.prediction or "",
        "a_ref": args.a_ref or "",
        "b_ref": args.b_ref or "",
        "must_not_move": list(args.must_not_move or []),
        "expect": {},
        "expect_counts": {},
    }
    for kv in args.expect_value or []:
        if "=" not in kv:
            die("--expect-value wants CAPTURE=PIXELS, got %r" % kv, 2)
        k, v = kv.rsplit("=", 1)
        exp["expect"][k.strip()] = int(v.replace(",", "").strip())
    for kv in args.expect_count or []:
        if "=" not in kv:
            die("--expect-count wants CLASS=N, got %r" % kv, 2)
        k, v = kv.rsplit("=", 1)
        if k.strip() not in ("better", "worse", "same", "noise"):
            die("--expect-count class must be better|worse|same|noise", 2)
        exp["expect_counts"][k.strip()] = int(v.strip())
    if not (exp["must_not_move"] or exp["expect"] or exp["expect_counts"]):
        die("a registration with nothing falsifiable in it is not a "
            "prediction. Give at least one --must-not-move, --expect-value "
            "or --expect-count.", 2)
    with open(path, "w") as f:
        json.dump(exp, f, indent=2)
        f.write("\n")
    print("registered %s" % path)
    print(json.dumps(exp, indent=2))
    print("\nCommit this file BEFORE the arms land, so its date is evidence.")
    return 0


# --------------------------------------------------------------------------
# reporting


def fmt(n):
    return format(n, ",")


def signed(n):
    return ("%+d" % n if abs(n) < 1000 else
            ("+" if n > 0 else "-") + fmt(abs(n)))


def report(a, b, rows, warn, exp, exp_notes, args):
    out = []
    out.append("=" * 78)
    out.append("A/B comparison, per capture")
    out.append("=" * 78)
    out += a.describe()
    out += b.describe()
    out.append("disc  %s" % (a.disc or "(none)"))
    out.append("      identical in both arms, so the arms are comparable")
    if warn:
        out.append("")
        for w in warn:
            out.append("WARNING: " + w)

    movers = [r for r in rows if r["cls"] in ("better", "worse")]
    noisy = [r for r in rows if r["cls"] == "noise"]
    tally = {c: sum(1 for r in rows if r["cls"] == c)
             for c in ("better", "worse", "same", "noise")}

    out.append("")
    out.append("-" * 78)
    out.append("movers")
    out.append("-" * 78)
    if not movers:
        out.append("  none: no capture moved outside its measured band.")
    for r in sorted(movers, key=lambda r: (r["cls"] != "worse", r["suite"],
                                           r["test"])):
        mark = ""
        if r["from_exact"]:
            mark = "  <<< WAS EXACT"
        elif r["to_exact"]:
            mark = "  <<< now exact"
        if r["status_a"] != r["status_b"]:
            mark += "  [status %s -> %s]" % (r["status_a"], r["status_b"])
        if r["unstable"] and r["band"] == 0:
            mark += "  [known unstable, unmeasured band]"

        out.append("  %-6s %-24s %-30s %9s -> %9s  %+10s%s"
                   % (r["cls"], r["suite"], r["test"][:30], fmt(r["a"]),
                      fmt(r["b"]), signed(r["delta"]), mark))
    if noisy:
        out.append("")
        out.append("  inside the measured run-to-run band, so not a result:")
        for r in sorted(noisy, key=lambda r: -abs(r["delta"])):
            out.append("  noise  %-24s %-30s %9s -> %9s  band %s"
                       % (r["suite"], r["test"][:30], fmt(r["a"]),
                          fmt(r["b"]), fmt(r["band"])))

    out.append("")
    out.append("-" * 78)
    out.append("counts, per capture -- the only valid unit")
    out.append("-" * 78)
    out.append("  better %-5d worse %-5d same %-5d noise %-5d   (%d compared)"
               % (tally["better"], tally["worse"], tally["same"],
                  tally["noise"], len(rows)))
    ea = sum(1 for r in rows if r["a"] == 0)
    eb = sum(1 for r in rows if r["b"] == 0)
    # Crossing zero only counts as a regression if the capture moved outside
    # its band. Five of ten runs of one unchanged binary have
    # Texture_border/2D_BorderTex_SZ bit-exact and five do not, so on that
    # capture "was exact, now 1,847" is the coin landing the other way up. An
    # earlier draft of this counted the flicker as a regression and returned
    # FAIL for a comparison of one binary against itself.
    reg = [r for r in rows if r["from_exact"] and r["cls"] == "worse"]
    rep = [r for r in rows if r["to_exact"] and r["cls"] == "better"]
    flicker = [r for r in rows
               if r["cls"] == "noise" and (r["from_exact"] or r["to_exact"])]
    out.append("  exact  %-5d ->    %-5d  (%+d)%s"
               % (ea, eb, eb - ea,
                  "   of which %d is flicker inside the band" % len(flicker)
                  if flicker else ""))
    out.append("  regressed from exact %-3d      repaired to exact %-3d"
               % (len(reg), len(rep)))
    if reg:
        out.append("  REGRESSED FROM EXACT: " +
                   ", ".join("%s/%s" % r["key"] for r in reg))
    if flicker:
        out.append("  flickered across exact, inside the measured band "
                   "(not a result): " +
                   ", ".join("%s/%s" % r["key"] for r in flicker))

    out.append("")
    out.append("-" * 78)
    out.append("per suite")
    out.append("-" * 78)
    out.append("  %-26s %5s %6s %5s %5s %5s %12s %12s"
               % ("suite", "caps", "better", "worse", "same", "noise",
                  "differing A", "differing B"))
    suites = sorted({r["suite"] for r in rows})
    for s in suites:
        sr = [r for r in rows if r["suite"] == s]
        out.append("  %-26s %5d %6d %5d %5d %5d %12s %12s"
                   % (s, len(sr),
                      sum(1 for r in sr if r["cls"] == "better"),
                      sum(1 for r in sr if r["cls"] == "worse"),
                      sum(1 for r in sr if r["cls"] == "same"),
                      sum(1 for r in sr if r["cls"] == "noise"),
                      fmt(sum(r["a"] for r in sr)),
                      fmt(sum(r["b"] for r in sr))))

    ta = sum(r["a"] for r in rows)
    tb = sum(r["b"] for r in rows)
    sa = sum(r["a_struct"] for r in rows)
    sb = sum(r["b_struct"] for r in rows)
    out.append("")
    out.append("-" * 78)
    out.append("totals -- ADVISORY ONLY: a total can hide a regression")
    out.append("-" * 78)
    out.append("  differing  %14s -> %14s  (%s)" % (fmt(ta), fmt(tb),
                                                    signed(tb - ta)))
    out.append("  structural %14s -> %14s  (%s)" % (fmt(sa), fmt(sb),
                                                    signed(sb - sa)))
    out.append("  structural is differing minus off-by-one; the two never "
               "overlap, so the subtraction is safe.")

    # -- verdict -----------------------------------------------------------
    out.append("")
    out.append("=" * 78)
    rc = 0
    if exp is None:
        # A capture on the known-unstable list, measured once, has no band and
        # so cannot be told from a coin flip. It is reported as a mover but it
        # does not on its own condemn the arm: requeue with --runs 3.
        hard = [r for r in movers
                if not (r["unstable"] and r["band"] == 0)]
        soft = [r for r in movers if r["unstable"] and r["band"] == 0]
        hard_worse = [r for r in hard if r["cls"] == "worse"]
        if hard_worse or reg:
            out.append("VERDICT: FAIL -- %d capture(s) worse, %d regressed "
                       "from exact, and no prediction on file."
                       % (len(hard_worse), len(reg)))
            rc = 1
        elif soft:
            out.append("VERDICT: UNJUDGED -- the only movers are on the "
                       "known-unstable list and were measured once, so there "
                       "is no band to test them against: %s. Requeue both "
                       "arms with --runs 3."
                       % ", ".join("%s/%s" % r["key"] for r in soft))
        else:
            out.append("VERDICT: UNJUDGED -- nothing got worse, but no "
                       "prediction was registered, so this measurement "
                       "confirms nothing. Register one with --register "
                       "before the next arm.")
            rc = 0
    else:
        for n in exp_notes:
            out.append(n)
        fails, checks = judge(exp, rows)
        if exp.get("prediction"):
            out.append("prediction (registered %s): %s"
                       % (exp.get("registered_utc", "?"), exp["prediction"]))
        if fails:
            out.append("VERDICT: FAIL -- %d of %d checks violated:"
                       % (len(fails), checks))
            for f in fails:
                out.append("    " + f)
            rc = 1
        else:
            out.append("VERDICT: PASS -- all %d registered checks hold."
                       % checks)
            if tally["worse"] or reg:
                out.append("    Note: %d capture(s) worse and %d regressed "
                           "from exact. The prediction allowed for them; the "
                           "regressions are still real."
                           % (tally["worse"], len(reg)))
        if exp_notes:
            rc = 1
    out.append("=" * 78)

    text = "\n".join(out)
    print(text)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(dict(
                a=dict(dir=a.label, ref=a.ref, apk=a.apk, disc=a.disc,
                       runs=len(a.runs)),
                b=dict(dir=b.label, ref=b.ref, apk=b.apk, disc=b.disc,
                       runs=len(b.runs)),
                counts=tally, exact_a=ea, exact_b=eb,
                regressed_from_exact=["%s/%s" % r["key"] for r in reg],
                repaired_to_exact=["%s/%s" % r["key"] for r in rep],
                totals=dict(differing_a=ta, differing_b=tb,
                            structural_a=sa, structural_b=sb),
                warnings=warn, post_hoc=exp_notes, verdict=rc,
                movers=[{k: v for k, v in r.items() if k != "key"}
                        for r in movers],
            ), f, indent=2)
            f.write("\n")
    return rc


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--a", help="baseline result directory")
    p.add_argument("--b", help="candidate result directory")
    p.add_argument("--probe", metavar="RESULTDIR",
                   help="print one capture's per-run values and band from a "
                        "single arm, and exit. This is the oracle a bisect "
                        "step reads; it lives here so that only one file "
                        "knows the TSV layout.")
    p.add_argument("--capture", metavar="SUITE/TEST",
                   help="with --probe, the capture to report")
    p.add_argument("--expect", help="registered expectations JSON")
    p.add_argument("--json", help="also write the comparison as JSON here")
    p.add_argument("--allow-same-binary", action="store_true",
                   help="permit both arms on one APK, to measure the noise "
                        "floor")
    p.add_argument("--register", metavar="FILE",
                   help="write an expectations file and exit")
    p.add_argument("--force", action="store_true",
                   help="with --register, overwrite an existing file")
    p.add_argument("--who"), p.add_argument("--issue")
    p.add_argument("--prediction", help="the prose prediction, for the record")
    p.add_argument("--a-ref"), p.add_argument("--b-ref")
    p.add_argument("--must-not-move", action="append", metavar="GLOB")
    p.add_argument("--expect-value", action="append", metavar="CAPTURE=PX")
    p.add_argument("--expect-count", action="append", metavar="CLASS=N")
    args = p.parse_args()

    if args.register:
        return register(args)
    if args.probe:
        if not args.capture or "/" not in args.capture:
            p.error("--probe needs --capture SUITE/TEST")
        arm = Arm(args.probe, "probe")
        bad = [i + 1 for i, r in enumerate(arm.runs)
               if not r.get("progress_log_proof")]
        if bad:
            die("%s run(s) %s have no progress-log proof; the arm is absent, "
                "not zero" % (arm.label, ",".join(map(str, bad))))
        suite, test = args.capture.split("/", 1)
        key = (suite, test)
        if key not in arm.captures():
            die("%s did not score %s. Its suites were: %s"
                % (arm.label, args.capture,
                   ", ".join(sorted({s for s, _ in arm.captures()}))))
        vals = arm.values(key)
        print("capture   %s" % args.capture)
        print("arm       %s  ref %s  apk %s" % (arm.label, arm.ref, arm.apk))
        print("runs      %s" % " ".join(str(v) for v in vals))
        print("median    %d" % point(vals))
        print("band      %d%s" % (band(vals),
                                  "   (one run: the band is UNMEASURED, not "
                                  "zero)" if len(vals) < 2 else ""))
        print("unstable  %s" % ("yes, by name" if unstable_by_name(key)
                                else "not on the known list"))
        return 0
    if not (args.a and args.b):
        p.error("need --a and --b (or --register)")

    a = Arm(args.a, "A")
    b = Arm(args.b, "B")
    warn = check_comparable(a, b, args.allow_same_binary)
    rows = compare(a, b)
    if not rows:
        die("the arms share no capture, so there is nothing to compare")
    exp = exp_notes = None
    if args.expect:
        exp, exp_notes = load_expect(args.expect, a, b)
    return report(a, b, rows, warn, exp, exp_notes or [], args)


if __name__ == "__main__":
    sys.exit(main())
