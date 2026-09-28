"""C7a: only ltA3 (the three-term aligned add, vsh-ff.c:210-243; ltA, ltVA and
ltDp call it) becomes a float add. Cost probe only."""
import sys
from _edit import edit

edit(sys.argv[1], "vsh-ff.c", [
    ('"float ltA3(float x0, float x1, float x2) {\\n"',
     '"float ltA3(float x0, float x1, float x2) { return x0 + x1 + x2; }\\n"\n'
     '        "float ltA3_exact(float x0, float x1, float x2) {\\n"'),
])
