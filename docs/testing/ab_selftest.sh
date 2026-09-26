#!/usr/bin/env bash
#
# Exit-code self-test for ab_compare.py, against real dispatch results.
#
#   ab_selftest.sh
#
# Every case below is a result directory that the dispatcher actually produced
# on 2026-09-12, not a synthetic fixture. That is the point: the comparison
# tool's job is to get the real incidents right, and a hand-built TSV proves
# only that the parser parses.
#
# The exit codes under test are ab_compare.py's contract:
#   0  pass, or nothing got worse
#   1  fail: a registered prediction was violated, or a capture regressed with
#      no prediction on file
#   2  refused: the arms are not comparable
#
# Two cases need a moment's explanation, because they look like the tool being
# wrong and are not:
#
#   * "two refs, byte-identical scores" expects 0. Refs f4e029b1d3 and
#     0bb035d89e are different commits and different APKs, and every one of
#     the 137 blend captures scores the same in both. The commits between them
#     were inert for that disc. This doubles as evidence that the device is
#     bit-reproducible on this suite across two separate boots.
#
#   * The noise-floor case needs --allow-same-binary and expects 0. It
#     compares the real ten-run Texture border measurement against itself,
#     sliced into two five-run halves by ab_selftest_slice.py. One binary, so
#     any delta is device noise by construction -- and the one capture that
#     moves (2D_BorderTex_SZ, 0 -> 1,847) is inside its measured band of
#     5,640 and must therefore be classed noise rather than a regression. An
#     early draft returned 1 here, counting the flicker across zero as
#     "regressed from exact".
#
# It needs no device. It needs the dispatch results still to be on disk; if
# they have been pruned it says which directory is missing and skips.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}/results"
WORK="${TMPDIR:-/tmp}/ab_selftest.$$"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

fails=0; skips=0; n=0
run() {
    local want="$1" label="$2"; shift 2
    n=$((n+1))
    # A missing fixture is a skip, not a failure: the results directory is
    # working space and gets pruned.
    local a
    for a in "$@"; do
        case "$a" in
            "$R"/*) [ -d "$a" ] || { echo "  skip       $label (no $a)"
                                     skips=$((skips+1)); return 0;};;
        esac
    done
    python3 "$HERE/ab_compare.py" "$@" >/dev/null 2>&1
    local got=$?
    if [ "$got" = "$want" ]; then
        echo "  ok   $got     $label"
    else
        echo "  FAIL want $want got $got  $label"
        fails=$((fails+1))
    fi
}

# The prose prediction that 1789253269-blend48b-fix recorded in its --purpose,
# registered here as a machine-checkable file. It must FAIL: its two
# per-capture values are exactly right, but its aggregate counts were computed
# against eb536abd50, the original #48 base, where the arm's baseline was
# 0bb035d89e with the first fix already in it.
EXP="$WORK/exp48b.json"
python3 "$HERE/ab_compare.py" --register "$EXP" --who blend48b --issue 48 \
    --a-ref 0bb035d89e --b-ref c6dd6fcdfb \
    --prediction "10 better / 0 worse / 127 same, exact 4 -> 7; DstAlpha_ARGB8 -> 0 and ARGB8_Add_SrcA_DstA -> 47,272" \
    --expect-value 'Blend_surface/DstAlpha_ARGB8=0' \
    --expect-value 'Blend_surface/ARGB8_Add_SrcA_DstA=47272' \
    --expect-count better=10 --expect-count worse=0 --expect-count same=127 \
    --must-not-move 'Blend_tests/*' >/dev/null || exit 2

python3 "$HERE/ab_selftest_slice.py" "$WORK/noise" >/dev/null || {
    echo "could not slice the ten-run fixture; noise cases skipped" >&2; }

echo "ab_compare.py against real dispatch results:"
run 1 "blend48: regression hidden inside a -271,760 px win" \
    --a "$R/1789251491-blend48-base-2869036" --b "$R/1789251814-blend48-fix2-2962762"
run 0 "blend48b: 2 better / 0 worse, no prediction -> unjudged" \
    --a "$R/1789253269-blend48b-base-3472491" --b "$R/1789253269-blend48b-fix-3472499"
run 1 "blend48b against its own prose prediction (wrong baseline, post-hoc)" \
    --a "$R/1789253269-blend48b-base-3472491" --b "$R/1789253269-blend48b-fix-3472499" \
    --expect "$EXP"
run 0 "fog42: 12 better / 0 worse, Alpha_func control unmoved" \
    --a "$R/1789252660-fog42-base-3275029" --b "$R/1789252660-fog42-fix-3275102"
run 1 "image blit: FBToZetaAsTex 14,383 -> 34,382 inside a -264,629 px win" \
    --a "$R/1789241036-orchestrator-2458180" --b "$R/1789241036-orchestrator-2458184"
run 0 "image blit: the following arm repairs it to 14,383 exactly" \
    --a "$R/1789241036-orchestrator-2458184" --b "$R/1789242846-orchestrator-2836113"
run 0 "two refs, byte-identical scores on all 137 captures" \
    --a "$R/1789251814-blend48-fix2-2962762" --b "$R/1789253269-blend48b-base-3472491"
run 2 "REFUSE: progress_log_proof false (704 captures against 1042)" \
    --a "$R/1789240604b-depth-baseline" --b "$R/1789238988-depth-agent-2367751"
run 2 "REFUSE: disc_id differs (blend disc against fog disc)" \
    --a "$R/1789251491-blend48-base-2869036" --b "$R/1789252660-fog42-fix-3275102"
run 2 "REFUSE: one binary in both arms" \
    --a "$R/1789253269-blend48b-fix-3472499" --b "$R/1789253269-blend48b-fix-3472499"
run 2 "REFUSE: a soak arm has no scored runs to compare" \
    --a "$R/1789250118-audio-armA-2154072" --b "$R/1789250119-audio-armB-2154167"
run 0 "noise floor: one binary, 5 runs against 5, flake neutralised" \
    --a "$WORK/noise/armA" --b "$WORK/noise/armB" --allow-same-binary
run 0 "probe: the flaky capture's band is 5,640 over ten runs" \
    --probe "$R/1789255594-exp54-stst-correct-3660183" \
    --capture Texture_border/2D_BorderTex_SZ
run 2 "REFUSE probe: the capture is absent from that arm" \
    --probe "$R/1789253269-blend48b-fix-3472499" \
    --capture Fog_carryover/CarryoverTris

echo
if [ "$fails" = 0 ]; then
    if [ "$skips" -gt 0 ]; then
        echo "all $n cases pass, $skips skipped for missing fixtures"
    else
        echo "all $n cases pass"
    fi
else
    echo "$fails of $n cases FAILED"
fi
exit "$fails"
