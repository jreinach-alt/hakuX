#!/usr/bin/env python3
"""Judge one Nova soak's screen video against its [boot1045] probe (#1045): did the screen show static or green at
launch, when, and what the emulator was presenting at that moment.

Usage: judge_video.py <result dir> [--json out.json]

<result dir> is a dispatcher result: video/meta.json and video/v*.mp4 (request.sh --video-seconds N --video-after 0),
pulled/boot1045_log.txt (--env HAKUX_BOOTPROBE=1 --pull 'boot1045_*'), logcat.txt.

Committed before any Nova data. The rules, fixed here:

Validity (the run counts only if all hold):
  V0  Turnip: logcat.txt has "GPU: PurpleVK", "Loading custom Vulkan driver" or a "[gpl569] ext=1" line with mode=3,
      and no "Qualcomm Adreno Vulkan Driver" device line. The stock driver is never a valid arm (owner, 10-17).
  V1  the video starts before the launch: the probe's first present (n=0, wall_us) is at least V1_LEAD_S after the
      first segment's start_wall (the dispatcher's device-clock second before screenrecord starts), and the video's
      first frame is not noise or green.
  V2  the video runs past the launch window: it reaches V2_TAIL_S past the probe's first GPU picture (judge_boot's
      C2, src=n), or, when the probe has none, its last quarter holds picture-class frames.

Per frame, decoded at 640 wide with nearest-neighbour scaling (every other pixel of a 1280 x 960 recording), over the
centre half in each axis, the probe's own window numbers: nb (mean |horizontal neighbour difference| per channel),
lit (max channel > 24), grn (g >= 48 and g > r + 32 and g > b + 32). Classes as judge_boot.py: black lit < 0.01;
green grn >= 0.25; noise nb >= nb_bar and lit >= 0.10; picture otherwise. nb_bar = max(20, 2 x the largest nb among
lit frames in the last quarter of the video's time), from the run's own clean spread; the verdict prints that spread.

Alignment. A frame's wall time is its segment's start_wall plus its pts, which is good to about a second
(start_wall is a whole device second taken before screenrecord starts). The offset is then found by content: over
offsets of -ALIGN_S to +ALIGN_S in 1/60 s steps, the one that minimises the mean |video lit - probe window lit| over
the frames inside the probe's span (each frame against the latest present at or before its aligned time). The
offset and its score are printed, with the score at offset 0, so an alignment that rests on nothing shows.

Episodes: maximal runs of consecutive noise or green frames. Each lists the probe presents within its aligned wall
window widened by MATCH_FRAMES display frames on both sides (the compositor shows a present a frame or few after
the probe reads it), with their src, screen-off count (sr01 bit 5), window class and texture class (tcls: what the
texture held, before any blank).

Readings (NOTES.md hypotheses), per episode:
  H1  the probe presents in its window that drew or held the flash (window or texture class noise or green) are all
      src=v (the VGA fallback), and a texture class is noise or green.
  H2  some are src=n with a noise or green window class.
  H5  most of those flash presents have the screen off (sr01 bit 5): silicon would show black there.
  H4  the episode starts before the probe's first present, or no probe present falls in its window.
And for the run: the probe's own window class over the same presents (what GL drew, before the compositor), so a
flash in the video that the probe's window never drew is the compositor's or the SurfaceView's (H4).
"""
import json
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge_boot  # noqa: E402

V1_LEAD_S = 2.0
V2_TAIL_S = 5.0
ALIGN_S = 2.0
MATCH_FRAMES = 4
DECODE_W = 640
TURNIP = re.compile(r"GPU: PurpleVK|Loading custom Vulkan driver|\[gpl569\] ext=1.*mode=3")
STOCK = re.compile(r"Qualcomm Adreno Vulkan Driver|GPU: Adreno \(TM\)")


