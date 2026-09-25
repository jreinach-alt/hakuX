#!/usr/bin/env bash
# Allow-list, config-parser and supervisor tests, checked by mutation.
#
# Passing tests prove nothing on their own: a check that cannot fail is
# decoration. Each mutant below breaks one property, and the suite must go RED
# for every one. If a mutant survives, the corresponding check is not testing
# what it claims and the suite fails.
#
# WHAT IS AND IS NOT COVERED HERE. probe/main.c needs nxdk and an Xbox, so
# nothing on this side compiles it. Every decision it makes that can be tested
# therefore lives in a header it includes -- nv2a_window.h (generated, the
# write allow-list and the hazard list) and probe_cfg.h (the config parser) --
# and those are what this suite builds and mutates. main.c itself is left with
# the socket loop and the MMIO store. When you add a decision to main.c, move
# it into a header first, or it is untested by construction.
set -u
cd "$(dirname "$0")"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
CC=${CC:-cc}
fail=0

build_and_run() {   # $1 = header dir ; $2 = test source ; $3 = extra cflags
    if ! $CC -I "$1" $3 -o "$TMP/t" "$2" >/dev/null 2>&1; then
        echo "BUILD-FAIL"; return
    fi
    if "$TMP/t" >/dev/null 2>&1; then echo "PASS"; else echo "FAIL"; fi
}

echo "== generated header matches the device model =="
python3 gen_window.py --check || fail=1

