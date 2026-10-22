#!/usr/bin/env python3
"""pathclass_selftest.py -- the generic `drive` fallback's wiring, without the venv (#433).

    python3 docs/testing/titles/pathclass_selftest.py

classify.py's `classifier = "pathclass"` branch and drive.py's fail-closed catch (run(),
on classify.Unavailable) are exercised here through a stub `pathclass.Client` -- a
recorded per-frame answer table, not a live model -- so this runs anywhere with PIL, no
torch, no GPU, no `pathclass.py serve` process, matching classify_selftest.py's own
reasons for staying out of jobs-selftest CI (that runner has neither).

The recorded answers are pathclass's real output, captured once through the venv against
`docs/testing/titles/pathknow/classifier/head.npz`, on the run the owner flagged (NOTES.md
"Restart, attempt 2"): 1-1791745785-nfsdefault1011-877404, Simpsons Hit & Run on the Nova,
reached free roam at 12:49:50 while a blind START/A survey loop kept running until 12:51:44.
Every frame from 124950-entry.png on reads `gameplay`: this run's capture cadence never
landed mid-pause (the pause/resume completed between captures), so there is no literal
paused-overlay frame from this run to replay. What protects that case is structural, not
frame-specific -- act() never presses START for state == play or stalled -- and the mutant
test below checks that a regression there would be caught, not assumed.
"""
import glob
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify  # noqa: E402
import drive  # noqa: E402
import learned  # noqa: E402  (drive.py's own import already put pathknow/ on sys.path)
import pathbook  # noqa: E402

