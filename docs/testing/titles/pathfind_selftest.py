#!/usr/bin/env python3
"""pathfind.py with no device and no model: frames from a directory, model
answers canned (PATHFIND_DRY). Each case names the defect it would catch.

  happy     black -> logo -> menu -> gameplay, probe moves, confirm says yes:
            result gameplay, a path written, black frames cost no model call.
  menu60    the model calls a menu gameplay and the probe frame does not
            change (the old pipeline's false pass, CAPA T6): NOT confirmed,
            and no confirm call is spent on it.
  refused   the probe frame changes but the confirm model says no: NOT
            confirmed.
  repeat    the same input on an unchanged screen: the 4th is overridden,
            and from the 3rd look the stronger model is asked.
  cycle     two screens alternating, the same input on each (Midnight Club 3's
            Yes/No dialog, 10-02): the stronger model is asked once the dialog
            comes back, and the dialog's input is overridden by the 5th visit.
  replay    a second run of the same title with the recorded path replays
            the logo and menu steps with no model call (2 calls, not 4).
  cinema    a letterboxed scene that moves under the probe and that the
            confirm model calls gameplay (Bruce Lee's intro cinematic, 10-02):
            NOT confirmed, refused before any confirm call.
  ownmotion the scene moves on its own (no-input change over SELF_MOVING):
            the confirm call gets the left/right steering frames (4 images),
            and its "did not follow" refusal is honoured.
  retract   confirmed, but the frame 30 s on is a title screen (the
            recheck says no): the claim is retracted, result not gameplay.
  plan      the model answers a plan for the next two menus (from a guide):
            they are sent with no model call while each input changes the
            screen (3 calls, not 5); a plan never crosses into gameplay; a
            planned input that leaves the screen unchanged drops the rest.
  blackhang a screen black for longer than BLACK_HANG_S ends the run as
            black-hang (Conker, 10-02: 8+ min of black after a level load).
  hold      --hold-s 200 after the claim, on a fake clock: 200 s of play judged
            from moving frames, a pause read by the model (START back to
            play), 3-6 model reads in all, a kept frame every 30 s, and the
            logcat marks title_verdict reads (mark gameplay, soak start, a
            state line per change of play, soak end).
  holdstuck the pause never clears: the hold gives up at the nav cap, and the
            claim itself still stands.
  holdrepeat a cutscene that asks for A is answered once; its A repeats HOLD_REPEAT times with no model read,
            then the screen is read again and play resumes.
  holdstill the model reads play, but two kept frames 30 s apart barely differ: the window is state=still (not
            play), the loop is led by an unlock button, and play is credited again once the scene moves.
  rounds    an ambiguous probe (the scene moves on its own, under SELF_MOVING) takes two more idle/input rounds;
            2 of 3 won goes to the model, none won is refused before it.
  holdshed  play drops into a menu right after a loop cycle: the loop sheds B (HOLD_SHED) for the rest of the hold.
  unlock    two probes in a row move nothing at all; the third is led by X
            (UNLOCK_LADDER; Black Stone, 10-03: a stance only X released).
  actions   clean_action keeps valid tokens and drops the rest (RSTICK too).
"""

import json
import os
import shutil
import sys
import tempfile
import types

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="pathfind-selftest-")
os.environ["PATHFIND_DRY"] = "1"
os.environ["PATHFIND_KNOW"] = os.path.join(TMP, "know")
os.environ["PATHFIND_AFTER_S"] = "0"
os.makedirs(os.path.join(TMP, "know", "hints"))
sys.path.insert(0, HERE)
import pathfind  # noqa: E402
# The fake device has no logcat for title_verdict.py, so the validity check would find no verdict and hold on. The
# existing hold legs test the loop, so their check passes; the validity rule itself is tested by the 'validity' legs
# below (hold_shortfall on fake verdicts), and on the device by every held run's validity lines in hold.jsonl.
pathfind.Agent.hold_check = lambda self, play_s, log: ("pass", 0.0, "")
# the selftest's claim budgets are seconds long and run on real time: a 300-s confirm grace would let every
# budget-ended case wait out its sim. The grace is a production setting; its path is the next real claim's test.
pathfind.CONFIRM_GRACE_S = 0

# the escalation cases need a stronger model than FAST; the default is Sonnet for both today (10-03), so pin Opus
pathfind.STRONG = "claude-opus-5-5"
pathfind.time.sleep = lambda s: None
fails = []


def frame(path, kind, shift=0):
    im = Image.new("RGB", (1280, 960), (0, 0, 0))
    d = ImageDraw.Draw(im)
    if kind == "logo":
        d.ellipse((440, 280, 840, 680), fill=(30, 200, 60))
    elif kind == "menu":
        im.paste((40, 40, 120), (0, 0, 1280, 960))
        for i in range(4):
            d.rectangle((400, 250 + i * 120, 880, 330 + i * 120), fill=(200, 200, 200) if i else (250, 220, 0))
    elif kind == "menu2":
        im.paste((120, 30, 30), (0, 0, 1280, 960))
        for i in range(3):
            d.ellipse((300 + i * 260, 380, 500 + i * 260, 580), fill=(230, 230, 230))
    elif kind == "game":
        im.paste((90, 140, 60), (0, 0, 1280, 960))
        for x in range(0, 1280, 160):
            d.rectangle((x + shift, 400, x + shift + 60, 960), fill=(120, 80, 40))
        d.rectangle((560, 600, 720, 900), fill=(220, 30, 30))
    elif kind in ("dark", "darkpatch"):
        # a dark dungeon: a 10-40 grey gradient (std ~9), and for "darkpatch" an 80x80 patch 12 levels brighter
        for x in range(1280):
            v = 10 + int(30 * x / 1280)
            d.line((x, 0, x, 960), fill=(v, v + 6, v))
        if kind == "darkpatch":
            for x in range(400, 480):
                v = 10 + int(30 * x / 1280) + 12
                d.line((x, 400, x, 480), fill=(v, v + 6, v))
    if kind == "cine":
        return frame(path, "game", shift) or _bars(path)
    im.save(path)


def _bars(path):
    im = Image.open(path)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1280, 140), fill=(0, 0, 0))
    d.rectangle((0, 820, 1280, 960), fill=(0, 0, 0))
    im.save(path)


def run(name, frames, answers, extra=()):
    fd = os.path.join(TMP, name, "in")
    os.makedirs(fd)
    for i, (kind, shift) in enumerate(frames):
        frame(os.path.join(fd, f"{i:03d}.png"), kind, shift)
    ans = os.path.join(TMP, name, "answers.json")
    json.dump(answers, open(ans, "w"))
    out = os.path.join(TMP, name, "out")
    rc = pathfind.main(["00000000", "--device", "nova", "--budget-min", "0.05", "--out", out, "--sim", fd,
                        "--sim-answers", ans] + list(extra))
    res = json.load(open(os.path.join(out, "result.json")))
    steps = [json.loads(l) for l in open(os.path.join(out, "steps.jsonl"))]
    calls = [json.loads(l) for l in open(os.path.join(out, "calls.jsonl"))] if os.path.exists(
        os.path.join(out, "calls.jsonl")) else []
    return rc, res, steps, calls


def check(case, cond, why):
    print(("ok   " if cond else "FAIL ") + f"{case}: {why}")
    if not cond:
        fails.append(case)


GAME = {"state": "gameplay", "why": "HUD, player on a field", "action": [], "wait_s": 1, "probe": "STICK:up:1.5"}

