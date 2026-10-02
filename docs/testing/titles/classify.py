#!/usr/bin/env python3
"""classify.py -- name the screen a title is on, from one screencap (#433).

The classifier half of route.sh's `drive` step (drive.py is the loop that
captures, calls `classify_frame`, and sends the input the title's profile
maps the state to). It never touches a device and never calls a model:
drive.py layers the Haiku fallback on top when this says `unknown` too often.

    classify.py frame  --profile P FRAME [--prev PREV] [--seen title,main_menu,...]
    classify.py crop   FRAME x,y,w,h OUT.png      cut a reference crop (1280x960 space)
    classify.py diff   A B [--profile P]          the motion numbers for one pair

THE STATES (owner, ADDENDUM 2, 2026-10-01 22:10 PDT). Boot-to-play is a
path through named states, in roughly this order:

    boot -> logo -> intro_video -> title -> main_menu -> profile -> loading
         -> cutscene -> ingame_menu -> play

plus `paused` (an in-level pause overlay: its own state because its input is
"resume", not "advance"), `stalled` (the title's play HUD is up but nothing
on screen moves: a pause the profile has no crop for, or the play input not
reaching the game -- Forza at 0 MPH with the race clock running, run
1790914021-lane.ibcache-3202498), and the two fallbacks `black` and
`unknown`. A profile (drive-profiles/<name>.toml) lists which states its title
has and in what order; drive.py logs a state seen out of that order as an
anomaly.

HOW A FRAME IS NAMED, cheapest and most specific first:

  1. BLACK. Mean luminance (FPS corner masked) under BLACK_LUMA, or a
     frame of one flat colour (grey-level std under FLAT_STD: a fade).
     Before any other state of the run it is `boot`; after, `black` (a load
     or a fade; drive.py waits on both).
  2. NAMED CROPS. `[[crop]]` entries in the profile, each a region, a
     reference PNG beside the profile and a state, scored with the same
     comparator route.sh's waitfor uses (waitfor_match.region_score: mean
     abs grey diff at 64x48). The first non-play crop that matches names the
     frame outright: a title's pause box, its title logo, its Name Entry
     banner. Non-play crops go first because a pause overlay sits on top of
     the live HUD (Sonic Heroes' PAUSE box leaves the score, timer and ring
     count on screen).
  3. PLAY CROPS ARE NOT ENOUGH. A crop whose state is `play` (a HUD element)
     only says the HUD is up. `play` also needs MOTION between this capture
     and the previous one: changed fraction >= the profile's `motion_bar`.
     HUD up and static is `stalled`, HUD up with a changed fraction between
     the two bars is `unknown`. A HUD and a ticking clock alone is never
     `play` (ADDENDUM 2, item 7). Motion is only read against a previous
     capture that was itself play, stalled or unknown: against a pause box
     or a menu, the change is the overlay leaving (Forza's blind route
     alternated pause and race frames, and every race frame read 0.8 moved
     though the car sat at 0 MPH). The first HUD frame after one is `unknown`.
     A profile may set `hud_motion_bar`/`hud_stall_bar` to judge HUD frames
     by their own bars (a title whose scene moves while the player is
     wedged: Sonic Heroes' water and clock read 0.14-0.18 against a wall).
  4. NO CROP MATCHED: liveness and context only, and never `play` -- a frame
     the classifier cannot name is `unknown`, not `play` (ADDENDUM 2, item 6).
       moving: `intro_video` until the run has been past the title into a
               menu (an attract movie that plays when the title sits idle is
               still the intro), then `cutscene`.
       static: `paused` if the run has seen play and the frame is darker
               than the last play frame by `dim_drop` (Forza's pause is a
               dark full-screen menu); otherwise `logo` before `title`,
               `main_menu` after it, `ingame_menu` after play.
       between the bars, or no previous frame to compare: `unknown`.
     A profile with no play crop at all can set `play_by_motion = true`:
     then a moving uncropped frame after `main_menu` is `play` (source
     `motion-only`), the weakest evidence the driver accepts and named so in
     the timeline.

MOTION, AND WHY A CHANGED FRACTION NOT A MEAN. Both frames are greyed, the
FPS overlay and any `motion_mask` regions (a HUD clock) blacked out, and
shrunk to 160x120; the score is the fraction of pixels whose grey level
moved by more than 16. A mean diff lets one bright moving object (a clock,
a spinning ring) look like a moving scene; a fraction asks how much of the
screen moved. Measured on frames already on disk, 5-10 s apart (NOTES.md,
session 2): live Sonic Heroes play 0.10-0.82, Super Monkey Ball's animated
Stage Select 0.18-0.42 (so it needs its crop), Sonic paused 0.000-0.006,
Forza on the grid at 0 MPH with the clock running 0.004-0.015.

COORDINATES. Every region is written in a 1280x960 frame (the Nova's
screencap) and scaled to the picture actually read, so a fixture downscaled
to 320x240 uses the same profile. A screencap that is not 4:3 is cropped to
its centred 4:3 picture first (`content`): the Thor's 1920x1080 pillarboxes a
1440x1080 picture, and its FPS overlay sits in the left bar, outside it.
"""
import argparse
import json
import os
import sys

