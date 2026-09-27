#!/usr/bin/env python3
"""Add a synthetic title registry to a COPY of the 16:24 fixture's work tree.

    synth.py <copied fixture work dir> <synth dir> <repo>

One title at each stage of the 0.5 scale (#433), each reaching it the way a
real title would: entries added to the fixture's targets.toml (ISO per device, route), a save in
titlestate's store, title_verdict.py-shaped verdict.json files beside
soak_title.sh's perf_regimen.json, a staged-ISO manifest, and an [issues] map.
Plus twelve staged titles, so the "not copied" tail folds after ten, and a
devwatch.json four minutes past stale.

Writes into <synth dir>: targets.toml, release-0.5.toml, xiso/manifest.csv,
devwatch.json, and expect.json (what each synthetic title must render as).
"""
import json, os, re, sys

WORK, OUT, REPO = sys.argv[1:4]
NOW = 1790465073                                  # the fixture's clock, 16:24:33 PDT
os.makedirs(os.path.join(OUT, "xiso"), exist_ok=True)

# name, tid, ISO devices, route, save, verdicts [(device, kind, fps, share, reached, pass, crash)], stage
SYN = [
    ("Zz Red", "5A5A0001", ("thor", "nova"), "burnout3", True, [("thor", "screening", 31.0, 0.95, True, False, True)], "blocked"),
    ("Zz Green", "5A5A0002", ("thor", "nova"), "burnout3", True, [("nova", "screening", 58.0, 0.99, True, True, False),
                                                                 ("nova", "confirmation", 57.5, 0.98, True, True, False)], "Playable"),
    ("Zz Orange", "5A5A0003", ("thor", "nova"), "burnout3", True, [("thor", "screening", 44.0, 0.96, True, True, False)], "soak pending"),
    ("Zz Yellow", "5A5A0004", ("thor", "nova"), "burnout3", True, [("nova", "screening", 22.5, 0.12, True, False, False)], "below 30"),
    ("Zz Purple", "5A5A0005", ("thor", "nova"), "burnout3", True, [], "inputs ready"),
    ("Zz Blue", "5A5A0006", ("thor",), "", False, [], "copied"),
    # lane.titleroutes' shapes (PR #455): one route with no profile step needs
    # no save, so it is inputs ready; a first-run route alone still needs one.
    ("Zz Purple Single Route", "5A5A0007", ("nova",), "kabuki-warriors", False, [], "inputs ready"),
    ("Zz Blue First Run: Tom Clancy's Rainbow Six 3 Black Arrow", "5A5A0008", ("nova",), "goldeneye-ra", False, [], "copied"),
]
GREY = [("Zz Grey %02d" % i, "5A5A01%02d" % i) for i in range(1, 13)]

# The registry the synthetic titles join is the fixture's own copy, not the
# live docs/testing/titles/targets.toml: every title the live file names is a
# row on the page, so each edit to it moved the counts asserted here
# (targets.toml beside this file says what that cost).
tg = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "targets.toml"), encoding="utf-8").read()
for name, tid, devs, route, save, verdicts, _ in SYN:
    tg += '\n[titles."%s"]\nname = "%s"\niso = { %s }\n' % (
        tid, name, ", ".join('%s = "%s-%s.xiso.iso"' % (d, tid, name.replace(" ", "_")) for d in devs))
    if route:
        tg += 'route = "%s"\n' % route
open(os.path.join(OUT, "targets.toml"), "w").write(tg)

ts = os.path.join(WORK, "dispatch", "titlestate")
for name, tid, devs, route, save, verdicts, _ in SYN:
    if save:
        d = os.path.join(ts, "saves", tid, "s-" + tid.lower())
        os.makedirs(d, exist_ok=True)
        json.dump({"title_id": tid, "save_id": "s-" + tid.lower()}, open(os.path.join(d, "save.json"), "w"))
    for k, (dev, kind, fps, share, reached, ok, crash) in enumerate(verdicts):
        rid = "1790450000-synth-%s-%d" % (tid.lower(), k)
        rd = os.path.join(WORK, "dispatch", "results", rid)
        os.makedirs(rd, exist_ok=True)
        v = {"title": "%s-%s.xiso.iso" % (tid, name.replace(" ", "_")), "title_id": tid, "name": name, "device": dev,
             "ref": "abcdef1234", "request_id": rid, "route": route + ".returning", "reached_gameplay": reached,
             "crash": crash, "hang": False, "fps_window_median": fps, "fps_ok_share": share, "pass": ok,
             "pass_kind": kind, "failing": "crash: SIGSEGV in the guest" if crash else (None if ok else "fps: 12% of play at >= 30"),
             "failures": [], "rating_candidate": "Playable" if ok else None}
        json.dump(v, open(os.path.join(rd, "verdict.json"), "w"))
        json.dump({"regimen": "max", "perf_mode": 2, "fan_mode": 4, "max": {"perf_mode": 2, "fan_mode": 4},
                   "rest": {"perf_mode": 0, "fan_mode": 4}}, open(os.path.join(rd, "perf_regimen.json"), "w"))
        for f in ("verdict.json", "perf_regimen.json"):
            os.utime(os.path.join(rd, f), (NOW - 7200 + 60 * k, NOW - 7200 + 60 * k))

with open(os.path.join(OUT, "xiso", "manifest.csv"), "w") as fh:
    fh.write("title_id,name,xemu_rank,xemu_rating,source_path,xiso_bytes,sha256,staged_utc\n")
    for name, tid in GREY:
        fh.write("%s,%s,1,Playable,X:\\\\Games\\\\%s,1,0,2026-09-26T06:00:00Z\n" % (tid, name, tid))

# SYNTH_CONF: the release config to start from (the proof's "before" run
# passes #448's own, docs/lanes/dash432/release-0.5.toml at deb0903b51).
conf = open(os.environ.get("SYNTH_CONF") or os.path.join(REPO, "docs/testing/release-0.5.toml"), encoding="utf-8").read()
conf = re.sub(r'(?m)^backfill = ".*"$', 'backfill = "%s"' % os.path.join(REPO, "docs/lanes/dash432/pass1-backfill.json"), conf)
if "\n[issues]" not in conf:
    conf += "\n[issues]\n"
conf += '"Zz Grey 01" = 9901\n'           # open, no lane, no run, no tracker row: the alarm
open(os.path.join(OUT, "release-0.5.toml"), "w").write(conf)

json.dump({"updated": NOW - 540, "updated_pdt": "16:15", "devices": {
    "thor": {"state": "hands-on", "since_pdt": "16:13", "detail": "lane.titlestate", "flags": ["held-idle"],
             "minutes_60": {"hands-on": 40, "held-idle": 12, "running": 8}},
    "nova": {"state": "idle-waiting", "since_pdt": "16:20", "detail": "", "flags": [],
             "minutes_60": {"running": 50, "idle-waiting": 4, "overdue": 2}}}},
          open(os.path.join(OUT, "devwatch.json"), "w"))
json.dump({n: s for n, _, _, _, _, _, s in SYN} | {n: "not copied" for n, _ in GREY},
          open(os.path.join(OUT, "expect.json"), "w"), indent=1)
