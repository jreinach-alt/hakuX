# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# hitch_report.py (#433): a frame-rate pass is not a smooth pass. These
# fixtures carry the counters VERBATIM from real captures (Sonic Heroes'
# single shader stall, Azurik's 5.4 s stall, Alien Hominid's unexplained
# hitch, Azurik's texture+shader "both" window) so the regexes and
# classifier are proven against what profile.c and physmem.c actually print,
# not a guessed format. Only the surrounding mark/soak-end timestamps and
# repeat counts are synthetic, to place a real hitch at a chosen offset or
# rate. static_window() itself needs PIL/numpy, which the CI runner does not
# have (see docs/lanes/hitchwatch/NOTES.md); its judging logic
# (static_window_fail) is pure Python and is what is tested here. The
# frame-reading half was validated by hand against real route-frames and is
# written up in NOTES.md, not re-proven in CI.

echo "== hitch_report: hitches() and report() on real-counter fixtures"
HF="$T/hitchfx"; rm -rf "$HF"; mkdir -p "$HF"

# make_logcat <file> <mark MM-DD HH:MM:SS.mmm> <end MM-DD HH:MM:SS.mmm> <extra lines...>
# One extra line per argument, written verbatim (they already have their own
# stamp -- real lines keep their real stamp; only mark/end are chosen here).
make_logcat() {
    local f="$1" mark="$2" end="$3"; shift 3
    { echo "$mark I/hakuX-route( 1): mark gameplay"
      for l in "$@"; do printf '%s\n' "$l"; done
      echo "$end I/hakuX-route( 1): soak end"
    } > "$f"
}

# Real line: Sonic Heroes, 1790902215-autoverdict-1078702/logcat.txt, the
# single captured stall (off=632.8s from that run's real mark). dsm=13,
# dpc_ms=996.0: classifies shader. 433.8 ms, once, is under both the owner's
# bars (500 ms, 6/min) -- this fixture must PASS the hitch check, same as
# the real run did (it fails on liveness instead; see 1078702 in NOTES.md).
SONIC_PACE='10-01 18:16:44.682 I/hakuX-pace( 5086): f=48420 v0=0 v1=56 v2=0 v3=0 v4=4 vb=129 max=433.8 ms=2151.1'
SONIC_SHD='10-01 18:16:44.682 I/hakuX-perf( 5086): [shd413] f=48420 dt_ms=2151 ph=13926404 pm=88 dph=19818 dpm=13 sh=7201146 sm=83 dsh=9230 dsm=13 vh=1480 vm=6 dvh=4 dvm=6 L=Y W=8 pc_ms=1024.6 dpc_ms=996.0 dpn=13 dfb=13 dfbh=0 dfb_ms=995.8 dvs_ms=219.9 dgs_ms=584.4 dfs_ms=37.7 dsru=7 dsrum=7 dsru_ms=499.2 dsnu=11 dsnum=11 dsnu_ms=342.6 dgl_ms=132.1 dsmod_ms=145.4 dsv_ms=220.5 kd=4/10/10/6/0/1/0/0/0 dins_us=28.1'
make_logcat "$HF/shader_mild_pass.logcat" "10-01 18:06:11.913" "10-01 18:16:50.000" "$SONIC_PACE" "$SONIC_SHD"

# Real line: Azurik, 1-1790725091-lane.verdict433-1456876/logcat.txt, its
# worst window (5463.0 ms; dsm=61, dpc_ms=7071.3: shader). Placed at off
# ~138 s (past the 60 s warmup) -- this run was rated Playable, so this
# fixture is the hitch check finding something new, not re-deriving a known
# fail (see NOTES.md: it is one of four such titles the survey found).
AZURIK_BIG_PACE='09-29 21:49:18.425 I/hakuX-pace(25956): f=41400 v0=1 v1=8 v2=34 v3=7 v4=10 vb=552 max=5463.0 ms=9609.7'
AZURIK_BIG_SHD='09-29 21:49:18.425 I/hakuX-perf(25956): [shd413] f=41400 dt_ms=9609 ph=3135831 pm=159 dph=10125 dpm=70 sh=630334 sm=131 dsh=6372 dsm=61 vh=126 vm=125 dvh=3 dvm=59 L=Y W=7 pc_ms=14438.0 dpc_ms=7071.3 dpn=70 dfb=70 dfbh=0 dfb_ms=7070.1 dvs_ms=1188.9 dgs_ms=4626.1 dfs_ms=299.5 dsru=96 dsrum=96 dsru_ms=4964.8 dsnu=60 dsnum=60 dsnu_ms=1149.7 dgl_ms=318.9 dsmod_ms=371.0 dsv_ms=0.0 kd=64/31/61/54/1/24/3/0/3 dins_us=228.0'
make_logcat "$HF/big_stall_fail.logcat" "09-29 21:47:00.000" "09-29 21:49:25.000" "$AZURIK_BIG_PACE" "$AZURIK_BIG_SHD"

