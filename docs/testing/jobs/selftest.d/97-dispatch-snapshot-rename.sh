# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# $REPO, ok/bad/check. Not executable, no shebang, no exit.
#
# snapshot_scripts must never rewrite a file another worker is executing
# (dispatch-hardening defect 13).
#
# $SNAP is shared by every worker, and bash reads a running script lazily, by
# byte offset. On 2026-09-25 the Nova worker re-execed after a fold and its
# `cp -f` rewrote $SNAP/run_disc.sh under the Thor, which was inside it. The
# Thor's bash read the new file at the old offset (`line 137: cess: command
# not found`) and a real run was voided as "the emulator never started".
#
# The fixture is exact, not a race: v1's first line is `sleep 2` (8 bytes), and
# v2 is built so that byte 8 starts `echo GARBLED`. A bash still reading v1
# prints `v1-done` if its file was left alone and `GARBLED` if it was
# overwritten in place. The mutant (the old `cp -f`) runs from a copy.

echo "== dispatch: a re-snapshot does not rewrite a script a worker is running"

SR="$T/snaprename"; rm -rf "$SR"; mkdir -p "$SR/src" "$SR/d"
printf 'sleep 2\necho v1-done\n' > "$SR/v1"
printf 'true ;  echo GARBLED\necho v2-done\n' > "$SR/v2"
snap_race() {   # <dispatcher.sh> -> what the running v1 printed, then the new snapshot's first line
    rm -rf "$SR/d"; mkdir -p "$SR/d/bin"
    cp "$SR/v1" "$SR/d/bin/run_disc.sh"; cp "$SR/v2" "$SR/src/run_disc.sh"
    bash "$SR/d/bin/run_disc.sh" > "$SR/out" 2>&1 &
    local pid=$!
    sleep 0.5
    ( export DISPATCH_DIR="$SR/d" DISPATCH_SRC="$SR/src" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
      . "$1" selftest-not-a-subcommand >/dev/null 2>&1
      snapshot_scripts )
    wait "$pid"
    tr '\n' ' ' < "$SR/out"; echo "| $(head -1 "$SR/d/bin/run_disc.sh")"
}

got=$(snap_race "$TESTING/dispatcher.sh")
check "the running worker finishes the file it started (v1-done)" grep -q '^v1-done |' <<< "$got"
check "  and reads nothing of the new one" bash -c '[[ "${1%%|*}" != *GARBLED* && "${1%%|*}" != *v2-done* ]]' -- "$got"
check "  and the snapshot now holds v2 for the next exec" grep -q '| true ;  echo GARBLED$' <<< "$got"
check "  and leaves no temp file behind" bash -c '[ -z "$(ls -A "$1" | grep -v "^run_disc.sh$")" ]' -- "$SR/d/bin"

# The mutant: the old in-place copy. Beside its sourced helper, like a worker.
md="$SR/mut"; mkdir -p "$md"; cp "$TESTING/devices.sh" "$md/"
python3 - "$TESTING/dispatcher.sh" "$md/dispatcher.sh" <<'PY'
import re, sys
src, dst = sys.argv[1:]
s = open(src).read()
old = re.search(r'        cp -f "\$SRC/\$f" "\$SNAP/\.\$f\.tmp\.\$\$" 2>/dev/null \\\n.*?\n.*?rm -f "\$SNAP/\.\$f\.tmp\.\$\$"\n', s, re.S)
assert old, "mutant anchor no longer matches dispatcher.sh"
open(dst, "w").write(s[:old.start()] + '        cp -f "$SRC/$f" "$SNAP/$f" 2>/dev/null\n' + s[old.end():])
PY
if [ -f "$md/dispatcher.sh" ]; then
    mg=$(snap_race "$md/dispatcher.sh")
    case "${mg%%|*}" in
        *GARBLED*) ok "mutant 'cp -f in place' garbles the running script (red, as it must be): $mg" ;;
        *) bad "mutant 'cp -f in place' did not garble the running script: $mg" ;;
    esac
else
    bad "mutant anchor no longer matches dispatcher.sh"
fi
rm -rf "$SR"
