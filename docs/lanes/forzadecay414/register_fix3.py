#!/usr/bin/env python3
"""Register the fix's claims on the merged head (#414): fix-pixels3 and fix-forza3.

Run from the worktree root. The branch merged origin/master 146b8887db (221
commits past this lane's base, 85347ffbd1), so both claims are re-registered
on the new refs: A 146b8887db (master), B eec025dd37 (that master plus the
one hunk in vk/surface.c, and nothing else outside docs/).

  fix-pixels3  the full sweep of fix-pixels2, same must_not_move list (Stencil/*
               out under #79), both arms hard-pinned to the Nova. pixels2's pair
               split Thor/Nova and its FAIL was confounded; the arms job could
               not queue its same-device re-run ("thor is gone"), and it
               queues no new pair while GitHub is unreachable. This lane queues
               the pair itself with request.sh and judges it with ab_compare.
  fix-forza3   one Nova Forza soak of B over a 420-s window, read by hand with
               judge.py --end 420. A is not run: a Forza race on master is
               killed by lmkd at ~215 s on the Nova (NOTES, "Do not repeat").
"""
import json
import subprocess
import sys

A = "146b8887db"   # origin/master when the branch merged it
B = "eec025dd37"   # the merge: A plus the one hunk in vk/surface.c
PIX = "docs/testing/predictions/forzadecay414-fix-pixels3.json"
FORZA = "docs/testing/predictions/forzadecay414-fix-forza3.json"

old = json.load(open("docs/testing/predictions/forzadecay414-fix-pixels2.json"))
disc = old["disc"]
mnm = old["must_not_move"]

PIX_TEXT = (
    "PIXEL-INERT, FULL SWEEP, ONE DEVICE (the Nova, both arms hard-pinned). "
    "Re-registration of forzadecay414-fix-pixels2.json on the merged refs. Its pair "
    "(1-1790727472-arms-forzadecay414-base-2035879 on the Thor, -fix-2035992 on the "
    "Nova) read FAIL, 37 of 3363, and the arms job called it CONFOUNDED (A thor, B "
    "nova): 36 of the 37 are ZPass_pixel_count captures, 35 moving by +1010 to +1114 "
    "and ZPass itself by +672, the shape of a device difference, and one is "
    "Antialiasing_tests/FramebufferNotModifiedBySurfac 0 -> 1. Its same-device re-run "
    "was never queued (thor is gone), so this pair is on the Nova alone. "
    "Stencil/* is run but excluded from must_not_move under tracker #79 (flakes ~8.6% "
    "per capture-run on every binary). B is A (master 146b8887db) plus one change in "
    "vk/surface.c: pgraph_vk_drain_deferred_surface_releases(r, frame), which runs "
    "only once that slot's fence has been waited, now also sets invalidation_frame = "
    "-1 on every surface in r->invalid_surfaces stamped with that slot. Only "
    "surface_in_flight() reads invalidation_frame, to keep an invalid surface out of "
    "get_any_compatible_invalid_surface() and prune_invalid_surfaces(). So B changes "
    "which invalid surface images are recycled or destroyed and when; it changes no "
    "draw, copy, upload or download, and a recycled image is a render target whose "
    "content the next draw defines. Prediction: every capture on all 100 golden "
    "suites is byte-identical between A and B within the run-to-run band measured by "
    "2 runs per arm; 0 better, 0 worse. RenderTextureLoop is skipped as in every arm "
    "since #379. Falsifier, and the world it fails in: a capture that moves outside "
    "its band, or a validation error, device-lost or crash line in B's logcat and not "
    "A's. That is the world where a surface was still referenced by a submitted "
    "command buffer after its slot's fence was waited, so B recycled an image in use; "
    "it shows first in Texture_render_target, Texture_render_update_in_place, "
    "Texture_Framebuffer_Blit, Surface_format, Color_zeta_overlap and Surface_clip. "
    "If ZPass_pixel_count moves on one device, that is the change's, not the "
    "device's. Rows scored unreadable are VOID, not exact."
)