# Real line: Alien Hominid, 1-1790515369-lanelocal-1183547/logcat.txt, f=71400
# (165.5 ms). No [shd413]/[rdc] line shares its tick in the real capture
# either -- the classifier must say UNEXPLAINED, not guess shader because
# dsm defaults to 0 looks like "no misses" rather than "no data".
ALIEN_PACE='09-27 06:43:02.705 I/hakuX-pace(28170): f=71400 v0=0 v1=49 v2=2 v3=5 v4=4 vb=98 max=165.5 ms=1619.4'
make_logcat "$HF/unexplained_single.logcat" "09-27 06:40:00.000" "09-27 06:43:10.000" "$ALIEN_PACE"

# The same real unexplained line, repeated at a rate past the owner's bar
# (8 in a 70 s scored window, all past the 60 s warmup = 6.86/min > 6/min),
# each kept byte-real; only the stamp moves, to 8 distinct seconds past mark.
make_logcat "$HF/rate_fail.logcat" "09-27 06:40:00.000" "09-27 06:42:10.000" \
    '09-27 06:41:08.705 I/hakuX-pace(28170): f=71400 v0=0 v1=49 v2=2 v3=5 v4=4 vb=98 max=165.5 ms=1619.4' \
    '09-27 06:41:16.705 I/hakuX-pace(28170): f=71400 v0=0 v1=49 v2=2 v3=5 v4=4 vb=98 max=165.5 ms=1619.4' \
    '09-27 06:41:24.705 I/hakuX-pace(28170): f=71400 v0=0 v1=49 v2=2 v3=5 v4=4 vb=98 max=165.5 ms=1619.4' \
    '09-27 06:41:32.705 I/hakuX-pace(28170): f=71400 v0=0 v1=49 v2=2 v3=5 v4=4 vb=98 max=165.5 ms=1619.4' \
    '09-27 06:41:40.705 I/hakuX-pace(28170): f=71400 v0=0 v1=49 v2=2 v3=5 v4=4 vb=98 max=165.5 ms=1619.4' \
    '09-27 06:41:48.705 I/hakuX-pace(28170): f=71400 v0=0 v1=49 v2=2 v3=5 v4=4 vb=98 max=165.5 ms=1619.4' \
    '09-27 06:41:56.705 I/hakuX-pace(28170): f=71400 v0=0 v1=49 v2=2 v3=5 v4=4 vb=98 max=165.5 ms=1619.4' \
    '09-27 06:42:04.705 I/hakuX-pace(28170): f=71400 v0=0 v1=49 v2=2 v3=5 v4=4 vb=98 max=165.5 ms=1619.4'

