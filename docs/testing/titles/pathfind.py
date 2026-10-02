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
# Sonnet 5 per step, not Haiku: measured 10-02 on the same ESPN frame with the image inline, Sonnet 5
# answered in 3.5-3.9 s (70-80 output tokens), Haiku 4.5 in 6.4-9.1 s (430-500, most of it thinking),
# and Haiku had looped 8 times on a Yes/No dialog in Midnight Club 3. Opus 5.5 when stuck.
FAST = os.environ.get("PATHFIND_FAST", "claude-sonnet-5")
STRONG = os.environ.get("PATHFIND_STRONG", "claude-opus-5-5")
STATES = ("intro_video", "publisher_logo", "title_screen", "main_menu", "submenu", "profile_creation",
          "name_entry", "save_load_prompt", "controller_prompt", "loading", "cutscene", "pause",
          "gameplay", "results", "game_over", "black", "unknown")
BUTTONS = ("A", "B", "X", "Y", "START", "BACK", "UP", "DOWN", "LEFT", "RIGHT", "L1", "R1", "L3", "R3")
STICK = {"up": (("LY", "min"),), "down": (("LY", "max"),), "left": (("LX", "min"),),
         "right": (("LX", "max"),), "upleft": (("LY", "min"), ("LX", "min")),
         "upright": (("LY", "min"), ("LX", "max"))}
# The d-pad BUTTONS (544-547) do nothing in hakuX: the pad's d-pad is the hat, and a back-to-back
# `axis HATY max` / `axis HATY mid` moves a menu ONE row (routes/midnight-club-3.returning.route).
HAT = {"UP": ("HATY", "min"), "DOWN": ("HATY", "max"), "LEFT": ("HATX", "min"), "RIGHT": ("HATX", "max")}
SKIP_LADDER = ("START", "A", "B", "BACK", "X", "Y", "DOWN", "UP", "RIGHT", "LEFT")
SIG = (16, 12)                       # a frame's signature: grey, box-averaged
SIG_MATCH = 9.0                      # mean grey-level distance under which two screens are the same
UNCHANGED = 0.01                     # classify.motion changed fraction at or under this: no change
PROBE_MOVED = 0.03                   # the probe frame must change at least this much
BLACK_MODEL_S = 40                   # seconds of black before the model is asked anyway
THOR_START_C, THOR_STOP_C = 55.0, 70.0


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
    seen, out = set(), []
    for f in files:
        if os.path.exists(f) and os.path.realpath(f) not in seen:
            seen.add(os.path.realpath(f))
            out.append(f)
    return out


def knowledge(tid, name, limit=6000):
    parts = []
    for f in hint_files(tid, name):
        txt = open(f).read().strip()
        parts.append(f"### {os.path.relpath(f, KNOW)}\n{txt}")
    s = "\n\n".join(parts)
    return s[-limit:] if len(s) > limit else s


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
    sibs.sort(key=lambda x: -x[0])
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
- Team/character/car/course select: accept the default with A (or START), repeatedly if several confirms.
- Profile creation / name entry: on a keyboard, A TYPES the highlighted letter. Prefer START, which usually
  jumps to Done/Accept; then A on Done/OK. Accept defaults.
- Save/load prompts: "no storage device / continue without saving": choose continue. Prompts that create a
  save: Yes is fine. Beware prompts whose default is No when Yes is needed to proceed.
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
  RT:<seconds>  LT:<seconds>                           hold a trigger (accelerate/brake in racing games)
  HOLD:<button>:<seconds>                              hold a button
An empty list [] means wait and look again.

States (pick exactly one): intro_video, publisher_logo, title_screen, main_menu, submenu, profile_creation,
name_entry, save_load_prompt, controller_prompt, loading, cutscene, pause, gameplay, results, game_over,
black, unknown.

