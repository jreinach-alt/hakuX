#!/usr/bin/env python3
"""Which device, if any, a request is pinned to.

    affinity.py <dispatch-dir> <request.req>     -> prints a device label, or ""
    affinity.py <dispatch-dir> --serving         -> prints the live lane labels
    affinity.py <dispatch-dir> --available <label> -> exit 0 if serving or held
                                                    (and coming back), 1 if gone
    affinity.py <dispatch-dir> --choose <key> <before-id>
                                                 -> the pooled device with the
                                                    least work queued ahead of
                                                    <before-id>, or "" (CHOOSE)

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
   device can do -- a soak on a title only one of them has -- and for the
   arms job's LOAD PIN (see CHOOSE below), which is the one explicit device
   that is a preference rather than a requirement: an `arms-*` request pinned
   to a pooled device that is not serving falls through to the rules below,
   exactly as a rule-2 pin to a gone device does, instead of stalling. And
   because it is only a preference, a load pin ranks BELOW a sibling that is
   running or has run on a live device: an arm that fell through while the
   pinned device was held pulls its partner after it when the hold lifts,
   rather than the partner going back to the pin and splitting the pair.

2. Otherwise, a request naming a registered prediction (`expect`) is pinned to
   whichever device already ran another request naming the same prediction.
   The arms of an A/B always share their prediction file, so this pins a pair
   without anyone having to say so, and it pins it to wherever the first arm
   happened to land rather than to a device chosen in advance.

   2b. A QUEUED sibling with an explicit `device` pins this request to that
   device. That covers a pair queued by hand with one arm given --device, and
   it is what keeps an arms-job pair together if only one arm carries the pin.

   A sibling that LANDED (running or run) on a device that is now HELD still
   pins, for up to HOLD_WAIT_S from the hold's mtime: a held device is coming
   back, and following the partner elsewhere splits the pair (#583, see
   `_held`). A device neither serving nor held is gone, and falls through.

   The siblings are read in the order a request MOVES -- queue/, then
   running/, then results/ -- so a sibling that is being claimed while this
   runs is seen in one place or the next, never in neither. A sibling found in
   running/ before its owner file is written is pinned by its own `device`
   field if it has one.

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

CHOOSE. The hash is race-free and blind: it never looks at what is queued.
On 2026-09-27 forza414's pair hashed to the nova behind nine `device: nova`
soaks (~2 h), while the thor served idle-tier `z-*` sweep legs, and the pair
waited 94 min until hostops re-pinned it by hand. flip474's pair starved the
same way that morning. So the arms job, which queues both arms of a pair in
one tick, asks `--choose` for the pooled device with the least work queued
AHEAD of the pair (requests whose id sorts before the pair's, plus what is
still running), and passes that device to request.sh --device for BOTH arms.
One writer decides once and writes the answer into both requests before
either can be claimed, so there is no read-read race to bring back: every
worker afterwards reads rule 1.

Work is priced with request.sh's pilot-gate estimate -- `seconds` + 90 s of
setup, times `runs`, 180 s with no `seconds` -- and a running request by what
remains of that estimate since its owner file was written. A queued request
counts on the device this file would send it to (rule 1, 2 or 3); a request
this file leaves free counts on neither, since either worker may take it. A
tie goes to the device rule 3 would have picked, so an empty queue changes
nothing.

NOT EVERY LANE IS A HANDHELD. `desktop` is this host's own xemu build, and it
is reachable ONLY through rule 1. See OFFPOOL below.
"""
import hashlib
import json
import os
import sys
import time

# Lanes that serve requests but must never be CHOSEN for a request.
#
# The desktop channel is an execution target with no serial: this host's own
# xemu build, running the OpenGL renderer that neither handheld can. It
# registers `lanes/desktop` like any other worker, so `serving()` sees it and
# the status roll-up can say it is alive -- and that is exactly the problem
# rule 3 would have had. Rule 3 hashes an A/B pair over the live lanes, so
# with nova, thor and desktop all serving, one A/B pair in three would have
# been sent to a renderer nobody asked for, and BOTH ARMS WOULD HAVE GONE
# THERE TOGETHER -- the hash is deterministic, so the pair stays paired and
# the result looks entirely healthy. It would have been scored against
# goldens captured on an Adreno running Vulkan, and every capture that
# differs for renderer reasons would have read as a defect this lane had
# introduced. That is the failure mode with no symptom.
#
# So the pool that rule 3 hashes over is the HANDHELDS, and rule 1 -- an
# explicit `device` field, which only a human or a script that means it can
# set -- is the only route onto the desktop.
#
# Rule 2 is deliberately NOT restricted. It pins to where a sibling ACTUALLY
# RAN, and a sibling can only have run on the desktop because someone asked
# for the desktop; following it there keeps the pair on one renderer, which
# is the whole point of rule 2.
#
# Kept here as a constant rather than read out of devices.sh: this is the
# scheduler, it runs on every claim, and a lane that cannot be classified
# because a file was unreadable would fall back to the behaviour above with
# no symptom. `selftest.d/55-affinity-offpool.sh` checks that this set and
# `devices.sh device_offpool_labels` still agree, so the duplication cannot
# drift in silence.
OFFPOOL = frozenset({"desktop"})

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


