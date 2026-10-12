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
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify  # noqa: E402
import drive  # noqa: E402

PROF = os.path.join(HERE, "drive-profiles")
RESULTS = os.path.join(os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch"), "results")

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

    print("pathclass_selftest: %d failure(s)" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
