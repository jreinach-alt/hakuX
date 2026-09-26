#!/usr/bin/env python3
"""Compile the whole vsh-ff.c fixed-function vertex shader (header + body,
lighting off and on, skinning off and on) with the NDK's glslc, under a stub
prelude that declares what vsh.c normally supplies.  Then a mutant of the
new position tail, which must be rejected (so a pass means glslc read it).

Build first: bash vshemit/build.sh.  Syntax/type check only.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GLSLC = ('/home/justin/Android/Sdk/ndk/29.0.14206865/shader-tools/'
         'linux-x86_64/glslc')
SCRATCH = os.path.join(HERE, "..", "..", "..", "..", ".scratch")

PRELUDE = r'''
layout(std140, binding = 0) uniform U {
  vec4 c[192];
  vec4 ltctxa[26];
  vec4 ltctxb[52];
  vec4 ltc1[20];
  vec3 lightInfiniteHalfVector[8];
  vec3 lightInfiniteDirection[8];
  vec3 lightLocalPosition[8];
  vec3 lightLocalAttenuation[8];
  vec3 specularParams[4];
  float material_alpha;
  float material_alpha_back;
  vec4 texMat0; vec4 texMat1; vec4 texMat2; vec4 texMat3;
  vec2 surfaceSize;
  vec2 clipRange;
  vec4 fogPlane;
  float pointParams[8];
};
layout(location = 0) in vec4 v0;
layout(location = 1) in vec4 v1;
layout(location = 2) in vec4 v2;
layout(location = 3) in vec4 v3;
layout(location = 4) in vec4 v4;
layout(location = 5) in vec4 v5;
layout(location = 6) in vec4 v6;
layout(location = 7) in vec4 v7;
layout(location = 8) in vec4 v8;
layout(location = 9) in vec4 v9;
layout(location = 10) in vec4 v10;
layout(location = 11) in vec4 v11;
layout(location = 12) in vec4 v12;
layout(location = 13) in vec4 v13;
layout(location = 14) in vec4 v14;
layout(location = 15) in vec4 v15;
layout(location = 0) out vec4 outc;
vec4 oPos = vec4(0.0); vec4 oD0 = vec4(0.0); vec4 oD1 = vec4(0.0);
vec4 oB0 = vec4(0.0); vec4 oB1 = vec4(0.0); vec4 oPts = vec4(0.0);
vec4 oFog = vec4(0.0); vec4 oT0 = vec4(0.0); vec4 oT1 = vec4(0.0);
vec4 oT2 = vec4(0.0); vec4 oT3 = vec4(0.0);
#define FLOAT_MAX uintBitsToFloat(0x7F7FFFFFu)
float clampAwayZeroInf(float t) {
  if (t > 0.0 || floatBitsToUint(t) == 0u) {
    t = clamp(t, uintBitsToFloat(0x1F800000u), uintBitsToFloat(0x5F800000u));
  } else {
    t = clamp(t, uintBitsToFloat(0xDF800000u), uintBitsToFloat(0x9F800000u));
  }
  return t;
}
vec2 roundScreenCoords(vec2 pos) {
  return trunc(pos * 16.0) / 16.0;
}
'''

EPILOGUE = ('\n  outc = oPos + oD0 + oD1 + oB0 + oB1 + oT0 + oFog + oPts'
            ' + vtxPos;\n}\n')


def emit(skinning, lighting):
    out = subprocess.run([os.path.join(HERE, 'emit'), str(skinning),
                          str(lighting)], capture_output=True, text=True,
                         check=True).stdout
    h = out.split('//HEADER\n', 1)[1].split('//BODY\n', 1)
    return h[0], h[1]


def compile_src(src, name, env):
    path = os.path.join(SCRATCH, name + '.vert')
    with open(path, 'w') as fh:
        fh.write(src)
    args = [GLSLC, '-fshader-stage=vert', '-o', os.devnull, path]
    if env == 'opengl':
        args[1:1] = ['--target-env=opengl', '-fauto-map-locations']
    else:
        args[1:1] = ['--target-env=vulkan1.0']
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, r.stderr


def build(skinning, lighting, mutate=None):
    header, body = emit(skinning, lighting)
    if mutate:
        assert mutate[0] in body, mutate
        body = body.replace(mutate[0], mutate[1], 1)
    return '#version 450\n' + PRELUDE + header + '\nvoid main() {\n' + \
        body + EPILOGUE


def main():
    os.makedirs(SCRATCH, exist_ok=True)
    bad = 0
    n = 0
    for skinning in (0, 1):
        for lighting in (0, 1):
            src = build(skinning, lighting)
            assert 'bvec2 carry' in src and 'mat4 cm = compositeMat' in src
            for env in ('vulkan', 'opengl'):
                n += 1
                rc, err = compile_src(src, 'ff_s%d_l%d' % (skinning, lighting),
                                      env)
                print('skinning=%d lighting=%d %-6s %s' % (
                    skinning, lighting, env, 'OK' if rc == 0 else
                    'FAIL ' + err.strip().splitlines()[0][-120:]))
                bad += rc != 0
    # Mutant: a vec3 from a vec4 product must not type-check.
    src = build(0, 0, ('vec4 p = tPosition * cm[j];',
                       'vec3 p = tPosition * cm[j];'))
    rc, err = compile_src(src, 'ff_mutant', 'vulkan')
    print('mutant (vec3 p) %s' % ('REJECTED' if rc else 'ACCEPTED (!)'))
    print('compiled %d/%d' % (n - bad, n))
    return 1 if bad or rc == 0 else 0


if __name__ == '__main__':
    sys.exit(main())
