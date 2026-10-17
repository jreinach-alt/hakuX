#!/usr/bin/env python3
"""Self-test for judge_boot.py on synthetic probe output (no emulator data).

Case A (the H1 shape): 10 black fallback presents, 8 noise fallback presents whose frame is the RAM dump decoded at
32 bpp, then 200 GPU presents of a smooth picture. Expect: covered, one episode of 8 noise presents, H1 HIT, H2 MISS,
RAM MATCH on the dumped present. Case B (the mutant): the same, but the frame is fresh random noise unrelated to the
RAM dump. Expect: RAM "no match". Case C: the noise presents come from src=n. Expect: H1 MISS, H2 HIT.

Case D (the desktop shape seen in d1, added before d2): every present is src=v. 10 reset presents; 6 presents with the
screen off (sr01 21) whose window is black but whose texture numbers are noise; one present with the screen on at a
new start, whose window is the previous present's RAM (one refresh late) while RAM at the new start is zero; black;
a logo at that start; then 200 presents of the title at another start. Expect: covered under the download rule, one
window episode with blanked_prev true, an unblanked episode of 6 presents all screen-off, and the RAM dump of the
present before the edge matching the window under the "next" pairing. Case E, its mutant: the leak frame is noise
unrelated to that RAM. Expect: no "next" MATCH.

Usage: judge_boot_selftest.py <scratch dir>
"""
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VW, VH = 640, 480
WW, WH = 1280, 720  # window; picture letterboxed to 960x720 at x=160
DW, DH = 320, 180   # probe's downscale (step 4)


def line(n, src, nb, lit, grn=0.0, dump=0, ramdump=0, bpp=32, cr28=3, start=0x10000, sr01=0, t=None):
    s = ("n=%d t_ms=%.1f wall_us=0 vt_ms=0 src=%s tex=1 flip=1 start=0x%08x lo=%d vga=%dx%d bpp=%d "
         "cr28=%02x gr06=01 ari=20 sr01=%02x cr17=e3 gc=00100000 pv=00000000 surf=640x480 ram_nz=60000/65536 "
         "ram_nb=80.0 ram_h=%08x win=%dx%d mean=100,100,100 nb=%.1f lit=%.3f grn=%.3f h=%08x dump=%d ramdump=%d"
         % (n, n * 16.7, src, start, VW * 4, VW, VH, bpp, cr28, sr01, n, WW, WH, nb, lit, grn, n, dump, ramdump))
    if t:
        s += " tnb=%.1f tlit=%.3f tgrn=%.3f" % t
    return s


def frame_of(ram, mutant):
    """A window frame showing `ram` at 32 bpp, letterboxed as the probe sees it, or unrelated noise if mutant."""
    other = random.Random(7)
    px = bytearray(DW * DH * 3)
    for y in range(DH):
        for x in range(DW):
            o = (y * DW + x) * 3
            if 40 <= x < 280:
                if mutant:
                    v = [other.randrange(256) for _ in range(3)]
                else:
                    sx = (x - 40) * VW // 240
                    sy = y * VH // DH
                    ro = (sy * VW + sx) * 4
                    v = [ram[ro + 2], ram[ro + 1], ram[ro]]
                px[o:o + 3] = bytes(v)
    return px


def write(d, name, data):
    with open(os.path.join(d, name), "wb") as f:
        f.write(data)


def ppm(px, w=DW, h=DH):
    return b"P6\n%d %d\n255\n" % (w, h) + bytes(px)


