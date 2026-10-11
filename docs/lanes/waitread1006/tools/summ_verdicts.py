#!/usr/bin/env python3
"""Summarize verdict.json and result.json of named dispatch result dirs.

Usage: summ_verdicts.py <result-dir-name> [...]
Reads ~/hakux-work/dispatch/results/<name>/{verdict,result}.json and prints the
fields the lane's report cites. Nothing is inferred; a missing key prints None.
"""
import json
import os
import sys

BASE = os.path.expanduser("~/hakux-work/dispatch/results")
KEYS = ["title", "device", "ref", "apk_sha", "route", "fps_ok_share",
        "fps_window_median", "gameplay_s", "pass", "failing", "void"]


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main(names):
    for name in names:
        d = os.path.join(BASE, name)
        v = load(os.path.join(d, "verdict.json"))
        r = load(os.path.join(d, "result.json"))
        print("==", name)
        for k in KEYS:
            val = v.get(k, r.get(k))
            print("   %-18s %s" % (k, str(val)[:200]))
        h = v.get("hitches") or {}
        print("   %-18s n=%s worst_ms=%s big=%s cls=%s" % (
            "hitches", h.get("n_after_warmup"), h.get("worst_ms"),
            h.get("n_big_after_warmup"), h.get("classification")))
        for w in (h.get("worst5") or [])[:5]:
            print("      stall off=%s max_ms=%s dsm=%s dpc_ms=%s shader_ms=%s cls=%s" % (
                w.get("off_s"), w.get("max_ms"), w.get("dsm"), w.get("dpc_ms"),
                w.get("shader_stage_ms"), w.get("cls")))


if __name__ == "__main__":
    main(sys.argv[1:])