def pooled(d):
    """The live lanes that an unpinned request may be assigned to.

    `serving()` answers "who is alive", which is what an observer wants.
    This answers "who may be chosen", which is what rule 3 needs, and the two
    are not the same question the moment a non-handheld lane exists. See
    OFFPOOL.
    """
    return [x for x in serving(d) if x not in OFFPOOL]


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
            f.write("no poolable device lane is registered in %s, so %s could "
                    "not be pinned at all; if this is one arm of an A/B its "
                    "partner may land on the other handheld. (Lanes alive but "
                    "not poolable: %s.)\n"
                    % (os.path.join(d, "lanes"), key,
                       ", ".join(sorted(set(serving(d)) & OFFPOOL)) or "none"))
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


# How long a pin waits for a HELD device before it falls through as if the
# device were gone. From the hold file's mtime. See `_held`.
HOLD_WAIT_S = int(os.environ.get("AFFINITY_HOLD_WAIT_S") or 3 * 3600)


def _held(d, label):
    """Is that device on a HOLD that is young enough to wait for?

    A HELD DEVICE IS COMING BACK; A GONE ONE IS NOT. `_live` cannot tell them
    apart, because a held worker drops its own `lanes/<label>` on purpose
    (dispatcher.sh, the hold check: "affinity must not pin a pair to a device
    on hold"), so both read as "not serving" and both fell through. That is
    right for a device that went away and wrong for one taken out of service
    for a title push or a cold slot: on 2026-09-28 #583's base arm ran on the
    thor, the thor was under a bounded hold when the fix arm came up, its load
    pin and its sibling pin both fell through, and the nova ran it. The pair
    then FAILED on a capture that differs by device, and the PR was labelled
    `regressed` on a verdict its own judge called unattributable.

    So a pin to a held device WAITS, for up to HOLD_WAIT_S from the hold
    file's mtime; after that the device is treated as gone and the pin falls
    through exactly as before. The hold file is the only record that survives
    a hold (the lane registration does not), which is why it is the test.

    The 09-13 incident `_live` was written for -- the nova out of service for
    four hours with #50's arm A run on it -- was a hold too. It now waits
    three hours instead of none, and then falls through and is noted as a
    split, as it always was. A device with neither a live lane nor a hold is
    gone and falls through at once.
    """
    p = os.path.join(d, "hold", label)
    try:
        if not os.path.isfile(p):
            return False
        return time.time() - os.path.getmtime(p) < HOLD_WAIT_S
    except OSError:
        return False


def _available(d, label):
    """Serving now, or held and coming back: a pin to it is worth keeping."""
    return _live(d, label) or _held(d, label)


