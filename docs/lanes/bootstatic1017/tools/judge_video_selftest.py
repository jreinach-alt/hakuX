#!/usr/bin/env python3
"""Self-test for judge_video.py on a synthetic result dir (an encoded video, a probe log, a logcat; no device data).

The video, 1280 x 960 at 60 fps, 10 s: 0-2 s a smooth launcher-like picture, 2-3 s black, 3.0-3.5 s whole-screen
noise (the static), 3.5-4 s black, 4-10 s a detailed picture (the title). meta.json's start_wall is 0.6 s early, as a
whole-second device clock read before screenrecord starts can be: the probe's wall times are the true ones, so an
event at video time t is at start_wall + 0.6 + t in the probe. The probe log starts 2.2 s into the video: src=v black
presents, src=v presents over 3.0-3.5 s with the screen off whose texture and window are noise (Android draws it, no
blank), then src=n pictures from 4 s.

Case A: as above, Turnip in the logcat. Expect VALID, alignment offset 0.6 s within 2 frames, one episode of about
30 frames, H1 and H5 true, H2 and H4 false.
Case B: the logcat names the stock driver. Expect V0 false.
Case C: the probe's first present comes 0.5 s after the video starts. Expect V1 false.
Case D, the after arm: no noise in the video, and the probe's window is black over 3.0-3.5 s while its texture is
still noise. Expect VALID and no episodes.
Case E: the noise comes from src=n presents whose window drew it, screen on. Expect H2 true, H1 and H5 false.
Case F: the video shows noise the probe's window never drew (the window black, the screen on). Expect H4 true.
Case G: a second burst at 6.0-6.2 s, in the probe too. Expect two episodes, each matched to its own presents (a
variable reused inside the episode loop once shifted every episode after the first).

Usage: judge_video_selftest.py <scratch dir>
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1280, 960, 60
START = 1700000000
SKEW = 0.6


def picture(t, detail):
    y, x = np.mgrid[0:H, 0:W]
    img = np.zeros((H, W, 3), np.uint8)
    img[..., 0] = (x * 255 // W)
    img[..., 1] = (y * 255 // H)
    img[..., 2] = 128
    if detail:
        img[(x // 16 + y // 16) % 2 == 0] //= 2
    return img


def in_burst(t, case):
    return (3.0 <= t < 3.5 and case != "D") or (case == "G" and 6.0 <= t < 6.2)


def make_video(path, case):
    rnd = np.random.default_rng(1045)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-b:v", "10M", "-pix_fmt", "yuv420p", path],
                         stdin=subprocess.PIPE)
    smooth, title, black = picture(0, False), picture(0, True), np.zeros((H, W, 3), np.uint8)
    for i in range(10 * FPS):
        t = i / FPS
        if t < 2.0:
            f = smooth
        elif in_burst(t, case):
            f = rnd.integers(0, 256, (H, W, 3), dtype=np.uint8)
        elif t < 4.0:
            f = black
        else:
            f = title
        p.stdin.write(f.tobytes())
    p.stdin.close()
    p.wait()


def line(n, wall, src, nb, lit, sr01, t):
    return ("n=%d t_ms=%.1f wall_us=%d vt_ms=0 src=%s tex=1 flip=1 start=0x00000000 lo=2560 vga=640x480 bpp=32 cr28=83 "
            "gr06=05 ari=20 sr01=%02x cr17=e3 gc=00100000 pv=00000000 surf=640x480 ram_nz=1/2 ram_nb=1.0 ram_h=0 "
            "win=1280x960 mean=0,0,0 nb=%.1f lit=%.3f grn=0.000 h=%08x dump=0 ramdump=0 tnb=%.1f tlit=%.3f tgrn=0.000"
            % (n, (wall - START - SKEW - 2.2) * 1000, int(wall * 1e6), src, sr01, nb, lit, n, t[0], t[1]))


def make(d, case):
    os.makedirs(os.path.join(d, "video"), exist_ok=True)
    os.makedirs(os.path.join(d, "pulled"), exist_ok=True)
    vid = os.path.join(d, "video", "v00001.mp4")
    # One encode per burst layout, reused across cases.
    cache = os.path.join(os.path.dirname(d), "bursts_%s.mp4" % (case if case in ("D", "G") else "A"))
    if not os.path.exists(cache):
        make_video(cache, case)
    shutil.copyfile(cache, vid)
    json.dump({"seconds": 10, "after": 0, "mark_wall": START, "segments": [
        {"file": "v00001.mp4", "start_wall": START, "bytes": os.path.getsize(vid)}], "bytes": 0},
        open(os.path.join(d, "video", "meta.json"), "w"))
    with open(os.path.join(d, "logcat.txt"), "w") as f:
        f.write("10-17 15:00:00.000 I hakuX: Loading custom Vulkan driver\n")
        f.write("10-17 15:00:00.100 I hakuX: GPU: %s\n" % ("Qualcomm Adreno Vulkan Driver" if case == "B" else "PurpleVK"))
    first = 0.5 if case == "C" else 2.2
    lines = []
    n = 0
    t = first
    while t < 10.0:
        wall = START + SKEW + t
        if case == "G" and 6.0 <= t < 6.2:
            lines.append(line(n, wall, "v", 60.0, 0.9, 0x21, (60.0, 0.9)))
        elif 3.0 <= t < 3.5:
            if case == "E":
                lines.append(line(n, wall, "n", 60.0, 0.9, 0x01, (-1, -1)))
            elif case == "D":
                lines.append(line(n, wall, "v", 0.0, 0.0, 0x21, (60.0, 0.9)))
            elif case == "F":
                lines.append(line(n, wall, "v", 0.0, 0.0, 0x01, (0.0, 0.0)))
            else:
                lines.append(line(n, wall, "v", 60.0, 0.9, 0x21, (60.0, 0.9)))
        elif t < 4.0:
            lines.append(line(n, wall, "v", 0.0, 0.0, 0x01, (0.0, 0.0)))
        else:
            lines.append(line(n, wall, "n", 4.0, 0.9, 0x01, (-1, -1)))
        n += 1
        t += 1.0 / 60
    with open(os.path.join(d, "pulled", "boot1045_log.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    root = sys.argv[1]
    os.makedirs(root, exist_ok=True)
    fails = 0
    ep = lambda r: r["episodes"]
    expect = {
        "A": [("valid", lambda r: r["verdict"].startswith("VALID")),
              ("offset 0.6 s", lambda r: abs(r["align_offset_s"] - SKEW) <= 2.0 / FPS),
              ("one episode of ~30 frames", lambda r: len(ep(r)) == 1 and 25 <= ep(r)[0]["frames"] <= 35),
              ("H1 H5 true, H2 H4 false", lambda r: ep(r)[0]["H1"] and ep(r)[0]["H5"] and not ep(r)[0]["H2"]
               and not ep(r)[0]["H4"])],
        "B": [("V0 false", lambda r: r["valid"]["V0"] is False)],
        "C": [("V1 false", lambda r: r["valid"]["V1"] is False)],
        "D": [("valid, no episodes", lambda r: r["verdict"].startswith("VALID") and len(ep(r)) == 0)],
        "E": [("H2 true, H1 H5 false", lambda r: len(ep(r)) == 1 and ep(r)[0]["H2"] and not ep(r)[0]["H1"]
               and not ep(r)[0]["H5"])],
        "F": [("H4 true", lambda r: len(ep(r)) == 1 and ep(r)[0]["H4"])],
        "G": [("two episodes, each matched to its own presents", lambda r: len(ep(r)) == 2
               and all(e["H1"] and e["H5"] and not e["H4"] for e in ep(r))
               and ep(r)[1]["probe_n"][0] > ep(r)[0]["probe_n"][1])],
    }
    for case, checks in expect.items():
        d = os.path.join(root, "case" + case)
        make(d, case)
        js = os.path.join(d, "judge.json")
        p = subprocess.run([sys.executable, os.path.join(HERE, "judge_video.py"), d, "--json", js],
                           capture_output=True, text=True)
        try:
            res = json.load(open(js))
        except (OSError, ValueError):
            res = {}
            print(p.stdout, p.stderr)
        for name, fn in checks:
            try:
                ok = bool(fn(res))
            except (KeyError, IndexError, TypeError):
                ok = False
            fails += not ok
            print("%s case %s: %s" % ("ok  " if ok else "FAIL", case, name))
        if case == "A":
            print(p.stdout)
    print("FAILS=%d" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
