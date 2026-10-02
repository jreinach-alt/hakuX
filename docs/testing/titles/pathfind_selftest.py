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
  replay    a second run of the same title with the recorded path replays
            the logo and menu steps with no model call (2 calls, not 4).
  actions   clean_action keeps valid tokens and drops the rest.
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
    elif kind == "game":
        im.paste((90, 140, 60), (0, 0, 1280, 960))
        for x in range(0, 1280, 160):
            d.rectangle((x + shift, 400, x + shift + 60, 960), fill=(120, 80, 40))
        d.rectangle((560, 600, 720, 900), fill=(220, 30, 30))
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

# menu60: gameplay claimed on a static menu; the probe frame does not change
rc, res, steps, calls = run("menu60", [("menu", 0)] * 12,
                            [dict(GAME, why="looks like play")] * 3, ["--no-record", "--no-replay"])
check("menu60", res["result"] != "gameplay", f"not confirmed (result {res['result']})")
check("menu60", not any(c["purpose"] == "confirm" for c in calls), "no confirm call on an unchanged probe")

# refused: the probe moves but the confirm model says it is a demo
rc, res, steps, calls = run("refused", [("game", 0), ("game", 0), ("game", 0), ("game", 80)] + [("game", 0)] * 4,
                            [GAME, {"gameplay": False, "responded": False, "why": "attract demo"}],
                            ["--no-record", "--no-replay"])
check("refused", res["result"] != "gameplay", f"a refused confirm is not gameplay ({res['result']})")

# repeat: the model keeps answering A on an unchanged menu
rc, res, steps, calls = run("repeat", [("menu", 0)] * 8,
                            [{"state": "main_menu", "why": "menu", "action": ["A"], "wait_s": 1}] * 8,
                            ["--no-record", "--no-replay"])
acts = [" ".join(s.get("action", [])) for s in steps if s.get("src") in ("haiku", "sonnet")]
check("repeat", acts[:3] == ["A", "A", "A"] and acts[3] != "A", f"4th repeat overridden: {acts[:5]}")
models = [c["model"] for c in calls]
check("repeat", models[2] == pathfind.STRONG, f"stronger model from the 3rd look: {models[:4]}")

# replay: the recorded path from `happy` replays the menu step without a call
rc, res, steps, calls = run("replay", [("logo", 0), ("menu", 0), ("game", 0), ("game", 0), ("game", 0),
                                       ("game", 80), ("game", 80)],
                            [GAME, {"gameplay": True, "responded": True, "why": "moved"}], ["--no-record"])
check("replay", res["result"] == "gameplay" and res["replayed"] == 2 and len(calls) == 2,
      f"result {res['result']}, replayed {res['replayed']}, calls {len(calls)}")

# actions
ca = pathfind.clean_action(["a", "START", "STICK:Up:9", "RT:1.5", "HOLD:A:1", "HOLD:Q:1", "JUMP", "select"])
check("actions", ca == ["A", "START", "STICK:up:4", "RT:1.5", "HOLD:A:1", "BACK"], f"{ca}")
check("actions", pathfind.clean_action("wait") == [], "'wait' is no input")

shutil.rmtree(TMP)
print("pathfind_selftest: " + ("FAIL " + ", ".join(sorted(set(fails))) if fails else "all ok"))
sys.exit(1 if fails else 0)
