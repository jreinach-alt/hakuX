#!/usr/bin/env python3
"""The #569 P6 render check: draw each specialised shader and its ubershader
on lavapipe with identical inputs and compare the targets per pixel.

    render_check.py SHADER_DIR [--jobs N] [--limit N] [--glslang PATH]

SHADER_DIR is uberhost's --out (spec_N.frag, uber_N.frag, comb_N.bin).
For each pair:
  * a vertex stub feeds every input the fragment shader declares, from seeded
    per-vertex constants over one full-screen triangle, so every pixel gets
    its own interpolated inputs;
  * the uniform block is filled from seeded values at std140 offsets computed
    from the block's own text, identically for both shaders; the ubershader's
    extra member (ubComb, the last) gets comb_N.bin;
  * render.c draws each into a 64x64 RGBA32F target.

A pair passes when the two targets are byte-identical. Where they are not,
the pair is reported with the float and the 8-bit (round(clamp(x)*255))
counts, since only the second is what a golden sees.

This is a check of the interpreter's LOGIC on one compiler (llvmpipe). It
cannot see how the device's compiler contracts arithmetic; that is the device
E leg's question.
"""
import argparse
import os
import random
import re
import struct
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
ICD = "/usr/share/vulkan/icd.d/lvp_icd.json"

IN_RE = re.compile(r"^layout\(location = (\d+)\) ((?:flat |noperspective |NOPERSPECTIVE )?)in (\w+) (\w+);", re.M)
SAMP_RE = re.compile(r"^layout\(binding = (\d)\) uniform (\w+) texSamp(\d);", re.M)
MEMBER_RE = re.compile(r"^(\w+) (\w+)(?:\[(\d+)\])?;$")
KIND = {"sampler2D": "2", "samplerCube": "c", "usampler2D": "u", "sampler3D": "3"}

# std140 (size, align) of one element, arrays aside.
BASE = {
    "int": (4, 4), "uint": (4, 4), "float": (4, 4), "bool": (4, 4),
    "vec2": (8, 8), "ivec2": (8, 8), "uvec2": (8, 8),
    "vec3": (12, 16), "ivec3": (12, 16), "uvec3": (12, 16),
    "vec4": (16, 16), "ivec4": (16, 16), "uvec4": (16, 16),
    "mat2": (32, 16),
}
COMPS = {"int": 1, "uint": 1, "float": 1, "bool": 1, "vec2": 2, "ivec2": 2,
         "uvec2": 2, "vec3": 3, "ivec3": 3, "uvec3": 3, "vec4": 4, "ivec4": 4,
         "uvec4": 4}


def block_members(text):
    start = text.index("uniform PshUniforms {\n") + len("uniform PshUniforms {\n")
    end = text.index("};\n", start)
    out = []
    for line in text[start:end].splitlines():
        m = MEMBER_RE.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2), int(m.group(3) or 1),
                        m.group(3) is not None))
    return out


def std140(members):
    off = 0
    lay = []
    for typ, name, count, is_arr in members:
        size, align = BASE[typ]
        if is_arr:
            stride = (size + 15) // 16 * 16
            align = 16
            size = stride * count
        else:
            stride = 0
        off = (off + align - 1) // align * align
        lay.append((typ, name, count, off, stride))
        off += size
    return lay, off


def value_for(rng, typ, name, idx, comp):
    """One component. Floats in [0, 1] mostly; ints chosen so nothing
    discards everything (clip regions cover the target, the stipple is all
    ones)."""
    if name == "alphaRef":
        # Low, so a GREATER/GEQUAL test passes somewhere; the others are
        # served by the target's spread of alphas.
        return rng.randrange(0, 64)
    if name == "clipRegion":
        # The left half: an inclusive clip keeps it and an exclusive one the
        # right half, so either way half the target is drawn.
        return (0, 0, 32, 64)[comp]
    if name == "stipplePattern":
        return -1
    if name in ("padAlphaMode", "signedBlendPass", "surfaceBSwap", "texX1A7"):
        return 0
    if name == "surfaceScale":
        return 1
    if name == "texScale":
        return 1.0
    if typ in ("uint", "uvec2", "uvec3", "uvec4"):
        return rng.randrange(0, 1 << 32)
    if typ in ("int", "ivec2", "ivec3", "ivec4"):
        return rng.randrange(0, 256)
    return rng.choice((0.0, 1.0, rng.random(), rng.random(), rng.uniform(-0.2, 1.2)))


