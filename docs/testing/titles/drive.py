#!/usr/bin/env python3
"""drive.py -- the screen-aware play driver behind route.sh's `drive` step (#433).

    SERIAL=<s> PAD_DEV=<node> drive.py --profile drive-profiles/<t>.toml --seconds N
                                       [--find] [--mark] --out <result dir> [--frames <dir>]
    drive.py --sim <frames dir or @list> --profile P --out DIR [--find]   no device
    drive.py learn <route-solution.json>          the [skip.*] tables to paste into the profile

WHY (owner, 2026-10-01 21:45 PDT). A route used to be open-loop: fixed waits,
one-shot presses, and a blind `repeat forever { ... press A ... }` play loop
that sent START and A into whatever was on screen. START in live play
pauses the game, A on a results screen opens a menu, and the scored window
filled with menus and pauses: Super Monkey Ball sat 10 minutes on Stage
Select (1790900520-autoverdict-566484), Sonic Heroes sat paused
(1790902215-autoverdict-1078702), Forza sat on the grid at 0 MPH
(1790914021-lane.ibcache-3202498). This loop LOOKS first: capture, name the
screen (classify.py), send the input the title's profile maps that state
to, and write the state down.

THE LOOP, per capture:
  1. `adb exec-out screencap -p` to a scratch file (its wall time is in the
     timeline: that is the capture's cost on the host side).
  2. classify.py names the state from the frame, the previous capture and
     the states already seen. `unknown` for `unknown_before_model`
     consecutive captures asks the model (MODEL FALLBACK, below) when
     ANTHROPIC_API_KEY is set; with no key nothing is ever sent anywhere.
  3. The state's policy (POLICY, below) decides the input.
  4. A state CHANGE is logged to logcat as `I/hakuX-route: state=<s> t=<s>`
     (device clock: title_verdict.py reads play time from these), a row goes
     to <out>/route-state.tsv for every capture, and the frame is kept in
     <frames> when the state changes, every `keep_every_s` of play, and on a
     failure.
  5. Sleep the capture interval (CAPTURE RATE) and go again.

POLICY. States are classify.py's; the inputs come from the profile's
[input] table, never from a guess here.
  boot, black, loading   wait; nothing pressed; any held play input released.
  logo, intro_video, cutscene
                         SKIP (owner, ADDENDUM 2): at once on entry, the
                         profile's recorded winning button first, then the
                         ladder A, START, B, X, START+A, one press per
                         `skip_settle_s`, re-classified between presses. A
                         press after which the state changes is the winner
                         and is recorded (`skip: intro_video via A at +2.1 s
                         -> title`). Three passes with no change: `skip=none`,
                         and wait. Nothing is held down. BACK and the guide
                         button are never used. START (and START+A) is left
                         out of the `cutscene` ladder unless the profile has a
                         `paused` crop: a cutscene that ends into live play
                         would take that START as a pause, and only a
                         pause the driver can SEE can be undone. A profile
                         may replace the ladder ([drive] ladder = [...]) where
                         a ladder button does harm on a screen the classifier
                         calls moving (Forza's dimmed menus: B backs out).
  title                  the profile's input.title (START), once per
                         `menu_gap_s`; the next state is checked, and `play`
                         or `paused` straight after `title` is an anomaly.
  main_menu, profile, ingame_menu
                         the crop's own `press` list if the crop that named
                         the screen carries one (a Name Entry needs START to
                         reach Accept, then A), else input.<state>, one press
                         per `menu_gap_s`; `menu_max_presses` on one screen
                         without leaving it is ROUTE FAIL "stuck".
  paused                 input.paused (the resume buttons, tried in turn),
                         then re-classify; still paused after 3 presses is
                         ROUTE FAIL.
A press may be `AXIS:value` (`LX:min`): the stick is flicked there and back,
for a cursor the d-pad does not move (Castlevania's save prompt).
  play                   the profile's play_hold axes held (re-asserted each
                         capture), or play_cycle's phases in turn ([[axes],
                         seconds]: an on-foot title walks a square, since one
                         held direction ends against the first wall),
                         play_tap buttons every N s. NEVER START: the profile
                         is refused if a play input is START. The play input
                         is also held, as a probe, on any frame where the
                         play HUD is up but the motion has not said `play`
                         yet: an idle character makes no motion, so play
                         would never be confirmed without it.
  stalled                HUD up, nothing moving (or a still, uncropped frame
                         within `hud_memory_s` of a HUD frame: a title that
                         hides its HUD when the player idles, Castlevania,
                         is not on a menu): keep the play input held;
                         `stall_fail_s` of it is ROUTE FAIL "the play input is
                         not reaching the game" (Forza at 0 MPH). A profile
                         with input.stall_cycle ([[axes], seconds, [buttons]]
                         phases) plays it once per stall, to its end, up to
                         `escape_max` times: back off, jump, try a side
                         (Sonic Heroes wedges on a Seaside Hill block).
                         input.stall_cycles, a list of cycles, plays
                         escape n with cycle (n-1) mod len: one run tries
                         several escapes, one per stall.
  unknown                wait; the model after `unknown_before_model`
                         captures; `unknown_fail_s` of it is ROUTE FAIL.
A state seen after a later one in the profile's `order` (a main_menu after
play) is logged as `anomaly`.

ENDING AT GAMEPLAY (owner, ADDENDUM 1). With --find the driver's job is to
FIND gameplay, not to play a window: `find_play_s` (20 s) of consecutive
`play` captures ends it, with exit 0 and `result=reached-play`. The frames of
that stretch are all kept, for the frame review the owner's rule still
requires. With --mark (and no --find) the driver writes `mark gameplay` to
logcat itself after `confirm_play_s` of play, so a scored window starts on
seen play, not on a timer.

CAPTURE RATE. `fast_s` between captures everywhere except stable play, and
there `slow_s` -- once play has been confirmed and no input other than the
held play axes went out in the last `fast_s`. --find stays fast throughout
(nothing is scored). The defaults come from the capture-cost study
(docs/lanes/routedriver/NOTES.md, CAPTURE COST).

THE SOLUTION. <out>/route-solution.json records what got this title to
play: every input sent with its state and time, every skip that landed (and
every state that would not skip), time to `title` and to `play`, and which
captures each classifier source named. `drive.py learn` turns its skips into
the profile's [skip.<state>] tables, so the next run tries the winner first.

MODEL FALLBACK. Claude Haiku 4.5 (`claude-haiku-4-5-20251001`), one JPEG
downscaled to 512 px, asked for {"screen_class", "button"}. Capped at
`model_calls_max` per run (default 20) and cached by frame hash. Every call
goes to <out>/classify-model-calls.jsonl with its token counts and cost.
Its answer names a state; its button is used only for a menu-like state and
never when the state is play. No key, no call: the default is zero calls.

EXIT: 0 the window ran out or (--find) play was reached; 1 ROUTE FAIL
(the reason is the last line printed and the summary in route-state.tsv);
2 usage/profile error.
"""
import argparse
import base64
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify  # noqa: E402

