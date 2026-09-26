# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $A/$B (the live refs), $GOLDENS, the shims on PATH, ok/bad/check. Not
# executable, no shebang, no exit.
#
# Release priority (#432): a request queued with HAKUX_RELEASE_PRIO=1 is named
# `1-<epoch>-...` and the dispatcher, which serves queue/*.req in glob order,
# serves it after every 0-* probe and 0-0-x-* promoted head and ahead of every
# plain <epoch>-... request and every z-* sweep. arms.sh sets the variable when
# the prediction's issue carries the release label, and a failed label read
# queues at normal priority rather than refusing.
#
# Its own work and dispatch dirs, so the shared queue 10..50 drive is neither
# read nor left changed.

echo "== release priority: 1-<epoch> ids sort after probes, ahead of plain requests"

RP="$T/relprio"
rm -rf "$RP"; mkdir -p "$RP/d/queue" "$RP/bin"

# -- request.sh names 1-... only with the variable set -----------------------
rp_name() {   # <HAKUX_RELEASE_PRIO value> -> the id request.sh printed
    HAKUX_RELEASE_PRIO="$1" DISPATCH_DIR="$RP/d" DISPATCH_TREE="$REPO" \
        bash "$TESTING/request.sh" --who relprio --suites "Blend surface" --ref "$B" \
        --no-expect "selftest: naming only" --purpose "selftest release priority" 2>/dev/null \
        | sed -n 's/^queued //p'
}
rp_plain=$(rp_name "")
sleep 1                                   # a later epoch: arrival order alone would put it last
rp_prio=$(rp_name 1)
echo "  request.sh named: plain=$rp_plain prio=$rp_prio"
check "request.sh without HAKUX_RELEASE_PRIO names <epoch>-relprio-<pid>" \
    python3 -c "import re,sys; sys.exit(0 if re.fullmatch(r'[0-9]{10}-relprio-[0-9]+', sys.argv[1]) else 1)" "$rp_plain"
check "request.sh with HAKUX_RELEASE_PRIO=1 names 1-<epoch>-relprio-<pid>" \
    python3 -c "import re,sys; sys.exit(0 if re.fullmatch(r'1-[0-9]{10}-relprio-[0-9]+', sys.argv[1]) else 1)" "$rp_prio"

# -- the dispatcher's glob order, under both collations it can run in --------
# The literal ladder from pri432.md, plus the two ids request.sh just wrote.
for n in 0-0-x-9 0-probe 1-1759000500-b 1759000000-a z-sweep-x; do echo '{}' > "$RP/d/queue/$n.req"; done
rp_want="0-0-x-9 0-probe $rp_prio 1-1759000500-b 1759000000-a $rp_plain z-sweep-x"
for loc in C C.UTF-8; do
    # bash globs exactly as dispatcher.sh's `queue/*.req` does
    got=$(cd "$RP/d/queue" && LC_ALL=$loc bash -c 'for f in *.req; do printf "%s " "${f%.req}"; done')
    python3 - "$got" "$rp_want" "$loc" <<'PY' && ok "glob order under LC_ALL=$loc: $got" || bad "glob order under LC_ALL=$loc: $got"
import sys
got, want, loc = sys.argv[1].split(), sys.argv[2].split(), sys.argv[3]
# the ladder the brief names, checked by word so a wrong answer names itself
lad = ["0-0-x-9", "0-probe", "1-1759000500-b", "1759000000-a", "z-sweep-x"]
pos = [got.index(w) for w in lad]
assert pos == sorted(pos), "ladder out of order under %s: %s" % (loc, got)
assert got == want, "want %s, got %s" % (want, got)
# and python's own byte order agrees with the shell's
assert sorted(got) == got, "python byte order disagrees: %s" % sorted(got)
PY
done

# -- arms.sh passes the label through, and never refuses on a failed read ----
# A gh in front of the selftest shim: the one issue read arms.sh makes is
# answered by RP_GH (label | nolabel | fail); everything else is the shim's.
cat > "$RP/bin/gh" <<EOF
#!/usr/bin/env bash
if [ "\$1" = api ] && [[ "\$2" == repos/*/issues/[0-9]* ]] && [[ "\$*" == *".labels[].name"* ]]; then
    echo "relprio-read \$2" >> "$RP/gh.log"
    case "\${RP_GH:-nolabel}" in
        label)   printf 'bug\n0.5\n' ;;
        nolabel) printf 'bug\n0.5-candidate\n' ;;
        *)       echo "HTTP 502" >&2; exit 1 ;;
    esac
    exit 0
fi
exec "$T/bin/gh" "\$@"
EOF
chmod +x "$RP/bin/gh"
rp_arms() {   # <RP_GH mode> -> the queue's names, one per line
    rm -rf "$RP/work" "$RP/ad"; mkdir -p "$RP/work/arms" "$RP/work/logs/arms" "$RP/ad"/{queue,running,results,expect}
    date -u -d '1 minute ago' '+%FT%TZ' > "$RP/work/arms/since"
    python3 - "$RP/ad/expect/relprio.json" "$A" "$B" <<'PY'
import json, sys, datetime
p, a, b = sys.argv[1:]
json.dump({"registered_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "who": "lane.relprio", "issue": "7", "prediction": "release priority: the arms queue 1-",
           "a_ref": a, "b_ref": b,
           "expect": {"Blend_surface/TestA": 0}, "must_not_move": ["Color_mask_blend/*"],
           "must_not_regress": [], "expect_counts": {}}, open(p, "w"), indent=2)
PY
    ( export HAKUX_WORK="$RP/work" DISPATCH_DIR="$RP/ad" RP_GH="$1" PATH="$RP/bin:$PATH"
      unset HAKUX_RELEASE_PRIO
      bash "$HERE/arms.sh" ) >/dev/null 2>&1
    ( cd "$RP/ad/queue" && LC_ALL=C bash -c 'for f in *.req; do echo "${f%.req}"; done' )
}
: > "$RP/gh.log"
for mode in label nolabel fail; do
    names=$(rp_arms "$mode" | tr '\n' ' ')
    python3 - "$mode" "$names" <<'PY' && ok "arms.sh, issue read '$mode': $names" || bad "arms.sh, issue read '$mode': $names"
import re, sys
mode, names = sys.argv[1], sys.argv[2].split()
assert len(names) == 2, "want two arms, got %s" % names
assert all(re.fullmatch(r"(1-)?[0-9]{10}-arms-relprio-(base|fix)-[0-9]+", n) for n in names), names
prio = [n.startswith("1-") for n in names]
want = mode == "label"
assert prio == [want, want], "%s: want prio=%s on both arms, got %s" % (mode, want, names)
PY
done
check "arms.sh read the issue's labels once per prediction (3 ticks, 3 reads of #7)" \
    python3 -c "import sys; l=open(sys.argv[1]).read().split('\n'); sys.exit(0 if [x for x in l if x] == ['relprio-read repos/example/hakux/issues/7']*3 else 1)" "$RP/gh.log"
check "a failed label read is said in the tick log" grep -q "could not read #7's labels; queued at normal priority" "$RP/work/logs/arms/tick.log"
