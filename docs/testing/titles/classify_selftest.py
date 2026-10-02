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
CVT = "1790839398-titleroutes-2238193"         # Castlevania, Thor: survey, status screen every other press
# lane.routedriver's own held Castlevania replays (not dispatch runs, so not
# under results/): the originals were in the lane worktree's scratch/ and
# only the fixtures are committed. --make keeps a fixture whose original is
# gone.
CVR2 = "rdcv2"                                 # replay 2: Name Entry answered, stuck on the Overwrite prompt
CVR3 = "rdcv3"                                 # replay 3: play, then walked into the fountain (stalled)
CVR5 = "rdcv5"                                 # replay 5: first run, boot to 20 s of play
SHR1 = "rdsh1"                                 # session 4, Nova: Seaside Hill, wedged on a block 14 s in
FZR1 = "rdfz1"                                 # session 4, Thor: boot to a race, RT held, 0 -> 73 MPH
SHT1 = "rdt1"                                  # lane.routedriver2 trial 1, Nova: past the pillar, then a corner
LOCAL = {CVR2: "scratch/run-cv2/route-frames", CVR3: "scratch/run-cv3/route-frames",
         CVR5: "scratch/run-cv5/route-frames", SHR1: "scratch/run-sh1/route-frames",
         FZR1: "scratch/run-fz1/route-frames", SHT1: "scratch/run-t1/route-frames"}

# drive.py's progress check ([drive] progress_bar): (name, profile, run, frame
# ~10 s earlier, the frame before this one, this frame, the sim seconds
# between the earlier frame and this one, the state wanted; the frames are
# 8 s apart on the run's clock, judged at the 10 s window). The counter-case to running
# is the team struggling in a corner, whose 2 s motion reads `play`.
PROGRESS = [
    ("sonic running, 8 s on: play", "sonic-heroes", SHT1, "022719-036-play.png", "022725-039-play.png",
     "022727-040-play.png", 10.0, "play"),
    ("sonic in a corner, moving, 8 s on: stalled", "sonic-heroes", SHT1, "022906-071-play.png", "022912-074-play.png",
     "022914-075-play.png", 10.0, "stalled"),
]
# [[mode]] from a HUD region's colour, through Driver.classify: (name,
# profile, run, frame, mode wanted). The counter-case is a menu: its blue
# reads as Speed's colour, so the mode is only read on a frame with the play
# HUD up, and a menu leaves it unset.
MODES = [
    ("sonic Speed (Sonic leads)", "sonic-heroes", SHT1, "022658-027-play.png", "speed"),
    ("sonic Power (Knuckles leads)", "sonic-heroes", SHT1, "022758-048-play.png", "power"),
    ("sonic Fly (Tails leads)", "sonic-heroes", SHR1, "234358-033-play.png", "fly"),
    ("sonic Speed (Thor)", "sonic-heroes", SONT, "004222-menu-start.png", "speed"),
    ("sonic Main Menu: no formation", "sonic-heroes", SON, "180456-menu-start.png", None),
]

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
    # The wedge: the team pressed against a Seaside Hill block, the clock
    # running and the water moving (0.14-0.18 changed, 2 s apart). Before
    # hud_stall_bar this read `play` (session 4's first replay: four `play`
    # captures that the frames show going nowhere).
    ("sonic wedged on a block, clock and water moving: stalled", "sonic-heroes", SHR1, "234358-033-play.png",
     "234356-032-play.png", "play", ["main_menu", "play"], "stalled"),
    ("sonic running Seaside Hill, 2 s apart", "sonic-heroes", SHR1, "234349-029-play.png", "234347-028-play.png",
     "play", ["main_menu", "play"], "play"),
    # Forza Motorsport
    ("forza title, PRESS A", "forza", FOR, "214158-menu-start.png", None, None, ["intro_video"], "title"),
    ("forza PROFILE SELECT", "forza", FOR, "214204-menu-a.png", None, None, ["title"], "profile"),
    ("forza MAIN MENU", "forza", FOR, "214211-menu-start.png", None, None, ["title", "profile"], "main_menu"),
    ("forza PAUSE (shares the menus' footer)", "forza", FOR, "214308-menu-start.png", None, None,
     ["main_menu", "play"], "paused"),
    ("forza live race", "forza", FOR, "214502-play.png", "214437-play.png", "play", ["main_menu", "play"], "play"),
    ("forza 0 MPH, race clock running: stalled", "forza", FOR, "214618-play.png", "214553-play.png", "play",
     ["main_menu", "play"], "stalled"),
    ("forza live race, slow scene change (Thor): play", "forza", FZR1, "234117-045-play.png", "234114-044-play.png",
     "play", ["main_menu", "play"], "play"),
    ("forza on the line at 0 MPH after the race intro: unknown", "forza", FZR1, "234101-038-unknown.png",
     "234051-034-cutscene.png", "cutscene", ["main_menu", "cutscene"], "unknown"),
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
    ("castlevania Konami logo", "castlevania-cod", CVR5, "230014-003-logo.png", "230013-002-intro_video.png",
     "intro_video", [], "logo"),
    ("castlevania title, cursor on Continue", "castlevania-cod", CVR5, "230018-005-title.png", None, None, [], "title"),
    ("castlevania Overwrite prompt over the SAVE list", "castlevania-cod", CVR2, "225522-066-fail-profile.png", None,
     None, ["title", "profile"], "profile"),
    ("castlevania LOAD list + 'Is this save data correct?'", "castlevania-cod", CVT, "011417-menu-start.png", None,
     None, ["title"], "profile"),
    ("castlevania Saving... is loading, not a menu", "castlevania-cod", CVR5, "230046-020-loading.png", None, None,
     ["title", "profile"], "loading"),
    ("castlevania Valachia text crawl", "castlevania-cod", CVT, "011428-menu-start.png", "011423-menu-a.png",
     "cutscene", ["title", "profile"], "cutscene"),
    ("castlevania Player status screen is paused", "castlevania-cod", CVT, "011452-menu-start.png", None, None,
     ["profile", "play"], "paused"),
    ("castlevania live courtyard play", "castlevania-cod", CVR5, "230108-033-play.png", "230106-032-play.png", "play",
     ["profile", "play"], "play"),
    ("castlevania HUD up, pinned on the fountain: stalled", "castlevania-cod", CVR3, "225651-021-stalled.png",
     "225649-020-play.png", "play", ["profile", "play"], "stalled"),
    ("castlevania HUD frame after the status screen: unknown", "castlevania-cod", CVT, "011505-menu-start.png",
     "011459-menu-a.png", "paused", ["profile", "play", "paused"], "unknown"),
]

