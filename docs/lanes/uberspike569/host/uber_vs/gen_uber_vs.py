#!/usr/bin/env python3
"""Generate the full-uber-pipeline VERTEX prototypes for the #569 addendum's C leg.

These shaders measure COST (compile on host Turnip, GPU time on the device). They
are NOT exact against vsh.c, and nothing ships them. Each one is hakuX's own
generated vertex shader text (turnipcost569's vs_ff_lit2_pfx.glsl for the prologue:
uniform block, lt* lighting helpers, the interface; vs_prog_skin4_a0_pfx.glsl for
the MAC/ILU op helpers), with main() replaced by an interpreter driven by
uniforms appended to VshUniforms:

  vp   the NV2A vertex-program interpreter: one loop over up to 136 microcode
       slots (uvec4 each, the field table of glsl/vsh-prog.c:49-88), register
       file as arrays, one MAC switch and one ILU switch per slot.
  ff   the fixed-function path with every VshState field that psh-uber's map calls
       uniformable read at run time: skinning (loop over up to 4 matrices),
       texgen per stage and component, texture matrices, 8 lights in a loop with
       the light type as a uniform (the lit shader's infinite and local bodies),
       fog generation.
  both one shader, `if (vpMode != 0) vp else ff`: what "one uber vertex stage per
       family" means.

  gen_uber_vs.py <template dir> <out dir>
"""
import os
import re
import sys

TPL = sys.argv[1]
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)

lit = open(os.path.join(TPL, "vs_ff_lit2_pfx.glsl")).read()
prog = open(os.path.join(TPL, "vs_prog_skin4_a0_pfx.glsl")).read()

# Prologue: everything before main() of the lit shader.
pro = lit[:lit.index("void main() {")]
# The uber state, appended to the vertex UBO (std140; set 1 binding 0).
pro = pro.replace(
    "vec2 surfaceSize;\n};",
    "vec2 surfaceSize;\n"
    "uvec4 vpProg[136];\n"
    "int vpMode;\n"
    "int ffSkin;\n"
    "int ffLighting;\n"
    "int ffFogGen;\n"
    "ivec4 ffTexgen[4];\n"
    "ivec4 ffTexMatEn;\n"
    "ivec4 ffLightType[2];\n"
    "int ffNumLights;\n"
    "int ffNumTexgen;\n"
    "};", 1)
assert "vpProg" in pro

# The op helpers of the program shader: from "int A0" up to its main().
ops = prog[prog.index("vec4 _temp_vec;"):prog.index("void main() {")]
ops = re.sub(r"#define \w+\(dest.*\n", "", ops)

