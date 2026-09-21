#!/usr/bin/env python3
"""`window_audit.py`'s classification, on a synthetic results directory.

The audit it performs is of an out-of-band action that left no artifact, so
the one thing the file must not do is answer "clean" for a reason other than
cleanliness. Case 1 is the reason this exists: a run CLAIMED BEFORE the swap
window opened and FINISHING AFTER it closed spends its whole measurement on
the swapped driver, and the original `window_start <= mtime <= window_end`
test -- did it FINISH inside -- cannot see it. That is the largest-exposure
case there is, and it was the only one the check was blind to.

Case 4 is the opposite error and is just as fatal to the check's usefulness:
a request can sit in `queue/` for twenty hours, so `[queued, done]` overlaps
everything and a check that calls that contamination is never read.

Run against the ORIGINAL finish-time test, case 1 fails. Run against a
`[queued, done]` overlap test with no artifact evidence, case 4 fails.

    python3 tests_window_audit.py
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import window_audit  # noqa: E402

# An arbitrary window: 1000 -> 2000 seconds past this base.
BASE = 1789000000
W_OPEN, W_SHUT = BASE + 1000, BASE + 2000
MINE = "mine-1"


def make_run(root, name, requester, queued, first_art, done, seconds=220,
             with_queued_utc=True, with_epoch=True):
    """One result dir with the three timestamps set explicitly."""
    d = os.path.join(root, ("%d-%s" % (queued, name)) if with_epoch else name)
    os.makedirs(d)
    req = dict(requester=requester, device="thor", seconds=seconds)
    if with_queued_utc:
        req["queued_utc"] = window_audit.time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", window_audit.time.gmtime(queued))
    with open(os.path.join(d, "request.json"), "w") as fh:
        json.dump(req, fh)
    os.utime(os.path.join(d, "request.json"), (queued, queued))
    with open(os.path.join(d, "run.log"), "w") as fh:
        fh.write("x\n")
    os.utime(os.path.join(d, "run.log"), (first_art, first_art))
    os.utime(d, (done, done))       # last: writing a file touches the dir
    return os.path.basename(d)


def run_audit(root):
    buf = io.StringIO()
    with redirect_stdout(buf):
        window_audit.main(["--results", root,
                           "--window", "w:%d:%d" % (W_OPEN, W_SHUT),
                           "--mine", MINE])
    return buf.getvalue()


def check(name, out, dirname, want_state):
    """`want_state` is EXPOSED, QUEUED-THRU, or None for "must not be listed"."""
    line = [ln for ln in out.splitlines() if ln.strip().endswith(dirname)]
    if want_state is None:
        ok = not line
        detail = "not listed" if ok else "listed: %s" % line[0].strip()
    else:
        ok = bool(line) and line[0].split()[0] == want_state
        detail = line[0].strip() if line else "NOT LISTED"
    print("%-4s %s -- %s" % ("PASS" if ok else "FAIL", name, detail))
    return ok


def main():
    ok = True
    with tempfile.TemporaryDirectory() as root:
        # 1. Straddles the window: started before it opened, finished after it
        #    closed. Never enters or leaves inside it, so a finish-time test
        #    is blind; it is the worst case there is.
        straddle = make_run(root, "straddle", "other-lane",
                            W_OPEN - 300, W_OPEN - 200, W_SHUT + 300)
        # 2. Finished inside -- the case the original test did catch.
        inside = make_run(root, "inside", "other-lane",
                          W_OPEN - 100, W_OPEN + 100, W_SHUT - 100)
        # 3. Done before the window opened: provably never exposed.
        before = make_run(root, "before", "other-lane",
                          W_OPEN - 5000, W_OPEN - 4000, W_OPEN - 3000)
        # 4. Queued long before, ran long after. `[queued, done]` covers the
        #    window; the run did not.
        thru = make_run(root, "thru", "other-lane",
                        W_OPEN - 50000, W_SHUT + 40000, W_SHUT + 41000)
        # 5. This lane's own run, inside the window: listed, never foreign.
        ours = make_run(root, "ours", MINE,
                        W_OPEN - 100, W_OPEN + 100, W_SHUT - 100)
        # 6. Neither an id epoch nor a `queued_utc`, finishing after the
        #    window opened: start unknown, so it must still be listed.
        blind = make_run(root, "blind-dir", "other-lane",
                         W_OPEN - 100, W_OPEN + 100, W_SHUT - 100,
                         with_queued_utc=False, with_epoch=False)

        out = run_audit(root)
        ok &= check("straddling run is caught", out, straddle, "EXPOSED")
        ok &= check("run finishing inside is caught", out, inside, "EXPOSED")
        ok &= check("run finished before the window is not listed", out,
                    before, None)
        ok &= check("queue-straddler is QUEUED-THRU, not EXPOSED", out, thru,
                    "QUEUED-THRU")
        ok &= check("this lane's own run is listed", out, ours, "EXPOSED")
        ok &= check("dir with no parseable start is still listed", out, blind,
                    "EXPOSED")

        # The counts, which are what a reader actually quotes.
        tail = [ln for ln in out.splitlines() if "overlapped a swap" in ln]
        want = ("5 run(s) overlapped a swap window by queue time; 4 were "
                "executing inside one; 3 of those are not this lane's")
        cok = bool(tail) and tail[0] == want
        print("%-4s counts line -- %s"
              % ("PASS" if cok else "FAIL", tail[0] if tail else "MISSING"))
        ok &= cok

        fok = out.count("FOREIGN:") == 3
        print("%-4s three FOREIGN lines -- got %d"
              % ("PASS" if fok else "FAIL", out.count("FOREIGN:")))
        ok &= fok

    print("ALL PASS" if ok else "FAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
