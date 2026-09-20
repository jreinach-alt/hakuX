#!/usr/bin/env bash
# Allow-list tests, checked by mutation.
#
# Passing tests prove nothing on their own: a check that cannot fail is
# decoration. Each mutant below breaks one property of the allow-list, and the
# suite must go RED for every one. If a mutant survives, the corresponding
# check is not testing what it claims and the suite fails.
set -u
cd "$(dirname "$0")"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
CC=${CC:-cc}
fail=0

build_and_run() {   # $1 = header dir ; echoes PASS/FAIL
    if ! $CC -I "$1" -o "$TMP/t" test_window.c >/dev/null 2>&1; then
        echo "BUILD-FAIL"; return
    fi
    if "$TMP/t" >/dev/null 2>&1; then echo "PASS"; else echo "FAIL"; fi
}

echo "== generated header matches the device model =="
python3 gen_window.py --check || fail=1

echo "== baseline: the real allow-list must PASS =="
r=$(build_and_run probe)
echo "   baseline: $r"
[ "$r" = "PASS" ] || { echo "   baseline must pass"; fail=1; }

mutate() {  # $1 = name, $2 = sed program
    mkdir -p "$TMP/m"; cp probe/nv2a_window.h "$TMP/m/"
    sed -i "$2" "$TMP/m/nv2a_window.h"
    if cmp -s probe/nv2a_window.h "$TMP/m/nv2a_window.h"; then
        echo "   $1: MUTANT DID NOT APPLY (sed matched nothing)"; fail=1; return
    fi
    r=$(build_and_run "$TMP/m")
    if [ "$r" = "FAIL" ]; then
        echo "   $1: killed (suite went red, as required)"
    else
        echo "   $1: SURVIVED ($r) -- the suite does not actually test this"
        fail=1
    fi
    rm -rf "$TMP/m"
}

echo "== mutants: each must be killed =="
mutate "write-excluded blocks honoured (USER)" 's|if (!b->writable) continue;|;|'
mutate "alignment enforced"                    's|if (off & 3u) return false;.*|;|'
mutate "block end is exclusive"                's|off + 4u <= (uint32_t)(b->offset + b->size)|off <= (uint32_t)(b->offset + b->size)|'
mutate "BAR end is exclusive for reads"        's|return off + 4u > off \&\& off + 4u <= NV2A_MMIO_SIZE;|return off <= NV2A_MMIO_SIZE;|'
mutate "unmodelled space stays refused"        's|{ "USER",|{ "PRAMIN",   0x700000u, 0x100000u, true },\n    { "USER",|'
mutate "hazard list is consulted"              's|return nv2a_offset_writable(off) \&\& nv2a_hazard_name(off) == 0;|return nv2a_offset_writable(off);|'
mutate "hazard table is not empty"             's|^#define NV2A_NUM_HAZARDS .*|#define NV2A_NUM_HAZARDS 0|'

echo "== host suites =="
for suite in test_driver_loopback test_supervisor; do
    if python3 "host/$suite.py" >/dev/null 2>&1; then echo "   $suite: PASS"
    else echo "   $suite: FAIL"; fail=1; fi
done

echo "== supervisor mutants: each must be killed =="
pymutate() {  # $1 = name, $2 = sed program on a copy of supervisor.py
    cp host/supervisor.py "$TMP/supervisor.py.bak"
    sed -i "$2" host/supervisor.py
    if cmp -s "$TMP/supervisor.py.bak" host/supervisor.py; then
        echo "   $1: MUTANT DID NOT APPLY"; fail=1
        cp "$TMP/supervisor.py.bak" host/supervisor.py; return
    fi
    if python3 host/test_supervisor.py >/dev/null 2>&1; then
        echo "   $1: SURVIVED -- the suite does not test this"; fail=1
    else
        echo "   $1: killed (suite went red, as required)"
    fi
    cp "$TMP/supervisor.py.bak" host/supervisor.py
}
pymutate "bounce protection present"  's|if self.bounces >= self.max_bounces:|if False:|'
pymutate "wedge is reported"          's|elif now - self.unreachable_since > self.unreachable_alert_s:|elif False:|'
pymutate "a dark console is not mistaken for the dashboard" 's|return State.UNREACHABLE|return State.AT_DASHBOARD|'

echo
if [ "$fail" = 0 ]; then echo "allow-list suite OK (baseline green, every mutant killed)"; else echo "SUITE FAILED"; fi
exit $fail
