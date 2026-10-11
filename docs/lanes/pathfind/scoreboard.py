#!/usr/bin/env python3
"""Print the scoreboard table from docs/lanes/pathfind/runs/*/result.json (+ calls.jsonl)."""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for d in sorted(glob.glob(os.path.join(HERE, "runs", "*")), key=os.path.getmtime):
    try:
        r = json.load(open(os.path.join(d, "result.json")))
    except (OSError, ValueError):
        continue
    calls = [json.loads(l) for l in open(os.path.join(d, "calls.jsonl"))] if os.path.exists(
        os.path.join(d, "calls.jsonl")) else []
    by = {}
    for c in calls:
        by[c["model"]] = by.get(c["model"], 0) + 1
    cost = sum(c.get("cost_usd") or 0 for c in calls)
    mins = r.get("minutes") if r.get("result") == "gameplay" else round(r.get("seconds", 0) / 60, 1)
    frame = os.path.join("runs", os.path.basename(d), "gameplay_frame.jpg") if r.get("result") == "gameplay" \
        else os.path.join("runs", os.path.basename(d), "strip.jpg")
    models = "/".join(f"{k.split('-')[1]} {v}" for k, v in sorted(by.items()))
    res = r.get("result")
    if os.path.exists(os.path.join(d, "review.json")):
        rv = json.load(open(os.path.join(d, "review.json")))
        res = f"{res} -> REVIEW: {rv.get('verdict')}"
        frame = os.path.join("runs", os.path.basename(d), "strip.jpg")
    rows.append(f"| {os.path.basename(d)} | {r.get('name')} | {r.get('device')} | "
                f"{'**gameplay**' if res == 'gameplay' else res} | {mins} | {r.get('model_calls')} ({models}) | "
                f"{r.get('steps')} | {r.get('replayed', 0)} | ${cost:.2f} | {r.get('reason') or ''} | {frame} |")
print("| run | title | device | result | min | model calls | steps | replayed | cost | reason | frame |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
print("\n".join(rows))