VP = r"""
uint fld(uvec4 t, int w, int s, int n) { return bitfieldExtract(t[w], s, n); }

vec4 R[13];
vec4 V[16];
vec4 O[16];

vec4 vpSwz(vec4 s, uint sw) {
  return vec4(s[(sw >> 6) & 3u], s[(sw >> 4) & 3u], s[(sw >> 2) & 3u], s[sw & 3u]);
}

vec4 vpFetch(uvec4 t, uint mux, uint reg, uint neg, uint sw, int a0) {
  int ci = int(fld(t, 1, 13, 8));
  if (fld(t, 3, 1, 1) != 0u) { ci += a0; }
  ci = clamp(ci, 0, 191);
  vec4 s = mux == 1u ? R[min(reg, 12u)] : (mux == 2u ? V[fld(t, 1, 9, 4)] : c[ci]);
  s = vpSwz(s, sw);
  return neg != 0u ? -s : s;
}

vec4 vpMask(vec4 d, vec4 v, uint m) {
  return mix(d, v, bvec4((m & 8u) != 0u, (m & 4u) != 0u, (m & 2u) != 0u, (m & 1u) != 0u));
}

void vpRun() {
  V[0] = v0; V[1] = v1; V[2] = v2; V[3] = v3; V[4] = v4; V[5] = v5; V[6] = v6; V[7] = v7;
  V[8] = v8; V[9] = v9; V[10] = v10; V[11] = v11; V[12] = v12; V[13] = v13; V[14] = v14;
  V[15] = v15;
  for (int i = 0; i < 13; i++) { R[i] = vec4(0.0); }
  for (int i = 0; i < 16; i++) { O[i] = vec4(0.0, 0.0, 0.0, 1.0); }
  int a0 = 0;
  for (int pc = 0; pc < 136; pc++) {
    uvec4 t = vpProg[pc];
    uint mac = fld(t, 1, 21, 4);
    uint ilu = fld(t, 1, 25, 3);
    vec4 a = vpFetch(t, fld(t, 2, 26, 2), fld(t, 2, 28, 4), fld(t, 1, 8, 1),
                     fld(t, 1, 0, 8), a0);
    vec4 b = vpFetch(t, fld(t, 2, 11, 2), fld(t, 2, 13, 4), fld(t, 2, 25, 1),
                     fld(t, 2, 17, 8), a0);
    vec4 cc = vpFetch(t, fld(t, 3, 28, 2), (fld(t, 2, 0, 2) << 2) | fld(t, 3, 30, 2),
                      fld(t, 2, 10, 1), fld(t, 2, 2, 8), a0);
    vec4 m = vec4(0.0);
    switch (mac) {
    case 1u: m = _MOV(a); break;
    case 2u: m = _MUL(a, b); break;
    case 3u: m = _ADD(a, cc); break;
    case 4u: m = _MAD(a, b, cc); break;
    case 5u: m = _DP3(a, b); break;
    case 6u: m = _DPH(a, b); break;
    case 7u: m = _DP4(a, b); break;
    case 8u: m = _DST(a, b); break;
    case 9u: m = _MIN(a, b); break;
    case 10u: m = _MAX(a, b); break;
    case 11u: m = _SLT(a, b); break;
    case 12u: m = _SGE(a, b); break;
    case 13u: a0 = _ARL(a.x); break;
    default: break;
    }
    vec4 l = vec4(0.0);
    switch (ilu) {
    case 1u: l = _MOV(cc); break;
    case 2u: l = _RCP(cc.x); break;
    case 3u: l = _RCC(cc.x); break;
    case 4u: l = _RSQ(cc.x); break;
    case 5u: l = _EXP(cc.x); break;
    case 6u: l = _LOG(cc.x); break;
    case 7u: l = _LIT(cc); break;
    default: break;
    }
    uint rr = min(fld(t, 3, 20, 4), 12u);
    if (mac != 0u && mac != 13u) { R[rr] = vpMask(R[rr], m, fld(t, 3, 24, 4)); }
    uint ir = (mac != 0u) ? 1u : rr;
    if (ilu != 0u) { R[ir] = vpMask(R[ir], l, fld(t, 3, 16, 4)); }
    if (fld(t, 3, 11, 1) != 0u) {
      uint oa = fld(t, 3, 3, 8) & 15u;
      O[oa] = vpMask(O[oa], fld(t, 3, 2, 1) != 0u ? l : m, fld(t, 3, 12, 4));
    }
    if (fld(t, 3, 0, 1) != 0u) { break; }
  }
  oPos = R[12] + O[0];
  oD0 = O[3]; oD1 = O[4]; oFog = O[5]; oPts = O[6]; oB0 = O[7]; oB1 = O[8];
  oT0 = O[9]; oT1 = O[10]; oT2 = O[11]; oT3 = O[12];
}

void vpEpilogue() {
  oPos.xy = roundScreenCoords(oPos.xy);
  oPos.w = clampAwayZeroInf(oPos.w);
  vec4 vtxPos = oPos;
  oPos.xy = (2.0 * oPos.xy - surfaceSize) / surfaceSize;
  oPos.z = oPos.z / clipRange.y;
  oPos.xyz *= oPos.w;
  float fogSpecial = 0.0;
  vtxD0 = colorPrecision(clamp(NaNToSignedOne(oD0), 0.0, 1.0));
  vtxB0 = colorPrecision(clamp(NaNToSignedOne(oB0), 0.0, 1.0));
  vtxD1 = colorPrecision(clamp(NaNToSignedOne(oD1), 0.0, 1.0));
  vtxB1 = colorPrecision(clamp(NaNToSignedOne(oB1), 0.0, 1.0));
  vtxFog = oFog.x;
  vtxFogSpecial = fogSpecial;
  vtxT0 = oT0; vtxT1 = oT1; vtxT2 = oT2; vtxT3 = oT3;
  vtxPos0 = vtxPos; vtxPos1 = vtxPos; vtxPos2 = vtxPos;
  triMZ = 0.0;
  vtxPointSize = oPts.x;
  gl_PointSize = oPts.x;
  gl_Position = oPos;
}
"""