PAD = os.path.join(HERE, "..", "perf", "pad.sh")
SKIPPABLE = ("logo", "intro_video", "cutscene")
MENU_LIKE = ("title", "main_menu", "profile", "ingame_menu")
LADDER = ("A", "START", "B", "X", "START+A")
NEVER = {"BACK", "SELECT"}            # BACK exits to the dashboard on some titles; no guide button exists here

DEFAULTS = dict(
    fast_s=1.0, slow_s=5.0, skip_settle_s=1.5, skip_passes=3, menu_gap_s=2.0, menu_max_presses=25,
    resume_tries=3, stall_fail_s=40.0, unknown_before_model=3, unknown_fail_s=90.0,
    model_calls_max=20, find_play_s=20.0, confirm_play_s=6.0, keep_every_s=30.0, screencap_fail_s=60.0,
    hud_memory_s=20.0, escape_max=6, escape_capture_s=0.0, escape_reset_s=0.0,
    progress_bar=0.0, progress_window_s=10.0, stall_clear_s=0.0,
)

MODEL = "claude-haiku-4-5-20251001"
# USD per million tokens, Haiku 4.5 list price when this was written. The
# cost logged per call is tokens x these; check them against the current
# price list before reading the dollars as a bill.
MODEL_USD_PER_MTOK = (1.0, 5.0)
MODEL_PROMPT = (
    "This is a screenshot of an original-Xbox game running in an emulator, taken during an "
    "unattended playtest that is trying to reach live gameplay. Answer with ONLY a JSON object: "
    '{"screen_class": one of "logo","intro_video","title","main_menu","profile","loading",'
    '"cutscene","ingame_menu","paused","play","black", '
    '"button": the ONE gamepad button (A, B, X, Y or START) that makes progress toward live '
    'gameplay from this screen, or "" if waiting is right}. "play" means the player is in '
    "control of a character or vehicle right now; a pause overlay over the game is \"paused\"."
)


def now():
    return time.monotonic()