FORZA_TEXT = (
    "NOVA SOAK, B ONLY, read by hand with docs/lanes/forzadecay414/judge.py --end 420 "
    "(arms.sh skips title soaks). Forza race, survey route, 420 s, perflog, regimen "
    "max. B is eec025dd37: master 146b8887db plus one hunk in vk/surface.c "
    "(pgraph_vk_drain_deferred_surface_releases() clears invalidation_frame on every "
    "invalid surface stamped with the slot whose fence was just waited). A, master, is "
    "named for the refs and NOT RUN: every Forza race on a build with #517 and without "
    "this fix leaked to invalid= 1915-1996 and was cut at 208-276 s on the Nova, and "
    "hostops withdrew the master re-run because lmkd kills it at ~215 s (xemu 4.4 GB "
    "PSS). The thresholds come from the fix's two runs on 10fe2f59a7 "
    "(1-1790625108-forzadecay414-3486226, 1-1790639501-forzadecay414-151099), which "
    "this file does not judge. Rows are timeline.py's 30-s rows, t = 0 at `soak "
    "start`; the t = 420 row is partial and not read. `walk` is the txw scan ms/flip "
    "less the [sdcall] range= completion on the nearest line. Legs, and the world each "
    "fails in: "
    "W0 WHOLE: `soak end` at t >= 400, and no ERROR, VOID or lmkd kill; else VOID. "
    "M0 RACE REACHED: >= 5 txw lines in t = 180-390 with scan calls/flip >= 500 "
    "(menus read 0-85, the race 685-931), and the last `play` route frame shows the "
    "race HUD; else VOID. "
    "B1 max invalid= over the run <= 400. Fails in the world where the merged master "
    "added a second holder that keeps surfaces off the prune. "
    "B2 last invalid= at or before t = 420 <= max(60, 2 x its median over t = "
    "150-240). Fails in the world where the list still grows, only slower, and a "
    "longer window shows it. "
    "B3 walk <= 0.5 ms/flip on the first and on the last race line. Fails in the "
    "world where the walk costs for a reason other than the list's length. "
    "D1 fps, mean of rows t = 330, 360, 390, >= 0.8 x mean of rows t = 150, 180, 210. "
    "Fails in the world where Forza has a second decay that shows only past 360 s. "
    "D3 every row t = 150..390 >= 0.6 x the median of those rows (the fix's earlier "
    "run reads min/median 0.77 over 150-330). Fails in the world where the race "
    "holds its mean but steps down inside the window: a pause, a stall or a "
    "regime like the Thor's thermal step. "
    "READOUTS, not judged: thermal.jsonl xo-therm, the hottest zone and clk; "
    "[sdcall] ms per frame; any validation, crash or device-lost line."
)

FORZA_EXPECT = {
    "W0/b_whole_is": True,
    "M0/b_reach_race_is": True,
    "B1/b_max_invalid_max": 400,
    "B2/b_last_invalid_max_of_60_or_2x_early_median": True,
    "B3/b_walk_ms_per_flip_max": 0.5,
    "D1/b_fps_late_over_early_min": 0.8,
    "D3/b_fps_row_min_over_median_min": 0.6,
}


def register(path, text, extra):
    cmd = [sys.executable, "docs/testing/ab_compare.py", "--register", path,
           "--a-ref", A, "--b-ref", B, "--who", "lane.forzadecay414",
           "--issue", "414", "--prediction", text, "--force"] + extra
    subprocess.run(cmd, check=True)


mnm_args = []
for g in mnm:
    mnm_args += ["--must-not-move", g]
register(PIX, PIX_TEXT, mnm_args + [
    "--disc-suites", ",".join(disc["suites"]),
    "--disc-skip-tests", ",".join(disc.get("skip_tests") or [])])
j = json.load(open(PIX))
j["runs_per_arm"] = 2
j["device"] = "nova"
out = json.dumps(j, indent=2) + "\n"
json.loads(out)
open(PIX, "w").write(out)

# --expect-value takes integers only; the full leg set is written below
register(FORZA, FORZA_TEXT, ["--expect-value", "B1/b_max_invalid_max=400"])
j = json.load(open(FORZA))
j.update({
    "title": "4D53006E-Forza_Motorsport.xiso.iso",
    "device": "nova",
    "seconds": 420,
    "route": "survey",
    "perflog": True,
    "runs_per_arm": 1,
    "expect": FORZA_EXPECT,
    "expect_counts": {},
    "expect_note": "Named rules read by hand from judge.py --end 420; a soak writes "
                   "no captures, so ab_compare never judges it. A is not run.",
})
out = json.dumps(j, indent=2) + "\n"
json.loads(out)
open(FORZA, "w").write(out)
print(PIX)
print(FORZA)
