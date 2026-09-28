#!/usr/bin/env python3
"""Per-run battery admission for a handheld (#507, owner rule 2026-09-28).

    battery_admit.py check <dispatch dir> <label> <request.json> <level> [<head id>]
    battery_admit.py learn <dispatch dir> <label> <soak|pgraph>

THE RULE. A request is admitted on device D only if D's battery level covers
the run with the owner's margin:

    need = FLOOR + MARGIN + rate(D, kind) x runs x (seconds + overhead_s) / 3600

FLOOR is 15 (hostops's battery hold places itself below it) and MARGIN is 5
("about 5% wiggle room"). kind is `soak` for a request with a title and
`pgraph` for a test-disc run.

`rate` and `overhead_s` are LEARNED from D's own last 10 results of that kind,
at the 75th percentile, because the number that matters is a bad run, not a
typical one:

  rate        the fall in pw.battery.capacity from the first thermal.jsonl
              sample to the last, over the time between them, in %/h. A run
              shorter than MIN_SPAN_S is not used: capacity is an integer, so
              one percent over two minutes reads as 30 %/h. Nor is a run that
              started above LEARN_BELOW (60): plugged in near its charge
              limit the Thor holds its level through a soak (ten of its last
              ten soaks on 09-28, all at 77-85 %, read 0 %/h), while the same
              Thor from 18 % fell to 5 % in 36 minutes. Admission only binds
              at low charge, so only low-charge runs teach it.
  overhead_s  the device time a run takes beyond its `seconds`, per run:
              (end - start) / runs - seconds, where end is DONE's mtime and
              start is, in order of preference, the `t_device` the dispatcher
              records in battery.json when it starts the install, the first
              thermal sample (a soak before battery.json existed), or the
              earliest file the run wrote (a disc run before it existed).

With fewer than MIN_HISTORY usable results the FALLBACK table answers
(devwatch's measured soak rates; a test disc at half), and the output says
which. A test disc writes no thermal.jsonl, so its rate is the fallback until
one does; its overhead is learned.

THE HEAD, AND WHY A LONG RUN IS NOT STARVED. The dispatcher walks the queue in
priority order and passes the id of the first request that did not fit this
tick (the device's head) when it asks about the requests behind it. Those may
be claimed instead -- a backfill -- but only for HEAD_WAIT_S after the head
was first refused. After that the head reserves the device: nothing behind it
is admitted, the device charges, and the head is claimed on the first check
at which it fits. Without that bound, a stream of short runs would each take
the charge the head is waiting for, and the level would hover at the short
runs' need forever. The reservation is a file, .battery_head.<label>, naming
the head and when it was first refused; a different head starts a new clock.

Exit: 0 admit, 1 does not fit, 3 fits but the head holds the device. Line one
of stdout is the dispatcher's log text; line two is the JSON it records.
"""
import glob
import json
import os
import sys
import time

FLOOR = float(os.environ.get("BATTERY_FLOOR", "15"))
MARGIN = float(os.environ.get("BATTERY_MARGIN", "5"))
HEAD_WAIT_S = float(os.environ.get("BATTERY_HEAD_WAIT_S", "1800"))
RATES_TTL_S = float(os.environ.get("BATTERY_RATES_TTL_S", "300"))
HISTORY = 10
MIN_HISTORY = 3
MIN_SPAN_S = 180
LEARN_BELOW = float(os.environ.get("BATTERY_LEARN_BELOW", "60"))
PCTL = 0.75
# %/h. devwatch's measured soak drains; a test disc at half.
FALLBACK_RATE = {("nova", "soak"): 21.0, ("thor", "soak"): 10.0,
                 ("nova", "pgraph"): 10.5, ("thor", "pgraph"): 5.0}
FALLBACK_RATE_OTHER = 21.0           # an unknown handheld: the worst we know
FALLBACK_OVERHEAD_S = {"soak": 120.0, "pgraph": 300.0}


def pctl(xs, q=PCTL):
    """Linear-interpolated percentile of a non-empty list."""
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def kind_of(req):
    return "soak" if (req or {}).get("title") else "pgraph"


def thermal_caps(path):
    """[(t, capacity)] from a thermal.jsonl, samples without a capacity dropped."""
    out = []
    try:
        fh = open(path)
    except OSError:
        return out
    with fh:
        for line in fh:
            try:
                r = json.loads(line)
                c = ((r.get("pw") or {}).get("battery") or {}).get("capacity")
                if c is not None:
                    out.append((float(r["t"]), float(c)))
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
    return out


def run_record(rdir):
    """What one finished result says about drain and overhead, or None."""
    done = os.path.join(rdir, "DONE")
    req = load(os.path.join(rdir, "request.json"))
    res = load(os.path.join(rdir, "result.json"))
    if req is None or res is None or not os.path.exists(done):
        return None
    end = os.path.getmtime(done)
    runs = max(1, int(req.get("runs") or 1))
    seconds = float(req.get("seconds") or 0)
    caps = thermal_caps(os.path.join(rdir, "thermal.jsonl"))
    rate = None
    if (len(caps) >= 2 and caps[-1][0] - caps[0][0] >= MIN_SPAN_S
            and caps[0][1] <= LEARN_BELOW):
        rate = (caps[0][1] - caps[-1][1]) * 3600.0 / (caps[-1][0] - caps[0][0])
    batt = load(os.path.join(rdir, "battery.json")) or {}
    start = batt.get("t_device")
    if start is None and caps:
        start = caps[0][0]
    if start is None:
        ts = [os.path.getmtime(os.path.join(rdir, f)) for f in os.listdir(rdir)
              if f not in ("request.json", "DONE")]
        start = min(ts) if ts else None
    overhead = None
    if start is not None and end > start:
        overhead = max(0.0, (end - start) / runs - seconds)
    return dict(id=os.path.basename(rdir), label=res.get("device_label", ""),
                kind=kind_of(req), end=end, rate=rate, overhead=overhead)