def fill_ubo(lay, total, seed, comb):
    rng = random.Random(seed)
    buf = bytearray((total + 15) // 16 * 16)
    for typ, name, count, off, stride in lay:
        if name == "ubComb":
            buf[off:off + len(comb)] = comb
            continue
        for e in range(count):
            base = off + e * stride
            if typ == "mat2":
                for col in range(2):
                    for r in range(2):
                        struct.pack_into("<f", buf, base + col * 16 + r * 4,
                                         rng.uniform(-1, 1))
                continue
            for c in range(COMPS[typ]):
                v = value_for(rng, typ, name, e, c)
                fmt = "<f" if typ.startswith(("float", "vec")) else (
                    "<I" if typ.startswith("u") else "<i")
                struct.pack_into(fmt, buf, base + 4 * c, v)
    return bytes(buf)


def vertex_stub(frag, seed):
    rng = random.Random(seed)
    lines = ["#version 450", "#define NOPERSPECTIVE noperspective"]
    body = ["    const vec2 P[3] = vec2[](vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));",
            "    gl_Position = vec4(P[gl_VertexIndex], 0.5, 1.0);"]
    for loc, qual, typ, name in IN_RE.findall(frag):
        lines.append("layout(location = %s) %sout %s %s;" % (loc, qual, typ, name))
        vals = []
        for v in range(3):
            if name == "vtxFogSpecial":
                x = [0.0, 0.0, 0.0, 0.0]
            else:
                x = [rng.uniform(-0.1, 1.1) for _ in range(3)] + [rng.uniform(0.5, 1.5)]
            vals.append("vec4(%s)" % ", ".join("%.6f" % c for c in x))
        body.append("    const vec4 V%s[3] = vec4[](%s);" % (loc, ", ".join(vals)))
        sw = "" if typ == "vec4" else ".x"
        body.append("    %s = V%s[gl_VertexIndex]%s;" % (name, loc, sw))
    return "\n".join(lines + ["void main() {"] + body + ["}", ""])


def run(cmd, env=None):
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if p.returncode:
        raise RuntimeError("%s\n%s%s" % (" ".join(cmd), p.stdout[-2000:], p.stderr[-2000:]))


def q8(x):
    if x != x:
        return -1
    return int(round(min(max(x, 0.0), 1.0) * 255.0))


def check(args, i):
    d = args.dir
    out = os.path.join(BUILD, "render")
    spec = open(os.path.join(d, "spec_%04d.frag" % i)).read()
    uber = open(os.path.join(d, "uber_%04d.frag" % i)).read()
    comb = open(os.path.join(d, "comb_%04d.bin" % i), "rb").read()

    kinds = ["-"] * 4
    for b, typ, n in SAMP_RE.findall(spec):
        if typ not in KIND:
            return (i, "skip", "sampler type %s" % typ)
        kinds[int(b)] = KIND[typ]
    kinds = "".join(kinds)

    lay_s, tot_s = std140(block_members(spec))
    lay_u, tot_u = std140(block_members(uber))
    if lay_u[:len(lay_s)] != lay_s or lay_u[-1][1] != "ubComb":
        return (i, "FAIL", "uniform layouts disagree")
    ubo_s = fill_ubo(lay_s, tot_s, i, comb)
    if args.mutant:
        # Falsifier: the ubershader gets D of the final combiner inverted.
        comb = bytearray(comb)
        comb[32 * 4] ^= 0x20
        comb = bytes(comb)
    ubo_u = fill_ubo(lay_u, tot_u, i, comb)

    pfx = os.path.join(out, "%04d" % i)
    for ext in (".spec.raw", ".uber.raw"):
        if os.path.exists(pfx + ext):
            os.remove(pfx + ext)
    with open(pfx + ".vert", "w") as f:
        f.write(vertex_stub(spec, i))
    with open(pfx + ".spec.ubo", "wb") as f:
        f.write(ubo_s)
    with open(pfx + ".uber.ubo", "wb") as f:
        f.write(ubo_u)
    try:
        run([args.glslang, "-V", "--target-env", "vulkan1.1", "-S", "vert",
             "-o", pfx + ".vert.spv", pfx + ".vert"])
        run([args.glslang, "-V", "--target-env", "vulkan1.1", "-S", "frag",
             "-o", pfx + ".spec.spv", os.path.join(d, "spec_%04d.frag" % i)])
        run([args.glslang, "-V", "--target-env", "vulkan1.1", "-S", "frag",
             "-o", pfx + ".uber.spv", os.path.join(d, "uber_%04d.frag" % i)])
        env = dict(os.environ, VK_ICD_FILENAMES=ICD)
        rend = os.path.join(BUILD, "render")
        run([os.path.join(BUILD, "render_bin"), pfx + ".vert.spv",
             pfx + ".spec.spv", pfx + ".spec.ubo", kinds, pfx + ".spec.raw"], env)
        run([os.path.join(BUILD, "render_bin"), pfx + ".vert.spv",
             pfx + ".uber.spv", pfx + ".uber.ubo", kinds, pfx + ".uber.raw"], env)
    except RuntimeError as e:
        return (i, "ERROR", str(e)[:600])

    a = open(pfx + ".spec.raw", "rb").read()
    b = open(pfx + ".uber.raw", "rb").read()
    fa = struct.unpack("<%df" % (len(a) // 4), a)
    fb = struct.unpack("<%df" % (len(b) // 4), b)
    px_f = px_8 = drawn = 0
    for p in range(len(fa) // 4):
        va, vb = fa[4 * p:4 * p + 4], fb[4 * p:4 * p + 4]
        if va[0] != -7.0:
            drawn += 1
        if a[16 * p:16 * p + 16] != b[16 * p:16 * p + 16]:
            px_f += 1
            if [q8(x) for x in va] != [q8(x) for x in vb]:
                px_8 += 1
    for ext in (".spec.raw", ".uber.raw"):
        if px_f == 0:
            os.remove(pfx + ext)
    status = "ok" if px_f == 0 else "DIFF"
    return (i, status, "drawn %d px, float-diff %d px, 8-bit-diff %d px"
            % (drawn, px_f, px_8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="", help="comma-separated pair ids only")
    ap.add_argument("--mutant", action="store_true",
                    help="stage a wrong combiner program into the ubershader; "
                         "every pair that draws must then DIFF")
    ap.add_argument("--glslang",
                    default="/home/justin/hakux-work/turnipfork-glslang/install/bin/glslangValidator")
    args = ap.parse_args()
    os.makedirs(os.path.join(BUILD, "render"), exist_ok=True)

    ids = sorted(int(f[5:9]) for f in os.listdir(args.dir)
                 if f.startswith("spec_") and f.endswith(".frag"))
    if args.ids:
        want = {int(x) for x in args.ids.split(",")}
        ids = [i for i in ids if i in want]
    if args.limit:
        ids = ids[:args.limit]
    manifest = {}
    mp = os.path.join(args.dir, "manifest.txt")
    if os.path.exists(mp):
        for line in open(mp):
            manifest[int(line[:4])] = line[5:].strip()

    with ThreadPoolExecutor(args.jobs) as ex:
        res = list(ex.map(lambda i: check(args, i), ids))
    counts = {}
    for i, status, msg in res:
        counts[status] = counts.get(status, 0) + 1
        if status != "ok":
            print("%04d %-5s %s | %s" % (i, status, msg, manifest.get(i, "")))
    drawn = [r for r in res if r[1] == "ok" and "drawn 0 px" in r[2]]
    per = {}
    for i, status, msg in res:
        bl = manifest.get(i, "? ").split()[0]
        row = per.setdefault(bl, [0, 0, 0, 0])
        row[0] += 1
        row[1 if status == "ok" else 2] += 1
        if "drawn 0 px" in msg:
            row[3] += 1
    print("%-10s %6s %6s %6s %12s" % ("baseline", "pairs", "ok", "not ok", "drew nothing"))
    for bl, row in sorted(per.items()):
        print("%-10s %6d %6d %6d %12d" % (bl, *row))
    print("render_check: %s; %d of the ok pairs drew no pixel" %
          (", ".join("%s %d" % kv for kv in sorted(counts.items())), len(drawn)))
    return 0 if set(counts) <= {"ok"} else 1


if __name__ == "__main__":
    sys.exit(main())
