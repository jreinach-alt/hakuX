#!/usr/bin/env python3
"""classify.py -- screen classifier for route.sh's `drive` step (#433).

THE PROBLEM (owner, 2026-10-01 21:45 PDT). A blind play loop
(`repeat forever { ... press A ... }`) sends input into whatever is on
screen: START in live play pauses the game, A on a results/menu screen
advances to another menu. Nothing reads the screen DURING play, so a scored
window can fill with menus and pauses while fps still looks fine. `drive`
replaces the blind loop with: capture a frame, classify it, send the input
the title's profile maps that class to, log the class. This module is the
classifier; `route.sh`'s `drive_step` (see its grammar comment) is the loop
that calls it once per capture and acts on the result.

CLASSES: play, paused, menu, loading, cutscene, black, unknown. `unknown`
is not a screen state, it is this classifier admitting it does not know --
see POLICY below for what happens on it.

THE CHEAP CLASSIFIER, IN THE ORDER IT IS TRIED (no model call in this
path -- the brief's requirement that the default work with zero model
calls):

  1. BLACK: mean luminance of the whole frame under BLACK_LUMA_BAR. A
     screencap race (the display hasn't drawn yet) or a real black frame
     both read this way; treated as `loading` by policy, not failed.
  2. NAMED REFERENCE CROPS (`profile["crops"]`, reusing route.sh's own
     waitfor/press-until comparator, `waitfor_match.region_score` --
     one comparator for the whole codebase, not two). Each crop names a
     region, a reference PNG and a class; the first crop (in the profile's
     own order) whose region scores <= its threshold against the reference
     wins outright, before anything cheaper-but-vaguer runs. This is how a
     title's specific pause overlay, results screen or stage-select grid
     gets named exactly, the same way `waitfor` already does for a single
     scripted step -- `drive` is that same idea, polled continuously.
  3. HUD CROP: a crop whose class is `play` -- the brief's "HUD present =
     play". Checked after the named crops (a menu screen that happens to
     show a HUD-shaped icon must not be read as play) but before liveness.
  4. LIVENESS, only once 1-3 found no match. `frame_diff` scores two
     consecutive captures with the profile's `corner_mask` (the FPS-counter
     corner; it updates every frame regardless of what else is on screen
     and would otherwise make EVERY pair of frames look live) blanked out.
     Liveness alone cannot say `play` -- a cutscene moves too, and a menu
     over a replaying background moves under a perfectly static dialog
     (see NOTES.md, the Burnout Revenge SAVE/LOAD case) -- so it only
     chooses among the screens the first three steps did NOT already name:
       - moving (diff > STATIC_BAR): `cutscene` (no HUD, something is
         still happening -- an in-engine cinematic, most likely).
       - static (diff <= STATIC_BAR): dim check (mean luminance well below
         the profile's typical play luminance, `dim_drop`) -> `paused`,
         else -> `menu`.
     A score within MARGIN of either bar is treated as `unknown` rather
     than guessed -- see UNKNOWN AND THE MODEL FALLBACK.

UNKNOWN AND THE MODEL FALLBACK. `unknown` accumulates in the driver's state
file (see `step()`). Below `profile.get("unknown_before_model", 2)`
consecutive unknowns, the policy is just "wait, try again" -- a single
ambiguous capture is cheap to re-poll and often resolves itself (a frame
mid-transition). At the threshold, and only if ANTHROPIC_API_KEY is set
and the frame hash is not already in the state file's model cache, one
call to Haiku 4.5 (`claude-haiku-4-5-20251001`) asks for
`{"screen_class": ..., "button": ...}` on a downscaled frame -- see
`model_classify`. Every call (hit or cached) is appended to
`<result-dir>/classify-model-calls.jsonl` with its cost; the cap
(`profile.get("model_calls_max", 20)`) is enforced in `step()`, which is
also what makes "zero model calls" the default: no key, no call, ever.

WHY A SEPARATE STATE FILE, NOT IN-PROCESS STATE. `route.sh` calls this
script fresh, once per capture, from bash -- there is no long-lived
process to hold a liveness baseline, an unknown streak or a resume-attempt
counter. `<result-dir>/drive-state.json` carries it between calls, written
with the same tmp-then-rename pattern `title_verdict.py` uses so a reader
mid-write never sees a half-written file.
"""
import base64
import datetime as dt
import hashlib
import json
import os
import sys