def history(d, label, kind, n=HISTORY):
    """The last n finished results of this device and kind, newest first.
    A result directory reached through two names (a renamed id is a symlink)
    counts once."""
    seen, dirs = set(), []
    for p in glob.glob(os.path.join(d, "results", "*", "DONE")):
        real = os.path.realpath(os.path.dirname(p))
        if real in seen:
            continue
        seen.add(real)
        try:
            dirs.append((os.path.getmtime(p), real))
        except OSError:
            continue
    dirs.sort(reverse=True)
    rates, overheads = [], []
    for _, rdir in dirs:
        if len(rates) >= n and len(overheads) >= n:
            break
        rec = run_record(rdir)
        if rec is None or rec["label"] != label or rec["kind"] != kind:
            continue
        if rec["rate"] is not None and len(rates) < n:
            rates.append((rec["id"], rec["rate"]))
        if rec["overhead"] is not None and len(overheads) < n:
            overheads.append((rec["id"], rec["overhead"]))
    return rates, overheads


def learn(d, label, kind):
    rates, overheads = history(d, label, kind)
    if len(rates) >= MIN_HISTORY:
        rate, rsrc = max(0.0, pctl([r for _, r in rates])), "learned"
    else:
        rate = FALLBACK_RATE.get((label, kind), FALLBACK_RATE_OTHER)
        rsrc = "fallback"
    if len(overheads) >= MIN_HISTORY:
        ovh, osrc = pctl([o for _, o in overheads]), "learned"
    else:
        ovh, osrc = FALLBACK_OVERHEAD_S[kind], "fallback"
    return dict(rate=round(rate, 2), rate_src=rsrc, rate_n=len(rates),
                rate_from=rates, overhead_s=round(ovh, 1), overhead_src=osrc,
                overhead_n=len(overheads), overhead_from=overheads)


def learn_cached(d, label, kind):
    path = os.path.join(d, ".battery_rates.%s.%s.json" % (label, kind))
    c = load(path)
    if c and time.time() - c.get("t", 0) < RATES_TTL_S:
        return c["v"]
    v = learn(d, label, kind)
    tmp = path + ".%d" % os.getpid()
    try:
        with open(tmp, "w") as fh:
            json.dump(dict(t=time.time(), v=v), fh)
        os.replace(tmp, path)
    except OSError:
        pass
    return v


def check(d, label, req_path, level, head):
    req = load(req_path) or {}
    rid = os.path.basename(req_path)[:-4] if req_path.endswith(".req") else os.path.basename(req_path)
    kind = kind_of(req)
    runs = max(1, int(req.get("runs") or 1))
    seconds = float(req.get("seconds") or 0)
    lv = learn_cached(d, label, kind)
    dev_s = runs * (seconds + lv["overhead_s"])
    need = FLOOR + MARGIN + lv["rate"] * dev_s / 3600.0
    need = round(need + 0.049, 1)          # rounded up: never admit on a rounding
    now = time.time()
    state_path = os.path.join(d, ".battery_head.%s" % label)
    state = load(state_path) or {}
    inputs = "rate %.1f %%/h %s n=%d, %s x (%ds + overhead %ds %s n=%d)" % (
        lv["rate"], lv["rate_src"], lv["rate_n"], runs, seconds,
        lv["overhead_s"], lv["overhead_src"], lv["overhead_n"])
    rec = dict(battery_start=level, need=need, rate=lv["rate"],
               rate_src=lv["rate_src"], rate_n=lv["rate_n"],
               overhead_s=lv["overhead_s"], overhead_src=lv["overhead_src"],
               overhead_n=lv["overhead_n"], kind=kind, runs=runs,
               seconds=seconds, floor=FLOOR, margin=MARGIN, t_admit=now)
    if level < need:
        waited = 0
        if not head:
            # This is the device's head. Start its clock, or keep it running.
            if state.get("id") != rid:
                state = dict(id=rid, since=now)
                with open(state_path, "w") as fh:
                    json.dump(state, fh)
            waited = now - state["since"]
        print("BATTERY: skip %s: level %d < need %.1f (%s)%s" % (
            rid, level, need, inputs,
            "" if head else "; head, refused for %ds" % waited))
        print(json.dumps(rec))
        return 1
    if head:
        waited = now - state["since"] if state.get("id") == head else 0
        if waited >= HEAD_WAIT_S:
            print("BATTERY: hold for head %s (refused for %ds >= %ds): not backfilling %s, level %d >= need %.1f" % (
                head, waited, HEAD_WAIT_S, rid, level, need))
            print(json.dumps(rec))
            return 3
        rec["backfill_for"] = head
        print("BATTERY: admit %s as backfill for %s (refused %ds of %ds): level %d >= need %.1f (%s)" % (
            rid, head, waited, HEAD_WAIT_S, level, need, inputs))
    else:
        try:
            os.remove(state_path)
        except OSError:
            pass
        print("BATTERY: admit %s: level %d >= need %.1f (%s)" % (rid, level, need, inputs))
    print(json.dumps(rec))
    return 0


def main(argv):
    if len(argv) >= 6 and argv[1] == "check":
        return check(argv[2], argv[3], argv[4], int(argv[5]),
                     argv[6] if len(argv) > 6 else "")
    if len(argv) == 5 and argv[1] == "learn":
        print(json.dumps(learn(argv[2], argv[3], argv[4]), indent=1))
        return 0
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
