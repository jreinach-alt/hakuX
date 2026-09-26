#!/usr/bin/env bash
# Each mutant is one edit to one file in a COPY of the testing tree; the
# release fragment must go red on every one. Prints one line per mutant.
set -u
LANE="$(cd "$(dirname "$0")" && pwd)"; SRC="$(cd "$LANE/../../testing" && pwd)"
S=$(mktemp -d "${TMPDIR:-/tmp}/boardrelease-mut.XXXXXX")
mutate() {   # <name> <file under testing/> <old> <new>
    local d="$S/$1/testing"
    mkdir -p "$d/jobs"
    cp "$SRC/check_territory.py" "$SRC/fleet.py" "$SRC/gh_rest.py" "$SRC/board_files.py" "$d/"
    cp "$SRC/jobs/board.sh" "$SRC/jobs/localtime.sh" "$SRC/jobs/window.sh" "$d/jobs/"
    python3 -c 'import sys
p, old, new = sys.argv[1:]
s = open(p).read()
assert s.count(old) == 1, "mutant anchor not found exactly once: %r" % old
open(p, "w").write(s.replace(old, new))' "$d/$2" "$3" "$4" || { echo "$1: MUTANT DID NOT APPLY"; return; }
    if out=$(bash "$LANE/run-release.sh" "$d" 2>&1); then
        echo "$1: GREEN (the fragment cannot see this mutant)"
    else
        echo "$1: red -- $(grep -c '  FAIL' <<< "$out") failed: $(grep '  FAIL' <<< "$out" | head -1 | sed 's/^ *FAIL //')"
    fi
}
# check_territory.py
mutate ct-ignore-released check_territory.py '            if f not in released:' '            if True:'
mutate ct-two-more        check_territory.py '        if len(lanes) > 1:' '        if len(lanes) > 2:'
mutate ct-no-subset       check_territory.py '            if f not in files:' '            if False:'
# fleet.py
mutate fl-draft-releases  fleet.py $'        if p.get("isDraft"):\n            continue\n        n = p["number"]' $'        n = p["number"]'
mutate fl-ignore-ci       fleet.py '        if cand and ci == "green":' '        if cand:'
mutate fl-ignore-unit     fleet.py '                and p["lane"] not in units)' '                )'
mutate fl-ignore-released fleet.py $'        todo = [f for f in meta.get("files", [])\n                if f not in meta.get("released", [])]' '        todo = list(meta.get("files", []))'
mutate fl-no-threshold    fleet.py '        if age is None or age < FOLD_STUCK_S:' '        if age is None:'
mutate fl-conflict-waits  fleet.py '        if mergeable is False:' '        if mergeable is False and age and age >= FOLD_STUCK_S:'
mutate fl-never-ran-green fleet.py $'    if not runs:\n        ci = "never ran"' $'    if False:\n        ci = "never ran"'
mutate fl-no-stuck-fail   fleet.py $'    for n, lane, age, why, fix in stuck:\n        print("FAIL' $'    for n, lane, age, why, fix in []:\n        print("FAIL'
# board.sh
mutate bs-taken-ignored   jobs/board.sh '"taken by lane." + taken[0] if taken else "AVAILABLE"' '"AVAILABLE"'
mutate bs-no-released     jobs/board.sh '    for f in meta.get("released") or []:' '    for f in meta.get("files") or []:'
rm -rf "$S"
