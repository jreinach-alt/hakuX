# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# status_html.py's title table must not overstate a title's fps (#433).
#
# WHY THIS EXISTS. lane.verdict433 (#433, 13:33Z 2026-09-29) found the 0.5
# title table showing "59.9 fps, 100%" for titles that a real run of
# title_verdict.py, over the SAME logcat, scored 22-47% (Kabuki, with hangs
# of 22-72 s), 81% (Bruce Lee, a 21 s hang) and 0% (BF2 MC, D&D Heroes): the
# table's own soak fallback (before this fix) read only the Ghoulies gate's
# fixed 90-240 s slice, never the full gameplay window (mark to `soak end`)
# title_verdict.py judges a stored verdict by -- so a title that fell over
# right after the slice ended still showed as ready to confirm.
#
# The two logcats below share one shape -- 100% at 60 fps in the 90-240 s
# slice (anchored at the first perf line), then ~8 fps (under the 28.5 bar)
# from 255 s to the end -- one with a route (title_verdict.py can score its
# full window from the mark) and one without (it cannot, so status_html.py
# must fall back to the slice and LABEL it one, never a verdict).
#
# Independent of every other fragment: its own dispatch dir, targets.toml and clock.

echo "== status_html.py: the title table reads the full gameplay window, not a 90-240 s slice (#433)"
FW="$T/fullwindow"; rm -rf "$FW"; mkdir -p "$FW"
cat > "$FW/check.py" <<'PY'
import json, os, sys, time

JOBS, ROOT = sys.argv[1:3]
sys.path.insert(0, JOBS)