try:
    import tomllib
except ImportError:            # python < 3.11
    tomllib = None

from PIL import Image
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from waitfor_match import CMP_SIZE  # noqa: E402  -- one comparator for waitfor and drive

STATES = ("boot", "logo", "intro_video", "title", "main_menu", "profile", "loading",
          "cutscene", "ingame_menu", "paused", "play", "stalled", "black", "unknown")
REF_W, REF_H = 1280, 960
FPS_CORNER = (0, 0, 130, 50)     # the FPS: overlay TextView (MainActivity.kt), top-left
BLACK_LUMA = 8.0
FLAT_STD = 3.0                    # a single-colour frame (a fade): 1790830432 222523 is flat grey
MOTION_SIZE = (160, 120)
MOTION_PIXEL = 16                 # grey levels a pixel must move to count as changed
STATIC_BAR = 0.025                # changed fraction at or under this: static
MOVING_BAR = 0.05                 # at or over this: moving. Between: unknown
DIM_DROP = 25.0                   # luma below the last play frame's: a pause dim


def load_profile(path):
    if tomllib is None:
        raise SystemExit("classify.py: python has no tomllib; need 3.11+")
    with open(path, "rb") as f:
        p = tomllib.load(f)
    p["_dir"] = os.path.join(os.path.dirname(os.path.abspath(path)),
                             os.path.splitext(os.path.basename(path))[0])
    for c in p.get("crop", []):
        if c.get("state") not in STATES:
            raise SystemExit("classify.py: %s: crop %s names state %r, not one of %s"
                             % (path, c.get("name"), c.get("state"), ",".join(STATES)))
    return p


def scale_box(box, size):
    """A region in 1280x960 space -> pixel box (l, t, r, b) in a frame of `size`."""
    x, y, w, h = box
    sx, sy = size[0] / REF_W, size[1] / REF_H
    return (int(round(x * sx)), int(round(y * sy)), int(round((x + w) * sx)), int(round((y + h) * sy)))


def content(im):
    """The 4:3 picture inside a screencap. The Nova's 1280x960 is all picture;
    the Thor's 1920x1080 pillarboxes a 1440x1080 picture between black bars,
    and every region, mask and motion score is about the picture."""
    w, h = im.size
    if abs(w / h - REF_W / REF_H) < 0.02:
        return im
    if w / h > REF_W / REF_H:
        cw = int(round(h * REF_W / REF_H))
        return im.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
    ch = int(round(w * REF_H / REF_W))
    return im.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch))


def open_grey(path):
    im = Image.open(path)
    im.load()
    return content(im.convert("L"))


def open_rgb(path):
    im = Image.open(path)
    im.load()
    return content(im.convert("RGB"))


def masked(im, boxes):
    im = im.copy()
    for b in boxes:
        im.paste(0, scale_box(b, im.size))
    return im


def luma(im, profile=None):
    return float(np.asarray(masked(im, [FPS_CORNER]), dtype=np.float64).mean())


_REFS = {}


def _ref(path):
    if path not in _REFS:
        im = Image.open(path)
        im.load()
        _REFS[path] = im
    return _REFS[path]