class Device:
    """The only thing that touches the handheld: screencap, pad.sh, logcat."""

    def __init__(self, serial):
        self.serial = serial
        self.env = dict(os.environ, SERIAL=serial)

    def capture(self, path):
        t = now()
        try:
            with open(path, "wb") as f:
                r = subprocess.run(["adb", "-s", self.serial, "exec-out", "screencap", "-p"],
                                   stdout=f, stderr=subprocess.DEVNULL, timeout=30)
            ok = r.returncode == 0 and os.path.getsize(path) > 0
        except (subprocess.TimeoutExpired, OSError):
            ok = False
        return ok, now() - t

    def pad(self, *args):
        try:
            subprocess.run(["bash", PAD] + list(args), env=self.env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=30)
        except subprocess.TimeoutExpired:
            pass

    def logcat(self, msg):
        try:
            subprocess.run(["adb", "-s", self.serial, "shell", "log", "-t", "hakuX-route", "'%s'" % msg],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        except subprocess.TimeoutExpired:
            pass


class SimDevice:
    """Frames from disk, in order, one per capture; inputs recorded, not sent.
    It cannot react to an input -- it replays what a past run saw -- so it
    tests the naming, the timeline and the bookkeeping, not the policy's
    effect on a title."""

    def __init__(self, frames, step_s):
        self.frames = list(frames)
        self.i = 0
        self.sent = []
        self.log = []
        self.step_s = step_s
        self.clock = 0.0

    def capture(self, path):
        if self.i >= len(self.frames):
            return False, 0.0
        shutil.copyfile(self.frames[self.i], path)
        self.i += 1
        return True, 0.0

    def pad(self, *args):
        self.sent.append((round(self.clock, 1),) + args)

    def logcat(self, msg):
        self.log.append(msg)


class Driver:
    def __init__(self, dev, profile, out, frames_dir, seconds, find=False, mark=False, sim=False):
        self.dev, self.p, self.out, self.frames_dir = dev, profile, out, frames_dir
        self.seconds, self.find, self.mark, self.sim = seconds, find, mark, sim
        self.cfg = dict(DEFAULTS)
        self.cfg.update({k: v for k, v in profile.get("drive", {}).items() if k in DEFAULTS})
        self.inp = profile.get("input", {})
        self.check_profile()
        self.crops = {c["name"]: c for c in profile.get("crop", [])}
        self.order = profile.get("order", [])
        self.has_pause_crop = any(c["state"] == "paused" for c in profile.get("crop", []))
        os.makedirs(out, exist_ok=True)
        os.makedirs(frames_dir, exist_ok=True)
        self.tsv = open(os.path.join(out, "route-state.tsv"), "w")
        self.tsv.write("t\tstate\tsource\tchanged\tluma\tcap_s\taction\tframe\tmode\n")
        self.t0 = None
        self.clock_sim = 0.0
        self.state = None
        self.state_since = 0.0
        self.seen = []
        self.furthest = -1
        self.prev = None
        self.last_play_luma = None
        self.held = []                   # (axis, value) currently held
        self.last_press_t = -1e9
        self.inputs = []                 # the solution's input list
        self.skips = []
        self.ladder = None               # current skip attempt: dict
        self.screen_presses = {}         # (state, source) -> presses this visit
        self.resume_tries = 0
        self.unknown_since = None
        self.unknown_streak = 0
        self.stalled_since = None
        self.escapes = 0                 # stall_cycle runs so far
        self.esc_frames = 0
        self.esc_phase = 0
        self.mode = None                 # the [[mode]] the HUD shows (Sonic Heroes: the formation)
        self.mode_escapes = {}           # escapes played per mode: picks that mode's next cycle
        self.scene_hist = []             # (t, scene) of recent HUD frames: the progress check
        self.stall_streak = False        # stall_clear_s: inside a stall, play must hold to count
        self.recover_since = None
        self.last_hud_t = None
        self.play_since = None
        self.play_frames = []
        self.marked = False
        self.last_keep = -1e9
        self.model_calls = 0
        self.model_cache = {}
        self.sources = {}
        self.anomalies = []
        self.time_to = {}
        self.result = None
        self.n = 0
        self.cap_t = 0.0

    # -- bookkeeping -------------------------------------------------------
    def check_profile(self):
        for b, _ in self.inp.get("play_tap", []):
            if b in ("START", "SELECT", "BACK"):
                raise SystemExit("drive.py: profile play_tap sends %s: START in live play pauses it" % b)
        for mode in [None] + [m["name"] for m in self.p.get("mode", [])]:
            self.mode = mode
            for b, _ in self.inp_for("play_tap", []):
                if b in ("START", "SELECT", "BACK"):
                    raise SystemExit("drive.py: profile play_tap (mode %s) sends %s: START in live play pauses it"
                                     % (mode, b))
            for n in range(1, len(self.stall_cycles()) + 1):
                for b in [b.split("/")[0] for _, _, btns in self.stall_phases(n) for b in btns]:
                    if b in ("START", "SELECT", "BACK") or b in NEVER:
                        raise SystemExit("drive.py: profile stall_cycle (mode %s) sends %s: START in live play "
                                         "pauses it" % (mode, b))
        self.mode = None
        for k, v in self.inp.items():
            if k.startswith("play") or k in ("stall_cycle", "stall_cycles"):
                continue
            for b in v:
                if b in NEVER:
                    raise SystemExit("drive.py: profile input.%s sends %s, which can exit to the dashboard" % (k, b))

    def t(self):
        return self.clock_sim if self.sim else now() - self.t0

    def press(self, btn, why):
        t = self.t()
        if btn == "START+A":
            self.dev.pad("hold", "START")
            self.dev.pad("press", "A")
            self.dev.pad("release", "START")
        elif ":" in btn:                 # AXIS:value, a stick flick (a cursor move where the d-pad is not mapped)
            ax, val = btn.split(":", 1)
            self.dev.pad("axis", ax, val)
            self.sleep(0.4)
            self.dev.pad("axis", ax, "mid")
        else:
            self.dev.pad("press", btn)
        self.last_press_t = t
        self.inputs.append(dict(t=round(t, 1), state=self.state, input=btn, why=why))
        return "press %s (%s)" % (btn, why)

    def stall_cycles(self):
        """input.stall_cycles (a list of cycles: escape n plays cycle
        (n-1) mod len, so one run can try several escapes, one per stall),
        else [input.stall_cycle]."""
        m = self.mode_table()
        src = m if ("stall_cycles" in m or "stall_cycle" in m) else self.inp
        if src.get("stall_cycles"):
            return list(src["stall_cycles"])
        return [src["stall_cycle"]] if src.get("stall_cycle") else []

    def mode_table(self):
        for m in self.p.get("mode", []):
            if m["name"] == self.mode:
                return m
        return {}

    def inp_for(self, key, default=None):
        """input.<key>, or the current [[mode]]'s own <key> when it has one."""
        m = self.mode_table()
        return m[key] if key in m else self.inp.get(key, default)

    def which_mode(self, frame):
        """The [[mode]] whose `rgb` the frame's `region` is nearest, within
        `tol` (Euclidean, 0-255 RGB); None when no mode is that close."""
        best, bd = None, None
        for m in self.p.get("mode", []):
            c = classify.region_rgb(frame, m["region"])
            d = sum((x - y) ** 2 for x, y in zip(c, m["rgb"])) ** 0.5
            if d <= m.get("tol", 45.0) and (bd is None or d < bd):
                best, bd = m["name"], d
        return best

    def stall_phases(self, n=1):
        """Escape n's cycle as [(axes, seconds, buttons)]: [[axes], seconds]
        or [[axes], seconds, [buttons]] (pressed once on entering the phase,
        0.3 s apart: A, A is a jump and a mid-air action; `A/800` holds A
        for 800 ms instead of pad.sh's 60). Empty axes release the stick."""
        cycles = self.stall_cycles()
        if not cycles:
            return []
        out = []
        for ph in cycles[(n - 1) % len(cycles)]:
            out.append(([tuple(x) for x in ph[0]], float(ph[1]), list(ph[2]) if len(ph) > 2 else []))
        return out

    def start_escape(self):
        self.escapes += 1
        self.mode_escapes[self.mode] = self.mode_escapes.get(self.mode, 0) + 1
        self.escape()

    def escape(self):
        """Play escape number self.escapes's cycle through, now, with no
        decisions in between: each phase's axes held for its seconds, its
        buttons pressed 0.3 s apart at its start. Synchronous because the
        phases are short and exact: run off the capture clock (5 s apart in
        stable play), Sonic Heroes' 2.5 s back-off ran ~6 s and walked the
        team off the ledge into the sea, three times (session 4, replay 3).
        [drive] escape_capture_s > 0 keeps a frame that often through the
        escape (named `esc<n>-p<phase>`), so a trial can see where it went.
        The captures run on a thread of their own: taken in line they would
        put a gap into the press cadence a flight depends on."""
        every = float(self.cfg.get("escape_capture_s") or 0)
        stop = threading.Event()
        cap = None
        if every and not self.sim:
            cap = threading.Thread(target=self.escape_frames, args=(every, stop), daemon=True)
            cap.start()
        try:
            self.escape_phases()
        finally:
            stop.set()
            if cap:
                cap.join(timeout=35)

    def escape_phases(self):
        n = self.mode_escapes.get(self.mode, 0)
        for k, (axes, s, btns) in enumerate(self.stall_phases(n)):
            self.esc_phase = k + 1
            self.inputs.append(dict(t=round(self.t(), 1), state=self.state,
                                    why="stall escape %d phase %d" % (self.escapes, k + 1),
                                    input=" ".join("%s %s" % a for a in axes) + (" + " + ",".join(btns) if btns else "")))
            for ax, _ in self.held:
                if ax not in [a for a, _ in axes]:
                    self.dev.pad("axis", ax, "mid")
            for ax, val in axes:
                self.dev.pad("axis", ax, str(val))
            self.held = list(axes)
            t0 = self.t()
            for j, b in enumerate(btns):
                if j:
                    self.sleep(0.3)
                if "/" in b:
                    b, ms = b.split("/", 1)
                    self.dev.pad("press", b, ms)
                else:
                    self.dev.pad("press", b)
            self.sleep(max(0.0, s - (self.t() - t0)))

    def escape_frames(self, every, stop):
        path = os.path.join(self.frames_dir, ".esc.png")
        while not stop.is_set():
            t = now()
            ok, _ = self.dev.capture(path)
            if ok:
                self.esc_frames += 1
                os.replace(path, os.path.join(self.frames_dir, "%s-%03d-esc%d-p%d-%03d.png" % (
                    time.strftime("%H%M%S"), self.n, self.escapes, self.esc_phase, self.esc_frames)))
            stop.wait(max(0.0, every - (now() - t)))

    def hold_play(self):
        want = [tuple(x) for x in self.inp_for("play_hold", [])]
        cycle = self.inp_for("play_cycle")
        if cycle:
            # An on-foot title: one held direction walks into the first wall
            # (Castlevania's fountain, run 3), so the held axes rotate through
            # phases of [[axis, value], seconds].
            total = sum(float(s) for _, s in cycle)
            at = self.t() % total
            for axes, s in cycle:
                if at < float(s):
                    want = [tuple(x) for x in axes]
                    break
                at -= float(s)
        for ax, _ in self.held:
            if ax not in [a for a, _ in want]:
                self.dev.pad("axis", ax, "mid")
        for ax, val in want:
            self.dev.pad("axis", ax, str(val))
        if want and self.held != want:
            self.inputs.append(dict(t=round(self.t(), 1), state=self.state,
                                    input="hold " + " ".join("%s %s" % a for a in want), why="play"))
        self.held = want

    def release_play(self):
        for ax, _ in self.held:
            self.dev.pad("axis", ax, "mid")
        if self.held:
            self.inputs.append(dict(t=round(self.t(), 1), state=self.state, input="release axes", why="left play"))
        self.held = []

    def keep(self, frame, tag):
        name = "%s-%03d-%s.png" % (time.strftime("%H%M%S"), self.n, tag)
        shutil.copyfile(frame, os.path.join(self.frames_dir, name))
        return name

    # -- the model ---------------------------------------------------------
    def ask_model(self, frame):
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key or self.model_calls >= self.cfg["model_calls_max"]:
            return None
        with open(frame, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()[:16]
        if h in self.model_cache:
            return self.model_cache[h]
        from PIL import Image
        im = Image.open(frame).convert("RGB")
        im.thumbnail((512, 512))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        body = dict(model=MODEL, max_tokens=100, messages=[dict(role="user", content=[
            dict(type="image", source=dict(type="base64", media_type="image/jpeg",
                                           data=base64.b64encode(buf.getvalue()).decode())),
            dict(type="text", text=MODEL_PROMPT)])])
        rec = dict(t=round(self.t(), 1), frame_hash=h, model=MODEL)
        self.model_calls += 1
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages",
                                         data=json.dumps(body).encode(),
                                         headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                                  "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.load(r)
            text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
            ans = json.loads(text[text.find("{"):text.rfind("}") + 1])
            u = resp.get("usage", {})
            rec.update(answer=ans, input_tokens=u.get("input_tokens"), output_tokens=u.get("output_tokens"))
            rec["usd"] = round((u.get("input_tokens", 0) * MODEL_USD_PER_MTOK[0]
                                + u.get("output_tokens", 0) * MODEL_USD_PER_MTOK[1]) / 1e6, 6)
            st = ans.get("screen_class")
            out = dict(state=st if st in classify.STATES else None, button=str(ans.get("button") or "").upper())
        except Exception as exc:                       # an API failure is an unknown, not a crash
            rec["error"] = str(exc)[:200]
            out = None
        with open(os.path.join(self.out, "classify-model-calls.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        self.model_cache[h] = out
        return out

    # -- one capture -------------------------------------------------------
    def classify(self, frame):
        r = classify.classify_frame(frame, self.prev, self.p, self.seen, self.last_play_luma, self.state)
        if r.get("crop") and r["source"].startswith("hud:"):
            self.last_hud_t = self.t()
        elif (r["source"] in ("static", "between") and self.last_hud_t is not None
              and self.t() - self.last_hud_t < self.cfg["hud_memory_s"]):
            # A still, uncropped frame moments after the play HUD was up: a
            # title that hides its HUD when the player idles (Castlevania),
            # not a menu. `stalled`: the play input stays held, and the stall
            # watch still ends the run if nothing ever moves.
            r.update(state="stalled", source="static+hud-recent")
        if "hud:" in r["source"]:                 # the play HUD is up (also on a run's first frame, `no-prev hud:`)
            if self.p.get("mode"):
                m = self.which_mode(frame)
                if m is not None:
                    self.mode = m
            self.progress(frame, r)
        else:
            self.scene_hist = []
        self.recovering(r)
        if r["state"] == "unknown":
            self.unknown_streak += 1
            if self.unknown_streak >= self.cfg["unknown_before_model"]:
                m = self.ask_model(frame)
                if m and m["state"]:
                    r.update(state=m["state"], source="model", model_button=m["button"])
        else:
            self.unknown_streak = 0
        return r

    def progress(self, frame, r):
        """[drive] progress_bar > 0: a `play` frame whose scene layout
        (classify.scene, 32x24) changed less than the bar against the HUD
        frame `progress_window_s` earlier is `stalled` (source
        hud+no-progress): the player is moving in place, not getting
        anywhere. Sonic Heroes, trial 1 of lane.routedriver2: running
        changed 0.46-0.71 of the cells over 8-14 s, a team struggling in a
        corner 0.07-0.26 while its 2 s motion read 0.35-0.50 -- `play` on
        the per-capture bars. Off by default: a title whose play can stay in
        one place (an arena, a play_cycle walking a square) must not opt in.
        Any non-HUD frame (a death's black, a menu) starts the window over."""
        bar = self.cfg["progress_bar"]
        if not bar:
            return
        t, win = self.t(), self.cfg["progress_window_s"]
        sig = classify.scene(frame, self.p.get("drive", {}).get("progress_mask", []))
        old = [(ht, hs) for ht, hs in self.scene_hist if t - 1.6 * win <= ht <= t - win]
        self.scene_hist = [(ht, hs) for ht, hs in self.scene_hist if ht >= t - 1.6 * win] + [(t, sig)]
        if not old:
            return
        ch = classify.scene_change(sig, old[-1][1])
        r["progress"] = round(ch, 3)
        if r["state"] == "play" and ch < bar:
            r.update(state="stalled", source="hud+no-progress")

    def recovering(self, r):
        """[drive] stall_clear_s > 0: once stalled, `play` must hold that long
        before it is play again; until then the frame is `stalled` (source
        +recovering, r["recovering"]). A team wedged at one place keeps
        throwing short `play` reads -- Tails hovering up and down beside a
        block moves the camera (lane.routedriver2 trial 2: ~45% of 100 s
        stuck at Seaside Hill's POWER block read play) -- and each one both
        counted as play time and restarted the stall watch, so the run never
        ended. The cost: the first stall_clear_s of real play after a stall
        is logged as stalled, which understates play_share, never inflates it.
        A frame without the play HUD (a death's black, a menu) ends the streak."""
        clear = self.cfg["stall_clear_s"]
        if not clear:
            return
        if r["state"] == "stalled":
            self.stall_streak, self.recover_since = True, None
        elif "hud:" not in r["source"]:
            self.stall_streak, self.recover_since = False, None
        elif r["state"] == "play" and self.stall_streak:
            if self.recover_since is None:
                self.recover_since = self.t()
            if self.t() - self.recover_since < clear:
                r.update(state="stalled", source=r["source"] + "+recovering", recovering=True)
            else:
                self.stall_streak, self.recover_since = False, None

    def play_taps(self, t):
        act = ""
        for b, every in self.inp_for("play_tap", []):
            last = getattr(self, "_tap_" + b, -1e9)
            if t - last >= every:
                setattr(self, "_tap_" + b, t)
                self.dev.pad("press", b)
                act += " tap %s" % b
        return act

    def enter(self, state, r, frame):
        t = self.t()
        prev = self.state
        self.state, self.state_since = state, t
        if state not in self.seen:
            self.seen.append(state)
        if state in self.order:
            i = self.order.index(state)
            if i < self.furthest and state not in ("paused", "ingame_menu", "loading", "cutscene", "stalled"):
                self.anomalies.append(dict(t=round(t, 1), state=state, after=self.order[self.furthest]))
            self.furthest = max(self.furthest, i)
        if state in ("title", "play") and state not in self.time_to:
            self.time_to[state] = round(t, 1)
        if prev == "title" and state in ("play", "paused"):
            self.anomalies.append(dict(t=round(t, 1), state=state, after="title"))
        # a skip attempt resolves on the first capture in another state
        if self.ladder and state != self.ladder["state"]:
            lad = self.ladder
            if lad["last"] is not None and state != "paused":
                self.skips.append(dict(state=lad["state"], button=lad["last"],
                                       after_s=round(lad["last_t"] - lad["since"], 1),
                                       landed=state, presses=lad["presses"]))
            elif lad["last"] is None:
                self.skips.append(dict(state=lad["state"], button=None, waited_s=round(t - lad["since"], 1),
                                       landed=state, presses=0))
            self.ladder = None
        self.dev.logcat("state=%s t=%d" % (state, int(t)))
        if prev != "paused":
            self.resume_tries = 0

    def act(self, state, r, frame):
        """The policy. Returns the action string for the timeline, or raises Fail."""
        t = self.t()
        cfg = self.cfg
        if state == "unknown" and r.get("source", "").startswith("hud:"):
            # The play HUD is up but the motion does not say play yet: the
            # first frame after a load or overlay, or a character standing
            # still because nothing is held -- and play is only confirmed by
            # motion, which an idle character never makes (Castlevania, run
            # 1 of this lane: HUD up, nothing held, then A presses into the
            # game as a "menu"). So hold the play input as the probe. Inside
            # a play stretch this neither ends the stretch nor counts toward it.
            self.hold_play()
            return "hold (hud up, motion not yet play)"
        if state != "play" and state != "stalled" and self.held:
            self.release_play()
        if state != "stalled":
            self.stalled_since = None
        if state != "unknown":
            self.unknown_since = None
        if state != "play":
            self.play_since = None
            self.play_frames = []

        if state in ("boot", "black", "loading"):
            return "wait"

        if state in SKIPPABLE:
            lad = self.ladder
            if lad is None or lad["state"] != state:
                rec = self.p.get("skip", {}).get(state, {}).get("button")
                ladder = [b for b in self.p.get("drive", {}).get("ladder", LADDER)
                          if state != "cutscene" or self.has_pause_crop or "START" not in b]
                if rec:
                    ladder = [rec] + [b for b in ladder if b != rec]
                if rec == "none":
                    ladder = []
                lad = self.ladder = dict(state=state, since=t, ladder=ladder, i=0, last=None, last_t=None,
                                         presses=0, gave_up=False)
            if lad["gave_up"] or not lad["ladder"]:
                return "wait (skip=none)"
            if lad["i"] >= len(lad["ladder"]) * cfg["skip_passes"]:
                lad["gave_up"] = True
                lad["last"] = None
                return "skip=none after %d passes" % cfg["skip_passes"]
            if t - self.last_press_t < cfg["skip_settle_s"]:
                return "settle"
            b = lad["ladder"][lad["i"] % len(lad["ladder"])]
            lad["i"] += 1
            lad["presses"] += 1
            lad["last"], lad["last_t"] = b, t
            return self.press(b, "skip %s" % state)

        if state == "paused":
            if t - self.last_press_t < cfg["menu_gap_s"]:
                return "settle"
            if self.resume_tries >= cfg["resume_tries"]:
                raise Fail("paused after %d resume presses" % self.resume_tries)
            self.resume_tries += 1
            seq = self.inp.get("paused") or ["START"]
            return self.press(seq[(self.resume_tries - 1) % len(seq)], "resume %d" % self.resume_tries)

        if state in MENU_LIKE:
            key = (state, r.get("source"))
            n = self.screen_presses.get(key, 0)
            if t - self.last_press_t < cfg["menu_gap_s"]:
                return "settle"
            if n >= cfg["menu_max_presses"]:
                raise Fail("stuck on %s (%s) after %d presses" % (state, r.get("source"), n))
            crop = self.crops.get(r.get("crop") or "")
            seq = (crop or {}).get("press") or self.inp.get(state) or (["START"] if state == "title" else ["A"])
            if r.get("source") == "model" and r.get("model_button") in ("A", "B", "X", "Y", "START"):
                seq = [r["model_button"]]
            self.screen_presses = {key: n + 1}
            return self.press(seq[n % len(seq)], "%s %d" % (state, n + 1))

        if state in ("play", "stalled"):
            if (state == "stalled" and not r.get("recovering") and self.stall_cycles()
                    and self.escapes < cfg["escape_max"]):
                self.start_escape()
                self.last_press_t = self.t()     # the next capture comes at the fast rate
                self.stalled_since = None
                return "stall escape %d" % self.escapes
            self.hold_play()
            if state == "stalled":
                if self.stalled_since is None:
                    self.stalled_since = t
                if t - self.stalled_since >= cfg["stall_fail_s"]:
                    raise Fail("stalled %.0f s: the play HUD is up and nothing moves -- "
                               "the play input is not reaching the game, or a pause the profile cannot see"
                               % (t - self.stalled_since))
                if r.get("recovering"):     # moving again after a stall: play's inputs, not yet play
                    return "hold (recovering, stalled %.0f s)%s" % (t - self.stalled_since, self.play_taps(t))
                return "hold (stalled %.0f s)" % (t - self.stalled_since)
            self.last_play_luma = r["luma"]
            if self.play_since is None:
                self.play_since = t
            if cfg["escape_reset_s"] and self.escapes and t - self.play_since >= cfg["escape_reset_s"]:
                # Sustained play since the last escape: the player got past
                # whatever stalled it, so the next obstacle gets a fresh budget.
                self.escapes = 0
                self.mode_escapes = {}
                act_reset = " (escape budget reset)"
            else:
                act_reset = ""
            return "hold" + self.play_taps(t) + act_reset

        # unknown
        if self.unknown_since is None:
            self.unknown_since = t
        if t - self.unknown_since >= cfg["unknown_fail_s"]:
            raise Fail("unknown screen for %.0f s (%s)" % (t - self.unknown_since,
                                                             "model unavailable" if not os.environ.get("ANTHROPIC_API_KEY")
                                                             else "%d model calls" % self.model_calls))
        return "wait (unknown)"

    def interval(self):
        cfg = self.cfg
        if self.find or self.state != "play" or self.play_since is None:
            return cfg["fast_s"]
        if self.t() - self.play_since < cfg["confirm_play_s"] or self.t() - self.last_press_t < cfg["fast_s"]:
            return cfg["fast_s"]
        return cfg["slow_s"]

    def run(self):
        self.t0 = now()
        self.dev.logcat("drive start %s %s" % (self.p.get("name", "?"), "find" if self.find else "play"))
        tmpdir = tempfile.mkdtemp(prefix="drive-")
        cap_fail_since = None
        try:
            while self.t() < self.seconds:
                self.n += 1
                cur = os.path.join(tmpdir, "cap%d.png" % (self.n % 2))
                ok, cap_s = self.dev.capture(cur)
                self.cap_t = self.t()        # the row's time: a stall escape acts for seconds after it
                if not ok:
                    if self.sim:
                        break
                    if cap_fail_since is None:
                        cap_fail_since = self.t()
                    self.tsv.write("%.1f\t-\tscreencap-failed\t\t\t%.2f\t\t\n" % (self.t(), cap_s))
                    if self.t() - cap_fail_since >= self.cfg["screencap_fail_s"]:
                        self.result = "ROUTE FAIL drive %s: screencap failed for %.0f s" % (
                            self.p.get("name"), self.t() - cap_fail_since)
                        return 1
                    self.sleep(1.0)
                    continue
                cap_fail_since = None
                r = self.classify(cur)
                st = r["state"]
                self.sources[r["source"].split(":")[0]] = self.sources.get(r["source"].split(":")[0], 0) + 1
                changed = st != self.state
                if changed:
                    self.enter(st, r, cur)
                kept = ""
                try:
                    action = self.act(st, r, cur)
                except Fail as e:
                    kept = self.keep(cur, "fail-" + st)
                    self.row(r, cap_s, "ROUTE FAIL", kept)
                    self.result = "ROUTE FAIL drive %s: %s: %s" % (self.p.get("name"), st, e)
                    return 1
                if st == "play" and self.play_since is not None:
                    if self.find:
                        kept = self.keep(cur, "play")
                        self.play_frames.append(kept)
                        if self.t() - self.play_since >= self.cfg["find_play_s"]:
                            self.row(r, cap_s, action, kept)
                            self.result = "reached-play"
                            return 0
                    elif self.mark and not self.marked and self.t() - self.play_since >= self.cfg["confirm_play_s"]:
                        self.dev.logcat("mark gameplay")
                        self.marked = True
                        action += " mark gameplay"
                        kept = self.keep(cur, "gameplay")
                if not kept and (changed or (st == "play" and self.t() - self.last_keep >= self.cfg["keep_every_s"])):
                    kept = self.keep(cur, st)
                    self.last_keep = self.t()
                self.row(r, cap_s, action, kept)
                self.prev_path(cur, tmpdir)
                self.sleep(self.interval())
            self.result = "window-done"
            return 0
        finally:
            self.release_play()
            self.finish()
            shutil.rmtree(tmpdir, ignore_errors=True)

    def prev_path(self, cur, tmpdir):
        keep = os.path.join(tmpdir, "prev.png")
        shutil.copyfile(cur, keep)
        self.prev = keep

    def sleep(self, s):
        if self.sim:
            self.clock_sim += s
            self.dev.clock = self.clock_sim
        else:
            time.sleep(s)

    def row(self, r, cap_s, action, kept):
        src = r["source"] + ("" if r.get("progress") is None else " p=%s" % r["progress"])
        self.tsv.write("%.1f\t%s\t%s\t%s\t%s\t%.2f\t%s\t%s\t%s\n" % (
            self.cap_t, r["state"], src, "" if r.get("changed") is None else r["changed"],
            r.get("luma", ""), cap_s, action, kept, self.mode or ""))
        self.tsv.flush()

    def finish(self):
        t = self.t()
        res = self.result or "stopped"
        self.dev.logcat("state=end t=%d" % int(t))
        if self.ladder and self.ladder.get("gave_up"):
            self.skips.append(dict(state=self.ladder["state"], button=None,
                                   waited_s=round(t - self.ladder["since"], 1), landed=None, presses=self.ladder["presses"]))
        for k in ("title", "play"):
            self.tsv.write("# time_to_%s_s=%s\n" % (k, self.time_to.get(k, "")))
        self.tsv.write("# result=%s\n" % res)
        self.tsv.close()
        sol = dict(profile=self.p.get("name"), title=self.p.get("title"), mode="find" if self.find else "play",
                   result=res, seconds=round(t, 1), time_to_title_s=self.time_to.get("title"),
                   time_to_play_s=self.time_to.get("play"), states_seen=self.seen, skips=self.skips,
                   inputs=self.inputs, anomalies=self.anomalies, classifier_sources=self.sources,
                   model_calls=self.model_calls, play_stretch_frames=self.play_frames,
                   written_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        tmp = os.path.join(self.out, ".route-solution.json.tmp")
        with open(tmp, "w") as f:
            json.dump(sol, f, indent=1)
        os.replace(tmp, os.path.join(self.out, "route-solution.json"))
        print("drive: %s after %.0f s; title at %s s, play at %s s; %d inputs, %d skips, %d model calls"
              % (res, t, self.time_to.get("title"), self.time_to.get("play"), len(self.inputs),
                 len(self.skips), self.model_calls))


class Fail(Exception):
    pass


def learn(path):
    """The profile's [skip.<state>] tables from a route-solution.json."""
    sol = json.load(open(path))
    out = []
    # One table per state (a state is visited more than once: Castlevania has
    # three cutscenes). The button that landed most often wins; `none` only
    # if no press ever landed -- a visit that ended on its own before the
    # settle allowed a press (a logo cut short by a fade) says nothing.
    by = {}
    for s in sol.get("skips", []):
        by.setdefault(s["state"], []).append(s)
    for st, visits in by.items():
        won = [v for v in visits if v.get("button")]
        out.append("[skip.%s]   # %s, %d visit(s)" % (st, sol.get("written_utc", ""), len(visits)))
        if won:
            b = max({v["button"] for v in won}, key=lambda x: sum(v["button"] == x for v in won))
            hits = [v for v in won if v["button"] == b]
            out.append('button = "%s"\nafter_s = %s\nlanded = "%s"\nlanded_times = %d'
                       % (b, max(v["after_s"] for v in hits), hits[0]["landed"], len(hits)))
        elif any(v.get("presses") for v in visits):
            out.append('button = "none"\nwaited_s = %s   # skip: none after the ladder'
                       % max(v.get("waited_s") or 0 for v in visits))
        else:
            out.pop()
    print("\n".join(out))


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "learn":
        learn(argv[1])
        return 0
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--profile", required=True)
    ap.add_argument("--seconds", type=float, default=600)
    ap.add_argument("--find", action="store_true")
    ap.add_argument("--mark", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames")
    ap.add_argument("--sim", help="frames dir, or @file listing frames: replay them instead of a device")
    ap.add_argument("--sim-step", type=float, default=None, help="seconds between sim frames (default fast_s)")
    a = ap.parse_args(argv)
    profile = classify.load_profile(a.profile)
    frames_dir = a.frames or os.path.join(a.out, "route-frames")
    if a.sim:
        if a.sim.startswith("@"):
            fl = [l.strip() for l in open(a.sim[1:]) if l.strip() and not l.startswith("#")]
        else:
            fl = sorted(os.path.join(a.sim, f) for f in os.listdir(a.sim) if f.endswith(".png"))
        dev = SimDevice(fl, a.sim_step)
    else:
        serial = os.environ.get("SERIAL")
        if not serial:
            print("drive.py: SERIAL is required", file=sys.stderr)
            return 2
        dev = Device(serial)
    d = Driver(dev, profile, a.out, frames_dir, a.seconds, find=a.find, mark=a.mark, sim=bool(a.sim))
    if a.sim and a.sim_step:
        d.cfg["fast_s"] = d.cfg["slow_s"] = a.sim_step

    def term(*_):
        d.result = d.result or "terminated"
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, term)
    rc = d.run()
    if d.result and d.result.startswith("ROUTE FAIL"):
        print(d.result)
    if a.sim:
        with open(os.path.join(a.out, "sim-inputs.txt"), "w") as f:
            for s in dev.sent:
                f.write(" ".join(str(x) for x in s) + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