def load(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _key(req):
    """The name a request is pinned on: its prediction, or a soak's requester."""
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
    return key


def _hash_pick(key, devs):
    # sha256 rather than hash() because hash() of a str is salted per
    # process -- two workers would compute different answers for the same
    # name, which is the race again wearing a hat.
    h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    return h % len(devs)


# BATTERY. Rule 3's hash and a load pin are both blind to the battery gate,
# and the gate is asked only on the device this file names, so a refusal
# there is seen by nobody else. On 2026-09-28 three arm pairs (ibcache,
# gpl569, tcg424flip) hashed to the nova and were refused on every walk for
# 8-14 h -- level 35 < need 49.6, the nova hovering at 35-39 % on its 500 mA
# port -- while the thor sat at 80-83 % and would have admitted them at need
# 29.9. It never saw them: this file had sent them to the nova.
#
# So a device that has refused a request of this key for REFUSED_MOVE_S, and
# whose level is still below the need it refused at, is passed over -- but
# only for another pooled device whose own level covers its own need, and
# only where nothing has landed (a sibling that ran is still followed, rule
# 2). No refusal, or every candidate refusing, and the answer is the one it
# always was. battery_admit.py writes the record (`.battery_refused.<label>`)
# and computes the need; see there.
#
# PAIRS. Both arms share the key and so read the same records, the same level
# files and (same runs, same kind) the same need: one answer for both, from
# state rather than from nothing, which is what the hash was for. The answer
# can change only when a level file does, which is once a minute at most; an
# arm claimed in that minute is in running/ and rule 2 pulls its partner
# after it. The one gap is the rename-to-owner-write instant rule 2 already
# names. A device with no fresh level (nothing asked it for 15 min) counts as
# admitting: it reads its level when it is offered the request, and if it
# refuses, that refusal is recorded and the request goes back.
REFUSED_MOVE_S = float(os.environ.get("AFFINITY_REFUSED_MOVE_S") or 600)

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import battery_admit as _ba
except Exception:        # a copy of this file alone: no battery rule, as before
    _ba = None


def _key_ids(d, key, me):
    """Ids of the queued or running requests pinned on `key`, `me` included."""
    ids = {me[:-4] if me.endswith(".req") else me}
    for sub in ("queue", "running"):
        p = os.path.join(d, sub)
        try:
            names = os.listdir(p)
        except OSError:
            continue
        for name in names:
            if name.endswith(".req") and _key(load(os.path.join(p, name))) == key:
                ids.add(name[:-4])
    return ids


def _refusing(d, label, ids, now, age=0.0):
    """The refusal of one of `ids` on `label` that still holds and is at least
    `age` old, or None. "Still holds": the device's current level, or the
    level it refused at if it has not read one since, is below that need."""
    lvl = _ba.level_now(d, label)
    for i, r in sorted(_ba.refusals(d, label).items()):
        try:
            if i not in ids or now - float(r["since"]) < age:
                continue
            at = lvl if lvl is not None else float(r["level"])
            if at < float(r["need"]):
                return dict(r, id=i, level_now=at)
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _battery_alt(d, req, me, key, dev, devs):
    """Where to send `req` instead of `dev`, or "" to leave it on `dev`."""
    if _ba is None or not key or dev not in devs:
        return ""
    try:
        if not _ba.refusals(d, dev):
            return ""    # the common case, without listing the queue
        now = time.time()
        ids = _key_ids(d, key, me)
        if not _refusing(d, dev, ids, now, REFUSED_MOVE_S):
            return ""
        ok = []
        for x in devs:
            if x == dev or _refusing(d, x, ids, now):
                continue
            lvl = _ba.level_now(d, x)
            if lvl is None or lvl >= _ba.need_for(d, x, req)[0]:
                ok.append(x)
        return ok[_hash_pick(key, ok)] if ok else ""
    except Exception:    # never fail a claim over the battery rule
        return ""


def _note_battery_move(d, reqname, key, frm, to):
    """The move is a decision only this file knows it made: say so once.
    Not in splits/: the pair stays on one device, and status.sh reads every
    note there as "may span two devices"."""
    p = os.path.join(d, "moves", reqname + ".battery.txt")
    try:
        if os.path.exists(p):
            return
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write("prediction %s: %s has refused it on battery for %ds or more "
                    "and %s would admit it, so this request goes to %s\n"
                    % (key, frm, REFUSED_MOVE_S, to, to))
    except OSError:
        pass  # never fail a claim over a note


def _is_load_pin(req, label):
    """Is this explicit `device` the arms job's preference, not a requirement?

    `arms-*` is the arms job's requester namespace (request.sh's pilot gate
    keys on the same prefix). The arms job queues disc A/Bs only -- soaks are
    hand-read and it skips them -- and the two handhelds measure identical on
    a disc, so the device it writes is CHOOSE's load pick and nothing else.
    Honouring it past the device's death would turn "run where the queue is
    shorter" into "never run", which is the stall `_live` exists to prevent.
    Off-pool lanes are never a load pick, so a pin to one stays absolute.

    `"pin": "hard"` (request.sh --hard-pin) makes an arms-job pin absolute
    too. The arms job writes it on the one arm pair it must NOT let fall
    through: the same-device re-run of a pair whose FAIL was confounded by
    running its two arms on two devices. Falling through there would
    reproduce the confound it exists to remove.
    """
    return ((req.get("requester") or "").startswith("arms-")
            and not (req.get("title") or "").strip()
            and (req.get("pin") or "").strip() != "hard"
            and label not in OFFPOOL)


def _result_labels(d, key):
    """device_label of every result naming `key`, newest first."""
    results = os.path.join(d, "results")
    try:
        entries = sorted(os.scandir(results), key=lambda e: e.stat().st_mtime,
                         reverse=True)
    except OSError:
        return
    for e in entries:
        if not e.is_dir():
            continue
        sib = load(os.path.join(e.path, "request.json"))
        if os.path.basename((sib.get("expect") or "").strip()) != key:
            continue
        meta = load(os.path.join(e.path, "result.json"))
        label = (meta.get("device_label") or "").strip()
        # A result from before device labels existed cannot pin anything, and
        # guessing would be worse than leaving the pair free.
        if label:
            yield label


def _results_index(d):
    """`_result_labels` for every key at once, for CHOOSE's many lookups."""
    idx = {}
    results = os.path.join(d, "results")
    try:
        entries = sorted(os.scandir(results), key=lambda e: e.stat().st_mtime,
                         reverse=True)
    except OSError:
        return idx
    for e in entries:
        if not e.is_dir():
            continue
        sib = load(os.path.join(e.path, "request.json"))
        k = os.path.basename((sib.get("expect") or "").strip())
        if not k:
            continue
        label = (load(os.path.join(e.path, "result.json")).get("device_label")
                 or "").strip()
        if label:
            idx.setdefault(k, []).append(label)
    return idx


def decide(d, req, me, notes=True, labels_for=None):
    """The device `req` (file name `me`) is pinned to, or "".

    `notes` False is a question asked on the request's behalf (CHOOSE pricing
    the queue), not a claim, and must not write split or blind notes.
    """
    note_split = _note_split if notes else (lambda *a: None)

    # A LOAD PIN RANKS BELOW A SIBLING THAT HAS LANDED. It was written before
    # either arm was claimed, as a guess at the shorter queue; a sibling that
    # is running or has run is ground truth. Returning a live load pin first
    # split a pair: thor held, the nova took the base arm, the hold lifted,
    # and the thor took the fix arm on its own pin (audit of #503, H1). So a
    # live load pin is kept aside and answered only once no sibling has
    # landed on a live device. A hand pin stays absolute (rule 1).
    explicit = (req.get("device") or "").strip()
    load_pin = ""
    if explicit:
        if not _is_load_pin(req, explicit):
            return explicit
        # A load pin to a HELD device still falls through (nothing has
        # landed, so both arms can go elsewhere together), but it is not a
        # split: a sibling that did land there is followed below (`_held`).
        if _live(d, explicit):
            load_pin = explicit
            # A load pin to a device refusing it on battery falls through
            # like one to a held device: nothing has landed, and both arms
            # carry the same pin, so both go wherever the rules below say.
            if _battery_alt(d, req, me, _key(req), explicit, pooled(d)):
                load_pin = ""
        elif not _held(d, explicit):
            note_split(d, me, _key(req) or "(none)", explicit)

    key = _key(req)
    if not key:
        return load_pin

    # Rule 2b, read FIRST because queue/ is where a sibling is before it is
    # anywhere else (see the module docstring). Sorted, so two explicit
    # siblings that disagree -- a hand edit -- still give every reader one
    # answer.
    queued_pin = ""
    qdir = os.path.join(d, "queue")
    try:
        qnames = sorted(os.listdir(qdir))
    except OSError:
        qnames = []
    for name in qnames:
        if not name.endswith(".req") or name == me:
            continue
        sib = load(os.path.join(qdir, name))
        if os.path.basename((sib.get("expect") or "").strip()) != key:
            continue
        dev = (sib.get("device") or "").strip()
        if not dev:
            continue
        if _is_load_pin(sib, dev) and (
                not _live(d, dev)
                or _battery_alt(d, sib, name, key, dev, pooled(d))):
            continue  # the sibling falls through too; follow it there
        queued_pin = dev
        break

    # A sibling that is RUNNING pins just as hard as one that has finished,
    # and this is the common case rather than the rare one: both arms of a
    # pair are usually queued seconds apart, so the second is claimed while
    # the first is still on a device and has written no result.json yet.
    #
    # Missing this split a pair across two handhelds within an hour of the
    # second device arriving -- base on the Nova, fix on the Thor -- which is
    # precisely the comparison-with-two-variables this file exists to stop.
    running = os.path.join(d, "running")
    try:
        for name in sorted(os.listdir(running)):
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
            # Claimed a moment ago: renamed into running/, owner file not yet
            # written. Its own explicit device is where it is running.
            owner = owner or (sib.get("device") or "").strip()
            if owner:
                if _available(d, owner):
                    return owner
                note_split(d, me, key, owner)
    except OSError:
        pass

    # A queued sibling has not landed, so it does not outrank a live load pin
    # (which, for an arms-job pair, it normally equals anyway).
    if queued_pin and not load_pin:
        return queued_pin

    # Then any completed result whose request named the same prediction.
    # Newest first, so a re-run of a pair follows its most recent arm rather
    # than one from hours ago.
    labels = labels_for(key) if labels_for else _result_labels(d, key)
    for label in labels:
        if _available(d, label):
            return label
        note_split(d, me, key, label)

    # No sibling has landed on a live device: now the load pin decides.
    if load_pin:
        return load_pin

    # Rule 3: no sibling anywhere, so this is the pair's first arm. Decide by
    # hash, so the second arm decides the same way without having to see this
    # one.
    devs = pooled(d)
    if len(devs) > 1:
        pick = devs[_hash_pick(key, devs)]
        alt = _battery_alt(d, req, me, key, pick, devs)
        if alt:
            if notes:
                _note_battery_move(d, me, key, pick, alt)
            return alt
        return pick
    # One serving device needs no pin -- everything lands there anyway, which
    # is the same answer the hash would give. NO serving device is different
    # in kind: it means this file's only input is missing and every rule above
    # was decided over an empty set. Say so.
    if not devs and notes:
        _note_blind(d, me, key)
    return ""


def _est(rq):
    """request.sh's pilot-gate estimate, in seconds. Change both or neither."""
    try:
        sec = int(rq.get("seconds") or 0)
        return (sec + 90) * int(rq.get("runs") or 1) if sec > 0 else 180
    except (TypeError, ValueError):
        return 180


def backlog(d, before, devs=None):
    """Seconds of work each pooled device has ahead of an id `before`.

    Byte order, as request.sh documents the queue's priority order. A request
    that sorts at or after `before` does not delay it and is not counted.
    """
    devs = pooled(d) if devs is None else devs
    load_s = {x: 0 for x in devs}
    idx = _results_index(d)
    labels_for = lambda k: idx.get(k, [])
    qdir = os.path.join(d, "queue")
    try:
        qnames = sorted(os.listdir(qdir))
    except OSError:
        qnames = []
    for name in qnames:
        if not name.endswith(".req") or (before and name >= before):
            continue
        rq = load(os.path.join(qdir, name))
        dev = decide(d, rq, name, notes=False, labels_for=labels_for)
        if dev in load_s:
            load_s[dev] += _est(rq)
    rdir = os.path.join(d, "running")
    try:
        rnames = os.listdir(rdir)
    except OSError:
        rnames = []
    now = time.time()
    for name in rnames:
        if not name.endswith(".req"):
            continue
        opath = os.path.join(rdir, name[:-4] + ".owner")
        try:
            with open(opath) as f:
                owner = f.read().strip()
            began = os.path.getmtime(opath)
        except OSError:
            continue
        if owner in load_s:
            rq = load(os.path.join(rdir, name))
            load_s[owner] += max(0, _est(rq) - (now - began))
    return load_s


def choose(d, key, before):
    """CHOOSE: the pooled device with the least work ahead of `before`.

    "" with fewer than two pooled devices: there is nothing to choose, and a
    pin written into a request then would outlive the moment it was right.
    """
    devs = pooled(d)
    if len(devs) < 2:
        return ""
    load_s = backlog(d, before, devs)
    h = _hash_pick(key, devs)
    n = len(devs)
    return devs[min(range(n), key=lambda i: (load_s[devs[i]], (i - h) % n))]


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
    # The pool rule 3 actually hashes over. A reader asking "why did this pair
    # not get pinned" needs THIS set, not the one above: with only the desktop
    # lane alive, `--serving` prints a lane and `--serving-pooled` prints
    # nothing, and the second is the one that explains the empty pin.
    if reqpath == "--serving-pooled":
        print(" ".join(pooled(d)))
        return
    # For the arms job's same-device re-run: is this device worth a HARD pin
    # (serving, or held and coming back), or gone, so CHOOSE should pick?
    if reqpath == "--available":
        sys.exit(0 if _available(d, sys.argv[3]) else 1)
    if reqpath == "--choose":
        print(choose(d, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else ""))
        return
    if reqpath == "--backlog":   # for a reader: "<device> <seconds>" per line
        before = sys.argv[3] if len(sys.argv) > 3 else ""
        for dev, s in sorted(backlog(d, before).items()):
            print("%s %d" % (dev, s))
        return
    print(decide(d, load(reqpath), os.path.basename(reqpath)))


if __name__ == "__main__":
    main()