try:
    import tomllib
except ImportError:            # python < 3.11
    tomllib = None

from PIL import Image
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from waitfor_match import region_score  # noqa: E402  -- the one comparator, shared with waitfor/press-until

CLASSES = ("play", "paused", "menu", "loading", "cutscene", "black", "unknown")

BLACK_LUMA_BAR = 8.0        # 0-255; a screencap race or a true black frame
STATIC_BAR = 6.0            # frame_diff below this: not moving
MARGIN = 1.5                # within this of STATIC_BAR or dim_drop: unknown, not guessed
DIFF_RESIZE = (160, 90)     # downscaled grayscale size liveness is scored at

MODEL_NAME = "claude-haiku-4-5-20251001"
MODEL_IMAGE_MAX = 512        # longest side, downscaled before sending
MODEL_PROMPT = (
    "This is a screenshot from an original-Xbox game running under emulation, "
    "captured during an unattended automated playtest. Classify what is on "
    "screen right now. Answer with ONLY a JSON object, no other text: "
    '{"screen_class": one of "play","paused","menu","loading","cutscene","black", '
    '"button": the single gamepad button (A, B, START, or "") that would make '
    "the most progress toward live gameplay from this screen}."
)


def luminance(path, region=None):
    im = Image.open(path).convert("L")
    if region:
        x, y, w, h = region
        im = im.crop((x, y, x + w, y + h))
    return float(np.asarray(im, dtype=np.float64).mean())


def _mask(arr, region):
    """Zero out `region` (x,y,w,h in ORIGINAL frame pixels) in a DIFF_RESIZE-scaled array."""
    if region is None:
        return arr
    # region is in the original frame's coordinates; scale it into DIFF_RESIZE space.
    # Callers pass the SOURCE image size so this scales correctly regardless of crop size.
    return arr  # masking is applied before resize in frame_diff(); see there.


def frame_diff(frame_a, frame_b, mask_region=None):
    """Mean abs grayscale diff between two frames, downscaled, with `mask_region`
    (x,y,w,h in the frames' own pixel coordinates -- the FPS-counter corner)
    painted black in both before the diff, so a free-running counter cannot
    read as motion. 0-255 scale, same convention as waitfor_match's score."""
    a = Image.open(frame_a).convert("L")
    b = Image.open(frame_b).convert("L")
    if mask_region:
        x, y, w, h = mask_region
        for im in (a, b):
            blank = Image.new("L", (w, h), 0)
            im.paste(blank, (x, y))
    aa = np.asarray(a.resize(DIFF_RESIZE), dtype=np.int16)
    bb = np.asarray(b.resize(DIFF_RESIZE), dtype=np.int16)
    return float(np.abs(aa - bb).mean())


def load_profile(path):
    if tomllib is None:
        raise SystemExit("classify.py: python has no tomllib; need 3.11+")
    with open(path, "rb") as f:
        return tomllib.load(f)


def match_crops(frame_path, crops, profile_dir):
    """First crop (in profile order) whose region matches its reference.
    `crops` is a list of dicts: name, region [x,y,w,h], ref (path relative
    to profile_dir), threshold, class. Returns (name, cls, score) or None."""
    for c in crops:
        ref = os.path.join(profile_dir, c["ref"])
        try:
            score = region_score(frame_path, ref, tuple(c["region"]))
        except Exception:
            continue
        if score <= c["threshold"]:
            return c["name"], c["class"], score
    return None


