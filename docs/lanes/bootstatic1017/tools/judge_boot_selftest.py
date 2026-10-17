#!/usr/bin/env python3
"""Self-test for judge_boot.py on synthetic probe output (no emulator data).

Case A (the H1 shape): 10 black fallback presents, 8 noise fallback presents whose frame is the RAM dump decoded at
32 bpp, then 200 GPU presents of a smooth picture. Expect: covered, one episode of 8 noise presents, H1 HIT, H2 MISS,
RAM MATCH on the dumped present. Case B (the mutant): the same, but the frame is fresh random noise unrelated to the
RAM dump. Expect: RAM "no match". Case C: the noise presents come from src=n. Expect: H1 MISS, H2 HIT.

Usage: judge_boot_selftest.py <scratch dir>
"""
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VW, VH = 640, 480
WW, WH = 1280, 720  # window; picture letterboxed to 960x720 at x=160
DW, DH = 320, 180   # probe's downscale (step 4)


def line(n, src, nb, lit, grn=0.0, dump=0, ramdump=0, bpp=32, cr28=3):
    return ("n=%d t_ms=%.1f wall_us=0 vt_ms=0 src=%s tex=1 flip=1 start=0x00010000 lo=%d vga=%dx%d bpp=%d "
            "cr28=%02x gr06=01 ari=20 sr01=00 cr17=e3 gc=00100000 pv=00000000 surf=640x480 ram_nz=60000/65536 "
            "ram_nb=80.0 ram_h=%08x win=%dx%d mean=100,100,100 nb=%.1f lit=%.3f grn=%.3f h=%08x dump=%d ramdump=%d"
            % (n, n * 16.7, src, VW * 4, VW, VH, bpp, cr28, n, WW, WH, nb, lit, grn, n, dump, ramdump))


def make(d, case):
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.startswith("boot1045_"):
            os.replace(os.path.join(d, f), os.path.join(d, "old." + f))
    rnd = random.Random(1045)
    lines = []
    n = 0
    for _ in range(10):
        lines.append(line(n, "v", 0.0, 0.0))
        n += 1
    ram = bytes(rnd.randrange(256) for _ in range(VW * VH * 4))
    for k in range(8):
        dump = 1 if k == 0 else 0
        src = "n" if case == "C" else "v"
        lines.append(line(n, src, 80.0, 0.9, dump=dump, ramdump=dump))
        if dump:
            with open(os.path.join(d, "boot1045_r%05u.bin" % n), "wb") as f:
                f.write(ram)
            other = random.Random(7)
            px = bytearray(DW * DH * 3)
            for y in range(DH):
                for x in range(DW):
                    o = (y * DW + x) * 3
                    if 40 <= x < 280:
                        if case == "B":
                            v = [other.randrange(256) for _ in range(3)]
                        else:
                            sx = (x - 40) * VW // 240
                            sy = y * VH // DH
                            ro = (sy * VW + sx) * 4
                            v = [ram[ro + 2], ram[ro + 1], ram[ro]]
                        px[o:o + 3] = bytes(v)
            with open(os.path.join(d, "boot1045_f%05u.ppm" % n), "wb") as f:
                f.write(b"P6\n%d %d\n255\n" % (DW, DH))
                f.write(px)
        n += 1
    for _ in range(200):
        lines.append(line(n, "n", 3.0 + rnd.random(), 0.6))
        n += 1
    with open(os.path.join(d, "boot1045_log.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")


def run(d):
    p = subprocess.run([sys.executable, os.path.join(HERE, "judge_boot.py"), d], capture_output=True, text=True)
    return p.stdout


def main():
    root = sys.argv[1]
    fails = 0
    expect = {
        "A": ["covered: True", '"H1": "HIT"', '"H2": "MISS"', '"verdict": "MATCH"', '"presents": 8'],
        "B": ['"verdict": "no match"'],
        "C": ['"H1": "MISS', '"H2": "HIT'],
    }
    for case, needles in expect.items():
        d = os.path.join(root, "case" + case)
        make(d, case)
        out = run(d)
        for s in needles:
            ok = s in out
            fails += not ok
            print("%s case %s: %s" % ("ok  " if ok else "FAIL", case, s))
        if case == "A":
            print(out)
    print("FAILS=%d" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
