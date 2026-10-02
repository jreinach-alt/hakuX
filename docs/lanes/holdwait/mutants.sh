#!/usr/bin/env bash
# Runs selftest.d/99-hold-take.sh against broken copies of hold.sh, one per
# way wait-idle could be wrong, and prints which legs each copy fails. A leg
# that no mutant fails checks nothing; a mutant that fails no leg is a hole.
#   bash docs/lanes/holdwait/mutants.sh [outdir]
set -u
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
SRC="$REPO/docs/testing/jobs/hold.sh"
OUT="${1:-$(mktemp -d)}"
mkdir -p "$OUT"

mutant() {   # <name> <python that edits the text s>
    python3 - "$SRC" "$OUT/$1.sh" "$2" <<'PY'
import sys
s = open(sys.argv[1]).read()
t = s
exec(sys.argv[3])
assert t != s, "mutant changed nothing"
open(sys.argv[2], "w").write(t)
PY
}

# M1 never looks: wait-idle always exits 0.
mutant always-idle 't = s.replace("if op == \"idle\":\n", "if op == \"idle\":\n    sys.exit(0)\n", 1)'
# M2 running/ only: the worker registration is not consulted.
mutant no-lane-check 't = s.replace("    if lane.isdigit():", "    if False:", 1)'
# M3 reads .req, not .owner: an owner past its .req does not block.
mutant req-not-owner 't = s.replace("        rid = n[:-len(\".owner\")]\n", "        rid = n[:-len(\".owner\")]\n        if not os.path.exists(os.path.join(rdir, rid + \".req\")): continue\n", 1)'
# M8 never idle: the device always reads busy.
mutant always-busy 't = s.replace("    print(\"idle: %s is held and runs nothing\" % label)\n    sys.exit(0)", "    sys.exit(3)", 1)'
# M4 substring match: "nova" matches an owner "nova2".
mutant substring 't = s.replace(".strip() != label:", ".strip().find(label) != 0:", 1)'
# M5 no hold needed: idle without a hold answers 0.
mutant no-hold-check 't = s.replace("    if read(path) is None:\n        print(\"no hold", "    if False:\n        print(\"no hold", 1)'
# M6 any lanes pid blocks: a stale or reused pid jams the wait.
mutant any-pid 't = s.replace("live = b\"dispatcher.sh\" in f.read()", "live = True", 1)'
# M7 take stays silent on a busy device (the pre-holdwait take).
mutant silent-take 't = s.replace("        hold_py take \"$label\" \"$3\" \"${*:4}\" || exit $?\n        notice_idle ;;", "        hold_py take \"$label\" \"$3\" \"${*:4}\" ;;", 1)'

for m in "$OUT"/*.sh; do
    name=$(basename "$m" .sh)
    env SELFTEST_ONLY=99-hold-take SELFTEST_HOLD_SH="$m" bash "$REPO/docs/testing/jobs/selftest.sh" > "$OUT/$name.log" 2>&1
    echo "== $name: $(grep -c '^  FAIL' "$OUT/$name.log") failing"
    grep '^  FAIL' "$OUT/$name.log" | sed 's/^/   /'
done