def classify_frame(frame_path, prev_frame_path, profile, profile_dir):
    """The cheap classifier (steps 1-4 of the module doc). Returns a dict:
    cls, reason, detail -- never calls the model; `step()` layers that on
    top when this returns `unknown` often enough."""
    luma = luminance(frame_path)
    if luma < BLACK_LUMA_BAR:
        return dict(cls="black", reason="luma %.1f < %.1f" % (luma, BLACK_LUMA_BAR), luma=luma)

    crops = [c for c in profile.get("crops", []) if c.get("class") != "play"]
    hit = match_crops(frame_path, crops, profile_dir)
    if hit:
        name, cls, score = hit
        return dict(cls=cls, reason="crop %s score %.2f" % (name, score), crop=name, score=score)

    hud = [c for c in profile.get("crops", []) if c.get("class") == "play"]
    hit = match_crops(frame_path, hud, profile_dir)
    if hit:
        name, cls, score = hit
        return dict(cls="play", reason="hud crop %s score %.2f" % (name, score), crop=name, score=score)

    if prev_frame_path is None:
        return dict(cls="unknown", reason="no previous frame yet (first capture)")

    corner = profile.get("corner_mask")
    diff = frame_diff(frame_path, prev_frame_path, tuple(corner) if corner else None)
    if diff > STATIC_BAR + MARGIN:
        return dict(cls="cutscene", reason="moving (diff %.2f), no crop matched" % diff, diff=diff)
    if diff < STATIC_BAR - MARGIN:
        dim_drop = profile.get("dim_drop", 40.0)
        play_luma = profile.get("play_luma", 110.0)
        if play_luma - luma > dim_drop + MARGIN:
            return dict(cls="paused", reason="static (diff %.2f), dim (luma %.1f vs play ~%.1f)"
                        % (diff, luma, play_luma), diff=diff, luma=luma)
        if play_luma - luma < dim_drop - MARGIN:
            return dict(cls="menu", reason="static (diff %.2f), not dim (luma %.1f vs play ~%.1f)"
                        % (diff, luma, play_luma), diff=diff, luma=luma)
        return dict(cls="unknown", reason="static but luma %.1f is within %.1f of the dim bar"
                    % (luma, MARGIN), diff=diff, luma=luma)
    return dict(cls="unknown", reason="diff %.2f is within %.1f of the static bar" % (diff, MARGIN), diff=diff)


def _state_path(result_dir):
    return os.path.join(result_dir, "drive-state.json")


def load_state(result_dir):
    try:
        with open(_state_path(result_dir)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return dict(unknown_streak=0, resume_tries=0, model_calls=0, model_cache={}, last_class=None)


def save_state(result_dir, state):
    tmp = _state_path(result_dir) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, _state_path(result_dir))


def frame_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def model_classify(frame_path, result_dir, state):
    """One Haiku 4.5 call on a downscaled frame, cached by frame hash in
    `state["model_cache"]`. Returns (cls, button, called:bool, cost:dict|None).
    No ANTHROPIC_API_KEY, no SDK, or any API error: (None, None, False, None)
    -- the caller falls back to `unknown` and keeps going. This is what makes
    the model optional rather than required: nothing above this function
    ever calls it unless the cheap classifier already gave up."""
    h = frame_hash(frame_path)
    if h in state["model_cache"]:
        return state["model_cache"][h]["cls"], state["model_cache"][h].get("button", ""), False, None
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None, None, False, None
    try:
        import anthropic
    except ImportError:
        return None, None, False, None
    try:
        im = Image.open(frame_path).convert("RGB")
        im.thumbnail((MODEL_IMAGE_MAX, MODEL_IMAGE_MAX))
        import io
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode()
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=MODEL_NAME, max_tokens=200,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": MODEL_PROMPT},
            ]}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        parsed = json.loads(text[text.find("{"):text.rfind("}") + 1])
        cls = parsed.get("screen_class")
        button = parsed.get("button", "")
        if cls not in CLASSES:
            cls = None
        cost = dict(input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens)
        state["model_cache"][h] = dict(cls=cls, button=button)
        log = dict(t=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   frame=os.path.basename(frame_path), frame_hash=h, cls=cls, button=button, **cost)
        with open(os.path.join(result_dir, "classify-model-calls.jsonl"), "a") as f:
            f.write(json.dumps(log) + "\n")
        return cls, button, True, cost
    except Exception as exc:
        with open(os.path.join(result_dir, "classify-model-calls.jsonl"), "a") as f:
            f.write(json.dumps(dict(t=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                     frame=os.path.basename(frame_path), frame_hash=h,
                                     error=str(exc)[:200])) + "\n")
        return None, None, True, None


