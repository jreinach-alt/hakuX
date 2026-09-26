#!/usr/bin/env python3
"""Registers lane.tiecode282's arm 3: arm 2's legs, re-run on the head merged
with master (which now carries #367 y16bump10 and #274).  Run from the
repository root: python3 docs/lanes/tiecode282/register_merge.py A B

Writes docs/testing/predictions/tiecode282-merge.json (the arms job's disc,
23 suites, no skip) and docs/lanes/tiecode282/tiecode282-trt-merge.json
(Texture render target with RenderTextureLoop skipped, queued by hand with
request.sh --skip-tests, because arms.sh does not carry skip_tests until
#386 folds).
"""
import json
import subprocess
import sys

A, B = sys.argv[1], sys.argv[2]
POW2 = "docs/testing/predictions/tiecode282-pow2.json"
TRT = "docs/lanes/tiecode282/tiecode282-trt.json"
OUT = "docs/testing/predictions/tiecode282-merge.json"
OUT_TRT = "docs/lanes/tiecode282/tiecode282-trt-merge.json"

pow2 = json.load(open(POW2))
trt = json.load(open(TRT))

PRED = (
    "#282/#283 binade v-tie rule with the power-of-two gate, re-run after "
    "merging master (#367 y16bump10, #274 uniform refresh) into the lane. "
    "Arm 2 (e673558587 vs 1462da29d2) passed 375 of 375 checks, 139 better "
    "0 worse. The merge touches psh.c only in the bump paths, which the rule "
    "does not share, so this arm predicts arm 2's legs unchanged: Volume "
    "texture, Texture palette, Material color source and Lighting range "
    "Directional exact; Pixel shader, Texture 3D as 2D, Texture signed and "
    "the other texture suites byte-identical to master; the checkerboard "
    "suites no worse. A leg that fails here and passed in arm 2 is an "
    "interaction with the merged code, not a new reading of the rule."
)
PRED_TRT = (
    "#282 row 240 of Texture render target's BiTri, re-run after merging "
    "master (#367, #274). Arm 2's hand-queued pair took 28 TexFmt_* captures "
    "to exact (1,473 -> 0 px, 40 of 40 exact); this predicts the same: every "
    "one of those 28 at 0 and no capture worse."
)
# The 28 captures arm 2's TRT pair took to exact.
TRT_EXACT = [
    "A8B8G8R8", "A8B8G8R8_L", "A8R8G8B8", "A8R8G8B8_L", "A8Y8", "AY8",
    "AY8_L", "B8G8R8A8", "B8G8R8A8_L", "G8B8", "G8B8_L", "R16B16",
    "R16B16_L", "R8B8", "R8G8B8A8", "R8G8B8A8_L", "SZ_Index8_p128",
    "SZ_Index8_p256", "SZ_Index8_p32", "SZ_Index8_p64", "UYVY_L",
    "X8R8G8B8", "X8R8G8B8_L", "Y16", "Y16_L", "Y8", "Y8_L", "YUY2_L",
]


def register(path, pred, expect, mnm, disc):
    args = [sys.executable, "docs/testing/ab_compare.py", "--register", path,
            "--who", "lane.tiecode282", "--issue", "282",
            "--a-ref", A, "--b-ref", B, "--prediction", pred,
            "--disc-suites", ",".join(disc["suites"])]
    if disc["skip_tests"]:
        args += ["--disc-skip-tests", ",".join(disc["skip_tests"])]
    for k, v in expect.items():
        args += ["--expect-value", f"{k}={v}"]
    for g in mnm:
        args += ["--must-not-move", g]
    subprocess.run(args, check=True)


def add_mnr(path, globs):
    # must_not_regress has no command-line flag; parse and check in memory
    # before writing back.
    exp = json.load(open(path))
    exp["must_not_regress"] = globs
    text = json.dumps(exp, indent=2) + "\n"
    assert json.loads(text) == exp
    open(path, "w").write(text)


register(OUT, PRED, pow2["expect"], pow2["must_not_move"], pow2["disc"])
add_mnr(OUT, pow2["must_not_regress"])

trt_expect = {f"Texture_render_target/TexFmt_{t}": 0 for t in TRT_EXACT}
register(OUT_TRT, PRED_TRT, trt_expect, [], trt["disc"])
add_mnr(OUT_TRT, trt["must_not_regress"])
print("registered", OUT, OUT_TRT)
