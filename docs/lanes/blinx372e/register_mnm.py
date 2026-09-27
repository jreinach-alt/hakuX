#!/usr/bin/env python3
"""Register blinx372e-mnm.json: the must-not-move arm for the #372 quadrant copy.

    python3 docs/lanes/blinx372e/register_mnm.py <a_ref> <b_ref>
"""
import os
import subprocess
import sys

WT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
A_REF, B_REF = sys.argv[1], sys.argv[2]
SUITES = ["Color zeta overlap", "Depth buffer fixed function", "Surface format",
          "Texture CPU Update", "Texture render update in place", "Surface clip",
          "3D primitive"]
GLOBS = [s.replace(" ", "_") + "/*" for s in SUITES]

PRED = (
    "MUST-NOT-MOVE guard for #372's small-to-big quadrant copy. A is %s (lane/doa413b's head, "
    "PR #440: master's hw/ tree plus #440's logging and env-gated lazy completion, off); B is %s "
    "(A merged into this lane: a linear D24S8 zeta binding evicted draw-dirty by a larger one at "
    "the same address, format and pitch, rows fitting the pitch, is copied into the top-left "
    "corner of the larger binding's kept image with vkCmdCopyImage, guarded by a hash of the "
    "larger binding's VRAM taken when its own eviction download landed). `git diff A B -- hw/` "
    "is that hunk alone. Prediction: every capture in the seven suites is byte-identical "
    "between arms. What would move each: Surface_clip's seven rt_* tests bind the default zeta "
    "(offset 0, Z24S8, pitch 2560) small then 640x480 inside one test (rt_x320y240_w320h240 is "
    "Blinx's own 320x240 -> 640x480 pair; rt_x0y240_w640h240, rt_x0y0_w512h384, "
    "rt_x16y8_w512h384, rt_x8y16_w632h464, rt_x0y0_w512h0, rt_x0y0_w0h384 the others), so they "
    "move if the copied corner or the uncopied rest differs from the download-then-upload "
    "route, or if the larger binding's owed download is missed by a capture's readback; "
    "XemuBug420, DebugTextShouldClip and rt_x0y0_w0h0 flip big to small (and back across test "
    "boundaries) and move if the big-to-small path changed, which it must not. 3D_primitive's "
    "-ls/-ps tests flip the default zeta 640x480 -> 1280x480 under AA x2 at pitch 2560, rows "
    "wider than the pitch: the row-fit guard declines them, and they move if it does not. On "
    "1-1790479164-arms-retreason425-fix-2241115, 56 of 3D_primitive's 160 rows (52 of the 120 "
    "-ls/-ps rows) read white-content: unreadable, not passes; the other 68 -ls/-ps rows carry "
    "that leg. All 47 Surface_clip rows were ok and exact there. "
    "Depth_buffer_fixed_function flips Z16/Z24 and fixed/float at one size (declined: same "
    "size, and Z16 differs in bpp); Color_zeta_overlap's AdjacentWithClipOffset_l/_sz clear then "
    "draw zeta at 128x128 and 126x126 in texture memory (pitch 512); both move if an eviction "
    "outside the demo's shape is wrongly accepted. Surface_format is colour-only and cannot "
    "move from this change. Texture_CPU_Update and Texture_render_update_in_place are PR #387's "
    "arm: they move if the copied-into binding owes its download without a live watch. PR "
    "#396's handoff runs in these suites too (handoffs=2 on its arm) and must still read "
    "handoffs=2 in B's [evict372]. Read B's [quad372] copies= before calling a pass anything but "
    "inert: zero copies across Surface_clip makes this arm inert. Read every scores1.tsv status: "
    "white-content rows (Depth_buffer_fixed_function z16_*_FZy_M00ffff in the last run) are "
    "unreadable, not passes." % (A_REF, B_REF))

cmd = [sys.executable, os.path.join(WT, "docs/testing/ab_compare.py"),
       "--register", os.path.join(WT, "docs/testing/predictions/blinx372e-mnm.json"),
       "--who", "lane.blinx372e", "--issue", "372", "--prediction", PRED,
       "--a-ref", A_REF, "--b-ref", B_REF, "--disc-suites", ",".join(SUITES)]
for g in GLOBS:
    cmd += ["--must-not-move", g]
sys.exit(subprocess.call(cmd))
