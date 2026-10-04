#!/usr/bin/env python3
"""Register lane.forzadecay414's two Nova soak predictions (#414 item 1).

Run from the worktree root. ab_compare.py --register writes the file and its
refs; the soak fields (title, device, seconds, route, perflog) and the
hand-read legs are added here, the way forza414's soak predictions carry them.
A soak writes no captures, so ab_compare never judges these: the legs are read
by hand from the logcats with docs/lanes/forza414/timeline.py and the txw lines.
"""
import json
import subprocess
import sys

A = "f82e7e87fe"   # master first-parent just before the #517 fold
B = "09050ddbe5"   # the #517 fold (lane.drain474): A plus one moved flush
M = "85347ffbd1"   # master at this lane's base

COMMON = (
    "NOVA SOAK, read by hand (arms.sh skips title soaks). Forza race, survey route, "
    "360 s, perflog, regimen max, the Nova because it plateaus near 49 C and never "
    "reaches the Thor's xo-therm 78 C pause, which is a second, separate 2-4 fps "
    "regime (NOTES section 2) that would confound a Thor read. Buckets are "
    "docs/lanes/forza414/timeline.py's 30-s rows (t = 0 at `soak start`); `invalid` "
    "is the [watch311] line's invalid= (length of r->invalid_surfaces); `faf` and "
    "`scan` are the txw probe's ms/flip and calls/flip for pgraph_vk_flush_all_frames "
    "and pgraph_vk_download_surfaces_in_range_if_dirty. Mechanism under test (NOTES "
    "section 3): invalidate_surface() stamps a surface invalidated inside the open "
    "command buffer with invalidation_frame = r->current_frame, a ring-slot index that "
    "is never reset; surface_in_flight() is then true whenever that slot is current or "
    "submitted, which in steady state is always, so prune_invalid_surfaces() keeps the "
    "surface until pgraph_vk_flush_all_frames() clears every frame_submitted[] at once. "
    "#517 moved the flush Forza hit on every direct surface-to-texture bind behind the "
    "copy branch, so in Forza's race nothing flushes, the list grows, and every "
    "texture bind (~800 per flip) walks it in "
    "pgraph_vk_download_surfaces_in_range_if_dirty. "
)

BISECT = COMMON + (
    "A is %s (master before #517), B is %s (the #517 fold; the only emulator change "
    "between them is that moved flush). Legs, and the world each fails in: "
    "M0 both arms reach the race: timeline rows t = 180-330 have G >= 40 ms and there "
    "are >= 5 [watch311] lines after t = 150; else VOID. "
    "P0 A's median txw faf calls/flip over t = 180-330 >= 0.2 and B's <= 0.02. Fails "
    "in the world where A does not flush in the race either: then A's pruning comes "
    "from somewhere else and the flush is not the link. "
    "P1 B's last [watch311] invalid= at or before t = 360 >= 1000. Fails in the world "
    "where #517 alone does not grow the list on the Nova: the growth then needs #518's "
    "pending flip pre-download (deferred_downloads_reference) or something Thor-only, "
    "and the fa56a26f1f runs named the wrong commit. "
    "P2 A's max [watch311] invalid= over the run <= 400 (the eight pre-#517 Nova soaks "
    "peak at 50-240). Fails in the world where the leak predates #517. "
    "P3 fps (timeline fps column, mean of rows t = 270, 300, 330) B/A <= 0.6. Fails in "
    "the world where the list grows but costs the Nova no fps: then the Thor's decay "
    "needs a second, Thor-side cost. "
    "READOUTS, not judged: txw scan ms/flip first and last race line, ic, cpu, G per "
    "bucket, thermal.jsonl xo-therm (the Nova must not cross 60 C for the read to "
    "stand as cool-device)." % (A, B))

MASTER = COMMON + (
    "A is %s (the same A run as forzadecay414-bisect.json, one soak serves both), B is "
    "%s (master at this lane's base, after #518, #543 and every later fold). Legs: "
    "M0 as bisect M0 on these two arms; else VOID. "
    "P1 B's last [watch311] invalid= at or before t = 360 >= 1000. Fails in the world "
    "where a fold after #517 already stopped the growth: then master's Forza does not "
    "decay and only the historical refs did. "
    "P3 fps (mean of timeline rows t = 270, 300, 330) B/A <= 0.6. Fails in the world "
    "where master grows the list without the fps cost. "
    "READOUTS: as bisect." % (A, M))


def register(path, a, b, text, expect):
    cmd = [sys.executable, "docs/testing/ab_compare.py", "--register", path,
           "--a-ref", a, "--b-ref", b, "--who", "lane.forzadecay414",
           "--issue", "414", "--prediction", text, "--force"]
    # --expect-value takes integers only; the full leg set is written below
    cmd += ["--expect-value", "P1/b_last_invalid_min=1000"]
    subprocess.run(cmd, check=True)
    j = json.load(open(path))
    j.update({
        "title": "4D53006E-Forza_Motorsport.xiso.iso",
        "device": "nova",
        "seconds": 360,
        "route": "survey",
        "perflog": True,
        "runs_per_arm": 1,
        "expect": expect,
        "expect_counts": {},
        "expect_note": "Named rules read by hand from the logcats (timeline.py rows, "
                       "[watch311] invalid=, txw faf/scan); a soak writes no captures, "
                       "so ab_compare never judges it.",
    })
    text_out = json.dumps(j, indent=2) + "\n"
    json.loads(text_out)
    open(path, "w").write(text_out)


register("docs/testing/predictions/forzadecay414-bisect.json", A, B, BISECT, {
    "M0/both_reach_race_is": True,
    "P0/a_faf_calls_per_flip_min": 0.2,
    "P0/b_faf_calls_per_flip_max": 0.02,
    "P1/b_last_invalid_min": 1000,
    "P2/a_max_invalid_max": 400,
    "P3/b_over_a_fps_t270_330_max": 0.6,
})
register("docs/testing/predictions/forzadecay414-master.json", A, M, MASTER, {
    "M0/both_reach_race_is": True,
    "P1/b_last_invalid_min": 1000,
    "P3/b_over_a_fps_t270_330_max": 0.6,
})
