#!/usr/bin/env python3
"""Which build a handheld last ran, and whether it is the release build.

    device_build.py check   <dispatch_dir> <label>
        exit 0: the device's newest recorded run is on master (or none is
                recorded yet); prints the build either way.
        exit 4: it is on a non-release build; prints a line naming the build.
                jobs/hold.sh take refuses on this.

    device_build.py restore <dispatch_dir> <label> <run_id>
        after a run that is not on master (its ref, env or requester differ),
        writes the 60 s master restore into queue/ and prints its id; prints
        nothing and writes nothing when the run is already on master, when
        the run is itself a restore, or when a restore for this device is
        already queued or running. The dispatcher calls this after each
        run's result.json is written.

    device_build.py promote <dispatch_dir> <label> [--force]
        called by jobs/hold.sh's build gate on a refusal: gives the label's
        queued dispatch.restore request the top queue tier (id prefix "0-"),
        or queues one (at the same tier) when none is pending. Always exits
        0 and prints what it did; the caller's refusal is build_gate's, not
        this command's. restore_request's own id stays bare either way, so
        the dispatcher's own after-every-off-master-run restores still wait
        their ASCII-ordered turn.

        --force: also called by jobs/hold.sh's wait loop while some OTHER
        request is running for the label (device_build.py running's "other"
        case) -- the in-flight request has not written a result.json yet,
        so the device's newest recorded run can still read as master even
        though the device will be off master the moment this run ends.
        Without --force, that stale "on master" reading makes the no-
        restore-needed check below refuse to queue anything. --force skips
        only that check; the pending- and running-restore short-circuits
        above it still run first and still win, so a restore already
        queued or in flight is never duplicated.

    device_build.py running <dispatch_dir> <label>
        exit 0 "restore: <id>": the label's own dispatch.restore request is
                in running/ right now.
        exit 1 "other: <id>": some other request for the label is.
        exit 2 "none": nothing is.
        jobs/hold.sh's wait loop asks this before trusting a `check` pass:
        the dispatcher claims its next request the instant a served one
        ends, at the top of its tick, before the queue (and before this
        process could see a fresh result.json) -- so a `check` pass read
        moments after a promoted restore finishes can still be describing
        a device with a brand new off-master request already running
        underneath it.

A run is on master when its result.json says ref master (or origin/master,
or the master sha given as MASTER_SHA, or a sha reachable from origin/master
-- see _on_trunk below) and env []. A result with no `env` key predates the
field, so the build it ran is not known to be master: it is not release.
The record is the result.json the dispatcher wrote for the device's newest
run (device_label == label), read by mtime.
"""
import datetime
import glob
import json
import os
import subprocess
import sys

MASTER_REFS = ("master", "origin/master")
RESTORE_REQUESTER = "dispatch.restore"
RESTORE_SECONDS = 60


def _repo_root():
    """Best-effort repo path for _on_trunk's git calls.

    DISPATCH_REPO, when the caller has one -- dispatcher.sh always does
    ($REPO), even from the snapshot its worker re-execs into. Otherwise this
    file's own location: right when it is the real jobs/device_build.py in
    a checkout, which is how hold.sh runs it; wrong (no .git above it) for
    the snapshot's copy, where the git call below just fails and ancestry
    is not checked.
    """
    return os.environ.get("DISPATCH_REPO") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")


