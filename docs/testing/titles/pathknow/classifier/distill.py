#!/usr/bin/env python3
"""Collect pathfind's language-model answers as training labels (tier 3 -> tier 2 distillation).

    python3 distill.py --pool <dir>          writes <dir>/extra_labels.jsonl

pathfind saves each decided frame as runs/<title-slug>/frames/NNN-<state>.jpg, the state being the model's
answer for that frame. Those are copied to ~/hakux-work/models/pathclass/frames/pathfind/ (a live lane's
scratch is rewritten under us) and appended as {path, title, state, model: "pathfind"}. Excluded: any run
whose title could be a held-out eval title (slug and title compared by prefix, both ways: pathfind's slugs
are truncated, 'ninja-gaiden' for Ninja Gaiden Black), and near-duplicate frames within a run.
Re-running adds only new frames.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pool import title_key, heldout_titles, load_eval, thumb  # noqa: E402

WORK = os.path.expanduser("~/hakux-work")
RUNS = os.environ.get("PATHCLASS_PATHFIND_RUNS", os.path.join(WORK, "wt", "pathfind", "scratch", "runs"))
DEST = os.path.join(WORK, "models", "pathclass", "frames", "pathfind")
# pathfind slugs that do not prefix-match their title's key
ALIASES = {"sw3": "starwarsepisodeiiirevengeofthesith", "doa3": "deadoralive3", "doa1u": "deadoralive1ultimate",
           "ngb": "ninjagaidenblack", "mc3": "midnightclub3dubedition", "pgr": "projectgothamracing",
           "gta-sa": "grandtheftautosanandreas", "cod3": "callofduty3", "thps3": "tonyhawksproskater3"}
STATES = {"intro_video", "publisher_logo", "title_screen", "main_menu", "submenu", "profile_creation", "name_entry",
          "save_load_prompt", "controller_prompt", "loading", "cutscene", "pause", "gameplay", "results",
          "game_over", "black", "unknown"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--thresh", type=float, default=4.0)
    a = ap.parse_args()
    ev = load_eval()
    held = heldout_titles({r["key"] for r in ev})
    out = os.path.join(a.pool, "extra_labels.jsonl")
    have = set()
    if os.path.exists(out):
        have = {json.loads(l)["src"] for l in open(out) if l.strip()}
    os.makedirs(DEST, exist_ok=True)
    n_new, skipped = 0, set()
    with open(out, "a") as fo:
        for run in sorted(glob.glob(os.path.join(RUNS, "*", "frames"))):
            slug = os.path.basename(os.path.dirname(run)).split(".")[0]
            k = ALIASES.get(slug, title_key(slug))
            if any(h.startswith(k) or k.startswith(h) for h in held):
                skipped.add(slug)
                continue
            kept = []
            for f in sorted(os.listdir(run)):
                m = re.match(r"\d+-([a-z_]+)\.(jpe?g|png)$", f)
                if not m or m.group(1) not in STATES:
                    continue
                src = os.path.join(run, f)
                th = thumb(src)
                if th is None:
                    continue
                if any(sum(abs(p - q) for p, q in zip(th, o)) / len(th) < a.thresh for o in kept):
                    continue
                kept.append(th)
                if src in have:
                    continue
                dst = os.path.join(DEST, os.path.basename(os.path.dirname(run)) + "--" + f)
                try:
                    shutil.copyfile(src, dst)
                except OSError:
                    continue
                fo.write(json.dumps({"path": dst, "src": src, "title": k, "state": m.group(1), "model": "pathfind"}) + "\n")
                n_new += 1
    print(f"distill: +{n_new} frames; runs skipped as possible held-out titles: {sorted(skipped)}", file=sys.stderr)


if __name__ == "__main__":
    main()
