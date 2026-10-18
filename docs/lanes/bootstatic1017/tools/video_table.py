#!/usr/bin/env python3
"""judge_video over every finished Nova request in nova_ids.tsv (as nova_table.py finds them), one row per run:
validity (V0 Turnip, V1 video starts before the launch, V2 runs past it), the content alignment, the episodes of
static or green frames with their probe readings, and vidruns.py's whole-frame runs to the title's first picture
(the look sequence a player saw: black, static, streaks, logo, picture).

usage: video_table.py [MAX_S]
"""
import glob
import io
import os
import sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge_video as jv  # noqa: E402
import nova_table as nt  # noqa: E402
import vidruns  # noqa: E402


def main():
    mx = sys.argv[1] if len(sys.argv) > 1 else "12"
    print("| request | arm | ref | title | video verdict | V1 lead s | align off s (score, at 0) | episodes: frames, "
          "classes, s after first present, probe src / screen-off / H1 H5 H4 |")
    print("|---|---|---|---|---|---|---|---|")
    runs = []
    for arm, ref, title, rid in nt.rows_of_ids():
        hits = [p for p in glob.glob(os.path.join(nt.D, "*" + rid)) if os.path.exists(os.path.join(p, "DONE"))]
        if not hits:
            continue
        rd = hits[0]
        r = jv.judge(rd)
        eps = "; ".join("%d fr %s @%s s, %s / %d of %d / %s %s %s" % (
            e["frames"], ",".join(e["classes"]), e["s_after_first_present"], ",".join(e["probe_flash_src"]) or "-",
            e["probe_screen_off"], e["probe_presents"], int(e["H1"]), int(e["H5"]), int(e["H4"]))
            for e in r.get("episodes", [])) or "none"
        print("| %s | %s | %s | %s | %s | %s | %s (%s, %s) | %s |" % (
            os.path.basename(rd).split("-lane")[0], arm, ref, title.split(" (")[0], r["verdict"],
            None if r.get("V1_lead_s") is None else round(r["V1_lead_s"], 2), r.get("align_offset_s"),
            r.get("align_score"), r.get("align_score_at_0"), eps))
        runs.append((os.path.basename(rd).split("-lane")[0], arm, title.split(" (")[0], rd, r))
    for rid, arm, title, rd, r in runs:
        if not os.path.isdir(os.path.join(rd, "video")) or not r["verdict"].startswith(("VALID", "VOID: V")):
            continue
        buf = io.StringIO()
        sys.argv = ["vidruns.py", rd, mx]
        try:
            with redirect_stdout(buf):
                vidruns.main()
        except Exception as ex:  # noqa: BLE001
            buf.write("vidruns failed: %s\n" % ex)
        print("\n%s %s %s (first present at video +%s s):" % (rid, arm, title, None if r.get("V1_lead_s") is None
                                                                else round(r["V1_lead_s"], 2)))
        print(buf.getvalue().rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
