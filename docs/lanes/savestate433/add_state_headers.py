#!/usr/bin/env python3
"""Add the `# state:` line to every route in docs/testing/titles/routes/
(lane.savestate433, 2026-10-02). Idempotent: a route that already declares a
state is left alone. The state is the one the route was RECORDED in, so the
disk compose() builds for it is the disk it was written on:

  first-run   recorded on a disk with no save for the title: a nav.py
              `<title>.first-run-<stamp>` session on 09-26/27 (each title's
              first play), a survey run whose title had no save yet, or an
              unplayed draft (its first play will be on such a disk)
  returning   recorded on a disk carrying the title's profile
  any         reads the screen (a drive route) or serves every title
              (generic, survey and the survey's text)

The basis for each is in docs/lanes/savestate433/NOTES.md, section E.
"""
import os
import sys

RD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "testing", "titles", "routes")

RETURNING = {
    "crimson-skies": "the only frame-proven 600 s window (1-1790804473) ran on a disk carrying 'Nathan'",
    "sonic-heroes": "written from sonic-heroes.returning-observe-20261001T171059, slot 01 present",
}
ANY = {
    "generic": "serves every title; never marks gameplay",
    "survey": "serves every title; never marks gameplay",
    "forza414": "the survey route's text",
    "forza.drive": "screen-driven (drive.py reads each screen)",
    "sonic-heroes.drive": "screen-driven (drive.py reads each screen)",
}


def state_for(base):
    if base.endswith(".first-run") or base.endswith(".save") or base == "castlevania-cod.drive":
        return "first-run", "recorded creating the profile"
    if base.endswith(".returning"):
        return "returning", "recorded loading the profile"
    if base in RETURNING:
        return "returning", RETURNING[base]
    if base in ANY:
        return "any", ANY[base]
    return "first-run", "recorded on a disk with no save for the title (NOTES.md E)"


def main():
    changed = 0
    for f in sorted(os.listdir(RD)):
        if not f.endswith(".route"):
            continue
        p = os.path.join(RD, f)
        text = open(p).read()
        if any(l.strip().lstrip("#").strip().lower().startswith("state:")
               for l in text.splitlines()[:40] if l.strip().startswith("#")):
            continue
        st, why = state_for(f[:-len(".route")])
        open(p, "w").write(f"# state: {st}   ({why}; lane.savestate433)\n" + text)
        changed += 1
        print(f"{st:9} {f}")
    print(f"{changed} route(s) given a state", file=sys.stderr)


if __name__ == "__main__":
    main()