def _on_trunk(ref):
    """True when ref names a commit reachable from origin/master.

    request.sh resolves every --ref to a concrete sha AT QUEUE TIME, before
    a request ever reaches the dispatcher (a request must name the tree the
    requester meant, not "whatever HEAD is when this is served"). So a real
    request's ref is never the literal string "master": only
    restore_request() below ever writes that, straight into queue/, for the
    dispatcher's own internal restore. Without this check, an ordinary
    measurement run -- any plain run on trunk -- reads as non-release
    forever, and queue_master_restore would queue a 60 s restore after
    every single run, not only after a test build.
    """
    if not ref:
        return False
    try:
        return subprocess.run(
            ["git", "-C", _repo_root(), "merge-base", "--is-ancestor", ref,
             "origin/master"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
    except OSError:
        return False


def build_of(rec):
    """(release, why) for one result.json record."""
    if rec is None:
        return True, "no run recorded on this device"
    ref = rec.get("ref") or ""
    master_sha = os.environ.get("MASTER_SHA", "")
    if "env" not in rec:
        return False, "its run (ref %s) predates the env field" % (ref or "?")
    if rec["env"]:
        return False, "ref %s with env %s" % (ref or "?", ", ".join(rec["env"]))
    if ref in MASTER_REFS or (master_sha and ref == master_sha) or _on_trunk(ref):
        return True, "master"
    return False, "ref %s" % (ref or "?")


def last_run(dispatch_dir, label):
    """(record, run_id) of the device's newest run, or (None, None)."""
    newest = None
    for path in glob.glob(os.path.join(dispatch_dir, "results", "*", "result.json")):
        try:
            rec = json.load(open(path))
        except (OSError, ValueError):
            continue
        if rec.get("device_label") != label:
            continue
        mt = os.path.getmtime(path)
        if newest is None or mt > newest[0]:
            newest = (mt, rec, os.path.basename(os.path.dirname(path)))
    return (newest[1], newest[2]) if newest else (None, None)


def restore_request(run_id, label, now=None):
    """The request the dispatcher queues to put master back on a handheld."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    rid = "%d-%s-%s" % (int(now.timestamp()), RESTORE_REQUESTER, run_id[-8:])
    return {"id": rid, "requester": RESTORE_REQUESTER,
            "purpose": "master restore after run %s" % run_id,
            "program": "", "suites": [], "tests": [], "skip_tests": [],
            "ref": "master", "arm": "solo", "runs": 1,
            "title": "", "seconds": RESTORE_SECONDS, "device": label,
            "pull_glob": "", "audio_capture": "", "base_iso": "",
            "perflog": "", "only_tests": [], "env": [], "frames_every": 0,
            "route_name": "", "route": "", "title_id": "", "title_state": "any",
            "identified": "", "expect": "", "expect_sha": "", "no_expect": "",
            "priority": "study",
            "queued_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ")}


def restore_needed(rec):
    """True when the run just finished left the device off master."""
    if rec is not None and rec.get("requester") == RESTORE_REQUESTER:
        return False
    return not build_of(rec)[0]


def restore_pending(dispatch_dir, label):
    """True when a restore for this device is already queued or running.

    A queued restore writes no result.json until it is served, so without
    this check last_run() keeps reading the same off-master result for
    every non-master run that finishes while the restore waits, and queues
    one more of them -- forever, as long as the chain of non-master runs
    continues. Checked against both queue/ (not yet claimed) and running/
    (claimed by a worker, mid-serve): either one already satisfies the need
    this call would otherwise re-queue for.
    """
    for sub in ("queue", "running"):
        for path in glob.glob(os.path.join(dispatch_dir, sub, "*.req")):
            try:
                req = json.load(open(path))
            except (OSError, ValueError):
                continue
            if req.get("requester") == RESTORE_REQUESTER and req.get("device") == label:
                return True
    return False


def _restore_path(dispatch_dir, label, sub):
    """Path to label's dispatch.restore request under queue/ or running/, or None."""
    for path in glob.glob(os.path.join(dispatch_dir, sub, "*.req")):
        try:
            req = json.load(open(path))
        except (OSError, ValueError):
            continue
        if req.get("requester") == RESTORE_REQUESTER and req.get("device") == label:
            return path
    return None


def _promote(path):
    """Atomic rename <dir>/<base> -> <dir>/0-<base>, via a tmp file first.

    A no-op (prints the already-promoted name) on a path already carrying
    the prefix, so a second caller polling the same refusal does not try to
    rename a file that is not there under its old name.
    """
    d, base = os.path.split(path)
    if base.startswith("0-"):
        return base
    tmp = os.path.join(d, "." + base + ".promote.tmp")
    dst = os.path.join(d, "0-" + base)
    os.replace(path, tmp)
    os.replace(tmp, dst)
    return os.path.basename(dst)


def cmd_promote(dispatch_dir, label, force=False):
    pending = _restore_path(dispatch_dir, label, "queue")
    if pending is not None:
        print("promoted: %s" % _promote(pending))
        return 0
    running = _restore_path(dispatch_dir, label, "running")
    if running is not None:
        print("already running: %s" % os.path.basename(running))
        return 0
    rec, run_id = last_run(dispatch_dir, label)
    if not force:
        if rec is None:
            print("no run recorded for %s; nothing to restore from" % label)
            return 0
        if not restore_needed(rec):
            print("%s already on master; no restore needed" % label)
            return 0
    req = restore_request(run_id or "pending", label)
    queue = os.path.join(dispatch_dir, "queue")
    tmp = os.path.join(queue, "." + req["id"] + ".req.tmp")
    with open(tmp, "w") as f:
        json.dump(req, f, indent=2)
    path = os.path.join(queue, req["id"] + ".req")
    os.rename(tmp, path)
    print("queued: %s" % _promote(path))
    return 0


def cmd_running(dispatch_dir, label):
    path = _restore_path(dispatch_dir, label, "running")
    if path is not None:
        print("restore: %s" % os.path.basename(path))
        return 0
    for p in glob.glob(os.path.join(dispatch_dir, "running", "*.req")):
        try:
            req = json.load(open(p))
        except (OSError, ValueError):
            continue
        if req.get("device") == label:
            print("other: %s" % os.path.basename(p))
            return 1
    print("none")
    return 2


def cmd_check(dispatch_dir, label):
    rec, run_id = last_run(dispatch_dir, label)
    release, why = build_of(rec)
    if release:
        print("%s: on master (%s)" % (label, why))
        return 0
    print("%s is on a non-release build: %s (run %s). It is not on master; "
          "the master restore is queued after that run, or request one with "
          "request.sh --ref master --seconds 60" % (label, why, run_id))
    return 4


def cmd_restore(dispatch_dir, label, run_id):
    path = os.path.join(dispatch_dir, "results", run_id, "result.json")
    rec = json.load(open(path))
    if not restore_needed(rec):
        return 0
    if restore_pending(dispatch_dir, label):
        return 0
    req = restore_request(run_id, label)
    queue = os.path.join(dispatch_dir, "queue")
    tmp = os.path.join(queue, "." + req["id"] + ".req.tmp")
    with open(tmp, "w") as f:
        json.dump(req, f, indent=2)
    os.rename(tmp, os.path.join(queue, req["id"] + ".req"))
    print(req["id"])
    return 0


def main(argv):
    if len(argv) == 4 and argv[1] == "check":
        return cmd_check(argv[2], argv[3])
    if len(argv) == 5 and argv[1] == "restore":
        return cmd_restore(argv[2], argv[3], argv[4])
    if len(argv) == 4 and argv[1] == "promote":
        return cmd_promote(argv[2], argv[3])
    if len(argv) == 5 and argv[1] == "promote" and argv[4] == "--force":
        return cmd_promote(argv[2], argv[3], force=True)
    if len(argv) == 4 and argv[1] == "running":
        return cmd_running(argv[2], argv[3])
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
