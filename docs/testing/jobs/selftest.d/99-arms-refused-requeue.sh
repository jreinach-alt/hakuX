# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# $REPO, $GOLDENS, the shims on PATH, ok/bad/check. Not executable, no
# shebang, no exit.
#
# A REFUSED pair (ab_compare printed `REFUSED:` and no VERDICT) is re-queued
# once, like INCOMPLETE, and a second REFUSED is final (lane.armsrequeue).
#
# #583's fix arm (forzadecay414-fix-pixels2.json) hit its 1800 s timeout on
# both runs on 2026-09-29, and neither set progress_log_proof. ab_compare
# refused it ("Requeue the arm"), arms.sh took the refusal for a verdict,
# judged the sha forever and left both results clean in the RAN walk, so the
# prediction could not be queued again even by the ARM ERROR recovery.
#
# Builds its own work dir, dispatch dir and pairs under $T/refused and asks
# `arms.sh list` whether the prediction would queue, so no request.sh, no
# other fragment's leftovers, and nothing left behind.
#
# RF_ARMS names the arms.sh under test (default: this tree's). Pointing it at
# origin/master's copy is the falsification run; docs/lanes/armsrequeue/NOTES.md
# has its output.

echo "== arms.sh: a REFUSED (no-proof) pair is re-queued once, and a second REFUSED is final"

RF="$T/refused"; RW="$RF/work"; RD="$RF/dispatch"
RF_ARMS="${RF_ARMS:-$TESTING/jobs/arms.sh}"
rm -rf "$RF"; mkdir -p "$RW/arms"/{pairs,judged,log,expect} "$RW/logs/arms" "$RD"/{queue,running,results,expect}
date -u -d '1 minute ago' '+%FT%TZ' > "$RW/arms/since"   # fences every committed prediction
RFB=$(git -C "$REPO" rev-parse --short origin/master 2>/dev/null || git -C "$REPO" rev-parse --short HEAD)
RFA=$(git -C "$REPO" rev-parse --short "$RFB~1")
RFEXP="$RD/expect/forzadecay414-fix-pixels2.json"
python3 - "$RFEXP" "$RFA" "$RFB" <<'PY'
import json, sys, datetime
p, a, b = sys.argv[1:]
json.dump({"registered_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "who": "lane.forzadecay414", "issue": "414", "a_ref": a, "b_ref": b,
           "expect": {"Blend_surface/TestA": 0}}, open(p, "w"), indent=2)
PY
RSHA=$(sha256sum "$RFEXP" | cut -d' ' -f1)
mkdir -p "$GOLDENS/Blend_surface"; [ -f "$GOLDENS/Blend_surface/TestA.png" ] || : > "$GOLDENS/Blend_surface/TestA.png"
printf 'lane/forzadecay414\t583\n' > "$RW/arms/log/prs.tsv"

rfarm() {   # <id> <ref> <proof True|False>: a DONE oracle result for the prediction
    local d="$RD/results/$1"
    mkdir -p "$d"; : > "$d/DONE"
    printf 'suite\ttest\tsolo\tstatus\tdiffering\tmax_rgb\tmax_a\tpixels\toff_by_one\tapk_sha\tdisc_id\tlabel\n' > "$d/scores1.tsv"
    printf 'Blend_surface\tTestA\tTrue\tok\t10\t9\t0\t1000\t0\n' >> "$d/scores1.tsv"
    python3 - "$d" "$2" "$3" "$RFEXP" "$RSHA" <<'PY'
import json, sys
d, ref, proof, exp, sha = sys.argv[1:]
json.dump({"apk_sha": "ab" + ref, "disc_id": "1-suites:x:Blend surface", "ref": ref,
           "program": "pgraph", "device_label": "thor", "scorer_rev": "s", "classifier_rev": "c",
           "runs": [{"tsv": "scores1.tsv", "captures": 1, "progress_log_proof": proof == "True"}]},
          open(d + "/result.json", "w"))
json.dump({"expect": exp, "expect_sha": sha, "ref": ref}, open(d + "/request.json", "w"))
PY
}
rfpair() {  # <run>: a pair record for the prediction, its fix arm without proof (#583)
    rfarm "rf$1-a" "$RFA" True; rfarm "rf$1-b" "$RFB" False
    python3 - "$RW/arms/pairs/$RSHA.json" "$RSHA" "rf$1" "$RFEXP" "$RFA" "$RFB" <<'PY'
import json, sys
p, sha, ids, exp, a, b = sys.argv[1:]
json.dump({"sha": sha, "id_a": ids + "-a", "id_b": ids + "-b", "expect": exp,
           "source": "lane/forzadecay414:docs/testing/predictions/forzadecay414-fix-pixels2.json",
           "who": "lane.forzadecay414", "issue": "414", "a_ref": a, "b_ref": b,
           "suites": "Blend surface", "queued_utc": "2026-09-29T19:00:00Z"}, open(p, "w"), indent=2)
PY
}
rftick() {
    ( export HAKUX_WORK="$RW" DISPATCH_DIR="$RD" ARMS_MAX_PAIRS_PER_TICK=0
      bash "$RF_ARMS" ) >/dev/null 2>&1
}
rfwould() { ( export HAKUX_WORK="$RW" DISPATCH_DIR="$RD"; bash "$RF_ARMS" list 2>/dev/null ) | grep -c "^WOULD QUEUE $RSHA "; }

