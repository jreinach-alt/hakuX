# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# dispatch_gate.py + title_registry.py: admission control between "someone
# decides to run it" and a handheld (owner order 2026-10-06 ~16:50, after four
# wrong dispatches in one day: Strike Force ahead of the plan order, RalliSport
# under an owner flicker hold, a validation on an unread-back APK, DOA3 and
# Dino Crisis 3 below the fps bar). dispatch_gate_selftest.py builds its own
# fixture work tree in a temp dir (no host file, no device, no forge) and runs
# each incident as a leg with a mutant that disables the rule it rests on; a
# leg whose mutant does not flip the decision is red ("MUTANT SURVIVED").

echo "== dispatch gate: the 2026-10-06 incidents as regression fixtures"
python3 "$REPO/docs/testing/dispatch_gate_selftest.py" > "$T/dispatch-gate.txt" 2>&1; dg_rc=$?
check "dispatch_gate_selftest.py: every leg green, every mutant flips its leg" [ "$dg_rc" -eq 0 ]
check "...and it ran the incident legs (DOA3, RalliSport, Strike Force)" \
    grep -q "GREEN DOA3 PLAYABLE_ATTEMPT -> deny" "$T/dispatch-gate.txt"
check "...and a commit that is merely newer is not a fix (fix:6cef37f426 denies DOA3)" \
    grep -q "GREEN DOA3 PLAYABLE_ATTEMPT citing fix:6cef37f426" "$T/dispatch-gate.txt"
check "...and the registry never shells out to gh" \
    grep -q "GREEN no .gh. invocation" "$T/dispatch-gate.txt"
[ "$dg_rc" -eq 0 ] || tail -20 "$T/dispatch-gate.txt"