PROF = os.path.join(HERE, "drive-profiles")
RESULTS = os.path.join(os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch"), "results")

# #433: the owner's ask was "drop the API key path entirely" -- not reworded,
# removed. Scoped to drive.py's own runtime loop and the files it reads
# (classify.py, pathclass.py, drive-profiles/*.toml), not pathfind.py or
# pathknow/classifier/label.py, which are separate, intentionally
# model-driven tools (cold-boot path discovery and offline frame labelling)
# that this lane's brief never asked to touch and whose files are not on
# this lane's edit list.
GREP_GATE_FILES = (
    [os.path.join(HERE, "drive.py"), os.path.join(HERE, "classify.py"), os.path.join(HERE, "pathclass.py")]
    + sorted(glob.glob(os.path.join(PROF, "*.toml")))
)
GREP_GATE_STRINGS = ("anthropic", "ask_model", "claude -p", "model_calls_max", "unknown_before_model")


def grep_gate():
    hits = []
    for path in GREP_GATE_FILES:
        with open(path) as f:
            text = f.read().lower()
        for s in GREP_GATE_STRINGS:
            if s in text:
                hits.append("%s: %r" % (os.path.relpath(path, HERE), s))
    return hits

SIM_RUN = "1-1791745785-nfsdefault1011-877404"
# frame -> (pathclass state, confidence), recorded via pathclass.Classifier(ocr=False)
# .classify() over this run's route-frames/, in order, context={"menu_seen": True}.
SIM_ANSWERS = {
    "124759-entry.png": ("black", 0.99),
    "124821-entry.png": ("main_menu", 0.39),
    "124827-entry.png": ("cutscene", 0.48),
    "124833-entry.png": ("cutscene", 0.78),
    "124840-entry.png": ("cutscene", 0.83),
    "124846-entry.png": ("cutscene", 0.79),
    "124852-entry.png": ("cutscene", 0.65),
    "124859-entry.png": ("cutscene", 0.32),
    "124905-entry.png": ("main_menu", 0.57),
    "124911-entry.png": ("gameplay", 0.69),
    "124918-entry.png": ("controller_prompt", 0.56),
    "124924-entry.png": ("controller_prompt", 0.55),
    "124931-entry.png": ("controller_prompt", 0.53),
    "124937-entry.png": ("controller_prompt", 0.56),
    "124944-entry.png": ("controller_prompt", 0.46),
    "124950-entry.png": ("gameplay", 0.92),
    "124957-entry.png": ("gameplay", 0.90),
    "125004-entry.png": ("gameplay", 0.93),
    "125010-entry.png": ("gameplay", 0.93),
    "125017-entry.png": ("gameplay", 0.91),
    "125023-entry.png": ("gameplay", 0.93),
    "125030-entry.png": ("gameplay", 0.93),
    "125112-entry.png": ("gameplay", 0.93),
    "125118-entry.png": ("gameplay", 0.93),
    "125125-entry.png": ("gameplay", 0.93),
    "125131-entry.png": ("gameplay", 0.91),
    "125138-entry.png": ("gameplay", 0.93),
    "125144-entry.png": ("gameplay", 0.92),
    "125159-gameplay.png": ("gameplay", 0.97),
    "125200-gameplay.png": ("gameplay", 0.97),
    "125214-play.png": ("gameplay", 0.86),
    "125228-play.png": ("gameplay", 0.98),
    "125242-play.png": ("gameplay", 0.98),
}


AVP_RUN = "1-1791808256-lane.pathclass-215913"
# frame -> (pathclass state, confidence), recorded via pathclass.Classifier(ocr=True)
# .classify() over this run's route-frames/, in order, context={"menu_seen": False}
# (#433 Addendum 6): AvP Extinction's gen-avp-extinction run stalled 91 s on `unknown` at
# the title screen -- ROUTE FAIL "unknown screen for 91 s (model unavailable)" -- because
# the single 0.85 `classifier_confidence` floor gated this answer too. The title screen's
# own answer, 0.8 (OCR's "Press START" confirming the image model's own title_screen call,
# pathclass.py's "+text-confirmed" branch), was 0.05 short of it; a hand-tuned profile
# picking a confidence anywhere above 0.8 would have stalled here regardless of the text
# match. The fix is a second, lower floor for non-gameplay answers only
# (`classifier_confidence_menu`, generic.toml); this replays the run's frames (unchanged)
# to prove it.
#
# This run's own frames include three that are genuinely near-black (luma 0, boot/loading
# transitions) -- classify.py's real pixel-based black check answers those directly, the
# same way it would on a live route, without ever reaching pathclass.Client. All ten frames
# still get replayed (AVP_FRAMES, for realistic pacing), but only the seven StubClient is
# actually asked about are listed here, in call order, so the stub's answer queue lines up
# with the calls classify.py really makes -- not with the frame list's own order.
AVP_FRAMES = [
    "053316-001-boot.png",
    "053337-002-intro_video.png",
    "053341-003-unknown.png",
    "053346-006-black.png",
    "053350-008-unknown.png",
    "053353-010-black.png",
    "053355-011-unknown.png",
    "053414-015-intro_video.png",
    "053416-016-unknown.png",
    "053550-059-fail-unknown.png",
]
AVP_ANSWERS = [
    ("publisher_logo", 0.942),  # 002-intro_video.png
    ("loading", 0.694),  # 003-unknown.png
    ("loading", 0.756),  # 008-unknown.png
    ("intro_video", 0.767),  # 011-unknown.png
    ("intro_video", 0.91),  # 015-intro_video.png
    ("publisher_logo", 0.395),  # 016-unknown.png
    ("title_screen", 0.8),  # 059-fail-unknown.png -- the stalled title screen
]


def avp_frames():
    d = os.path.join(RESULTS, AVP_RUN, "route-frames")
    # the stalled title screen three times: the fallen floor names the 0.395 capture before it `unknown`, the
    # d-pad look flick lands on that one, and START needs a capture after the settle to go out on
    return [os.path.join(d, f) for f in AVP_FRAMES + AVP_FRAMES[-1:] * 3], d


def avp_answers_ordered():
    return list(AVP_ANSWERS)


class StubClient:
    """Stands in for pathclass.Client in classify.pathclass_client(): the next answer off a
    list, in call order, no subprocess, no model. In order because SimDevice.capture()
    copies each source frame to an alternating `cap0.png`/`cap1.png` before classify.py
    ever sees a path, so the original frame's name is gone by the time it gets here.
    An answer is (state, confidence), or a whole pathclass answer dict (top3, action,
    diff: routebuild1021's lean tests)."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.i = 0

    def classify(self, frame, prev, context):
        a = self.answers[min(self.i, len(self.answers) - 1)]
        self.i += 1
        if isinstance(a, dict):
            return dict({"moving": True, "diff": 0.5}, **a)
        st, conf = a
        return {"state": st, "confidence": conf, "moving": True, "diff": 0.5}


def install_stub(answers):
    classify._PATHCLASS_CLIENT = StubClient(answers)
    classify.pathclass_client = lambda: classify._PATHCLASS_CLIENT


def install_unavailable(reason):
    def raiser():
        raise classify.Unavailable(reason)
    classify.pathclass_client = raiser


def sim_frames():
    d = os.path.join(RESULTS, SIM_RUN, "route-frames")
    return [os.path.join(d, f) for f in sorted(SIM_ANSWERS)], d


def sim_answers_ordered():
    # same order as sim_frames(): StubClient has no frame name to key on (see its
    # docstring), just the position of the capture.
    return [SIM_ANSWERS[f] for f in sorted(SIM_ANSWERS)]


def run_sim(step_s=6.0):
    fl, d = sim_frames()
    generic = classify.load_profile(os.path.join(PROF, "generic.toml"))
    with tempfile.TemporaryDirectory() as td:
        drv = drive.Driver(drive.SimDevice(fl, step_s), generic, td, td, 999, mark=True, sim=True)
        drv.run()
        tsv = open(os.path.join(td, "route-state.tsv")).read()
    return drv, tsv


def problems(drv, tsv):
    probs = []
    if any(i["input"] in ("START", "START+A") and i["state"] == "play" for i in drv.inputs):
        probs.append("START sent in play")
    pre_play = [i for i in drv.inputs if i["state"] != "play" and i["input"]]
    if any(i["input"] == "START" and "; ladder)" in i["why"] for i in pre_play):
        probs.append("START sent before play by the exploration ladder (generic.toml's ladder is [A] only)")
    if "\tplay\t" not in tsv:
        probs.append("never reached play")
    if "mark gameplay" not in tsv:
        probs.append("never marked")
    return probs


def main(argv):
    fails = 0

    # #433 Part C: every scenario below that reaches `unknown` presses and so writes a
    # learned-table record (profile name "generic") -- redirect learned.py's module-level
    # paths to a throwaway directory for this whole run, or every selftest invocation
    # pollutes the real `pathknow/learned/generic.jsonl` a live `--profile generic` run
    # also reads, making both the real table and this file's own test order non-
    # reproducible (caught by running this file twice in a row and diffing the output).
    learned_td = tempfile.mkdtemp(prefix="pathclass-selftest-learned-")
    learned.DIR = os.path.join(learned_td, "learned")
    learned.GLOBAL_PATH = os.path.join(learned.DIR, "_global.jsonl")

    # #433 Part A: no API key path anywhere in drive.py's runtime loop or the files it
    # reads. A reintroduced `ask_model`/ANTHROPIC_API_KEY/etc. (even just a string naming
    # them) fails this, not just a wired-up call -- the owner's ask was to remove the path,
    # not leave it dormant.
    hits = grep_gate()
    ok0 = not hits
    fails += not ok0
    print("%s  grep gate: no API key path in drive.py/classify.py/pathclass.py/drive-profiles/*.toml  %s" %
          ("ok  " if ok0 else "FAIL", "" if ok0 else "; ".join(hits)))

    # fail-closed: classify.Unavailable (no venv/GPU/serve) ends the route, not a blind
    # press and not a model call.
    install_unavailable("no venv")
    fl, d = sim_frames()
    # not the first frame: that one is black (124759-entry.png), and classify.py's own
    # flat-luma check answers it before the pathclass branch is ever reached, so the
    # Unavailable stub would never actually fire. Use a frame classify.py has to ask
    # pathclass about.
    live = os.path.join(d, "124950-entry.png")
    with tempfile.TemporaryDirectory() as td:
        drv = drive.Driver(drive.SimDevice([live], 6.0), classify.load_profile(os.path.join(PROF, "generic.toml")),
                           td, td, 999, mark=True, sim=True)
        rc = drv.run()
    ok = rc == 1 and drv.result == "ROUTE FAIL drive generic: pathclass unavailable (no venv)"
    fails += not ok
    print("%s  fail-closed: pathclass.Unavailable -> ROUTE FAIL, no press  got %s" %
          ("ok  " if ok else "FAIL", drv.result))

    # the recorded sequence: reaches play at the real free-roam frame (124950-entry.png,
    # the moment the owner's run stopped being a blind loop and started wasting time),
    # marks it, and never presses START once there.
    install_stub(sim_answers_ordered())
    drv, tsv = run_sim()
    probs = problems(drv, tsv)
    ok = not probs
    fails += not ok
    print("%s  simpsons run: generic reaches play, marks it, no START in play  %s" %
          ("ok  " if ok else "FAIL", "" if ok else "; ".join(probs)))
    play_inputs = [i for i in drv.inputs if i["state"] == "play"]
    # hold_play only: generic.toml's play_cycle phases are logged as `hold ...`, and the
    # run's end releases them (routebuild1021)
    ok2 = all(i["input"] in ("", "release axes") or i["input"].startswith("hold ") for i in play_inputs)
    fails += not ok2
    print("%s  simpsons run: no presses at all while playing (hold only)  inputs=%s" %
          ("ok  " if ok2 else "FAIL", [i["input"] for i in play_inputs] if not ok2 else "none"))

    # the mutant: a regression that presses START while state == play. Patch Driver.act to
    # do exactly that, re-run the same recorded sequence, and check that `problems()` --
    # the same check the case above just passed under -- now reports it. This is the
    # brief's required mutant: if this check stays green here, the real check above is
    # vacuous.
    real_act = drive.Driver.act

    def mutant_act(self, state, r, frame):
        if state == "play":
            return self.press("START", "mutant: forced START in play (#433 selftest)")
        return real_act(self, state, r, frame)

    drive.Driver.act = mutant_act
    try:
        install_stub(sim_answers_ordered())
        mdrv, mtsv = run_sim()
    finally:
        drive.Driver.act = real_act
    mprobs = problems(mdrv, mtsv)
    ok3 = "START sent in play" in mprobs
    fails += not ok3
    print("%s  mutant (START forced in play) is caught by the same check  %s" %
          ("ok  " if ok3 else "FAIL", mprobs if ok3 else "NOT CAUGHT -- the check above is vacuous"))

    # the title screen must lead to START, not to a wait (#433 Addendum 6): replay AvP
    # Extinction's stalled run. Under the single 0.85 floor this never presses anything (the
    # title screen's own 0.8 stays `unknown`); under the fixed two-floor generic.toml it
    # does, at the last (and only non-wait-class) frame.
    install_stub(avp_answers_ordered())
    fl, d = avp_frames()
    generic = classify.load_profile(os.path.join(PROF, "generic.toml"))
    with tempfile.TemporaryDirectory() as td:
        drv = drive.Driver(drive.SimDevice(fl, 6.0), generic, td, td, 999, mark=True, sim=True)
        drv.run()
    starts = [i for i in drv.inputs if i["input"] == "START"]
    ok4 = len(starts) >= 1
    fails += not ok4
    print("%s  AvP Extinction title screen: generic presses START, not stuck at `unknown`  inputs=%s" %
          ("ok  " if ok4 else "FAIL", [i["input"] for i in drv.inputs]))

    # #433 Part C mutant: a button that `advanced` a screen is suggested FIRST the next
    # time that exact screen (same key, no embedding here) comes up -- before any ladder
    # fallback, which would otherwise always start from the ladder's first rung.
    learned.record("generic", "unknown:test-screen", None, "X", "advanced", 1.0, "run1")
    own, glob = learned.load("generic")
    suggested = learned.suggest(own, glob, "unknown:test-screen", None, [])
    ok5 = suggested == "X"
    fails += not ok5
    print("%s  learned table: a button that `advanced` a screen is suggested first next time  got %s" %
          ("ok  " if ok5 else "FAIL", suggested))

    # #433 Part C mutant (veto): a button that ever `regressed` this screen is never
    # suggested again -- even as the ONLY record for it, where a plain "any record"
    # or "most recent" pick would hand it right back.
    learned.record("generic", "unknown:veto-screen", None, "B", "regressed", 1.0, "run2")
    own, glob = learned.load("generic")
    suggested2 = learned.suggest(own, glob, "unknown:veto-screen", None, [])
    ok6 = suggested2 is None
    fails += not ok6
    print("%s  learned table: a button that `regressed` a screen is never suggested again  got %s" %
          ("ok  " if ok6 else "FAIL", suggested2))

    # #433 Part B mutant: an `unknown` screen that never resolves -- every one of 20
    # captures reads the same confidence-starved answer -- must never Fail. The route's own
    # wall-clock budget (seconds=15, fast_s=1.0) ends it; this exercises the full 8-button
    # ladder (generic.toml has no paused crop, so START is excluded) past one full wrap.
    install_stub([("controller_prompt", 0.1)] * 20)
    fl, d = sim_frames()
    live = os.path.join(d, "124950-entry.png")
    with tempfile.TemporaryDirectory() as td:
        drv = drive.Driver(drive.SimDevice([live] * 20, 1.0), classify.load_profile(os.path.join(PROF, "generic.toml")),
                           td, td, 15.0, mark=True, sim=True)
        rc = drv.run()
    ok7 = (rc == 0 and drv.result == "window-done" and drv.seen == ["unknown"]
           and len(drv.inputs) > 0 and all(b != "START" for (_, b, _) in drv.explored))
    fails += not ok7
    print("%s  never idle-fail: an `unknown` screen that never resolves ends on budget, not Fail  "
          "result=%s inputs=%d explored=%d" %
          ("ok  " if ok7 else "FAIL", drv.result, len(drv.inputs), len(drv.explored)))

    fails += book_tests(learned_td)
    fails += probe_tests()
    fails += loading_tests()
    fails += decay_tests()
    print("pathclass_selftest: %d failure(s)" % fails)
    return 1 if fails else 0


# -- routebuild1021: the lean, the d-pad, the path book -------------------------------
def lean_answer(do="DOWN", top3=(("main_menu", 0.40), ("submenu", 0.30), ("gameplay", 0.05))):
    """A low-confidence (0.40, under generic.toml's 0.7 menu floor) answer whose top-3
    leans menu, with pathclass's own action."""
    return {"state": top3[0][0], "confidence": top3[0][1], "top3": [list(x) for x in top3],
            "action": {"do": do, "why": "selftest"}, "diff": 0.0, "moving": False}


NO_DPAD = dict(dpad_probe=0)   # the lean tests below are about the lean: the d-pad rotation has its own (decay_tests)


def sim(answers, frames, seconds, step_s=1.0, env=None, out=None, drive_set=None):
    """One generic.toml run over `frames` with these stub answers. `env`: TITLE_ID /
    HAKUX_PATHS_DIR for the run (set for the Driver's construction and finish()); `drive_set`
    replaces keys of the profile's [drive] section."""
    install_stub(answers)
    old = {k: os.environ.get(k) for k in (env or {})}
    os.environ.update(env or {})
    try:
        with tempfile.TemporaryDirectory() as td:
            prof = classify.load_profile(os.path.join(PROF, "generic.toml"))
            prof["drive"].update(drive_set or {})
            drv = drive.Driver(drive.SimDevice(frames, step_s), prof, out or td, out or td, seconds, mark=True, sim=True)
            drv.run()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return drv


def report(ok, what, got=""):
    print("%s  %s  %s" % ("ok  " if ok else "FAIL", what, "" if ok else got))
    return 0 if ok else 1


def flat(v):
    return [[v] * 16 for _ in range(12)]


def clear_learned():
    for f in os.listdir(learned.DIR) if os.path.isdir(learned.DIR) else []:
        os.remove(os.path.join(learned.DIR, f))


def book_tests(learned_td):
    fails = 0
    clear_learned()                     # the never-idle case above recorded `changed` for this screen's key
    fl, d = sim_frames()
    live = os.path.join(d, "124950-entry.png")

    # The lean: an `unknown` screen whose top-3 leans menu is pressed with pathclass's own
    # action, not the ladder's first rung (A) -- and DOWN goes out as a hat flick, since
    # hakuX's d-pad buttons do nothing. The mutant reinstates the button: HAT emptied, DOWN
    # is sent as `press DOWN`, and the same check must see it.
    for mutant in (False, True):
        real_hat = dict(drive.HAT)
        if mutant:
            drive.HAT.clear()
        try:
            drv = sim([lean_answer()], [live] * 4, 4.0, drive_set=NO_DPAD)
        finally:
            drive.HAT.update(real_hat)
        first = next((i for i in drv.inputs if i["why"].startswith("explore")), {})
        hat = any(s[1:] == ("axis", "HATY", "max") for s in drv.dev.sent)
        btn = any(s[1:] == ("press", "DOWN") for s in drv.dev.sent)
        ok = first.get("input") == "DOWN" and "leans menu" in first.get("why", "") and hat and not btn
        if mutant:
            fails += report(not ok, "mutant (d-pad as buttons) is caught by the lean/hat check",
                            "NOT CAUGHT -- the check is vacuous")
        else:
            fails += report(ok, "lean: unknown leaning menu presses pathclass's DOWN, sent as HATY max",
                            "first=%s hat=%s button=%s" % (first, hat, btn))

    # The lean against the learned table: a button whose only record on this screen is
    # `none` does not outrank the lean (min_rank=2); one that `changed` it does.
    key = "unknown:pathclass:low-confidence"
    learned.record("generic", key, None, "X", "none", 1.0, "selftest")
    drv = sim([lean_answer()], [live] * 4, 4.0, drive_set=NO_DPAD)
    first = next((i for i in drv.inputs if i["why"].startswith("explore")), {})
    fails += report(first.get("input") == "DOWN", "lean beats a learned button recorded only as `none`",
                    "first=%s" % first)
    clear_learned()
    learned.record("generic", key, None, "X", "none", 1.0, "selftest")
    real_suggest = learned.suggest
    learned.suggest = lambda own, glob, k, emb, tried, min_rank=0: real_suggest(own, glob, k, emb, tried)
    try:
        drv = sim([lean_answer()], [live] * 4, 4.0, drive_set=NO_DPAD)
    finally:
        learned.suggest = real_suggest
    first = next((i for i in drv.inputs if i["why"].startswith("explore")), {})
    fails += report(first.get("input") != "DOWN", "mutant (min_rank ignored) is caught by the same check",
                    "NOT CAUGHT -- the check is vacuous")
    clear_learned()                     # that run's own DOWN was recorded too (no embedding here: `changed`)
    learned.record("generic", key, None, "Y", "changed", 2.0, "selftest")
    drv = sim([lean_answer()], [live] * 4, 4.0, drive_set=NO_DPAD)
    first = next((i for i in drv.inputs if i["why"].startswith("explore")), {})
    fails += report(first.get("input") == "Y" and first["why"].endswith("learned)"),
                    "a learned button that `changed` this screen beats the lean", "first=%s" % first)
    clear_learned()

    # A play lean holds the play input and presses nothing; START never goes out on a
    # screen whose top-3 gives gameplay LEAN_PLAY_START or more.
    drv = sim([lean_answer(top3=(("gameplay", 0.6), ("cutscene", 0.2), ("main_menu", 0.1)))], [live] * 4, 4.0)
    presses = [i for i in drv.inputs if not i["input"].startswith(("hold", "release"))]
    held = any(i["input"].startswith("hold ") for i in drv.inputs)
    fails += report(not presses and held, "lean play: holds the play input, presses nothing",
                    "presses=%s held=%s" % (presses, held))
    drv = sim([lean_answer(do="START", top3=(("title_screen", 0.4), ("main_menu", 0.2), ("gameplay", 0.2)))],
              [live] * 8, 8.0)
    starts = [i for i in drv.inputs if "START" in i["input"]]
    fails += report(not starts and any(i["why"].startswith("explore") for i in drv.inputs),
                    "lean menu with gameplay at 0.2 of the top-3: START is never sent",
                    "inputs=%s" % [i["input"] for i in drv.inputs])

    # pathbook.build: same-screen DOWN, DOWN, A is a cursor walk, not a loop; a loop with
    # no menu step in it (an attract video coming round) is cut; one through a menu is not.
    A, B, C, D = flat(10), flat(100), flat(200), flat(50)

    def e(t, sig, btn, after, menu, d=90.0, ch=0.5, state="unknown"):
        return dict(t=t, state=state, cls=None, button=btn, why="", menu=menu, sig=sig, in_play=False,
                    after_state=after, after_d=d, after_changed=ch)
    walk = [e(1, A, "DOWN", "main_menu", True, d=1.0, ch=0.03), e(3, A, "DOWN", "main_menu", True, d=1.0, ch=0.03),
            e(5, A, "A", "main_menu", True), e(7, B, "A", "loading", True),
            e(8, B, "B", "main_menu", True, d=0.0, ch=0.0)]       # nothing moved: dropped
    p = pathbook.build(walk, [], dict(title_id="ffff0001", complete=True, time_to_play_s=20.0))
    acts = [" ".join(s["action"]) for s in p["steps"]]
    fails += report(acts == ["DOWN", "DOWN", "A", "A"], "pathbook: same-screen DOWN, DOWN, A kept; a dead press dropped",
                    "got %s" % acts)
    loop = [e(1, C, "A", "cutscene", False), e(3, D, "A", "cutscene", False), e(5, C, "START", "title", False),
            e(7, B, "A", "main_menu", True)]
    acts = [" ".join(s["action"]) for s in pathbook.build(loop, [], {})["steps"]]
    fails += report(acts == ["START", "A"], "pathbook: a loop with no menu step is cut", "got %s" % acts)
    mloop = [dict(x, menu=True) for x in loop]
    acts = [" ".join(s["action"]) for s in pathbook.build(mloop, [], {})["steps"]]
    fails += report(acts == ["A", "A", "START", "A"], "pathbook: a loop through a menu is kept (the cursor is unseen)",
                    "got %s" % acts)

    # pathbook.save/load: faster complete replaces; slower or incomplete does not; a
    # complete pathfind path is not hidden by an incomplete drive one.
    pd = tempfile.mkdtemp(prefix="pathbook-selftest-")
    repo = tempfile.mkdtemp(prefix="pathbook-selftest-repo-")
    real_repo = pathbook.REPO_PATHS
    pathbook.REPO_PATHS = repo
    try:
        mk = lambda secs, done: pathbook.build(walk, [], dict(title_id="FFFF0001", complete=done, time_to_play_s=secs,
                                                             furthest=3))
        r1 = pathbook.save(mk(60.0, True), pd)[0]
        r2 = pathbook.save(mk(90.0, True), pd)[0]
        r3 = pathbook.save(mk(40.0, False), pd)[0]
        r4 = pathbook.save(mk(40.0, True), pd)[0]
        fails += report((r1, r2, r3, r4) == (True, False, False, True),
                        "pathbook.save: first, slower, incomplete, faster -> written, kept, kept, written",
                        "got %s" % ((r1, r2, r3, r4),))
        with open(os.path.join(repo, "FFFF0002.json"), "w") as f:
            json.dump(dict(title_id="FFFF0002", complete=True, minutes=3.0, steps=[dict(state="title_screen",
                      action=["START"], sig=A)]), f)
        with open(os.path.join(pd, "FFFF0002.json"), "w") as f:
            json.dump(mk(None, False), f)
        got, f = pathbook.load("ffff0002", [pd, repo])
        fails += report(f and f.startswith(repo), "pathbook.load: a complete pathfind path beats an incomplete drive one",
                        "got %s" % f)
        # An unfinished pathfind path (Blinx 2's 4D530065: `gave-up`, 9 steps) is not
        # replaced by an unfinished drive run however far that got; a finished one is.
        with open(os.path.join(repo, "FFFF0003.json"), "w") as f:
            json.dump(dict(title_id="FFFF0003", complete=False, result="gave-up", steps=[dict(state="title_screen",
                      action=["START"], sig=A)]), f)
        mk3 = lambda done: pathbook.build(walk, [], dict(title_id="FFFF0003", complete=done, furthest=6,
                                                         time_to_play_s=50.0 if done else None))
        r5, r6 = pathbook.save(mk3(False), pd)[0], pathbook.save(mk3(True), pd)[0]
        fails += report((r5, r6) == (False, True),
                        "pathbook.save: an unfinished pathfind path is kept over an unfinished drive run, "
                        "replaced by a finished one", "got %s" % ((r5, r6),))
    finally:
        pathbook.REPO_PATHS = real_repo

    # Replay: a book step whose screen matches is pressed before the policy, by name; a
    # step that never moves its screen is given up after REPLAY_TRIES presses. The mutant
    # never gives up (the weaker rule: a stale book holds the run on one screen).
    sig = pathbook.sig_list(pathbook.signature(live))
    with open(os.path.join(pd, "FFFF0003.json"), "w") as f:
        json.dump(dict(title_id="FFFF0003", complete=True, time_to_play_s=5.0, builder="drive",
                       steps=[dict(state="cutscene", action=["Y"], sig=sig, useful=True)]), f)
    env = {"TITLE_ID": "ffff0003", "HAKUX_PATHS_DIR": pd}
    for mutant in (False, True):
        real = drive.REPLAY_TRIES
        drive.REPLAY_TRIES = 99 if mutant else real
        try:
            drv = sim([("controller_prompt", 0.1)], [live] * 20, 20.0, step_s=1.0, env=env)
        finally:
            drive.REPLAY_TRIES = real
        book = [i for i in drv.inputs if i["why"].startswith("book step")]
        ok = (len(book) == drive.REPLAY_TRIES and all(i["input"] == "Y" for i in book)
              and any(i["why"].startswith("explore") for i in drv.inputs))
        if mutant:
            fails += report(not ok, "mutant (book step never given up) is caught", "NOT CAUGHT -- the check is vacuous")
        else:
            fails += report(ok, "replay: the book's Y pressed %d times on its screen, then the policy takes over"
                            % drive.REPLAY_TRIES, "book=%s" % [(i["t"], i["input"]) for i in book])

    # End to end: a TITLE_ID run that reaches play saves the title's path; the trail is
    # written either way.
    out = tempfile.mkdtemp(prefix="pathbook-selftest-run-")
    drv = sim(sim_answers_ordered(), fl, 999, step_s=6.0, env={"TITLE_ID": "ffff0004", "HAKUX_PATHS_DIR": pd},
              out=out)
    tr = json.load(open(os.path.join(out, "route-trail.json")))
    saved = pathbook._read(os.path.join(pd, "FFFF0004.json"))
    fails += report(tr["meta"]["complete"] and saved and saved["complete"] and saved["steps"],
                    "end to end: a run that marks play writes its trail and saves the title's path",
                    "complete=%s saved=%s" % (tr["meta"]["complete"], bool(saved)))
    drv = sim(sim_answers_ordered(), fl, 999, step_s=6.0, env={"TITLE_ID": "ffff0004", "HAKUX_PATHS_DIR": pd})
    book = [i for i in drv.inputs if i["why"].startswith("book step")]
    fails += report(book and book[0]["input"] == " ".join(saved["steps"][0]["action"]),
                    "end to end: the next run of that title replays the saved path from its first step",
                    "book=%s" % [(i["t"], i["input"], i["why"]) for i in book])
    return fails


# -- playprobe1021: the play probe ------------------------------------------------------
def held_now(dev):
    """The sim device's pad as the game would see it: buttons down, last value per axis,
    replayed from what it was sent (SimDevice records, it does not react)."""
    btn, axis = set(), {}
    for s in dev.sent:
        if s[1] == "hold":
            btn.add(s[2])
        elif s[1] == "release":
            btn.discard(s[2])
        elif s[1] == "axis":
            axis[s[2]] = s[3]
    return btn, axis


class ReactiveStub:
    """pathclass, but the picture answers the pad: `moves(dev)` says whether the screen
    changes on this capture, given what the device has been sent so far. The recorded-answer
    stub cannot show a probe working -- nothing it is sent changes what it says next.
    confidence 0.5 is under the gameplay floor (an `unknown` leaning play, HP2's case);
    0.9 is a confident gameplay, `play` when the screen moves and `stalled` when it does not."""

    def __init__(self, dev, moves, conf=0.5):
        self.dev, self.moves, self.conf = dev, moves, conf

    def classify(self, frame, prev, context):
        d = 0.3 if self.moves(self.dev) else 0.0
        return {"state": "gameplay", "confidence": self.conf, "moving": d >= 0.05, "diff": d,
                "top3": [["gameplay", 0.6], ["cutscene", 0.2], ["main_menu", 0.1]], "action": {"do": "A", "why": "selftest"}}


def probe_run(moves, seconds, conf=0.5, drive_set=None, inp_set=None, make_stub=None, prof_set=None):
    """One generic.toml run against a ReactiveStub (or `make_stub(dev)`); returns (driver, device).
    `prof_set` replaces top-level profile keys (None removes one); the run's route-state.tsv is
    left on the driver as `drv.tsv_text`."""
    fl, d = sim_frames()
    live = os.path.join(d, "124950-entry.png")
    dev = drive.SimDevice([live] * (int(seconds) + 10), 1.0)
    stub = make_stub(dev) if make_stub else ReactiveStub(dev, moves, conf)
    classify._PATHCLASS_CLIENT = stub
    classify.pathclass_client = lambda: stub
    prof = classify.load_profile(os.path.join(PROF, "generic.toml"))
    prof["drive"].update(drive_set or {})
    prof["input"].update(inp_set or {})
    for k, v in (prof_set or {}).items():
        prof.pop(k, None) if v is None else prof.__setitem__(k, v)
    with tempfile.TemporaryDirectory() as td:
        drv = drive.Driver(dev, prof, td, td, seconds, mark=True, sim=True)
        drv.run()
        drv.tsv_text = open(os.path.join(td, "route-state.tsv")).read()
    return drv, dev


def outcomes(drv):
    return [(p["input"], p["outcome"]) for p in drv.probes]


def probe_tests():
    fails = 0
    clear_learned()
    real = dict(mark_input=drive.Driver.mark_input, probe_axes=drive.Driver.probe_axes,
                probe_release=drive.Driver.probe_release, suggest=learned.suggest, matches=learned._matches)

    # HP2: the gas is not on the stick. Nothing in the base cycle moves the screen; only R1
    # held does. The probe holds A, X, Y (misses), then R1, which moves it on two captures
    # running, and R1 stays held; it is let go when the run ends.
    gas_r1 = lambda dev: "R1" in held_now(dev)[0]
    drv, dev = probe_run(gas_r1, 70)
    want = [("A", "missed"), ("X", "missed"), ("Y", "missed"), ("R1", "won")]
    fails += report(outcomes(drv) == want and drv.result == "window-done",
                    "probe: A, X, Y miss and R1 is held until the screen moves; the run is not failed",
                    "got %s result=%s" % (outcomes(drv), drv.result))
    r1 = [s[1] for s in dev.sent if len(s) > 2 and s[2] == "R1"]
    fails += report(r1 == ["hold", "release"] and not drv.pheld and held_now(dev)[0] == set(),
                    "probe: the winner stays down through the run (one hold) and is let go at the end",
                    "R1 events=%s pheld=%s" % (r1, drv.pheld))
    recs = [(r["button"], r["outcome"]) for r in learned.load("generic")[0] if r.get("kind") == "play"]
    fails += report(recs == [("A", "none"), ("X", "none"), ("Y", "none"), ("R1", "advanced")],
                    "probe: each probe is a learned record of kind `play` (screen, input, motion)", "got %s" % recs)
    rec = next((r for r in learned.load("generic")[0] if r.get("button") == "R1"), {})
    fails += report(rec.get("key") == drive.PROBE_KEY and rec.get("motion", 0) >= classify.MOVING_BAR
                    and rec.get("before") == 0.0 and rec.get("held_s", 0) > 0,
                    "probe: the record carries the motion before and under the hold and how long it was held",
                    "rec=%s" % rec)
    marks = [m for m in dev.log if m.startswith(("input t=", "play-probe"))]
    fails += report(any(m.startswith("play-probe won R1") for m in marks)
                    and sum(m.startswith("play-probe missed") for m in marks) == 3
                    and any(m.startswith("input t=") and "probe hold R1" in m for m in marks)
                    and any(m.startswith("input t=") and "hold LY min RT max" in m for m in marks),
                    "probe: every probe and every play input goes to logcat, where the fps lines are",
                    "marks=%s" % marks[:6])
    drive.Driver.mark_input = lambda *a: None
    try:
        drv2, dev2 = probe_run(gas_r1, 70)
    finally:
        drive.Driver.mark_input = real["mark_input"]
    fails += report(not any(m.startswith("input t=") for m in dev2.log),
                    "mutant (inputs not written to logcat) is caught by the same check", "NOT CAUGHT -- vacuous")

    # The weaker rule: probe off. The leans-play branch holds the stick and RT and nothing
    # else, which is the 100 s at 0 MPH. The same check must see it.
    clear_learned()
    drv3, dev3 = probe_run(gas_r1, 70, drive_set={"probe_idle_s": 0.0})
    fails += report(not drv3.probes and "R1" not in held_now(dev3)[0] and not any(s[1:] == ("hold", "R1") for s in dev3.sent),
                    "mutant (probe off) never holds R1: the check on the winner above is not vacuous",
                    "probes=%s" % outcomes(drv3))

    # A second run of the title tries what moved a screen like this one first.
    clear_learned()
    probe_run(gas_r1, 70)
    drv4, _ = probe_run(gas_r1, 70)
    fails += report(outcomes(drv4)[:1] == [("R1", "won")] and drv4.probes[0]["origin"] == "learned",
                    "probe: the next run tries the learned input first and wins on it", "got %s" % drv4.probes[:1])
    learned.suggest = lambda *a, **k: None
    try:
        drv5, _ = probe_run(gas_r1, 70)
    finally:
        learned.suggest = real["suggest"]
    fails += report(outcomes(drv5)[:1] == [("A", "missed")],
                    "mutant (learned play inputs ignored) is caught by the same check", "got %s" % outcomes(drv5)[:1])

    # A play record is never an explore answer: its embedding can sit near a menu's.
    clear_learned()
    e1 = [1.0, 0.0]
    learned.record("generic", drive.PROBE_KEY, e1, "R1", "advanced", 1.0, "selftest", kind="play", motion=0.3)
    own, glob = learned.load("generic")
    ex = learned.suggest(own, glob, "unknown:pathclass:low-confidence", e1, [])
    pl = learned.suggest(own, glob, drive.PROBE_KEY, e1, [], min_rank=3, kind="play")
    fails += report(ex is None and pl == "R1", "learned: a play record is suggested to a probe and never to explore",
                    "explore=%s play=%s" % (ex, pl))
    both = lambda recs, k, e, kind="explore": real["matches"](recs, k, e, "explore") + real["matches"](recs, k, e, "play")
    learned._matches = both
    try:
        ex2 = learned.suggest(own, glob, "unknown:pathclass:low-confidence", e1, [])
    finally:
        learned._matches = real["matches"]
    fails += report(ex2 == "R1", "mutant (kind ignored) is caught by the same check", "NOT CAUGHT -- vacuous")
    clear_learned()

    # One moving capture is not motion: a hold that makes the picture blink (a camera cut, a
    # button's flash) must not be taken for the player moving. probe_hits=2 rejects it; the
    # mutant at 1 takes it.
    def blink(dev, seen={"set": None}):
        cur = frozenset(held_now(dev)[0])
        if cur != seen["set"]:
            seen["set"] = cur
            return bool(cur)
        return False
    drv6, _ = probe_run(blink, 200)
    fails += report(drv6.probes and all(o == "missed" for _, o in outcomes(drv6)),
                    "probe: a single moving capture under a hold is not a win", "got %s" % outcomes(drv6)[:3])
    clear_learned()
    drv7, _ = probe_run(blink, 200, drive_set={"probe_hits": 1})
    fails += report(any(o == "won" for _, o in outcomes(drv7)),
                    "mutant (one moving capture wins) is caught by the same check", "NOT CAUGHT -- vacuous")

    # Nothing moves it: the step FAILS, naming the probe, after probe_rounds empty rounds --
    # for a screen the classifier calls confident gameplay (`stalled`) as for one it only
    # leans to. The 40 s stall Fail and the blind stall_cycle do not run ahead of the probe.
    clear_learned()
    never = lambda dev: False
    for conf, what in ((0.5, "unknown leaning play"), (0.9, "stalled gameplay")):
        drv8, dev8 = probe_run(never, 400, conf=conf)
        fails += report("play probe: 3 rounds" in (drv8.result or "") and drv8.t() > 60 and not drv8.pheld
                        and drv8.escapes == 0 and len(drv8.probes) == 3 * len(drive.PROBE_LADDER),
                        "probe: nothing moves a %s screen -> ROUTE FAIL naming the probe, nothing left held" % what,
                        "result=%s t=%.0f probes=%d escapes=%d" % (drv8.result, drv8.t(), len(drv8.probes), drv8.escapes))
    drv9, _ = probe_run(never, 400, conf=0.9, drive_set={"probe_idle_s": 0.0})
    fails += report("stalled" in (drv9.result or "") and "play probe" not in (drv9.result or ""),
                    "probe off: a stalled screen still ends in the old stall Fail (a profile that does not opt in is unchanged)",
                    "result=%s" % drv9.result)

    # After a win, the screen going still again (a wall) starts a new round: the old winner
    # is let go first and tried last, and the input that works now wins.
    clear_learned()
    wall = lambda dev: (("A" in held_now(dev)[0]) if dev.clock < 30 else ("X" in held_now(dev)[0]))
    drv10, dev10 = probe_run(wall, 90)
    ev = [(s[1], s[2]) for s in dev10.sent if len(s) > 2 and s[1] in ("hold", "release") and s[2] in ("A", "X")]
    fails += report(outcomes(drv10)[:2] == [("A", "won"), ("X", "won")] and [p["round"] for p in drv10.probes[:2]] == [1, 2]
                    and ev.index(("release", "A")) < ev.index(("hold", "X")),
                    "probe: when the winner stops moving the screen a new round lets it go and finds the one that does",
                    "got %s events=%s" % (outcomes(drv10)[:3], ev))
    drive.Driver.probe_release = lambda self, tok: None
    try:
        drv11, dev11 = probe_run(wall, 90)
    finally:
        drive.Driver.probe_release = real["probe_release"]
    fails += report(not any(s[1] == "release" for s in dev11.sent if len(s) > 2),
                    "mutant (nothing is ever released) is caught by the same checks", "NOT CAUGHT -- vacuous")

    # A stick candidate must beat the play cycle for its axis: the cycle holds LY min and
    # re-sends it every capture, so a probe holding LY max moves nothing unless hold_play
    # steps aside.
    clear_learned()
    reverse = lambda dev: held_now(dev)[1].get("LY") == "max"
    def ly_after_win(dev):
        vals = [s[3] for s in dev.sent if s[1] == "axis" and s[2] == "LY"]
        return vals[vals.index("max"):-1] if "max" in vals else None   # the last is the end-of-run release

    drv12, dev12 = probe_run(reverse, 90)
    tail = ly_after_win(dev12)
    fails += report(outcomes(drv12)[-1:] == [("LY:max", "won")] and tail and set(tail) == {"max"},
                    "probe: a held stick candidate is not overwritten by the play cycle (LY stays max once held)",
                    "got %s LY after=%s" % (outcomes(drv12)[-2:], tail and sorted(set(tail))))
    clear_learned()          # else the mutant starts on the learned LY:max, at a cycle phase that happens to suit it
    drive.Driver.probe_axes = lambda self: set()
    try:
        drv13, dev13 = probe_run(reverse, 90)
    finally:
        drive.Driver.probe_axes = real["probe_axes"]
    tail13 = ly_after_win(dev13)
    fails += report(("LY:max", "won") not in outcomes(drv13) and (tail13 is None or set(tail13) != {"max"}),
                    "mutant (the cycle keeps its axis) is caught by the same check", "NOT CAUGHT -- vacuous")
    clear_learned()

    # A profile's own list is checked like play_tap: START pauses live play, B backs out of a
    # menu the classifier may have miscalled as play.
    for bad in ("START", "B", "SELECT"):
        try:
            probe_run(never, 5, inp_set={"probe": ["A", bad]})
            fails += report(False, "probe: input.probe naming %s is refused" % bad, "no SystemExit")
        except SystemExit:
            fails += report(True, "probe: input.probe naming %s is refused" % bad)
    return fails


class LoadingStub:
    """pathclass calling a screen `loading` at 0.9 (over generic.toml's 0.7 menu floor), the
    way it called NFS Hot Pursuit 2's "A Advance" briefing for 530 s. `ends(dev)` says when it
    stops being one: the game's own load finishing, or a button that advances it; then it is a
    confident gameplay on a moving picture."""

    def __init__(self, dev, ends):
        self.dev, self.ends = dev, ends

    def classify(self, frame, prev, context):
        if self.ends(self.dev):
            return {"state": "gameplay", "confidence": 0.95, "moving": True, "diff": 0.3,
                    "top3": [["gameplay", 0.9], ["cutscene", 0.05], ["main_menu", 0.03]], "action": {"do": "A", "why": "selftest"}}
        return {"state": "loading", "confidence": 0.9, "moving": True, "diff": 0.05,
                "top3": [["loading", 0.9], ["main_menu", 0.05], ["gameplay", 0.02]], "action": {"do": "A", "why": "selftest"}}


def loading_tests():
    """loadstuck1021: a `loading` that never ends is handled as `unknown` after loading_stuck_s."""
    fails = 0
    clear_learned()
    a_sent = lambda dev: any(s[1:] == ("press", "A") for s in dev.sent)
    presses = lambda dev: [s for s in dev.sent if len(s) > 2 and s[1] == "press"]
    run = lambda ends, seconds, **ds: probe_run(None, seconds, drive_set=dict(dpad_probe=0, **ds),
                                                make_stub=lambda dev: LoadingStub(dev, ends))

    # the HP2 briefing: `loading` for as long as nothing is pressed, gameplay once A is.
    drv, dev = run(a_sent, 200)
    first = presses(dev)[0] if presses(dev) else None
    fails += report(first is not None and first[2] == "A" and 90.0 <= first[0] <= 100.0 and "play" in drv.seen,
                    "loading: a `loading` that outlasts loading_stuck_s (90) gets an A, and the run reaches play",
                    "first press %s seen=%s" % (first, drv.seen))
    fails += report(not [s for s in presses(dev) if s[0] < 90.0],
                    "loading: nothing is pressed before the bar", "early presses %s" % [s for s in presses(dev) if s[0] < 90.0])
    fails += report(any(m.startswith("loading-overstay") for m in dev.log),
                    "loading: the overstay is written to logcat, so a long wait is visible", "log=%s" % dev.log[:4])
    fails += report(("unknown:pathclass:loading", "A", "advanced") in drv.explored,
                    "loading: the press that ended it is a learned record (screen, A, advanced)", "explored=%s" % drv.explored)

    # the weaker rule: no bar. The same screen is waited on for the whole run -- the 530 s.
    clear_learned()
    drv2, dev2 = run(a_sent, 200, loading_stuck_s=0.0)
    fails += report(not presses(dev2) and "play" not in drv2.seen,
                    "mutant (loading waited out for ever) never presses: the check above is not vacuous",
                    "presses=%s seen=%s" % (presses(dev2)[:2], drv2.seen))

    # a real load that ends by itself inside the bar is left alone.
    clear_learned()
    ends60 = lambda dev: dev.clock >= 60.0
    # (play's own A tap starts once the load is over, so only presses before 60 s are into the load)
    into_load = lambda dev: [s for s in presses(dev) if s[0] < 60.0]
    drv3, dev3 = run(ends60, 200)
    fails += report(not into_load(dev3) and "play" in drv3.seen,
                    "loading: a load that ends on its own inside the bar gets no press", "presses=%s seen=%s" % (into_load(dev3)[:2], drv3.seen))
    clear_learned()
    drv4, dev4 = run(ends60, 200, loading_stuck_s=30.0)
    fails += report(bool(into_load(dev4)),
                    "mutant (bar lowered to 30 s) presses into a real load: the check above is not vacuous",
                    "presses=%s" % presses(dev4)[:2])

    # decaydpad1022: the overstay hands the screen to the same policy as any unknown, so with the d-pad
    # rotation on it opens with UP, DOWN, LEFT, RIGHT -- and the A (which is what ended it) follows them
    clear_learned()
    drv5, dev5 = probe_run(None, 200, make_stub=lambda dev: LoadingStub(dev, a_sent))
    fl5, pr5 = [t for (t, _, _) in hat_flicks(dev5)], presses(dev5)
    fails += report(len(fl5) >= 4 and min(fl5) >= 90.0 and bool(pr5) and pr5[0][2] == "A" and pr5[0][0] > fl5[3]
                    and "play" in drv5.seen,
                    "loading: past the bar the d-pad rotation runs first (UP DOWN LEFT RIGHT), then the A that ends it",
                    "flicks %s presses %s seen=%s" % (fl5[:5], pr5[:2], drv5.seen))
    clear_learned()
    return fails


# -- decaydpad1022: the floor falls over a low-confidence stretch, and the d-pad is pressed meanwhile -----
class DecayStub:
    """pathclass reading one screen at a fixed confidence (`conf`) as `state`, with a top-3 that
    leans nowhere (no press from the lean). Its embedding is one-hot on how many HATY flicks the
    device has been sent, so UP and DOWN move the picture (settle_explore reads a new embedding as
    `changed`) and LEFT and RIGHT do not; `diff` is 0 so nothing else moves it."""

    def __init__(self, dev, conf, state="main_menu", top3=None):
        self.dev, self.conf, self.state = dev, conf, state
        self.top3 = top3 or [["boot", 0.1], ["loading", 0.1], ["logo", 0.1]]

    def classify(self, frame, prev, context):
        n = sum(1 for s in self.dev.sent if len(s) > 3 and s[1] == "axis" and s[2] == "HATY" and s[3] in ("min", "max"))
        emb = [0.0] * 16
        emb[n % 16] = 1.0
        return {"state": self.state, "confidence": self.conf, "moving": False, "diff": 0.0, "embedding": emb,
                "top3": self.top3, "action": {"do": "A", "why": "selftest"}}


def hat_flicks(dev):
    """The d-pad flicks sent, in order, as (time, axis, value): a hat axis taken off rest."""
    return [(s[0], s[2], s[3]) for s in dev.sent if len(s) > 3 and s[1] == "axis" and s[2] in ("HATX", "HATY") and s[3] != "mid"]


def tsv_states(drv):
    rows = [l.split("\t") for l in drv.tsv_text.splitlines()[1:] if l and not l.startswith("#")]
    return [(float(r[0]), r[1], r[2]) for r in rows]


def decay_tests():
    """The floor in force falls with every capture running that stayed under it (classify.decay_floor,
    the profile's `classifier_decay_*`), and an unknown stretch opens with the d-pad, UP DOWN LEFT
    RIGHT (drive.py DPAD_ROTATION), instead of waiting."""
    fails = 0
    clear_learned()
    df = classify.decay_floor
    HAT_ORDER = [("HATY", "min"), ("HATY", "max"), ("HATX", "min"), ("HATX", "max")]
    order_of = lambda dev: [(a, v) for (_, a, v) in hat_flicks(dev)]

    def run(conf, seconds, state="main_menu", top3=None, ds=None, ps=None, keep=False):
        if not keep:
            clear_learned()     # a run's own presses are recorded, and the next run's first screen would match them
        return probe_run(None, seconds, drive_set=ds, prof_set=ps, make_stub=lambda dev: DecayStub(dev, conf, state, top3))
    presses_of = lambda dev: [s for s in dev.sent if len(s) > 2 and s[1] == "press"]

    # the schedule: step 0 is the profile's own floor, step k is steps[k-1], the last entry holds,
    # and nothing a profile lists can raise a floor above its own
    steps = [0.55, 0.45, 0.40, 0.35]
    got = [df(0.7, steps, k) for k in (0, 1, 2, 3, 4, 5, 40)]
    fails += report(got == [0.7, 0.55, 0.45, 0.40, 0.35, 0.35, 0.35],
                    "decay: the floor is the profile's at step 0, steps[k-1] at step k, the last entry holds", "got %s" % got)
    fails += report(df(0.3, [0.9, 0.2], 1) == 0.3 and df(0.7, None, 5) == 0.7 and df(0.7, [], 5) == 0.7,
                    "decay: a list cannot raise a floor above its own; no list is the floor for ever (a hand-tuned profile)")

    # the shipped numbers: 3-5 steps (owner 2026-10-22), stopping where the held-out set stops giving
    # answers worth taking (menu: 0.30 jumps wrong-other from 1 to 5; gameplay: no gameplay answer under 0.55)
    g = classify.load_profile(os.path.join(PROF, "generic.toml"))
    dm, dg = g["classifier_decay_menu"], g["classifier_decay_gameplay"]
    fails += report(3 <= len(dm) <= 5 and 3 <= len(dg) <= 5 and dm == sorted(dm, reverse=True) and dg == sorted(dg, reverse=True)
                    and dm[0] < g["classifier_confidence_menu"] and dg[0] < g["classifier_confidence"]
                    and min(dm) >= 0.35 and min(dg) >= 0.60,
                    "decay: generic.toml's lists are 3-5 steep steps that stop at the measured limits (menu 0.35, gameplay 0.60)",
                    "menu %s gameplay %s" % (dm, dg))

    # a 0.5 menu answer is `unknown` at the profile's 0.7 and at step 1 (0.55), named at step 2 (0.45):
    # the third capture, not the 45th second
    drv, dev = run(0.5, 20, ds=dict(dpad_probe=0))
    st = tsv_states(drv)
    fails += report(len(st) > 3 and [s for (_, s, _) in st[:2]] == ["unknown", "unknown"] and st[2][1] == "main_menu"
                    and [src for (_, _, src) in st[:2]] == ["pathclass:low-confidence"] * 2,
                    "decay: a 0.5 menu answer is unknown for two captures and named on the third", "states %s" % st[:5])
    # ... and it stays named: the floor stays down until pathclass is sure at its OWN floor
    fails += report(len(st) > 3 and all(s == "main_menu" for (_, s, _) in st[2:]),
                    "decay: once named under the fallen floor it stays named (no flip-flop back to unknown)",
                    "states %s" % [s for (_, s, _) in st])
    # mutant: the floor does not fall -> never named
    real_df = classify.decay_floor
    classify.decay_floor = lambda full, steps, step: full
    try:
        drvm, _ = run(0.5, 20, ds=dict(dpad_probe=0))
    finally:
        classify.decay_floor = real_df
    fails += report(not [1 for (_, s, _) in tsv_states(drvm) if s == "main_menu"],
                    "mutant (floor never falls) leaves the 0.5 screen unknown: the check above is not vacuous")
    # mutant: the floor resets the moment a lowered floor names the screen -> flip-flop
    real_cf = classify.classify_frame

    def strip_decayed(*a, **k):
        r = real_cf(*a, **k)
        r.pop("decayed", None)
        return r
    classify.classify_frame = strip_decayed
    try:
        drvf, _ = run(0.5, 20, ds=dict(dpad_probe=0))
    finally:
        classify.classify_frame = real_cf
    sf = [s for (_, s, _) in tsv_states(drvf)]
    fails += report(sf[2:4] == ["main_menu", "unknown"],
                    "mutant (floor resets on a decayed acceptance) flip-flops main_menu/unknown: the no-flip-flop check is not vacuous",
                    "states %s" % sf[:6])

    # the gameplay list is its own: 0.80 is under 0.85 and over 0.75 (step 1), so a gameplay answer
    # at 0.80 is named on the second capture, and one at 0.5 never is
    drvg, _ = run(0.80, 12, state="gameplay", ds=dict(dpad_probe=0))
    sg = tsv_states(drvg)
    fails += report(len(sg) > 2 and sg[0][1] == "unknown" and sg[1][1] in ("play", "stalled"),
                    "decay: a 0.80 gameplay answer is named on the second capture (gameplay list 0.75 at step 1)", "states %s" % sg[:3])
    drvg2, _ = run(0.5, 30, state="gameplay", ds=dict(dpad_probe=0))
    fails += report(all(s == "unknown" for (_, s, _) in tsv_states(drvg2)),
                    "decay: a 0.5 gameplay answer is never named, however long it lasts (the list stops at 0.60)")

    # the d-pad: UP, DOWN, LEFT, RIGHT, one per press, as hat flicks, before the ladder's A
    drv, dev = run(0.1, 40, state="boot")
    flicks = hat_flicks(dev)
    presses = presses_of(dev)
    t4 = flicks[3][0] if len(flicks) >= 4 else 1e9
    fails += report(order_of(dev)[:4] == HAT_ORDER,
                    "dpad: an unknown stretch opens with UP, DOWN, LEFT, RIGHT, sent as hat flicks (HATY min/max, HATX min/max)",
                    "flicks %s" % order_of(dev)[:6])
    fails += report(bool(presses) and presses[0][2] == "A" and presses[0][0] > t4,
                    "dpad: the ladder's A comes after the rotation, never before it", "presses %s t4=%s" % (presses[:2], t4))
    fails += report(drv.result == "window-done", "dpad: a stretch nothing resolves still ends on the budget, never a Fail",
                    "result=%s" % drv.result)
    # mutant: the profile does not opt in -> the first press is the ladder's A and no flick leads
    drvm, devm = run(0.1, 40, state="boot", ds=dict(dpad_probe=0))
    fails += report(order_of(devm)[:4] != HAT_ORDER and presses_of(devm) and presses_of(devm)[0][2] == "A",
                    "mutant (dpad_probe = 0) opens with the ladder's A, not UP: the check above is not vacuous",
                    "flicks %s" % order_of(devm)[:3])

    # what the d-pad found is written down: UP and DOWN moved the picture, LEFT and RIGHT did not
    verdict = [m for m in dev.log if m.startswith("dpad-probe")]
    want = {"UP": "changed", "DOWN": "changed", "LEFT": "none", "RIGHT": "none"}
    fails += report(bool(verdict) and "2/4 moved the picture" in verdict[0] and bool(drv.dpad_log)
                    and drv.dpad_log[0]["results"] == want and drv.dpad_log[0]["moved"] == 2,
                    "dpad: the verdict (2 of 4 moved the picture) is logged and kept for route-solution.json",
                    "log=%s dpad_log=%s" % (verdict[:1], drv.dpad_log[:1]))
    real_v = drive.Driver.dpad_verdict
    drive.Driver.dpad_verdict = lambda self: None
    try:
        drvv, devv = run(0.1, 40, state="boot")
    finally:
        drive.Driver.dpad_verdict = real_v
    fails += report(not [m for m in devv.log if m.startswith("dpad-probe")],
                    "mutant (verdict not written) leaves no dpad-probe line: the check above is not vacuous")
    marks = [m for m in dev.log if m.startswith("input t=") and "dpad probe" in m]
    fails += report(len(marks) == 4,
                    "dpad: each flick is an `input` line in logcat, tagged with its step of the rotation (for the fps report)",
                    "log=%s" % [m for m in dev.log if m.startswith("input t=")][:5])

    # a d-pad press followed by a named screen is a cursor move, not progress: never learned `advanced`
    class NamedAfterFlick(DecayStub):
        def classify(self, frame, prev, context):
            r = DecayStub.classify(self, frame, prev, context)
            if hat_flicks(self.dev):
                r.update(state="main_menu", confidence=0.95)
            return r
    clear_learned()
    drvu, _ = probe_run(None, 20, make_stub=lambda dev: NamedAfterFlick(dev, 0.1, "boot"))
    up = [e for e in drvu.explored if e[1] == "UP"]
    fails += report(bool(up) and all(e[2] == "changed" for e in up),
                    "dpad: UP followed by a named screen is learned `changed`, never `advanced`", "explored=%s" % drvu.explored)
    clear_learned()
    real_r = drive.Driver.resolve_explore

    def no_downgrade(self, outcome):
        if self.explore:
            self.explore["dpad"] = False
        return real_r(self, outcome)
    drive.Driver.resolve_explore = no_downgrade
    try:
        drvw, _ = probe_run(None, 20, make_stub=lambda dev: NamedAfterFlick(dev, 0.1, "boot"))
    finally:
        drive.Driver.resolve_explore = real_r
    fails += report(any(e[1] == "UP" and e[2] == "advanced" for e in drvw.explored),
                    "mutant (no downgrade) learns UP `advanced`: the check above is not vacuous", "explored=%s" % drvw.explored)

    # a press resolved because the FLOOR fell is judged by the picture, not by the state change
    clear_learned()
    drv, dev = run(0.5, 20, ds=dict(dpad_probe=0))
    a = [e for e in drv.explored if e[1] == "A"]
    fails += report(bool(a) and a[0][2] == "none",
                    "decay: A pressed on a static unknown, then the floor falls and names it, is learned `none` (the picture did not move)",
                    "explored=%s" % drv.explored)
    clear_learned()
    classify.classify_frame = strip_decayed
    try:
        drvx, _ = run(0.5, 20, ds=dict(dpad_probe=0))
    finally:
        classify.classify_frame = real_cf
    fails += report(any(e[1] == "A" and e[2] == "advanced" for e in drvx.explored),
                    "mutant (a decayed acceptance not marked) learns A `advanced` because the bar fell: the check above is not vacuous",
                    "explored=%s" % drvx.explored)

    # what this title already learned goes first; the rotation is for a screen nothing is known about
    clear_learned()
    for _ in range(2):
        learned.record("generic", "unknown:pathclass:low-confidence", None, "X", "advanced", 1.0, "selftest")
    drv, dev = run(0.1, 12, state="boot", keep=True)
    pr, fl = presses_of(dev), hat_flicks(dev)
    fails += report(bool(pr) and pr[0][2] == "X" and len(fl) >= 1 and fl[0][0] < pr[0][0] and (len(fl) < 2 or fl[1][0] > pr[0][0]),
                    "dpad: the first flick is the look; a learned answer for this screen is pressed next, before the rest of the rotation",
                    "press %s flicks %s" % (pr[:1], fl[:2]))
    real_s = learned.suggest
    learned.suggest = lambda *a, **k: None
    try:
        drvl, devl = run(0.1, 12, state="boot", keep=True)
    finally:
        learned.suggest = real_s
    fl2 = hat_flicks(devl)
    fails += report(len(fl2) >= 2 and not [p for p in presses_of(devl) if p[2] == "X" and p[0] < fl2[1][0]],
                    "mutant (learned answers ignored) goes on to DOWN, not the learned X: the check above is not vacuous",
                    "press %s flicks %s" % (presses_of(devl)[:1], fl2[:2]))
    clear_learned()

    # a screen that leans PLAY goes to the play probe, never the d-pad: a flick in live play moves a
    # camera or a weapon. The control: the same confidence on a screen that leans nowhere gets the rotation.
    drv, dev = probe_run(lambda dev: False, 40, conf=0.5)
    fails += report(not hat_flicks(dev) and bool(drv.probes),
                    "dpad: an unknown that leans play is probed with held inputs, never flicked",
                    "flicks %s probes %s" % (order_of(dev)[:2], outcomes(drv)))
    drvc, devc = run(0.5, 40, state="gameplay")
    fails += report(order_of(devc)[:1] == HAT_ORDER[:1],
                    "control: a 0.5 answer that leans nowhere does get the rotation (the check above is detecting flicks)",
                    "flicks %s" % order_of(devc)[:2])

    # a hand-tuned profile has no lists and no dpad_probe: unchanged -- the floor never falls, no flick is sent
    clear_learned()
    drv, dev = run(0.5, 40, ps=dict(classifier_decay_menu=None, classifier_decay_gameplay=None), ds=dict(dpad_probe=0))
    fails += report(all(s == "unknown" for (_, s, _) in tsv_states(drv)) and order_of(dev)[:4] != HAT_ORDER,
                    "decay: a profile with no lists and dpad_probe 0 behaves as before (a 0.5 menu answer stays unknown, no rotation)")

    # the lists are validated, not trusted: a list that rises, is empty or holds a non-number stops the run
    def bad(**ps):
        try:
            run(0.5, 3, ps=ps)
        except SystemExit as e:
            return str(e)
        return None
    msgs = [bad(classifier_decay_menu=[0.3, 0.5]), bad(classifier_decay_menu=[]), bad(classifier_decay_gameplay=[1.5]),
            bad(classifier_decay_menu="0.5"), bad(classifier_decay_gameplay=[True])]
    fails += report(all(m and "classifier_decay" in m for m in msgs),
                    "decay: a decay list that rises, is empty, is out of range or is not a list of numbers is refused",
                    "got %s" % msgs)
    fails += report(bad(classifier_decay_menu=[0.5, 0.5, 0.4]) is None,
                    "decay: a flat step (equal floors) is a valid list")

    # the guard: under the fallen floor a non-gameplay answer is not taken while the top-3 still gives
    # gameplay as much as drive.LEAN_PLAY_START -- a menu press on a frame that might be live play (the
    # held-out set: zero such presses at every step with it, one at 0.55 without it)
    fails += report(classify.DECAY_PLAY_MASS == drive.LEAN_PLAY_START,
                    "decay guard: the gameplay mass that refuses a decayed menu answer is the lean's own START limit",
                    "%s vs %s" % (classify.DECAY_PLAY_MASS, drive.LEAN_PLAY_START))
    leans_play = [["main_menu", 0.5], ["gameplay", 0.2], ["submenu", 0.1]]
    leans_menu = [["main_menu", 0.5], ["gameplay", 0.05], ["submenu", 0.1]]
    drvp, _ = run(0.5, 20, top3=leans_play, ds=dict(dpad_probe=0))
    drvq, _ = run(0.5, 20, top3=leans_menu, ds=dict(dpad_probe=0))
    fails += report(all(s == "unknown" for (_, s, _) in tsv_states(drvp)) and "main_menu" in [s for (_, s, _) in tsv_states(drvq)],
                    "decay guard: a 0.5 menu answer with gameplay 0.2 in its top-3 stays unknown; with gameplay 0.05 it is named",
                    "0.2: %s; 0.05: %s" % ([s for (_, s, _) in tsv_states(drvp)][:6], [s for (_, s, _) in tsv_states(drvq)][:6]))
    real_m = classify.DECAY_PLAY_MASS
    classify.DECAY_PLAY_MASS = 2.0
    try:
        drvr, _ = run(0.5, 20, top3=leans_play, ds=dict(dpad_probe=0))
    finally:
        classify.DECAY_PLAY_MASS = real_m
    fails += report("main_menu" in [s for (_, s, _) in tsv_states(drvr)],
                    "mutant (no guard) names the gameplay-leaning 0.5 screen a menu: the check above is not vacuous")

    # the look and the lean: a screen whose top-3 leans menu still gets the free look first (UP), and its own
    # lean press (pathclass's DOWN) on the capture after, ahead of the rest of the rotation
    clear_learned()
    fl_, d_ = sim_frames()
    live = os.path.join(d_, "124950-entry.png")
    # (an embedding that never changes: the look flick leaves the picture as it was, so it is learned `none`)
    drvk = sim([dict(lean_answer(), embedding=[1.0] + [0.0] * 15)], [live] * 8, 8.0)
    ex = [i for i in drvk.inputs if i["why"].startswith("explore")]
    fails += report(len(ex) >= 2 and ex[0]["input"] == "UP" and "dpad probe 1/4" in ex[0]["why"]
                    and ex[1]["input"] == "DOWN" and "leans menu" in ex[1]["why"],
                    "dpad: the first flick is the look, the lean's own press comes next, before LEFT and RIGHT",
                    "explore=%s" % [(i["t"], i["input"], i["why"]) for i in ex[:3]])
    clear_learned()
    return fails


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