def crop_score(im, ref_path, box):
    """Mean abs grey diff of a frame region against a reference crop, region
    in 1280x960 space. An opaque reference is scored exactly as waitfor_match
    scores one (both sides at 64x48). A reference WITH AN ALPHA CHANNEL is a
    masked crop (see `learn`): both sides at the reference's own size, and
    only the pixels its alpha marks are compared -- a HUD drawn over a moving
    scene matches whatever the scene behind it is."""
    ref = _ref(ref_path)
    region = im.crop(scale_box(box, im.size))
    if ref.mode != "RGBA":
        a = np.asarray(region.resize(CMP_SIZE), dtype=np.int16)
        b = np.asarray(ref.convert("L").resize(CMP_SIZE), dtype=np.int16)
        return float(np.abs(a - b).mean())
    a = np.asarray(region.resize(ref.size, Image.BILINEAR), dtype=np.int16)
    b = np.asarray(ref.convert("L"), dtype=np.int16)
    m = np.asarray(ref.getchannel("A")) > 127
    if not m.any():
        return 255.0
    return float(np.abs(a - b)[m].mean())


def save_crop(im, box, out):
    """An opaque reference crop, stored grey at LEARN_SCALE of its 1280x960 size:
    it is compared at 64x48, so full resolution is only bytes in the repo."""
    w, h = max(1, int(round(box[2] * LEARN_SCALE))), max(1, int(round(box[3] * LEARN_SCALE)))
    im.crop(scale_box(box, im.size)).resize((w, h), Image.LANCZOS).convert("L").save(out, optimize=True)


LEARN_STD = 14.0     # grey-level std across the sample frames under which a pixel is "the HUD"
LEARN_SCALE = 0.5    # masked references are stored at half the 1280x960 size


def learn(frames, box, out, max_std=LEARN_STD):
    """Build a masked reference crop from frames that all show the same
    overlay over DIFFERENT scenes: the per-pixel median is the reference, and
    the alpha keeps only pixels whose grey level barely moves across the
    frames (the overlay), dropping the scene behind it. Frames whose scenes
    are alike (Sonic wedged against one wall for 8 minutes) teach the wall as
    part of the HUD: pick frames from different places. Returns the kept
    fraction, so a near-empty or near-full mask is visible at once."""
    w, h = int(round(box[2] * LEARN_SCALE)), int(round(box[3] * LEARN_SCALE))
    stack_rgb, stack_l = [], []
    for f in frames:
        im = open_rgb(f)
        r = im.crop(scale_box(box, im.size)).resize((w, h), Image.BILINEAR)
        stack_rgb.append(np.asarray(r, dtype=np.float32))
        stack_l.append(np.asarray(r.convert("L"), dtype=np.float32))
    rgb = np.median(np.stack(stack_rgb), axis=0).astype(np.uint8)
    std = np.stack(stack_l).std(axis=0)
    alpha = np.where(std < max_std, 255, 0).astype(np.uint8)
    img = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
    img.save(out)
    return float((alpha > 0).mean())


def motion(a, b, mask_boxes=()):
    """Changed fraction and mean grey diff between two open grey frames."""
    boxes = [FPS_CORNER] + list(mask_boxes)
    aa = np.asarray(masked(a, boxes).resize(MOTION_SIZE, Image.BILINEAR), dtype=np.int16)
    bb = np.asarray(masked(b, boxes).resize(MOTION_SIZE, Image.BILINEAR), dtype=np.int16)
    d = np.abs(aa - bb)
    return float((d > MOTION_PIXEL).mean()), float(d.mean())


SCENE_SIZE = (32, 24)
SCENE_PIXEL = 24                  # grey levels a 32x24 cell must move to count as changed


def scene(path, mask_boxes=()):
    """The scene's layout: the grey frame, FPS corner and `mask_boxes` blacked
    out, box-averaged to 32x24 cells. At that size a character is a cell or
    two and the level around it is the rest, so two of these taken ~10 s apart
    ask whether the PLAYER got anywhere, where `motion` (2 s apart, 160x120)
    asks whether anything moved -- a team struggling in a corner moves plenty
    (Sonic Heroes, lane.routedriver2 trial 1: 0.35-0.50 changed) and goes
    nowhere."""
    im = masked(open_grey(path), [FPS_CORNER] + list(mask_boxes))
    return np.asarray(im.resize(SCENE_SIZE, Image.BOX), dtype=np.float32)


def scene_change(a, b):
    """Fraction of 32x24 cells that changed between two `scene` arrays."""
    return float((np.abs(a - b) > SCENE_PIXEL).mean())