def make_desktop(d, mutant):
    rnd = random.Random(1045)
    ram = bytes(rnd.randrange(256) for _ in range(VW * VH * 4))
    black = bytearray(DW * DH * 3)
    lines = []
    n = 0
    for _ in range(10):
        lines.append(line(n, "v", 0.0, 0.0, start=0, t=(0.0, 0.0, 0.0)))
        if n == 0:
            write(d, "boot1045_f%05u.ppm" % n, ppm(black))
        n += 1
    for k in range(6):
        last = k == 5
        lines.append(line(n, "v", 0.0, 0.0, start=0, sr01=0x21, ramdump=2 if last else 0, t=(80.0, 0.9, 0.05)))
        if last:
            write(d, "boot1045_r%05u.bin" % n, ram)
        n += 1
    # The edge: screen on, new start, RAM there zero; the window is the previous present's RAM.
    lines.append(line(n, "v", 80.0, 0.9, start=0x32a4000, sr01=0x01, dump=1, ramdump=1, t=(0.0, 0.0, 0.0)))
    write(d, "boot1045_r%05u.bin" % n, bytes(len(ram)))
    write(d, "boot1045_f%05u.ppm" % n, ppm(frame_of(ram, mutant)))
    n += 1
    lines.append(line(n, "v", 0.0, 0.0, start=0x32a4000, sr01=0x01, dump=1, t=(0.0, 0.0, 0.0)))
    write(d, "boot1045_f%05u.ppm" % n, ppm(black))
    n += 1
    for _ in range(5):
        lines.append(line(n, "v", 2.0, 0.3, start=0x32a4000, sr01=0x01, t=(2.0, 0.3, 0.0)))
        n += 1
    for _ in range(200):
        lines.append(line(n, "v", 3.0 + rnd.random(), 0.6, start=0x18e8000, sr01=0x01, t=(3.0, 0.6, 0.0)))
        n += 1
    with open(os.path.join(d, "boot1045_log.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")


def make(d, case):
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.startswith("boot1045_"):
            os.replace(os.path.join(d, f), os.path.join(d, "old." + f))
    if case in ("D", "E"):
        make_desktop(d, case == "E")
        return
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
    js = os.path.join(d, "judge.json")
    p = subprocess.run([sys.executable, os.path.join(HERE, "judge_boot.py"), d, "--json", js], capture_output=True,
                       text=True)
    with open(js) as f:
        return p.stdout, json.load(f)


def rm(res, n):
    return next((m for m in res["ram_match"] if m["n"] == n), {})


def main():
    root = sys.argv[1]
    fails = 0
    eps = lambda r: r["episodes"]
    ueps = lambda r: r["unblanked"]["episodes"]
    expect = {
        "A": [("covered", lambda r: r["covered"] is True),
              ("H1 HIT", lambda r: r["hypotheses"]["H1"] == "HIT"),
              ("H2 MISS", lambda r: r["hypotheses"]["H2"] == "MISS"),
              ("RAM same MATCH", lambda r: rm(r, 10).get("same", {}).get("verdict") == "MATCH"),
              ("one episode of 8", lambda r: len(eps(r)) == 1 and eps(r)[0]["presents"] == 8)],
        "B": [("RAM same no match", lambda r: rm(r, 10).get("same", {}).get("verdict") == "no match")],
        "C": [("H1 MISS", lambda r: r["hypotheses"]["H1"].startswith("MISS")),
              ("H2 HIT", lambda r: r["hypotheses"]["H2"].startswith("HIT"))],
        "D": [("covered", lambda r: r["covered"] is True),
              ("C2 download rule", lambda r: r["coverage"]["C2_rule"] == "download: start moved"
               and r["coverage"]["C2_first_gpu_picture_n"] == 23),
              ("one window episode at 16, blanked_prev", lambda r: len(eps(r)) == 1 and eps(r)[0]["first_n"] == 16
               and eps(r)[0]["blanked_prev"] is True and eps(r)[0]["blanked"] is False),
              ("unblanked episode of 6, all screen-off", lambda r: len(ueps(r)) == 1
               and ueps(r)[0]["presents"] == 6 and ueps(r)[0]["screen_off_presents"] == 6),
              ("RAM 15 next MATCH", lambda r: rm(r, 15).get("next", {}).get("verdict") == "MATCH"),
              ("RAM 16 (zero) same no match", lambda r: rm(r, 16).get("same", {}).get("verdict") == "no match")],
        "E": [("RAM 15 next not MATCH", lambda r: rm(r, 15).get("next", {}).get("verdict") == "no match")],
    }
    for case, checks in expect.items():
        d = os.path.join(root, "case" + case)
        make(d, case)
        out, res = run(d)
        for name, fn in checks:
            try:
                ok = bool(fn(res))
            except (KeyError, IndexError, TypeError):
                ok = False
            fails += not ok
            print("%s case %s: %s" % ("ok  " if ok else "FAIL", case, name))
        if case in ("A", "D"):
            print(out)
    print("FAILS=%d" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
