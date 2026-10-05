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

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="pathfind-selftest-")
os.environ["PATHFIND_DRY"] = "1"
os.environ["PATHFIND_KNOW"] = os.path.join(TMP, "know")
os.environ["PATHFIND_AFTER_S"] = "0"
os.makedirs(os.path.join(TMP, "know", "hints"))
sys.path.insert(0, HERE)
import pathfind  # noqa: E402

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

# hold stuck: the screen stays a pause and START never gets back to play: the hold gives up after the nav cap
rc, res, steps, calls = run("holdstuck", PREFIX + [("menu", 0)] * 30,
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}, GENRE]
                            + [PAUSED] * 16, ["--no-record", "--no-replay", "--hold-s", "200", "--budget-min", "60"])
hold = res.get("hold", {})
check("holdstuck", res["result"] == "gameplay" and hold.get("ok") is False and "off play" in hold.get("reason", ""),
      f"the claim stands but the hold gives up: {hold.get('reason', '')[:80]}")
check("holdstuck", sum(1 for c in calls if c["purpose"] == "hold-check") <= pathfind.HOLD_NAV_MAX + 1,
      "no more than the nav cap of model steps")

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
check("titlehold", all(a in (walk, ["X"]) for a in acts), f"every other cycle is the walk: {acts[:6]}")

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

shutil.rmtree(TMP)
print("pathfind_selftest: " + ("FAIL " + ", ".join(sorted(set(fails))) if fails else "all ok"))
sys.exit(1 if fails else 0)