def line_reading(path, band, hue, min_sat=0.45, min_val=0.35):
    """Where a coloured guide line is in a band ahead of the player (1280x960
    space): (pixel count, centroid x in 1280 space or None). `hue` is
    [lo, hi] degrees. Forza Motorsport's suggested line is green chevrons on
    the asphalt (lane.routedriver2: 330-1290 px in a 1280x200 band over a
    race, centroid at x 650-760 on the straight and 958-1054 at the bend the
    car ran wide on). Saturation and value floors keep the grey road, the sky
    and dull verges out."""
    im = open_rgb(path)
    l, t, r, b = scale_box(band, im.size)
    hsv = np.asarray(im.crop((l, t, r, b)).convert("HSV"), dtype=np.float32)
    h = hsv[..., 0] * (360.0 / 255.0)
    m = (hsv[..., 1] > min_sat * 255) & (hsv[..., 2] > min_val * 255)
    m &= (h >= hue[0]) & (h <= hue[1]) if hue[0] <= hue[1] else ((h >= hue[0]) | (h <= hue[1]))
    xs = np.nonzero(m)[1]
    if not len(xs):
        return 0, None
    sx = REF_W / float(im.size[0])
    return int(len(xs) * sx * sx), float((xs.mean() + l) * sx)


def region_rgb(path, box):
    """Mean RGB of a region (1280x960 space): a HUD badge's colour."""
    im = open_rgb(path)
    a = np.asarray(im.crop(scale_box(box, im.size)), dtype=np.float64).reshape(-1, 3)
    return [float(x) for x in a.mean(0)]


def match_crop(im, crops, profile):
    """First crop in profile order whose region scores <= its threshold.
    Returns (crop, score, all_scores) -- all_scores is every crop's score,
    for the timeline, so a near miss is visible after the fact."""
    scores = {}
    hit = None
    for c in crops:
        s = crop_score(im, os.path.join(profile["_dir"], c["ref"]), c["region"])
        scores[c["name"]] = round(s, 2)
        if hit is None and s <= c["threshold"]:
            hit = (c, s)
    return (hit[0], hit[1], scores) if hit else (None, None, scores)


