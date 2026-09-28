"""C7b: only the lighting multiply (ltM/ltsM -> ltMulCore, vsh-ff.c:189-208)
becomes a float multiply. Cost probe only."""
import sys
from _edit import edit

edit(sys.argv[1], "vsh-ff.c", [
    ('"float ltM(float a, float b) { return ltMulCore(a, b, false); }\\n"',
     '"float ltM(float a, float b) { return a * b; }\\n"'),
    ('"float ltsM(float a, float b) { return ltMulCore(a, b, true); }\\n"',
     '"float ltsM(float a, float b) { return a * b; }\\n"'),
])