echo "== baselines: every real configuration must PASS =="
for spec in "test_window.c::allow-list (safe build)" \
            "test_window.c:-DPROBE_ALLOW_HAZARDS:allow-list (hazards build)" \
            "test_probe_cfg.c::config parser"; do
    src=${spec%%:*}; rest=${spec#*:}; cf=${rest%%:*}; name=${rest#*:}
    r=$(build_and_run probe "$src" "$cf")
    echo "   baseline $name: $r"
    [ "$r" = "PASS" ] || { echo "   baseline must pass"; fail=1; }
done

mutate() {  # $1 = name, $2 = sed program, $3 = header to break,
            # $4 = test source, $5 = extra cflags
    mkdir -p "$TMP/m"
    cp probe/nv2a_window.h probe/probe_cfg.h "$TMP/m/"
    sed -i "$2" "$TMP/m/$3"
    if cmp -s "probe/$3" "$TMP/m/$3"; then
        echo "   $1: MUTANT DID NOT APPLY (sed matched nothing)"; fail=1
        rm -rf "$TMP/m"; return
    fi
    r=$(build_and_run "$TMP/m" "$4" "$5")
    if [ "$r" = "FAIL" ]; then
        echo "   $1: killed (suite went red, as required)"
    else
        echo "   $1: SURVIVED ($r) -- the suite does not actually test this"
        fail=1
    fi
    rm -rf "$TMP/m"
}

win() { mutate "$1" "$2" nv2a_window.h test_window.c "${3:-}"; }
cfg() { mutate "$1" "$2" probe_cfg.h    test_probe_cfg.c ""; }

echo "== allow-list mutants: each must be killed =="
win "write-excluded blocks honoured (USER)" 's|if (!b->writable) continue;|;|'
win "alignment enforced"                    's|if (off & 3u) return false;.*|;|'
win "block end is exclusive"                's|off + 4u <= (uint32_t)(b->offset + b->size)|off <= (uint32_t)(b->offset + b->size)|'
win "BAR end is exclusive for reads"        's|return off + 4u > off \&\& off + 4u <= NV2A_MMIO_SIZE;|return off <= NV2A_MMIO_SIZE;|'
win "unmodelled space stays refused"        's|{ "USER",|{ "PRAMIN",   0x700000u, 0x100000u, true },\n    { "USER",|'
win "hazard list is consulted"              's|return nv2a_offset_writable(off) \&\& nv2a_hazard_name(off) == 0;|return nv2a_offset_writable(off);|'
win "hazard table is not empty"             's|^#define NV2A_NUM_HAZARDS .*|#define NV2A_NUM_HAZARDS 0|'

# The emulator-only build. These run WITH -DPROBE_ALLOW_HAZARDS, because the
# lines they break are not compiled without it -- a mutant applied to code the
# configuration under test does not build is killed by nothing.
echo "== hazard-build mutants (the relaxation must relax ONE thing) =="
win "the hazard build still honours the window" \
    's|^    return nv2a_offset_writable(off);$|    return true;|' -DPROBE_ALLOW_HAZARDS
win "the hazard build really does allow hazards" \
    's|^    return nv2a_offset_writable(off);$|    return nv2a_offset_writable(off) \&\& nv2a_hazard_name(off) == 0;|' -DPROBE_ALLOW_HAZARDS

echo "== config-parser mutants: each must be killed =="
cfg "a boolean is not just its first character" \
    's|^static inline bool probe_cfg__bool(const char \*v, bool \*out)$|static inline bool probe_cfg__bool(const char *v, bool *out) { *out = (v[0] == (char)49); return true; }\nstatic inline bool probe_cfg__bool_unused(const char *v, bool *out)|'
cfg "a bad boolean is reported, not swallowed" \
    's|else probe_cfg__reject(c, key, "not a boolean");|else { }|'
cfg "port is validated as a port" \
    's|^static inline bool probe_cfg__port(const char \*v, int \*out)$|static inline bool probe_cfg__port(const char *v, int *out) { *out = atoi(v); return true; }\nstatic inline bool probe_cfg__port_unused(const char *v, int *out)|'
cfg "an over-long value is refused, not truncated" \
    's|if (strlen(val) >= cap) { probe_cfg__reject(c, key, "value too long"); return; }|if (strlen(val) >= cap) { memcpy(dst, val, cap - 1); dst[cap - 1] = 0; c->applied++; return; }|'
cfg "a split line is refused whole" \
    's|\&\& !feof(f)) {|\&\& 0) {|'
cfg "an unknown key is reported" \
    's|probe_cfg__reject(c, key, "unknown key");|;|'
cfg "whitespace around a key is trimmed" \
    's|^    key = probe_cfg__trim(key);$|;|'
cfg "a line with no .=. is reported" \
    's|{ probe_cfg__reject(c, key, "no .=. in the line"); return; }|{ return; }|'

echo "== host suites =="
for suite in test_driver_loopback test_supervisor test_canary; do
    if python3 "host/$suite.py" >/dev/null 2>&1; then echo "   $suite: PASS"
    else echo "   $suite: FAIL"; fail=1; fi
done

echo "== supervisor mutants: each must be killed =="
pymutate() {  # $1 = name, $2 = sed program, $3 = file under host/ (default supervisor.py)
    f=${3:-supervisor.py}
    cp "host/$f" "$TMP/$f.bak"
    sed -i "$2" "host/$f"
    if cmp -s "$TMP/$f.bak" "host/$f"; then
        echo "   $1: MUTANT DID NOT APPLY"; fail=1
        cp "$TMP/$f.bak" "host/$f"; return
    fi
    if python3 host/test_supervisor.py >/dev/null 2>&1; then
        echo "   $1: SURVIVED -- the suite does not test this"; fail=1
    else
        echo "   $1: killed (suite went red, as required)"
    fi
    cp "$TMP/$f.bak" "host/$f"
}
pymutate "bounce protection present"  's|if self.bounces >= self.max_bounces:|if False:|'
pymutate "wedge is reported"          's|elif now - self.unreachable_since > self.unreachable_alert_s:|elif False:|'
pymutate "a dark console is not mistaken for the dashboard" 's|return State.UNREACHABLE|return State.AT_DASHBOARD|'
# The retracted claim, put back. This one keeps the AutoTurnOff sentence and
# the power button, so the only check that can kill it is the absence check --
# which is the point: without that check the suite is green with the false
# diagnosis restored.
pymutate "the retracted diagnosis stays retracted" \
    's|"identical from here and both need the power button, so "|"identical from here and both need the power button. No ICMP "\n                    "means the processor is gone, and nothing recovers that. "|'

echo "== driver mutants: each must be killed =="
pydrivermutate() {  # $1 = name, $2 = sed program on probe_driver.py
    cp host/probe_driver.py "$TMP/probe_driver.py.bak"
    sed -i "$2" host/probe_driver.py
    if cmp -s "$TMP/probe_driver.py.bak" host/probe_driver.py; then
        echo "   $1: MUTANT DID NOT APPLY"; fail=1
        cp "$TMP/probe_driver.py.bak" host/probe_driver.py; return
    fi
    if python3 host/test_driver_loopback.py >/dev/null 2>&1; then
        echo "   $1: SURVIVED -- the suite does not test this"; fail=1
    else
        echo "   $1: killed (suite went red, as required)"
    fi
    cp "$TMP/probe_driver.py.bak" host/probe_driver.py
}
pydrivermutate "the HELLO's hazard marker is read" \
    's|self.hazards_allowed = self.HAZARD_MARK in self.hello|self.hazards_allowed = False|'
pydrivermutate "the hazard-allowed session is refused by default" \
    's|if self.hazards_allowed and not allow_hazards:|if False:|'

echo
if [ "$fail" = 0 ]; then echo "probe suite OK (baselines green, every mutant killed)"; else echo "SUITE FAILED"; fi
exit $fail
