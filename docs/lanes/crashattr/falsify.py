#!/usr/bin/env python3
"""crashattr falsifier: title_verdict's crash field, old against new, on the
real result dirs, and on a twin of each bystander run with only the crashed
process's name changed to hakuX's.

  python3 docs/lanes/crashattr/falsify.py <new title_verdict.py> [<old>]

Reads dispatch/results/ only (judge(write_contact_sheet=False) writes
nothing). The twins go in docs/lanes/crashattr/work/, which is not committed.
Exit 0 when every row is what it must be.
"""
import importlib.util
import os
import shutil
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TESTING = os.path.join(REPO, "docs", "testing")
RESULTS = "/home/justin/hakux-work/dispatch/results"
WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work")
sys.path.insert(0, TESTING)          # thermal_state, hitch_report

# (run, what crashed, must the new verdict say crash)
BYSTANDER = [
    ("1790951866-titleroutes2-46925", "media.extractor x4 (ToeJam & Earl III)"),
    ("1790951914-titleroutes2-68595", "media.extractor x1 (Tron 2.0)"),
    ("1790953776-titleroutes2-447685", "media.extractor x3 (Tron 2.0)"),
    ("0-0-x-1790465684-lane.remote-2069760", "surfaceflinger (libc + tombstone)"),
]
# Every run in results/ through 2026-10-02 with an F/libc line from hakuX's
# own pid (no tombstone: the handler re-raises under SIG_DFL), and the two
# with a hakuX-crash BugCheck.
HAKUX = [
    ("1-1790724657-lane.memfast-1385791", "libc FORTIFY"),
    ("1-1790724657-lane.memfast-1385837", "libc FORTIFY + SIG_DFL"),
    ("1-1790724689-lane.ibcache-1389824", "libc FORTIFY"),
    ("1-1790724690-lane.ibcache-1389915", "libc SIG_DFL"),
    ("1-1790724692-lane.ibcache-1390704", "libc FORTIFY"),
    ("1-1790724693-lane.ibcache-1390830", "libc SIG_DFL x2"),
    ("1-1790724693-lane.ibcache-1391025", "libc FORTIFY"),
    ("1-1790725089-lane.verdict433-1456493", "libc FORTIFY"),
    ("1-1790725089-lane.verdict433-1456544", "libc FORTIFY"),
    ("1-1790519287-titleroutes-2112912r", "hakuX-crash BugCheck"),
    ("1790933948-titleroutes-171701", "hakuX-crash BugCheck"),
]
# The twin's rename: the bystander's tombstone and libc names become a hakuX
# process's, one variant per run so all three suffixes are exercised.
RENAME = {
    "1790951866-titleroutes2-46925": [("Cmdline: media.extractor aextractor", "Cmdline: com.jreinach.hakux:xemu")],
    "1790951914-titleroutes2-68595": [("Cmdline: media.extractor aextractor", "Cmdline: com.jreinach.hakux.debug:xemu")],
    "1790953776-titleroutes2-447685": [("Cmdline: media.extractor aextractor", "Cmdline: com.jreinach.hakux.debug2:xemu")],
    # libc's "pid N (name)" is comm, the last 15 characters; the tombstone
    # half is dropped from the twin so the libc name check alone decides.
    "0-0-x-1790465684-lane.remote-2069760": [("pid 1369 (surfaceflinger)", "pid 1369 (akux.debug:xemu)"),
                                              ("Cmdline: /system/bin/surfaceflinger", "Cmdline: -")],
}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def twin(run):
    src, dst = os.path.join(RESULTS, run), os.path.join(WORK, run + "-hakux")
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    for f in os.listdir(src):
        p = os.path.join(src, f)
        if f == "logcat.txt":
            s = open(p, errors="replace").read()
            for a, b in RENAME[run]:
                assert a in s, (run, a)
                s = s.replace(a, b)
            open(os.path.join(dst, f), "w").write(s)
        elif f in ("verdict.json", "contact.png", "VOID.txt"):
            continue
        else:
            os.symlink(p, os.path.join(dst, f))
    return dst


def main():
    new = load(sys.argv[1], "tv_new")
    old = load(sys.argv[2] if len(sys.argv) > 2 else os.path.join(TESTING, "title_verdict.py"), "tv_old")
    rows = [(r, w, os.path.join(RESULTS, r), False) for r, w in BYSTANDER]
    rows += [(r, w, os.path.join(RESULTS, r), True) for r, w in HAKUX]
    rows += [(r + " (twin)", "renamed to hakuX", twin(r), True) for r, _ in BYSTANDER]
    # The row is judged on the crash LINES the new code attributes to hakuX;
    # `crash` is also true for a run.log `guest exited`, which is not this
    # change's to decide and is shown in its own column.
    bad = 0
    print("| run | what crashed | old crash | new crash lines | guest exited | new crash | new failing | must have lines |")
    print("|---|---|---|---|---|---|---|---|")
    for name, what, rdir, want in rows:
        vo = old.judge(rdir, write_contact_sheet=False)
        vn = new.judge(rdir, write_contact_sheet=False)
        pids = []
        lc, _g, _o = new.parse_logcat(os.path.join(rdir, "logcat.txt"), pids)
        lines = new.crash_lines_of(lc, pids)
        runlog = open(os.path.join(rdir, "run.log"), errors="replace").read()
        exited = "guest exited after" in runlog
        ok = bool(lines) is want and vn["crash"] is (want or exited)
        bad += not ok
        print("| %s | %s | %s | %d | %s | %s | %s | %s%s |" % (
            name, what, vo["crash"], len(lines), exited, vn["crash"],
            (vn["failing"] or "")[:50].replace("|", "/"), want, "" if ok else "  **WRONG**"))
    print("\n%d of %d rows wrong" % (bad, len(rows)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