# happy: 2 black, logo, menu, gameplay look, probe a/b (same), probe c (shifted), after frames
rc, res, steps, calls = run("happy", [("black", 0), ("black", 0), ("logo", 0), ("menu", 0), ("game", 0),
                                      ("game", 0), ("game", 0), ("game", 80), ("game", 80)],
                            [{"state": "publisher_logo", "why": "logo", "action": ["START"], "wait_s": 2},
                             {"state": "main_menu", "why": "menu, cursor on Play", "action": ["A"], "wait_s": 2},
                             GAME,
                             {"gameplay": True, "responded": True, "why": "the field scrolled"}])
check("happy", res["result"] == "gameplay" and rc == 0, f"result {res['result']} rc {rc}")
check("happy", sum(1 for s in steps if s.get("src") == "black") == 2 and len(calls) == 4,
      f"black steps cost no call: {len(calls)} calls")
path = os.path.join(TMP, "know", "paths", "00000000.json")
check("happy", os.path.exists(path), "the path was recorded")
lp = os.path.join(TMP, "know", "hints", "learned-pub-0000.md")
check("happy", os.path.exists(lp) and "(00000000," in open(lp).read() and "main_menu A" in open(lp).read(),
      "one learned line was appended to learned-pub-0000.md")

# repeat: a dialogue the model answered with one A that advanced it: A again unlooked, CLAIM_REPEAT times, then a look
# (Phantom Crash, 10-04: 62 model calls on a ClubWired dialogue)
rc, res, steps, calls = run("dialogue", [("cine", 0), ("cine", 40), ("cine", 80), ("cine", 120), ("cine", 160),
                                         ("cine", 200), ("menu", 0), ("menu", 0)],
                            [{"state": "cutscene", "why": "dialogue box", "action": ["A"], "wait_s": 2},
                             {"state": "cutscene", "why": "dialogue box", "action": ["A"], "wait_s": 2},
                             {"state": "main_menu", "why": "menu", "action": ["A"], "wait_s": 2}], ["--no-record"])
src = [s.get("src") for s in steps]
check("dialogue", src[:6] == ["fast"] + ["repeat"] * 5,
      f"one look, five unlooked repeats (CLAIM_REPEAT_BOX on a letterboxed cutscene), then the next step: {src}")
check("dialogue", all(s.get("action") == ["A"] for s in steps[:6]), "the repeats send the look's own press")

# proberot: a live HUD whose probe input never moves anything (Road Rage's RT, 10-04): the third probe is not RT
check("proberot", [pathfind.probe_key(t) for t in ("RT:1.5", "RT:3", "HOLD:A:3", "STICK:up:2", "RT+left:1.2", "A")]
      == ["RT", "RT", "HOLD:A", "STICK:up", "RT+left", "A"], "probe_key drops the seconds only")
G_RT = dict(GAME, probe="RT:3")
rc, res, steps, calls = run("proberot", [("game", 0)] * 30, [G_RT] * 8, ["--no-record"])
probes = [s["action"][-1] for s in steps if s.get("src") == "probe"]
check("proberot", len(probes) >= 3 and [pathfind.probe_key(p) for p in probes[:2]] == ["RT", "RT"]
      and pathfind.probe_key(probes[2]) == "HOLD:A", f"two RT probes, then the ladder's HOLD:A: {probes}")

# dark: a dark dungeon scene, the probe moves an 80x80 patch by 12 grey levels (under the old fixed 16-level step,
# 0.5% of the frame: refused before any confirm call). Black Stone's sword and spell in the 10-03 gate.
rc, res, steps, calls = run("dark", [("black", 0), ("black", 0), ("dark", 0), ("dark", 0), ("dark", 0),
                                     ("darkpatch", 0), ("darkpatch", 0), ("darkpatch", 0), ("darkpatch", 0)],
                            [GAME, {"gameplay": True, "responded": True, "why": "the character moved in the dungeon"}],
                            ["--no-record"])
check("dark", res["result"] == "gameplay", f"a dark scene's change under input is confirmed ({res['result']})")
check("dark", any(c["purpose"] == "confirm" for c in calls), "the confirm call was made")
ctrl, moved = pathfind.probe_change(os.path.join(TMP, "dark", "in", "003.png"),
                                    os.path.join(TMP, "dark", "in", "004.png"),
                                    os.path.join(TMP, "dark", "in", "005.png"))
check("dark", ctrl < pathfind.PROBE_MOVED and moved >= pathfind.PROBE_MOVED,
      f"the idle pair is still and the input pair clears the floor (control {ctrl:.4f}, under input {moved:.4f})")

# menu60: gameplay claimed on a static menu; the probe frame does not change
rc, res, steps, calls = run("menu60", [("menu", 0)] * 12,
                            [dict(GAME, why="looks like play")] * 3, ["--no-record", "--no-replay"])
check("menu60", res["result"] != "gameplay", f"not confirmed (result {res['result']})")
check("menu60", not any(c["purpose"] == "confirm" for c in calls), "no confirm call on an unchanged probe")

# unlock: two probes move nothing at all; the third is led by X, the first of UNLOCK_LADDER (Black Stone, 10-03)
rc, res, steps, calls = run("unlock", [("game", 0)] * 8 + [("game", 0)] * 3 + [("game", 80)] * 3,
                            [GAME, GAME, GAME, {"gameplay": True, "responded": True, "why": "he ran"}],
                            ["--no-record", "--no-replay", "--budget-min", "1"])
pacts = [s.get("action") for s in steps if s.get("src") == "probe"]
check("unlock", len(pacts) == 3 and pacts[0][0] != "X" and pacts[1][0] != "X" and pacts[2][0] == "X",
      f"the third probe, after two dead ones, is led by X: {pacts}")
check("unlock", res["result"] == "gameplay", f"result {res['result']}")

# refused: the probe moves but the confirm model says it is a demo
rc, res, steps, calls = run("refused", [("game", 0), ("game", 0), ("game", 0), ("game", 80)] + [("game", 0)] * 4,
                            [GAME, {"gameplay": False, "responded": False, "why": "attract demo"}],
                            ["--no-record", "--no-replay"])
check("refused", res["result"] != "gameplay", f"a refused confirm is not gameplay ({res['result']})")

# repeat: the model keeps answering A on an unchanged menu
rc, res, steps, calls = run("repeat", [("menu", 0)] * 8,
                            [{"state": "main_menu", "why": "menu", "action": ["A"], "wait_s": 1}] * 8,
                            ["--no-record", "--no-replay"])
acts = [" ".join(s.get("action", [])) for s in steps if s.get("src") in ("fast", "strong")]
check("repeat", acts[:3] == ["A", "A", "A"] and acts[3] != "A", f"4th repeat overridden: {acts[:5]}")
models = [c["model"] for c in calls]
check("repeat", models[2] == pathfind.STRONG, f"stronger model from the 3rd look: {models[:4]}")

# cycle: dialog (menu) <-> garage (logo), "UP A" on the dialog and "A" on the garage, forever
rc, res, steps, calls = run("cycle", [("menu", 0), ("logo", 0)] * 6,
                            [{"state": "submenu", "why": "Yes/No dialog", "action": ["UP", "A"], "wait_s": 1},
                             {"state": "submenu", "why": "garage", "action": ["A"], "wait_s": 1}] * 6,
                            ["--no-record", "--no-replay", "--budget-min", "0.3"])
dlg = [(s.get("src"), " ".join(s.get("action", []))) for s in steps if s.get("src") in ("fast", "strong")][0::2]
check("cycle", dlg[2][0] == "strong", f"stronger model on the 3rd dialog visit: {dlg[:5]}")
check("cycle", any(a != "UP A" for _, a in dlg[:5]), f"the dialog input is overridden by the 5th visit: {dlg[:5]}")

