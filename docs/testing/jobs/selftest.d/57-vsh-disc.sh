# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# nxdk_vsh_tests discs: refused at QUEUE TIME when they would hang.
#
# The program reads d:\vsh_tests.cnf and, when it is missing, ASSERTs and
# waits forever (debug_output.cpp PrintAssertAndWaitForever). The emulator
# stays up, so the worker sees a live guest and burns the whole run timeout
# with the device awake. A request.sh without the check QUEUES such a disc:
# a vsh base ISO passed as an ordinary --base-iso is built as a pgraph disc --
# nxdk_pgraph_tests_config.json, no cnf -- which is exactly that hang.
#
# THE FALSIFIER is the "vsh ISO queued as pgraph" leg below. Against the code
# before this change request.sh accepts it and a .req lands in the queue, so
# that leg goes red on the queue file existing, not on a missing flag or an
# import error. The other legs pin the rest of the rule: a rebooting build, an
# unknown suite, a stale serving snapshot, and the accepted case.
#
# FIXTURES ARE SYNTHESISED, not copied: CI has no Xbox images. A fixture xiso
# is a root directory table carrying a default.xbe whose bytes contain the
# strings make_test_iso.py identifies a program by -- the config path each
# program compiles in, and the reboot message only a non-shutdown build has.
# Depends on nothing from the other fragments; its dispatch dir is its own.

echo "== vsh: a disc that would hang is refused before it is queued"

VT="$T/vsh"; mkdir -p "$VT"
VD="$VT/dispatch"; mkdir -p "$VD/queue" "$VD/running" "$VD/results" "$VD/bin"
MKISO="$TESTING/make_test_iso.py"

python3 - "$TESTING" "$VT" <<'PY'
import os, struct, sys
sys.path.insert(0, sys.argv[1])
import make_test_iso as m
out = sys.argv[2]

def xiso(path, files):
    data = bytearray(m.SECTOR * (m.HEADER_SECTOR + 2))
    entries = []
    for name, body in files.items():
        start = len(data) // m.SECTOR
        data += body + b"\0" * (-len(body) % m.SECTOR)
        entries.append((name, start, len(body), m.ATTR_ARCHIVE))
    table, size = m.build_directory(entries)
    tsec = len(data) // m.SECTOR
    data += table + b"\0" * (-len(table) % m.SECTOR)
    off = m.HEADER_SECTOR * m.SECTOR
    data[off:off + 20] = m.MAGIC
    struct.pack_into("<II", data, off + 20, tsec, size)
    open(path, "wb").write(data)

# LITERALS, not make_test_iso's constants: the fixture must build against the
# pre-change module too, or the falsification run goes red on a missing
# attribute and every leg after it passes or fails for no reason at all.
vsh = b"XBEH" + b"\0" * 60 + b"d:\\vsh_tests.cnf\0Testing completed normally\0"
xiso(os.path.join(out, "vsh.iso"), {"default.xbe": vsh, "OFL.txt": b"font"})
xiso(os.path.join(out, "vsh-reboot.iso"),
     {"default.xbe": vsh + b"Rebooting in 4 seconds...\0"})
xiso(os.path.join(out, "pgraph.iso"),
     {"default.xbe": b"XBEH" + b"\0" * 60 + b"d:\\nxdk_pgraph_tests_config.json\0"})
PY
check "the fixture images were written" \
      eval '[ -s "$VT/vsh.iso" ] && [ -s "$VT/vsh-reboot.iso" ] && [ -s "$VT/pgraph.iso" ]'

# -------------------------------------------------------- make_test_iso.py
vsh_out=$(python3 "$MKISO" --inspect --program vsh "$VT/vsh.iso" 2>&1); vsh_rc=$?
check "a bare vsh image is refused by --inspect (rc=$vsh_rc)" [ "$vsh_rc" = 1 ]
check "  ... and the refusal names the missing cnf" grep -q "no vsh_tests.cnf" <<<"$vsh_out"

