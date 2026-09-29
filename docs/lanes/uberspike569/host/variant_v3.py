#!/usr/bin/env python3
"""Rewrite a generated ubershader into a LEAN interpreter, for the C leg's
compile-cost floor: the register file is an array indexed by the register
code (no read or write switch), input and output mappings are arithmetic
(no switch), and a stage is one straight-line body.

    variant_v3.py IN.frag OUT.frag

Not exact against psh.c in the ways the shipped generator tries to be (it
selects dot/mul and mux/sum by value); this prices the lightest interpreter
worth building, to say whether ANY interpreter compiles cheaply on Turnip.
"""
import sys

V3 = r'''vec4 ubRf[16];

vec3 ubIn3(uint b, uint s) {
    vec4 r = ubRf[b & 0xFu];
    vec3 x = (b & 0x10u) != 0u ? r.aaa : r.rgb;
    uint m = (b >> 5) & 7u;
    vec3 base = m == 1u ? clamp(x, 0.0, 1.0) : (m >= 6u ? x : max(x, 0.0));
    float k = ubMapK[m], o = ubMapO[m];
    return base * k + o;
}

float ubIn1(uint b, uint s) {
    vec4 r = ubRf[b & 0xFu];
    float x = (b & 0x10u) != 0u ? r.a : r.b;
    uint m = (b >> 5) & 7u;
    float base = m == 1u ? clamp(x, 0.0, 1.0) : (m >= 6u ? x : max(x, 0.0));
    return base * ubMapK[m] + ubMapO[m];
}

void ubLoad(uint s) {
    uint cc = ubComb[8].z, fin = ubComb[8].y;
    ubRf[1] = consts[((cc & 0x1000u) != 0u || s == 8u) ? s * 2u : 0u];
    ubRf[2] = consts[((cc & 0x10000u) != 0u || s == 8u) ? s * 2u + 1u : 1u];
    vec3 v1 = (fin & 0x40u) != 0u ? 1.0 - ubRf[5].rgb : ubRf[5].rgb;
    vec3 r0 = (fin & 0x20u) != 0u ? 1.0 - ubRf[12].rgb : ubRf[12].rgb;
    ubRf[14] = (fin & 0x80u) != 0u ? clamp(vec4(v1 + r0, 0.0), 0.0, 1.0)
                                   : vec4(v1 + r0, 0.0);
    ubRf[15] = s == 8u ? vec4(ubE * ubF, 0.0) : vec4(0.0);
}

void ubStage(uint s) {
    ubLoad(s);
    uvec4 w = ubComb[s];
    bool muxCd = (ubComb[8].z & 0x100u) != 0u ? ubRf[12].a >= 0.5
                                              : (uint(ubRf[12].a * 255.0) & 1u) == 1u;
    uint rf = w.y >> 12, af = w.w >> 12;
    float rbias = (rf & 8u) != 0u ? 0.5 : 0.0, abias = (af & 8u) != 0u ? 0.5 : 0.0;
    float rsc = ubScale[(rf >> 4) & 3u], asc = ubScale[(af >> 4) & 3u];
    vec3 ra = ubIn3(w.x >> 24, s), rb = ubIn3((w.x >> 16) & 0xFFu, s);
    vec3 rc = ubIn3((w.x >> 8) & 0xFFu, s), rd = ubIn3(w.x & 0xFFu, s);
    vec3 rab = (rf & 2u) != 0u ? vec3(dot(ra, rb)) : ra * rb;
    vec3 rcd = (rf & 1u) != 0u ? vec3(dot(rc, rd)) : rc * rd;
    vec3 rms = (rf & 4u) != 0u ? (muxCd ? rcd : rab) : rab + rcd;
    float aa = ubIn1(w.z >> 24, s), ab = ubIn1((w.z >> 16) & 0xFFu, s);
    float ac = ubIn1((w.z >> 8) & 0xFFu, s), ad = ubIn1(w.z & 0xFFu, s);
    float aab = aa * ab, acd = ac * ad;
    float ams = (af & 4u) != 0u ? (muxCd ? acd : aab) : aab + acd;
    vec3 rabO = clamp((rab - rbias) * rsc, -1.0, 1.0);
    vec3 rcdO = clamp((rcd - rbias) * rsc, -1.0, 1.0);
    vec3 rmsO = clamp((rms - rbias) * rsc, -1.0, 1.0);
    float aabO = clamp((aab - abias) * asc, -1.0, 1.0);
    float acdO = clamp((acd - abias) * asc, -1.0, 1.0);
    float amsO = clamp((ams - abias) * asc, -1.0, 1.0);
    /* Unwritable destinations land in slot 0, which every read of register
     * 0 overwrites with zero on the next ubLoad-free read: keep it zero. */
    uint rAb = (w.y >> 4) & 0xFu, rCd = w.y & 0xFu, rMs = (w.y >> 8) & 0xFu;
    uint aAb = (w.w >> 4) & 0xFu, aCd = w.w & 0xFu, aMs = (w.w >> 8) & 0xFu;
    rAb = ubWritable(rAb) ? rAb : 6u; rCd = ubWritable(rCd) ? rCd : 6u;
    rMs = ubWritable(rMs) ? rMs : 6u; aAb = ubWritable(aAb) ? aAb : 6u;
    aCd = ubWritable(aCd) ? aCd : 6u; aMs = ubWritable(aMs) ? aMs : 6u;
    ubRf[rAb].rgb = rabO;
    if ((rf & 0x80u) != 0u) ubRf[rAb].a = rabO.b;
    ubRf[rCd].rgb = rcdO;
    if ((rf & 0x40u) != 0u) ubRf[rCd].a = rcdO.b;
    ubRf[rMs].rgb = rmsO;
    ubRf[aAb].a = aabO;
    ubRf[aCd].a = acdO;
    ubRf[aMs].a = amsO;
    ubRf[6] = vec4(0.0);
}

vec4 ubRun() {
    ubRf[0] = vec4(0.0); ubRf[6] = vec4(0.0); ubRf[7] = vec4(0.0);
    ubRf[3] = ubFog; ubRf[4] = ubV0; ubRf[5] = ubV1;
    ubRf[8] = ubT0; ubRf[9] = ubT1; ubRf[10] = ubT2; ubRf[11] = ubT3;
    ubRf[12] = ubR0; ubRf[13] = ubR1;
    uint n = min(ubComb[8].z & 0xFFu, 8u);
    for (uint s = 0u; s < n; s++) {
        ubStage(s);
    }
    uint f0 = ubComb[8].x, f1 = ubComb[8].y;
    ubLoad(8u);
    ubE = ubIn3(f1 >> 24, 8u);
    ubF = ubIn3((f1 >> 16) & 0xFFu, 8u);
    ubLoad(8u);
    vec3 fa = ubIn3(f0 >> 24, 8u), fb = ubIn3((f0 >> 16) & 0xFFu, 8u);
    vec3 fc = ubIn3((f0 >> 8) & 0xFFu, 8u), fd = ubIn3(f0 & 0xFFu, 8u);
    float fg = ubIn1((f1 >> 8) & 0xFFu, 8u);
    return vec4(fd + mix(vec3(fc), vec3(fb), vec3(fa)), fg);
}

'''

CONSTS = r'''const float ubMapK[8] = float[](1.0, -1.0, 2.0, -2.0, 1.0, -1.0, 1.0, -1.0);
const float ubMapO[8] = float[](0.0, 1.0, -1.0, 1.0, -0.5, 0.5, 0.0, 0.0);
const float ubScale[4] = float[](1.0, 2.0, 4.0, 0.5);
'''

src = open(sys.argv[1]).read()
# Keep the globals and ubWritable; drop everything else the generator put
# between the prelude's globals and main().
g = src.index("vec3 ubE, ubF;\n") + len("vec3 ubE, ubF;\n")
w0 = src.index("bool ubWritable(uint reg) {")
w1 = src.index("}\n", w0) + 2
m = src.index("void main() {")
out = src[:g] + CONSTS + src[w0:w1] + "\n" + V3 + src[m:]
open(sys.argv[2], "w").write(out)