FF = r"""
mat4 ffMat(int base) { return mat4(c[base], c[base + 1], c[base + 2], c[base + 3]); }

vec4 ffTexgenOne(int mode, int s, int comp, vec4 tex, vec4 tPos, vec3 tN, vec3 refl,
                 vec2 sphere) {
  int pl = 0x40 + s * 8 + comp;
  switch (mode) {
  case 1: return vec4(dot(position, c[pl]));             /* object linear */
  case 2: return vec4(dot(tPos, c[pl + 4]));             /* eye linear */
  case 3: return vec4(comp < 2 ? sphere[comp] : 0.0);    /* sphere map */
  case 4: return vec4(refl[min(comp, 2)]);               /* reflection map */
  case 5: return vec4(tN[min(comp, 2)]);                 /* normal map */
  default: return vec4(tex[comp]);                       /* passthrough */
  }
}

void ffRun() {
  vec4 tPosition = vec4(0.0);
  vec3 tNormal = vec3(0.0);
  int nm = max(ffSkin, 1);
  float wsum = 0.0;
  for (int i = 0; i < 4; i++) {
    if (i >= nm) break;
    float w = (i == nm - 1 && nm > 1) ? 1.0 - wsum : (nm > 1 ? weight[i] : 1.0);
    wsum += w;
    tPosition += (position * ffMat(0x08 + i * 8)) * w;
    tNormal += (vec4(normal, 0.0) * ffMat(0x0c + i * 8)).xyz * w;
  }
  tNormal = normalize(tNormal);
  vec3 eyeV = normalize(tPosition.xyz);
  vec3 refl = reflect(eyeV, tNormal);
  float sm = 2.0 * length(refl + vec3(0.0, 0.0, 1.0));
  vec2 sphere = refl.xy / sm + 0.5;
  vec4 texIn[4] = vec4[4](texture0, texture1, texture2, texture3);
  /* One texgen body, run ffNumTexgen (16) times: a uniform trip count, so NIR
   * cannot unroll it into 16 switch copies (section 5.1's lesson). */
  vec4 oT[4] = texIn;
  for (int k = 0; k < ffNumTexgen; k++) {
    int s = k >> 2, comp = k & 3;
    oT[s][comp] = ffTexgenOne(ffTexgen[s][comp], s, comp, texIn[s], tPosition, tNormal, refl,
                              sphere).x;
  }
  for (int s = 0; s < 4; s++) {
    if (ffTexMatEn[s] != 0) { oT[s] = oT[s] * ffMat(0x44 + s * 8); }
  }
  oT0 = oT[0]; oT1 = oT[1]; oT2 = oT[2]; oT3 = oT[3];
  vec4 ltDiffuse = lt(diffuse);
  oD0 = vec4(sceneAmbientColor, diffuse.a);
  oD1 = vec4(0.0, 0.0, 0.0, specular.a);
  if (ffLighting != 0) {
    vec3 N = lt(tNormal);
    vec3 ltEye = lt(eyeDirection);
    vec3 tPos = tPosition.xyz / tPosition.w;
    for (int i = 0; i < ffNumLights; i++) {
      int type = ffLightType[i >> 2][i & 3];
      if (type == 0) continue;
      float ca = 1.0;
      vec3 lv;
      vec3 hi;
      bool inRange = true;
      if (type == 1) {
        lv = lt(lightInfiniteDirection[i]);
        hi = lt(lightInfiniteHalfVector[i]);
      } else {
        vec3 VP = lightLocalPosition[i] - tPos;
        float d = length(VP);
        inRange = d <= lightLocalRange(i);
        lv = lt(normalize(VP));
        ca = ltR(ltDp(vec3(1.0, lt(d), lt(d * d)), lt(lightLocalAttenuation[i])));
        hi = ltVA(ltEye, lv);
      }
      if (!inRange) continue;
      vec3 k = lt(specularParams[i & 3]);
      bool zero = false;
      float cd = ltDp(N, lv);
      if (cd < 0.0) { zero = true; cd = 0.0; }
      cd = ltM(ca, cd);
      float hd = ltDp(hi, hi);
      float s = ltDp(N, hi);
      if (s < 0.0) zero = true;
      float ss = ltsM(s, s);
      float t = ltsA(ss, ltsM(hd, k.x));
      if (t < 0.0) zero = true;
      float b = ltsA(ltsA(ltsM(ss, k.y), 0.0), ltsM(hd, k.z));
      float cs = zero ? 0.0 : ltM(ca, ltsM(t, ltR(b)));
      oD0.xyz = ltVA(oD0.xyz, ltVM(vec3(ca), lightAmbientColor(i)));
      oD0.xyz = ltVA(oD0.xyz, ltVM(ltVM(vec3(cd), lightDiffuseColor(i)), ltDiffuse.rgb));
      oD1.xyz = ltVA(oD1.xyz, ltVM(vec3(cs), lightSpecularColor(i)));
    }
  }
  float fogDistance = ffFogGen == 1 ? length(tPosition.xyz)
                    : ffFogGen == 2 ? abs(tPosition.z)
                    : ffFogGen == 3 ? dot(tPosition, fogPlane) : fogCoord;
  tPosition = position;
  oPos = tPosition * compositeMat;
  oPos.w = clampAwayZeroInf(oPos.w);
  vec2 hPos = oPos.xy;
  vec2 scrPos = oPos.xy / oPos.w + c[0x3b].xy;
  oPos.xy = roundScreenCoords(scrPos);
  vec4 vtxPos = vec4(oPos.xy, oPos.z / oPos.w, oPos.w);
  oPos.z = oPos.z / clipRange.y;
  oPos.xy = (2.0 * oPos.xy - surfaceSize) / surfaceSize;
  oPos.xy *= oPos.w;
  bvec2 carry = not(lessThan(abs(scrPos), vec2(524288.0)));
  oPos.xy = mix(oPos.xy, 2.0 * hPos / surfaceSize
      + (2.0 * c[0x3b].xy / surfaceSize - 1.0) * oPos.w, carry);
  if (clipRange.y <= 16777216.0) {
    vtxPos.z = ffScreenZ(tPosition);
  }
  float fogSpecial = 0.0;
  if (isnan(fogDistance)) { fogSpecial = 1.0; oFog = vec4(0.0); }
  else if (isinf(fogDistance)) { fogSpecial = 2.0; oFog = vec4(0.0); }
  else { oFog = vec4(fogDistance); }
  vtxD0 = colorPrecision(clamp(NaNToSignedOne(oD0), 0.0, 1.0));
  vtxB0 = colorPrecision(clamp(NaNToSignedOne(oB0), 0.0, 1.0));
  vtxD1 = colorPrecision(clamp(NaNToSignedOne(oD1), 0.0, 1.0));
  vtxB1 = colorPrecision(clamp(NaNToSignedOne(oB1), 0.0, 1.0));
  vtxFog = oFog.x;
  vtxFogSpecial = fogSpecial;
  vtxT0 = oT0; vtxT1 = oT1; vtxT2 = oT2; vtxT3 = oT3;
  vtxPos0 = vtxPos; vtxPos1 = vtxPos; vtxPos2 = vtxPos;
  triMZ = 0.0;
  vtxPointSize = 1.0;
  gl_PointSize = 1.0;
  gl_Position = oPos;
}
"""

MAINS = {
    "vp": "void main() {\n  vpRun();\n  vpEpilogue();\n}\n",
    "ff": "void main() {\n  ffRun();\n}\n",
    "both": "void main() {\n  if (vpMode != 0) {\n    vpRun();\n    vpEpilogue();\n"
            "  } else {\n    ffRun();\n  }\n}\n",
}
for name, main in MAINS.items():
    body = pro + ops + (VP if name != "ff" else "") + (FF if name != "vp" else "") + main
    path = os.path.join(OUT, "vs_uber_%s.glsl" % name)
    open(path, "w").write(body)
    print(path, len(body))