def frame_metrics(px):
    h, w, _ = px.shape
    c = px[h // 4:h * 3 // 4, w // 4:w * 3 // 4 + 1].astype(np.int16)
    a, b = c[:, :-1], c[:, 1:]
    nb = float(np.abs(a - b).sum()) / (3.0 * a.shape[0] * a.shape[1])
    r, g, bl = a[..., 0], a[..., 1], a[..., 2]
    lit = float((np.maximum(np.maximum(r, g), bl) > 24).mean())
    grn = float(((g >= 48) & (g > r + 32) & (g > bl + 32)).mean())
    return nb, lit, grn


def decode(path):
    """[(pts_s, nb, lit, grn)] for every frame of one segment."""
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts_time",
                         "-of", "csv=p=0", path], capture_output=True, text=True)
    pts = [float(x.split(",")[0]) for x in pr.stdout.split() if x.strip() and x.split(",")[0] not in ("", "N/A")]
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                         "-of", "csv=p=0", path], capture_output=True, text=True)
    w, h = (int(x) for x in pr.stdout.strip().split(",")[:2])
    dh = (h * DECODE_W // w) // 2 * 2
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-fps_mode", "passthrough", "-vf",
                          "scale=%d:%d:flags=neighbor" % (DECODE_W, dh), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    size = DECODE_W * dh * 3
    out = []
    i = 0
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        px = np.frombuffer(buf, dtype=np.uint8).reshape(dh, DECODE_W, 3)
        t = pts[i] if i < len(pts) else (pts[-1] if pts else 0.0) + (i - len(pts) + 1) / 60.0
        out.append((t,) + frame_metrics(px))
        i += 1
    p.wait()
    return out, len(pts)


def classify(nb, lit, grn, nb_bar):
    return judge_boot.classify({"lit": lit, "grn": grn, "nb": nb}, nb_bar)


def judge(rd):
    res = {"dir": rd}
    meta_p = os.path.join(rd, "video", "meta.json")
    if not os.path.exists(meta_p):
        res["verdict"] = "VOID: no video/meta.json"
        return res
    meta = json.load(open(meta_p))
    segs = meta.get("segments") or []
    if not segs:
        res["verdict"] = "VOID: no video segments (%s)" % meta.get("skipped", "?")
        return res

    # V0: the driver.
    lc = os.path.join(rd, "logcat.txt")
    turnip = stock = 0
    if os.path.exists(lc):
        with open(lc, errors="replace") as f:
            for line in f:
                turnip += bool(TURNIP.search(line))
                stock += bool(STOCK.search(line))
    res["V0_turnip_lines"] = turnip
    res["V0_stock_lines"] = stock
    v0 = turnip > 0 and stock == 0

    # The probe.
    plog = os.path.join(rd, "pulled", "boot1045_log.txt")
    rows, walls = [], []
    if os.path.exists(plog):
        rows = judge_boot.parse_log(plog)
        for r in rows:
            walls.append(int(r["raw"].get("wall_us", "0")) / 1e6)
    res["probe_presents"] = len(rows)
    probe0 = walls[0] if walls else None
    gpu_pic = next((i for i, r in enumerate(rows) if r["src"] == "n" and r["lit"] >= judge_boot.LIT_PICTURE), None)
    res["probe_first_present_wall"] = probe0
    res["probe_first_gpu_picture"] = None if gpu_pic is None else {"n": rows[gpu_pic]["n"], "wall": walls[gpu_pic]}

    # Frames.
    frames = []
    for s in segs:
        p = os.path.join(rd, "video", s["file"])
        if not os.path.exists(p):
            continue
        fr, npts = decode(p)
        for t, nb, lit, grn in fr:
            frames.append({"seg": s["file"], "pts": t, "wall": s["start_wall"] + t, "nb": nb, "lit": lit, "grn": grn})
    res["frames"] = len(frames)
    if not frames:
        res["verdict"] = "VOID: no decodable frames"
        return res
    t_end = frames[-1]["wall"]
    t0 = frames[0]["wall"]
    tail = [f for f in frames if f["wall"] >= t0 + 0.75 * (t_end - t0) and f["lit"] >= judge_boot.LIT_BLACK]
    clean_max = max((f["nb"] for f in tail), default=0.0)
    nb_bar = max(judge_boot.NB_FLOOR, 2 * clean_max)
    res["nb_bar"] = nb_bar
    res["clean_nb_max"] = clean_max
    res["clean_grn_max"] = max((f["grn"] for f in tail), default=0.0)
    for f in frames:
        f["cls"] = classify(f["nb"], f["lit"], f["grn"], nb_bar)

    # V1, V2.
    first_start = segs[0]["start_wall"]
    v1_lead = (probe0 - first_start) if probe0 is not None else None
    v1 = v1_lead is not None and v1_lead >= V1_LEAD_S and frames[0]["cls"] not in ("noise", "green")
    if gpu_pic is not None:
        v2 = t_end >= walls[gpu_pic] + V2_TAIL_S
    else:
        v2 = sum(1 for f in tail if f["cls"] == "picture") > 0
    res["V1_lead_s"] = v1_lead
    res["V1_first_frame_class"] = frames[0]["cls"]
    res["V2_video_end_wall"] = t_end
    res["valid"] = {"V0": v0, "V1": v1, "V2": v2}
    res["gaps_s"] = [round(b["start_wall"] - (a["start_wall"] + 60.0), 2) for a, b in zip(segs, segs[1:])]

    # Episodes.
    eps = []
    cur = None
    for i, f in enumerate(frames):
        bad = f["cls"] in ("noise", "green")
        if bad and cur is None:
            cur = [i, i]
        elif bad:
            cur[1] = i
        elif cur is not None:
            eps.append(cur)
            cur = None
    if cur is not None:
        eps.append(cur)

    nb_bar_p = nb_bar_probe(rows)
    off, score, score0 = align(frames, rows, walls)
    res["align_offset_s"] = off
    res["align_score"] = score
    res["align_score_at_0"] = score0
    slack = MATCH_FRAMES / 60.0
    out = []
    for a, b in eps:
        fa, fb = frames[a], frames[b]
        w0, w1 = fa["wall"] + off - slack, fb["wall"] + off + slack
        pr = [r for r, w in zip(rows, walls) if w0 <= w <= w1]
        srcs = sorted({r["src"] for r in pr})
        soff = sum(1 for r in pr if r["sr01"] & 0x20)
        wcls = sorted({judge_boot.classify(r, nb_bar_p) for r in pr})
        tcls = sorted({judge_boot.classify({"lit": r["tlit"], "grn": r["tgrn"], "nb": r["tnb"]}, nb_bar_p)
                       for r in pr if r["tlit"] >= 0})
        e = {"first_wall": round(fa["wall"], 3), "last_wall": round(fb["wall"], 3),
             "s_after_video_start": round(fa["wall"] - first_start, 3),
             "s_after_first_present": None if probe0 is None else round(fa["wall"] + off - probe0, 3),
             "frames": b - a + 1, "ms": round((fb["wall"] - fa["wall"]) * 1000, 1),
             "classes": sorted({frames[k]["cls"] for k in range(a, b + 1)}),
             "nb_min_max": [round(min(frames[k]["nb"] for k in range(a, b + 1)), 1),
                            round(max(frames[k]["nb"] for k in range(a, b + 1)), 1)],
             "grn_max": round(max(frames[k]["grn"] for k in range(a, b + 1)), 3),
             "probe_presents": len(pr), "probe_n": [pr[0]["n"], pr[-1]["n"]] if pr else None,
             "probe_src": srcs, "probe_screen_off": soff, "probe_window_classes": wcls, "probe_texture_classes": tcls}
        # The window widened by MATCH_FRAMES takes in neighbouring presents, which may be the title's src=n
        # pictures; H1 asks about the presents that drew or held the flash, not their neighbours.
        bad = [r for r in pr if judge_boot.classify(r, nb_bar_p) in ("noise", "green") or (
            r["tlit"] >= 0 and judge_boot.classify({"lit": r["tlit"], "grn": r["tgrn"], "nb": r["tnb"]},
                                                   nb_bar_p) in ("noise", "green"))]
        e["probe_flash_presents"] = len(bad)
        e["probe_flash_src"] = sorted({r["src"] for r in bad})
        e["H1"] = bool(bad) and e["probe_flash_src"] == ["v"] and any(c in ("noise", "green") for c in tcls)
        e["H2"] = any(r["src"] == "n" and judge_boot.classify(r, nb_bar_p) in ("noise", "green") for r in pr)
        e["H5"] = bool(bad) and sum(1 for r in bad if r["sr01"] & 0x20) * 2 > len(bad)
        e["H4"] = probe0 is None or fa["wall"] + off < probe0 - slack or not pr or not any(
            judge_boot.classify(r, nb_bar_p) in ("noise", "green") for r in pr)
        out.append(e)
    res["episodes"] = out

    # The probe's own view of the same launch, for the H4 reading: presents whose window drew noise or green.
    pw = [r for r in rows if judge_boot.classify(r, nb_bar_p) in ("noise", "green")]
    res["probe_window_flash_presents"] = len(pw)
    res["probe_window_flash_n"] = [pw[0]["n"], pw[-1]["n"]] if pw else None
    res["probe_nb_bar"] = nb_bar_p
    res["verdict"] = ("VALID" if all(res["valid"].values()) else "VOID: " + ", ".join(
        k for k, v in res["valid"].items() if not v)) + "; %d episode(s), %d frame(s) of static or green" % (
        len(out), sum(e["frames"] for e in out))
    return res


def align(frames, rows, walls):
    """(offset s, score, score at 0): the shift of the video's wall times that best matches its lit series to the
    probe window's, each frame against the latest present at or before its shifted time."""
    if not rows:
        return 0.0, None, None
    import bisect
    lo, hi = walls[0], walls[-1]

    def score(off):
        s = n = 0
        for f in frames:
            t = f["wall"] + off
            if t < lo or t > hi:
                continue
            i = bisect.bisect_right(walls, t) - 1
            s += abs(f["lit"] - rows[i]["lit"])
            n += 1
        return s / n if n else None

    best = (0.0, score(0.0))
    k = -int(ALIGN_S * 60)
    while k <= int(ALIGN_S * 60):
        off = k / 60.0
        sc = score(off)
        if sc is not None and (best[1] is None or sc < best[1] - 1e-9):
            best = (off, sc)
        k += 1
    s0 = score(0.0)
    return round(best[0], 4), None if best[1] is None else round(best[1], 4), None if s0 is None else round(s0, 4)


def nb_bar_probe(rows):
    if not rows:
        return judge_boot.NB_FLOOR
    t_end = rows[-1]["t_ms"]
    clean = [r["nb"] for r in rows if r["t_ms"] >= 0.75 * t_end and r["lit"] >= judge_boot.LIT_BLACK]
    return max(judge_boot.NB_FLOOR, 2 * max(clean, default=0.0))


def main():
    a = sys.argv[1:]
    rd = a[0]
    js = a[a.index("--json") + 1] if "--json" in a else None
    res = judge(rd)
    print("verdict:", res["verdict"])
    for k in ("V0_turnip_lines", "V0_stock_lines", "V1_lead_s", "V1_first_frame_class", "valid", "gaps_s", "frames",
              "align_offset_s", "align_score", "align_score_at_0",
              "nb_bar", "clean_nb_max", "clean_grn_max", "probe_presents", "probe_first_present_wall",
              "probe_first_gpu_picture", "probe_nb_bar", "probe_window_flash_presents", "probe_window_flash_n"):
        if k in res:
            print("%s: %s" % (k, res[k]))
    for e in res.get("episodes", []):
        print("episode:", json.dumps(e))
    if js:
        with open(js, "w") as f:
            json.dump(res, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
