#!/usr/bin/env python3
"""Drive a title from a cold boot into gameplay by reading the screen.

    pathfind.py <title> [--device nova|thor] [--budget-min 15] --out <dir>

<title> is a title id (8 hex) or a fragment of the ISO's file name. The loop
is screencap -> decide -> input -> wait -> screencap. A MODEL decides, reading
the frame through the Claude CLI (`claude -p`, the Read tool viewing a 640 px
JPEG), given the last steps, the title's knowledge (pathknow/hints/*.md) and
any recorded path (pathknow/paths/<TITLEID>.json, or a series sibling's). It
answers one JSON object: state, why, action, wait_s.

Gameplay is CLAIMED only when the model says gameplay AND an input visibly
changes the playfield: a control pair of frames with no input, then a frame
while the probe input is held; the pixels must move AND a second model call,
shown all three frames, must say the playfield answered the input (not a
menu cursor, not a cutscene or attract demo running by itself). A 60-fps
menu is not gameplay: that was the old pipeline's main false pass (CAPA T6,
T14). Then 30 s more frames (20 s on the Thor, whose fan is dead), stop.

--hold-s N (Nova only) keeps going after the claim: a model-free genre loop of inputs (drive, attack, rally,
on-rails, other, named once by the model) runs while the screen is play, the model reads the screen only when
play may have ended or every 90 s, and it steers back to play with its own inputs. Frames every 30 s, and the
run is held when N seconds of play are judged (hold.jsonl, hold_strip.jpg, result.json "hold").

Cheap checks avoid a model call: a black frame waits; a static frame after
a `wait` on a loading screen waits again; a recorded path's step whose frame
signature matches the screen replays its action. Never the same input on
the same unchanged screen more than 3 times: the step escalates to the
stronger model and is told what failed; a 4th repeat is overridden.

Outputs in --out: frames/NNN-<state>.jpg, steps.jsonl, calls.jsonl (every
model call: model, seconds, tokens, cost), result.json, strip.jpg. On a
confirmed success the path is written to pathknow/paths/<TITLEID>.json
(--no-record to skip).

Inputs go ONLY through perf/pad.sh: `input keyevent` to the app kills the
emulator (AGENTS.md "Working with a device"). The only keyevents sent are
KEYCODE_WAKEUP before launch and 223 (sleep) after the force-stop at the end.
PATHFIND_DRY=1 with --sim <frames dir> touches no device (the selftest).
"""

import argparse
import base64
import glob
import json
import os
import re
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify  # noqa: E402  (content(), motion(), FPS_CORNER: the cheap checks)
sys.path.insert(0, os.path.join(HERE, ".."))
import hangwatch  # noqa: E402  (a HANG: frames, audio and the vCPU all still for HANG_S; stopped with telemetry)

PAD = os.path.join(HERE, "..", "perf", "pad.sh")
KNOW = os.environ.get("PATHFIND_KNOW") or os.path.join(HERE, "pathknow")
TARGETS = os.path.join(HERE, "targets.toml")
BLOCKED = os.path.join(os.environ.get("HAKUX_WORK", "/home/justin/hakux-work"), "host-tools",
                       "blocked-titles.txt")
DEVICES = {
    "nova": ("ee317437", ["/storage/E6C6-D7AA/Games/XBox"]),
    "thor": ("bdc158a5", ["/storage/388C-68F7/ROMS/xbox", "/storage/emulated/0/ROMS/xbox"]),
}
PKG = os.environ.get("PKG", "com.jreinach.hakux.debug")
ACT = PKG + "/com.rfandango.haku_x.LauncherActivity"
# soak_title.sh's tags plus the route's marks and state lines: what title_verdict.py judges a hold from
LOGCAT_SPEC = ("hakuX-crash:V hakuX-audio:I hakuX-audiocap:I hakuX-build:I hakuX-perf:I hakuX-pages:I hakuX:W "
               "hakuX-route:I hakuX-pace:I VALIDATION:W ValidationLayer:W vulkan:W VulkanLoader:W libc:F DEBUG:F *:S")
VERDICT = os.path.join(HERE, "..", "title_verdict.py")
# Sonnet 5 per step, not Haiku: measured 10-02 on the same ESPN frame with the image inline, Sonnet 5
# answered in 3.5-3.9 s (70-80 output tokens), Haiku 4.5 in 6.4-9.1 s (430-500, most of it thinking),
# and Haiku had looped 8 times on a Yes/No dialog in Midnight Club 3. Opus 5.5 when stuck.
FAST = os.environ.get("PATHFIND_FAST", "claude-sonnet-5")
# Opus 5.5 is the stronger step model, but the owner held Opus for token burn on 10-02 and navigation resumed on
# Sonnet only for 10-03 (lane.local addendum 2: Sonnet only, <= $25). Restore Opus when that hold lifts.
STRONG = os.environ.get("PATHFIND_STRONG", "claude-sonnet-5")
STATES = ("intro_video", "publisher_logo", "title_screen", "main_menu", "submenu", "profile_creation",
          "name_entry", "save_load_prompt", "controller_prompt", "loading", "cutscene", "pause",
          "gameplay", "results", "game_over", "continue", "black", "fatal_error", "unknown")
BUTTONS = ("A", "B", "X", "Y", "START", "BACK", "UP", "DOWN", "LEFT", "RIGHT", "L1", "R1", "L3", "R3")
STICK = {"up": (("LY", "min"),), "down": (("LY", "max"),), "left": (("LX", "min"),),
         "right": (("LX", "max"),), "upleft": (("LY", "min"), ("LX", "min")),
         "upright": (("LY", "min"), ("LX", "max"))}
# The right stick, at FULL deflection: Blinx 2 (10-02) did not yaw the camera below about a third.
RSTICK = {"up": (("RY", "min"),), "down": (("RY", "max"),), "left": (("RX", "min"),), "right": (("RX", "max"),)}
# The d-pad BUTTONS (544-547) do nothing in hakuX: the pad's d-pad is the hat, and a back-to-back
# `axis HATY max` / `axis HATY mid` moves a menu ONE row (routes/midnight-club-3.returning.route).
HAT = {"UP": ("HATY", "min"), "DOWN": ("HATY", "max"), "LEFT": ("HATX", "min"), "RIGHT": ("HATX", "max")}
SKIP_LADDER = ("START", "A", "B", "BACK", "X", "Y", "DOWN", "UP", "RIGHT", "LEFT")
# After 2 probes in a row that move nothing at all, the next probe is led by one of these in turn. Black Stone
# (10-03): the player stood in a sword-raised stance for 12 min while 40 stick, d-pad, A and RT probes moved
# nothing; one X lowered the sword and the next stick ran. The pad was never the problem.
UNLOCK_LADDER = ("X", "B", "Y", "R1", "L1", "BACK")
# A probe input refused twice is not tried a third time: the next untried input of this ladder replaces it. The
# Simpsons Road Rage, 10-04: ten RT probes on a live race HUD, each 0.02 idle vs 0.02 under input, until the timer ran
# out; the model was told the earlier throttle probes failed and still chose RT.
PROBE_LADDER = ("HOLD:A:3", "STICK:up:2", "RT:3", "HOLD:X:3", "LT:2", "STICK:left:1.5", "HOLD:B:3")
PROBE_REFUSED_MAX = 2
SIG = (16, 12)                       # a frame's signature: grey, box-averaged
SIG_MATCH = 9.0                      # mean grey-level distance under which two screens are the same
UNCHANGED = 0.01                     # classify.motion changed fraction at or under this: no change
PROBE_MOVED = 0.004                  # the probe frame must change at least this much (10-03 gate: 0.03 refused dark scenes)
PROBE_DARK = 0.6                     # probe grey step = this x the frame's std (floor 4, cap MOTION_PIXEL) -- see probe_change
SELF_MOVING = 0.15                   # no-input change over this: the scene moves by itself; steer L/R
WINDOW_WIN = 1.3                     # an ambiguous probe's extra rounds: input change > this x idle (and + 0.02) wins
BLACK_MODEL_S = 40                   # seconds of black before the model is asked anyway
BLACK_HANG_S = float(os.environ.get("PATHFIND_BLACK_HANG_S", 180))                  # continuous black this long ends the run (Conker, 10-02: 8+ min black
                                     # after a level load, inputs every 5 s changing nothing)
