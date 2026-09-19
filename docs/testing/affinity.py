#!/usr/bin/env python3
"""Which device, if any, a request is pinned to.

    affinity.py <dispatch-dir> <request.req>     -> prints a device label, or ""
    affinity.py <dispatch-dir> --serving         -> prints the live lane labels

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

    Failing open is still right and it is no longer SILENT: `_note_blind`
    below records every claim made while this returns nothing, because on
    2026-09-19 it returned nothing for five hours and every line of this file
    went on executing exactly as written over an input that was gone.

    Note that `lanes/` is shared with `check_coverage.py`, which stamps
    `lanes/<lane>.lastbrief` there for an unrelated feature with an unrelated
    meaning of "lane". Those survive only because a brief stamp does not parse
    as an int and is skipped by the ValueError below. Nothing may write a
    NUMERIC file into that directory without this inventing a device.
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


def _note_split(d, reqname, key, dead):
    """Record that a pair was deliberately un-pinned, where a reader will see it.

    THE FALLTHROUGH IS CORRECT AND ITS SILENCE IS NOT. Freeing a request whose
    sibling ran on a device that has gone away is the right call -- the
    alternative is an arm nobody claims for the length of the outage. But it
    CHANGES WHAT THE PAIR MEASURES: two arms on two devices answer "is this
    deterministic run-to-run AND device-to-device", and no leg registered
    before the outage said that.

    That happened on 2026-09-13. #50's arm A ran on the nova, the nova was
    held for four hours, this rule freed arm B, and the thor took it. The
    registered determinism legs -- must_not_move over a suite and
    better=0/worse=0 -- silently became a confounded claim. The lane noticed
    only because arm B's device run was 20% faster than arm A's and it thought
    to check `device_label`.

    A note in the dispatch directory is not a strong mechanism, and it is not
    meant to be: the strong one is that a judged result records device_label
    already. This exists so the DECISION is discoverable rather than
    reconstructed from a pace difference -- the fallthrough is the only actor
    that knows a pin was dropped, and it was the only one not saying so.
    """
    try:
        os.makedirs(os.path.join(d, "splits"), exist_ok=True)
        with open(os.path.join(d, "splits", reqname + ".txt"), "w") as f:
            f.write("prediction %s was pinned to %s, which is not serving; "
                    "freed this request, so the pair may span two devices and "
                    "cannot isolate run-to-run variation\n" % (key, dead))
    except OSError:
        pass  # never fail a claim over a note


def _note_blind(d, reqname, key):
    """Record that no pin was even ATTEMPTED, because no lane is registered.

    `_note_split` covers the case where the scheduler knew where a sibling ran
    and let the request go anyway. This covers the worse one, because it is
    invisible from every angle: `serving()` returned nothing, so rule 2's
    `_live()` was false for a device that was in fact serving, and rule 3 had
    no devices to hash over. The pin was not overridden. It was ABSENT, and an
    absent pin prints exactly what a request with no sibling prints -- "".

    Measured 2026-09-19: something emptied `$D/lanes/` ten minutes after the
    workers started and nothing rewrote it for five hours, because the worker
    wrote that file only at startup. #89's arm A ran on the thor and arm B on
    the nova. `ab_compare` caught the split at judge time, as designed, and
    the cost was the run rather than the conclusion -- but nothing between the
    queue and the judge had said a word, and the scheduler was the one actor
    that knew it had stopped scheduling.

    Written into `splits/` next to `_note_split`'s notes, under a distinct
    `.blind.txt` suffix so one cannot clobber the other, and so the status
    roll-up can render both with one glob.
    """
    try:
        os.makedirs(os.path.join(d, "splits"), exist_ok=True)
        with open(os.path.join(d, "splits", reqname + ".blind.txt"), "w") as f:
            f.write("no device lane is registered in %s, so %s could not be "
                    "pinned at all; if this is one arm of an A/B its partner "
                    "may land on the other handheld\n"
                    % (os.path.join(d, "lanes"), key))
    except OSError:
        pass  # never fail a claim over a note


def _live(d, label):
    """Is that device serving RIGHT NOW?

    A PIN TO A DEVICE THAT IS NOT SERVING IS NOT A PIN, IT IS A STALL. Rule 2
    pins a request to wherever its sibling landed, which is ground truth while
    both devices are up and a trap the moment one goes away: the sibling's
    owner file and its result.json outlive the device by design, so the pin
    survives and nothing will ever claim the request. This file's own docstring
    already names that as the worse of the two failures -- "a queued request
    with no claimant is silent" -- and it was reachable through rule 2 the whole
    time.

    Measured 2026-09-13: the nova went offline for four hours with #50's arm A
    already run on it. Arm B was queued, rule 2 pinned it to the nova from arm
    A's owner file, and the thor -- idle, and byte-identical to the nova on
    62 of 62 captures by devices.sh's own check -- would have skipped it for
    the whole outage.

    Falling through to rule 3 costs at most a pair split across two handhelds,
    and devices.sh records that as an efficiency matter rather than a
    correctness one since the two measured identical. A silent stall costs the
    measurement.
    """
    return label in serving(d)


def load(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    d, reqpath = sys.argv[1], sys.argv[2]
    # `serving()` is the one input every rule here is decided over, and until
    # now nothing outside this file could ask for it. The dispatcher log and
    # the status roll-up both need the answer to say "pairs are not being
    # pinned right now", so expose it rather than have two callers each
    # reimplement a pid check that took three attempts to get right.
    if reqpath == "--serving":
        print(" ".join(serving(d)))
        return
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
                if _live(d, owner):
                    print(owner)
                    return
                _note_split(d, me, key, owner)
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
            if _live(d, label):
                print(label)
                return
            _note_split(d, me, key, label)
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
    # One serving device needs no pin -- everything lands there anyway, which
    # is the same answer the hash would give. NO serving device is different
    # in kind: it means this file's only input is missing and every rule above
    # was decided over an empty set. Say so.
    if not devs:
        _note_blind(d, me, key)
    print("")


if __name__ == "__main__":
    main()