# Frames that must never be `play` under a profile that is not their title's.
FOREIGN = [(SON2, "200707-play.png", "200657-play.png"), (FOR, "214502-play.png", "214437-play.png"),
           (SMB, "172713-gameplay.png", "172712-rolling.png"), (SONT, "004222-menu-start.png", "004215-menu-a.png"),
           (SMB, "172733-play.png", "172723-play.png"), (CVR5, "230108-033-play.png", "230106-032-play.png"),
           (SHR1, "234349-029-play.png", "234347-028-play.png"), (FZR1, "234117-045-play.png", "234114-044-play.png")]
TITLE_OF = {SON: "sonic-heroes", SON2: "sonic-heroes", SONT: "sonic-heroes", SONT2: "sonic-heroes",
            FOR: "forza", FZR1: "forza", SHR1: "sonic-heroes", SMB: "super-monkey-ball-deluxe", CV: "castlevania-cod", CVT: "castlevania-cod",
            CVR2: "castlevania-cod", CVR3: "castlevania-cod", CVR5: "castlevania-cod"}

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
    ("castlevania: first run, boot to play", "castlevania-cod", CVR5, (0, 27), ["--find", "--sim-step", "2"],
     dict(result="reached-play", time_to_title=True, time_to_play=True)),
    # 14 s of running, then wedged: not 20 s of play, and the stall escape
    # goes out (session 4's first replay called the wedge play and ended).
    ("sonic: a wedge on a block is not play; the escape runs", "sonic-heroes", SHR1, (9, 20),
     ["--find", "--sim-step", "2"], dict(result="window-done", input_why="stall escape")),
    ("forza: boot to a race with RT held (Thor)", "forza", FZR1, (0, 28), ["--find", "--sim-step", "2"],
     dict(result="reached-play", time_to_title=True, time_to_play=True)),
]


def fixture(run, frame):
    return os.path.join(FIX, "%s--%s.jpg" % (run.split("-")[0], frame[:-4]))


def frames_dir(run):
    if run in LOCAL:
        return os.path.join(HERE, "..", "..", "..", LOCAL[run])
    return os.path.join(RESULTS, run, "route-frames")


def source(run, frame, disk):
    return os.path.join(frames_dir(run), frame) if disk else fixture(run, frame)


def all_frames():
    seen = set()
    for c in CASES:
        seen.add((c[2], c[3]))
        if c[4]:
            seen.add((c[2], c[4]))
    for run, f, p in FOREIGN:
        seen.update({(run, f), (run, p)})
    for _, _, run, a, b, c, _, _ in PROGRESS:
        seen.update({(run, a), (run, b), (run, c)})
    for _, _, run, f, _ in MODES:
        seen.add((run, f))
    for _, _, run, (lo, hi), _, _ in SIMS:
        d = frames_dir(run)
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
        src = os.path.join(frames_dir(run), f)
        if not os.path.exists(src) and os.path.exists(fixture(run, f)):
            continue
        im = classify.content(Image.open(src).convert("RGB")).resize(FIX_SIZE, Image.LANCZOS)
        im.save(fixture(run, f), quality=FIX_Q, optimize=True)
        n += 1
    with open(os.path.join(FIX, "sims.json")) as f:
        lists = json.load(f)
    for _, _, run, _, _, _ in SIMS:
        d = frames_dir(run)
        if os.path.isdir(d):
            lists[run] = sorted(x for x in os.listdir(d) if x.endswith(".png"))
    with open(os.path.join(FIX, "sims.json"), "w") as f:
        json.dump(lists, f, indent=0)
    print("made %d fixtures in %s" % (n, FIX))


