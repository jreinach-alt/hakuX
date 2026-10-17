#!/usr/bin/env python3
"""The held-run falsifier (#433, title_id as the join key).

The defect: a pathfind held run's verdict.json carries the ISO's own name
("Bad Boys Miami Takedown USA") and no title_id. titles05() resolved that
name alone, which no catalog spelling matches, so the run made a second row
beside the title's own: on 2026-10-16 69 titles had one, 28 of them were
counted as Measured twice (260 for a true 232), and 31 Playable rows showed
no fps because their reading sat on the other row. The run's request.json
and result.json carry the title_id, as title_registry.py's collect_runs()
already reads it.

This builds one self-contained work tree with that shape -- a held run as
pathfind writes it (request.json and result.json with the title_id, a
verdict.json and a provisional/verdict.json with the ISO's name and none)
and a ledger row in the title's own spelling -- and renders titles05()
twice: against the status_html.py at OLD_REF (must split into two rows, the
ISO-named one Measured and the Playable one with no fps) and against the
current one (must fold to one Playable row carrying the run's fps, Measured
once). A change that stopped the old half splitting, or the new half
folding, prints FAIL and exits 1.

Usage: python3 heldrun_falsifier.py [<repo>]
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
# The last master before status_html.py read a held run's title_id from its run directory.
OLD_REF = "fb6ebcff40"

TID = "5A5A0021"
ISO_SPELLING = "Zz Held Run Falsifier USA"
LEDGER_SPELLING = "Zz Held Run: Falsifier"
RUN = "n-%s-1014" % TID
FPS = 59.94

# Both versions import the repo's title_registry.py for the catalog; the old copy is written to a temp directory,
# where its own relative import would find nothing.
sys.path.insert(0, os.path.join(REPO, "docs", "testing"))
import title_registry  # noqa: E402,F401


def build_tree(root):
    for d in ("pm", "titles", "dispatch"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    run = os.path.join(root, "wt", "pathfind", "docs", "lanes", "pathfind", "runs", RUN)
    os.makedirs(os.path.join(run, "provisional"))
    iso = "%s-%s.xiso.iso" % (TID, ISO_SPELLING.replace(" ", "_"))
    req = {"title": ISO_SPELLING, "title_id": TID, "iso": iso}
    json.dump(req, open(os.path.join(run, "request.json"), "w"))
    json.dump(req, open(os.path.join(run, "provisional", "request.json"), "w"))
    json.dump({"title_id": TID, "iso": "/storage/X/Games/XBox/" + iso, "result": "held"},
              open(os.path.join(run, "result.json"), "w"))
    verdict = {"title": ISO_SPELLING, "title_id": None, "name": None, "device": "", "request_id": RUN,
               "booted": True, "reached_gameplay": True, "crash": False, "hang": False, "pass": True,
               "fps_windows": 634, "fps_bar": 30.0, "fps_ok_share": 1.0, "fps_window_median": FPS}
    json.dump(verdict, open(os.path.join(run, "verdict.json"), "w"))
    json.dump(verdict, open(os.path.join(run, "provisional", "verdict.json"), "w"))
    with open(os.path.join(root, "pm", "playable-accepted.tsv"), "w") as fh:
        fh.write("date_pdt\ttitle\ttitle_id\tresult\taccepted_by\tevidence\n")
        fh.write("2026-10-14 12:00\t%s\t%s\tfalsifier\tfalsifier\tframes reviewed\n" % (LEDGER_SPELLING, TID))
    # No registry entry: the run directory alone must name the title.
    open(os.path.join(root, "targets.toml"), "w").write("[defaults]\nplayable_fps = 30\n")


def render(status_html_path, root):
    """titles05() from `status_html_path`, under a fresh module name, against the tree at `root`: (this title's rows,
    the counts)."""
    name = "status_html_heldrun_%d" % id(status_html_path)
    spec = importlib.util.spec_from_file_location(name, status_html_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        del sys.modules[name]
    os.environ["TITLE_TARGETS"] = os.path.join(root, "targets.toml")
    os.environ["TITLESTATE_DIR"] = os.path.join(root, "dispatch", "titlestate")
    os.environ.pop("STATUS_PATHFIND_RUNS", None)
    os.environ["STATUS_XISO_DIR"] = os.path.join(root, "xiso")    # absent: not the host's staged-ISO manifest
    F = mod.Facts({"WORK": root, "D": os.path.join(root, "dispatch")})
    out = mod.titles05(F, {}, os.path.join(root, "release.toml"), 2000000000)
    return [r for r in out["rows"] if "held run" in r["title"].lower()], out["counts"]


def fps(r):
    p = r.get("prim") or {}
    return p.get("fps")


def main():
    fails = []
    with tempfile.TemporaryDirectory(prefix="heldrun-old-") as old_root, \
         tempfile.TemporaryDirectory(prefix="heldrun-new-") as new_root, \
         tempfile.TemporaryDirectory(prefix="heldrun-ref-") as refdir:
        build_tree(old_root)
        build_tree(new_root)
        old_path = os.path.join(refdir, "status_html_old.py")
        open(old_path, "w").write(subprocess.run(
            ["git", "-C", REPO, "show", "%s:docs/testing/jobs/status_html.py" % OLD_REF],
            capture_output=True, text=True, check=True).stdout)
        new_path = os.path.join(REPO, "docs", "testing", "jobs", "status_html.py")

        rows, counts = render(old_path, old_root)
        got = sorted((r["stage"], fps(r)) for r in rows)
        print("old status_html.py: %d row(s) %s, measured %s" % (len(rows), got, counts.get("measured")))
        play = [r for r in rows if r["stage"] == "playable"]
        if not (len(rows) == 2 and len(play) == 1 and fps(play[0]) is None and counts.get("measured") == 2):
            fails.append("old code was expected to SPLIT into two rows, both Measured, the Playable one with no fps, "
                         "and did not: %r, counts %r" % (got, counts))

        rows, counts = render(new_path, new_root)
        got = sorted((r["stage"], fps(r)) for r in rows)
        print("new status_html.py: %d row(s) %s, measured %s" % (len(rows), got, counts.get("measured")))
        if not (len(rows) == 1 and rows[0]["stage"] == "playable" and rows[0]["title"] == LEDGER_SPELLING
                and fps(rows[0]) == FPS and counts.get("measured") == 1):
            fails.append("new code was expected to FOLD to one Playable row named %r with fps %s, Measured once, "
                         "and did not: %r, counts %r" % (LEDGER_SPELLING, FPS, [(r["title"], r["stage"], fps(r))
                                                                               for r in rows], counts))

    if fails:
        print("FAIL")
        for f in fails:
            print(" - %s" % f)
        return 1
    print("PASS: a held run with no title_id in its verdict splits on the old code and joins its title on the current one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
