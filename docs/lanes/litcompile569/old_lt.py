"""old_lt: the harness's A side for #569 B1. Turns the GLSL 4.50 lighting
helpers off in the carved vsh-ff.c, so the #else branch (the forms master
ships, unchanged) is what the Vulkan build compiles. Install it as
gen/variants/old_lt.py in lane.turnipcost569's harness."""
import sys
from _edit import edit

edit(sys.argv[1], "vsh-ff.c", [
    ('"#if __VERSION__ >= 450\\n"', '"#if 0\\n"'),
])