THOR_START_C, THOR_STOP_C = 55.0, 70.0
# Hold-play (10-03): after the claim, keep the player in play. The inputs are a model-free loop per genre;
# the model reads the screen only when play may have ended, every HOLD_CHECK_S, and once for the genre.
HOLD_FRAME_S = 30                    # a kept frame every this many seconds of hold
HOLD_CHECK_S = 90                    # the model reads the screen at least this often while holding
HOLD_NAV_MAX = 12                    # model-steered steps back to play in one episode before the hold gives up
HOLD_REPEAT = 3                      # a cutscene or game over that asked for one button: that press, unlooked, this often
HOLD_REPEAT_STATES = ("cutscene", "game_over")
# A CONTINUE countdown after a lost round (fighting games, 10-04): Guilty Gear XX's A did not continue (three presses,
# the countdown ran out to GAME OVER). Non-title holds try START, then A, unlooked, up to CONTINUE_TRIES presses per
# episode, then ask the model again. The hold log's `continue` look says which press took.
CONTINUE_PRESS = ("START", "A")
CONTINUE_TRIES = 4
CLAIM_REPEAT = 3                     # the claim's unlooked repeats of a single press that advanced a cutscene
CLAIM_REPEAT_STATES = ("cutscene", "intro_video", "publisher_logo")
CLAIM_REPEAT_BOX = 6                 # the same, on a frame the letterbox check says is a cutscene
INTRO_STATES = ("cutscene", "intro_video", "publisher_logo")
# Two kept frames (HOLD_FRAME_S apart) that change less than this at the probe's contrast step: the player did not
# move in that window. 10-03, scratch/posprobe.py on the held runs: Black Stone standing on its octagon for 600 s
# (sword swinging, verdict PASS) 0.002-0.013 per 30-s pair; Panzer Dragoon Orta flying 0.31-0.92.
HOLD_STILL = 0.03
# "should we continue?" (owner 10-04 ~08:10): at 3 and 5 min of a hold longer than 5 min, read the gfps lines the
# hold's logcat has so far. A title on course for clear/close has >= 60% of seconds at >= 30 fps or a median >= 27;
# median < 22 at 3 min, or < 27 at 5 min (and the share under 60%), will not get there: stop the hold, so the
# 3-min telemetry run that follows is the evidence, not 600 s of a known miss.
FPS_GATES = ((180, 22.0), (300, 27.0))
FPS_BAR, FPS_SHARE_OK = 30, 0.60
FPS_TOL = 0.95   # title_verdict's fps_tolerance (targets.toml): a locked-30 title's 29s are on the bar (AvP, 10-04)
# a still window in the drive genre: a car against a wall (Forza, 10-03). Reverse while turning, then drive out the
# other way, alternating sides per still window, before the generic unlock rotation.
HOLD_UNSTICK = {
    "drive": (["LT+left:3", "RT+right:3"], ["LT+right:3", "RT+left:3"]),
    # a gun game that stands still at a wall (Halo 2, 10-03: 31% static in one room): strafe out, firing, the other way
    "shooter": (["STICK:left:2", "RT:1"], ["STICK:right:2", "RT:1"]),
    # a fighter that stands on its arena (Black Stone, 10-03: the attack loop's up and down cancel, 600 s on one spot,
    # window change 0.002-0.013). Each still window walks a square: the four legs are not undone by the next one.
    "attack": (["STICK:right:2", "A"], ["STICK:up:2", "A"], ["STICK:left:2", "A"], ["STICK:down:2", "A"]),
}
# play that drops into a menu right after a loop cycle: a loop button opened it (ToeJam & Earl III, 10-03: the
# "Presents" inventory in 13 of 19 kept frames). Each such drop sheds the next of these from the loop.
HOLD_SHED = ("B", "X", "Y", "BACK", "R1", "L1")
HOLD_SHED_STATES = ("menu", "pause", "other")
HOLD_GENRES = {
    "drive": ["RT:2", "RT+left:0.8", "RT+right:0.8"],
    "attack": ["STICK:up:1", "X", "A", "RSTICK:right:0.5", "STICK:down:1", "B", "RSTICK:left:0.5", "X"],
    # first- and third-person gun play: walk through the level, fire, sweep the look, so the player moves on
    # (Halo 2, 10-03: the attack loop stood at one wall). Fire is the right trigger; a strafe pass changes the spot.
    "shooter": ["STICK:up:1", "RT:1", "RSTICK:right:0.6", "STICK:left:1", "RT:1", "RSTICK:left:0.6", "STICK:down:0.6", "A"],
    "rally": ["A", "STICK:left:0.6", "A", "STICK:right:0.6"],
    "onrails": [],                   # the scene moves on its own: send nothing, watch it
    # basketball, football, hockey, soccer: run with the ball (RT is turbo in the EA and 2K5 families), pass,
    # shoot; on defence the same buttons switch player and steal (NBA Live family, addendum 3, 10-03)
    "team": ["RT:1", "STICK:up:1", "A", "STICK:right:1", "X", "STICK:left:1", "B", "STICK:down:1", "Y"],
    "other": ["STICK:up:1", "A", "RSTICK:right:0.6", "X", "STICK:down:1", "STICK:left:1", "B"],
}
# Title-specific hold loops (10-03 addendum, the owner's Black Stone design). They replace the genre's loop and its
# unlock rotation for these title ids. The walk moves the player with the left stick only, in long strokes that
# change direction. X is pressed once, alone: at the start of the hold and after two still windows in a row. Y, R1,
# BACK and START are never sent in the hold, and B only to close a menu that a look found open (then X, then walk).
TITLE_HOLD = {
    "58490004": {"walk": ["STICK:up:4", "STICK:right:4", "STICK:down:4", "STICK:left:4"]},   # Black Stone: Magic & Steel
    # Panzer Dragoon Orta (10-03 run 3): the dragon flies on its own; the hold keeps it moving (a stick stroke that
    # changes direction each cycle) and firing (RT held 1 s), and taps the lock-on button (A held 0.4 s, then released,
    # so the homing shots fire). No X: this title's X is not in the loop. A title return after a game over gets one
    # unlooked press of "continue" (DOWN to CONTINUE, A), up to twice per hold; the model reads the screen after it.
    "4947002B": {"walk": ["STICK:up:2", "RT:1", "HOLD:A:0.4", "STICK:right:2", "RT:1", "HOLD:A:0.4",
                          "STICK:down:2", "RT:1", "HOLD:A:0.4", "STICK:left:2"],
                 "x": False, "continue": ["DOWN", "A"]},
    # Tork: Prehistoric Punk (10-04 retro-tork): the "other" loop's up and down cancel; 600 s on one spot, the attack
    # effect firing in place. A long climb forward with a hop, bending right and left so the path's turns are taken.
    # the stand-still move for Tork is a hop up the stair: the stick forward, A held through the climb (10-05)
    "55530040": {"walk": ["STICK:up:4", "A", "STICK:up:3", "STICK:right:1.5", "STICK:up:4", "A", "STICK:up:3",
                          "STICK:left:1.5"],
                 "unstick": [["STICK:up:2", "HOLD:A:0.6", "STICK:up:2"]]},
}
TITLE_HOLD_FORBID = ("Y", "R1", "BACK", "START", "B")
# the stand-still detector for title holds (10-05): a stretch of two still windows gets the next of these moves, then the
# walk again. Generic: a hop forward, a turn of the camera, a back-out and a sidestep. A title's own list comes first.
TITLE_UNSTICK = [["STICK:up:1.5", "HOLD:A:0.6"], ["RSTICK:left:1", "STICK:up:2"],
                 ["STICK:down:1.5", "STICK:left:1.5"], ["RSTICK:right:1", "STICK:up:2"]]


def now():
    return time.time()


def dry():
    return bool(os.environ.get("PATHFIND_DRY"))


# ------------------------------------------------------------------ device

