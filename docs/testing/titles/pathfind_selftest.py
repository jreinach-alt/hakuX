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

# actions
ca = pathfind.clean_action(["a", "START", "STICK:Up:9", "RT:1.5", "HOLD:A:1", "HOLD:Q:1", "JUMP", "select"])
check("actions", ca == ["A", "START", "STICK:up:4", "RT:1.5", "HOLD:A:1", "BACK"], f"{ca}")
check("actions", pathfind.clean_action("wait") == [], "'wait' is no input")

shutil.rmtree(TMP)
print("pathfind_selftest: " + ("FAIL " + ", ".join(sorted(set(fails))) if fails else "all ok"))
sys.exit(1 if fails else 0)
