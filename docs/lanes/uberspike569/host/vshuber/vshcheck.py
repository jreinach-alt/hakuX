#!/usr/bin/env python3
"""Exactness of the uber vertex stage against the specialised one, on lavapipe.

    vshcheck.py [--keys shader_module_keys.bin] [--random N] [--seed S]
                [--prefix 0|1] [--out DIR] [--glslang PATH]

Generates the pairs (vshhost), compiles both shaders of each (glslang,
Vulkan 1.1), runs each on the same 64 vertices and uniform block (vsrender),
and compares the dumped outputs word by word. Per pair it prints OK, or the
outputs that differ with the first differing vertex's words. A pair whose
specialised shader does not compile is a harness or generator fault and is
reported as such; one whose uber shader does not compile is a vsh-uber.c
fault.

The dump per vertex (vshhost.c ubDump): D0 D1 B0 B1 (Fog,FogSpecial,triMZ,
PointSize) T0 T1 T2 T3 Pos0 gl_Position PointSize.
"""
import argparse
import json
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ["D0", "D1", "B0", "B1", "fog/fs/mz/ps", "T0", "T1", "T2", "T3", "Pos0",
         "gl_Position", "gl_PointSize"]
NV = 64
ENV = dict(os.environ, VK_ICD_FILENAMES="/usr/share/vulkan/icd.d/lvp_icd.json")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys")
    ap.add_argument("--random", type=int, default=200)
    ap.add_argument("--seed", default="0x569abc")
    ap.add_argument("--prefix", default="0")
    ap.add_argument("--out", default=os.path.join(HERE, "build", "pairs"))
    ap.add_argument("--glslang",
                    default="/home/justin/hakux-work/turnipfork-glslang/install/bin/glslangValidator")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--mutate", action="store_true",
                    help="stage a wrong uber uniform; every pair should DIFF")
    a = ap.parse_args()

    lay = json.load(open(os.path.join(HERE, "..", "keylayout.json")))
    cmd = [os.path.join(HERE, "build", "vshhost"), "--out", a.out,
           "--random", str(a.random), "--seed", a.seed, "--prefix", a.prefix]
    if a.mutate:
        cmd.append("--mutate")
    if a.keys:
        cmd += ["--keys", a.keys, "--keyrec", str(lay["record"]),
                "--keyoff", str(lay["vsh_state"]), "--vkind", str(lay["vertex_kind"])]
    r = run(cmd)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stderr.write(r.stderr)
        return 1
    refused = [ln for ln in r.stderr.splitlines() if ln.startswith("refused")]

    ok = diff = spec_bad = uber_bad = 0
    by_label = {}
    for line in open(os.path.join(a.out, "manifest")):
        pid, label, cmask = line.split()
        outs = {}
        for kind in ("spec", "uber"):
            src = os.path.join(a.out, "%s_%s.vert" % (kind, pid))
            spv = src + ".spv"
            c = run([a.glslang, "-V", "--target-env", "vulkan1.1", "-S", "vert",
                     "-o", spv, src])
            if c.returncode:
                print("%s %s: %s shader does not compile:\n%s" %
                      (pid, label, kind, "\n".join(l for l in c.stdout.splitlines()
                                                   if "ERROR" in l)[:2000]))
                outs = None
                if kind == "spec":
                    spec_bad += 1
                else:
                    uber_bad += 1
                break
            raw = spv + ".raw"
            v = run([os.path.join(HERE, "build", "vsrender"), spv,
                     os.path.join(a.out, "ubo_%s.bin" % pid), cmask, pid, raw], env=ENV)
            if v.returncode:
                print("%s %s: vsrender failed on %s: %s" % (pid, label, kind, v.stderr[-500:]))
                outs = None
                break
            outs[kind] = open(raw, "rb").read()
        if outs is None:
            continue
        s, u = outs["spec"], outs["uber"]
        if s == u:
            ok += 1
            by_label.setdefault(label.rstrip("0123456789ffprog") or label, [0, 0])
            if not a.quiet:
                print("%s %s: OK" % (pid, label))
            continue
        diff += 1
        sw = struct.unpack("<%dI" % (len(s) // 4), s)
        uw = struct.unpack("<%dI" % (len(u) // 4), u)
        bad = {}
        first = None
        for vtx in range(NV):
            for o in range(12):
                for k in range(4):
                    i = vtx * 64 + o * 4 + k
                    if sw[i] != uw[i]:
                        bad[NAMES[o]] = bad.get(NAMES[o], 0) + 1
                        if first is None:
                            first = (vtx, NAMES[o], k, sw[i], uw[i])
        vtx, name, k, x, y = first
        fx = struct.unpack("<f", struct.pack("<I", x))[0]
        fy = struct.unpack("<f", struct.pack("<I", y))[0]
        print("%s %s: DIFF %s; first v%d %s[%d] spec %08x (%g) uber %08x (%g)" %
              (pid, label, bad, vtx, name, k, x, fx, y, fy))
    print("vshcheck: %d identical, %d differ, %d spec compile fail, %d uber compile "
          "fail, %d refused" % (ok, diff, spec_bad, uber_bad, len(refused)))
    return 0 if diff == 0 and uber_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