# replay: the recorded path from `happy` replays the menu step without a call
rc, res, steps, calls = run("replay", [("logo", 0), ("menu", 0), ("game", 0), ("game", 0), ("game", 0),
                                       ("game", 80), ("game", 80)],
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}], ["--no-record"])
check("replay", res["result"] == "gameplay" and res["replayed"] == 2 and len(calls) == 2,
      f"result {res['result']}, replayed {res['replayed']}, calls {len(calls)}")

# cinema: letterboxed, moves under the probe, confirm model would say yes
rc, res, steps, calls = run("cinema", [("cine", 0), ("cine", 0), ("cine", 0), ("cine", 120)] + [("cine", 0)] * 4,
                            [GAME, {"gameplay": True, "responded": True, "why": "he walked"}],
                            ["--no-record", "--no-replay"])
check("cinema", res["result"] != "gameplay" and not any(c["purpose"] == "confirm" for c in calls),
      f"letterboxed scene refused before a confirm call ({res['result']})")

# ownmotion: the scene moves as much with no input as under it
rc, res, steps, calls = run("ownmotion", [("game", 0), ("game", 0), ("game", 80), ("game", 160)] + [("game", 0)] * 4,
                            [GAME, {"gameplay": True, "responded": False, "why": "did not steer"}],
                            ["--no-record", "--no-replay"])
conf = [c for c in calls if c["purpose"] == "confirm"]
check("ownmotion", res["result"] != "gameplay" and conf and conf[0]["images"] == 4,
      f"self-moving scene gets the steering test and its refusal holds ({res['result']}, "
      f"{[c['images'] for c in conf]})")

# rounds: the first probe is ambiguous (the scene moved 5 px on its own, nothing more under the input), then two more
# idle/input rounds where the input clearly wins: 2 of 3 won, the model is asked with the clearest round, gameplay.
ROUNDS = [("game", 0), ("game", 0), ("game", 5), ("game", 5),          # decide; a b c: idle 5 px, input none
          ("game", 5), ("game", 5), ("game", 85),                        # round 2: idle none, input 80 px
          ("game", 85), ("game", 85), ("game", 5)] + [("game", 5)] * 4    # round 3: idle none, input 80 px
rc, res, steps, calls = run("rounds", ROUNDS, [GAME, {"gameplay": True, "responded": True, "why": "moved"}],
                            ["--no-record", "--no-replay"])
pr = [s for s in steps if s.get("src") == "probe"]
check("rounds", bool(res["result"] == "gameplay" and pr and len(pr[0].get("rounds", [])) == 3
                     and ("2 of 3" in pr[0]["why"] or "3 of 3" in pr[0]["why"])),
      f"an ambiguous probe takes two more rounds and 2 of 3 wins: {res['result']}, "
      f"{pr[0].get('rounds') if pr else None}, {pr[0]['why'] if pr else None}")
# rounds refused: the scene moves on its own as much under the input in every round: no model call, refused
NOWIN = [("game", 0), ("game", 0), ("game", 5), ("game", 5), ("game", 10), ("game", 15), ("game", 15),
         ("game", 20), ("game", 25), ("game", 25)] + [("game", 25)] * 2
rc, res, steps, calls = run("roundsno", NOWIN, [GAME, {"gameplay": True, "responded": True, "why": "moved"}],
                            ["--no-record", "--no-replay", "--budget-min", "0.05"])
pr = [s for s in steps if s.get("src") == "probe"]
check("rounds", pr and len(pr[0].get("rounds", [])) == 3 and pr[0].get("verdict", "").startswith("no change")
      and not any(c["purpose"] == "confirm" for c in calls),
      f"rounds that never beat the idle change are refused before the model: "
      f"{pr[0].get('rounds') if pr else None}, {pr[0].get('verdict') if pr else None}")

# ownmotion with a throttle probe: the steering legs keep the throttle on (Forza, 10-03: gas-off steering legs put a
# slow car into the pit wall in both runs)
rc, res, steps, calls = run("ownrt", [("game", 0), ("game", 0), ("game", 80), ("game", 160)] + [("game", 0)] * 4,
                            [dict(GAME, probe="RT:1.5"), {"gameplay": True, "responded": False, "why": "no"}],
                            ["--no-record", "--no-replay"])
pr = [s for s in steps if s.get("src") == "probe"]
check("ownmotion", pr and pr[0]["action"][-2:] == ["RT+left:1.2", "RT+right:1.2"],
      f"a throttle probe steers on the throttle: {pr[0]['action'] if pr else None}")

# retract: confirmed, then the recheck 30 s on says it is a title screen
os.environ["PATHFIND_AFTER_S"] = "0.05"
rc, res, steps, calls = run("retract", [("game", 0), ("game", 0), ("game", 0), ("game", 80), ("logo", 0)] + [("logo", 0)] * 4,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"},
                             {"gameplay": False, "why": "title screen"}], ["--no-record", "--no-replay"])
os.environ["PATHFIND_AFTER_S"] = "0"
check("retract", res["result"] != "gameplay" and res.get("retracted") == 1,
      f"claim retracted ({res['result']}, retracted {res.get('retracted')})")

# siblings: same publisher and a shared distinctive word, with no series hint file
pd = os.path.join(TMP, "know", "paths")
for t, n in (("53450031", "ESPN NBA 2K5"), ("53450002", "Sonic Heroes"), ("4D530013", "ESPN Fake Other Pub")):
    json.dump({"title_id": t, "name": n, "steps": []}, open(os.path.join(pd, t + ".json"), "w"))
own, sibs = pathfind.load_paths("53450030", "ESPN NFL 2K5")
check("siblings", own is None and [d["title_id"] for d in sibs] == ["53450031"],
      f"ESPN NBA 2K5 is ESPN NFL 2K5's sibling, Sonic and another publisher's ESPN are not: {[d['title_id'] for d in sibs]}")

# plan: logo (model, plans 2 menus) -> menu (plan) -> menu2 (plan) -> game (model) -> confirm
rc, res, steps, calls = run("plan", [("logo", 0), ("menu", 0), ("menu2", 0), ("game", 0), ("game", 0), ("game", 0),
                                     ("game", 80), ("game", 80)],
                            [{"state": "publisher_logo", "why": "logo", "action": ["START"], "wait_s": 2,
                              "plan": [{"expect": "main_menu", "action": ["A"], "wait_s": 2},
                                       {"expect": "submenu", "action": ["DOWN", "A"], "wait_s": 2},
                                       {"expect": "gameplay", "action": ["A"], "wait_s": 2}]},
                             GAME, {"gameplay": True, "responded": True, "why": "moved"}],
                            ["--no-record", "--no-replay"])
srcs = [s.get("src") for s in steps]
check("plan", res["result"] == "gameplay" and srcs.count("plan") == 2 and len(calls) == 3,
      f"two planned menus sent with no call, the gameplay step dropped from the plan: {srcs}, {len(calls)} calls")

# plan dropped: the first planned input leaves the screen unchanged, so the rest goes back to the model
rc, res, steps, calls = run("plandrop", [("logo", 0), ("menu", 0), ("menu", 0)] + [("menu", 0)] * 4,
                            [{"state": "publisher_logo", "why": "logo", "action": ["START"], "wait_s": 2,
                              "plan": [{"expect": "main_menu", "action": ["A"], "wait_s": 2},
                                       {"expect": "submenu", "action": ["A"], "wait_s": 2}]},
                             {"state": "main_menu", "why": "menu", "action": ["DOWN"], "wait_s": 1}] * 1,
                            ["--no-record", "--no-replay"])
srcs = [s.get("src") for s in steps]
check("plan", srcs[:3] == ["fast", "plan", "fast"], f"an input that changed nothing drops the plan: {srcs[:4]}")

