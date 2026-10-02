#!/usr/bin/env python3
"""Label pool frames with a language model (Haiku through `claude -p`), ten frames per call.

    python3 label.py --pool <dir>/pool.tsv --out <dir>/labels.jsonl [--n 600] [--jobs 4]

Picks up to --n NOT held-out frames, spread evenly over titles, copies each as a 640 px JPEG under
<out dir>/lab/ (the CLI's Read tool views them there), and appends one JSON line per frame:
{path, title, state, why, model}. Re-running skips frames already labelled. Every call is logged to
<out dir>/label_calls.jsonl (model, seconds, frames), so the label count the brief asks for is on disk.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time

STATES = ["intro_video", "publisher_logo", "title_screen", "main_menu", "submenu", "profile_creation",
          "name_entry", "save_load_prompt", "controller_prompt", "loading", "cutscene", "pause", "gameplay",
          "results", "game_over", "black", "unknown"]

PROMPT = """You are labelling screenshots of original Xbox games running in an emulator, to train a screen-state
classifier. Use the Read tool to view each image file listed below, then name its state.

States (pick exactly one):
- intro_video: a pre-rendered or attract video before the title (incl. attract-mode demo play with a logo/PRESS START overlay)
- publisher_logo: a studio/publisher/engine logo or legal/copyright/warning text screen
- title_screen: the game's title/logo screen, usually "Press START"
- main_menu: the top-level menu (New Game / Continue / Options ...)
- submenu: any deeper menu: mode select, character/car/stage/level select, options, game list
- profile_creation: create/select a player profile or save slot
- name_entry: an on-screen keyboard or name field
- save_load_prompt: a dialog about saving/loading/storage (Yes/No, no save data, overwrite ...)
- controller_prompt: "press START/A to begin", "Player 1 press ...", controller connect/settings prompts
- loading: a loading screen, loading bar/spinner, "Loading", hint card while loading
- cutscene: an in-engine or pre-rendered story scene after the game started (letterbox, subtitles, no HUD)
- pause: a pause menu over gameplay ("PAUSED", Resume/Quit)
- gameplay: the player controls the game: HUD, playfield, player character/vehicle visible, no menu over it
- results: post-race/round/match results, scores, replays with Continue, "WINNER"/"PERFECT"
- game_over: a game over / mission failed / retry screen
- black: (nearly) all black
- unknown: none of these, an Android screen, a corrupt/garbage frame

Images (one per line, with the game title):
{items}

Answer with ONLY a JSON array, one object per image in the same order:
[{{"i": 1, "state": "<state>", "why": "<what you see, <= 12 words>"}}, ...]"""


def small_copy(src, dst):
    from PIL import Image
    im = Image.open(src).convert("RGB")
    im.thumbnail((640, 640))
    im.save(dst, quality=85)


def pretty_title(raw):
    t = re.sub(r"(\.xiso)?\.iso$", "", raw, flags=re.I)
    t = re.sub(r"^[0-9A-Fa-f]{8}-", "", t)
    return t.replace("_", " ")


def call(batch, model, labdir, log):
    items = "\n".join(f"{i + 1}. {b['jpg']}  ({pretty_title(b['title_raw'])})" for i, b in enumerate(batch))
    t0 = time.time()
    # the prompt goes on stdin: --allowedTools is variadic and would swallow a trailing prompt argument
    r = subprocess.run(["claude", "-p", "--model", model, "--output-format", "json", "--allowedTools", "Read"],
                       input=PROMPT.format(items=items), capture_output=True, text=True, timeout=600, cwd=labdir)
    dt = time.time() - t0
    out = []
    try:
        res = json.loads(r.stdout).get("result", "")
        m = re.search(r"\[.*\]", res, re.S)
        arr = json.loads(m.group(0)) if m else []
        for o in arr:
            i = int(o.get("i", 0)) - 1
            if 0 <= i < len(batch) and o.get("state") in STATES:
                out.append({"path": batch[i]["path"], "title": batch[i]["title"], "state": o["state"],
                            "why": o.get("why", ""), "model": model})
    except Exception as e:
        print(f"parse failed: {e}: {r.stdout[:300]} {r.stderr[:300]}", file=sys.stderr)
    with open(log, "a") as f:
        f.write(json.dumps({"model": model, "s": round(dt, 1), "frames": len(batch), "labelled": len(out),
                            "rc": r.returncode}) + "\n")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--per-call", type=int, default=10)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--heldout", action="store_true", help="label held-out-title frames instead (a test set)")
    a = ap.parse_args()
    rows = []
    with open(a.pool) as f:
        hdr = f.readline().rstrip("\n").split("\t")
        for line in f:
            rows.append(dict(zip(hdr, line.rstrip("\n").split("\t"))))
    rows = [r for r in rows if (r["heldout"] == "1") == a.heldout]
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["path"] for l in open(a.out) if l.strip()}
    by_t = {}
    for r in rows:
        by_t.setdefault(r["title"], []).append(r)
    rnd = random.Random(7)
    for v in by_t.values():
        rnd.shuffle(v)
    pick = []
    k = 0
    while len(pick) < a.n and any(k < len(v) for v in by_t.values()):
        for t in sorted(by_t):
            if k < len(by_t[t]) and len(pick) < a.n:
                pick.append(by_t[t][k])
        k += 1
    pick = [p for p in pick if p["path"] not in done]
    outdir = os.path.dirname(os.path.abspath(a.out))
    labdir = os.path.join(outdir, "lab")
    os.makedirs(labdir, exist_ok=True)
    keep = []
    for p in pick:
        p["jpg"] = os.path.join(labdir, hashlib.md5(p["path"].encode()).hexdigest()[:12] + ".jpg")
        if not os.path.exists(p["jpg"]):
            try:
                small_copy(p["path"], p["jpg"])
            except Exception as e:  # a live lane's scratch frame can vanish under us
                print(f"skip {p['path']}: {e}", file=sys.stderr)
                continue
        keep.append(p)
    pick = keep
    batches = [pick[i:i + a.per_call] for i in range(0, len(pick), a.per_call)]
    print(f"{len(pick)} frames to label in {len(batches)} calls", file=sys.stderr)
    log = os.path.join(outdir, "label_calls.jsonl")
    with cf.ThreadPoolExecutor(a.jobs) as ex, open(a.out, "a") as fo:
        for res in ex.map(lambda b: call(b, a.model, labdir, log), batches):
            for o in res:
                fo.write(json.dumps(o) + "\n")
            fo.flush()
            print(f"+{len(res)}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