class Device:
    def __init__(self, label):
        self.label = label
        self.serial, self.roots = DEVICES[label]
        self.env = dict(os.environ, SERIAL=self.serial)

    def sh(self, cmd, timeout=20):
        try:
            r = subprocess.run(["adb", "-s", self.serial, "shell", cmd], capture_output=True, text=True,
                               timeout=timeout)
            return r.stdout
        except subprocess.TimeoutExpired:
            return ""

    def capture(self, path):
        for _ in range(3):
            try:
                with open(path, "wb") as f:
                    r = subprocess.run(["adb", "-s", self.serial, "exec-out", "screencap", "-p"], stdout=f,
                                       stderr=subprocess.DEVNULL, timeout=30)
                if r.returncode == 0 and os.path.getsize(path) > 1000:
                    return True
            except (subprocess.TimeoutExpired, OSError):
                pass
            time.sleep(1)
        return False

    def pad(self, *args):
        try:
            subprocess.run(["bash", PAD] + [str(a) for a in args], env=self.env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=30)
        except subprocess.TimeoutExpired:
            pass

    def foreground(self):
        out = self.sh("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        return (not out.strip()) or PKG in out

    def alive(self):
        return f"{PKG}:xemu" in self.sh("ps -A -o NAME").split()

    def isos(self):
        """(root, file) for every ISO; three tries, since one WSL adb hiccup
        returns an empty listing (ESPN NFL 2K5 attempt 3, 10-02)."""
        for _ in range(3):
            names = []
            for root in self.roots:
                for line in self.sh(f"ls {root}/", timeout=30).splitlines():
                    line = line.strip()
                    if line.lower().endswith(".iso"):
                        names.append((root, line))
            if names:
                return names
            time.sleep(3)
        return names

    def launch(self, iso_path):
        self.sh(f"am force-stop {PKG}")
        self.sh("input keyevent KEYCODE_WAKEUP")
        time.sleep(1.5)
        q = "'" + iso_path.replace("'", "'\\''") + "'"
        self.sh(f"am start -a android.intent.action.VIEW -n {ACT} --es rom_path {q}")
        self.pad("detect")

    def stop(self, screen_off=True):
        self.sh(f"am force-stop {PKG}")
        if screen_off:
            self.sh("input keyevent 223")

    def route_log(self, msg):
        """A `hakuX-route: <msg>` line in logcat (route.sh's marks, soak_title.sh's soak start/end)."""
        self.sh(f"log -t hakuX-route '{msg}'")

    def logcat_start(self, path):
        """Follow logcat from now into `path` with the soak's tags: title_verdict.py reads it."""
        f = open(path, "w")
        # `-v time` (MM-DD HH:MM:SS.mmm V/tag(pid): msg), the format title_verdict.py's LINE parses and soak_title.sh writes
        return subprocess.Popen(["adb", "-s", self.serial, "logcat", "-v", "time", "-T", "1"]
                                + LOGCAT_SPEC.split(), stdout=f, stderr=subprocess.DEVNULL)

    def xo_c(self):
        """The Thor's xo-therm in C (None when unread)."""
        out = self.sh("for z in /sys/class/thermal/thermal_zone*; do "
                      "[ \"$(cat $z/type)\" = xo-therm ] && cat $z/temp; done")
        try:
            v = float(out.split()[0])
            return v / 1000 if v > 200 else v
        except (IndexError, ValueError):
            return None


class SimDevice:
    """PATHFIND_DRY: frames from a directory, in order, one per capture."""

    def __init__(self, label, frames):
        self.label, self.serial, self.roots = label, "SIM", ["/sim"]
        self.frames = sorted(glob.glob(os.path.join(frames, "*.png")) + glob.glob(os.path.join(frames, "*.jpg")))
        self.i = 0
        self.sent = []

    def capture(self, path):
        if not self.frames:
            return False
        src = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        Image.open(src).convert("RGB").save(path, "PNG")
        return True

    def pad(self, *args):
        self.sent.append(" ".join(str(a) for a in args))

    def foreground(self):
        return True

    def alive(self):
        return True

    def isos(self):
        return [("/sim", "00000000-Sim.iso")]

    def launch(self, iso_path):
        self.sent.append("launch")

    def stop(self, screen_off=True):
        self.sent.append("stop")

    def route_log(self, msg):
        self.sent.append("log " + msg)

    def logcat_start(self, path):
        return None

    def xo_c(self):
        return None


# ------------------------------------------------------------------ frames

def open_content(path):
    im = Image.open(path)
    im.load()
    return classify.content(im.convert("RGB"))


def to_jpeg(png, jpg, width=640):
    im = open_content(png)
    h = int(round(im.size[1] * width / im.size[0]))
    im.resize((width, h), Image.BILINEAR).save(jpg, "JPEG", quality=80)


def grey(path):
    return classify.masked(open_content(path).convert("L"), [classify.FPS_CORNER])


def signature(path):
    return np.asarray(grey(path).resize(SIG, Image.BOX), dtype=np.float32)


def sig_dist(a, b):
    return float(np.abs(np.asarray(a, dtype=np.float32) - np.asarray(b, dtype=np.float32)).mean())


def changed(a, b):
    """Changed fraction between two frame files (classify.motion's 160x120 rule)."""
    return classify.motion(grey(a), grey(b))[0]


def probe_change(a, b, c):
    """(idle change, input change) for a probe's three frames. Same 160x120 rule as `changed`, but the grey step
    scales with the first frame's contrast: a dark scene (Black Stone's dungeon, std ~14) moves its character by
    well under 16 levels. Gate 10-03 (scratch/probegate, labelled stored triplets): the fixed 16-level step refused
    every real control in that scene; this step accepts them and accepts no labelled cutscene or menu on its own."""
    ga = grey(a)
    step = probe_step(ga)
    gb, gc = grey(b), grey(c)
    return classify.motion(ga, gb, pixel=step)[0], classify.motion(gb, gc, pixel=step)[0]


def probe_step(g):
    std = float(np.asarray(g.resize(classify.MOTION_SIZE, Image.BILINEAR), dtype=np.float64).std())
    return min(classify.MOTION_PIXEL, max(4.0, PROBE_DARK * std))


def window_change(a, b):
    """Change between two kept hold frames at the probe's contrast step: did the player or camera move?"""
    ga = grey(a)
    return classify.motion(ga, grey(b), pixel=probe_step(ga))[0]


def probe_key(tok):
    """A probe input without its seconds: RT:1.5 and RT:3 are one input (RT), HOLD:A:3 is HOLD:A."""
    head, _, tail = tok.rpartition(":")
    return head if head and re.fullmatch(r"[\d.]+", tail) else tok


def route_frame(out, png):
    """A kept hold frame, linked as route-frames/HHMMSS-hold.png (its capture time): the name title_verdict.py's
    liveness and position tests read the scored window from (hitch_report.FRAME_NAME). Without them the window is
    `unmeasured` and fails (failgate, 10-04: RalliSport's 671-s hold at fps_ok 1.0 scored FAIL that way)."""
    d = os.path.join(out, "route-frames")
    os.makedirs(d, exist_ok=True)
    dest = os.path.join(d, time.strftime("%H%M%S", time.localtime(os.path.getmtime(png))) + "-hold.png")
    if not os.path.exists(dest):
        try:
            os.link(png, dest)
        except OSError:
            import shutil
            shutil.copyfile(png, dest)
    return dest


def fps_course(logcat):
    """The hold so far from its logcat's hakuX-perf `gfps=` lines (one per 1-2 s): {n samples, median, share at
    >= FPS_BAR * FPS_TOL}."""
    try:
        vals = [int(m.group(1)) for m in re.finditer(r"gfps=(\d+)", open(logcat, errors="replace").read())]
    except OSError:
        vals = []
    if not vals:
        return {"n": 0, "median": None, "share": None}
    return {"n": len(vals), "median": float(np.median(vals)),
            "share": round(sum(v >= FPS_BAR * FPS_TOL for v in vals) / len(vals), 3)}


def fps_gate_fails(course, floor):
    """True when the hold is not on course for the 30-fps bar: median below `floor` and the share under 60%."""
    return course["n"] >= 30 and course["median"] < floor and course["share"] < FPS_SHARE_OK


def letterboxed(path):
    """Black bars top AND bottom around a lit middle: a cutscene. Bruce Lee,
    10-02: a letterboxed intro cinematic whose character moves on its own was
    claimed and confirmed as gameplay."""
    g = np.asarray(grey(path), dtype=np.float32)
    h = g.shape[0]
    top, bot, mid = g[: int(h * 0.09)], g[int(h * 0.91):], g[int(h * 0.3): int(h * 0.7)]
    return bool(top.mean() < 10 and bot.mean() < 10 and top.std() < 6 and bot.std() < 6 and mid.mean() > 25)


def is_black(path):
    g = np.asarray(grey(path), dtype=np.float32)
    return g.mean() < classify.BLACK_LUMA and g.std() < 6


def strip(paths, out, cols=4, width=320):
    paths = [p for p in paths if p and os.path.exists(p)]
    if not paths:
        return None
    ims = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        h = int(round(im.size[1] * width / im.size[0]))
        im = im.resize((width, h), Image.BILINEAR)
        ImageDraw.Draw(im).text((4, 4), os.path.basename(p)[:44], fill=(255, 255, 0))
        ims.append(im)
    h = max(i.size[1] for i in ims)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * width, rows * h))
    for n, im in enumerate(ims):
        sheet.paste(im, ((n % cols) * width, (n // cols) * h))
    sheet.save(out, "JPEG", quality=80)
    return out


# ------------------------------------------------------------------ titles

def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def targets():
    """title id -> {name, iso{device}} from targets.toml (a minimal reader:
    tomllib is 3.11+, and only [titles."ID"] name/iso are needed)."""
    out, cur = {}, None
    try:
        lines = open(TARGETS).read().splitlines()
    except OSError:
        return out
    for line in lines:
        m = re.match(r'\[titles\."([0-9A-Fa-f]{8})"\]', line)
        if m:
            cur = out.setdefault(m.group(1).upper(), {"name": "", "iso": {}})
            continue
        if line.startswith("["):
            cur = None
        if cur is None:
            continue
        m = re.match(r'name\s*=\s*"(.*)"', line)
        if m:
            cur["name"] = m.group(1)
        m = re.match(r"iso\s*=\s*\{(.*)\}", line)
        if m:
            for k, v in re.findall(r'(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"', m.group(1)):
                cur["iso"][k] = v
    return out


def blocked(tid, name):
    try:
        for line in open(BLOCKED):
            line = line.split("#")[0].strip()
            if not line:
                continue
            key = line.split("\t")[0].strip()
            if key and (key.upper() == (tid or "").upper() or norm(key) in norm(name)):
                return line
    except OSError:
        pass
    return None


def resolve(dev, arg):
    """-> (title id or None, display name, device path of the ISO)."""
    t = targets()
    isos = dev.isos()
    hexid = arg.upper() if re.fullmatch(r"[0-9A-Fa-f]{8}", arg) else None
    cands = []
    for root, f in isos:
        fid = f[:8].upper() if re.match(r"[0-9A-Fa-f]{8}-", f) else None
        if fid is None:
            for k, v in t.items():
                if v["iso"].get(dev.label) == f:
                    fid = k
        if hexid:
            if fid == hexid:
                cands.append((fid, f, root))
        elif norm(arg) in norm(f) or (fid and fid in t and norm(arg) in norm(t[fid]["name"])):
            cands.append((fid, f, root))
    if not cands:
        sys.exit(f"pathfind: no ISO on {dev.label} matches {arg!r}")
    if len(cands) > 1:
        exact = [c for c in cands if not c[1].startswith("iso-")]
        if len(exact) != 1:
            sys.exit(f"pathfind: {arg!r} matches {len(cands)} ISOs: " + "; ".join(c[1] for c in cands))
        cands = exact
    fid, f, root = cands[0]
    name = (t.get(fid or "", {}).get("name") or
            re.sub(r"\.(xiso\.)?iso$", "", re.sub(r"^[0-9A-Fa-f]{8}-", "", f)).replace("_", " "))
    return fid, name, f"{root}/{f}"


# ------------------------------------------------------------------ knowledge

def series_files(name):
    """hints/series-<slug>.md whose every slug word appears in the title's name."""
    words = set(norm(name).split())
    out = []
    for p in sorted(glob.glob(os.path.join(KNOW, "hints", "series-*.md"))):
        slug = os.path.basename(p)[len("series-"):-3]
        if slug and all(w in words for w in slug.split("-")):
            out.append(p)
    return out


def hint_files(tid, name):
    files = [os.path.join(KNOW, "hints", "global.md")]
    if tid:
        files.append(os.path.join(KNOW, "hints", f"pub-{tid[:4].upper()}.md"))
        files.append(os.path.join(KNOW, "hints", f"pub-{tid[:4].lower()}.md"))
    files += series_files(name)
    # learned-<file>: what pathfind itself appended after a success, one line per title. A separate file so
    # lane.pathknow's seeded files and pathfind's appends never edit the same lines.
    files += [os.path.join(os.path.dirname(f), "learned-" + os.path.basename(f)) for f in list(files)]
    seen, out = set(), []
    for f in files:
        if os.path.exists(f) and os.path.realpath(f) not in seen:
            seen.add(os.path.realpath(f))
            out.append(f)
    return out


def knowledge(tid, name, per_file=9000):
    """The hint files' text, each cut at `per_file` chars (pathknow's global.md is ~8 KB)."""
    parts = []
    for f in hint_files(tid, name):
        txt = open(f).read().strip()
        parts.append(f"### {os.path.relpath(f, KNOW)}\n{txt[:per_file]}")
    return "\n\n".join(parts)


def learn(tid, name, device, steps, minutes):
    """After a confirmed success: one line per title in hints/learned-pub-<4hex>.md and in
    learned-<series file> for each series this title matches; the path condensed to the useful inputs."""
    if not tid:
        return []
    seq, last = [], None
    for st in steps:
        if st.get("state") in ("gameplay", "results", "pause", "game_over"):
            continue           # a refused claim and what play led to: not the way in
        if st.get("src") in ("probe", "check", "black", "static") or not st.get("action"):
            continue
        if st.get("changed") is not None and st["changed"] <= UNCHANGED:
            continue
        tag = f"{st.get('state')} {' '.join(st['action'])}"
        if tag != last:
            seq.append(tag)
        last = tag
    line = (f"- {name} ({tid}, {device}, pathfind {time.strftime('%Y-%m-%d')}): gameplay in {minutes:.1f} min via "
            + " -> ".join(seq))[:600]
    written = []
    hints = os.path.join(KNOW, "hints")
    os.makedirs(hints, exist_ok=True)
    targets = [os.path.join(hints, f"learned-pub-{tid[:4].upper()}.md")]
    targets += [os.path.join(hints, "learned-" + os.path.basename(f)) for f in series_files(name)]
    for t in targets:
        old = open(t).read() if os.path.exists(t) else (
            "# Learned by pathfind: the inputs that reached confirmed gameplay, one line per title\n")
        old = "".join(l for l in old.splitlines(True) if f"({tid}," not in l)   # one line per title
        with open(t, "w") as f:
            f.write(old + line + "\n")
        written.append(t)
    return written


STOP = {"the", "of", "and", "edition", "xiso", "iso", "usa", "europe", "japan", "game", "games", "pro", "tour"}


def name_words(name):
    return {w for w in norm(name).split() if len(w) >= 3 and w not in STOP and not re.fullmatch(r"[0-9a-f]{8}", w)}


def load_paths(tid, name):
    """(own path or None, [sibling paths]) from pathknow/paths/*.json. A
    sibling is a recorded title whose name shares a series hint file with
    ours, or one from the same publisher (title id's first 4 hex) sharing a
    distinctive name word ("espn", "fifa", "tiger"), most shared words first."""
    own, sibs = None, []
    mine = set(os.path.basename(f) for f in series_files(name))
    words = name_words(name)
    for p in sorted(glob.glob(os.path.join(KNOW, "paths", "*.json"))):
        try:
            d = json.load(open(p))
        except (OSError, ValueError):
            continue
        if tid and d.get("title_id", "").upper() == tid.upper():
            own = d
        elif mine and mine & set(os.path.basename(f) for f in series_files(d.get("name", ""))):
            sibs.append((99, d))
        elif tid and d.get("title_id", "")[:4].upper() == tid[:4].upper() and words & name_words(d.get("name", "")):
            sibs.append((len(words & name_words(d.get("name", ""))), d))
    sibs.sort(key=lambda x: (-x[0], not x[1].get("complete", True)))   # complete paths first
    return own, [d for _, d in sibs]


def path_text(d, limit=24):
    rows = [f"- {s['state']}: {s['why']} -> {' '.join(s['action']) or 'wait'} (wait {s['wait_s']}s)"
            for s in d.get("steps", []) if s.get("useful", True)][:limit]
    return f"Recorded path of {d.get('name')} ({d.get('title_id')}), {d.get('device')}:\n" + "\n".join(rows)


# ------------------------------------------------------------------ model

SYSTEM = ("You drive an original Xbox game running in an emulator on a handheld, from boot into gameplay, "
          "using only a gamepad. You see one screenshot per step. Answer with one JSON object and nothing else.")

RULES = """Your job: get from boot into real gameplay (the player controls a character, vehicle, ball or
cursor in the game world, usually with a HUD) as fast as possible, with default settings.

How to act:
- Intro videos and publisher logos: skip with START, then A; if the same video keeps playing after both,
  wait 3-5 s and look again. Several logos in a row is normal: a NEW logo is progress, not failure.
- Title screen ("Press Start"): START (or A).
- Menus: steer actively. Choose what leads to play fastest with defaults: Single Player, Quick Play,
  Exhibition, Quick Race, Arcade, New Game, Start Game, Play Now, Story/Campaign start. Avoid Options,
  Online/Xbox Live, Extras, Load. Read where the cursor/highlight IS before moving it; send the moves and the
  confirm together, e.g. ["DOWN","DOWN","A"].
- Team/character/car/course select: accept the default with A, repeatedly if several confirms. Never START on a
  select screen: a "PRESS START" over an empty player slot on a fighting character select did not start the match
  (Guilty Gear XX, 10-04); A on the highlighted character did (the claim's steps). START is for title/attract prompts.
- A CONTINUE countdown after a lost round (fighting games; "continue" with a countdown and credits): one START,
  then A if it stays. Do not wait it out: the countdown ends in GAME OVER, then the title, then the menus again.
  Guilty Gear XX, 10-04: START on the CONTINUE led to the character select, A on the highlighted fighter then
  resumed the round; A on the CONTINUE ran the countdown out.
- A live fighting round: "PRESS START" over an EMPTY player-2 slot in the HUD is a join prompt, not a title or a
  menu. Do not press START there: it opens the pause menu (Guilty Gear XX, 10-04). A round with the HUD and a
  counting timer is gameplay: probe with the stick. A "PLEASE WAIT" or a round-start banner (3, 2, 1, FIGHT, the
  round title) is not yet live: wait 2 s and look again before probing.
- Sports controller/team-select screens: if controller icons sit in the MIDDLE column between the two teams,
  nobody is assigned and the CPU plays both sides (a match that looks live but ignores the stick: ESPN NHL
  2K5, 10-02). First move controller 1 under a team with LEFT or RIGHT (or STICK:left:0.3), then A.
- Profile creation / name entry: on a keyboard, A TYPES the highlighted letter. Prefer START, which usually
  jumps to Done/Accept; then A on Done/OK. Accept defaults.
- Save/load prompts: "no storage device / continue without saving": choose continue. Prompts that create a
  save: Yes is fine. Beware prompts whose default is No when Yes is needed to proceed.
- A profile or save marked damaged/corrupt ("cannot be used", "Press X to delete") never loads: A on it only
  loops back (Forza, 10-03: 25 presses). Move to NEW PROFILE / Create New and make a fresh one; if there is no
  create option, delete the damaged one (X) first.
- Racing: hold the throttle 3 s or more (RT:3); 1.5-s taps only creep. A car at 0 MPH nosed into a wall or
  facing the wrong way does not move on RT: reverse while turning (LT+left:3 or LT+right:3), then RT+<the
  other way>:3 (Forza, 10-03: 40 RT/stick inputs against the pit wall, none reversed).
- "Continue" may replay a cutscene; prefer New Game/Start for a cold boot.
- Controller/"press start to begin" prompts: START or A.
- Loading screens: wait (wait_s 3-8). Cutscenes: try START, then A, then B/BACK to skip.
- Pause menus: choose Resume/Continue (A) or press START.
- Never press BACK/B on a main menu unless you are deliberately backing out of a wrong submenu.
- Never press the same input on an unchanged screen more than 3 times: change the input.
- UP/DOWN/LEFT/RIGHT move a menu cursor ONE row/column per press. Before confirming, check which item is
  REALLY highlighted (colour, arrow, box); on a Yes/No dialog the options may be side by side (LEFT/RIGHT).
- Sports: a kickoff, tip-off, faceoff, serve or pre-snap play-call screen waits for you: pick a play / press
  A to start the play, then the player can be moved. American football: a play-call screen is a MENU; press
  A to pick the play (sometimes twice: formation, then play), then A again to snap; only after the snap is it
  gameplay: then probe ["A", "STICK:up:1.5"] (snap and run).

Inputs (the "action" list, up to 8 tokens, sent in order ~0.4 s apart):
  A B X Y START BACK UP DOWN LEFT RIGHT L1 R1 L3 R3   one press (UP/DOWN/LEFT/RIGHT are the d-pad)
  STICK:<up|down|left|right|upleft|upright>:<seconds>  hold the left stick
  RSTICK:<up|down|left|right>:<seconds>                 hold the right stick (the camera or look; Halo's Armory
                                                       look test and tutorials need it: Halo 2, 10-03)
  RT:<seconds>  LT:<seconds>                           hold a trigger (accelerate/brake in racing games)
  RT+<left|right|up|down>:<seconds>  LT+<...>:<seconds>  a trigger and the left stick together (steer on the
                                                       gas; LT+left reverses while turning off a wall)
  HOLD:<button>:<seconds>                              hold a button
An empty list [] means wait and look again.

States (pick exactly one): intro_video, publisher_logo, title_screen, main_menu, submenu, profile_creation,
name_entry, save_load_prompt, controller_prompt, loading, cutscene, pause, gameplay, results, game_over,
continue, black, fatal_error, unknown. fatal_error is a screen no input can clear: "there is a problem with the disc /
dirty or damaged", "an error has occurred", a crash or dashboard error screen.

Say "gameplay" only when you see player-controlled play (a HUD, a playfield with the player's character or
vehicle), not a menu, not a replay/attract demo with "Press Start", not a cutscene with letterbox bars or
subtitles. The "FPS: NN" text at the top-left is the EMULATOR's overlay on every frame: it is NOT a game
HUD and never evidence of gameplay. An intro cinematic right after the publisher logos, before any title
screen or menu, is a cutscene even when it shows the hero in the game world: skip it. When you say gameplay, also give "probe": a list of inputs whose LAST one should visibly move
the player or camera for ~1.5 s (racing: ["RT:1.5"]; on foot: ["STICK:up:1.5"]); put any input needed to
start the play first (a kickoff or serve: ["A", "STICK:up:1.5"]).

Answer exactly:
{"see": "<a literal description of the image: its text, logos, HUD, highlighted item>",
 "state": "<state>", "why": "<one line: why this state and action, where the cursor is>",
 "action": ["<token>", ...], "wait_s": <seconds to wait after the inputs, 1-10>, "probe": [<tokens>] or []}"""


PLAN_RULE = """If the recorded path above clearly matches where you are, you may ALSO answer "plan": the inputs
for the next screens from that path, in order, as [{"expect": "<state of that screen>", "action": [...],
"wait_s": n}, ...] (at most 5; menus, prompts and loads only, never gameplay). They are sent one screen at a
time without asking you, as long as each input visibly changes the screen; anything unexpected comes back to
you. Leave "plan" out when unsure.

"""


def parse_json(text):
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    blob = m.group(0)
    for cut in range(len(blob), 0, -1):
        if blob[cut - 1] != "}":
            continue
        try:
            return json.loads(blob[:cut])
        except ValueError:
            continue
    return None


class Model:
    def __init__(self, out, sim=None):
        self.out = out
        self.log = os.path.join(out, "calls.jsonl")
        self.sim = sim               # PATHFIND_DRY: a list of canned answers
        self.calls = 0
        self.by_model = {}

    def ask(self, model, prompt, purpose, images=()):
        """One call; `images` (JPEG paths) go INLINE in a stream-json user
        message, so the model answers in one turn with no Read tool call."""
        t0 = now()
        rec = {"t": round(t0, 3), "model": model, "purpose": purpose, "images": len(images)}
        if self.sim is not None:
            ans = self.sim.pop(0) if self.sim else {"state": "unknown", "why": "sim exhausted", "action": []}
            text, meta = json.dumps(ans), {}
        else:
            cmd = ["claude", "-p", "--model", model, "--input-format", "stream-json", "--output-format",
                   "stream-json", "--verbose", "--tools", "", "--system-prompt", SYSTEM, "--no-session-persistence"]
            content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                     "data": base64.b64encode(open(i, "rb").read()).decode()}}
                       for i in images]
            # text FIRST, images after it: with the image first and a long prompt, Sonnet 5 read Tiger Woods
            # 2005's bright logo as "black frame with only the FPS overlay" 12 times running, anchored on the
            # history (10-02; 2/2 wrong image-first, 4/4 right image-last, scratch blacktest2)
            msg = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": prompt}] + content}}
            try:
                r = subprocess.run(cmd, input=json.dumps(msg) + "\n", capture_output=True, text=True, timeout=240,
                                   cwd=self.out)
                meta = {}
                for line in r.stdout.splitlines():
                    if line.startswith("{") and '"result"' in line:
                        try:
                            d = json.loads(line)
                        except ValueError:
                            continue
                        if d.get("type") == "result":
                            meta = d
                text = meta.get("result", "") if isinstance(meta, dict) else ""
                if not text:
                    rec["error"] = (r.stderr or r.stdout)[-400:]
            except subprocess.TimeoutExpired:
                meta, text = {}, ""
                rec["error"] = "timeout 240 s"
        rec["seconds"] = round(now() - t0, 2)
        u = meta.get("usage", {}) if isinstance(meta, dict) else {}
        rec.update({"in": u.get("input_tokens"), "out": u.get("output_tokens"),
                    "cache_read": u.get("cache_read_input_tokens"),
                    "cache_write": u.get("cache_creation_input_tokens"),
                    "cost_usd": meta.get("total_cost_usd") if isinstance(meta, dict) else None})
        ans = parse_json(text) if text else None
        rec["answer"] = ans if ans is not None else (text or "")[:300]
        self.calls += 1
        self.by_model[model] = self.by_model.get(model, 0) + 1
        with open(self.log, "a") as f:
            f.write(json.dumps(rec) + "\n")
        return ans if isinstance(ans, dict) else None


