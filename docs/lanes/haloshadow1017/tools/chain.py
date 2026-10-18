#!/usr/bin/env python3
"""Halo shadow chain (#1038): guest state of a frame dump's draws, by name.

  chain.py DUMP F N [N ...]        registers the shadow chain depends on
  chain.py DUMP shader HASH vsh|psh   one shader's GLSL

Built on docs/lanes/x1port1012/tools/gdread.py (load + replay). Prints, per
draw: BORDERCOLOR0-3, TEXADDRESS0-3, TEXCTL0/1, TEXFMT, TEXFILTER, the
texture matrices the shader names (c[0x44..0x63]), CSV1 texgen, COMBINECTL,
the clear value registers, SURFACE/clip state.
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "x1port1012", "tools"))
import gdread  # noqa: E402


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def main():
    path, cmd = sys.argv[1], sys.argv[2]
    session, draws, frames, skips, shaders = gdread.load(path)
    if cmd == "shader":
        sh = shaders[sys.argv[3]]
        print(sh.get(sys.argv[4], ""))
        return
    f = int(cmd)
    want = [int(x) for x in sys.argv[3:]]
    names = gdread.reg_names()
    inv = {v: k for k, v in names.items()}
    st = gdread.replay(draws, {f})
    for n in want:
        s = st[(f, n)]
        r, c = s["r"], s["c"]
        d = next(x for x in draws if x["f"] == f and x["n"] == n)
        print(gdread.short(d))

        def R(name):
            return r[inv[name]]
        print("  BORDERCOLOR", " ".join(f"{R(f'BORDERCOLOR{i}'):#010x}" for i in range(4)))
        print("  TEXADDRESS ", " ".join(f"{R(f'TEXADDRESS{i}'):#010x}" for i in range(4)))
        for nm in ("TEXCTL0_0", "TEXCTL1_0", "TEXFMT0", "TEXFILTER0",
                   "TEXCTL0_1", "TEXCTL1_1", "TEXFMT1", "TEXFILTER1"):
            if nm in inv:
                print(f"  {nm} {R(nm):#010x}", end="")
        print()
        for nm in ("COMBINECTL", "SHADERPROG", "SHADERCTL", "CSV0_D", "CSV0_C",
                   "CSV1_A", "CSV1_B", "COLORCLEARVALUE", "ZSTENCILCLEARVALUE",
                   "BLEND", "BLENDCOLOR", "CONTROL_0", "CONTROL_1", "SETUPRASTER"):
            if nm in inv:
                print(f"  {nm} {R(nm):#010x}", end="")
        print()
        for base, label in ((0x44, "texMat0"), (0x4c, "texMat1"),
                            (0x54, "texMat2"), (0x5c, "texMat3")):
            rows = []
            for k in range(4):
                i = (base + k) * 4
                rows.append("(" + ", ".join(f"{f32(c[i + j]):.5g}" for j in range(4)) + ")")
            print(f"  {label} " + " ".join(rows))
        print("  ff", " ".join(f"{f32(v):.4g}" for v in s["ff"][:16]))
        print("  va", " ".join(f"{f32(v):.4g}" for v in s["va"][:16]))


if __name__ == "__main__":
    main()
