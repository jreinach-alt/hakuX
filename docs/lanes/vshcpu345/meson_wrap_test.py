#!/usr/bin/env python3
"""Build nv2a_vsh_cpu through this branch's wrap, as hakuX's meson build does.

    meson_wrap_test.py MESON CMAKE_BIN_DIR [NINJA_BIN_DIR]

A throwaway meson project gets a copy of subprojects/nv2a_vsh_cpu.wrap and
subprojects/packagefiles/nv2a_vsh_cpu/, pulls the library in with
cmake.subproject() exactly as hw/xbox/nv2a/pgraph/thirdparty/meson.build
does, and links a program that evaluates MUL(0, inf) and RCC(+inf). It must
print meson's "Applying diff file" line at setup, compile the patched source
(the marker is in the file ninja compiled), and give silicon's answers:
MUL(0, inf) = 0x00000000 and RCC(+inf) = 0x1F800000.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
T = os.path.join(WT, ".scratch", "mesontest")

MESON_BUILD = """project('vshcpu_wrap_test', 'c')
cmake = import('cmake')
opts = cmake.subproject_options()
opts.add_cmake_defines({'nv2a_vsh_cpu_UNIT_TEST': 'OFF'})
sub = cmake.subproject('nv2a_vsh_cpu', options: opts)
dep = declare_dependency(include_directories: sub.include_directories('nv2a_vsh_emulator'),
                         link_with: [sub.target('nv2a_vsh_emulator'), sub.target('nv2a_vsh_cpu'),
                                     sub.target('nv2a_vsh_disassembler')])
m = meson.get_compiler('c').find_library('m', required: false)
executable('probe', 'probe.c', dependencies: [dep, m])
"""

PROBE = r"""#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "nv2a_vsh_cpu.h"
static uint32_t u(float f) { uint32_t r; memcpy(&r, &f, 4); return r; }
int main(void) {
  float in[12] = {0.0f, 0.0f, 0.0f, 0.0f, INFINITY, INFINITY, INFINITY, INFINITY};
  float out[4];
  nv2a_vsh_cpu_mul(out, in);
  printf("MUL(0,inf)=0x%08X\n", u(out[0]));
  float r[4] = {INFINITY, INFINITY, INFINITY, INFINITY};
  nv2a_vsh_cpu_rcc(out, r);
  printf("RCC(+inf)=0x%08X\n", u(out[0]));
  return 0;
}
"""


def main():
    meson, cmake_bin = sys.argv[1], sys.argv[2]
    ninja_bin = sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(meson)
    shutil.rmtree(T, ignore_errors=True)
    os.makedirs(os.path.join(T, "subprojects", "packagefiles"))
    shutil.copy(os.path.join(WT, "subprojects/nv2a_vsh_cpu.wrap"), os.path.join(T, "subprojects"))
    shutil.copytree(os.path.join(WT, "subprojects/packagefiles/nv2a_vsh_cpu"),
                    os.path.join(T, "subprojects/packagefiles/nv2a_vsh_cpu"))
    open(os.path.join(T, "meson.build"), "w").write(MESON_BUILD)
    open(os.path.join(T, "probe.c"), "w").write(PROBE)
    env = dict(os.environ, PATH=os.pathsep.join([cmake_bin, ninja_bin, os.environ["PATH"]]))
    setup = subprocess.run([meson, "setup", "build"], cwd=T, env=env, capture_output=True,
                           text=True)
    slog = setup.stdout + setup.stderr
    applied = [l for l in slog.splitlines() if "diff file" in l.lower()]
    print("setup rc=%d" % setup.returncode)
    for l in applied:
        print("    " + l.strip())
    if setup.returncode:
        print(slog[-3000:])
        return 1
    comp = subprocess.run([meson, "compile", "-C", "build", "-v"], cwd=T, env=env,
                          capture_output=True, text=True)
    clog = comp.stdout + comp.stderr
    compiled = [l for l in clog.splitlines() if "nv2a_vsh_cpu.c" in l and " -c " in l]
    print("compile rc=%d" % comp.returncode)
    marker = False
    for l in compiled:
        src = [w for w in l.split() if w.endswith("nv2a_vsh_cpu.c")][-1]
        path = src if os.path.isabs(src) else os.path.normpath(os.path.join(T, "build", src))
        marker = os.path.exists(path) and "hakuX #345" in open(path).read()
        print("    compiled %s (marker %s)" % (path, marker))
    if comp.returncode:
        print(clog[-3000:])
        return 1
    out = subprocess.run([os.path.join(T, "build", "probe")], capture_output=True,
                         text=True).stdout
    print("    " + out.strip().replace("\n", "\n    "))
    ok = (bool(applied) and comp.returncode == 0 and marker
          and "MUL(0,inf)=0x00000000" in out and "RCC(+inf)=0x1F800000" in out)
    print("ALL OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