# ------------------------------------------------------------------ the agent

def clean_action(a):
    """The model's action -> a list of valid tokens (invalid ones dropped)."""
    if isinstance(a, str):
        a = [] if a.strip().lower() in ("", "wait", "none") else re.split(r"[ ,]+", a.strip())
    out = []
    for tok in (a or [])[:8]:
        tok = str(tok).strip()
        up = tok.upper()
        if up in BUTTONS or up in ("SELECT", "BACK"):
            out.append("BACK" if up == "SELECT" else up)
        elif re.fullmatch(r"(STICK:(up|down|left|right|upleft|upright)|RSTICK:(up|down|left|right)|RT|LT"
                          r"|(RT|LT)\+(up|down|left|right)|HOLD:[A-Z0-9]+):[0-9.]+", tok, re.I):
            parts = tok.split(":")
            parts[0] = parts[0].upper()
            if parts[0] in ("STICK", "RSTICK"):
                parts[1] = parts[1].lower()
            if "+" in parts[0]:
                trig, d = parts[0].split("+")
                parts[0] = f"{trig}+{d.lower()}"
            if parts[0] == "HOLD":
                parts[1] = parts[1].upper()
                if parts[1] not in BUTTONS:
                    continue
            secs = min(max(float(parts[-1]), 0.2), 4.0)
            out.append(":".join(parts[:-1] + [f"{secs:g}"]))
    return out


