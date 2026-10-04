# Sourced by ../selftest.sh with the harness already built: $T, $TESTING, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# lane.failgate (#433, 2026-10-03): a failed or unproven run goes for
# identification, not a re-run. Repo-side holes, one block each:
#   1. the liveness window falls back to frames/ when route-frames are short,
#      and an unmeasured window FAILS the verdict (not Playable-eligible);
#   2. the position test: a window whose samples do not change is not gameplay;
#   3. request.sh's failure gate: a HELD title is refused before queueing;
#   4. the contact sheet names each source, so a boot sample is not read as a
#      second start. Checked only with PIL (CI has none).
# The Playable wall (item 5) is not here: it is docs/lanes/failgate/item5-wall.diff,
# waiting on a territory grant for docs/testing/jobs/status_html.py.
#
# Pure functions and stub tools only: no device, no host tools, no GitHub.

echo "== failgate: the liveness window, the position test, the gate, the wall"
FG="$T/failgate"; rm -rf "$FG"; mkdir -p "$FG"

# 1. window_frames(): route-frames first, frames/ when route-frames are short,
# and unmeasured when neither has FROZEN_MIN_FRAMES after the mark. Names carry
# the clock (HHMMSS-), the way the dispatcher writes them; no pixels are read.
python3 - "$TESTING" "$FG" <<'PY' > "$FG/window.out" 2>&1
import os, sys
sys.path.insert(0, sys.argv[1])
import hitch_report as hr
root = sys.argv[2]
T0 = 13 * 3600
def stamp(t):
    return "%02d%02d%02d" % ((T0 + t) // 3600, ((T0 + t) % 3600) // 60, (T0 + t) % 60)
def run(name, route, boot):
    d = os.path.join(root, name)
    for sub, ts in (("route-frames", route), ("frames", boot)):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
        for t in ts:
            open(os.path.join(d, sub, "%s-x.png" % stamp(t)), "w").close()
    with open(os.path.join(d, "logcat.txt"), "w") as f:
        f.write("09-25 13:00:00.000 I/hakuX(4242): start\n")
    return d
mark, end = hr.ts("09-25 13:01:40.000"), hr.ts("09-25 13:11:40.000")   # the fixture's clock: 100 s and 700 s after 13:00:00
fails = []
d = run("short-route", [110, 200], [120, 300, 400, 500])
src, after, why = hr.window_frames(d, mark, end)
if src != "frames" or len(after) != 4:
    fails.append("A: 2 route + 4 boot post-mark should fall back to frames/, got %r %r" % (src, len(after)))
d = run("full-route", [110, 200, 300], [120, 400])
src, after, why = hr.window_frames(d, mark, end)
if src != "route-frames" or len(after) != 3:
    fails.append("B: 3 post-mark route-frames should win, got %r %r" % (src, len(after)))
d = run("none", [50, 90], [60, 800])
src, after, why = hr.window_frames(d, mark, end)
if src is not None or after:
    fails.append("C: frames before the mark or after the end must not count, got %r" % src)
if why is None or "need 3" not in why:
    fails.append("C: the unmeasured reason does not say what is missing: %r" % why)
d = run("pre-mark", [90, 95, 99], [])
sw = hr.static_window(d, mark, end)
if sw.get("measured") is not False or sw.get("source") is not None:
    fails.append("D: a window with no post-mark frames must be unmeasured, got %r" % sw)
print("\n".join(fails) if fails else "ok")
PY
if [ "$(cat "$FG/window.out")" = "ok" ]; then
    ok "1: the window reads frames/ when route-frames are short, and says why when it cannot"
else bad "1: window_frames: $(cat "$FG/window.out")"; fi

# 1b. An unmeasured window fails the verdict as `window unmeasured`, and a
# measured one does not. Pure dicts: no PIL needed.
python3 - "$TESTING" <<'PY' > "$FG/unmeasured.out" 2>&1
import sys
sys.path.insert(0, sys.argv[1])
import hitch_report as hr
fails = []
bad_sw = dict(measured=False, reason="0 post-mark route-frame(s)", frozen_frac=None, n=0, source=None)
f, why = hr.static_window_unmeasured(bad_sw)
if not f or not why.startswith("window unmeasured") or "0 post-mark" not in why:
    fails.append("unmeasured did not fail, or did not name the reason: %r" % why)
if hr.static_window_unmeasured(dict(measured=True, frozen_frac=0.01, n=12, source="route-frames"))[0]:
    fails.append("a measured window failed as unmeasured")
if hr.static_window_fail(bad_sw) != (False, None):
    fails.append("static_window_fail judged an unmeasured window (its contract is unchanged)")
print("\n".join(fails) if fails else "ok")
PY
if [ "$(cat "$FG/unmeasured.out")" = "ok" ]; then
    ok "1b: an unmeasured scored window fails as window unmeasured; a measured one does not"
else bad "1b: unmeasured rule: $(cat "$FG/unmeasured.out")"; fi

# 2. position_fail(): the window's first and last samples the same scene, or
# more than half its consecutive pairs still, fails; a moving window passes.
# Dicts only, so the bar and the arithmetic are what is tested.
python3 - "$TESTING" <<'PY' > "$FG/position.out" 2>&1
import sys
sys.path.insert(0, sys.argv[1])
import hitch_report as hr
def pc(first_last, still, pairs, bar=0.025):
    return dict(measured=True, reason=None, source="route-frames", samples=pairs + 1, pairs=pairs,
                still=still, still_frac=round(still / pairs, 4), first_last=first_last, bar=bar)
fails = []
if not hr.position_fail(pc(0.0, 0, 10))[0]:
    fails.append("first == last (0.0) did not fail")
if not hr.position_fail(pc(0.3, 6, 10))[0]:
    fails.append("60% still pairs did not fail (bar is > 50%)")
if hr.position_fail(pc(0.3, 5, 10))[0]:
    fails.append("exactly 50% still failed (the bar is strictly more than half)")
if hr.position_fail(pc(0.3, 0, 10))[0]:
    fails.append("a moving window failed")
if hr.position_fail(dict(measured=False, reason="x", first_last=None, still_frac=None, bar=0.025))[0]:
    fails.append("an unmeasured position failed here (static_window_unmeasured owns that)")
print("\n".join(fails) if fails else "ok")
PY
if [ "$(cat "$FG/position.out")" = "ok" ]; then
    ok "2: a window with no scene change between its ends, or on most samples, is not gameplay"
else bad "2: position_fail: $(cat "$FG/position.out")"; fi

# 3. request.sh's failure gate, against a stub failure_intake.py. The stub
# answers `gate` from FI_MODE: held (exit 1 + HELD line), released (0), broken
# (2, no HELD). Judged on the words and on the queue, as the pilot gate is.
cat > "$FG/intake_stub.py" <<'PY'
import os, sys
mode = os.environ.get("FI_MODE", "released")
if sys.argv[1:2] != ["gate"]:
    sys.exit(0)
if mode == "held":
    print("HELD pathfind (%s): open route since 1790895867 (fx); route and golden unchanged. "
          "Identify and fix first (pm/pathfind-pool.tsv)." % sys.argv[2])
    sys.exit(1)
if mode == "broken":
    print("Traceback: boom")
    sys.exit(2)
sys.exit(0)
PY
fg_rq() {  # <dir> <who> [extra args...]: a soak of Crimson Skies (4D530021), the pilot gate's shape
    local d="$1" who="$2"; shift 2
    DISPATCH_DIR="$d" HAKUX_FAILURE_INTAKE="$FG/intake_stub.py" bash "$TESTING/request.sh" --who "$who" \
        --purpose "failgate selftest" --no-expect selftest --title "4D530021-Crimson Skies.iso" --seconds 60 "$@" 2>&1; }
fg_dir() { local d="$FG/$1"; rm -rf "$d"; mkdir -p "$d"/{queue,running,results,pilots}; echo "$d"; }
fg_n() { ls "$1"/queue/*.req 2>/dev/null | wc -l; }
fg_ok() { grep -qE "^queued [0-9]+-$1-[0-9]+$" <<< "$2"; }

# A. HELD, no --identified: refused with the tool's own message, exit 3, nothing queued.
D=$(fg_dir held)
out=$(FI_MODE=held fg_rq "$D" fgheld); rc=$?
if [ "$rc" = 3 ] && grep -q "refusing to queue: HELD pathfind" <<< "$out" && grep -q "identify the failure first" <<< "$out"; then
    ok "3A: a held title is refused with the tool's message and exit 3"
else bad "3A: held title: exit $rc, $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "3A: and nothing was queued" [ "$(fg_n "$D")" -eq 0 ]

# B. HELD, with --identified: admitted, and the id is recorded in the request.
out=$(FI_MODE=held fg_rq "$D" fgheld --identified 1790895867-autoverdict-3359625)
if fg_ok fgheld "$out" && grep -q "identified by 1790895867-autoverdict-3359625" <<< "$out"; then
    ok "3B: --identified admits a held title, and says which identification it used"
else bad "3B: --identified did not admit a held title: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "3B: the request records the identification" python3 -c '
import glob, json, sys
rq = [json.load(open(p)) for p in glob.glob(sys.argv[1] + "/queue/*.req")]
assert rq and rq[0]["identified"] == "1790895867-autoverdict-3359625", rq' "$D"

# C. RELEASED (the golden or route changed since the failure, which the host
# tool decides): admitted with no --identified, and the record says so.
D=$(fg_dir released)
out=$(FI_MODE=released fg_rq "$D" fgrel)
if fg_ok fgrel "$out" && [ "$(fg_n "$D")" -eq 1 ]; then ok "3C: a released title queues with no identification"
else bad "3C: a released title was refused: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "3C: and its record has an empty identified field" python3 -c '
import glob, json, sys
rq = [json.load(open(p)) for p in glob.glob(sys.argv[1] + "/queue/*.req")]
assert rq and rq[0]["identified"] == "", rq' "$D"

# D. A BROKEN gate (exit 2, no HELD line) refuses rather than admits: an open
# identification must not be skipped by a crash in the tool that holds it.
D=$(fg_dir broken)
out=$(FI_MODE=broken fg_rq "$D" fgbrk); rc=$?
if [ "$rc" = 3 ] && grep -q "failure_intake gate failed" <<< "$out" && [ "$(fg_n "$D")" -eq 0 ]; then
    ok "3D: a gate that fails is a refusal, not an admission"
else bad "3D: broken gate: exit $rc, $(tail -3 <<< "$out" | tr '\n' ' ')"; fi

# E. NO TOOL (CI, a fresh checkout): no gate at all, the request queues as before.
D=$(fg_dir absent)
out=$(DISPATCH_DIR="$D" HAKUX_FAILURE_INTAKE="$FG/nope/failure_intake.py" bash "$TESTING/request.sh" \
        --who fgabs --purpose "failgate selftest" --no-expect selftest --title "4D530021-Crimson Skies.iso" \
        --seconds 60 2>&1)
if fg_ok fgabs "$out"; then ok "3E: with no failure_intake.py the request queues as before"
else bad "3E: absent tool blocked the request: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi

# 4. The contact sheet: route frames and boot samples are two groups under their
# own headers, so the sheet's height has two header bands. Needs PIL.
if python3 -c 'import PIL, numpy' 2>/dev/null; then
    python3 - "$TESTING" "$FG" <<'PY' > "$FG/sheet.out" 2>&1
import os, sys
sys.path.insert(0, sys.argv[1])
from PIL import Image
import title_verdict as tv
root = os.path.join(sys.argv[2], "sheet"); os.makedirs(root, exist_ok=True)
for sub, names in (("route-frames", ["110000-a.png", "110030-b.png", "110100-c.png"]), ("frames", ["120000-x.png", "120030-y.png"])):
    os.makedirs(os.path.join(root, sub), exist_ok=True)
    for n in names:
        Image.new("RGB", (64, 48), (90, 90, 90)).save(os.path.join(root, sub, n))
name, why = tv.contact_sheet(root, os.path.join(root, "contact.png"))
im = Image.open(os.path.join(root, "contact.png"))
# one row each group (5 tiles in 6 columns): two 22 px headers and two 196 px rows
if why or im.size != (6 * 320, 2 * 22 + 2 * 196):
    print("sheet is %r, want (1920, 436): %s" % (im.size, why))
else:
    print("ok")
PY
    if [ "$(cat "$FG/sheet.out")" = "ok" ]; then
        ok "4: the contact sheet has a band for each source, so a boot sample is not read as a second start"
    else bad "4: contact sheet: $(cat "$FG/sheet.out")"; fi
else
    echo "  (4: skipped, PIL unavailable on this runner)"
fi

rm -rf "$FG"; unset FG D out rc
unset -f fg_rq fg_dir fg_n fg_ok