def stamp(t):
    return "09-25 %02d:%02d:%06.3f" % (t // 3600, (t % 3600) // 60, t % 60)


def write_logcat(path, mark):
    """100% at 60 fps from t=100.5 to 255 s (the 90-240 s slice, anchored at
    the first perf line t0=10, sits entirely inside this span), then ~8 fps
    (under the 28.5 bar) to t=757.5, `soak end` at 760. `mark` writes
    `mark gameplay` at t=100 -- title_verdict.py's own start of the scored
    window -- or omits it, for the route-less case."""
    lines = [(1.0, "I", "hakuX", "surface_scale=1 (override=)"),
             (2.0, "I", "hakuX-route", "soak start")]
    t = 10.0
    while t < 100.0:
        lines.append((t, "I", "hakuX-perf", "gfps=10 G:100.0(90.0-110.0)"))
        t += 6.0
    if mark:
        lines.append((100.0, "I", "hakuX-route", "mark gameplay"))
    t = 100.5
    while t < 255.0:
        lines.append((t, "I", "hakuX-perf", "gfps=60 G:16.7(15.0-18.0)"))
        t += 1.0
    t = 255.0
    while t < 759.5:
        lines.append((t, "I", "hakuX-perf", "gfps=8 G:120.0(100.0-140.0)"))
        t += 7.5
    lines.append((760.0, "I", "hakuX-route", "soak end"))
    lines.sort(key=lambda x: x[0])
    with open(path, "w") as fh:
        for t, lv, tag, msg in lines:
            fh.write("%s %s/%s( 4242): %s\n" % (stamp(t), lv, tag, msg))


def title_dir(rid, name, tid, device, route):
    rd = os.path.join(ROOT, "dispatch", "results", rid)
    os.makedirs(rd, exist_ok=True)
    iso = "%s-%s.xiso.iso" % (tid, name.replace(" ", "_"))
    write_logcat(os.path.join(rd, "logcat.txt"), mark=bool(route))
    req = {"id": rid, "title": iso, "ref": "abc1234567", "device": device}
    if route:
        req.update(route_name=route + ".returning", route="wait 1\n")
    json.dump(req, open(os.path.join(rd, "request.json"), "w"))
    json.dump({"device_label": device}, open(os.path.join(rd, "result.json"), "w"))
    open(os.path.join(rd, "run.log"), "w").write("ROUTE started\n")
    json.dump({"regimen": "max", "perf_mode": 2, "max": {"perf_mode": 2}, "rest": {"perf_mode": 0}},
              open(os.path.join(rd, "perf_regimen.json"), "w"))
    open(os.path.join(rd, "DONE"), "w").close()
    return rd, iso


def registry(tid, name, iso, device):
    return '[titles."%s"]\nname = "%s"\niso = { %s = "%s" }\nroute = "burnout3"\n\n' % (
        tid, name, device, iso)


targets_p = os.path.join(ROOT, "targets.toml")
ts_dir = os.path.join(ROOT, "titlestate")
os.environ["TITLE_TARGETS"] = targets_p
os.environ["TITLESTATE_DIR"] = ts_dir

rdA, isoA = title_dir("1790470000-fw-a", "Zz Fullwindow Full", "5A5A0091", "nova", "burnout3")
rdB, isoB = title_dir("1790470100-fw-b", "Zz Fullwindow Screen", "5A5A0092", "nova", None)
open(targets_p, "w").write(registry("5A5A0091", "Zz Fullwindow Full", isoA, "nova") +
                            registry("5A5A0092", "Zz Fullwindow Screen", isoB, "nova"))
for tid in ("5A5A0091", "5A5A0092"):
    d = os.path.join(ts_dir, "saves", tid, "s-" + tid.lower())
    os.makedirs(d, exist_ok=True)
    json.dump({"title_id": tid, "save_id": "s-" + tid.lower()}, open(os.path.join(d, "save.json"), "w"))

import status_html as S

now = int(time.time()) + 60
conf_path = os.path.join(ROOT, "release-0.5.toml")


def run():
    F = S.Facts({"WORK": ROOT, "D": os.path.join(ROOT, "dispatch"), "REPO": "", "GH_REPO": "",
                 "HAVE_GH": "0", "HAVE_SD": "0", "STATUS_NOW": str(now)})
    return S.titles05(F, {}, conf_path, now)


def row(res, name):
    return next(r for r in res["rows"] if r["title"] == name)


fails = []
res = run()
a = row(res, "Zz Fullwindow Full")
b = row(res, "Zz Fullwindow Screen")

# A: title_verdict.py can score the full window (a route to mark from). Its
# share must be the full window's (~23%, well under the 90% bar), not the
# 90-240 s slice's (~100%), and it must never show as a Playable candidate.
if a["stage"] in ("soak", "playable"):
    fails.append("A: stage is %r, a Playable candidate on a run that fails at full window" % a["stage"])
share_a = (a.get("prim") or {}).get("share")
if share_a is None or share_a >= 0.5:
    fails.append("A: fps cell share is %r; the full window (~0.23) must show, not the slice (~1.0)" % share_a)
if (a.get("prim") or {}).get("hang"):
    fails.append("A: no hang was written into the logcat, but hang reads true")

# B: no route, so title_verdict.py has no mark to score a window from; it
# must fall back to the slice, LABELLED as one, and never as a verdict.
if b["stage"] in ("soak", "playable"):
    fails.append("B: stage is %r, a Playable candidate on a slice-only reading" % b["stage"])
pb = b.get("prim") or {}
if not pb.get("screen_only"):
    fails.append("B: the route-less reading is not marked screen_only")
if "screen: 90-240 s only" not in (pb.get("verdict") or ""):
    fails.append("B: the route-less reading's verdict does not plainly say it is a slice: %r" % pb.get("verdict"))
if pb.get("share") is None or pb["share"] < 0.9:
    fails.append("B: the slice itself should read close to 100%%, got %r" % pb.get("share"))

# Mutant: without the live full-window judge, A's OWN reading falls back to
# the same slice B uses, and reads ~100% too -- proving the checks above
# catch the regression rather than a quirk of the fixture.
orig = S._title_verdict_module
S._title_verdict_module = lambda: None
try:
    res2 = run()
finally:
    S._title_verdict_module = orig
a2 = row(res2, "Zz Fullwindow Full")
pa2 = a2.get("prim") or {}
if pa2.get("share") is None or pa2["share"] < 0.9:
    fails.append("mutant SURVIVED: without the live judge, A should fall back to the ~100%% slice "
                 "(got %r) -- the fixture is not exercising the fix" % pa2.get("share"))

if fails:
    print("\n".join("FAIL " + f for f in fails))
    sys.exit(1)
print("all ok: full-window share=%r hang=%r; slice share=%r label=%r" % (
    share_a, (a.get("prim") or {}).get("hang"), pb.get("share"), pb.get("verdict")))
PY
python3 "$FW/check.py" "$HERE" "$FW" > "$FW/out.txt" 2>&1
check "the full-window run scores its real share (not the 90-240 s slice) and never reads as a Playable candidate; the route-less run is plainly labelled a slice" \
    grep -q "^all ok" "$FW/out.txt"
grep '^FAIL\|Traceback' "$FW/out.txt" | sed 's/^/    /'