class Agent:
    def __init__(self, dev, model, tid, name, iso, out, budget_s, record=True):
        self.dev, self.model, self.tid, self.name, self.iso = dev, model, tid, name, iso
        self.out, self.budget_s, self.record = out, budget_s, record
        self.frames = os.path.join(out, "frames")
        os.makedirs(self.frames, exist_ok=True)
        self.steps = []              # every step, as written to steps.jsonl
        self.n = 0
        self.t0 = now()
        self.own, self.sibs = load_paths(tid, name)
        self.cursor = 0              # next index into self.own's steps a replay may use
        self.sib_cursor = {}
        self.plan = []               # the model's planned next screens (from a guide), sent without a call
        self.hints = knowledge(tid, name)
        self.probes = 0
        self.dead_probes = 0         # probes in a row whose input moved nothing at all (UNLOCK_LADDER)
        self.probe_tries = {}        # probe_key -> confirms that used it (PROBE_LADDER past PROBE_REFUSED_MAX)
        self.black_since = None
        self.hold_s = 0              # hold-play: seconds of play to hold after the claim (0: off)
        self.goal = ""               # --goal: a settings goal on the way in (a sports family's longest quarter)
        self.result = {"title_id": tid, "name": name, "device": dev.label, "iso": iso, "result": "running",
                       "tool": subprocess.run(["git", "hash-object", os.path.abspath(__file__)], capture_output=True,
                                              text=True).stdout.strip()[:10],
                       "started": time.strftime("%Y-%m-%d %H:%M:%S %Z")}
        self.thermal = []
        self.watch = None            # hangwatch: the live logcat judge of the claim and the hold (None: no logcat)

    # -- bookkeeping
    def el(self):
        return now() - self.t0

    def frame(self, tag):
        png = os.path.join(self.frames, f"{self.n:03d}-{tag}.png")
        if not self.dev.capture(png):
            return None, None
        jpg = png[:-4] + ".jpg"
        to_jpeg(png, jpg)
        return png, jpg

    def write_step(self, rec):
        rec = dict(rec, n=self.n, t=round(self.el(), 1))
        self.steps.append(rec)
        with open(os.path.join(self.out, "steps.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"[{rec['t']:6.1f}s] #{self.n:3d} {rec.get('state', '?'):17s} {rec.get('src', ''):7s} "
              f"{' '.join(rec.get('action', [])) or 'wait':24s} {rec.get('why', '')[:90]}", flush=True)

    # -- input
    def send(self, action):
        for tok in action:
            if tok in HAT:
                ax, v = HAT[tok]
                self.dev.pad("axis", ax, v)
                self.dev.pad("axis", ax, "mid")
                time.sleep(0.35)
                continue
            if tok in BUTTONS:
                self.dev.pad("press", tok, 120)
                time.sleep(0.35)
                continue
            parts = tok.split(":")
            secs = float(parts[-1])
            if parts[0] in ("STICK", "RSTICK"):
                axes = (STICK if parts[0] == "STICK" else RSTICK)[parts[1]]
                for ax, v in axes:
                    self.dev.pad("axis", ax, v)
                time.sleep(secs)
                for ax, _ in axes:
                    self.dev.pad("axis", ax, "mid")
            elif parts[0] in ("RT", "LT"):
                self.dev.pad("axis", parts[0], "max")
                time.sleep(secs)
                self.dev.pad("axis", parts[0], "min")
            elif "+" in parts[0]:
                # a trigger and the left stick together: steer on the gas, or reverse while turning off a wall
                trig, d = parts[0].split("+")
                self.dev.pad("axis", trig, "max")
                for ax, v in STICK[d]:
                    self.dev.pad("axis", ax, v)
                time.sleep(secs)
                for ax, _ in STICK[d]:
                    self.dev.pad("axis", ax, "mid")
                self.dev.pad("axis", trig, "min")
            elif parts[0] == "HOLD":
                self.dev.pad("hold", parts[1])
                time.sleep(secs)
                self.dev.pad("release", parts[1])
            time.sleep(0.25)

    # -- the model's view
    def history(self, k=6):
        rows = []
        for s in self.steps[-k:]:
            ch = s.get("changed")
            chs = "?" if ch is None else ("no change" if ch <= UNCHANGED else f"changed {ch:.2f}")
            rows.append(f"- step {s['n']} [{s.get('state')}] {s.get('why', '')[:100]} -> "
                        f"{' '.join(s.get('action', [])) or 'wait'}; next screen: {chs}")
        return "\n".join(rows) or "(none: this is the first look)"

    def prompt(self, jpg, extra=""):
        guide = ""
        if self.own:
            guide = ("A path recorded on an earlier run of THIS title (a guide, not a script: check the "
                     "screen)" + ("" if self.own.get("complete", True) else
                                  ", from a run that did NOT reach gameplay (it ended: "
                                  + str(self.own.get("result")) + ")") + ":\n" + path_text(self.own) + "\n\n")
        elif self.sibs:
            guide = ("Paths recorded on SIBLING titles of the same series (menus are often laid out "
                     "alike):\n" + "\n\n".join(path_text(d) for d in self.sibs[:2]) + "\n\n")
        if guide:
            guide += PLAN_RULE
        if self.goal:
            guide += f"THIS RUN'S GOAL, on the way into play (it comes before 'fastest with defaults'): {self.goal}\n\n"
        return (f"{RULES}\n\nKnowledge from other titles (hints):\n{self.hints or '(none yet)'}\n\n{guide}"
                f"Title: {self.name} (id {self.tid or '?'}), device {self.dev.label}. "
                f"{self.el() / 60:.1f} min since cold boot.\n\nLast steps:\n{self.history()}\n\n{extra}"
                "The image below is the screen NOW. The history above may be stale: judge the screen only from "
                "the image. Answer with the JSON object only, starting with \"see\".")

    # -- repeats: the same input on the same unchanged screen
    def tried_here(self, sig):
        """Inputs already sent on this screen (consecutive steps whose screen
        matched `sig` and did not change after the input)."""
        tried = []
        for s in reversed(self.steps):
            if s.get("sig") is None or sig_dist(s["sig"], sig) > SIG_MATCH:
                break
            if s.get("action") and (s.get("changed") or 0) <= UNCHANGED:
                tried.append(" ".join(s["action"]))
            elif s.get("action"):
                break
        return tried

    def seen_here(self, sig, k=12):
        """Inputs sent on screens matching `sig` in the last k steps, whether or
        not the screen changed: a 2-screen cycle (Midnight Club 3, 10-02: Yes/No
        dialog -> UP A -> garage menu -> A -> the same dialog, 8 times) changes the
        screen every step and is invisible to tried_here. An unlooked repeat (4b) is
        not counted: it is the look's own press, and a dialogue's lines all match."""
        return [" ".join(s["action"]) for s in self.steps[-k:]
                if s.get("action") and s.get("src") != "repeat" and s.get("sig") is not None
                and sig_dist(s["sig"], sig) <= SIG_MATCH]

    MENU_STATES = ("title_screen", "main_menu", "submenu", "save_load_prompt", "controller_prompt",
                   "name_entry", "profile_creation", "publisher_logo")

    def sib_replay(self, sig):
        """A SIBLING's recorded menu step whose screen matches closely (0.6x the
        own-path threshold: a sibling's menus share a frontend, not every pixel):
        (sibling index, step index, step) or None."""
        for k, d in enumerate(self.sibs[:2]):
            steps = d.get("steps", [])
            cur = self.sib_cursor.get(k, 0)
            for j in range(cur, min(cur + 6, len(steps))):
                st = steps[j]
                if st.get("sig") is not None and st.get("useful", True) and st.get("state") in self.MENU_STATES \
                        and sig_dist(st["sig"], sig) <= 0.6 * SIG_MATCH:
                    return k, j, st
        return None

    def static_run(self):
        n = 0
        for st in reversed(self.steps):
            if st.get("src") != "static":
                break
            n += 1
        return n

    def repeat_run(self):
        n = 0
        for st in reversed(self.steps):
            if st.get("src") != "repeat":
                break
            n += 1
        return n

    def replay(self, sig):
        """A recorded step of this title's own path whose screen matches, at or
        a little past the cursor: (index, step) or None."""
        if not self.own:
            return None
        steps = self.own.get("steps", [])
        for j in range(self.cursor, min(self.cursor + 4, len(steps))):
            s = steps[j]
            if s.get("sig") is not None and s.get("useful", True) and sig_dist(s["sig"], sig) <= SIG_MATCH \
                    and s.get("state") not in ("gameplay",):
                return j, s
        return None

    # -- gameplay confirmation (brief rule 5)
    def confirm(self, probe, why):
        self.probes += 1
        toks = clean_action(probe if isinstance(probe, list) else [probe]) or ["STICK:up:1.5"]
        pre, probe = toks[:-1], toks[-1]
        if self.dead_probes >= 2:
            pre = [UNLOCK_LADDER[(self.dead_probes - 2) % len(UNLOCK_LADDER)]] + pre
        if probe in BUTTONS and probe not in HAT:
            probe = f"HOLD:{probe}:1.5"
        elif probe in HAT:
            probe = {"UP": "STICK:up:1.5", "DOWN": "STICK:down:1.5", "LEFT": "STICK:left:1.5",
                     "RIGHT": "STICK:right:1.5"}[probe]
        if self.probe_tries.get(probe_key(probe), 0) >= PROBE_REFUSED_MAX:
            fresh = [p for p in PROBE_LADDER if self.probe_tries.get(probe_key(p), 0) < PROBE_REFUSED_MAX]
            if fresh:
                probe = fresh[0]
        self.probe_tries[probe_key(probe)] = self.probe_tries.get(probe_key(probe), 0) + 1
        if pre:
            # inputs that START play first (a kickoff's A, a serve): then the control pair
            self.send(pre)
            time.sleep(1.5)
        self.n += 1
        a_png, a_jpg = self.frame("probe-a")
        time.sleep(1.0)
        b_png, b_jpg = self.frame("probe-b")
        if not (a_png and b_png):
            return False, "screencap failed"
        c_png, c_jpg = self.hold_capture(probe, "probe-c")
        if not c_png:
            return False, "screencap failed"
        ctrl, moved = probe_change(a_png, b_png, c_png)
        rec = {"state": "probe", "action": pre + [probe], "why": f"control {ctrl:.3f}, under input {moved:.3f}",
               "src": "probe", "changed": moved}
        selfmove = ctrl > SELF_MOVING
        self.dead_probes = self.dead_probes + 1 if moved < PROBE_MOVED and ctrl < PROBE_MOVED else 0
        won = False
        if not selfmove and ctrl >= PROBE_MOVED and moved < 1.5 * ctrl:
            # ambiguous: the scene moves on its own (a fight's enemies, an AI camera) about as much as under the
            # input. Two more idle/input rounds; the input must beat the idle change in 2 of 3 (addendum 4 item 2;
            # Spikeout, 10-03: 8 min of refused probes in the opening fight). The model sees the clearest round.
            rounds = [(ctrl, moved, a_png, a_jpg, b_png, b_jpg, c_png, c_jpg)]
            for k in (2, 3):
                x0 = self.frame(f"probe-a{k}")
                time.sleep(1.0)
                x1 = self.frame(f"probe-b{k}")
                x2 = self.hold_capture(probe, f"probe-c{k}")
                if not (x0[0] and x1[0] and x2[0]):
                    break
                rounds.append(probe_change(x0[0], x1[0], x2[0]) + x0 + x1 + x2)
            wins = [r for r in rounds if r[1] >= PROBE_MOVED and r[1] > max(WINDOW_WIN * r[0], r[0] + 0.02)]
            rec["rounds"] = [[round(r[0], 3), round(r[1], 3)] for r in rounds]
            rec["action"] = rec["action"] + [probe] * (len(rounds) - 1)
            if len(wins) >= 2:
                ctrl, moved, a_png, a_jpg, b_png, b_jpg, c_png, c_jpg = max(wins, key=lambda r: r[1] - r[0])
                rec["why"] += f"; {len(wins)} of {len(rounds)} idle/input rounds won"
                won = True
        if moved < PROBE_MOVED or (moved < 1.5 * ctrl and not selfmove and not won):
            rec["verdict"] = "no change under the input beyond what changes on its own"
            self.write_step(rec)
            return False, (f"the screen did not change while {probe} was held beyond its own motion "
                           f"(control {ctrl:.3f}, under input {moved:.3f})")
        if letterboxed(a_png) or letterboxed(c_png):
            rec["verdict"] = "letterboxed: a cutscene"
            self.write_step(rec)
            return False, "black bars top and bottom: this is a cutscene, not gameplay"
        head = (f"Screenshots of {self.name}, an Xbox game, below in order. The 'FPS: NN' text at the top-left "
                f"is the emulator's overlay, not a game HUD. The previous step judged this gameplay: \"{why}\".\n")
        tail = ("A menu cursor moving is NOT a response. Answer JSON only: "
                '{"gameplay": true|false, "responded": true|false, "why": "<one line>"}')
        if selfmove:
            # The scene moves by itself (downhill, on rails, a cinematic): pixels cannot say who moved it, so
            # steer LEFT then RIGHT and ask whether the player followed both (Amped 2 and Panzer Dragoon, 10-02).
            # A throttle probe steers ON the throttle: steering a slow car with the gas off turned Forza into the
            # pit wall in both 10-03 runs, and it never got off it.
            trig = probe.split(":")[0].split("+")[0]
            left, right = ((f"{trig}+left:1.2", f"{trig}+right:1.2") if trig in ("RT", "LT")
                           else ("STICK:left:1.2", "STICK:right:1.2"))
            l_png, l_jpg = self.hold_capture(left, "probe-left")
            r_png, r_jpg = self.hold_capture(right, "probe-right")
            if not (l_png and r_png):
                return False, "screencap failed"
            rec["action"] = rec["action"] + [left, right]
            q = head + ("A, then B (1 s after A, no input): the scene moves on its own. Then C taken while holding "
                        "the stick LEFT, then D taken while holding it RIGHT. Is this real player-controlled "
                        "gameplay (not a menu, cutscene, attract/demo or replay), AND did the player's character, "
                        "vehicle, aim reticle or camera steer LEFT in C and RIGHT in D? Both are needed. " + tail)
            imgs = [a_jpg, b_jpg, l_jpg, r_jpg]
        else:
            q = head + (f"A, then B (1 s after A, no input), then C (taken while holding {probe}, ~1 s after B). "
                        "Is this real player-controlled gameplay (not a menu, not a cutscene, not an attract/demo "
                        f"mode, not a replay), AND does C show the playfield responding to the input {probe} (the "
                        "player/vehicle/camera moved accordingly), beyond whatever changed on its own between A "
                        "and B? " + tail)
            imgs = [a_jpg, b_jpg, c_jpg]
        ans = self.model.ask(STRONG, q, "confirm", imgs) or {}
        ok = bool(ans.get("gameplay")) and bool(ans.get("responded"))
        rec["verdict"] = ("CONFIRMED: " if ok else "refused: ") + str(ans.get("why", "no answer"))[:200]
        self.write_step(rec)
        self.result["probe_frames"] = imgs
        return ok, rec["verdict"]

    def hold_capture(self, tok, tag):
        """Hold one input token, take a frame ~0.8 s into the hold, release."""
        parts = tok.split(":")
        held = []
        if parts[0] == "STICK":
            for ax, v in STICK[parts[1]]:
                self.dev.pad("axis", ax, v)
                held.append((ax, "mid"))
        elif parts[0] in ("RT", "LT"):
            self.dev.pad("axis", parts[0], "max")
            held.append((parts[0], "min"))
        elif "+" in parts[0]:
            trig, d = parts[0].split("+")
            self.dev.pad("axis", trig, "max")
            held.append((trig, "min"))
            for ax, v in STICK[d]:
                self.dev.pad("axis", ax, v)
                held.append((ax, "mid"))
        elif parts[0] == "HOLD" or parts[0] in BUTTONS:
            btn = parts[1] if parts[0] == "HOLD" else parts[0]
            self.dev.pad("hold", btn)
            held.append(("release", btn))
        time.sleep(0.8)
        png, jpg = self.frame(tag)
        time.sleep(0.4)
        for ax, v in held:
            if ax == "release":
                self.dev.pad("release", v)
            else:
                self.dev.pad("axis", ax, v)
        return png, jpg

    # -- the loop
    def thermal_ok(self, start=False):
        if self.dev.label != "thor":
            return True
        c = self.dev.xo_c()
        self.thermal.append((round(self.el(), 1), c))
        if c is None:
            return True
        return c <= (THOR_START_C if start else THOR_STOP_C)

    def run(self):
        if not self.thermal_ok(start=True):
            self.result.update(result="refused", reason=f"Thor xo {self.thermal[-1][1]} C > {THOR_START_C} C")
            return self.finish()
        self.dev.launch(self.iso)
        self.launched_at = now()
        self.watch = hangwatch.start(self.dev, self.out)
        relaunches = 0
        last_png = None
        last_therm = now()
        while self.el() < self.budget_s:
            if now() - last_therm > 30:
                last_therm = now()
                if not self.thermal_ok():
                    self.result.update(result="heat-stop", reason=f"Thor xo {self.thermal[-1][1]} C")
                    return self.finish()
            self.n += 1
            png, jpg = self.frame("look")
            if not png:
                time.sleep(2)
                continue
            ch = None
            if self.steps and last_png:
                ch = self.steps[-1]["changed"] = round(changed(last_png, png), 4)
            hang = hangwatch.look(self.watch, self.dev, self.out, ch, changed, (self.tid, self.name))
            if hang:
                self.result.update(result="hang", reason=hang["reason"])
                return self.finish(last=jpg)
            sig = signature(png)
            if not self.dev.foreground():
                alive = self.dev.alive()
                self.write_step({"state": "unknown", "why": f"hakuX not in front (xemu alive: {alive})",
                                 "action": [], "src": "check", "sig": sig.tolist()})
                if relaunches >= 1:
                    self.result.update(result="lost", reason="hakuX left the foreground twice")
                    return self.finish(last=jpg)
                relaunches += 1
                self.dev.launch(self.iso)
                last_png = None
                time.sleep(5)
                continue
            dec = self.decide(png, jpg, sig)
            if self.black_since and now() - self.black_since > BLACK_HANG_S:
                alive = self.dev.alive()
                self.write_step(dict(dec or {}, state="black", src="check", action=[],
                                     why=f"black for {now() - self.black_since:.0f} s (xemu alive: {alive})"))
                self.result.update(result="black-hang", reason=f"black for over {BLACK_HANG_S} s, xemu alive: {alive}")
                prev = [st for st in self.steps if st.get("state") != "black" and st.get("frame")]
                return self.finish(last=os.path.join(self.out, prev[-1]["frame"]) if prev else jpg)
            if dec is None:
                last_png = png
                continue
            os.replace(jpg, jpg.replace("-look.jpg", f"-{dec['state']}.jpg"))
            jpg = jpg.replace("-look.jpg", f"-{dec['state']}.jpg")
            dec["frame"] = os.path.relpath(jpg, self.out)
            if dec["state"] == "gameplay" and dec.get("src") != "black":
                self.write_step(dec)
                probe = dec.get("probe") or ["STICK:up:1.5"]
                probe = (probe if isinstance(probe, list) else [probe])
                # the model's own action first (ESPN NFL 2K5, 10-02: "gameplay" on the kickoff play-call
                # screen with action A; the stick alone only flipped the play menu)
                ok, why = self.confirm(list(dec.get("action") or []) + probe, dec.get("why", ""))
                if ok:
                    r = self.success(jpg)
                    if r is not None:
                        return r
                    why = "retracted: 30 s later it was no longer gameplay"
                if self.probes >= 4:
                    self.result.update(reason="four probes refused")
                self.steps[-1]["why"] += f" | probe: {why}"
                last_png = None
                continue
            if dec["state"] == "fatal_error" and self.steps and self.steps[-1].get("state") == "fatal_error":
                # twice in a row: the title cannot go on (ESPN NBA 2K5 on the Thor, 10-02: "disc is dirty or
                # damaged" after team select; four more inputs changed nothing)
                self.write_step(dec)
                self.result.update(result="title-error", reason=dec.get("why", "")[:200])
                return self.finish(last=jpg)
            self.write_step(dec)
            self.send(dec["action"])
            time.sleep(min(max(float(dec.get("wait_s") or 2), 0.5), 12))
            last_png = png
        self.result.update(result="gave-up", reason=f"budget {self.budget_s / 60:.0f} min",
                           last_state=self.steps[-1].get("state") if self.steps else None)
        return self.finish(last=jpg if self.steps else None)

    def decide(self, png, jpg, sig):
        """One step's decision: a cheap check, a replay, or a model call."""
        base = {"sig": sig.tolist()}
        # 1. black frame: wait, no model, until it has been black a while
        if is_black(png):
            self.black_since = self.black_since or now()
            if now() - self.black_since < BLACK_MODEL_S:
                return dict(base, state="black", why="black frame", action=[], wait_s=3, src="black")
            black_s = now() - self.black_since
            act = [SKIP_LADDER[int(black_s // 10) % 2]]
            return dict(base, state="black", why=f"black for {black_s:.0f} s", action=act, wait_s=4, src="black")
        self.black_since = None
        prev = self.steps[-1] if self.steps else None
        # 2. a load that has barely changed since the last look: wait again, no call. 0.05, not
        # UNCHANGED: a progress bar creeps (ESPN NHL 2K5 on the Thor, 10-02: six model calls, ~80 s of heat,
        # on one Team Match Up loading screen). At most 5 in a row, then the model looks again.
        if prev and not prev.get("action") and prev.get("state") in ("loading",) \
                and prev.get("changed") is not None and prev["changed"] <= 0.05 \
                and self.static_run() < 5:
            return dict(base, state="loading", why="load still on screen (barely changed)", action=[],
                        wait_s=4, src="static")
        # 3. a recorded step of this title's own path matches the screen
        tried = self.tried_here(sig)
        seen = self.seen_here(sig)
        rp = self.replay(sig) if not (tried or seen) else None
        if rp:
            j, s = rp
            self.cursor = j + 1
            return dict(base, state=s["state"], why=f"replay step {j}: {s['why']}", action=list(s["action"]),
                        wait_s=s.get("wait_s", 2), src="replay")
        sp = self.sib_replay(sig) if not (tried or seen or self.own) else None
        if sp:
            k, j, s = sp
            self.sib_cursor[k] = j + 1
            return dict(base, state=s["state"], why=f"sibling {self.sibs[k].get('title_id')} step {j}: {s['why']}",
                        action=list(s["action"]), wait_s=s.get("wait_s", 2), src="sibreplay")
        # 4. the model's plan from a guide: the next planned input, while every input so far has visibly changed
        # the screen. Sibling screens are 10-23 grey levels apart (ESPN 2K5 menus, 10-02), so a frame match
        # cannot carry a sibling's path; the model reading the guide can.
        if self.plan:
            last = next((st for st in reversed(self.steps) if st.get("action")), None)
            if tried or seen or not last or last.get("changed") is None or last["changed"] <= UNCHANGED:
                self.plan = []
            else:
                nxt = self.plan.pop(0)
                return dict(base, state=nxt["expect"], why=f"plan: {nxt['expect']} (from the guide)",
                            action=nxt["action"], wait_s=nxt["wait_s"], src="plan")
        # 4b. a cutscene or dialogue the model answered with ONE button, and that press changed the screen: the same
        # press again, unlooked, up to CLAIM_REPEAT times in a row, then the model looks. Phantom Crash, 10-04: 62 of
        # 92 calls ($6.7 of the claim) were one look per line of a ClubWired dialogue that A advanced every time.
        # Only on the SAME screen (its signature still matches: the box stayed, its text moved on). A press that
        # led somewhere new (a logo's START to a menu) gets a look: a repeat there would choose a menu item.
        # A letterboxed frame after a letterboxed cutscene step is a cutscene by the local check alone (owner 10-04:
        # Tork's claim spent 10 looks on START+A over a run of staged close-ups, ~9 s each, Tron 48 looks): the
        # press that advanced it goes again unlooked, one or two buttons, up to CLAIM_REPEAT_BOX times.
        boxed = bool(prev and prev.get("state") == "cutscene" and letterboxed(png))
        if prev and prev.get("state") in CLAIM_REPEAT_STATES and 1 <= len(prev.get("action") or []) <= (2 if boxed else 1) \
                and prev.get("src") in ("fast", "strong", "repeat") and (prev.get("changed") or 0) > UNCHANGED \
                and prev.get("sig") is not None and (boxed or sig_dist(prev["sig"], sig) <= SIG_MATCH) \
                and not tried and self.repeat_run() < (CLAIM_REPEAT_BOX if boxed else CLAIM_REPEAT):
            return dict(base, state=prev["state"], why=f"repeat {prev['action'][0]}: it advanced the {prev['state']}",
                        action=list(prev["action"]), wait_s=prev.get("wait_s", 2), src="repeat")
        # 5. the model; the stronger one when stuck or unsure
        cycle =max((seen.count(a) for a in seen), default=0) >= 2
        stuck = len(tried) >= 2 or cycle
        extra = ""
        if tried:
            extra = (f"On THIS unchanged screen these inputs did nothing: {tried}. Choose a different input.\n\n")
        elif cycle:
            extra = (f"You have been on this same screen before in the last 12 steps and sent: {seen}; it came "
                     "back here, so that did not work. Do something different: a different option or direction, "
                     "check which item is really highlighted, or back out and take another menu path.\n\n")
        model = STRONG if stuck else FAST
        ans = self.model.ask(model, self.prompt(jpg, extra), "step", [jpg])
        if ans and ans.get("state") == "unknown" and model == FAST:
            model = STRONG
            ans = self.model.ask(model, self.prompt(jpg, extra), "step-escalate", [jpg])
        if not ans:
            return dict(base, state="unknown", why="model gave no answer", action=[], wait_s=2, src="none")
        state = ans.get("state") if ans.get("state") in STATES else "unknown"
        action = clean_action(ans.get("action"))
        # an intro, logo or cutscene is never waited out while a skip button is untried here (owner 10-04: Dino Crisis
        # 3 waited 9 looks on a video its hint says START skips; Halo 2 and DOA3 "did not mash"). A press at a
        # video nothing skips costs nothing; the wait comes back once START, A and B have each had a go.
        if not action and state in INTRO_STATES:
            fresh = [b for b in ("START", "A", "B") if b not in tried]
            if fresh:
                action = [fresh[0]]
                ans["why"] = str(ans.get("why", "")) + f" [override: {state} is skipped, not waited out -> {action[0]}]"
        # never the same input a 4th time on the same unchanged screen
        if action and (tried.count(" ".join(action)) >= 3 or seen.count(" ".join(action)) >= 4):
            fresh = [b for b in SKIP_LADDER if b not in tried]
            action = [fresh[0]] if fresh else ["START"]
            ans["why"] = str(ans.get("why", "")) + f" [override: repeated input on unchanged screen -> {action[0]}]"
        try:
            wait_s = float(ans.get("wait_s") or 2)
        except (TypeError, ValueError):
            wait_s = 2.0
        self.plan = []
        for st in (ans.get("plan") or [])[:5] if isinstance(ans.get("plan"), list) else []:
            if not isinstance(st, dict) or st.get("expect") not in Agent.MENU_STATES + ("loading", "black"):
                break                # a plan only crosses menus and loads; play is the model's call
            act = clean_action(st.get("action"))
            try:
                w = min(max(float(st.get("wait_s") or 2), 0.5), 10)
            except (TypeError, ValueError):
                w = 2.0
            self.plan.append({"expect": st["expect"], "action": act, "wait_s": w})
        base["see"] = str(ans.get("see", ""))[:240]
        return dict(base, state=state, why=str(ans.get("why", ""))[:240], action=action, wait_s=wait_s,
                    probe=ans.get("probe") or "", src=("fast" if model == FAST else "strong"))

    def success(self, jpg):
        mins = self.el() / 60
        self.result.update(result="gameplay", minutes=round(mins, 2), gameplay_frame=jpg)
        # 30 s more frames (20 s on the Thor: stop within 30 s of the claim)
        span = 20 if self.dev.label == "thor" else 30
        span = float(os.environ.get("PATHFIND_AFTER_S", span))
        t_end = now() + span
        post = []
        while now() < t_end:
            self.n += 1
            png, j = self.frame("after")
            if j:
                post.append(j)
            time.sleep(3)
        self.result["after_frames"] = post
        # still gameplay 30 s on? A cinematic ends in a title screen; play does not (Bruce Lee, 10-02)
        last = post[-1] if post else None
        if last:
            lb = letterboxed(last[:-4] + ".png") if os.path.exists(last[:-4] + ".png") else False
            ans = self.model.ask(STRONG, (
                f"A screenshot of {self.name}, an Xbox game, taken {span:.0f} s after the agent judged it to be in "
                "gameplay (no input since). The 'FPS: NN' text at the top-left is the emulator's overlay, not "
                "the game's HUD. Is this still in-game play (the player's character/vehicle in the game world, "
                "possibly idle or paused) rather than a title screen, menu, logo, loading screen, cutscene or "
                'attract demo? Answer JSON only: {"gameplay": true|false, "why": "<one line>"}'), "recheck", [last]) or {}
            if lb or not ans.get("gameplay"):
                why = "letterboxed" if lb else str(ans.get("why", "no answer"))
                self.write_step({"state": "retracted", "action": [], "src": "probe",
                                 "why": f"retracted after {span:.0f} s: {why}"[:240]})
                self.result.update(result="running", minutes=None, gameplay_frame=None,
                                   retracted=self.result.get("retracted", 0) + 1)
                return None
        self.write_path()
        if self.record:
            self.result["learned"] = [os.path.relpath(f, KNOW) for f in
                                      learn(self.tid, self.name, self.dev.label, self.steps, mins)]
        if self.hold_s:
            return self.hold_play(jpg)
        return self.finish(last=jpg, post=post)

    # -- hold-play: keep the player in play, then judge the frames
    def hold_look(self, jpg, genre):
        """The model reads the screen: is the player in live play, and if not, what gets back to it?"""
        return self.model.ask(FAST, (
            f"Screenshot of {self.name}, an Xbox game. The 'FPS: NN' text at the top-left is the emulator's "
            f"overlay, not the game's HUD. An agent is keeping the player playing (genre: {genre}). Read the "
            "screen. Is the player in live play right now (the player's character, vehicle or ball in the game "
            "world, the game running)? A menu cursor, a pause screen, a cutscene, a loading screen, a results or "
            "game-over screen, or a black screen is NOT play. If it is not play, which input gets back to it? "
            'Answer JSON only: {"state": "gameplay|pause|game_over|results|menu|cutscene|loading|black|other", '
            '"in_play": true|false, "why": "<one line>", "action": [inputs, e.g. "START", "A", '
            '"STICK:down:0.5"], "wait_s": <number>}'), "hold-check", [jpg]) or {}

    def hold_genre(self, jpg):
        """One model look, once per hold: which genre loop fits this play."""
        ans = self.model.ask(FAST, (
            f"Screenshot of {self.name}, an Xbox game, in gameplay. The 'FPS: NN' text at the top-left is the "
            "emulator's overlay, not the game's HUD. What kind of play is this? Answer JSON only: "
            '{"genre": "drive|attack|shooter|rally|team|onrails|other", "why": "<one line>"}. drive: a car, bike, '
            "boat or plane moving through a world; attack: a character fighting in melee or with magic; shooter: "
            "a gun game, first or third person, walking through a level and firing a weapon; rally: a ball or "
            "shuttle played back and forth over a net (tennis, volleyball); team: a team sport on a court, "
            "field or rink (basketball, football, hockey, soccer); onrails: the scene moves on its own and the "
            "player only aims; other: anything else."), "genre", [jpg]) or {}
        return ans.get("genre") if ans.get("genre") in HOLD_GENRES else "other", str(ans.get("why", ""))[:160]

    def hold_play(self, jpg):
        """Keep play going for self.hold_s seconds of play, judged from the frames.

        A model-free genre loop of inputs runs while the screen is play. The model reads the screen only
        when play may have ended (black, or static on two looks in a row), every HOLD_CHECK_S, and once to
        name the genre. Off play, the model's own inputs steer back, one model look per step, until it reads
        play again. A frame is kept every HOLD_FRAME_S; the rest are deleted."""
        th = TITLE_HOLD.get((self.tid or "").upper())
        if th:
            genre, genre_why = "attack", "title hold (TITLE_HOLD): left-stick walk"
        else:
            genre, genre_why = self.hold_genre(jpg)
        tokens = th["walk"] if th else HOLD_GENRES[genre]
        log = os.path.join(self.out, "hold.jsonl")
        held = {"genre": genre, "why": genre_why}
        print(f"hold-play: genre {genre}, need {self.hold_s:.0f} s of play", flush=True)
        kept, play_s, navs, nav = [], 0.0, 0, 0
        still, off, reason = 0, False, ""
        # position test (10-03): a 30-s window whose kept frames barely differ is not play, however live the HUD
        # looks (Black Stone stood 600 s on one octagon and passed the verdict). Then rotate the inputs: an unlock
        # button and the next genre's loop, until the scene moves again.
        parked, rot, still_windows = False, 0, 0
        th_x = bool(th) and th.get("x", True)  # a title hold presses X alone first, unless the title says otherwise
        press_x, still_row, cont_left = th_x, 0, 2   # and again after a menu or two still windows; continue: 2 returns
        shed_set = set()                 # loop buttons that opened a menu (HOLD_SHED): never sent again this hold
        order = [genre] + [g for g in HOLD_GENRES if g not in (genre, "onrails")]
        rep, rep_left = None, 0          # the last off-play look's single press, and how many repeats it has left
        cont_tries = 0                   # CONTINUE presses in this off-play episode (CONTINUE_PRESS, CONTINUE_TRIES)
        last_png, last_check, last_kept, drop = None, now(), None, []
        fps_seen, fps_checks = set(), []  # the FPS_GATES passed so far, and what each read
        # the perflog: logcat from the mark to `soak end`, with a state line at every change of play, so
        # title_verdict.py judges fps over play seconds only (its TIMELINE)
        cat = self.dev.logcat_start(os.path.join(self.out, "logcat.txt"))
        time.sleep(1)
        for m in ("mark gameplay", "soak start", "state=play t=0"):
            self.dev.route_log(m)
        logged = "play"
        t_hold = now()
        # claim and hold get separate clocks (addendum 4, 10-03): the claim used the budget, the hold is owed its
        # seconds of play. A claim at 13 min used to leave the 600-s hold 2 min of budget (Black Stone, 10-03).
        self.budget_s = max(self.budget_s, self.el() + self.hold_s * 1.5 + 300)
        while play_s < self.hold_s and self.el() < self.budget_s:
            self.n += 1
            t_cycle = now()
            png, jp = self.frame("hold")
            if not png:
                time.sleep(2)
                continue
            if not self.dev.foreground():
                reason = "hakuX left the foreground during the hold"
                break
            t = now()
            hold_el = t - t_hold
            gate = next((g for g in FPS_GATES if g[0] <= hold_el and g[0] not in fps_seen), None)
            if gate and self.hold_s > FPS_GATES[-1][0] and cat is not None:
                fps_seen.add(gate[0])
                course = fps_course(os.path.join(self.out, "logcat.txt"))
                course.update(at_s=round(hold_el, 1), floor=gate[1], stop=fps_gate_fails(course, gate[1]))
                fps_checks.append(course)
                print(f"hold-play: fps at {hold_el:.0f} s: median {course['median']}, share>={FPS_BAR} "
                      f"{course['share']} over {course['n']} samples{' -> STOP (not on course)' if course['stop'] else ''}",
                      flush=True)
                if course["stop"]:
                    reason = (f"fps gate at {int(hold_el) // 60}:{int(hold_el) % 60:02d}: median {course['median']:.0f} "
                              f"< {gate[1]:.0f}, {course['share']:.0%} of {course['n']} samples at >= {FPS_BAR * FPS_TOL:g}")
                    break
            ch = changed(last_png, png) if last_png else None
            still = still + 1 if ch is not None and ch <= UNCHANGED else 0
            hang = hangwatch.look(self.watch, self.dev, self.out, ch, changed, (self.tid, self.name))
            if hang:
                if cat is not None:
                    cat.terminate()
                self.result.update(result="hang", reason=hang["reason"])
                return self.finish(last=jp)
            suspect = is_black(png) or still >= 1
            look = {"n": self.n, "hold_s": round(hold_el, 1), "play_s": round(play_s, 1),
                    "changed": None if ch is None else round(ch, 4), "off": off}
            if rep_left and off:
                # model-free recovery (Panzer, 10-03: each death cost 4 model looks at ~9 s, one per A of an episode
                # card): repeat the last look's single press, unlooked, then look again
                rep_left -= 1
                look.update(src="repeat", state=rep[2], action=rep[0])
                self.send(rep[0])
                time.sleep(rep[1])
            elif off or suspect or t - last_check >= HOLD_CHECK_S:
                last_check = t
                a = self.hold_look(jp, genre)
                was_play = not off
                off = a.get("in_play") is not True
                st = ("still" if parked else "play") if not off else \
                    re.sub(r"[^a-z_]", "", str(a.get("state") or "other").lower()) or "other"
                if off and was_play and st in HOLD_SHED_STATES:
                    shed = next((b for b in HOLD_SHED if b in tokens and b not in shed_set), None)
                    if shed:
                        shed_set.add(shed)
                        look["shed"] = shed
                if st != logged:
                    self.dev.route_log(f"state={st} t={int(hold_el)}")
                    logged = st
                look.update(src="check", state=a.get("state"), why=str(a.get("why", ""))[:160])
                if off:
                    nav += 1
                    navs += 1
                    if nav > HOLD_NAV_MAX:
                        reason = f"off play for {nav} steps: {a.get('state')} ({a.get('why', '')})"[:240]
                        self.hold_note(log, dict(look, action=[]))
                        break
                    action = clean_action(a.get("action"))
                    try:
                        wait_s = min(max(float(a.get("wait_s") or 2), 0.5), 8)
                    except (TypeError, ValueError):
                        wait_s = 2.0
                    if st == "continue" and not th and cont_tries < CONTINUE_TRIES:
                        # a CONTINUE countdown (fighting games): START, then A, unlooked; the look after each says which took
                        action, wait_s = [CONTINUE_PRESS[cont_tries % len(CONTINUE_PRESS)]], 1.5
                        cont_tries += 1
                        look["continue"] = cont_tries
                    elif th:
                        # title hold: a menu is closed with one B and X follows; anything else keeps the model's press
                        # minus the forbidden buttons (a cutscene's A)
                        if st == "title_screen" and th.get("continue") and cont_left:
                            # a game over returned to the title: one unlooked CONTINUE, not the NEW GAME walk
                            cont_left -= 1
                            action, wait_s = list(th["continue"]), 4.0
                            look["continue"] = True
                        elif st in HOLD_SHED_STATES:
                            action, wait_s, press_x = ["B"], 1.5, th_x
                        else:
                            action = [t for t in action if t.upper() not in TITLE_HOLD_FORBID] or ["A"]
                    look["action"] = action
                    self.send(action)
                    time.sleep(wait_s)
                    single = len(action) == 1 and st in HOLD_REPEAT_STATES
                    rep, rep_left = (action, wait_s, st), (HOLD_REPEAT if single else 0)
                else:
                    nav = 0
                    rep_left = 0
                    cont_tries = 0
            if not off and look.get("action") is None:
                # play: the genre loop (a check look that said play sends it too). The time credited is this
                # cycle's own, from its frame to its inputs: the look before may have been off play.
                loop = [t for t in tokens if t not in shed_set]
                if th and press_x:
                    loop, press_x = ["X"], False
                look.update(src=look.get("src", "genre"), action=loop)
                self.send(loop)
                if not parked:
                    play_s += now() - t_cycle
            keep = last_kept is None or hold_el - last_kept >= HOLD_FRAME_S
            if keep:
                if kept and not off:
                    mv = window_change(kept[-1], jp)
                    look["window"] = round(mv, 4)
                    if mv < HOLD_STILL:
                        still_windows += 1
                        if th:
                            # two still windows in a row (60 s): X once, then a different move for the next 30 s
                            # (10-05, Tork: 500 s on one stair with the same walk; the stair needs a hop). Each
                            # still stretch gets the next move in the list; a moving window puts the walk back.
                            still_row += 1
                            if still_row >= 2:
                                press_x, still_row = th_x, 0
                                rot += 1
                                moves = th.get("unstick", []) + TITLE_UNSTICK
                                move = moves[(rot - 1) % len(moves)]
                                tokens = move + th["walk"]
                                look["unstick"] = " ".join(move)
                        else:
                            rot += 1
                            unstick = HOLD_UNSTICK.get(genre)
                            if unstick and rot <= 2 * len(unstick):
                                tokens = unstick[(rot - 1) % len(unstick)] + HOLD_GENRES[genre]
                            else:
                                tokens = [UNLOCK_LADDER[(rot - 1) % len(UNLOCK_LADDER)]] + \
                                    HOLD_GENRES[order[rot % len(order)]]
                        parked = True
                    else:
                        still_row, parked = 0, False
                        if th:
                            tokens = th["walk"]
                    want = "still" if parked else "play"
                    if logged in ("play", "still") and want != logged:
                        self.dev.route_log(f"state={want} t={int(hold_el)}")
                        logged = want
                last_kept = hold_el
                kept.append(jp)
                route_frame(self.out, png)
            # the previous look's frame is spent now: this look has been measured against it
            for p in drop:
                os.remove(p)
            drop = [] if keep else [png, jp]
            look.update(play_s=round(play_s, 1), kept=keep)
            self.hold_note(log, look)
            last_png = png
        for p in drop:
            os.remove(p)
        ok = play_s >= self.hold_s
        if not ok and not reason:
            reason = f"budget {self.budget_s / 60:.0f} min with {play_s:.0f} s of play"
        held.update(ok=ok, play_s=round(play_s, 1), need_s=self.hold_s, hold_s=round(now() - t_hold, 1),
                    model_navs=navs, frames=len(kept), still_windows=still_windows, shed=sorted(shed_set),
                    reason=reason, title_hold=bool(th), fps_checks=fps_checks)
        self.result["hold"] = held
        print(f"hold-play: {'HELD' if ok else 'not held'} {play_s:.0f}/{self.hold_s:.0f} s of play; {reason}",
              flush=True)
        strip(kept, os.path.join(self.out, "hold_strip.jpg"), cols=5, width=256)
        self.dev.route_log("soak end")
        if cat is not None:
            time.sleep(2)
            cat.terminate()
            held["verdict"] = self.hold_verdict(now() - t_hold)
        return self.finish(last=kept[-1] if kept else jpg, post=kept)

    def hold_verdict(self, secs):
        """title_verdict.py on the hold's logcat: its one VERDICT line (verdict.json beside it)."""
        # title_verdict resolves the title by the ISO's basename (targets.toml `iso` map), not by the display name
        with open(os.path.join(self.out, "request.json"), "w") as f:
            json.dump({"title": self.name, "title_id": self.tid, "device": self.dev.label,
                       "iso": os.path.basename(self.iso or "")}, f)
        # title_verdict reads `held <title> for <n>s` from run.log; append it there (stdout is not run.log)
        with open(os.path.join(self.out, "run.log"), "a") as f:
            f.write(f"held {self.name} for {int(secs)}s\n")
        print(f"held {self.name} for {int(secs)}s", flush=True)
        try:
            r = subprocess.run([sys.executable, VERDICT, self.out, "--require", "confirmation"],
                               capture_output=True, text=True, timeout=120)
            line = (r.stdout.strip().splitlines() or [r.stderr.strip()[-200:]])[-1]
        except (subprocess.TimeoutExpired, OSError) as e:
            line = f"title_verdict failed: {e}"
        print(line, flush=True)
        return line

    def hold_note(self, log, look):
        with open(log, "a") as f:
            f.write(json.dumps(look) + "\n")

    def write_path(self, complete=True):
        """pathknow/paths/<TITLEID>.json. A run that did not reach gameplay
        writes its steps too (complete: false), cut before the first screen it
        had already visited, so a loop is never recorded; it never replaces a
        complete path. On the Thor a retry's replayed menus are minutes of heat
        saved (ESPN NFL 2K5, 10-02: 52 -> 70 C in 3.6 min of menus)."""
        if not self.record or not self.tid:
            return
        dest = os.path.join(KNOW, "paths", f"{self.tid.upper()}.json")
        if not complete:
            try:
                if json.load(open(dest)).get("complete", True):
                    return
            except (OSError, ValueError):
                pass
        keep = []
        seen = []
        for s in self.steps:
            if s.get("src") in ("probe", "check"):
                continue
            if not complete and s.get("sig") is not None:
                if any(sig_dist(s["sig"], o) <= SIG_MATCH for o in seen) and s.get("state") not in (
                        "black", "loading"):
                    break
                seen.append(s["sig"])
            useful = bool(s.get("action")) and (s.get("changed") or 0) > UNCHANGED
            keep.append({"state": s.get("state"), "why": s.get("why", "")[:160], "action": s.get("action", []),
                         "wait_s": s.get("wait_s", 2), "useful": useful or s.get("state") == "gameplay",
                         "sig": [[round(v) for v in row] for row in s["sig"]] if s.get("sig") else None})
        d = {"title_id": self.tid, "name": self.name, "device": self.dev.label,
             "recorded": time.strftime("%Y-%m-%d %H:%M %Z"), "minutes": self.result.get("minutes"),
             "model_calls": self.model.calls, "complete": complete, "result": self.result.get("result"),
             "steps": keep}
        os.makedirs(os.path.join(KNOW, "paths"), exist_ok=True)
        with open(dest, "w") as f:
            json.dump(d, f, indent=0)
            f.write("\n")

    def finish(self, last=None, post=()):
        hangwatch.close(self.watch)
        self.dev.stop(screen_off=not os.environ.get("PATHFIND_LEAVE_ON"))
        if self.result.get("result") != "gameplay" and self.steps:
            self.write_path(complete=False)
        self.result.update(model_calls=self.model.calls, calls_by_model=self.model.by_model,
                           steps=len(self.steps), seconds=round(self.el(), 1), last_frame=last,
                           last_state=self.steps[-1].get("state") if self.steps else None,
                           replayed=sum(1 for s in self.steps if s.get("src") == "replay"),
                           sib_replayed=sum(1 for s in self.steps if s.get("src") == "sibreplay"),
                           guide=[d.get("title_id") for d in ([self.own] if self.own else self.sibs[:2])],
                           cheap=sum(1 for s in self.steps if s.get("src") in ("black", "static")),
                           thermal=self.thermal)
        looks = sorted(glob.glob(os.path.join(self.frames, "*.jpg")))
        pre = [p for p in looks if "-after" not in p and "probe" not in p]
        sheet = pre[-8:] + list(self.result.get("probe_frames", [])) + list(post)[:8]
        self.result["strip"] = strip(sheet, os.path.join(self.out, "strip.jpg"))
        for p in glob.glob(os.path.join(self.frames, "*.png")):
            os.remove(p)     # the 640-px JPEGs are the record; full PNGs are 2-4 MB each
        with open(os.path.join(self.out, "result.json"), "w") as f:
            json.dump(self.result, f, indent=1)
        print(json.dumps({k: self.result.get(k) for k in ("name", "device", "result", "minutes", "model_calls",
                                                          "steps", "replayed", "reason", "gameplay_frame")}))
        return 0 if self.result["result"] == "gameplay" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("title")
    ap.add_argument("--device", default="nova", choices=sorted(DEVICES))
    ap.add_argument("--budget-min", type=float, default=15)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-record", action="store_true", help="do not write pathknow/paths/<id>.json")
    ap.add_argument("--no-replay", action="store_true", help="ignore this title's own recorded path")
    ap.add_argument("--no-guide", action="store_true",
                    help="use no recorded path at all, own or sibling (a cross-title baseline)")
    ap.add_argument("--hold-s", type=float, default=0,
                    help="after the claim, hold play for this many seconds of play (Nova only: the Thor's fan is dead)")
    ap.add_argument("--state", default="any", choices=("returning", "first-run", "any"),
                    help="the titles disk to boot (titlestate.py compose): the title's golden profile "
                         "(returning), none (first-run), or its golden if it has one (any)")
    ap.add_argument("--hdd-img", action="store_true",
                    help="boot whatever hdd.img holds (hand play); the path found then assumes it")
    ap.add_argument("--goal", default="",
                    help="a settings goal on the way into play, given to the model each step "
                         "(e.g. the longest quarter length, so one quarter covers the hold)")
    ap.add_argument("--sim", help="PATHFIND_DRY: frames dir to play back")
    ap.add_argument("--sim-answers", help="PATHFIND_DRY: JSON list of canned model answers")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    a.out = os.path.abspath(a.out)
    if dry():
        dev = SimDevice(a.device, a.sim)
        model = Model(a.out, sim=json.load(open(a.sim_answers)) if a.sim_answers else [])
    else:
        dev = Device(a.device)
        model = Model(a.out)
    tid, name, iso = resolve(dev, a.title)
    why = blocked(tid, name)
    if why:
        sys.exit(f"pathfind: {name} is owner-blocked: {why}")
    if a.hold_s and dev.label == "thor":
        sys.exit("pathfind: --hold-s is Nova only: the Thor's fan is dead and it stops within 30 s of a claim")
    print(f"pathfind: {name} ({tid}) on {dev.label}: {iso}", flush=True)
    agent = Agent(dev, model, tid, name, iso, a.out, a.budget_min * 60, record=not a.no_record)
    agent.hold_s = a.hold_s
    agent.goal = a.goal
    if a.no_replay or a.no_guide:
        agent.own = None
    if a.no_guide:
        agent.sibs = []
    # The titles disk a dispatched run of the path would boot (lane.savestate433):
    # the path found is only replayable from the state it was found in.
    hdd = None
    if not dry() and not a.hdd_img:
        import titlestate
        hdd = titlestate.prepare(dev.label, tid, a.state, log=lambda m: print(m, flush=True))
        json.dump(hdd, open(os.path.join(a.out, "hdd.json"), "w"), indent=1)
    try:
        return agent.run()
    finally:
        if hdd:
            titlestate.release(dev.label, hdd.get("run"), log=lambda m: print(m, flush=True))


if __name__ == "__main__":
    sys.exit(main())