# blackhang: black for longer than BLACK_HANG_S ends the run as black-hang, not a 15-min budget
pathfind.BLACK_HANG_S = 1.0
rc, res, steps, calls = run("blackhang", [("black", 0)] * 3, [], ["--no-record", "--no-replay", "--budget-min", "0.2"])
pathfind.BLACK_HANG_S = 180.0
check("blackhang", res["result"] == "black-hang", f"a long black screen ends as black-hang ({res['result']})")

# hold: confirmed, then play on a fake clock (200 s of play). Moving frames are play, two identical frames are a
# pause the model reads (START back to play), and the model reads the screen every 90 s. Kept frames every 30 s.
CLOCK = [1000.0]
real_now, real_sleep = pathfind.now, pathfind.time.sleep
pathfind.now = lambda: CLOCK[0]
pathfind.time.sleep = lambda s: CLOCK.__setitem__(0, CLOCK[0] + s)
PREFIX = [("game", 0), ("game", 0), ("game", 0), ("game", 80)]          # the decide look, then the probe a/b/c
# 47 px a frame: never periodic within a run, so two kept frames 30 s apart differ (the position test, HOLD_STILL)
PLAY = [("game", (i * 47) % 160) for i in range(40)]
PLAY2 = [("game", (i * 47 + 20) % 160) for i in range(120)]
PAUSE = [("menu", 0), ("menu", 0)]
GENRE = {"genre": "drive", "why": "a car on a road"}
PAUSED = {"state": "pause", "in_play": False, "why": "pause menu", "action": ["START"], "wait_s": 1}
PLAYING = {"state": "gameplay", "in_play": True, "why": "back in play", "action": [], "wait_s": 1}
ROUTE_LOG = []
pathfind.SimDevice.route_log = lambda self, msg: ROUTE_LOG.append(msg)
rc, res, steps, calls = run("hold", PREFIX + PLAY + PAUSE + PLAY2,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}, GENRE, PAUSED]
                            + [PLAYING] * 6, ["--no-record", "--no-replay", "--hold-s", "200", "--budget-min", "60"])
hold = res.get("hold", {})
look = [json.loads(l) for l in open(os.path.join(TMP, "hold", "out", "hold.jsonl"))]
nchk = sum(1 for c in calls if c["purpose"] == "hold-check")
check("hold", rc == 0 and res["result"] == "gameplay" and hold.get("ok") is True and hold.get("genre") == "drive",
      f"200 s of play held: {hold.get('play_s')} s, genre {hold.get('genre')}, rc {rc}")
check("hold", any(l.get("action") == ["START"] for l in look), "the pause was read and START sent back to play")
check("hold", 3 <= nchk <= 6, f"model read the screen a few times, not every step: {nchk} hold checks")
check("hold", 6 <= hold.get("frames", 0) <= 9 and os.path.exists(os.path.join(TMP, "hold", "out", "hold_strip.jpg")),
      f"a kept frame every 30 s: {hold.get('frames')} kept")
states = [m for m in ROUTE_LOG if m.startswith("state=")]
check("hold", ROUTE_LOG[:2] == ["mark gameplay", "soak start"] and ROUTE_LOG[-1] == "soak end"
      and [m.split()[0] for m in states] == ["state=play", "state=pause", "state=play"],
      f"the perflog marks: mark gameplay, soak start, play/pause/play, soak end: {ROUTE_LOG}")
kept_left = [f for f in os.listdir(os.path.join(TMP, "hold", "out", "frames")) if "hold" in f and f.endswith(".jpg")]
check("hold", len(kept_left) == hold.get("frames"), f"the other hold frames were deleted ({len(kept_left)} left)")

# hold stuck: the screen stays a pause and START never gets back to play. The step cap no longer ends the hold while budget
# remains (10-06 owner order): it runs ladder rounds, and the hold stops only when the ladder has run out and the budget is gone
rc, res, steps, calls = run("holdstuck", PREFIX + [("menu", 0)] * 30,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}, GENRE]
                            + [PAUSED] * 16, ["--no-record", "--no-replay", "--hold-s", "200", "--budget-min", "60"])
hold = res.get("hold", {})
check("holdstuck", res["result"] == "gameplay" and hold.get("ok") is False
      and ("off play" in hold.get("reason", "") or "budget" in hold.get("reason", "")),
      f"the claim stands but the hold gives up at the end of its budget: {hold.get('reason', '')[:80]}")
check("holdstuck", sum(1 for c in calls if c["purpose"] == "hold-check") > pathfind.HOLD_NAV_MAX + 1,
      "the hold runs past the nav cap while budget remains, with ladder rounds, instead of stopping at it")

# holdrepeat: a cutscene that asks for A (an episode card) is answered once; its A is repeated HOLD_REPEAT times
# with no model call, then the screen is read again, and the play resumes (Panzer, 10-03: 4 looks per death)
CUT = {"state": "cutscene", "in_play": False, "why": "episode card", "action": ["A"], "wait_s": 1}
rc, res, steps, calls = run("holdrepeat", PREFIX + PLAY[:6] + [("menu", 0)] * 2 + PLAY2,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}, GENRE, CUT]
                            + [PLAYING] * 6, ["--no-record", "--no-replay", "--hold-s", "60", "--budget-min", "60"])
hold = res.get("hold", {})
look = [json.loads(l) for l in open(os.path.join(TMP, "holdrepeat", "out", "hold.jsonl"))]
reps = [l for l in look if l.get("src") == "repeat"]
nchk = sum(1 for c in calls if c["purpose"] == "hold-check")
check("holdrepeat", len(reps) == pathfind.HOLD_REPEAT and all(l.get("action") == ["A"] for l in reps),
      f"the cutscene's A repeated {len(reps)} times, unlooked: {[l.get('action') for l in reps]}")
check("holdrepeat", nchk <= 2 + 1, f"no model read for the repeats: {nchk} hold checks in all")
check("holdrepeat", hold.get("ok") is True, f"play resumed and held: {hold.get('play_s')} s of play")

# holdstill: the model reads play on every look, but the scene does not move for ~100 s (Black Stone, 10-03: 600 s on
# one octagon, verdict PASS). Still windows are not play: the perflog says state=still, the loop is led by an unlock
# button, and play is credited again only once the kept frames move.
ROUTE_LOG.clear()
rc, res, steps, calls = run("holdstill", PREFIX + [("game", 0)] * 60 + PLAY2,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}, GENRE]
                            + [PLAYING] * 80, ["--no-record", "--no-replay", "--hold-s", "60", "--budget-min", "60"])
hold = res.get("hold", {})
look = [json.loads(l) for l in open(os.path.join(TMP, "holdstill", "out", "hold.jsonl"))]
states = [m.split()[0] for m in ROUTE_LOG if m.startswith("state=")]
check("holdstill", hold.get("still_windows", 0) >= 1 and "state=still" in states and states[-1] == "state=play",
      f"a still window is marked and play resumes once the scene moves: {states}, {hold.get('still_windows')} still")
firsts = [l.get("action", [None])[0] for l in look if l.get("action")]
check("holdstill", "LT+left:3" in firsts and firsts.index("LT+left:3") < firsts.index("X") if "X" in firsts else False,
      f"a still drive window first reverses while turning (HOLD_UNSTICK), then the unlock buttons (X): "
      f"{sorted(set(firsts))}")
still_s = max((l["hold_s"] for l in look if l.get("window") is not None and l["window"] < pathfind.HOLD_STILL),
              default=0)
check("holdstill", hold.get("ok") is True and hold.get("hold_s", 0) >= still_s + 50,
      f"play was not credited while still: held {hold.get('play_s')} s of play over {hold.get('hold_s')} s, "
      f"last still window at {still_s} s")

