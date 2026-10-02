#!/usr/bin/env python3
"""classify_selftest.py -- classify.py and drive.py against real frames (#433).

    python3 docs/testing/titles/classify_selftest.py            committed fixtures
    python3 docs/testing/titles/classify_selftest.py --disk     the full-size originals
                                                                 under $DISPATCH_DIR/results
    python3 docs/testing/titles/classify_selftest.py --make     (re)build the fixtures from them

Every case is a frame from a dispatch run already on disk, the frame before
it where motion matters, the states the run had seen, and the state the
classifier must name. The fixtures are those frames as 640x480 JPEGs
(drive-profiles/selftest/; 320x240 lost the small HUD elements the masked
crops look for), so this runs anywhere with PIL and numpy -- not
in jobs-selftest CI, whose runner has neither (as for waitfor_selftest.py).

A classifier shown only passing cases proves nothing, so every state comes
with a COUNTER-CASE: the screen that looks most like it and must NOT be it
(a pause box over a live HUD is `paused`, not `play`; the HUD with nothing
moving is `stalled`; an animated Stage Select is a menu, not a cutscene;
the first HUD frame after a pause is `unknown`, because the motion there is
the pause box leaving). And the rule the owner set (ADDENDUM 2, item 6), a
frame the classifier cannot name is never `play`, is checked over every
fixture under every OTHER title's profile.

The driver's bookkeeping is checked too, with drive.py --sim over a run's
frames in order: the timeline, the skip record, the `play` stretch that ends
a --find run, and a ROUTE FAIL on a stall (Forza at 0 MPH).
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify  # noqa: E402
from PIL import Image  # noqa: E402

PROF = os.path.join(HERE, "drive-profiles")
FIX = os.path.join(PROF, "selftest")
FIX_SIZE, FIX_Q = (640, 480), 60     # the scale the masked references are stored at
RESULTS = os.path.join(os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch"), "results")

SON = "1790902215-autoverdict-1078702"        # Sonic, Nova, the paused confirmation
SON2 = "1790910096-lane.local-2693820"         # Sonic, Nova, live play (wedged on a wall later)
SONT = "1790839390-titleroutes-2237657"        # Sonic, Thor (1920x1080 pillarboxed)
SONT2 = "1790830432-titleroutes-311058"        # Sonic, Thor: stood still, flat grey frame
FOR = "1790914021-lane.ibcache-3202498"        # Forza, Nova: paused every cycle, then 0 MPH
SMB = "1790900520-autoverdict-566484"          # Super Monkey Ball, Nova: ten minutes on Stage Select
CV = "1790902028-titleroutes-1005086"          # Castlevania, Nova: stuck on Name Entry

# (case name, profile, run, frame, prev frame or None, prev state, seen, expected state)
CASES = [
    # Sonic Heroes
    ("sonic title (logo over sky)", "sonic-heroes", SON, "180331-boot20.png", None, None, [], "title"),
    ("sonic title (team art)", "sonic-heroes", SON2, "200413-booted.png", None, None, ["intro_video"], "title"),
    ("sonic Sonic Team logo", "sonic-heroes", SON, "180421-menu-start.png", None, None, ["title"], "logo"),
    ("sonic intro FMV, nothing seen", "sonic-heroes", SON2, "200305-boot60.png", "200233-boot30.png", "intro_video", [], "intro_video"),
    ("sonic no-game-data prompt", "sonic-heroes", SON, "180444-menu-start.png", None, None, ["title"], "profile"),
    ("sonic slot strip", "sonic-heroes", SON2, "200422-menu1.png", None, None, ["title"], "profile"),
    ("sonic Main Menu", "sonic-heroes", SON, "180456-menu-start.png", None, None, ["title", "profile"], "main_menu"),
    ("sonic team select (animated) is a menu", "sonic-heroes", SON2, "200456-team.png", "200449-story.png", "main_menu",
     ["title", "profile", "main_menu"], "main_menu"),
    ("sonic story cutscene", "sonic-heroes", SON2, "200505-cutscene-start.png", "200456-team.png", "main_menu",
     ["title", "profile", "main_menu"], "cutscene"),
    ("sonic NOW LOADING (Thor)", "sonic-heroes", SONT, "004157-menu-start.png", None, None, ["main_menu"], "loading"),
    ("sonic PAUSE over the live HUD", "sonic-heroes", SON, "180617-play.png", "180609-gameplay.png", "paused",
     ["main_menu", "play"], "paused"),
    ("sonic live Seaside Hill", "sonic-heroes", SON2, "200707-play.png", "200657-play.png", "play",
     ["main_menu", "play"], "play"),
    ("sonic live play (Thor)", "sonic-heroes", SONT, "004222-menu-start.png", "004215-menu-a.png", "play",
     ["main_menu", "play"], "play"),
    ("sonic HUD up, team standing still: stalled", "sonic-heroes", SONT2, "222514-play.png", "222505-play.png", "play",
     ["main_menu", "play"], "stalled"),
    ("sonic first HUD frame after a pause: unknown", "sonic-heroes", SON, "180544-menu-start.png", "180538-menu-a.png",
     "paused", ["main_menu", "play", "paused"], "unknown"),
    ("sonic flat grey fade: black", "sonic-heroes", SONT2, "222523-play.png", "222514-play.png", "stalled",
     ["main_menu", "play"], "black"),
    ("sonic black after the title", "sonic-heroes", SONT2, "222229-menu-start.png", None, None, ["title"], "black"),
    ("sonic black at boot", "sonic-heroes", SONT2, "222229-menu-start.png", None, None, [], "boot"),
    ("sonic no previous frame: unknown", "sonic-heroes", SON2, "200233-boot30.png", None, None, [], "unknown"),
    # Forza Motorsport
    ("forza title, PRESS A", "forza", FOR, "214158-menu-start.png", None, None, ["intro_video"], "title"),
    ("forza PROFILE SELECT", "forza", FOR, "214204-menu-a.png", None, None, ["title"], "profile"),
    ("forza MAIN MENU", "forza", FOR, "214211-menu-start.png", None, None, ["title", "profile"], "main_menu"),
    ("forza PAUSE (shares the menus' footer)", "forza", FOR, "214308-menu-start.png", None, None,
     ["main_menu", "play"], "paused"),
    ("forza live race", "forza", FOR, "214502-play.png", "214437-play.png", "play", ["main_menu", "play"], "play"),
    ("forza 0 MPH, race clock running: stalled", "forza", FOR, "214618-play.png", "214553-play.png", "play",
     ["main_menu", "play"], "stalled"),
    ("forza race frame after a pause frame: unknown", "forza", FOR, "214313-menu-a.png", "214308-menu-start.png",
     "paused", ["main_menu", "play", "paused"], "unknown"),
    # Super Monkey Ball Deluxe
    ("smb Stage Select (animated) is a menu", "super-monkey-ball-deluxe", SMB, "172733-play.png", "172723-play.png",
     "main_menu", ["main_menu", "play"], "main_menu"),
    ("smb Mode Select (animated) is a menu", "super-monkey-ball-deluxe", SMB, "172554-menu-a.png", "172548-menu-start.png",
     "main_menu", ["title", "main_menu"], "main_menu"),
    ("smb Name Entry", "super-monkey-ball-deluxe", SMB, "172631-menu-a.png", None, None, ["title", "main_menu"], "profile"),
    ("smb pause box", "super-monkey-ball-deluxe", SMB, "172702-menu-start.png", None, None, ["main_menu"], "paused"),
    ("smb rolling in World 1-1", "super-monkey-ball-deluxe", SMB, "172713-gameplay.png", "172712-rolling.png", "play",
     ["main_menu", "play"], "play"),
    # Castlevania: Curse of Darkness
    ("castlevania title menu", "castlevania-cod", CV, "174750-boot.png", None, None, [], "title"),
    ("castlevania intro FMV after the title", "castlevania-cod", CV, "174810-a1.png", "174750-boot.png", "title",
     ["title"], "intro_video"),
    ("castlevania Name Entry", "castlevania-cod", CV, "174838-name-a.png", None, None, ["title"], "profile"),
]

# Frames that must never be `play` under a profile that is not their title's.
FOREIGN = [(SON2, "200707-play.png", "200657-play.png"), (FOR, "214502-play.png", "214437-play.png"),
           (SMB, "172713-gameplay.png", "172712-rolling.png"), (SONT, "004222-menu-start.png", "004215-menu-a.png"),
           (SMB, "172733-play.png", "172723-play.png")]
TITLE_OF = {SON: "sonic-heroes", SON2: "sonic-heroes", SONT: "sonic-heroes", SONT2: "sonic-heroes",
            FOR: "forza", SMB: "super-monkey-ball-deluxe", CV: "castlevania-cod"}

# drive.py --sim runs: (name, profile, run, frames slice, args, checks). The
# sim step is the seconds between frames; the default 6 is these runs'
# START/A cadence, and Forza's play frames are ~25 s apart.
SIMS = [
    ("sonic: find play in a live run", "sonic-heroes", SON2, (0, 20), ["--find"],
     dict(result="reached-play", time_to_title=True, time_to_play=True)),
    ("forza: 0 MPH is a ROUTE FAIL, not play", "forza", FOR, (31, 39), ["--seconds", "999", "--sim-step", "25"],
     dict(result_prefix="ROUTE FAIL", fail_word="stalled")),
    ("sonic: a pause that never resumes is a ROUTE FAIL", "sonic-heroes", SON, (21, 40), ["--seconds", "999"],
     dict(result_prefix="ROUTE FAIL", fail_word="paused")),
]


def fixture(run, frame):
    return os.path.join(FIX, "%s--%s.jpg" % (run.split("-")[0], frame[:-4]))


def source(run, frame, disk):
    return os.path.join(RESULTS, run, "route-frames", frame) if disk else fixture(run, frame)


def all_frames():
    seen = set()
    for c in CASES:
        seen.add((c[2], c[3]))
        if c[4]:
            seen.add((c[2], c[4]))
    for run, f, p in FOREIGN:
        seen.update({(run, f), (run, p)})
    for _, _, run, (lo, hi), _, _ in SIMS:
        d = os.path.join(RESULTS, run, "route-frames")
        if os.path.isdir(d):
            for f in sorted(x for x in os.listdir(d) if x.endswith(".png"))[lo:hi]:
                seen.add((run, f))
    return sorted(seen)


def _slice_from_list(run, lo, hi):
    with open(os.path.join(FIX, "sims.json")) as f:
        lists = json.load(f)
    return [fixture(run, n) for n in lists[run][lo:hi]]


def make():
    os.makedirs(FIX, exist_ok=True)
    n = 0
    for run, f in all_frames():
        src = os.path.join(RESULTS, run, "route-frames", f)
        im = classify.content(Image.open(src).convert("RGB")).resize(FIX_SIZE, Image.LANCZOS)
        im.save(fixture(run, f), quality=FIX_Q, optimize=True)
        n += 1
    lists = {}
    for _, _, run, _, _, _ in SIMS:
        d = os.path.join(RESULTS, run, "route-frames")
        lists[run] = sorted(x for x in os.listdir(d) if x.endswith(".png"))
    with open(os.path.join(FIX, "sims.json"), "w") as f:
        json.dump(lists, f, indent=0)
    print("made %d fixtures in %s" % (n, FIX))


def main(argv):
    if "--make" in argv:
        make()
        return 0
    disk = "--disk" in argv
    profiles = {}

    def prof(name):
        if name not in profiles:
            profiles[name] = classify.load_profile(os.path.join(PROF, name + ".toml"))
        return profiles[name]

    fails = 0
    for name, pn, run, f, prev, pst, seen, want in CASES:
        r = classify.classify_frame(source(run, f, disk), source(run, prev, disk) if prev else None,
                                    prof(pn), seen, None, pst)
        ok = r["state"] == want
        fails += not ok
        print("%s  %-48s want %-11s got %-11s %s" % ("ok  " if ok else "FAIL", name, want, r["state"], r["source"]))

    for run, f, p in FOREIGN:
        for pn in ("sonic-heroes", "forza", "super-monkey-ball-deluxe", "castlevania-cod"):
            if pn == TITLE_OF[run]:
                continue
            r = classify.classify_frame(source(run, f, disk), source(run, p, disk), prof(pn),
                                        ["title", "main_menu", "play"], None, "play")
            ok = r["state"] != "play"
            fails += not ok
            print("%s  %-48s not play under %-24s got %s (%s)" % ("ok  " if ok else "FAIL",
                  "%s %s" % (run.split("-")[0], f), pn, r["state"], r["source"]))

    for name, pn, run, (lo, hi), args, want in SIMS:
        fl = [os.path.join(RESULTS, run, "route-frames", x) for x in
              sorted(y for y in os.listdir(os.path.join(RESULTS, run, "route-frames")) if y.endswith(".png"))[lo:hi]] \
            if disk else _slice_from_list(run, lo, hi)
        with tempfile.TemporaryDirectory() as td:
            lst = os.path.join(td, "frames.txt")
            with open(lst, "w") as fh:
                fh.write("\n".join(fl) + "\n")
            out = os.path.join(td, "out")
            cmd = [sys.executable, os.path.join(HERE, "drive.py"), "--profile", os.path.join(PROF, pn + ".toml"),
                   "--out", out, "--sim", "@" + lst] + (["--sim-step", "6"] if "--sim-step" not in args else []) + args
            if "--seconds" not in args:
                cmd += ["--seconds", "999"]
            p = subprocess.run(cmd, capture_output=True, text=True)
            sol = json.load(open(os.path.join(out, "route-solution.json")))
            tsv = open(os.path.join(out, "route-state.tsv")).read()
            probs = []
            if "result" in want and sol["result"] != want["result"]:
                probs.append("result %s" % sol["result"])
            if "result_prefix" in want and not sol["result"].startswith(want["result_prefix"]):
                probs.append("result %s" % sol["result"])
            if "fail_word" in want and want["fail_word"] not in sol["result"]:
                probs.append("fail reason %s" % sol["result"])
            if want.get("time_to_title") and sol["time_to_title_s"] is None:
                probs.append("no time_to_title")
            if want.get("time_to_play") and sol["time_to_play_s"] is None:
                probs.append("no time_to_play")
            if "\tplay\t" in tsv and any(i["input"] in ("START", "START+A") and i["state"] == "play" for i in sol["inputs"]):
                probs.append("START sent in play")
            if "# result=" not in tsv:
                probs.append("tsv has no summary")
            ok = not probs
            fails += not ok
            print("%s  sim %-44s %s%s" % ("ok  " if ok else "FAIL", name, sol["result"][:70],
                                          "" if ok else "  <- " + "; ".join(probs) + "\n" + p.stdout + p.stderr))
    print("classify_selftest: %d failure(s)" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
