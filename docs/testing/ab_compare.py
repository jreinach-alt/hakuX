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

**`same` MEANS SAME SCORE, AND A SCORE IS NOT A PICTURE.** Every class here --
better, worse, same, noise -- is computed from the `differing` column, so
`same` has always meant "the two arms are the same distance from the golden",
never "the two arms drew the same thing". Those come apart, and it has cost
this campaign twice in the other direction each time:

  * #59's arm 3 (``1789359225-padwrite59-base-1009294`` ->
    ``1789360413-padwrite59only-fix-1396389``) read ``0 better, 0 worse,
    217 same`` with the totals identical to the pixel, and was reported as
    inert. It was not. ``Clear/SFC_X1R5G5B5_Z1R5G5B5`` moved on 49,104 px:
    the fix repaired the green channel exactly and the restored readback
    swizzle broke the same pixels in alpha, so the count held while the image
    changed. A flat A/B hid a working fix.
  * #75 went the other way -- a sweep column diffed by hand showed ~100,652 px
    on ``Stencil``, a suspect commit was named and a bisect lane spawned, and
    the whole delta was one column's run-to-run noise.

So as of 2026-09-14 the comparison also **hashes the capture PNGs both arms
wrote** and reports, separately from the classes, how many captures scored the
same while their bytes differ. What this changed, exactly:

  * ``cls`` is UNCHANGED and still score-based, so ``--expect-count same=N``
    and every prediction already on file mean what they meant. No registered
    leg changes its verdict because of this.
  * a ``byte-level check`` block is printed, and the ``UNJUDGED -- nothing got
    worse`` verdict now refuses to be read as inertness when the pixels moved.
  * ``must_not_move`` gains a byte leg, but it can only FAIL on evidence --
    see ``judge()``. On the single-run arms that are the norm here it reports
    and does not fail, because one run per arm cannot tell "the change moved
    it" from "the device moved it".

**WHAT THE BYTE CHECK CANNOT SEE.** It needs the ``capturesN`` directories to
still be on disk; 82 of the 708 scored result directories here no longer have
them. When they are gone the check reports UNAVAILABLE, which is deliberately
not the same word as "agree": a flat count from two armless directories is not
evidence of inertness, and the old behaviour was to say nothing at all. It
also cannot attribute a byte move to the change rather than to the device
unless both arms ran at least twice and each was self-identical; that is the
same rule the numeric band already follows, applied to bytes.

What it deliberately does not do: it does not decode PNGs, it does not score,
and it does not decide whether a mixed result should land. It says what moved.
Which *pixels* moved is ``diff_specimen.py``; which captures a disc can be
trusted to reproduce at all is ``sweep_agreement.py``.