Say "gameplay" only when you see player-controlled play (a HUD, a playfield with the player's character or
vehicle), not a menu, not a replay/attract demo with "Press Start", not a cutscene with letterbox bars or
subtitles. The "FPS: NN" text at the top-left is the EMULATOR's overlay on every frame: it is NOT a game
HUD and never evidence of gameplay. An intro cinematic right after the publisher logos, before any title
screen or menu, is a cutscene even when it shows the hero in the game world: skip it. When you say gameplay, also give "probe": a list of inputs whose LAST one should visibly move
the player or camera for ~1.5 s (racing: ["RT:1.5"]; on foot: ["STICK:up:1.5"]); put any input needed to
start the play first (a kickoff or serve: ["A", "STICK:up:1.5"]).

Answer exactly:
{"state": "<state>", "why": "<one line: what you see, where the cursor is>",
 "action": ["<token>", ...], "wait_s": <seconds to wait after the inputs, 1-10>, "probe": [<tokens>] or []}"""


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
        rec = {"t": round(t0, 3), "model": model, "purpose": purpose}
        if self.sim is not None:
            ans = self.sim.pop(0) if self.sim else {"state": "unknown", "why": "sim exhausted", "action": []}
            text, meta = json.dumps(ans), {}
        else:
            cmd = ["claude", "-p", "--model", model, "--input-format", "stream-json", "--output-format",
                   "stream-json", "--verbose", "--tools", "", "--system-prompt", SYSTEM, "--no-session-persistence"]
            content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                     "data": base64.b64encode(open(i, "rb").read()).decode()}}
                       for i in images]
            msg = {"type": "user", "message": {"role": "user", "content": content + [{"type": "text", "text": prompt}]}}
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
        elif re.fullmatch(r"(STICK:(up|down|left|right|upleft|upright)|RT|LT|HOLD:[A-Z0-9]+):[0-9.]+", tok, re.I):
            parts = tok.split(":")
            parts[0] = parts[0].upper()
            if parts[0] == "STICK":
                parts[1] = parts[1].lower()
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
        self.hints = knowledge(tid, name)
        self.probes = 0
        self.black_since = None
        self.result = {"title_id": tid, "name": name, "device": dev.label, "iso": iso, "result": "running",
                       "tool": subprocess.run(["git", "hash-object", os.path.abspath(__file__)], capture_output=True,
                                              text=True).stdout.strip()[:10],
                       "started": time.strftime("%Y-%m-%d %H:%M:%S %Z")}
        self.thermal = []

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
            if parts[0] == "STICK":
                axes = STICK[parts[1]]
                for ax, v in axes:
                    self.dev.pad("axis", ax, v)
                time.sleep(secs)
                for ax, _ in axes:
                    self.dev.pad("axis", ax, "mid")
            elif parts[0] in ("RT", "LT"):
                self.dev.pad("axis", parts[0], "max")
                time.sleep(secs)
                self.dev.pad("axis", parts[0], "min")
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
        return (f"{RULES}\n\nKnowledge from other titles (hints):\n{self.hints or '(none yet)'}\n\n{guide}"
                f"Title: {self.name} (id {self.tid or '?'}), device {self.dev.label}. "
                f"{self.el() / 60:.1f} min since cold boot.\n\nLast steps:\n{self.history()}\n\n{extra}"
                "The attached image is the screen NOW. Answer with the JSON object only.")

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
        screen every step and is invisible to tried_here."""
        return [" ".join(s["action"]) for s in self.steps[-k:]
                if s.get("action") and s.get("sig") is not None and sig_dist(s["sig"], sig) <= SIG_MATCH]

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
        if probe in BUTTONS and probe not in HAT:
            probe = f"HOLD:{probe}:1.5"
        elif probe in HAT:
            probe = {"UP": "STICK:up:1.5", "DOWN": "STICK:down:1.5", "LEFT": "STICK:left:1.5",
                     "RIGHT": "STICK:right:1.5"}[probe]
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
        # hold the probe and capture DURING it
        parts = probe.split(":")
        held = []
        if parts[0] == "STICK":
            for ax, v in STICK[parts[1]]:
                self.dev.pad("axis", ax, v)
                held.append((ax, "mid"))
        elif parts[0] in ("RT", "LT"):
            self.dev.pad("axis", parts[0], "max")
            held.append((parts[0], "min"))
        elif parts[0] == "HOLD" or parts[0] in BUTTONS:
            btn = parts[1] if parts[0] == "HOLD" else parts[0]
            self.dev.pad("hold", btn)
            held.append(("release", btn))
        time.sleep(0.8)
        c_png, c_jpg = self.frame("probe-c")
        time.sleep(0.5)
        for ax, v in held:
            if ax == "release":
                self.dev.pad("release", v)
            else:
                self.dev.pad("axis", ax, v)
        if not c_png:
            return False, "screencap failed"
        ctrl, moved = changed(a_png, b_png), changed(b_png, c_png)
        rec = {"state": "probe", "action": pre + [probe], "why": f"control {ctrl:.3f}, under input {moved:.3f}",
               "src": "probe", "changed": moved}
        if moved < PROBE_MOVED or moved < 1.5 * ctrl:
            # 1.5x the no-input control: Bruce Lee's cinematic moved 0.249 with no input, 0.297 "under" it
            rec["verdict"] = "no change under the input beyond what changes on its own"
            self.write_step(rec)
            return False, (f"the screen did not change while {probe} was held beyond its own motion "
                           f"(control {ctrl:.3f}, under input {moved:.3f})")
        if letterboxed(a_png) or letterboxed(c_png):
            rec["verdict"] = "letterboxed: a cutscene"
            self.write_step(rec)
            return False, "black bars top and bottom: this is a cutscene, not gameplay"
        q = (f"Three screenshots of {self.name}, an Xbox game, attached in order: A, then B (1 s after A, no "
             f"input), then C (taken while holding {probe}, ~1 s after B). The 'FPS: NN' text at the top-left is the "
             f"emulator's overlay, not a game HUD. The previous step "
             f"judged this gameplay: \"{why}\".\nIs this real player-controlled gameplay (not a menu, not a "
             "cutscene, not an attract/demo mode, not a replay), AND does C show the playfield responding to "
             f"the input {probe} (the player/vehicle/camera moved accordingly), beyond whatever changed on its "
             "own between A and B? A menu cursor moving is NOT a response. Answer JSON only: "
             '{"gameplay": true|false, "responded": true|false, "why": "<one line>"}')
        ans = self.model.ask(STRONG, q, "confirm", [a_jpg, b_jpg, c_jpg]) or {}
        ok = bool(ans.get("gameplay")) and bool(ans.get("responded"))
        rec["verdict"] = ("CONFIRMED: " if ok else "refused: ") + str(ans.get("why", "no answer"))[:200]
        self.write_step(rec)
        self.result["probe_frames"] = [a_jpg, b_jpg, c_jpg]
        return ok, rec["verdict"]

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
            if self.steps and last_png:
                self.steps[-1]["changed"] = round(changed(last_png, png), 4)
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
        # 2. static after a wait on a loading/black screen: wait again
        if prev and not prev.get("action") and prev.get("state") in ("loading",) \
                and prev.get("changed") is not None and prev["changed"] <= UNCHANGED \
                and sum(1 for s in self.steps[-4:] if s.get("src") == "static") < 3:
            return dict(base, state="loading", why="static frame after waiting on a load", action=[],
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
        # 4. the model; the stronger one when stuck or unsure
        cycle = max((seen.count(a) for a in seen), default=0) >= 2
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
        # never the same input a 4th time on the same unchanged screen
        if action and (tried.count(" ".join(action)) >= 3 or seen.count(" ".join(action)) >= 4):
            fresh = [b for b in SKIP_LADDER if b not in tried]
            action = [fresh[0]] if fresh else ["START"]
            ans["why"] = str(ans.get("why", "")) + f" [override: repeated input on unchanged screen -> {action[0]}]"
        try:
            wait_s = float(ans.get("wait_s") or 2)
        except (TypeError, ValueError):
            wait_s = 2.0
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
        return self.finish(last=jpg, post=post)

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
    print(f"pathfind: {name} ({tid}) on {dev.label}: {iso}", flush=True)
    agent = Agent(dev, model, tid, name, iso, a.out, a.budget_min * 60, record=not a.no_record)
    if a.no_replay or a.no_guide:
        agent.own = None
    if a.no_guide:
        agent.sibs = []
    return agent.run()


if __name__ == "__main__":
    sys.exit(main())
