# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# status_html.py: the 0.6 curve toward 1.0 (#433) -- Chart 1 ("How close is
# 0.6?"), Chart 2 ("How close is 1.0?"), the rolling 7-day-rate projection,
# and the projected-date table. Direct unit tests of the chart and forecast
# code, since the titles05/measured05 fixtures each pin their own synthetic
# 0.5-style release conf (no curve, no prior_published) and so never exercise
# any of this.
#
# Independent of every other fragment: its own tree, clock and conf dict.

echo "== status_html.py: the 0.6 curve, the 1.0 projection chart (#433)"

# _perf_label: the fps cell's words. Never "unrecorded" again (a required mutant).
check "fps cell words: max perf / default perf / nothing, never 'unrecorded'" python3 -c '
import sys; sys.path.insert(0, sys.argv[1]); import status_html as S
sys.exit(0 if S._perf_label("MAX") == "max perf" and S._perf_label("REST") == "default perf"
         and S._perf_label("unrecorded") == "" and "unrecorded" not in (S._perf_label("MAX"), S._perf_label("REST"), S._perf_label("unrecorded"))
         else 1)' "$HERE"

# _proj: "met" when the target is already reached; a date when the rolling
# 7-day rate is positive; "no progress in 7 days" when it is zero.
check "_proj: met / a projected date / no progress in 7 days" python3 -c '
import sys; sys.path.insert(0, sys.argv[1]); import status_html as S
now = 1790000000
met, eta = S._proj(900, 5 / 7.0, 876, now)
no, eta2 = S._proj(100, 0.0, 876, now)
days = (876 - 100) * 86400.0 / (10 / 7.0)
want, eta3 = S._proj(100, 10 / 7.0, 876, now)
sys.exit(0 if met == "met" and eta == now and no == "no progress in 7 days" and eta2 is None
         and abs(eta3 - (now + days)) < 2 and want[:4].isdigit() and "-" in want else 1)' "$HERE"

# titles05's forecast: a separate rolling 7-day rate (titles reaching Measured
# in the last 7 days / 7), never the all-time rate (a required mutant) and
# never conf's rate_hours window (the "Ships when both are met" line's rate).
check "the 1.0 projection's rate is the rolling 7 days, not all-time and not rate_hours" python3 -c '
import json, os, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
root = sys.argv[2]; os.makedirs(root, exist_ok=True)
R = os.path.join(root, "results")
tg = os.path.join(root, "targets.toml"); open(tg, "w").write("[defaults]\nplayable_fps = 30\nfps_tolerance = 0.95\n")
os.environ["TITLE_TARGETS"] = tg; os.environ["TITLESTATE_DIR"] = os.path.join(root, "ts")
NOW = 1790000000
# 5 titles measured within the last 7 days (10..160 h ago); 2 older (200, 300 h ago).
ages_h = [10, 30, 50, 100, 160, 200, 300]
for i, age in enumerate(ages_h):
    tid = "5A5A02%02d" % i
    d = os.path.join(R, "curve-%d" % i); os.makedirs(d, exist_ok=True)
    at = NOW - int(age * 3600)
    json.dump({"name": "Zz Curve %d" % i, "title_id": tid, "title": "%s-Zz_Curve_%d.xiso.iso" % (tid, i), "device": "nova",
               "fps_window_median": 30.0, "fps_ok_share": 1.0, "fps_bar": 30.0, "reached_gameplay": True, "pass": False,
               "failing": "fps"}, open(os.path.join(d, "verdict.json"), "w"))
    os.utime(os.path.join(d, "verdict.json"), (at, at))
E = {"WORK": root, "D": root, "STATUS_XISO_DIR": root, "STATUS_TITLES_DIR": root}
F = S.Facts(E); F.now = NOW
conf = {"measured_target": 300, "playable_target": 110, "rate_hours": 48,
        "curve": [{"release": "0.6", "measured": 300, "playable": 110}, {"release": "1.0", "measured": 876, "playable": 789}]}
t = S.titles05(F, conf, os.path.join(root, "none.toml"), F.now)
have = t["counts"]["measured"]
rate7 = t["forecast"]["measured"]["rate7"]
sys.exit(0 if have == 7 and abs(rate7 - 5 / 7.0) < 1e-9 else 1)' "$HERE" "$T/status-curve-rate"

# Chart 1: a labelled vertical line at the 0.5 publish, and dashed horizontal
# lines at the 0.6 targets. Removing the line (a required mutant) must fail this.
check "Chart 1 draws a vertical line at the 0.5 publish, and dashed lines at the 0.6 targets" python3 -c '
import sys; sys.path.insert(0, sys.argv[1]); import status_html as S
now = 1790000000
series = {"measured": [[now - 5 * 86400, 3], [now - 86400, 7]], "playable": [[now - 86400, 2]]}
pub_at = now - 3 * 86400
svg = S._chart1(series, now, 300, 110, pub_at, "0.5")
ok = ("0.5 published" in svg and "Measured target 300" in svg and "Playable target 110" in svg
      and "Benchmarked" not in svg and "stroke-dasharray:2 2" in svg)
sys.exit(0 if ok else 1)' "$HERE"

check "Chart 1 omits the vertical line when the prior release has no publish date" python3 -c '
import sys; sys.path.insert(0, sys.argv[1]); import status_html as S
now = 1790000000
series = {"measured": [[now - 86400, 7]], "playable": [[now - 86400, 2]]}
svg = S._chart1(series, now, 300, 110, None, "0.5")
sys.exit(0 if "0.5 published" not in svg else 1)' "$HERE"

# Chart 2: the 0.6-1.0 curve as levels, and a dashed projection line to 1.0
# when the rate is positive -- never using the all-time rate (a required mutant).
check "Chart 2 draws the release curve as levels and a 7-day-rate projection to 1.0" python3 -c '
import sys; sys.path.insert(0, sys.argv[1]); import status_html as S
now = 1790000000
series = {"measured": [[now - 5 * 86400, 100], [now - 86400, 150]], "playable": [[now - 86400, 20]]}
curve = [{"release": "0.6", "measured": 300, "playable": 110}, {"release": "1.0", "measured": 876, "playable": 789}]
fc = {"measured": {"rate7": 10.0}, "playable": {"rate7": 2.0}}
svg = S._chart2(series, now, curve, fc)
ok = ("0.6 Measured 300" in svg and "1.0 Playable 789" in svg and "Benchmarked" not in svg
      and "stroke-dasharray:4 3" in svg)
sys.exit(0 if ok else 1)' "$HERE"

check "Chart 2 draws no projection line when the 7-day rate is zero" python3 -c '
import sys; sys.path.insert(0, sys.argv[1]); import status_html as S
now = 1790000000
series = {"measured": [[now - 86400, 100]], "playable": [[now - 86400, 20]]}
curve = [{"release": "0.6", "measured": 300, "playable": 110}, {"release": "1.0", "measured": 876, "playable": 789}]
fc = {"measured": {"rate7": 0.0}, "playable": {"rate7": 0.0}}
svg = S._chart2(series, now, curve, fc)
sys.exit(0 if "stroke-dasharray:4 3" not in svg else 1)' "$HERE"

# No "Benchmarked" and no C I S B column anywhere _chart1/_chart2 can emit one.
check "neither chart function can emit 'Benchmarked' or a C I S B header" python3 -c '
import sys; sys.path.insert(0, sys.argv[1]); import status_html as S
sys.exit(0 if "Benchmarked" not in "".join(l for l, _, _, _ in S._SERIES) and len(S._SERIES) == 2 else 1)' "$HERE"