python3 "$MKISO" "$VT/vsh.iso" --program vsh -o "$VT/built.iso" \
    --suite "ILU RCP Tests" --suite "Exceptional Float" >"$VT/build.log" 2>&1
check "a vsh disc builds with --program vsh and two suites" [ -s "$VT/built.iso" ]
built=$(python3 "$MKISO" --inspect --program vsh "$VT/built.iso" 2>&1); built_rc=$?
check "the built vsh disc passes --inspect (rc=$built_rc)" [ "$built_rc" = 0 ]
vsh_cnf_is() {
    python3 -c 'import json,sys; d=json.loads(sys.stdin.read().split("\nrefused")[0])
sys.exit(0 if d["cnf"] == ["ILU RCP Tests", "Exceptional Float"] and not d["pgraph_config"] else 1)' <<<"$built"
}
check "  ... its cnf lists both suites in order, and it carries no pgraph JSON" vsh_cnf_is

pg_out=$(python3 "$MKISO" "$VT/vsh.iso" -o "$VT/wrong.iso" --suite "ILU RCP Tests" 2>&1); pg_rc=$?
check "a vsh image given the pgraph treatment is refused (rc=$pg_rc)" [ "$pg_rc" != 0 ]
check "  ... because it carries the vsh program, and no disc was written" \
      eval 'grep -q "carries the vsh program" <<<"$pg_out" && [ ! -e "$VT/wrong.iso" ]'

rb_out=$(python3 "$MKISO" "$VT/vsh-reboot.iso" --program vsh -o "$VT/rb.iso" --suite "MAC mov" 2>&1)
check "a rebooting vsh build is refused, and no disc was written" \
      eval 'grep -q "rebooting build" <<<"$rb_out" && [ ! -e "$VT/rb.iso" ]'

ty_out=$(python3 "$MKISO" "$VT/vsh.iso" --program vsh -o "$VT/ty.iso" --suite "ILU_RCP_Tests" 2>&1)
check "an unknown vsh suite is refused (the program would run every suite)" \
      eval 'grep -q "not an nxdk_vsh_tests suite" <<<"$ty_out" && [ ! -e "$VT/ty.iso" ]'

python3 "$MKISO" "$VT/pgraph.iso" -o "$VT/pg.iso" --suite "Blend tests" >/dev/null 2>&1
check "a pgraph image still builds as pgraph" [ -s "$VT/pg.iso" ]

# -------------------------------------------------------------- request.sh
vsh_req() {   # vsh_req <who> <args...>: request.sh against this fragment's queue
    local who=$1; shift
    DISPATCH_DIR="$VD" bash "$TESTING/request.sh" --who "$who" --purpose selftest \
        --no-expect "selftest" "$@"
}
vsh_queued() { ls "$VD/queue/" 2>/dev/null | grep -q -- "-$1-"; }
vsh_not_queued() { ! vsh_queued "$1"; }

# THE FALSIFIER. No --program: the pre-change request.sh queues this.
fq_out=$(vsh_req vshpgraph --base-iso "$VT/vsh.iso" --suites "ILU RCP Tests" 2>&1)
# One leg, both halves: refused for ANY reason (a missing fixture reads
# "no such file") would otherwise pass it.
check "request.sh does NOT queue a vsh ISO passed as a pgraph disc, BECAUSE it is one" \
      eval 'vsh_not_queued vshpgraph && grep -q "queued as pgraph" <<<"$fq_out"'

# A serving snapshot that predates program vsh would build the same hang.
st_out=$(vsh_req vshstale --program vsh --base-iso "$VT/vsh.iso" --suites "ILU RCP Tests" 2>&1)
check "program vsh is refused while the serving snapshot cannot run it" vsh_not_queued vshstale
check "  ... naming the snapshot" grep -q "serving dispatcher snapshot" <<<"$st_out"

cp "$TESTING/make_test_iso.py" "$TESTING/dispatcher.sh" "$TESTING/vsh_score.py" "$VD/bin/"

