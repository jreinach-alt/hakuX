#!/usr/bin/env python3
"""Add three soaks (request.json, logcat with hakuX-perf gfps, DONE) to a COPY
of the 16:24 fixture's work tree, and write <synth dir>/measured.json: the
titles that must count as Measured, computed from the fixture's inputs alone
(the backfill's rows with fps, the synthetic verdicts with fps, and the soaks
below whose gfps fall in 90-240 s), never from the renderer.

    soaks.py <copied fixture work dir> <synth dir>
"""
import datetime, json, os, re, sys, tomllib

WORK, SYN = sys.argv[1:3]
NOW = 1790465073                                   # the fixture's clock
RES = os.path.join(WORK, "dispatch", "results")

# (request id, ISO, device, first gfps second, last gfps second, gfps, the title it names or None)
SOAKS = [
    ("1790460000-measured05-soakonly", "Zz Soak Only (USA).xiso.iso", "nova", 0, 300, 41.0, "Zz Soak Only"),
    ("1790460100-measured05-purple-t", "5A5A0005-Zz_Purple.xiso.iso", "thor", 0, 240, 33.0, "Zz Purple"),
    ("1790460200-measured05-purple-n", "5A5A0005-Zz_Purple.xiso.iso", "nova", 0, 240, 34.0, "Zz Purple"),
    ("1790460300-measured05-menu", "Zz Soak Menu (USA).xiso.iso", "thor", 0, 60, 59.0, None),
]
t0 = datetime.datetime(2026, 9, 26, 22, 0, 0)
for k, (rid, iso, dev, a, b, g, _) in enumerate(SOAKS):
    rd = os.path.join(RES, rid)
    os.makedirs(rd, exist_ok=True)
    json.dump({"id": rid, "title": iso, "device": dev, "ref": "abcdef1234", "seconds": 300}, open(os.path.join(rd, "request.json"), "w"))
    with open(os.path.join(rd, "logcat.txt"), "w") as fh:
        for s in range(a, b + 1, 5):
            fh.write("%s  1234  5678 I hakuX-perf: fps=%g gfps=%g\n" % ((t0 + datetime.timedelta(seconds=s)).strftime("%m-%d %H:%M:%S.000"), g, g))
    open(os.path.join(rd, "DONE"), "w").close()
    at = NOW - 3600 + 60 * k
    os.utime(os.path.join(rd, "DONE"), (at, at))

want = set()
# A verdict with no name (scored before its registry entry) is the title its
# ISO's title-ID prefix names in the fixture's registry (synth.py's).
reg = tomllib.load(open(os.path.join(SYN, "targets.toml"), "rb")).get("titles", {})
bf = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../dash432/pass1-backfill.json")))
want |= {r["title"] for r in bf["rows"] if r.get("fps_median") is not None}
for n in os.listdir(RES):
    p = os.path.join(RES, n, "verdict.json")
    if os.path.exists(p):
        v = json.load(open(p))
        if v.get("fps_window_median") is not None:
            m = re.match(r"([0-9A-Fa-f]{8})-", v.get("title") or "")
            want.add(v.get("name") or reg[m.group(1).upper()]["name"])
want |= {s[6] for s in SOAKS if s[6]}
json.dump(sorted(want), open(os.path.join(SYN, "measured.json"), "w"), indent=1)