# Real line: Azurik's window classified BOTH (dsm=2>0 shader, tex=20797 us
# over the texture bar). Single occurrence, well under both fail bars --
# this fixture is for classify(), not hitch_fail().
AZURIK_BOTH_PACE='09-29 21:49:42.163 I/hakuX-pace(25956): f=41880 v0=0 v1=1 v2=51 v3=2 v4=6 vb=148 max=319.1 ms=2464.1'
AZURIK_BOTH_SHD='09-29 21:49:42.163 I/hakuX-perf(25956): [shd413] f=41880 dt_ms=2464 ph=3201561 pm=206 dph=6007 dpm=2 sh=665489 sm=175 dsh=3342 dsm=2 vh=126 vm=164 dvh=0 dvm=2 L=Y W=8 pc_ms=20422.4 dpc_ms=276.4 dpn=2 dfb=2 dfbh=0 dfb_ms=276.4 dvs_ms=42.5 dgs_ms=185.9 dfs_ms=11.8 dsru=4 dsrum=4 dsru_ms=197.7 dsnu=2 dsnum=2 dsnu_ms=42.5 dgl_ms=11.5 dsmod_ms=13.8 dsv_ms=0.0 kd=2/1/2/2/0/0/0/0/0 dins_us=8.0'
# Real [rdc] line content, verbatim; its real stamp (21:49:42.179) trails the
# pace line by 16 ms (the probe's own async clock), just outside the hitch's
# own [t - window_ms, t] span that find_hitches sums tex-us over -- moved
# here to 21:49:41.500 (inside the span) so this one-line fixture reproduces
# the real multi-line window's BOTH verdict without needing every rdc tick.
AZURIK_BOTH_RDC='09-29 21:49:41.500 I/hakuX-perf(25956): [rdc] f=60 dt=2469 tid=26010 tcpu=1114.1 rdo=8344 rdous=39671 vtx=3713/18873/19333/1802 nv2a=0/0/0/0 tex=4631/20797/108107/2305 vga=0/0/0/0 code=0/0/0/0 mig=0/0/0/0 snap=0/0/0/0 oth=0/0/0/0 v=2397 dra=-1076652 dx=0 vr=0 tm=0 ovh=17344/130 tk=41'
make_logcat "$HF/both_class.logcat" "09-29 21:47:00.000" "09-29 21:49:45.000" "$AZURIK_BOTH_PACE" "$AZURIK_BOTH_SHD" "$AZURIK_BOTH_RDC"

eval_fixture() {   # <logcat file> -> "n n_after_warmup per_min worst_ms cls_shader cls_texture cls_both cls_unexplained hitch_fail"
    python3 -c '
import sys
sys.path.insert(0, sys.argv[2])
import title_verdict as tv
import hitch_report as hr
lc, _g, _o = tv.parse_logcat(sys.argv[1])
marks = [(t, msg[5:].strip()) for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.startswith("mark ")]
mark_t = [t for t, lab in marks if lab == "gameplay"][0]
ends = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "soak end"]
end_t = ends[-1]
hs = hr.find_hitches(lc, mark_t, end_t)
rep = hr.report(hs, end_t - mark_t)
fail, why = hr.hitch_fail(rep)
cls = rep["classification"]
print(rep["n"], rep["n_after_warmup"], rep["per_min_after_warmup"], rep["worst_ms"],
      cls["shader"], cls["texture"], cls["both"], cls["unexplained"], fail, why)
' "$1" "$TESTING"
}

case "$(eval_fixture "$HF/shader_mild_pass.logcat")" in
    "1 1 0.104 433.8 1 0 0 0 False None") ok "Sonic Heroes' real single stall: 1 shader hitch, passes the hitch bars" ;;
    *) bad "shader_mild_pass: $(eval_fixture "$HF/shader_mild_pass.logcat")" ;;
esac
case "$(eval_fixture "$HF/big_stall_fail.logcat")" in
    "1 1 0.706 5463.0 1 0 0 0 True"*"5463 ms stall"*) ok "Azurik's real 5.4 s stall fails as a big hitch" ;;
    *) bad "big_stall_fail: $(eval_fixture "$HF/big_stall_fail.logcat")" ;;
esac
case "$(eval_fixture "$HF/unexplained_single.logcat")" in
    "1 1"*" 0 0 0 1 False None") ok "Alien Hominid's real hitch with no shd413/rdc line classifies unexplained, not shader" ;;
    *) bad "unexplained_single: $(eval_fixture "$HF/unexplained_single.logcat")" ;;
esac
case "$(eval_fixture "$HF/rate_fail.logcat")" in
    "8 8"*"True"*"/min after the first 60 s"*) ok "8 real unexplained hitches in a 70 s window fails on rate, not magnitude" ;;
    *) bad "rate_fail: $(eval_fixture "$HF/rate_fail.logcat")" ;;
esac
case "$(eval_fixture "$HF/both_class.logcat")" in
    "1 1 0.571"*" 0 0 1 0 False None") ok "Azurik's real shader+texture window classifies both" ;;
    *) bad "both_class: $(eval_fixture "$HF/both_class.logcat")" ;;
