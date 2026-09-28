#!/usr/bin/env python3
"""Register forzadecay414-fix-forza2.json: the fix's Forza legs, re-cut (#414).

Run from the worktree root. forzadecay414-fix-forza.json stays as registered;
three of its thresholds were wrong, and its first runs said so (NOTES
section 8):

  M0   took G >= 40 ms as the mark of the race. A race that does not decay
       runs at G 33-36 ms, so the leg voids exactly the arm that is fixed.
  B3   capped txw `scan` at 3.0 ms/flip. Since #543 the scan's time holds a
       download completion it triggers ([sdcall] range=), 3.8-7.5 ms a frame
       on master and on the fix alike; the walk of the list is what is left.
  D2   names the master arm's first request, which was voided twice.

This file is the same question with those three corrected, for runs that have
not happened: the master arm's re-run (1-1790624589-forzadecay414-3394871-r4,
queued by hostops) and a new run of the fix. Every quantity is printed by
docs/lanes/forzadecay414/judge.py, committed with this file.
"""
import json
import subprocess
import sys

A = "85347ffbd1"   # master at this lane's base
B = "10fe2f59a7"   # A plus the one hunk in vk/surface.c
PATH = "docs/testing/predictions/forzadecay414-fix-forza2.json"

TEXT = (
    "NOVA SOAK, read by hand with docs/lanes/forzadecay414/judge.py (arms.sh skips "
    "title soaks). Forza race, survey route, 360 s, perflog, regimen max. A is "
    "85347ffbd1 (master at this lane's base), run as "
    "1-1790624589-forzadecay414-3394871-r4. B is 10fe2f59a7, A plus one hunk in "
    "vk/surface.c: pgraph_vk_drain_deferred_surface_releases() clears "
    "invalidation_frame on every invalid surface stamped with the slot whose fence "
    "was just waited. This file re-cuts forzadecay414-fix-forza.json, whose M0, B3 "
    "and D2 could not be read as written (NOTES section 8); its first B run, "
    "1-1790625108-forzadecay414-3486226, is what the thresholds below were set "
    "from, and is not judged by this file. Rows are timeline.py's 30-s rows, t = 0 "
    "at `soak start`. `walk` is the txw scan ms/flip less the [sdcall] range= "
    "completion ms/frame on the nearest line: the scan's time without the download "
    "it triggers. Legs, and the world each fails in: "
    "M0 RACE REACHED, both arms: >= 5 txw lines in t = 180-330 with scan "
    "calls/flip >= 500 (menus read 0-85, the race 685-931), and the last `play` "
    "route frame shows the race HUD; else VOID. "
    "A1 A's last [watch311] invalid= at or before t = 360 >= 1000. Fails in the "
    "world where master does not leak on the Nova over a whole race. "
    "A3 A's walk on its last race line >= 5.0 ms/flip (the cut master run read "
    "8.78 at t = 213). Fails in the world where the list grows but the walk is not "
    "where master's time goes. "
    "B1 B's max invalid= over the run <= 400. Fails in the world where a second "
    "holder keeps surfaces off the prune. "
    "B2 B's last invalid= at or before t = 360 <= max(60, 2 x its median over "
    "t = 150-240). Fails in the world where the list still grows, only slower. "
    "B3 B's walk <= 0.5 ms/flip on its first and on its last race line. Fails in "
    "the world where the walk still costs for a reason other than the list's "
    "length. "
    "D1 B's fps, mean of rows t = 270, 300, 330, >= 0.8 x its mean of rows "
    "t = 150, 180, 210. Fails in the world where Forza has a second decay that "
    "does not need the list. "
    "D2 B/A fps over rows t = 270-330 >= 1.5, VOID if A1 fails. Fails in the "
    "world where the list costs the Nova no fps. "
    "READOUTS, not judged: [sdcall] range/surfupd/record ms per frame in both "
    "arms (the fix must not be what put a completion in the scan: A has it too), "
    "thermal.jsonl xo-therm and clk, any validation, crash or device-lost line "
    "in B and not in A."
)

EXPECT = {
    "M0/both_reach_race_is": True,
    "A1/a_last_invalid_min": 1000,
    "A3/a_walk_ms_per_flip_last_min": 5.0,
    "B1/b_max_invalid_max": 400,
    "B2/b_last_invalid_max_of_60_or_2x_early_median": True,
    "B3/b_walk_ms_per_flip_max": 0.5,
    "D1/b_fps_late_over_early_min": 0.8,
    "D2/b_over_a_fps_t270_330_min": 1.5,
}

cmd = [sys.executable, "docs/testing/ab_compare.py", "--register", PATH,
       "--a-ref", A, "--b-ref", B, "--who", "lane.forzadecay414",
       "--issue", "414", "--prediction", TEXT, "--force",
       # --expect-value takes integers only; the full leg set is written below
       "--expect-value", "B1/b_max_invalid_max=400"]
subprocess.run(cmd, check=True)
j = json.load(open(PATH))
j.update({
    "title": "4D53006E-Forza_Motorsport.xiso.iso",
    "device": "nova",
    "seconds": 360,
    "route": "survey",
    "perflog": True,
    "runs_per_arm": 1,
    "expect": EXPECT,
    "expect_counts": {},
    "expect_note": "Named rules read by hand from judge.py's output; a soak writes "
                   "no captures, so ab_compare never judges it.",
})
out = json.dumps(j, indent=2) + "\n"
json.loads(out)
open(PATH, "w").write(out)
print(PATH)