check "(R0) CONTROL: before any pair exists, the prediction would queue" [ "$(rfwould)" = 1 ]

# ------------------------------------------------------ the first REFUSED
rfpair 1
check "(R0) CONTROL: ab_compare refuses the fixture for progress_log_proof, with no VERDICT" \
    bash -c 'o=$(cd "$1" && DISPATCH_DIR="$2" python3 "$3/ab_compare.py" --a "$2/results/rf1-a" --b "$2/results/rf1-b" --expect "$4" 2>&1)
             grep -q "^REFUSED: .*progress_log_proof false" <<< "$o" && ! grep -q "^VERDICT:" <<< "$o"' \
    -- "$REPO" "$RD" "$TESTING" "$RFEXP"
: > "$SELFTEST_GH_LOG"; rftick
check "(R1a) the first REFUSED writes no judged marker" [ ! -f "$RW/arms/judged/$RSHA" ]
check "(R1b) both results are VOIDED" bash -c '[ -f "$1/rf1-a/VOIDED" ] && [ -f "$1/rf1-b/VOIDED" ]' -- "$RD/results"
check "(R1c) the pair record is gone" [ ! -f "$RW/arms/pairs/$RSHA.json" ]
check "(R1c) and the next tick would queue the prediction again" [ "$(rfwould)" = 1 ]
check "(R1) the once-only marker is written" [ -f "$RW/arms/refused/$RSHA" ]
check "(R1) the PR comment carries the refusal and says it is re-queued once" \
    bash -c 'grep -q "^\[job.arms\] REFUSED: .*progress_log_proof false" "$1" && grep -q "queued again on the next tick, once" "$1"' \
    -- "$RW/arms/pairs/$RSHA.comment.md"
check "(R1) it is posted" grep -q "583" "$SELFTEST_GH_LOG"
check "(R1) no label moves on it" bash -c '! grep -q "issues/583/labels" "$1"' -- "$SELFTEST_GH_LOG"

# ----------------------------------------------------- the second REFUSED
rfpair 2; rftick
check "(R2) a second REFUSED for the same sha is final: judged" [ -f "$RW/arms/judged/$RSHA" ]
check "(R2) and not queued a third time" [ "$(rfwould)" = 0 ]
check "(R2) its results are VOIDED too (the manual recovery can queue it)" \
    bash -c '[ -f "$1/rf2-a/VOIDED" ] && [ -f "$1/rf2-b/VOIDED" ]' -- "$RD/results"
check "(R2) the comment says it is final" grep -q "second REFUSED, so it is not queued again" "$RW/arms/pairs/$RSHA.comment.md"
check "(R2) the judged marker carries no PASS/FAIL a label could read" bash -c '! grep -q "PASS\|FAIL" "$1"' -- "$RW/arms/judged/$RSHA"
rm -f "$RW/arms/judged/$RSHA" "$RW/arms/pairs/$RSHA.json"
check "(R3) deleting judged/ and pairs/ (the documented recovery) queues it once more" [ "$(rfwould)" = 1 ]

rm -rf "$RF"
