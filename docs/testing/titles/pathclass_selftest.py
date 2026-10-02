#!/usr/bin/env python3
"""pathclass.py selftest. Runs with the system python3: no venv, no GPU, no device.

    python3 docs/testing/titles/pathclass_selftest.py           the fail-open path and the tables
    python3 docs/testing/titles/pathclass_selftest.py --gpu     also the live classifier, when the venv is here

Checked without the venv:
  - fail open: with no venv, `classify`, `serve` and `check` print ONE line `pathclass: unavailable: ...` and
    exit 3, and `Client()` raises `Unavailable` (pathfind falls back to the language model, never stops);
  - the rule table names an action for every state, and every counter-case gets the opposite answer:
    a highlighted play item is A and a highlighted avoid item is not; Name Entry is START, never A;
    a save prompt escalates; unread menus escalate;
  - the intent table: 'Play Now'/'Exhibition'/'Quick Race'/'New Game'/'Start'/'Single Player' select,
    'Options'/'Credits'/'Xbox Live' avoid, and a word inside another word does not match;
  - the OCR text rules on the known false passes' OCR text (Sonic PAUSE, KOF WINNER, Castlevania Name Entry,
    187's keyboard), each with the gameplay HUD text that must NOT flip play (lap, MPH, a tip);
  - the temporal rule: an attract demo before the first menu is intro_video, a cutscene-looking frame
    after it is cutscene, a moving logo is intro_video and a static one stays a logo;
  - the free checks on synthetic frames: black, a flat fade, static vs moving, the FPS corner ignored.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pathclass as pc  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {name}{(': ' + str(detail)) if detail and not cond else ''}")
    if not cond:
        FAILS.append(name)


def run_cli(args, env_extra, stdin=None):
    env = dict(os.environ)
    env.pop("PATHCLASS_NO_REEXEC", None)
    env.update(env_extra)
    return subprocess.run([sys.executable, os.path.join(HERE, "pathclass.py")] + args, capture_output=True,
                          text=True, env=env, input=stdin, timeout=120)


def fail_open():
    nov = {"PATHCLASS_VENV": "/nonexistent/pathclass-venv"}
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "f.png")
        from PIL import Image
        Image.new("RGB", (640, 480)).save(f)
        for args in (["classify", f], ["check"], ["serve"]):
            r = run_cli(args, nov, stdin="")
            lines = [l for l in r.stderr.splitlines() if l.strip()]
            check(f"fail open: {args[0]} exits {pc.UNAVAILABLE_EXIT} without the venv", r.returncode == pc.UNAVAILABLE_EXIT,
                  r.returncode)
            check(f"fail open: {args[0]} says so in one line", len(lines) == 1 and lines[0].startswith(
                "pathclass: unavailable:"), r.stderr)
            check(f"fail open: {args[0]} prints nothing on stdout but serve's not-ready line",
                  r.stdout.strip() == "" or (args[0] == "serve" and not json.loads(r.stdout.splitlines()[0])["ready"]),
                  r.stdout)
    old = os.environ.get("PATHCLASS_VENV")
    os.environ["PATHCLASS_VENV"] = "/nonexistent/pathclass-venv"
    try:
        pc.Client()
        check("fail open: Client raises Unavailable", False, "no exception")
    except pc.Unavailable as e:
        check("fail open: Client raises Unavailable", "unavailable" in str(e), e)
    finally:
        if old is None:
            os.environ.pop("PATHCLASS_VENV")
        else:
            os.environ["PATHCLASS_VENV"] = old


def item(text, box=(100, 100, 300, 130), hi=False):
    return {"text": text, "box": list(box), "highlighted": hi, "intent": pc.intent_of(text)}


def rules():
    for s in pc.STATES:
        check(f"rule table names an action for {s}", s in pc.RULES and pc.RULES[s][0])
    act, esc = pc.decide("main_menu", [item("Exhibition", hi=True), item("Options", (100, 140, 300, 170))])
    check("menu: highlighted 'Exhibition' is A", act["do"] == "A" and esc is None, act)
    act, esc = pc.decide("main_menu", [item("Options", hi=True), item("Credits", (100, 140, 300, 170))])
    check("menu counter-case: highlighted 'Options' with no play item is not A", act["do"] != "A", act)
    act, esc = pc.decide("main_menu", [item("Options", hi=True), item("Quick Race", (100, 140, 300, 170))])
    check("menu: from highlighted 'Options' move DOWN to 'Quick Race' below", act["do"] == "DOWN", act)
    act, esc = pc.decide("main_menu", [item("Options", (100, 140, 300, 170), hi=True), item("New Game")])
    check("menu: from highlighted 'Options' move UP to 'New Game' above", act["do"] == "UP", act)
    act, esc = pc.decide("submenu", [item("Gamma"), item("Brightness", (100, 140, 300, 170))])
    check("menu with no matching text escalates", esc == "menu_no_match", (act, esc))
    act, esc = pc.decide("main_menu", [])
    check("menu with no text read escalates", esc == "menu_unread", (act, esc))
    act, _ = pc.decide("name_entry", [item("A"), item("B")])
    check("Name Entry is START (A types a letter)", act["do"] == "START", act)
    _, esc = pc.decide("save_load_prompt", [])
    check("save prompt escalates (they default to No)", esc is not None)
    act, _ = pc.decide("gameplay", [])
    check("gameplay is only a candidate: verify, not a claim", act["do"] == "verify", act)
    _, esc = pc.decide("unknown", [])
    check("unknown escalates", esc == "unknown")


def intents():
    for t in ("Play Now", "EXHIBITION", "Quick Race", "New Game", "Start", "Single Player", "START GAME"):
        check(f"intent: '{t}' selects", pc.intent_of(t) == "select", pc.intent_of(t))
    for t in ("Options", "Credits", "Xbox Live", "OPTIONS", "Xbox LIVE"):
        check(f"intent: '{t}' is avoided", pc.intent_of(t) == "avoid", pc.intent_of(t))
    for t in ("Startled", "Gostop", "Snowboard", "Nobody"):
        check(f"intent counter-case: '{t}' matches nothing", pc.intent_of(t) is None, pc.intent_of(t))


def texts():
    m = lambda *ts: [item(t, (100, 100 + 30 * i, 300, 125 + 30 * i)) for i, t in enumerate(ts)]  # noqa: E731
    # the known false passes (pathknow eval OCR text, as read by easyocr)
    check("Sonic PAUSE over play is pause", pc.text_state("gameplay", m("00821 :29", "006", "PAUSE", "Continue",
                                                                        "Restart", "Quit")) == "pause")
    check("KOF lost round 'WINNI' over play is results", pc.text_state("gameplay", m("YAGAMI", "WINNI")) == "results")
    check("Castlevania Name Entry is name_entry", pc.text_state("submenu", m("Name Entry", "A B C D E F G",
                                                                          "(Delete)", "Accept")) == "name_entry")
    check("187 keyboard is name_entry", pc.text_state("gameplay", m("Select char", "Back", "Erase char",
                                                                  "Validate text", "Define the profile name")) == "name_entry")
    check("Burnout-style GAME OVER over play is game_over", pc.text_state("gameplay", m("GAME OVER")) == "game_over")
    check("'Now Loading' is loading", pc.text_state("cutscene", m("The Book of the Fiends", "Now Loading")) == "loading")
    check("attract 'PRESS START' over play is title_screen", pc.text_state("gameplay", m("PRESS START")) == "title_screen")
    check("a menu over play with Select/Back legend is not gameplay",
          pc.text_state("gameplay", m("Stage 1", "Stage 2", "Select", "Back")) == "submenu")
    # counter-cases: HUD text on real play must not flip it
    check("counter-case: a racing HUD (LAP, MPH, PLACE) stays play",
          pc.text_state("gameplay", m("LAP", "0/2", "RACE", "00:10.667", "MPH", "PLACE 8/8")) is None)
    check("counter-case: a tutorial tip on play stays play",
          pc.text_state("gameplay", m("TIP: Move the", "Rthumbstick to", "move the camera")) is None)
    check("counter-case: SMB Stage Select's 'press START button' line does not make a title screen",
          pc.text_state("submenu", m("Select", "World", "Jungle Island", "Difficulty",
                                     "For other options, press START button")) != "title_screen")
    check("counter-case: no text, no override", pc.text_state("gameplay", []) is None)


def temporal():
    check("attract demo before the first menu is intro_video",
          pc.temporal("gameplay", {"moving": True}, {"menu_seen": False}) == "intro_video")
    check("counter-case: play after a menu stays gameplay",
          pc.temporal("gameplay", {"moving": True}, {"menu_seen": True}) == "gameplay")
    check("cutscene-looking frame before the first menu is intro_video",
          pc.temporal("cutscene", {}, {"menu_seen": False}) == "intro_video")
    check("intro-looking frame after a menu is cutscene", pc.temporal("intro_video", {}, {"menu_seen": True}) == "cutscene")
    check("a moving logo is intro_video", pc.temporal("publisher_logo", {"moving": True}, {}) == "intro_video")
    check("counter-case: a static logo stays publisher_logo",
          pc.temporal("publisher_logo", {"moving": False}, {}) == "publisher_logo")
    check("no context: the image state stands", pc.temporal("gameplay", {"moving": None}, {}) == "gameplay")


def free():
    from PIL import Image, ImageDraw
    with tempfile.TemporaryDirectory() as d:
        p = lambda n: os.path.join(d, n)  # noqa: E731
        im = Image.new("RGB", (640, 480))
        ImageDraw.Draw(im).text((10, 10), "FPS: 60", fill=(255, 255, 255))  # the FPS overlay corner
        im.save(p("black.png"))
        Image.new("RGB", (640, 480), (120, 120, 120)).save(p("fade.png"))
        import random
        rnd = random.Random(1)
        a = Image.new("RGB", (640, 480))
        ImageDraw.Draw(a).rectangle((200, 150, 440, 330), fill=(200, 60, 60))
        for _ in range(400):
            x, y = rnd.randrange(640), rnd.randrange(480)
            ImageDraw.Draw(a).rectangle((x, y, x + 8, y + 8), fill=(rnd.randrange(256),) * 3)
        a.save(p("a.png"))
        b = a.copy()
        ImageDraw.Draw(b).rectangle((0, 0, 120, 45), fill=(255, 255, 255))  # only the FPS corner changes
        b.save(p("a_fps.png"))
        c = a.transpose(Image.FLIP_LEFT_RIGHT)
        c.save(p("c.png"))
        r = pc.free_checks(p("black.png"))
        check("black frame (FPS text in the corner) is black", r["black"], r)
        r = pc.free_checks(p("fade.png"))
        check("flat grey fade is black", r["black"], r)
        r = pc.free_checks(p("a.png"), p("a_fps.png"))
        check("counter-case: a busy frame is not black", not r["black"], r)
        check("static: only the FPS corner changed", r["moving"] is False, r)
        r = pc.free_checks(p("c.png"), p("a.png"))
        check("moving: the scene changed", r["moving"] is True, r)
        r = pc.free_checks(p("a.png"))
        check("no prev: moving is unknown (None)", r["moving"] is None, r)


def gpu():
    py = os.path.join(pc.VENV, "bin", "python")
    if not os.path.exists(py):
        print("skip --gpu: no venv")
        return
    from PIL import Image
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "f.png")
        Image.new("RGB", (640, 480)).save(f)
        r = run_cli(["classify", f, "--no-ocr"], {})
        try:
            o = json.loads(r.stdout)
        except Exception:
            o = {}
        need = {"state", "confidence", "top3", "moving", "black", "menu", "ms"}
        check("live: classify answers every interface field", need <= set(o), (r.returncode, r.stderr[-300:]))
        check("live: an all-black frame is black", o.get("state") == "black" and o.get("black") is True, o)
        c = pc.Client()
        try:
            o2 = c.classify(f, f, {"menu_seen": False})
            check("live: Client round trip (serve)", o2.get("state") == "black" and o2.get("moving") is False, o2)
        finally:
            c.close()


def main():
    fail_open()
    rules()
    intents()
    texts()
    temporal()
    free()
    if "--gpu" in sys.argv:
        gpu()
    print(f"\npathclass_selftest: {'PASS' if not FAILS else 'FAIL ' + str(len(FAILS))}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
