#!/usr/bin/env python3
"""Register doa413b-instr-mnm.json: the must-not-move arm for the instrumentation-only diff.

Every capture in the eight suites is guarded except Blend_surface/R5G6B5_Add_SrcA_DstA,
whose moved capture on the first arm was byte-identical to other lanes' base legs
(a known two-state row). Blend_surface's other keys are listed one by one because
must_not_move globs have no exclusion.
"""
import csv
import os
import subprocess
import sys

WT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = "/home/justin/hakux-work/dispatch/results/1790463182-arms-doa413b-base-1083820"
NOISY = "R5G6B5_Add_SrcA_DstA"
A_REF, B_REF = sys.argv[1], sys.argv[2]

rows = list(csv.DictReader(open(os.path.join(BASE, "scores1.tsv")), delimiter="\t"))
blend = sorted(r["test"] for r in rows if r["suite"] == "Blend_surface" and r["test"] != NOISY)
assert len(blend) == 31, len(blend)

PRED = (
    "MUST-NOT-MOVE guard for #413, instrumentation only. A is %s (master), B is %s (master plus "
    "the [surf413] surface_update sub-split probe; the refuted lazy-completion path is removed). "
    "Every added line is inside NV2A_PERF_LOG && __ANDROID__ macros that only read clocks and "
    "bump counters, and the arm's build runs the same surface_update, completion and upload order "
    "as master. Prediction: every guarded capture is byte-identical between arms. What would move "
    "each: Depth_buffer_fixed_function, Color_zeta_overlap, Surface_format, Blend_surface and Clear "
    "if a probe macro changed statement order or skipped the deferred-download completion; "
    "Texture_render_target, Texture_CPU_Update and Texture_render_update_in_place if the probe's "
    "hash counter in surface_watch_resume changed the re-arm path. Blend_surface/%s is unguarded: "
    "on the first arm (1790463182-arms-doa413b-*) its fix capture was byte-identical to the base "
    "legs of arms-zrtz272 and arms-pshqueue, a known two-state row. Read every scores1.tsv status "
    "for unreadable." % (A_REF, B_REF, NOISY))

cmd = [sys.executable, os.path.join(WT, "docs/testing/ab_compare.py"),
       "--register", os.path.join(WT, "docs/testing/predictions/doa413b-instr-mnm.json"),
       "--who", "lane.doa413b", "--issue", "413", "--prediction", PRED,
       "--a-ref", A_REF, "--b-ref", B_REF, "--disc-from", BASE]
for g in ["Depth_buffer_fixed_function/*", "Color_zeta_overlap/*", "Surface_format/*", "Clear/*",
          "Texture_render_target/*", "Texture_CPU_Update/*", "Texture_render_update_in_place/*"]:
    cmd += ["--must-not-move", g]
for t in blend:
    cmd += ["--must-not-move", "Blend_surface/" + t]
sys.exit(subprocess.call(cmd))