esac

echo "== hitch_report: hitch_fail() and static_window_fail() boundary logic"
check "hitch_fail ignores an allowed title even past both bars" \
    python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import hitch_report as hr
rep = dict(per_min_after_warmup=99.0, n_big_after_warmup=3, worst5=[dict(off_s=100, max_ms=9000)])
fail, why = hr.hitch_fail(rep, allowance=True)
assert fail is False and why is None, (fail, why)' "$TESTING"
check "hitch_fail per-minute bar is exclusive (6.0 itself does not fail)" \
    python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import hitch_report as hr
rep = dict(per_min_after_warmup=6.0, n_big_after_warmup=0, worst5=[])
assert hr.hitch_fail(rep)[0] is False' "$TESTING"
check "hitch_fail per-minute bar trips just past 6.0" \
    python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import hitch_report as hr
rep = dict(per_min_after_warmup=6.01, n_big_after_warmup=0, worst5=[])
assert hr.hitch_fail(rep)[0] is True' "$TESTING"
check "static_window_fail never fails an unmeasured window" \
    python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import hitch_report as hr
assert hr.static_window_fail(dict(measured=False, frozen_frac=None, n=0)) == (False, None)' "$TESTING"
check "static_window_fail trips at the frozen-fraction bar" \
    python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import hitch_report as hr
assert hr.static_window_fail(dict(measured=True, frozen_frac=hr.FROZEN_FRAC_BAR, n=10))[0] is True
assert hr.static_window_fail(dict(measured=True, frozen_frac=0.03, n=10))[0] is False' "$TESTING"

echo "== hitch_report: mutants"
# A mutant is written to $T/hr_mutant.py (a distinct module name) so the real
# hitch_report.py is never touched and no import cache can hide a failure.
hr_mutant() {   # <name> <fixture file> <want: True|False (new hitch_fail)> <python: old> <python: new>
    local name="$1" fx="$2" want="$3" old="$4" new="$5"
    python3 - "$TESTING/hitch_report.py" "$T/hr_mutant.py" "$old" "$new" <<'PY'
import sys
src, dst, old, new = sys.argv[1:5]
s = open(src).read()
if s.count(old) != 1:
    sys.exit("anchor not found once: %r" % old)
open(dst, "w").write(s.replace(old, new))
PY
    if [ $? != 0 ]; then bad "mutant '$name': its anchor is gone from hitch_report.py -- update the mutant"; return; fi
    out=$(python3 -c '
import sys
sys.path.insert(0, sys.argv[2])
sys.path.insert(0, sys.argv[3])
import title_verdict as tv
import hr_mutant as hr
lc, _g, _o = tv.parse_logcat(sys.argv[1])
marks = [(t, msg[5:].strip()) for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.startswith("mark ")]
mark_t = [t for t, lab in marks if lab == "gameplay"][0]
ends = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "soak end"]
end_t = ends[-1]
hs = hr.find_hitches(lc, mark_t, end_t)
rep = hr.report(hs, end_t - mark_t)
print(hr.hitch_fail(rep)[0])
' "$fx" "$TESTING" "$T")
    rm -f "$T/hr_mutant.py"
    case "$out" in
        "$want") ok "mutant caught by '$fx': $name" ;;
        *) bad "mutant SURVIVED '$fx' (got $out, want $want): $name" ;;
    esac
}
hr_mutant "ignore the big-stall bar" "$HF/big_stall_fail.logcat" "False" \
    'if rep["n_big_after_warmup"] > 0:' 'if False:'
hr_mutant "ignore the per-minute bar" "$HF/rate_fail.logcat" "False" \
    'if rep["per_min_after_warmup"] is not None and rep["per_min_after_warmup"] > HITCHES_PER_MIN_BAR:' \
    'if False:'
rm -rf "$HF"
unset HF SONIC_PACE SONIC_SHD AZURIK_BIG_PACE AZURIK_BIG_SHD ALIEN_PACE rate_lines t n \
      AZURIK_BOTH_PACE AZURIK_BOTH_SHD AZURIK_BOTH_RDC
