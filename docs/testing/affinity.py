#!/usr/bin/env python3
"""Which device, if any, a request is pinned to.

    affinity.py <dispatch-dir> <request.req>     -> prints a device label, or ""

With more than one handheld, the scheduler's first duty is not throughput --
it is making sure the two arms of an A/B land on the SAME device.

A comparison is only a comparison if one thing changed. Running `base` on the
Nova and `fix` on the Thor changes the binary *and* the hardware, and presents
the result as a one-commit delta. Both devices here are kalama/Adreno 740 on
the same Turnip, so the two would probably agree -- and "probably agree" is
precisely the kind of assumption this campaign has been burned by, most
recently when a scoreboard column turned out to be built from a binary 35
commits stale while every row's apk_sha agreed with every other.

Two rules, in order:

1. An explicit `device` field in the request wins. That is for work only one
   device can do -- a soak on a title only one of them has.

2. Otherwise, a request naming a registered prediction (`expect`) is pinned to
   whichever device already ran another request naming the same prediction.
   The arms of an A/B always share their prediction file, so this pins a pair
   without anyone having to say so, and it pins it to wherever the first arm
   happened to land rather than to a device chosen in advance.

A request with neither is free and any idle device may take it.
"""
import json
import os
import sys


def load(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    d, reqpath = sys.argv[1], sys.argv[2]
    req = load(reqpath)

    explicit = (req.get("device") or "").strip()
    if explicit:
        print(explicit)
        return

    expect = (req.get("expect") or "").strip()
    if not expect:
        print("")
        return
    key = os.path.basename(expect)

    # Look for a sibling arm: any completed result whose request named the
    # same prediction. Newest first, so a re-run of a pair follows its most
    # recent arm rather than one from hours ago.
    results = os.path.join(d, "results")
    try:
        entries = sorted(os.scandir(results), key=lambda e: e.stat().st_mtime,
                         reverse=True)
    except OSError:
        print("")
        return

    for e in entries:
        if not e.is_dir():
            continue
        sib = load(os.path.join(e.path, "request.json"))
        if os.path.basename((sib.get("expect") or "").strip()) != key:
            continue
        meta = load(os.path.join(e.path, "result.json"))
        label = (meta.get("device_label") or "").strip()
        if label:
            print(label)
            return
        # A result from before device labels existed cannot pin anything, and
        # guessing would be worse than leaving the pair free.
    print("")


if __name__ == "__main__":
    main()
