"""Register the #286 class-A arm (docs/testing/predictions/aasample-cc2-viewport.json).

Kept so the must-not-move list is reproducible: the 40 plain 3D_primitive captures
and the 10 Antialiasing_tests captures that draw no geometry into a CC2 surface.
"""
import subprocess
import sys

A_REF = "18a0ab9387"  # origin/master, the fold base
B_REF = "57e46af766"  # + vk/draw.c viewport hunk

PRED = """\
#286 class A. b_ref adds a +0.5 AA-pixel x offset (times surface_scale_factor) to both Vulkan viewport initialisers in vk/draw.c (pipeline bind and reorder-window snapshot) when the surface is AA_CENTER_CORNER_2; 0.0f for every other mode. Silicon shades CC2 column 2x+1 at the pixel centre; we shaded it at x+0.75 and our u=2x+1 resolve tie picks that column. Priced offline over the 120 AA captures (docs/lanes/aasample/NOTES.md sec 3, price.py): structural px 605,298 -> 347,077 (+258,221 net).

MUST MOVE BETTER (bound in prose; the judge has no exact values): every 3D_primitive TriFan/TriStrip/QuadStrip/Polygon/Triangles capture with -ls, -ps or -ls-ps (60 captures). Structural px (|d|>1) per primitive, now -> fixed: TriFan 175,560 -> 65,068; TriStrip 121,264 -> 52,392; QuadStrip 127,956 -> 71,816; Polygon 40,296 -> 13,216; Triangles 27,896 -> 12,148. Falsifier on the inert rows (where the smoothing flag moves 0 px on silicon): ours(X) == ours(P) byte-exact below the label band. KILL: any of these 60 gets worse, or the inert rows keep a horizontal shift (tiedir.py's sign test of X-P against the gradient is nonzero).
Antialiasing_tests/FBSurfaceWithCenterCorner2 moves better: coverage mismatches over the visible AA rows 352 -> 272 (odd columns 96 -> 0).

MUST MOVE WORSE, NAMED LOSS: 3D_primitive/Quads*-ls, *-ps, *-ls-ps, structural 17,040 -> 35,952 (owner #38, the Gouraud |d|=2 floor that today's quarter-pixel shift partly cancels). The Lines/LineLoop/LineStrip AA rows move slightly worse, -1,259 structural in total (owner #13).
Points AA rows: 9 of 12 points present in every AA Points capture (today 5 of 12). Points 3, 4 and 5 still drop: their fractional x (0.0625, 0.9375) needs a 2x1 AA-px footprint.

MUST NOT MOVE: the 40 plain 3D_primitive captures (CENTER_1; an offset leaking into non-CC2 surfaces moves every one of them) and the other 10 Antialiasing_tests captures (CPU write, NoOpDraw, or overwritten by a CPU write; FBSurfaceWithCenter1 would move under the same leak). Read status for unreadable and the coverage line before reading a mover.
"""

PRIMS = ["LineLoop", "LineStrip", "Lines", "Points", "Polygon", "QuadStrip",
         "Quads", "TriFan", "TriStrip", "Triangles"]
AA_STILL = ["AAOnThenOffCPUWrite", "CPUWriteIgnoresSurfaceConfig",
            "CreateSurfaceWithCenter1", "CreateSurfaceWithCenterCorner2",
            "CreateSurfaceWithSquareOffset4", "FBSurfaceWithCenter1",
            "FramebufferNotModifiedBySurfaceState", "GPUAAWriteAfterCPUWrite",
            "NonAACPURoundTrip", "SurfaceStatesAreIndependent"]

mnm = [f"3D_primitive/{p}{path}" for p in PRIMS
       for path in ("", "-inlinearrays", "-inlinebuf", "-inlineelements")]
mnm += [f"Antialiasing_tests/{t}" for t in AA_STILL]
assert len(mnm) == 50

cmd = ["python3", "docs/testing/ab_compare.py", "--register",
       "docs/testing/predictions/aasample-cc2-viewport.json",
       "--who", "lane.aasample", "--issue", "286", "--prediction", PRED,
       "--a-ref", A_REF, "--b-ref", B_REF,
       "--disc-suites", "3D primitive,Antialiasing tests"]
for g in mnm:
    cmd += ["--must-not-move", g]
sys.exit(subprocess.call(cmd + sys.argv[1:]))
