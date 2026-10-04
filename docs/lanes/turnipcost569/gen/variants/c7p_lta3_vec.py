"""C7p: Phase B prototype. ltA3 rewritten loop-free and vectorised, meant to be
BIT-EXACT with vsh-ff.c:210-243 (checked on the CPU by gen/lta3_check.c, which
carries the same two functions transcribed to C). The original stays in the
source as ltA3_exact (uncalled). Uses mix(uvec, uvec, bvec) and findMSB, so it
is GLSL 4.50 (the Vulkan path); a GLES 3.00 build would need the old form."""
import sys
from _edit import edit

NEW = r'''        "float ltA3(float x0, float x1, float x2) {\n"
        "  uvec3 v = floatBitsToUint(vec3(x0, x1, x2));\n"
        "  uvec3 mn = v & 0x7FFFFFu;\n"
        "  uvec3 top = uvec3(equal(v & 0x7F800000u, uvec3(0x7F800000u)));\n"
        "  uvec3 hasm = uvec3(notEqual(mn, uvec3(0u)));\n"
        "  uvec3 sgn = v >> 31;\n"
        "  bool anyNan = (top & hasm) != uvec3(0u);\n"
        "  uvec3 infv = top & (1u - hasm);\n"
        "  bool pinf = (infv & (1u - sgn)) != uvec3(0u);\n"
        "  bool ninf = (infv & sgn) != uvec3(0u);\n"
        "  ivec3 e = ivec3(v >> 23 & 0xFFu);\n"
        "  uvec3 m = (mn | (uvec3(notEqual(e, ivec3(0))) << 23)) >> 10;\n"
        "  int er = max(max(e.x, e.y), e.z) + 2;\n"
        "  ivec3 sh = ivec3(er) - e - 7;\n"
        "  uvec3 f = mix(m << uvec3(clamp(-sh, 0, 31)), m >> uvec3(clamp(sh, 0, 31)),\n"
        "                greaterThanEqual(sh, ivec3(0)));\n"
        "  f = mix(f, uvec3(0u), greaterThanEqual(sh, ivec3(32)));\n"
        "  ivec3 fi = ivec3(f);\n"
        "  fi = mix(fi, -fi, notEqual(sgn, uvec3(0u)));\n"
        "  int r = fi.x + fi.y + fi.z;\n"
        "  uint s = r < 0 ? 1u : 0u;\n"
        "  uint u = uint(abs(r));\n"
        "  int sh2 = 20 - findMSB(u);\n"
        "  u <<= uint(sh2);\n"
        "  er -= sh2;\n"
        "  u >>= 7u;\n"
        "  bool big = er >= 255;\n"
        "  float res = ltMk(s, big ? 254 : er, big ? 0x3FFFu : u);\n"
        "  res = r == 0 ? 0.0 : res;\n"
        "  res = (pinf || ninf) ? uintBitsToFloat(LT_INF) : res;\n"
        "  res = (pinf && ninf) ? uintBitsToFloat(LT_NAN) : res;\n"
        "  return anyNan ? uintBitsToFloat(LT_NAN) : res;\n"
        "}\n"
'''

edit(sys.argv[1], "vsh-ff.c", [
    ('        "float ltA3(float x0, float x1, float x2) {\\n"\n',
     NEW + '        "float ltA3_exact(float x0, float x1, float x2) {\\n"\n'),
])
