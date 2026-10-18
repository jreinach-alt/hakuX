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
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify  # noqa: E402
import drive  # noqa: E402

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
    return [os.path.join(d, f) for f in AVP_FRAMES], d


def avp_answers_ordered():
    return list(AVP_ANSWERS)


class StubClient:
    """Stands in for pathclass.Client in classify.pathclass_client(): the next answer off a
    list, in call order, no subprocess, no model. In order because SimDevice.capture()
    copies each source frame to an alternating `cap0.png`/`cap1.png` before classify.py
    ever sees a path, so the original frame's name is gone by the time it gets here."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.i = 0

    def classify(self, frame, prev, context):
        st, conf = self.answers[self.i]
        self.i += 1
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
    if any(i["input"] == "START" for i in pre_play):
        probs.append("START sent before play (generic.toml's ladder is [A] only)")
    if "\tplay\t" not in tsv:
        probs.append("never reached play")
    if "mark gameplay" not in tsv:
        probs.append("never marked")
    return probs


def main(argv):
    fails = 0

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
    ok2 = all(i["input"] == "" for i in play_inputs)  # no press at all while playing: hold_play only
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

    print("pathclass_selftest: %d failure(s)" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