# holdshed: play drops into a menu right after a loop cycle (ToeJam & Earl III, 10-03: a loop button opened the Presents
# inventory over and over): the loop sheds its first HOLD_SHED button (B) for the rest of the hold
MENUOPEN = {"state": "menu", "in_play": False, "why": "a dialog box is open", "action": ["A"], "wait_s": 1}
rc, res, steps, calls = run("holdshed", PREFIX + PLAY[:6] + [("menu", 0)] * 2 + PLAY2,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"},
                             {"genre": "attack", "why": "a fighter"}, MENUOPEN] + [PLAYING] * 6,
                            ["--no-record", "--no-replay", "--hold-s", "60", "--budget-min", "60"])
hold = res.get("hold", {})
look = [json.loads(l) for l in open(os.path.join(TMP, "holdshed", "out", "hold.jsonl"))]
i = next((k for k, l in enumerate(look) if l.get("shed")), None)
after = [l["action"] for l in look[i + 1:] if l.get("src") == "genre"] if i is not None else []
check("holdshed", hold.get("shed") == ["B"] and after and all("B" not in a and "X" in a for a in after),
      f"the menu-opening drop shed B from the loop and kept X: shed {hold.get('shed')}, "
      f"{after[:1]}")

# titlehold: a title's own hold (TITLE_HOLD, Black Stone's design, 10-03 addendum) opens with X alone, walks with the left
# stick in long strokes, never sends Y, R1, BACK, START or B, and presses X again after two still windows in a row. The
# genre model is not asked: the title names its loop.
pathfind.TITLE_HOLD["00000000"] = pathfind.TITLE_HOLD["58490004"]
ROUTE_LOG.clear()
rc, res, steps, calls = run("titlehold", PREFIX + [("game", 0)] * 120 + PLAY2,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}] + [PLAYING] * 160,
                            ["--no-record", "--no-replay", "--hold-s", "60", "--budget-min", "60"])
pathfind.TITLE_HOLD.pop("00000000")
hold = res.get("hold", {})
look = [json.loads(l) for l in open(os.path.join(TMP, "titlehold", "out", "hold.jsonl"))]
acts = [l["action"] for l in look if l.get("action")]
flat = [t.upper() for a in acts for t in a]
check("titlehold", hold.get("title_hold") is True and not any(c["purpose"] == "genre" for c in calls),
      f"the title's loop is used and the genre is not asked: {[c['purpose'] for c in calls]}")
check("titlehold", acts[0] == ["X"], f"the hold opens with X alone: {acts[:2]}")
check("titlehold", not any(t in pathfind.TITLE_HOLD_FORBID for t in flat),
      f"no forbidden button in the hold: {sorted(set(flat))}")
check("titlehold", [a for a in acts if "X" in a] == [["X"]] * flat.count("X") and flat.count("X") >= 2,
      f"X is pressed alone again after still windows: {flat.count('X')} presses")
walk = pathfind.TITLE_HOLD["58490004"]["walk"]
# the walk may be turned round (16:08 reverse rule): each walk and move, in either direction
moves = [m + walk for m in pathfind.TITLE_UNSTICK]
moves = moves + [pathfind.flip_walk(a, True) for a in moves] + [pathfind.flip_walk(walk, True)]
check("titlehold", all(a in (walk, ["X"]) or a in moves for a in acts),
      f"every other cycle is the walk or a stand-still move before it: {acts[:6]}")
check("titlehold", any(l.get("unstick") for l in look),
      "two still windows in a row send a stand-still move (the detector fires on a still scene)")

# continue: a CONTINUE countdown in a non-title hold gets START, then A, unlooked (Guilty Gear XX, 10-04: three A presses
# did not continue, and the countdown ran out to GAME OVER). The count restarts once play is back.
CONT = {"state": "continue", "in_play": False, "why": "CONTINUE countdown after a lost round", "action": ["A"], "wait_s": 1}
ROUTE_LOG.clear()
rc, res, steps, calls = run("continue", PREFIX + [("game", 0)] * 120 + PLAY2,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}, {"genre": "attack"}]
                            + [CONT] * 3 + [PLAYING] * 160,
                            ["--no-record", "--no-replay", "--hold-s", "60", "--budget-min", "60"])
look = [json.loads(l) for l in open(os.path.join(TMP, "continue", "out", "hold.jsonl"))]
cont = [l for l in look if l.get("continue")]
check("continue", [l["action"] for l in cont[:3]] == [["START"], ["A"], ["START"]],
      f"the continue looks press START, A, START: {[l.get('action') for l in cont[:3]]}")
check("continue", all(l.get("state") == "continue" for l in cont[:3]) and cont and cont[0]["continue"] == 1,
      f"the continue count is recorded per look: {[l.get('continue') for l in cont[:3]]}")

# sports (10-05 owner rule): a team hold reads the clock and period once before it starts (held["sports"], purpose
# "sports"), and a quarter/period break is its own state: START, then A, unlooked, like a CONTINUE countdown.
PB = {"state": "period_break", "in_play": False, "why": "end of the first quarter, stats card", "action": ["A"], "wait_s": 1}
SPORTS = {"clock": "0:00", "period": "Q1", "human_controlled": True, "why": "Q1 clock, a controller under the home team"}
ROUTE_LOG.clear()
rc, res, steps, calls = run("sports", PREFIX + [("game", 0)] * 120 + PLAY2,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}, {"genre": "team"}, SPORTS]
                            + [PB] * 2 + [PLAYING] * 160,
                            ["--no-record", "--no-replay", "--hold-s", "60", "--budget-min", "60"])
hold = res.get("hold", {})
look = [json.loads(l) for l in open(os.path.join(TMP, "sports", "out", "hold.jsonl"))]
sp = hold.get("sports", {})
check("sports", any(c["purpose"] == "sports" for c in calls) and sp.get("human_controlled") is True
      and sp.get("period") == "Q1", f"the team hold reads the clock and period before it starts: {sp}")
pb = [l for l in look if l.get("state") == "period_break"]
check("sports", [l["action"] for l in pb[:2]] == [["START"], ["A"]],
      f"a period break gets START, then A, unlooked: {[l.get('action') for l in pb[:2]]}")
check("sports", "period_break" in pathfind.STATES and "LONGEST" in pathfind.RULES
      and "period_break" in pathfind.RULES,
      "the state list names period_break, and the claim prompt sets the period to the longest value")
# replay (10-05, NHL 2K3 hold2): the hold's look prompt names the instant-replay footer as period_break, not play. The fake
# model cannot read a prompt, so this checks the rule's text and that the look sends it (the frame test is the device run).
import inspect  # noqa: E402
rp = pathfind.HOLD_REPLAY
check("replay", all(w in rp for w in ("Rewind", "Play/Pause", "Back", "period_break", "START"))
      and "HOLD_REPLAY" in inspect.getsource(pathfind.Agent.hold_look),
      "the hold look sends the replay footer rule: a replay is period_break, input START")
# name entry (10-05, Strike Force Bowling hold4): a title's own name sequence is pressed at a name entry in the hold; any
# other title gets START, then A, in turn. The high-score entry at a game end walked the hold off the lanes.
check("nameseq", pathfind.name_press("Strike Force Bowling", 0) == ["DOWN", "DOWN", "DOWN", "DOWN", "A"]
      and pathfind.name_press("Strike_Force_Bowling", 3) == ["DOWN", "DOWN", "DOWN", "DOWN", "A"]
      and pathfind.name_press("NBA 2K3", 0) == ["START"] and pathfind.name_press("NBA 2K3", 1) == ["A"],
      "a title's name sequence is used at a name entry; other titles keep START, then A")
