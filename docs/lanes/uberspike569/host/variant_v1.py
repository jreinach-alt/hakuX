#!/usr/bin/env python3
"""Rewrite a generated ubershader into the FIRST interpreter design (one
straight-line stage body: both products computed, dot/mul chosen by select,
the output mapping by switch), for the C leg's compile-cost comparison.

    variant_v1.py IN.frag OUT.frag

Only ubStage() is replaced (and its helpers added); everything else, the
psh.c text included, is the shipped generator's. The shipped generator
branches each stage half on its shape instead (psh-uber.c, gen_half()).
"""
import sys

V1 = r'''vec3 ubOut3(vec3 x, uint m) {
    switch (m & 0x38u) {
    case 0x00u: return x;
    case 0x08u: return (x - 0.5);
    case 0x10u: return (x * 2.0);
    case 0x18u: return ((x - 0.5) * 2.0);
    case 0x20u: return (x * 4.0);
    case 0x28u: return ((x - 0.5) * 4.0);
    case 0x30u: return (x / 2.0);
    default: return ((x - 0.5) / 2.0);
    }
}

float ubOut1(float x, uint m) {
    switch (m & 0x38u) {
    case 0x00u: return x;
    case 0x08u: return (x - 0.5);
    case 0x10u: return (x * 2.0);
    case 0x18u: return ((x - 0.5) * 2.0);
    case 0x20u: return (x * 4.0);
    case 0x28u: return ((x - 0.5) * 4.0);
    case 0x30u: return (x / 2.0);
    default: return ((x - 0.5) / 2.0);
    }
}

void ubStage(uint s) {
    uvec4 w = ubComb[s];
    bool muxCd = (ubComb[8].z & 0x100u) != 0u ? ubR0.a >= 0.5
                                              : (uint(ubR0.a * 255.0) & 1u) == 1u;
    uint ro = w.y;
    uint rf = ro >> 12;
    vec3 ra = ubInRgb(w.x >> 24, s);
    vec3 rb = ubInRgb((w.x >> 16) & 0xFFu, s);
    vec3 rc = ubInRgb((w.x >> 8) & 0xFFu, s);
    vec3 rd = ubInRgb(w.x & 0xFFu, s);
    vec3 rab = (rf & 2u) != 0u ? vec3(dot(ra, rb)) : (ra * rb);
    vec3 rcd = (rf & 1u) != 0u ? vec3(dot(rc, rd)) : (rc * rd);
    vec3 rms = (rf & 4u) != 0u ? (muxCd ? rcd : rab) : (rab + rcd);
    vec3 rabO = clamp(ubOut3(rab, rf), -1.0, 1.0);
    vec3 rcdO = clamp(ubOut3(rcd, rf), -1.0, 1.0);
    vec3 rmsO = clamp(ubOut3(rms, rf), -1.0, 1.0);
    uint ao = w.w;
    uint af = ao >> 12;
    float aa = ubInA(w.z >> 24, s);
    float ab = ubInA((w.z >> 16) & 0xFFu, s);
    float ac = ubInA((w.z >> 8) & 0xFFu, s);
    float ad = ubInA(w.z & 0xFFu, s);
    float aab = aa * ab;
    float acd = ac * ad;
    float ams = (af & 4u) != 0u ? (muxCd ? acd : aab) : (aab + acd);
    float aabO = clamp(ubOut1(aab, af), -1.0, 1.0);
    float acdO = clamp(ubOut1(acd, af), -1.0, 1.0);
    float amsO = clamp(ubOut1(ams, af), -1.0, 1.0);
    uint rAb = (ro >> 4) & 0xFu, rCd = ro & 0xFu, rMs = (ro >> 8) & 0xFu;
    ubWriteRgb(rAb, rabO);
    if ((rf & 0x80u) != 0u) ubWriteA(rAb, rabO.b);
    ubWriteRgb(rCd, rcdO);
    if ((rf & 0x40u) != 0u) ubWriteA(rCd, rcdO.b);
    ubWriteRgb(rMs, rmsO);
    uint aAb = (ao >> 4) & 0xFu, aCd = ao & 0xFu, aMs = (ao >> 8) & 0xFu;
    ubWriteA(aAb, aabO);
    ubWriteA(aCd, acdO);
    ubWriteA(aMs, amsO);
}

'''

src = open(sys.argv[1]).read()
a = src.index("void ubStage(uint s) {")
b = src.index("vec4 ubRun() {")
open(sys.argv[2], "w").write(src[:a] + V1 + src[b:])