Exit status: 0 pass, 1 fail (a prediction was violated, or a capture regressed
with no prediction on file), 2 refused (the arms are not comparable). The byte
check does not change the exit code -- it changes what the verdict is allowed
to claim.
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
        self._shas = None
        self._sha_runs = 0

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
    def env(self):
        """The environment the run was given, as an ordered tuple.

        Added with `request.sh --env`. A result written before that has NO
        `env` key, which is not the same as `env: []` -- the first means the
        question was never asked, the second that it was asked and the answer
        was none. `env_recorded` is what separates them, and nothing here may
        conclude "the environments matched" from two absences.
        """
        v = self.meta.get("env")
        if isinstance(v, dict):
            return tuple("%s=%s" % kv for kv in sorted(v.items()))
        return tuple(v or ())

    @property
    def env_recorded(self):
        return "env" in self.meta

    @property
    def classifier(self):
        return self.meta.get("classifier_rev", "")

    @property
    def scorer(self):
        # score_sweep.py's revision, which is what actually assigns the
        # `status` column. `classifier_rev` names classify_residuals.py and
        # never touched it -- see the warning below.
        return self.meta.get("scorer_rev", "")

    @property
    def device(self):
        return (self.meta.get("device_label")
                or self.meta.get("device_serial") or "")

    def captures(self):
        keys = set()
        for rows in self.per_run:
            keys |= set(rows)
        return keys

    def capture_shas(self):
        """{(suite, test): [sha256 per run]} over the PNGs this arm wrote.

        The capture filenames use the ``Suite::Test.png`` spelling and the TSV
        keys use ``(suite, test)`` with the same underscored suite, so the map
        is exact -- checked against
        ``1789359225-padwrite59-base-1009294``, where all 217 scored rows have
        a PNG and the only unmatched file is ``pgraph_progress_log.txt``.

        An EMPTY result means the directories are gone, not that the captures
        agree. ``sha_runs`` says how many run directories were actually read,
        and every caller must branch on it rather than on the map being empty
        -- "no evidence of a difference" and "evidence of no difference" are
        the two readings this whole file exists to keep apart.
        """
        if self._shas is not None:
            return self._shas
        out = {}
        self._sha_runs = 0
        for i in range(1, len(self.runs) + 1):
            d = os.path.join(self.path, "captures%d" % i)
            if not os.path.isdir(d):
                continue
            self._sha_runs += 1
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(".png") or "::" not in fn:
                    continue
                suite, test = fn[:-4].split("::", 1)
                h = hashlib.sha256()
                with open(os.path.join(d, fn), "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                out.setdefault((suite, test), []).append(h.hexdigest())
        self._shas = out
        return out

    @property
    def sha_runs(self):
        """Run directories the byte check could actually read. 0 means the
        check is UNAVAILABLE for this arm."""
        self.capture_shas()
        return self._sha_runs

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


# --------------------------------------------------------------------------
# a run that Android took the window away from

MINIMISED = "android: window minimized"
RESTORED = "android: window restored"


def truncation_findings(path):
    """Logcats in a result directory whose window went away and never came back.

    `ui/xemu.c` pauses the display path on SDL_WINDOWEVENT_MINIMIZED and
    prints these two lines from the __ANDROID__ arms of that switch. So a run
    that Android minimises stops producing captures and stops logging, and
    what lands on disk is a PARTIAL capture set that reads exactly like a
    defect -- #52 spent its life believing DepthFmt_z24_Cy_FZn_Maaaaaf stalls,
    and it was simply whichever test was running when the window went away.
    1,500 s of an 1,800 s budget, silently.

    MEASURED over every logcat in dispatch/results on 2026-09-14: 912 files,
    ONE with a minimize (`1789320304-depth52-A-599886/logcat1.txt`, 293 s into
    the run, and the last line in the file) and none with a restore. So this
    is rare and not a routine event to be tolerated -- which is the argument
    for failing on it rather than counting it.

    WHAT THIS CANNOT SEE, and it is half the value of the check:

      * WHY the window went away. The capture spec ends `*:S` and names only
        `hakuX*` tags plus the Vulkan ones, so there is not an
        `ActivityManager` line anywhere in these files. THAT, never WHY.
        Twelve runs on disk ran longer (1147, 977, 956, 697, 471 s) and none
        was minimised, so it is not a screen timeout and not a run ceiling;
        beyond that this instrument has nothing to say and must not pretend
        to.
      * A minimize during TEARDOWN from one during the run. The event is the
        last line in the one real case, which is what both look like. So the
        finding reports the corroborating facts -- how many log lines follow
        it, and what the caller knows about completion -- rather than
        asserting truncation on its own.
      * A run Android killed outright, which logs nothing at all. Absence of
        a minimize is not proof the run was whole; `progress_log_proof` is
        the check for that, and this one sits in front of it.
    """
    out = []
    names = sorted(glob.glob(os.path.join(path, "logcat.txt")) +
                   glob.glob(os.path.join(path, "logcat[0-9]*.txt")))
    for f in names:
        try:
            lines = open(f, errors="replace").read().splitlines()
        except OSError:
            continue
        last_min = last_rest = None
        for i, ln in enumerate(lines):
            if MINIMISED in ln:
                last_min = i
            elif RESTORED in ln:
                last_rest = i
        if last_min is None:
            continue
        if last_rest is not None and last_rest > last_min:
            continue
        # The timestamp is the head of an Android log line; keep it as text
        # rather than parsing, because the guest clock is offset from host
        # time and a parsed value invites arithmetic that does not hold.
        stamp = " ".join(lines[last_min].split()[:2])
        out.append(dict(file=os.path.basename(f), line=last_min + 1,
                        when=stamp, after=len(lines) - last_min - 1,
                        total=len(lines)))
    return out


def truncation_lines(path, label):
    """The finding as reportable text. Empty list when the run was never
    minimised, which is the normal case."""
    out = []
    for t in truncation_findings(path):
        out.append(
            "%s: %s shows `%s` at line %d (%s) with NO later `%s`, and %d of "
            "%d log lines follow it."
            % (label, t["file"], MINIMISED, t["line"], t["when"], RESTORED,
               t["after"], t["total"]))
        out.append(
            "  Android took the window away mid-run, so the display path was "
            "paused from that point (ui/xemu.c, SDL_WINDOWEVENT_MINIMIZED). "
            "Whatever is missing from this result is missing because the run "
            "stopped, not because the emulator got it wrong -- a partial "
            "capture set reads exactly like a defect. Requeue.")
    return out


def check_comparable(a, b, allow_same_binary=False):
    """Refuse the comparisons that are invalid, and say which. Returns the
    list of non-fatal warnings."""
    warn = []

    # 0. THE WINDOW. This sits in front of the proof check on purpose. Both
    #    fire on the same arm -- depth52-A has progress_log_proof false AND a
    #    minimize -- but "requeue the arm" is the advice #52 followed for its
    #    whole life while believing a named test stalls. The proof check
    #    reports the SYMPTOM; this one reports the CAUSE, and a reader who
    #    sees it knows there is no defect to chase.
    #
    #    An arm whose window went away can be read anyway by setting
    #    AB_ALLOW_MINIMISED to a REASON, on the same argument as
    #    `--no-expect REASON`: the escape hatch exists, and it makes you say
    #    why in something that gets printed.
    for arm in (a, b):
        tr = truncation_lines(arm.path, "%s (%s)" % (arm.name, arm.label))
        if not tr:
            continue
        why = os.environ.get("AB_ALLOW_MINIMISED", "").strip()
        if why:
            warn.append(tr[0] + " Read anyway, because AB_ALLOW_MINIMISED "
                        "says: " + why)
            continue
        die("\n".join(tr))

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
               "Three ways that happens: the two refs resolve to one commit, "
               "the build cache served one binary twice, or -- MEASURED on "
               "2026-09-13 -- the refs differ by commits that touch no "
               "buildable source, and the build is reproducible enough to "
               "produce a BYTE-IDENTICAL apk. A survey at ref 78d539834f came "
               "back with apk_sha b0cba34acef7, the same sha as arms built "
               "from 49afee8889, across a range of 40 commits touching 20 "
               "files, none of them buildable source. That third case is not "
               "a fault and "
               "the arms really are comparable; it is also the only one of the "
               "three that a reader cannot diagnose from the shas alone, so "
               "check whether the range touches hw/ before assuming a cache "
               "bug." % a.apk)
        # A FOURTH WAY, AND IT IS NOT A FAULT: an `--env` A/B is ONE BINARY BY
        # DESIGN. `request.sh --env KEY=VALUE` exists precisely so that
        # HAKUX_FIFO_SKEW_BOUND 0/1/2 is three requests against one build
        # instead of three builds; the independent variable is the environment
        # and apk_sha is identical across the arms on purpose.
        #
        # Refusing that would have made this gate the seventh false-positive
        # class in this file's history, and the one that bites hardest: it
        # would refuse the arm the feature was added to enable, and the
        # documented escape hatch -- --allow-same-binary -- prints "any delta
        # below is run-to-run noise on one device", which for an env pair is
        # not a caveat but a false statement about a real result.
        #
        # BOTH ARMS MUST HAVE RECORDED AN env FOR THIS TO APPLY. Two results
        # that merely lack the field are two results from before the feature
        # existed, and reading that as "the environments differ" would turn a
        # genuine same-binary accident into a licence.
        if a.env_recorded and b.env_recorded and a.env != b.env:
            warn.append(
                "SAME BINARY, DIFFERENT ENVIRONMENT, which is what an --env "
                "A/B is: one build, one disc, and the environment as the "
                "independent variable.\n    A env: %s\n    B env: %s\n"
                "  apk_sha is identical by design here and is NOT evidence "
                "that the arms are the same experiment. What this pair cannot "
                "show is anything the environment does not reach: if the "
                "variable is read once at startup, a delta is attributable; "
                "if nothing in the build reads that name at all, BOTH ARMS ARE "
                "THE CONTROL and will agree perfectly. Check the `env: KEY="
                "VALUE` line the app logs at startup under tag `hakuX` in each "
                "arm's logcat before reading the numbers below."
                % (", ".join(a.env) or "(none)", ", ".join(b.env) or "(none)"))
        elif allow_same_binary:
            same_dev = a.device and a.device == b.device
            warn.append(
                "SAME BINARY: " + msg + " Continuing on --allow-same-binary. "
                + ("Both arms ran on %s, so any delta below is run-to-run "
                   "noise on one device." % a.device if same_dev else
                   "The arms ran on DIFFERENT devices (A %s, B %s), so a "
                   "delta below is run-to-run noise OR a difference between "
                   "the two handhelds, and this pair cannot separate them."
                   % (a.device or "?", b.device or "?")))
        else:
            die(msg + "\nPass --allow-same-binary if the point is to measure "
                "the noise floor.")
    if a.ref and a.ref == b.ref:
        warn.append("both arms name ref %s; the arms differ only by build or "
                    "by run." % a.ref)

    # 5b. THE ENVIRONMENT IS A SECOND INDEPENDENT VARIABLE WHEN IT IS NOT THE
    #     FIRST. Two different refs AND two different envs is two changes, and
    #     the delta cannot be assigned to either. Not fatal -- it is sometimes
    #     exactly what was meant, e.g. a fix that only takes effect under a
    #     probe -- but it must be said, because it is invisible in every
    #     number this tool prints.
    if a.env_recorded and b.env_recorded:
        if a.env != b.env and a.apk != b.apk:
            warn.append(
                "TWO VARIABLES: the arms differ in BOTH binary and "
                "environment.\n    A %s env %s\n    B %s env %s\nA delta "
                "below is not attributable to either on its own."
                % (a.apk or "?", ", ".join(a.env) or "(none)",
                   b.apk or "?", ", ".join(b.env) or "(none)"))
        elif a.env and a.env == b.env:
            warn.append("both arms ran with env %s, so it is held constant "
                        "and is not the variable here." % ", ".join(a.env))
    elif a.env_recorded != b.env_recorded:
        warn.append(
            "env is recorded for only one arm (A %s, B %s). The field was "
            "added 2026-09-14, so an older result simply predates it -- that "
            "asymmetry is NOT evidence the environments matched, and it is "
            "not evidence they differed either. If either arm was an --env "
            "arm, requeue the other one rather than reading across."
            % ("yes" if a.env_recorded else "no",
               "yes" if b.env_recorded else "no"))

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
    # THE DEVICE. There was no check here at all, and the omission cost a
    # registered leg rather than merely a nicety.
    #
    # `affinity.py` pins both arms of a pair to one handheld precisely so a
    # comparison has one variable. That pin is not a guarantee: it falls
    # through when the sibling's device is no longer serving, which is correct
    # -- the alternative is an arm nobody claims for the length of an outage --
    # and it means a pair CAN span two devices without anyone asking for it.
    #
    # Measured 2026-09-13. #50's arm A ran on the nova, the nova was held for
    # four hours, arm B ran on the thor. The registered determinism legs --
    # must_not_move over a suite and better=0/worse=0 -- were written to ask
    # "is this disc deterministic run-to-run". A split pair answers
    # "run-to-run AND device-to-device together", and a FAILURE stops being
    # evidence for the world the prediction named, because a device difference
    # produces the same signature.
    #
    # Not fatal, deliberately, and this is the one place it differs from
    # disc_id. A different disc makes captures INCOMPARABLE. A different device
    # makes them comparable and CONFOUNDED -- the two handhelds measured 62 of
    # 62 captures byte-identical -- so the honest response is to say what the
    # pair can and cannot establish, not to refuse it. Note that the 62/62 was
    # measured on `Texture DXT` + `Surface clip` on the STOCK disc, so it does
    # not transfer to an arbitrary capture class on its own.
    if a.device and b.device and a.device != b.device:
        warn.append(
            "DEVICES DIFFER (A %s, B %s). The pair is comparable but "
            "CONFOUNDED: every figure below mixes run-to-run variation with "
            "any difference between the two handhelds. A leg that HOLDS is "
            "strictly stronger than one device would give. A leg that FAILS "
            "is NOT attributable -- a device difference has the same "
            "signature as the defect -- so a failure here needs a same-device "
            "pair before it can be diagnosed." % (a.device, b.device))
    elif not a.device or not b.device:
        warn.append("device not recorded for %s; a pair cannot be shown to be "
                    "single-device, so treat any band below as an upper bound "
                    "on determinism."
                    % (", ".join(n for n, arm in (("A", a), ("B", b))
                                 if not arm.device)))
    # The SCORER, not just the classifier. `status` -- ok / label-differs /
    # white-content, and therefore which captures are VOID -- comes from
    # score_sweep.py, which `classifier_rev` does not name. Two results with
    # the same classifier_rev disagreed about 63 captures for exactly this
    # reason, and a whole sweep column turned out to have been scored by two
    # scorers because the fix landed mid-run.
    if a.scorer and b.scorer and a.scorer != b.scorer:
        warn.append("scorer_rev differs (A %s, B %s); the arms disagree about "
                    "which captures are VOID, which is not a fact about the "
                    "renderer. Re-score one arm before reading any status "
                    "count below." % (a.scorer, b.scorer))
    elif bool(a.scorer) != bool(b.scorer):
        warn.append("scorer_rev is recorded for only one arm (A %r, B %r). "
                    "The field was added 2026-09-13, so an older result simply "
                    "predates it -- that asymmetry is not evidence the scorers "
                    "differed." % (a.scorer, b.scorer))
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


