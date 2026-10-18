#!/usr/bin/env python3
"""The desktop before/after table for #1045 under judge_nova.py's measures (M1 screen-off presents not black, M2 the
centre-half noise or green with the screen on, M3 a whole-frame static or streaks look with the screen on), which
desk_ab.py's centre-half classes cannot replace: the green look on Halo lies outside the centre half.

usage: desk_judge.py RUN:ARM:TITLE [...] [--sheets DIR]     (RUN is a dir under build-linux/runs with probe/)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_nova as jn  # noqa: E402

RUNS = "/home/justin/hakux-work/wt/bootstatic1017/build-linux/runs"


def main():
    a = sys.argv[1:]
    sheets = a[a.index("--sheets") + 1] if "--sheets" in a else None
    specs = [s for s in a if s.count(":") >= 2]
    print("| run | arm | title | verdict | title's first picture (n, s) | screen-off presents to it | M1 (whole log) "
          "| M2 | M3 | undumped hashes |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    eps = []
    for spec in specs:
        run, arm, title = spec.split(":", 2)
        pd = os.path.join(RUNS, run, "probe")
        r = jn.judge(pd, desktop=True)
        fp = r.get("title_first_picture")
        print("| %s | %s | %s | %s | %s | %s | %s (%s) | %s | %s | %s |" % (
            run, arm, title, r["verdict"].split(";")[0],
            "n%d, %.1f s" % (fp["n"], fp["t_ms"] / 1000) if fp else "none",
            r.get("screen_off_presents_to_first_picture"), r.get("M1_to_first_picture"), r.get("M1_whole_log"),
            r.get("M2_to_first_picture"), r.get("M3_to_first_picture"), r.get("undumped_hashes_to_first_picture")))
        for e in r.get("episodes", []):
            eps.append("%s: M1 episode n%d-%d, %d presents, %.0f ms, starts %s, src %s, looks %s" % (
                run, e["n"][0], e["n"][1], e["presents"], e["ms"], ",".join(e["starts"]), ",".join(e["src"]),
                ",".join(e["looks"]) or "-"))
        for k in ("M2_n", "M3_n"):
            if r.get(k):
                eps.append("%s: %s %s" % (run, k, r[k]))
        if sheets:
            jn.sheet(r, os.path.join(sheets, "desk_%s.png" % run), pd)
    for e in eps:
        print(e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
