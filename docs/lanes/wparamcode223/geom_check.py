#!/usr/bin/env python3
"""Compile every docs/testing/geom_dump case with the NDK's glslc: Vulkan
cases for vulkan1.0, GL/GLES cases for opengl with -fauto-map-locations
(as #235 and wparamclip223 did).  Then a mutant of hunk (B), which must be
rejected.

Build first, outside the tree:
    make -C docs/testing/geom_dump BUILD=$PWD/.scratch/geom
"""
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DUMP = os.path.join(ROOT, ".scratch", "geom", "geom-dump")
GLSLC = ('/home/justin/Android/Sdk/ndk/29.0.14206865/shader-tools/'
         'linux-x86_64/glslc')
RULE = "if (garea == 0.0 && max(pmax.x, pmax.y) < 524288.0) { return true; }"


def cases():
    out = subprocess.run([DUMP], capture_output=True, text=True,
                         check=True).stdout
    parts = re.split(r"^=== (\S+)(.*)$", out, flags=re.M)
    for i in range(1, len(parts), 3):
        name, tail, body = parts[i], parts[i + 1], parts[i + 2]
        if tail.strip():
            continue  # "no geometry shader"
        yield name, body.lstrip("\n")


def glslc(name, src):
    path = os.path.join(ROOT, ".scratch", name + ".geom")
    with open(path, "w") as fh:
        fh.write(src)
    args = [GLSLC, "-fshader-stage=geom", "-o", os.devnull, path]
    if name.endswith("_vk"):
        args[1:1] = ["--target-env=vulkan1.0"]
    else:
        args[1:1] = ["--target-env=opengl", "-fauto-map-locations"]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, r.stderr


def main():
    n = bad = with_rule = 0
    mutant_src = None
    for name, src in cases():
        n += 1
        if RULE in src:
            with_rule += 1
            if mutant_src is None and name.endswith("_vk"):
                mutant_src = (name, src.replace(RULE, RULE.replace(
                    "max(pmax.x, pmax.y)", "pmax"), 1))
        rc, err = glslc(name, src)
        bad += rc != 0
        print("%-52s %s%s" % (name, "OK" if rc == 0 else "FAIL",
                              "" if rc == 0 else " " + err.strip()[-160:]))
    rc, _ = glslc(mutant_src[0] + "_mutant", mutant_src[1])
    print("mutant (vec2 < float) on %s: %s" % (
        mutant_src[0], "REJECTED" if rc else "ACCEPTED (!)"))
    print("compiled %d/%d; hunk (B) present in %d" % (n - bad, n, with_rule))
    return 1 if bad or rc == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