def byte_verdict(ha, hb):
    """Did the picture move? ``(moved, attributable)``.

    ``moved`` is True/False/None -- None meaning the captures are not on disk
    for one or both arms, which is a third answer and not a False.

    ``attributable`` says whether a move can be blamed on the CHANGE rather
    than on the device. It needs each arm to have run at least twice and to
    have been byte-identical with itself: that is the numeric band's rule
    applied to bytes. With one run per arm -- the shape of almost every arm
    here -- a cross-arm byte difference and a nondeterministic capture have
    the same signature, so ``attributable`` is False and the move is reported
    rather than judged. ``Texture_border/2D_BorderTex_SZ`` is bit-exact in
    five of ten runs of ONE binary; a byte guard that failed on single-run
    evidence would fail that capture about half the time with nothing changed.
    """
    if not ha or not hb:
        return None, False
    moved = not (set(ha) & set(hb))
    self_stable = (len(ha) >= 2 and len(set(ha)) == 1
                   and len(hb) >= 2 and len(set(hb)) == 1)
    return moved, bool(moved and self_stable)


def compare(a, b):
    sha_a, sha_b = a.capture_shas(), b.capture_shas()
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
        moved, attributable = byte_verdict(sha_a.get(key), sha_b.get(key))
        rows.append(dict(
            pixels_moved=moved, pixels_moved_attributable=attributable,
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
            # Print the path and the full sha, not just the label. PRE-REGISTERED
            # is the one line in this output that stops a reader looking
            # further, so it has to carry enough for a reader to check it
            # WITHOUT trusting the binding: `sha256sum <path>` against the
            # value printed here, independently of anything in this script or
            # in the request. The remote lane asked for this after the
            # detached-checkout hashing bug, where the failure mode was a
            # wrongly bound prediction reported under exactly this label.
            notes.append("PRE-REGISTERED: arm %s was queued at %s naming %s, "
                         "and its content still hashes to the sha recorded "
                         "then. The prediction existed before the device ran "
                         "and has not been edited since.\n"
                         "  bound sha256 %s\n"
                         "  verify with: sha256sum %s"
                         % (arm.name.upper(),
                            (arm.request or {}).get("queued_utc", "?"),
                            named, want, path))
            return exp, notes
        notes.append("TAMPERED: arm %s was queued naming this file, but its "
                     "content has changed since. The prediction has been "
                     "edited since the device work was asked for, so the "
                     "verdict below is worth nothing. Recover the queued "
                     "version, or re-register and re-run.\n"
                     "  bound at queue time  %s\n"
                     "  hashes now           %s\n"
                     "  file                 %s"
                     % (arm.name.upper(), want, (got or "unreadable"), path))
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

    # `must_not_move` is BIT-IDENTICAL. `must_not_regress` allows improvement.
    #
    # For a long time must_not_move was the only guard, so every "leave this
    # alone" intent got written as it -- including the ones that meant "do not
    # make this worse". That cost two otherwise-good arms in one day:
    #
    #   - #13's wide-line arm FAILED on ELEVEN captures that all moved BETTER
    #     and none worse. The leg had been transcribed as bit-identical when
    #     its source criterion was must-not-regress, and at w=1.0 a correct
    #     fix MUST move a non-axis-aligned line.
    #   - #67's arm registered Stencil/* as must_not_move to prove scoping,
    #     and six Stencil captures moved -- five of them better. That one was
    #     a different bug (#79, the suite is nondeterministic), but the leg
    #     could not have expressed "do not regress" either.
    #
    # A guard nobody can state correctly gets stated incorrectly. So both now
    # exist, and the message says which one is being applied, because "must
    # not move, but moved (better)" reads like a defect and usually is not.
    for kind, pats in (("must_not_move", exp.get("must_not_move") or []),
                       ("must_not_regress", exp.get("must_not_regress") or [])):
        bad_cls = ("better", "worse") if kind == "must_not_move" else ("worse",)
        for pat in pats:
            hit = [n for n in by_name if fnmatch.fnmatch(n, pat)]
            if not hit:
                fails.append("%s %r matched no capture in either arm; "
                             "the guard was never actually applied"
                             % (kind, pat))
                continue
            checks += len(hit)
            for n in sorted(hit):
                r = by_name[n]
                if r["cls"] in bad_cls:
                    fails.append("%s, but %s: %-40s %9d -> %9d"
                                 % (kind.replace("_", " "),
                                    "moved" if kind == "must_not_move"
                                    else "REGRESSED",
                                    n, r["a"], r["b"]))
                    continue
                # `must_not_move` SAYS BIT-IDENTICAL AND USED TO CHECK THE
                # SCORE. Both this function's own comment and AGENTS.md
                # describe it as bit-identical; `cls` is computed from the
                # `differing` column, so until 2026-09-14 a capture could
                # hold its number, draw a different picture, and satisfy the
                # guard. #59's arm 3 passed twelve such globs over 192
                # captures on a disc where one capture's pixels had moved.
                #
                # It fails here ONLY on evidence that the change did it --
                # both arms run twice or more and each self-identical. On a
                # single-run arm the byte difference is reported by
                # byte_summary() and does not fail, because device
                # nondeterminism has the same signature and a guard that
                # cannot tell them apart is a coin flip, not a check.
                if kind == "must_not_move" and r["pixels_moved_attributable"]:
                    fails.append(
                        "must not move, and the score held, but THE PIXELS "
                        "MOVED: %-30s %9d -> %9d (byte-different in every "
                        "run, and each arm was byte-identical with itself, "
                        "so this is the change and not the device)"
                        % (n, r["a"], r["b"]))

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
                msg = ("predicted %s = %s, measured %s"
                       % (k, want, tally.get(k)))
                # SAY WHICH CAPTURES BROKE A COUNT, and whether an open
                # harness issue already owns them.
                #
                # `expect_counts` is a GLOBAL tally over the whole disc, and
                # nothing about excluding a suite from `must_not_move`
                # excludes it here. On the #67 arm the prediction deliberately
                # left Stencil out of every per-capture leg, because six runs
                # had shown nine of its sixteen captures varying WITHIN an
                # arm -- and then `worse = 0` failed anyway, on a Stencil
                # capture, taking a 121-of-122 result to FAIL. The number was
                # correct and told the reader nothing about where to look.
                #
                # So name them, and cross-reference the tracker: an open issue
                # with disposition "harness" that names the suite is the board
                # already saying "this observable is not trustworthy". That
                # turns a bare count into a pointer, without weakening the
                # check -- it still fails.
                if k in ("better", "worse"):
                    got = sorted("%s/%s" % r["key"] for r in rows
                                 if r["cls"] == k)
                    shown = got[:6]
                    msg += "\n      " + ", ".join(shown)
                    if len(got) > len(shown):
                        msg += ", ... and %d more" % (len(got) - len(shown))
                    owned = _harness_issue_for({n.split("/")[0] for n in got})
                    if owned:
                        msg += ("\n      every one is in a suite an OPEN "
                                "harness issue already owns: %s"
                                % ", ".join("#%s (%s)" % (i, ", ".join(su))
                                            for i, su in sorted(owned.items())))
                fails.append(msg)
    return fails, checks


def _harness_issue_for(suites):
    """Open `harness` tracker issues whose suites cover ALL of `suites`.

    Returns {issue: [suite, ...]} or {} -- and {} on any problem reading the
    tracker, because this is an annotation on a failure that has already been
    decided. It must never be the reason a judgement changes.
    """
    try:
        import tomllib
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "nv2a_issues.toml")
        with open(path, "rb") as fh:
            tracker = tomllib.load(fh)["issue"]
    except Exception:
        return {}
    # The tracker spells suites with spaces; rows carry the results-directory
    # spelling. Same two spellings that made ten legs inert on the #67 arm.
    want = {s.replace("_", " ") for s in suites}
    if not want:
        return {}
    out = {}
    covered = set()
    for num, v in tracker.items():
        if v.get("disposition") != "harness" or v.get("status") != "open":
            continue
        named = set(v.get("suites") or [])
        hit = want & named
        if hit:
            out[num] = sorted(hit)
            covered |= hit
    return out if covered == want else {}


def resolve_ref(ref):
    """A registered ref must be a concrete sha, for the same reason a queued
    --ref must be.

    `--a-ref 19c74e95da~1` reads fine and is useless: the arm reports the sha
    it actually built, `9bdec552c1`, and the two do not compare, so the judge
    aborts with "a prediction registered for other refs is not a prediction
    about this measurement" -- refusing the very measurement it was written
    for. Worse is the moving kind: `HEAD` resolves at read time, so a
    prediction registered against HEAD silently follows the branch and can end
    up naming the fix it was supposed to be blind to. request.sh resolves
    --ref at queue time for exactly this reason; this is the same rule one
    step earlier.
    """
    if not ref:
        return ""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", ref],
            text=True, stderr=subprocess.DEVNULL).strip() or ref
    except Exception:
        return ref


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
        "a_ref": resolve_ref(args.a_ref),
        "b_ref": resolve_ref(args.b_ref),
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
    exp.setdefault("must_not_regress", [])
    if not (exp["must_not_move"] or exp["must_not_regress"]
            or exp["expect"] or exp["expect_counts"]):
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