# REMATCH (10-06, Marvel Nemesis, runs/sweep-4541038A and -r2): A on a panel that reads REMATCH highlighted, else one UP (the menu
# wraps); the confirm dialog (which opens on NO) goes DOWN to YES and A; a RETURN confirm gets A (NO cancels). Other menus get no rule.
check("rematch", pathfind.rematch_press("END OF MATCH results: REMATCH highlighted", "results") == ["A"]
      and pathfind.rematch_press("END OF MATCH: RETURN TO CHARACTER SELECT highlighted, REMATCH below", "results") == ["UP"]
      and pathfind.rematch_press("Are you sure you want to REMATCH? NO highlighted", "menu") == ["DOWN", "A"]
      and pathfind.rematch_press("Are you sure you want to RETURN TO CHARACTER SELECT? NO highlighted", "menu") == ["A"]
      and pathfind.rematch_press("pause menu, resume", "pause") is None,
      "REMATCH: A on the highlighted REMATCH row else UP; DOWN and A on the REMATCH confirm; A cancels a RETURN confirm")
# fighting select (10-06, MK Armageddon rehold, rehold2, rehold2b): a grid look plays A, B, START from the first look
check("charsel", pathfind.charsel_press("Character select grid is showing with STRYKER highlighted; not live play.", "menu", 0) == ["A"]
      and pathfind.charsel_press("Character select grid, handicap panel open", "menu", 1) == ["B"]
      and pathfind.charsel_press("Character select grid", "menu", 2) == ["START"]
      and pathfind.charsel_press("Character select grid", "menu", 3) == ["A"]
      and pathfind.charsel_press("Character select grid", "menu", pathfind.CHARSEL_TRIES) is None
      and pathfind.charsel_press("Character select grid", "gameplay", 0) is None
      and pathfind.charsel_press("title screen with PRESS START", "menu", 0) is None
      and pathfind.charsel_press("Fight HUD, round timer 90", "other", 0) is None,
      "the select cycle is A, B, START; a grid look only, not a title, not play, CHARSEL_TRIES presses at most")
# still by the scene's shift for title and fighting holds (10-06, Shaolin Monks: effects in place read as moving on pixels)
check("still-shift", pathfind.still_window(True, 0.2, 0.0) and not pathfind.still_window(True, 0.0, 2.0)
      and pathfind.still_window(False, 0.01, 50.0) and not pathfind.still_window(False, 0.2, 0.0),
      "a title or fighting window is still on the shift (effect in place: still); other genres on the pixel change")
# the reverse rule (16:08 owner order, Blowout's corner): REVERSE_N looks in a row at or under UNCHANGED turn the walk round;
# a moving look resets the count; two flips with no movement between stop flipping (the still unstick takes over)
_lr, _fl, _rv, _flips = 0, False, 0, []
for _ch in [0.2, 0.004, 0.005, 0.006, 0.005, 0.2, 0.003, 0.004, 0.002, 0.001, 0.002, 0.003]:
    _lr, _fl, _rv, _now = pathfind.reverse_trigger(_ch, _lr, _fl, _rv)
    if _now:
        _flips.append(_fl)
_lr, _fl, _rv, _stuck = 0, False, 0, []
for _ch in [0.004] * 9:
    _lr, _fl, _rv, _now = pathfind.reverse_trigger(_ch, _lr, _fl, _rv)
    if _now:
        _stuck.append(_fl)
check("reverse-stop", _stuck == [True, False] and _rv == 2,
      f"nine still looks flip twice then stop: the still unstick takes the hold from there: {_stuck}")
# the patrol backstop (lane.local 17:4x): the shooter walk turns round every PATROL_EVERY play looks, and two turns bring
# the walk back to where it started. A mutant that drops the periodic turn fails the cadence and the round trip.
_due = [n for n in range(1, 13) if pathfind.patrol_due(n)]
_walk = pathfind.HOLD_GENRES["shooter"]
_fl, _seen = False, []
for _n in range(1, 9):
    if pathfind.patrol_due(_n):
        _fl = not _fl
    _seen.append(pathfind.flip_walk(_walk, _fl))
check("patrol", _due == [4, 8, 12] and _seen[3] != _walk and _seen[7] == _walk,
      f"the shooter walk turns at looks {_due}, is reversed at look 4 and back to the start at look 8")
check("reverse-trigger", _flips == [True, False, True]
      and pathfind.flip_walk(["STICK:up:1", "A", "STICK:left:2.5", "RSTICK:right:0.6"], True)
          == ["STICK:down:1", "A", "STICK:right:2.5", "RSTICK:right:0.6"]
      and pathfind.flip_walk(["STICK:up:1", "A"], False) == ["STICK:up:1", "A"],
      f"three still looks flip the walk, a moving look resets, two flips with no movement stop, the stick tokens turn round: {_flips}")
# bowling (10-05, AMF Bowling 2004): a bowl hold loops aim and throw with no B, X or Y, and each frame's scorecard
# (a period_break) gets START, then A, on its own budget (PERIOD_TRIES), not the shared CONTINUE budget.
ROUTE_LOG.clear()
rc, res, steps, calls = run("bowl", PREFIX + [("game", 0)] * 120 + PLAY2,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}, {"genre": "bowl"}]
                            + [PB] * 10 + [PLAYING] * 160,
                            ["--no-record", "--no-replay", "--hold-s", "60", "--budget-min", "60"])
hold = res.get("hold", {})
look = [json.loads(l) for l in open(os.path.join(TMP, "bowl", "out", "hold.jsonl"))]
loop = pathfind.HOLD_GENRES["bowl"]
check("bowl", hold.get("genre") == "bowl" and not any(t in ("B", "X", "Y") for t in loop),
      f"the bowl loop is aim and throw, no B, X or Y: {loop}")
pb = [l for l in look if l.get("state") == "period_break"]
check("bowl", [l.get("action") for l in pb[:2]] == [["START"], ["A"]] and all("continue" not in l for l in pb)
      and [l.get("period") for l in pb[:3]] == [1, 2, 3],
      f"scorecards press START, then A, counted as period looks: {[(l.get('action'), l.get('period')) for l in pb[:3]]}")
check("bowl", any(l.get("action") == loop for l in look) and hold.get("ok") is True,
      f"the hold runs the bowl loop and holds play after the scorecards: ok {hold.get('ok')}")
# name entry (10-05, Strike Force Bowling): a high-score keyboard during a hold gets START, then A, on its own budget
# (NAME_TRIES), and a bowling still window never sends X (the unlock ladder's button that opened the entry).
NE = {"state": "name_entry", "in_play": False, "why": "high-score name entry with a keyboard", "action": ["A"], "wait_s": 1}
ROUTE_LOG.clear()
rc, res, steps, calls = run("nameent", PREFIX + [("game", 0)] * 120 + PLAY2,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}, {"genre": "bowl"}]
                            + [NE] * 8 + [PLAYING] * 160,
                            ["--no-record", "--no-replay", "--hold-s", "60", "--budget-min", "60"])
hold = res.get("hold", {})
look = [json.loads(l) for l in open(os.path.join(TMP, "nameent", "out", "hold.jsonl"))]
ne = [l for l in look if l.get("state") == "name_entry"]
check("nameent", [l.get("action") for l in ne[:2]] == [["START"], ["A"]] and all("continue" not in l for l in ne),
      f"a name entry gets START, then A, unlooked: {[l.get('action') for l in ne[:2]]}")
check("nameent", all("X" not in m for m in sum(pathfind.HOLD_UNSTICK["bowl"], [])),
      f"a bowling still window moves the aim, not X: {pathfind.HOLD_UNSTICK['bowl']}")
pathfind.now, pathfind.time.sleep = real_now, real_sleep

