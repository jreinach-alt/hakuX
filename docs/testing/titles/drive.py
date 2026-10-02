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
  paused                 input.paused (the resume button), then re-classify;
                         still paused after 3 presses is ROUTE FAIL.
  play                   the profile's play_hold axes held (re-asserted each
                         capture), play_tap buttons every N s. NEVER START:
                         the profile is refused if a play input is START.
  stalled                HUD up, nothing moving: keep the play input held;
                         `stall_fail_s` of it is ROUTE FAIL "the play input is
                         not reaching the game" (Forza at 0 MPH).
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
    model_calls_max=20, find_play_s=20.0, confirm_play_s=6.0, keep_every_s=30.0,
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
        self.tsv.write("t\tstate\tsource\tchanged\tluma\tcap_s\taction\tframe\n")
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

    # -- bookkeeping -------------------------------------------------------
    def check_profile(self):
        for b, _ in self.inp.get("play_tap", []):
            if b in ("START", "SELECT", "BACK"):
                raise SystemExit("drive.py: profile play_tap sends %s: START in live play pauses it" % b)
        for k, v in self.inp.items():
            if k.startswith("play"):
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
        else:
            self.dev.pad("press", btn)
        self.last_press_t = t
        self.inputs.append(dict(t=round(t, 1), state=self.state, input=btn, why=why))
        return "press %s (%s)" % (btn, why)

    def hold_play(self):
        want = [tuple(x) for x in self.inp.get("play_hold", [])]
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
        if r["state"] == "unknown":
            self.unknown_streak += 1
            if self.unknown_streak >= self.cfg["unknown_before_model"]:
                m = self.ask_model(frame)
                if m and m["state"]:
                    r.update(state=m["state"], source="model", model_button=m["button"])
        else:
            self.unknown_streak = 0
        return r

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
            return self.press((self.inp.get("paused") or ["START"])[0], "resume %d" % self.resume_tries)

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
            self.hold_play()
            if state == "stalled":
                if self.stalled_since is None:
                    self.stalled_since = t
                if t - self.stalled_since >= cfg["stall_fail_s"]:
                    raise Fail("stalled %.0f s: the play HUD is up and nothing moves -- "
                               "the play input is not reaching the game, or a pause the profile cannot see"
                               % (t - self.stalled_since))
                return "hold (stalled %.0f s)" % (t - self.stalled_since)
            self.last_play_luma = r["luma"]
            if self.play_since is None:
                self.play_since = t
            act = "hold"
            for b, every in self.inp.get("play_tap", []):
                last = getattr(self, "_tap_" + b, -1e9)
                if t - last >= every:
                    setattr(self, "_tap_" + b, t)
                    self.dev.pad("press", b)
                    act += " tap %s" % b
            return act

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
        try:
            while self.t() < self.seconds:
                self.n += 1
                cur = os.path.join(tmpdir, "cap%d.png" % (self.n % 2))
                ok, cap_s = self.dev.capture(cur)
                if not ok:
                    if self.sim:
                        break
                    self.tsv.write("%.1f\t-\tscreencap-failed\t\t\t%.2f\t\t\n" % (self.t(), cap_s))
                    self.sleep(1.0)
                    continue
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
        self.tsv.write("%.1f\t%s\t%s\t%s\t%s\t%.2f\t%s\t%s\n" % (
            self.t(), r["state"], r["source"], "" if r.get("changed") is None else r["changed"],
            r.get("luma", ""), cap_s, action, kept))
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
    for s in sol.get("skips", []):
        out.append("[skip.%s]   # %s" % (s["state"], sol.get("written_utc", "")))
        if s.get("button"):
            out.append('button = "%s"\nafter_s = %s\nlanded = "%s"' % (s["button"], s["after_s"], s["landed"]))
        else:
            out.append('button = "none"\nwaited_s = %s   # skip: none after the ladder' % s.get("waited_s"))
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
