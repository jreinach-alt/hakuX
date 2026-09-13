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

Three rules, in order:

1. An explicit `device` field in the request wins. That is for work only one
   device can do -- a soak on a title only one of them has.

2. Otherwise, a request naming a registered prediction (`expect`) is pinned to
   whichever device already ran another request naming the same prediction.
   The arms of an A/B always share their prediction file, so this pins a pair
   without anyone having to say so, and it pins it to wherever the first arm
   happened to land rather than to a device chosen in advance.

3. Otherwise, a request naming a prediction -- or a SOAK, which has none, and
   is then keyed on its requester -- is pinned by HASHING that key over the
   live devices. Same prediction, same
   device, computed from nothing but the name.

   Rule 2 alone has a race, and it fired: the two arms of a pair are queued
   seconds apart and can be claimed by two workers in the same instant, each
   asking "did a sibling already land somewhere?" before the other has written
   its owner file. Both get "no", both claim, and the pair splits -- which is
   exactly what happened to #13's arms after `running/` was already being
   consulted. No amount of looking harder at shared state fixes a read-read
   race; the fix is to stop reading. A hash needs no state, so there is no
   window in which two workers can disagree.

   Rule 2 still comes first, because a sibling that has ALREADY RUN is ground
   truth and the hash is only a prediction of where it would have gone. A
   re-queued arm after the device set changes must follow its partner, not the
   modulus.

A request naming no prediction is free and any idle device may take it.
"""
import hashlib
import json
import os
import sys

def serving(d):
    """Labels of the device lanes that are alive right now.

    Each worker writes `lanes/<label>` holding its own pid and removes it on
    exit. Liveness is then `kill -0` on that pid, which is the only test that
    survives the two ways the obvious answers fail:

      - a list written by the supervisor outlives the worker it describes, and
        the worker is the thing that dies (one lane was silently down for 25
        minutes on 2026-09-12);
      - a timestamp cannot tell a dead lane from a live one 20 minutes into a
        26-minute A/B arm, and that is the normal state of this queue, not the
        rare one.

    Fail open: an empty or unreadable directory yields no devices and the hash
    rule is skipped, which degrades to the old raced behaviour -- at worst a
    split pair, which `ab_compare` still scores. The alternative failure,
    hashing over a lane that has stopped serving, pins a request nobody will
    ever claim, and a queued request with no claimant is silent.
    """
    live = set()
    ldir = os.path.join(d, "lanes")
    try:
        names = os.listdir(ldir)
    except OSError:
        return []
    for name in names:
        try:
            with open(os.path.join(ldir, name)) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
        except (OSError, ValueError):
            continue
        live.add(name)
    return sorted(live)


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
    key = os.path.basename(expect) if expect else ""
    if not key and (req.get("title") or "").strip():
        # A SOAK has no prediction to pin on, by design: the audio and timing
        # streams have no golden to disagree with, so they queue with
        # --no-expect. That left exactly the streams that most need one device
        # as the only ones affinity ignored, and it cost a real measurement --
        # #64's four vblank soaks ran free, so its cost leg (median gfps 16 vs
        # 29, control 21) has the device as an uncontrolled variable and cannot
        # now exclude it. A soak comparison is between soaks by the same
        # requester, so pin on the requester instead. Still hash, still no
        # state.
        #
        # Deliberately NOT applied to disc requests: their requester is
        # "full-sweep" for a hundred suites, and pinning those to one lane
        # would halve the corpus sweep to buy a comparability nobody asked
        # for -- a sweep column is scored per capture against a golden, which
        # is a per-capture comparison, not a cross-run one.
        who = (req.get("requester") or "").strip()
        if who:
            key = "who:" + who
    if not key:
        print("")
        return

    # A sibling that is RUNNING pins just as hard as one that has finished,
    # and this is the common case rather than the rare one: both arms of a
    # pair are usually queued seconds apart, so the second is claimed while
    # the first is still on a device and has written no result.json yet.
    #
    # Missing this split a pair across two handhelds within an hour of the
    # second device arriving -- base on the Nova, fix on the Thor -- which is
    # precisely the comparison-with-two-variables this file exists to stop.
    running = os.path.join(d, "running")
    me = os.path.basename(reqpath)
    try:
        for name in os.listdir(running):
            if not name.endswith(".req") or name == me:
                continue  # a request does not pin to itself
            sib = load(os.path.join(running, name))
            if os.path.basename((sib.get("expect") or "").strip()) != key:
                continue
            owner = ""
            opath = os.path.join(running, name[:-4] + ".owner")
            try:
                with open(opath) as f:
                    owner = f.read().strip()
            except OSError:
                pass
            if owner:
                print(owner)
                return
    except OSError:
        pass

    # Then any completed result whose request named the same prediction.
    # Newest first, so a re-run of a pair follows its most recent arm rather
    # than one from hours ago.
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

    # Rule 3: no sibling anywhere, so this is the pair's first arm. Decide by
    # hash, so the second arm decides the same way without having to see this
    # one. sha256 rather than hash() because hash() of a str is salted per
    # process -- two workers would compute different answers for the same
    # name, which is the race again wearing a hat.
    devs = serving(d)
    if len(devs) > 1:
        h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
        print(devs[h % len(devs)])
        return
    print("")


if __name__ == "__main__":
    main()