# actions
ca = pathfind.clean_action(["a", "START", "STICK:Up:9", "RT:1.5", "HOLD:A:1", "HOLD:Q:1", "JUMP", "select"])
check("actions", ca == ["A", "START", "STICK:up:4", "RT:1.5", "HOLD:A:1", "BACK"], f"{ca}")
check("actions", pathfind.clean_action("wait") == [], "'wait' is no input")
check("actions", pathfind.clean_action(["RSTICK:Right:0.6", "RSTICK:diag:1", "RSTICK:up:0.5"])
      == ["RSTICK:right:0.6", "RSTICK:up:0.5"], "the right stick takes four directions at full deflection")
check("actions", pathfind.clean_action(["rt+Left:3", "LT+right:9", "RT+upleft:1", "LT+:1"])
      == ["RT+left:3", "LT+right:4"], "a trigger with the stick: RT+<dir> / LT+<dir>, four directions")
SENT = []
pathfind.Agent.send(type("A", (), {"dev": type("D", (), {"pad": lambda self, *a: SENT.append(a)})()})(),
                    ["LT+left:0.2"])
check("actions", SENT[0] == ("axis", "LT", "max") and ("axis", "LX", "min") in SENT
      and SENT[-1] == ("axis", "LT", "min") and ("axis", "LX", "mid") in SENT,
      f"LT+left holds the trigger and the stick together, then releases both: {SENT}")

# fps gate (owner 10-04): the 3- and 5-min "should we continue?" reads of the hold's gfps lines
def _course(vals):
    p = os.path.join(TMP, "gate-logcat.txt")
    with open(p, "w") as f:
        f.writelines(f"10-04 08:06:{i % 60:02d}.139 I/hakuX-perf(1): gfps={v} G:16.7\n" for i, v in enumerate(vals))
    return pathfind.fps_course(p)


ralli = _course([59] * 222 + [34, 35, 38, 45, 45, 49, 51, 52, 54, 58, 60, 60, 60, 60])
check("fpsgate", ralli["share"] == 1.0 and not pathfind.fps_gate_fails(ralli, 22),
      f"RalliSport's 234 s (all >= 30) goes on: {ralli}")
slow = _course([18, 19, 20, 21, 20] * 36)
check("fpsgate", pathfind.fps_gate_fails(slow, 22), f"a steady 20 fps stops at 3 min: {slow}")
near = _course([26, 27, 28, 31, 25] * 60)
check("fpsgate", pathfind.fps_gate_fails(near, 22) is False and pathfind.fps_gate_fails(near, 27) is False,
      f"median 27 (close) is on course at both marks: {near}")
low = _course([24, 25, 26, 31, 25] * 60)
check("fpsgate", not pathfind.fps_gate_fails(low, 22) and pathfind.fps_gate_fails(low, 27),
      f"median 25: on course at 3 min, stops at 5 min: {low}")
mixed = _course([20] * 100 + [40] * 200)
check("fpsgate", not pathfind.fps_gate_fails(mixed, 27), f"a slow start then 40 fps (share 67%) goes on: {mixed}")
locked = _course([29] * 230 + [31] * 190 + [30] * 19 + [28] * 2)
check("fpsgate", locked["share"] > 0.99 and not pathfind.fps_gate_fails(locked, 27),
      f"a locked-30 title reading 29/31 (AvP) is on the verdict's bar (30 x 0.95): {locked}")
check("fpsgate", not pathfind.fps_gate_fails(_course([10] * 10), 22) and _course([])["n"] == 0,
      "under 30 s of gfps lines is no evidence either way")

# teamsport (10-05): a team sport's self-moving confirm judges the marked player; bowling, baseball and racing do not
_ts = lambda goal, name: pathfind.Agent.team_sport(types.SimpleNamespace(goal=goal, name=name))
check("teamsport", _ts("", "NBA 2K3") and _ts("Set the period length to the LONGEST", "NHL 2K3")
      and _ts("", "ESPN College Hoops 2K5") and _ts("On TEAM SELECT: press RIGHT", "Some Title"),
      "NBA/NHL names, a period goal and a team-select goal are team sports")
check("teamsport", not _ts("Set the game length to the LONGEST (10 frames)", "AMF Xtreme Bowling")
      and not _ts("Set innings to the longest", "MLB SlugFest 2004") and not _ts("", "RalliSport Challenge"),
      "bowling, baseball and racing keep the both-ways steering test")

# claim (10-06 owner order): the budget ends on live play with refused probes, so the run enters the hold instead of giving up
# On the fake clock: on real time the hold's budget (claim + 1.75 x hold + 300) is ~11 min of wall time. One confirm refusal
# (the PREFIX probe moves), then every look reads play: a refusal-shaped answer taken by a look reads unknown, not play.
CLOCK = [1000.0]
pathfind.now = lambda: CLOCK[0]
pathfind.time.sleep = lambda s: CLOCK.__setitem__(0, CLOCK[0] + s)
rc, res, steps, calls = run("claimlive", PREFIX + [("game", 0)] * 400,
                            [GAME, {"gameplay": True, "responded": False, "why": "the probe did not move the scene"}]
                            + [GAME] * 600,
                            ["--no-record", "--no-replay", "--hold-s", "200", "--budget-min", "2"])
res_budget = res
# self-moving live play (10-06, NFL Blitz Pro: live football from ~610 s, every probe refused on the moving camera): the
# third live read whose probe was refused on a self-moving scene enters the hold, not the 25-min budget. One answer serves
# the look (state, probe), the confirm (refused), the genre and the hold looks (in_play), so call order cannot shift it.
SELFMOVE = [("game", 0), ("game", 0), ("game", 80), ("game", 160), ("game", 0), ("game", 0)]   # look, a b c, left, right
LIVE = dict(GAME, gameplay=True, responded=False, in_play=True, genre="drive")
rc, res, steps, calls = run("selfmove", SELFMOVE * 4 + [("game", (i * 47) % 160) for i in range(400)], [LIVE] * 300,
                            ["--no-record", "--no-replay", "--hold-s", "200", "--budget-min", "60"])
nprobe = sum(1 for s in steps if s.get("state") == "probe")
check("selfmove", res.get("claim_live_selfmove") == pathfind.LIVE_SELFMOVE_TO_HOLD and res.get("result") == "gameplay"
      and res.get("hold") is not None and nprobe == pathfind.LIVE_SELFMOVE_TO_HOLD and CLOCK[0] - 1000 < 1800,
      f"3 refused self-moving probes of live play enter the hold ({res.get('result')}, {nprobe} probes, "
      f"live {res.get('claim_live_selfmove')}, hold {bool(res.get('hold'))})")
CLOCK[0] = 1000.0
rc, res, steps, calls = run("selfmove0", SELFMOVE * 4 + [("game", 0)] * 40, [LIVE] * 300,
                            ["--no-record", "--no-replay", "--budget-min", "1"])
check("selfmove", res.get("claim_live_selfmove") is None and res.get("result") != "gameplay",
      f"with no --hold-s the refusals stand: no claim ({res.get('result')})")
pathfind.now, pathfind.time.sleep = real_now, real_sleep
res = res_budget
check("claimlive", res.get("claim_budget_live") is True and res.get("result") == "gameplay"
      and res.get("hold") is not None,
      f"the claim budget ran out on live play: the run enters the hold ({res.get('result')}, hold {bool(res.get('hold'))})")
check("claimlive", pathfind.TEAM_CLAIM_EXTRA_S == 600 and pathfind.hold_budget_s(0, 600) == 1050 + 300,
      "a team claim gets 600 s more budget; the hold budget formula is unchanged")

# replay abort (10-06 owner order): a path that no longer matches, past its recorded time to gameplay + 3 min, stops the run
dpath = {"minutes": 4.44, "steps": [{"state": "menu"}]}
check("diverge", pathfind.replay_diverged(dpath, 7.5 * 60 + 1, False) and not pathfind.replay_diverged(dpath, 6 * 60, False)
      and not pathfind.replay_diverged(dpath, 7.5 * 60 + 1, True) and not pathfind.replay_diverged(None, 9999, False)
      and not pathfind.replay_diverged({"minutes": 4.44, "steps": []}, 9999, False),
      "Deadly Alliance (4.44 min recorded): aborts past 7.5 min on a non-matching screen, not before, not on a match, not without a path")