rr_out=$(vsh_req vshreboot --program vsh --base-iso "$VT/vsh-reboot.iso" --suites "MAC mov" 2>&1)
check "program vsh on a rebooting build is refused at queue time" vsh_not_queued vshreboot
check "  ... naming the reboot" grep -q "rebooting build" <<<"$rr_out"

vsh_req vshtypo --program vsh --base-iso "$VT/vsh.iso" --suites "ILU_RCP_Tests" >/dev/null 2>&1
check "program vsh with an unknown suite is refused at queue time" vsh_not_queued vshtypo

vsh_req vshnoiso --program vsh --suites "ILU RCP Tests" >/dev/null 2>&1
check "program vsh with no --base-iso is refused (the stock disc is pgraph)" vsh_not_queued vshnoiso

vsh_req vshok --program vsh --base-iso "$VT/vsh.iso" --suites "ILU RCP Tests,Exceptional Float" >/dev/null 2>&1
check "program vsh on a shutdown build with known suites IS queued" vsh_queued vshok
vsh_req_program() {
    python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["program"] == "vsh" else 1)' \
        "$(ls "$VD"/queue/*-vshok-*.req | head -1)"
}
check "  ... and the queued request records program vsh" vsh_req_program

# ------------------------------------------------------------ vsh_score.py
# Three tests, so a first-wins or last-wins mistake cannot pass: one identical,
# one differing in the MIDDLE, one stale. Plus one the console has that never
# came back.
mkdir -p "$VT/ref/S_A" "$VT/run"
printf 'A\n1.0\n' > "$VT/ref/S_A/one.txt";   printf 'A\n1.0\n' > "$VT/run/S_A::one.txt"
printf 'B\nnan\n' > "$VT/ref/S_A/two.txt";   printf 'B\n0.0\n' > "$VT/run/S_A::two.txt"
printf 'C\ninf\n' > "$VT/ref/S_A/three.txt"; printf 'C\ninf\n' > "$VT/run/S_A::three.txt"
printf 'D\n' > "$VT/ref/S_A/four.txt"
printf 'Starting S A::one\nTesting completed normally, closing log.\n' > "$VT/run/log.txt"
cat > "$VT/run/.fatx_times.json" <<'JSON'
{"log.txt": {"created": "2026-09-25T10:00:00", "modified": "2026-09-25T10:01:00"},
 "S_A::one.txt": {"created": "2026-09-25T10:00:10", "modified": "2026-09-25T10:00:10"},
 "S_A::two.txt": {"created": "2026-09-25T10:00:20", "modified": "2026-09-25T10:00:20"},
 "S_A::three.txt": {"created": "2026-09-24T09:00:00", "modified": "2026-09-24T09:00:00"}}
JSON
python3 "$TESTING/vsh_score.py" "$VT/run" --reference "$VT/ref" --tsv "$VT/score.tsv" \
    > "$VT/score.out" 2>&1
vsh_verdict() { grep -qP "^S_A/$1\t$2\t" "$VT/score.tsv"; }
check "vsh_score: an identical .txt is IDENTICAL"             vsh_verdict one IDENTICAL
check "vsh_score: a changed value is DIFFERS"                 vsh_verdict two DIFFERS
check "  ... and the differing line is printed"               grep -q -- "+0.0" "$VT/score.out"
check "vsh_score: a file older than this run's log is STALE"  vsh_verdict three STALE
check "vsh_score: a console test that never came back is MISSING" vsh_verdict four MISSING

# ------------------------------------------------------------ dispatcher.sh
# vsh_score.py is run from the snapshot, so it must be shipped AND hashed.
vsh_shipped() {
    grep -A3 '^SCRIPT_DEPS=' "$TESTING/dispatcher.sh" | grep -q vsh_score.py &&
    sed -n '/^snapshot_scripts()/,/^}/p' "$TESTING/dispatcher.sh" | grep -q vsh_score.py
}
check "dispatcher.sh ships and hashes vsh_score.py" vsh_shipped