def byte_summary(a, b, rows):
    """The byte check, as reportable lines plus the facts a verdict needs.

    ``flat_but_moved`` is the one that matters: no capture changed class, and
    the pixels changed anyway. That is #59 arm 3 exactly, and it is the state
    in which "inert" is the wrong word.
    """
    checked = [r for r in rows if r["pixels_moved"] is not None]
    unchecked = [r for r in rows if r["pixels_moved"] is None]
    moved = [r for r in checked if r["pixels_moved"]]
    quiet = [r for r in moved if r["cls"] in ("same", "noise")]
    lines = []
    info = dict(available=bool(checked), checked=len(checked),
                unchecked=len(unchecked), moved=len(moved),
                quiet=["%s/%s" % r["key"] for r in quiet],
                attributable=[("%s/%s" % r["key"]) for r in moved
                              if r["pixels_moved_attributable"]],
                flat_but_moved=False)

    if not checked:
        lines.append("  UNAVAILABLE: %s kept no capture directory, so nothing "
                     "here can tell"
                     % (", ".join(x.label for x in (a, b) if not x.sha_runs)))
        lines.append("  'same number' from 'same image'. THE FLAT COUNT ABOVE "
                     "IS THEREFORE NOT")
        lines.append("  EVIDENCE OF INERTNESS -- it is the absence of "
                     "evidence. Requeue both arms")
        lines.append("  if inertness is the claim you need.")
        return dict(info, lines=lines)

    lines.append("  hashed %d of %d shared captures (%d run-dir(s) A, %d B)"
                 % (len(checked), len(rows), a.sha_runs, b.sha_runs))
    if unchecked:
        lines.append("  %d capture(s) had no PNG in one or both arms and were "
                     "NOT checked" % len(unchecked))
    if not moved:
        lines.append("  every checked capture is byte-identical between the "
                     "arms.")
        return dict(info, lines=lines)

    lines.append("  %d capture(s) differ BYTE FOR BYTE between the arms."
                 % len(moved))
    if quiet:
        lines.append("")
        lines.append("  of those, %d did not change class -- the same number, "
                     "a different image:" % len(quiet))
        for r in sorted(quiet, key=lambda r: (r["suite"], r["test"])):
            lines.append("    %-6s %-24s %-30s %9s -> %9s  PIXELS MOVED"
                         % (r["cls"], r["suite"], r["test"][:30],
                            fmt(r["a"]), fmt(r["b"])))
        lines.append("  A score is a distance from the golden, so two "
                     "different images can sit the")
        lines.append("  same distance away. #59's arm 3 read 0/0/217-same "
                     "with identical totals while")
        lines.append("  49,104 px moved on Clear/SFC_X1R5G5B5_Z1R5G5B5 -- "
                     "green repaired, alpha broken")
        lines.append("  by the same edit. Run diff_specimen.py on these "
                     "before calling the arm inert.")

    if info["attributable"]:
        lines.append("")
        lines.append("  ATTRIBUTABLE to the change: both arms ran twice or "
                     "more and each was")
        lines.append("  byte-identical with itself, so the device did not do "
                     "this: " + ", ".join(info["attributable"][:6]))
    elif moved:
        lines.append("")
        lines.append("  NOT ATTRIBUTABLE: one run per arm cannot tell a "
                     "change from device")
        lines.append("  nondeterminism -- both have this signature. Requeue "
                     "with --runs 3 to")
        lines.append("  separate them; sweep_agreement.py measures the same "
                     "thing within one ref.")

    info["flat_but_moved"] = bool(quiet) and not [
        r for r in rows if r["cls"] in ("better", "worse")]
    return dict(info, lines=lines)


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

    # -- the byte-level check ----------------------------------------------
    #
    # Printed unconditionally, including when it found nothing and when it
    # could not run. A check that only prints when it fires teaches the reader
    # that silence means agreement, and the whole point here is that silence
    # is the third answer.
    bc = byte_summary(a, b, rows)
    out.append("")
    out.append("-" * 78)
    out.append("byte-level check -- what a score count cannot see")
    out.append("-" * 78)
    for line in bc["lines"]:
        out.append(line)

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
        elif bc["flat_but_moved"]:
            # THE FLAT-COUNT TRAP, NAMED IN THE VERDICT LINE.
            #
            # This used to read "nothing got worse", which is true of the
            # scores and was read as "the change did nothing" -- the sentence
            # #59's arm 3 was reported with while a working fix sat inside it.
            out.append("VERDICT: UNJUDGED, AND NOT INERT -- no capture "
                       "changed class, but %d capture(s) are a DIFFERENT "
                       "IMAGE at the same score: %s. Do not report this arm "
                       "as having done nothing; the byte check above says "
                       "otherwise. No prediction was registered either, so "
                       "register one with --register before the next arm."
                       % (len(bc["quiet"]), ", ".join(bc["quiet"][:6])))
            rc = 0
        else:
            out.append("VERDICT: UNJUDGED -- nothing got worse, but no "
                       "prediction was registered, so this measurement "
                       "confirms nothing. Register one with --register "
                       "before the next arm."
                       + ("" if bc["available"] else
                          " AND THE CAPTURES ARE GONE, so 'nothing got worse'"
                          " is a statement about two numbers only."))
            rc = 0
    else:
        for n in exp_notes:
            out.append(n)
        fails, checks = judge(exp, rows)
        if bc["quiet"]:
            out.append("BYTE CHECK: %d capture(s) held their score and moved "
                       "their pixels: %s. No registered leg tests that -- "
                       "every class here is score-based -- so this is a fact "
                       "about the arm, not a verdict on it."
                       % (len(bc["quiet"]), ", ".join(bc["quiet"][:6])))
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
        # Only the BAD binding labels make the exit code non-zero. This used
        # to be `if exp_notes: rc = 1`, and exp_notes carries the GOOD label
        # too -- so **every PRE-REGISTERED PASS this campaign produced exited
        # 1**, and the exit code has been useless as a signal since the binding
        # was added. Nobody was caught by it because every lane reads the
        # verdict text, but a script keying on `$?` would have seen a clean
        # pass as a failure, which is the worst direction for a gate to be
        # wrong in. Found by the #6 lane, in a file it does not own.
        if any(n.startswith(("TAMPERED", "POST-HOC", "UNBOUND"))
               for n in exp_notes):
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
                byte_check={k: v for k, v in bc.items() if k != "lines"},
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
    p.add_argument("--check-truncation", metavar="RESULTDIR",
                   help="exit 1 if that result's logcat shows the Android "
                        "window minimized with no later restore. Works on a "
                        "SOAK result too, which is the case nothing else "
                        "covers")
    args = p.parse_args()

    # THE ONE CHECK THAT HAS TO WORK ON A SOAK, which is why it is a mode of
    # its own rather than only a step inside check_comparable().
    #
    # A disc arm is already stopped by two gates: progress_log_proof, and now
    # the minimize check in front of it. A SOAK reaches neither -- ab_compare
    # dies on it at "records no runs at all", correctly, because there is
    # nothing to compare. So a soak that Android minimised 20 s into 90 s
    # produces a short logcat, the requester reads their legs off it, and
    # NOTHING anywhere says the window went away. That is the worst place for
    # this hole to be: the no-oracle streams are the ones that queue soaks,
    # and per-window counts have been measured varying 3-5x WITHIN one run, so
    # a truncated window does not look wrong on inspection.
    #
    # `request.sh --wait` calls this when a result lands, so both shapes are
    # covered by one implementation rather than by two that drift.
    if args.check_truncation:
        lines = truncation_lines(args.check_truncation, "result")
        for ln in lines:
            print(ln)
        return 1 if lines else 0

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
