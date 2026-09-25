#!/usr/bin/env python3
"""Emit vsh-ff.c's lighting GLSL for a set of VshStates and compile each with
the NDK's glslc (Vulkan 450) under a stub prelude. Syntax/type check only."""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GLSLC = '/home/justin/Android/Sdk/ndk/29.0.14206865/shader-tools/linux-x86_64/glslc'

PRELUDE = r'''
#define FLOAT_MAX uintBitsToFloat(0x7F7FFFFFu)
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
layout(location = 0) out vec4 outc;
vec4 oPos = vec4(0.0); vec4 oD0 = vec4(0.0); vec4 oD1 = vec4(0.0);
vec4 oB0 = vec4(0.0); vec4 oB1 = vec4(0.0); vec4 oPts = vec4(0.0);
vec4 oFog = vec4(0.0); vec4 oT0 = vec4(0.0); vec4 oT1 = vec4(0.0);
vec4 oT2 = vec4(0.0); vec4 oT3 = vec4(0.0);
'''


def emit(args):
    out = subprocess.run([os.path.join(HERE, 'emit')] + [str(a) for a in args],
                         capture_output=True, text=True, check=True).stdout
    h = out.split('//HEADER\n', 1)[1].split('//BODY\n', 1)
    return h[0], h[1]


def compile_one(args, prog):
    header, body = emit(list(args) + [prog])
    # The lighting part only: the FF body also does transforms, texgen and
    # fog, which reference registers this prelude does not stub. Cut the
    # body down to the lighting block when it is the FF path.
    if not prog:
        start = body.index('  vec4 ltDiffuse = lt(diffuse);')
        # scan from the start: depth counts braces; end after the depth
        # returns to 0 following the last light block
        last = body.rindex('/* Light')
        depth, end = 0, None
        for i in range(start, len(body)):
            ch = body[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and i > last:
                    end = i + 1
                    break
        body = ('  vec4 tPosition = v0; vec3 tNormal = v2.xyz;\n'
                '#define diffuse v3\n#define specular v4\n'
                + body[start:end] + '\n')
        hstart = header.index('#define modelViewMat0') if '#define modelViewMat0' in header else 0
        header = header[hstart:]
    else:
        body = body.replace('{\n  vec4 ltDiffuse', '{\n  vec4 ltDiffuse', 1)
    src = ('#version 450\n' + PRELUDE + header + '\nvoid main() {\n' + body
           + '\n  outc = oD0 + oD1 + oB0 + oB1;\n}\n')
    path = os.path.join(HERE, 'x.vert')
    open(path, 'w').write(src)
    r = subprocess.run([GLSLC, '-o', os.devnull, path], capture_output=True,
                       text=True)
    return r.returncode, r.stderr


if __name__ == '__main__':
    bad = 0
    # light0 light1 local_eye sep spec two_side vc ; LIGHT_OFF 0, INFINITE 1,
    # LOCAL 2, SPOT 3 (check vsh.h enum if this fails)
    for l0, l1 in ((1, 0), (2, 0), (3, 0), (1, 2), (1, 3)):
        for le in (0, 1):
            for sep, spe in ((1, 1), (0, 1), (1, 0)):
                for ts in (0, 1):
                    for vc in (0, 1):
                        for prog in (0, 1):
                            a = (l0, l1, le, sep, spe, ts, vc)
                            rc, err = compile_one(a, prog)
                            if rc:
                                bad += 1
                                if True:
                                    print(a, prog, err.splitlines()[0][-90:])
    print('failed', bad)
    sys.exit(1 if bad else 0)
