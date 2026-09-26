#!/usr/bin/env python3
"""Compile the fixed-function vertex shader with the RTZ screen z, using
wparamcode223's emitter and glslc harness, and show the new code is what was
compiled: the helpers and the vtxPos.z statement are present in every
variant, and a type mutant of each is rejected.

Build first: bash docs/lanes/wparamcode223/vshemit/build.sh
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'wparamcode223', 'vshemit'))
import check  # noqa: E402

NEEDLES = ('float ffRcpRtz(float w)', 'float ffScreenZ(vec4 p)',
           'vtxPos.z = ffScreenZ(tPosition);')
MUTANTS = (
    ('body', 'vtxPos.z = ffScreenZ(tPosition);',
     'vtxPos.z = ffScreenZ(tPosition.xyz);'),
    ('header', 'return ffMulRtz(ffDotRtz(p, cm[2]), ffRcpRtz(w));',
     'return ffMulRtz(ffDotRtz(p.xyz, cm[2]), ffRcpRtz(w));'),
    ('header', 'precise float r = 1.0 / aw;', 'precise float r = 1.0 / p;'),
)


def main():
    os.makedirs(check.SCRATCH, exist_ok=True)
    bad = 0
    for skinning in (0, 1):
        for lighting in (0, 1):
            header, body = check.emit(skinning, lighting)
            src = header + body
            missing = [n for n in NEEDLES if n not in src]
            ok = not missing
            for env in ('vulkan', 'opengl'):
                rc, err = check.compile_src(
                    check.build(skinning, lighting),
                    'rtz_s%d_l%d' % (skinning, lighting), env)
                ok = ok and rc == 0
                print('skinning=%d lighting=%d %-6s %s %s' % (
                    skinning, lighting, env, 'OK' if rc == 0 else 'FAIL',
                    ('missing ' + repr(missing)) if missing else ''))
                if rc:
                    print(err[-600:])
            bad += not ok
    for where, old, new in MUTANTS:
        header, body = check.emit(0, 0)
        if where == 'body':
            assert old in body, old
            body = body.replace(old, new, 1)
        else:
            assert old in header, old
            header = header.replace(old, new, 1)
        src = ('#version 450\n' + check.PRELUDE + header + '\nvoid main() {\n'
               + body + check.EPILOGUE)
        rc, _ = check.compile_src(src, 'rtz_mutant', 'vulkan')
        print('mutant %-60s %s' % (new[:60], 'REJECTED' if rc else
                                   'ACCEPTED (!)'))
        bad += rc == 0
    print('FAILED' if bad else 'ALL OK')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
