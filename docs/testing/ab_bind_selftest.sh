#!/usr/bin/env bash
#
# Self-test for the prediction binding: PRE-REGISTERED, TAMPERED, UNBOUND,
# POST-HOC.
#
# This is the check that decides whether a verdict means anything, so it is the
# last thing that should be taken on trust. It builds synthetic arms in a temp
# dir rather than using real results, because the states it has to distinguish
# differ only in a request.json field and a file's bytes.
set -u
cd "$(dirname "$0")/../.."
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
pass=0; fail=0
ok(){ if [ "$2" = "$3" ]; then pass=$((pass+1)); else
        fail=$((fail+1)); echo "FAIL: $1 -- wanted '$3', got '$2'"; fi; }

mkarm(){ # mkarm DIR REF PX [EXPECT_PATH EXPECT_SHA] [NO_EXPECT]
    local d="$T/$1"; mkdir -p "$d"; touch "$d/DONE"
    printf 'suite\ttest\tsolo\tstatus\tdiffering\tmax_rgb\tmax_a\tpixels\toff_by_one\tapk_sha\tdisc_id\tlabel\n' > "$d/s.tsv"
    printf 'S\tt1\tFalse\tok\t%s\t255\t0\t307200\t0\tapk%s\tdisc1\t%s\n' "$3" "$2" "$1" >> "$d/s.tsv"
    python3 - "$d" "$2" <<'PY'
import json,sys,os
d,ref=sys.argv[1],sys.argv[2]
json.dump({"ref":ref,"apk_sha":"apk"+ref,"disc_id":"disc1","classifier_rev":"c1",
           "captures_vs_goldens":{"S":{"scored":1,"goldens":1,"partial":False}},
           "runs":[{"tsv":"s.tsv","captures":1,"exact":0,"px":0,
                    "progress_log_proof":True}]}, open(os.path.join(d,"result.json"),"w"))
PY
    if [ -n "${4:-}" ]; then
        python3 - "$d" "$4" "${5:-}" <<'PY'
import json,sys,os
d,exp,sha=sys.argv[1],sys.argv[2],sys.argv[3]
json.dump({"expect":exp,"expect_sha":sha,"no_expect":"",
           "queued_utc":"2026-09-12T00:00:00Z"}, open(os.path.join(d,"request.json"),"w"))
PY
    elif [ -n "${6:-}" ]; then
        python3 - "$d" "$6" <<'PY'
import json,sys,os
d,why=sys.argv[1],sys.argv[2]
json.dump({"expect":"","expect_sha":"","no_expect":why,
           "queued_utc":"2026-09-12T00:00:00Z"}, open(os.path.join(d,"request.json"),"w"))
PY
    fi
}

EXP="$T/pred.json"
python3 - "$EXP" <<'PY'
import json,sys
json.dump({"registered_utc":"2026-09-12T00:00:00Z","who":"t","issue":"0",
           "prediction":"px goes to 0","a_ref":"aaaaaaaaaa","b_ref":"bbbbbbbbbb",
           "must_not_move":[],"expect":{"S/t1":0},"expect_counts":{}},
          open(sys.argv[1],"w"), indent=2)
PY
SHA=$(sha256sum "$EXP" | cut -d' ' -f1)

# The mtime comparison needs a real gap; synthetic arms are made moments
# before the assertion, so backdate the results when the test is about which
# came first.
age_arms(){ touch -d '2020-01-01' "$T/a/result.json" "$T/b/result.json"; }

run(){ python3 docs/testing/ab_compare.py --a "$T/a" --b "$T/b" --expect "$EXP" 2>&1; }
state(){ run | grep -oE 'PRE-REGISTERED|TAMPERED|UNBOUND|POST-HOC' | head -1; }
verdict(){ run | grep -oE 'VERDICT: [A-Z-]+' | head -1; }

# 1. bound, sha matches, prediction holds -> PRE-REGISTERED and PASS
rm -rf "$T/a" "$T/b"
mkarm a aaaaaaaaaa 5 ; mkarm b bbbbbbbbbb 0 "$EXP" "$SHA"
ok "bound+intact reports PRE-REGISTERED" "$(state)" "PRE-REGISTERED"
ok "bound+intact still judges"           "$(verdict)" "VERDICT: PASS"

# 2. bound, but the file was edited afterwards -> TAMPERED, and the verdict is
#    disclaimed even though the (rewritten) prediction now passes
python3 - "$EXP" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); d["prediction"]="px goes to 0, or thereabouts"
json.dump(d,open(sys.argv[1],"w"),indent=2)
PY
ok "bound+edited reports TAMPERED" "$(state)" "TAMPERED"

# 3. the sha is restored -> PRE-REGISTERED again (the check is on content, so
#    it is reversible; a hash that only ever ratchets would punish a revert)
python3 - "$EXP" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); d["prediction"]="px goes to 0"
json.dump(d,open(sys.argv[1],"w"),indent=2)
PY
ok "restored content reports PRE-REGISTERED" "$(state)" "PRE-REGISTERED"

# 4. no request.json at all, prediction older than the results -> UNBOUND,
#    not POST-HOC: it was not written to fit, but nothing proves it was the
#    prediction made
rm -rf "$T/a" "$T/b"
mkarm a aaaaaaaaaa 5 ; mkarm b bbbbbbbbbb 0
touch -d '2020-01-01' "$EXP"
ok "unbound+old reports UNBOUND" "$(state)" "UNBOUND"

# 5. prediction newer than the results -> POST-HOC
age_arms; touch "$EXP"
ok "unbound+new reports POST-HOC" "$(state)" "POST-HOC"

# 6. queued with --no-expect: POST-HOC, and it says so
rm -rf "$T/a" "$T/b"
mkarm a aaaaaaaaaa 5 ; mkarm b bbbbbbbbbb 0 "" "" "noise floor"
age_arms; touch "$EXP"
ok "no-expect reports POST-HOC"        "$(state)" "POST-HOC"
ok "no-expect names the reason"        "$(run | grep -c "no-expect 'noise floor'")" "1"

# 7. a bound sha that names a DIFFERENT file must not be honoured -- otherwise
#    binding arm B to prediction X would launder a verdict read from Y
rm -rf "$T/a" "$T/b"
mkarm a aaaaaaaaaa 5 ; mkarm b bbbbbbbbbb 0 "$T/other.json" "$SHA"
age_arms; touch "$EXP"
ok "sha bound to another filename is ignored" "$(state)" "POST-HOC"

# 8. request.sh refuses a suites request with neither flag
out=$(docs/testing/request.sh --who t --suites "S" --ref HEAD 2>&1 || true)
ok "request.sh refuses without a prediction" \
   "$(printf '%s' "$out" | grep -c 'refusing to queue')" "1"
out=$(docs/testing/request.sh --who t --suites "S" --ref HEAD --expect /nope 2>&1 || true)
ok "request.sh refuses a missing --expect" \
   "$(printf '%s' "$out" | grep -c 'does not exist')" "1"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
