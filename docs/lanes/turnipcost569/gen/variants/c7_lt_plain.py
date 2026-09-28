"""C7: the fixed-function lighting unit's bit-exact arithmetic (vsh-ff.c:128-283,
#224) becomes float32 arithmetic: lt() is identity, ltM/ltsM multiply,
ltA3/ltsA add, ltR is 1/x. The exact versions stay in the source under
*_exact names (uncalled). Cost probe only: this is the approximation #224
replaced, and it is not pixel-inert."""
import sys
from _edit import edit

edit(sys.argv[1], "vsh-ff.c", [
    ('"float lt(float x) { return uintBitsToFloat(ltBits(floatBitsToUint(x))); }\\n"',
     '"float lt(float x) { return x; }\\n"'),
    ('"float ltM(float a, float b) { return ltMulCore(a, b, false); }\\n"',
     '"float ltM(float a, float b) { return a * b; }\\n"'),
    ('"float ltsM(float a, float b) { return ltMulCore(a, b, true); }\\n"',
     '"float ltsM(float a, float b) { return a * b; }\\n"'),
    ('"float ltA3(float x0, float x1, float x2) {\\n"',
     '"float ltA3(float x0, float x1, float x2) { return x0 + x1 + x2; }\\n"\n'
     '        "float ltA3_exact(float x0, float x1, float x2) {\\n"'),
    ('"float ltsA(float fa, float fb) {\\n"',
     '"float ltsA(float fa, float fb) { return fa + fb; }\\n"\n'
     '        "float ltsA_exact(float fa, float fb) {\\n"'),
    ('"float ltR(float fx) {\\n"',
     '"float ltR(float fx) { return 1.0 / fx; }\\n"\n'
     '        "float ltR_exact(float fx) {\\n"'),
])