# validity (10-06 owner order): the hold ends on a passing verdict; a shortfall is extended only when more play can fix it
short_dur = {"pass": False, "failing": "duration: 589 s of gameplay < 600 s confirmation", "crash": False, "hang": False,
             "fps_ok_share": 1.0, "gameplay_s": 589, "timeline": {"play_share": 0.99, "play_s": 589, "scored_s": 589}}
kind, s = pathfind.hold_shortfall(short_dur, 600)
check("validity", kind == "duration" and abs(s - 26) < 0.01,
      f"11 s short on duration is extended by 11 + 15 = 26 s: {kind} {s}")
menu94 = {"pass": False, "failing": "menu time: 0.84 of the scored window in play (bar 90%)", "crash": False, "hang": False,
          "fps_ok_share": 1.0, "gameplay_s": 600, "timeline": {"play_share": 0.84, "play_s": 506, "scored_s": 600}}
kind, s = pathfind.hold_shortfall(menu94, 600)
check("validity", kind == "share" and abs(s - 340) < 0.01,
      f"94 s of menu in a 600-s window needs 94 / 0.10 - 600 = 340 s more: {kind} {s}")
fps_fail = {"pass": False, "failing": "fps: 40% of gameplay at >= 28.5 fps (bar 90%)", "crash": False, "hang": False,
            "fps_ok_share": 0.4, "gameplay_s": 600, "timeline": {"play_share": 0.99, "play_s": 600, "scored_s": 600}}
hitch_fail = dict(short_dur, failing="hitch: 3 stalls over 500 ms after warm-up")
check("validity", pathfind.hold_shortfall(fps_fail, 600)[0] == "stop" and pathfind.hold_shortfall(hitch_fail, 600)[0] == "stop"
      and pathfind.hold_shortfall({"pass": True}, 600)[0] == "pass" and pathfind.hold_shortfall(None, 600)[0] == "stop",
      "an fps fail and a hitch stop the hold at once; a pass ends it; no verdict stops it")
# the ladder (10-06): off play past the cap runs its rounds, one press per look, cycling A, START, A, A, B, START
check("ladder", pathfind.HOLD_LADDER[0] == "A" and pathfind.HOLD_LADDER[1] == "START" and "B" in pathfind.HOLD_LADDER
      and pathfind.HOLD_LADDER_ROUNDS >= 1 and pathfind.HOLD_LADDER_ROUNDS * pathfind.HOLD_NAV_MAX >= 60,
      f"A then START on the select, B out of a menu; {pathfind.HOLD_LADDER_ROUNDS} rounds x {pathfind.HOLD_NAV_MAX} steps")
# budget: a 600-s hold with a 15-min claim gets 900 + 1050 + 300 s, not the old 900 + 900 + 300
check("budget", pathfind.hold_budget_s(900, 600) == 900 + 1050 + 300, f"claim + 1.75 x hold + 300: {pathfind.hold_budget_s(900, 600)}")

shutil.rmtree(TMP)
# football goes last (owner order 10-05 12:35): football titles are refused, every other sport is not, and the env lifts it
_fb = [("NFL Blitz Pro", "NFL_Blitz_Pro.xiso.iso"), ("ESPN NFL 2K5", "ESPN_NFL_2K5.iso"), ("Madden NFL 2005", "x.iso"),
       ("NCAA College Football 2K3", "NCAA_College_Football_2K3.xiso.iso")]
_ok = [("NHL Hitz Pro", "NHL_Hitz_Pro.xiso.iso"), ("NBA 2K2", "NBA_2K2.xiso.iso"), ("AMF Bowling 2004", "AMF_Bowling_2004.xiso.iso"),
       ("NCAA March Madness 2005", "NCAA_March_Madness_2005.iso"), ("MLB SlugFest 2003", "MLB_SlugFest_2003.xiso.iso")]
os.environ.pop("PATHFIND_FOOTBALL", None)
check("football", all(pathfind.football_deferred(n, f) for n, f in _fb) and not any(pathfind.football_deferred(n, f) for n, f in _ok),
      "NFL Blitz Pro, NFL 2K5, Madden and NCAA Football are deferred; hockey, basketball, bowling, baseball and March Madness are not")
os.environ["PATHFIND_FOOTBALL"] = "1"
check("football", not any(pathfind.football_deferred(n, f) for n, f in _fb), "PATHFIND_FOOTBALL=1 lifts the deferral")
os.environ.pop("PATHFIND_FOOTBALL", None)
# below the bar (owner order 10-06 16:45): a title whose latest verdict is under 0.9 with no fix is refused in code,
# a committed fix or PATHFIND_BELOW_BAR=1 lifts it, and seeding keeps the cause and fix of a row it already has
_bb = tempfile.mkdtemp(prefix="pf_belowbar_")
_tsv = os.path.join(_bb, "below-bar.tsv")
with open(_tsv, "w") as f:
    f.write("\t".join(pathfind.BELOW_BAR_COLS) + "\n")
    f.write("\t".join(["Dino Crisis 3", "", "0.3793", "runs/dino/verdict.json", "2026-10-04T04:44", "slowdown", ""]) + "\n")
    f.write("\t".join(["Blowout", "4D4A0008", "0.9000", "runs/b/verdict.json", "2026-10-06", "", "abc123"]) + "\n")
    f.write("\t".join(["Tork: Prehistoric Punk", "", "1.0000", "runs/t/verdict.json", "2026-10-05", "", ""]) + "\n")
os.environ.pop("PATHFIND_BELOW_BAR", None)
check("below-bar", pathfind.below_bar_refusal(None, "Dino Crisis 3", _tsv) is not None,
      "a row under 0.9 with no fix refuses its title, and the refusal names the cause")
check("below-bar", pathfind.below_bar_refusal("4D4A0008", "Blowout", _tsv) is None,
      "a fix commit lifts the refusal, and a share at the bar is not below it")
check("below-bar", pathfind.below_bar_refusal(None, "Tork Prehistoric Punk", _tsv) is None,
      "a title whose latest verdict clears the bar is not refused")
check("below-bar", pathfind.below_bar_refusal(None, "Mario Kart", _tsv) is None,
      "a title with no row is not refused")
os.environ["PATHFIND_BELOW_BAR"] = "1"
check("below-bar", pathfind.below_bar_refusal(None, "Dino Crisis 3", _tsv) is None, "PATHFIND_BELOW_BAR=1 lifts it for telemetry")
os.environ.pop("PATHFIND_BELOW_BAR", None)
_runs = os.path.join(_bb, "runs")
for _d, _j, _s in [("old", "2026-10-03T10:00Z", 0.3), ("new", "2026-10-04T10:00Z", 0.95)]:
    os.makedirs(os.path.join(_runs, _d))
    json.dump({"title": "Dino Crisis 3", "fps_ok_share": _s, "judged_utc": _j}, open(os.path.join(_runs, _d, "verdict.json"), "w"))
_seeded = pathfind.seed_below_bar(_runs, _tsv)
check("below-bar", len(_seeded) == 1 and _seeded[0]["fps_ok_share"] == "0.9500" and _seeded[0]["cause"] == "slowdown",
      "seeding keeps the latest verdict per title and the cause already recorded on its row")
shutil.rmtree(_bb)

print("pathfind_selftest: " + ("FAIL " + ", ".join(sorted(set(fails))) if fails else "all ok"))
sys.exit(1 if fails else 0)