def escape_checks():
    """input.stall_cycles: escape n plays cycle (n-1) mod len, a `B/ms` press
    goes to pad.sh with its hold time, and a cycle that sends START is
    refused. The counter-cases: a single stall_cycle replays the same cycle
    every time, and START hidden in the SECOND cycle (or behind a /ms) is
    still refused."""
    import drive
    fails = 0

    def drv(inp):
        with tempfile.TemporaryDirectory() as td:
            return drive.Driver(drive.SimDevice([], 1.0), dict(name="t", input=inp), td, td, 10, sim=True)

    def sent_by_escape(inp, n):
        d = drv(inp)
        out = []
        for _ in range(n):
            d.dev.sent = []
            d.start_escape()
            out.append([s[1:] for s in d.dev.sent if s[1] == "press"])
        return out

    a = [[[], 0.5, ["A", "A/800"]]]
    b = [[[["LY", "min"]], 0.5, ["Y"]]]
    got = sent_by_escape(dict(stall_cycles=[a, b]), 3)
    want = [[("press", "A"), ("press", "A", "800")], [("press", "Y")], [("press", "A"), ("press", "A", "800")]]
    checks = [("stall_cycles: escapes 1, 2, 3 play cycles a, b, a", got == want, got)]
    got1 = sent_by_escape(dict(stall_cycle=b), 2)
    checks.append(("stall_cycle (one): every escape plays it", got1 == [[("press", "Y")]] * 2, got1))
    for name, inp in (("START in the second of stall_cycles", dict(stall_cycles=[a, [[[], 0.5, ["START"]]]])),
                      ("START/500 in stall_cycle", dict(stall_cycle=[[[], 0.5, ["START/500"]]]))):
        try:
            drv(inp)
            checks.append(("refused: " + name, False, "accepted"))
        except SystemExit as e:
            checks.append(("refused: " + name, "START" in str(e), str(e)))
    for name, ok, got in checks:
        fails += not ok
        print("%s  escape %-44s %s" % ("ok  " if ok else "FAIL", name, "" if ok else got))
    return fails


def progress_checks(prof, disk):
    """The progress check and the mode reading, through drive.Driver.classify
    on the sim clock, as a run would meet them."""
    import drive
    fails = 0
    for name, pn, run, old, prev, cur, dt, want in PROGRESS:
        with tempfile.TemporaryDirectory() as td:
            d = drive.Driver(drive.SimDevice([], 1.0), prof(pn), td, td, 999, sim=True)
            d.seen = ["main_menu", "play"]
            d.state = "play"
            d.classify(source(run, old, disk))
            d.clock_sim = dt
            d.prev = source(run, prev, disk)
            r = d.classify(source(run, cur, disk))
        ok = r["state"] == want
        fails += not ok
        print("%s  progress %-44s want %-8s got %-8s %s p=%s" % ("ok  " if ok else "FAIL", name, want, r["state"],
                                                                  r["source"], r.get("progress")))
    for name, pn, run, f, want in MODES:
        with tempfile.TemporaryDirectory() as td:
            d = drive.Driver(drive.SimDevice([], 1.0), prof(pn), td, td, 999, sim=True)
            d.seen = ["main_menu", "play"]
            d.classify(source(run, f, disk))
            got = d.mode
        ok = got == want
        fails += not ok
        print("%s  mode %-48s want %-6s got %s" % ("ok  " if ok else "FAIL", name, want, got))
    return fails


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
        fl = [os.path.join(frames_dir(run), x) for x in
              sorted(y for y in os.listdir(frames_dir(run)) if y.endswith(".png"))[lo:hi]] \
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
            if "input_why" in want and not any(i["why"].startswith(want["input_why"]) for i in sol["inputs"]):
                probs.append("no input '%s'" % want["input_why"])
            if "# result=" not in tsv:
                probs.append("tsv has no summary")
            ok = not probs
            fails += not ok
            print("%s  sim %-44s %s%s" % ("ok  " if ok else "FAIL", name, sol["result"][:70],
                                          "" if ok else "  <- " + "; ".join(probs) + "\n" + p.stdout + p.stderr))
    fails += escape_checks()
    fails += progress_checks(prof, disk)
    print("classify_selftest: %d failure(s)" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
