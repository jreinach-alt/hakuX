#!/usr/bin/env python3
"""The exact --register call for dpforce345-inert-finite.json, kept so the
prediction can be re-registered on new refs without retyping it.

    register.py <prediction-text-file> <a_ref> <b_ref> [--force]
"""
import subprocess
import sys

SUITES = [
    "Lighting_Two_Sided", "Lighting_accumulation", "Lighting_control",
    "Lighting_normals", "Lighting_range", "Lighting_spotlight",
    "Vertex_shader_independence_tests", "Vertex_shader_rounding_tests",
    "Vertex_shader_swizzle_tests",
    "Attrib_float",
    "Fog_vsh", "Fog_exceptional_value", "Fog_inf_coord",
]

text_file, a_ref, b_ref = sys.argv[1:4]
with open(text_file) as fh:
    text = fh.read().strip()
cmd = [sys.executable, "docs/testing/ab_compare.py",
       "--register", "docs/testing/predictions/dpforce345-inert-finite.json",
       "--who", "lane.dpforce345", "--issue", "345",
       "--prediction", text, "--a-ref", a_ref, "--b-ref", b_ref,
       "--disc-suites", ",".join(SUITES)]
# Vertex_shader_rounding_tests/GeometrySuperscreen_* is left unguarded: its
# nine captures drift between single runs of one build (off the modal image in
# the base arms of vshnobegin242 and of this lane's first arm, neither of
# which had this hunk). superscreen_hashes.py shows it; NOTES.md has the table.
ROUNDING_GUARDS = ["[!G]*", "Geometry_*", "GeometrySubscreen_*"]
for s in SUITES:
    if s == "Vertex_shader_rounding_tests":
        cmd += [a for g in ROUNDING_GUARDS for a in ("--must-not-move", s + "/" + g)]
    else:
        cmd += ["--must-not-move", s + "/*"]
cmd += sys.argv[4:]
sys.exit(subprocess.call(cmd))