def resolve_action(cls, profile, state):
    """(action_name, args) from `profile["policy"][cls]`. `paused` and
    `unknown` carry their own retry/escalation logic (see the module doc);
    everything else is a straight policy lookup. `profile["policy"]` maps a
    class to one of: "hold_accel" (the title's play input, from
    `profile["accel"]`, held for this whole tick), "none" (wait), or an
    explicit "press BTN" / "press-pattern NAME" naming a block under
    `profile["patterns"][NAME]` (a short list of route.sh step dicts)."""
    pol = profile.get("policy", {})
    if cls == "paused":
        max_tries = profile.get("max_resume_tries", 3)
        if state["resume_tries"] >= max_tries:
            return "fail", "paused %d times; resume did not work" % state["resume_tries"]
        state["resume_tries"] += 1
        return "press", profile.get("resume_button", "START")
    if cls != "paused":
        state["resume_tries"] = 0
    if cls == "unknown":
        threshold = profile.get("unknown_before_model", 2)
        if state["unknown_streak"] < threshold:
            return "none", None
        return "model_or_fail", None
    spec = pol.get(cls, "none")
    if spec == "hold_accel":
        return "hold_accel", profile.get("accel", {})
    if spec.startswith("press "):
        return "press", spec.split(" ", 1)[1]
    return "none", None


def step(args):
    """CLI entry: one classification + policy decision for one capture.
    Prints a single JSON line to stdout; route.sh's drive_step() reads it
    and does the actual pad.sh call and logcat/tsv writing -- this process
    never touches the device."""
    profile = load_profile(args.profile)
    profile_dir = os.path.dirname(os.path.abspath(args.profile))
    state = load_state(args.result_dir)

    result = classify_frame(args.frame, args.prev, profile, profile_dir)
    cls = result["cls"]
    model_called = False

    if cls == "unknown":
        state["unknown_streak"] = state.get("unknown_streak", 0) + 1
    else:
        state["unknown_streak"] = 0

    action, action_arg = resolve_action(cls, profile, state)

    if action == "model_or_fail":
        if state["model_calls"] < profile.get("model_calls_max", 20):
            mcls, mbutton, called, cost = model_classify(args.frame, args.result_dir, state)
            if called:
                state["model_calls"] += 1
                model_called = True
            if mcls:
                cls = mcls
                result = dict(cls=cls, reason="model: " + (mcls or "?"), model_cost=cost)
                state["unknown_streak"] = 0
                action, action_arg = resolve_action(cls, profile, state)
                if mbutton and action == "none" and cls != "play":
                    action, action_arg = "press", mbutton
            else:
                action, action_arg = "fail", "unknown after model (unavailable or inconclusive)"
        else:
            action, action_arg = "fail", "unknown, and model_calls_max (%d) reached" % profile.get("model_calls_max", 20)

    state["last_class"] = cls
    save_state(args.result_dir, state)

    print(json.dumps(dict(cls=cls, action=action, action_arg=action_arg, model_called=model_called,
                           detail=result)))
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("step", help="classify one capture and resolve the policy action")
    s.add_argument("--profile", required=True)
    s.add_argument("--frame", required=True)
    s.add_argument("--prev", default=None)
    s.add_argument("--result-dir", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "step":
        return step(a)
    return 2


if __name__ == "__main__":
    sys.exit(main())
