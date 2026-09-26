"""Register docs/testing/predictions/yuv10-csc.json. The must-not-move list is
every Bump_map and Bump_env_lum capture but the four YUV ones, read from a
full-suite arm (1790404182-arms-y16bump10-fix, master-era), because a glob
cannot exclude."""
import subprocess, sys

TSV = "/home/justin/hakux-work/dispatch/results/1790404182-arms-y16bump10-fix-2554339/scores1.tsv"
YUV = {"Bump_map/BumpMap_YUY2_L", "Bump_map/BumpMap_UYVY_L",
       "Bump_env_lum/BumpEnvLum_YUY2_L", "Bump_env_lum/BumpEnvLum_UYVY_L"}
A_REF, B_REF = sys.argv[1], sys.argv[2]

keys = []
for line in open(TSV):
    p = line.rstrip("\n").split("\t")
    if len(p) > 4 and p[0] in ("Bump_map", "Bump_env_lum"):
        keys.append("%s/%s" % (p[0], p[1]))
assert YUV <= set(keys), YUV - set(keys)
still = sorted(k for k in keys if k not in YUV)

prediction = (
    "#10 SET_CONTROL0 colour-space conversion as measured on the console "
    "(docs/testing/xbox-csc-2026-09-26.md): raw YUY2/UYVY fetch, every "
    "fetched stage converted after the texture shader (util.h converter, red "
    "constant 128), luminance product truncated first. The four YUV bump "
    "captures fall from 111,496 to the sign-label floor their A8/Y8 siblings "
    "already sit at on device, 1,576 (310/422/422/422); the brief's "
    "acceptance is <= 2,000 each, and csc_measured_model.py's 1,688 is the "
    "same floor measured without labels drawn. TexFmt_YUY2_L/UYVY_L set the "
    "field (pbkitplusplus nv2astate.cpp) and stay 0 via the shader "
    "converter: kr 127 and 128 differ only at Cr = 0, which the harness "
    "never writes. Every other Bump capture sets no field and is untouched.")

cmd = [sys.executable, "docs/testing/ab_compare.py",
       "--register", "docs/testing/predictions/yuv10-csc.json",
       "--who", "lane.yuv10", "--issue", "10",
       "--prediction", prediction,
       "--a-ref", A_REF, "--b-ref", B_REF,
       "--disc-suites", "Bump env lum,Bump map,Texture format"]
for k in sorted(YUV):
    cmd += ["--expect-value", "%s=1576" % k]
for k in still + ["Texture_format/TexFmt_YUY2_L", "Texture_format/TexFmt_UYVY_L"]:
    cmd += ["--must-not-move", k]
sys.exit(subprocess.call(cmd + sys.argv[3:]))