def classify_frame(frame, prev, profile, seen=(), last_play_luma=None, prev_state=None):
    """Name one capture. `prev` is the previous capture's path (None for the
    first), `seen` the states this run has already been in, `last_play_luma`
    the luminance of the last `play` frame. Returns a dict: state, source
    (what decided it), and the numbers it was decided on."""
    seen = set(seen)
    im = open_grey(frame)
    lu = luma(im)
    out = dict(state="unknown", source="", luma=round(lu, 1), changed=None, diff=None, crop=None, scores={})
    # below the FPS corner, not with it painted black: a blacked-out corner
    # on a flat grey frame is itself a contrast
    below = im.crop(scale_box((0, FPS_CORNER[3], REF_W, REF_H - FPS_CORNER[3]), im.size))
    flat = float(np.asarray(below.resize(MOTION_SIZE), dtype=np.float64).std()) < FLAT_STD
    if lu < BLACK_LUMA or flat:
        out.update(state="black" if seen - {"boot", "black"} else "boot", source="black" if lu < BLACK_LUMA else "flat")
        return out

    crops = profile.get("crop", [])
    hit, score, scores = match_crop(im, [c for c in crops if c["state"] != "play"], profile)
    out["scores"] = scores
    if hit:
        out.update(state=hit["state"], source="crop:" + hit["name"], crop=hit["name"], score=round(score, 2))
        return out

    hud, hscore, hscores = match_crop(im, [c for c in crops if c["state"] == "play"], profile)
    out["scores"].update(hscores)

    if prev is None:
        out["source"] = "no-prev" + (" hud:" + hud["name"] if hud else "")
        return out
    changed, diff = motion(im, open_grey(prev), profile.get("motion_mask", []))
    out.update(changed=round(changed, 4), diff=round(diff, 2))
    static_bar = profile.get("static_bar", STATIC_BAR)
    moving_bar = profile.get("motion_bar", MOVING_BAR)
    moving = changed >= moving_bar
    static = changed <= static_bar

    if hud:
        out["crop"] = hud["name"]
        # HUD-only bars (default: the profile's motion/static bars). A title
        # whose scene keeps moving while the player is wedged -- water, a
        # clock, an idle animation -- sets them per title: Sonic Heroes'
        # team wedged against a Seaside Hill block reads 0.14-0.18 changed,
        # live running 0.59-0.83 (routedriver session 4).
        hud_moving = changed >= profile.get("hud_motion_bar", moving_bar)
        hud_static = changed <= profile.get("hud_stall_bar", static_bar)
        if prev_state is not None and prev_state not in ("play", "stalled", "unknown"):
            # The previous capture was a pause box or a menu: the "motion" is
            # that overlay going away, not the scene. One more capture decides.
            out.update(state="unknown", source="hud:%s+after-%s" % (hud["name"], prev_state))
        elif hud_moving:
            out.update(state="play", source="hud:%s+motion" % hud["name"])
        elif hud_static:
            out.update(state="stalled", source="hud:%s+static" % hud["name"])
        else:
            out.update(state="unknown", source="hud:%s+between" % hud["name"])
        return out

    after_title = bool(seen & {"title", "main_menu", "profile", "ingame_menu", "play", "paused", "loading"})
    after_menu = bool(seen & {"main_menu", "profile", "ingame_menu", "play", "paused"})
    played = bool(seen & {"play", "stalled", "paused"})
    if moving:
        if profile.get("play_by_motion") and after_menu:
            out.update(state="play", source="motion-only")
        else:
            out.update(state="cutscene" if after_menu else "intro_video", source="moving")
    elif static:
        dim = profile.get("dim_drop", DIM_DROP)
        if played and last_play_luma is not None and last_play_luma - lu >= dim:
            out.update(state="paused", source="static+dim")
        elif not after_title:
            out.update(state="logo", source="static")
        else:
            out.update(state="ingame_menu" if played else "main_menu", source="static")
    else:
        out["source"] = "between"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("frame")
    f.add_argument("--profile", required=True)
    f.add_argument("frame")
    f.add_argument("--prev")
    f.add_argument("--seen", default="")
    f.add_argument("--last-play-luma", type=float)
    c = sub.add_parser("crop")
    c.add_argument("frame")
    c.add_argument("region")
    c.add_argument("out")
    d = sub.add_parser("diff")
    d.add_argument("a")
    d.add_argument("b")
    d.add_argument("--profile")
    lr = sub.add_parser("learn", help="masked reference crop from frames showing one overlay over different scenes")
    lr.add_argument("region")
    lr.add_argument("out")
    lr.add_argument("frames", nargs="+")
    lr.add_argument("--max-std", type=float, default=LEARN_STD)
    sc = sub.add_parser("score", help="score frames against one reference crop")
    sc.add_argument("ref")
    sc.add_argument("region")
    sc.add_argument("frames", nargs="+")
    tb = sub.add_parser("table", help="classify a run's frames in order, with every crop's score")
    tb.add_argument("--profile", required=True)
    tb.add_argument("frames", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "table":
        p = load_profile(a.profile)
        names = [c["name"] for c in p.get("crop", [])]
        print("%-40s %-12s %-26s %7s  %s" % ("frame", "state", "source", "changed", " ".join(n[:9] for n in names)))
        prev, seen, lpl, pst = None, [], None, None
        for f in a.frames:
            r = classify_frame(f, prev, p, seen, lpl, pst)
            pst = r["state"]
            if r["state"] not in seen:
                seen.append(r["state"])
            if r["state"] == "play":
                lpl = r["luma"]
            sc = " ".join("%9s" % ("%.1f" % r["scores"][n] if n in r["scores"] else "-") for n in names)
            print("%-40s %-12s %-26s %7s  %s" % (os.path.basename(f)[:40], r["state"], r["source"][:26],
                                                 "" if r["changed"] is None else "%.3f" % r["changed"], sc))
            prev = f
        return 0
    if a.cmd == "learn":
        kept = learn(a.frames, tuple(int(v) for v in a.region.split(",")), a.out, a.max_std)
        print("%s: %d frames, %.1f%% of the region kept" % (a.out, len(a.frames), 100 * kept))
        return 0
    if a.cmd == "score":
        box = tuple(int(v) for v in a.region.split(","))
        for f in a.frames:
            print("%7.2f  %s" % (crop_score(open_grey(f), a.ref, box), f))
        return 0
    if a.cmd == "frame":
        p = load_profile(a.profile)
        r = classify_frame(a.frame, a.prev, p, [s for s in a.seen.split(",") if s], a.last_play_luma)
        print(json.dumps(r))
    elif a.cmd == "crop":
        box = tuple(int(v) for v in a.region.split(","))
        im = open_rgb(a.frame)
        save_crop(im, box, a.out)
        print(a.out)
    elif a.cmd == "diff":
        p = load_profile(a.profile) if a.profile else {}
        ch, mn = motion(open_grey(a.a), open_grey(a.b), p.get("motion_mask", []))
        print("changed=%.4f mean=%.2f" % (ch, mn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
