# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, $DISPATCH_DIR, the shims on PATH, ok/bad/check. Not executable, no
# shebang, no exit -- `fail` is shared and is the run's verdict.
#
# The board's third dispatch state: covered, blocked, AVAILABLE.
# Written as an append to selftest.sh (#134, lane/backlogstate) and carried
# here unchanged when the split (#136) landed underneath it, except for the
# two adaptations the split's neighbours forced, each marked AFTER THE SPLIT
# below.
#
# 93 because it must run before 96-fleet-registry.sh, which asserts on the
# exact count of registry entries under $DISPATCH_DIR/fleet; this fragment
# keeps its fleet fixtures in a directory of its own so that count is not its
# business. It builds its own board, its own gh and its own systemctl, and
# depends on no other fragment.

echo "== the board's three states: covered, blocked, AVAILABLE"
# WHY THIS IS HERE. check_coverage.py demanded that every open issue be owned
# by a lane or carry a non-empty `blocked_on`, and a failure makes preflight
# red for every lane on the repository. A backlog's normal condition -- open,
# unblocked, nobody on it yet, waiting for capacity -- had no third state, so
# the board's only way to get a green preflight for an issue it could not
# dispatch this tick was to write into the one field that means "do not
# dispatch this". On 2026-09-18 six open rows carried a `blocked_on` whose
# first words were "NOT BLOCKED" and two more (since deleted) read "Blocked on
# local dispatch capacity this tick, not on anything technical."
#
# THE FIXTURE IS A WHOLE FAKE BOARD, not a unit test of a regex, because the
# defect is a disagreement BETWEEN two consumers of one schema: coverage
# counted those rows as blocked while fleet undid it with a substring search.
# Both scripts read the board through board_files.py, which falls back to the
# working tree when HAKUX_BOARD_REF is empty -- so a directory holding copies
# of the three modules plus two toml files IS a board, and the real scripts
# run against it unmodified.
#
# SELFTEST_BOARD_SRC exists so this section can be pointed at the OLD scripts
# (`git show origin/master:docs/testing/check_coverage.py` into a directory)
# and seen to fail, rather than being reasoned about. Verified 2026-09-19:
# against master@bdeab36f75 four of these checks fail -- the available row
# reads as an uncovered gap, the "NOT BLOCKED" opening passes as a blocker,
# and fleet calls both the unclassified row and the mid-text mention
# dispatchable.
BSRC="${SELFTEST_BOARD_SRC:-$TESTING}"
BD="$T/board"; BDD="$T/board-dispatch"
# AFTER THE SPLIT (1/2): a dispatch directory of this fragment's OWN, not the
# shared $DISPATCH_DIR. 96-fleet-registry.sh asserts on the exact registry
# contents under $DISPATCH_DIR/fleet ("a registry entry whose unit is gone is
# not reported as running", by name), and this fragment sorts before it. When
# both appended to one selftest.sh the write order was the same but the
# coupling was invisible; a fragment that leaves fixtures in a shared
# directory for a later fragment to trip over is the failure mode the split
# was done to remove.
mkdir -p "$BD" "$T/bin2" "$BDD/fleet" "$BDD/deliveries"
cp "$BSRC/check_coverage.py" "$BSRC/fleet.py" "$BSRC/board_files.py" "$BD/"
check "the three board modules were copied from $BSRC" \
    bash -c '[ -s "$1/check_coverage.py" ] && [ -s "$1/fleet.py" ] && [ -s "$1/board_files.py" ]' _ "$BD"
printf '{"lane":"alpha","agent":"a","issues":["1"],"dispatched_utc":"2026-09-19T00:00:00Z","asked":"the running lane"}\n' > "$BDD/fleet/alpha.json"
: > "$BDD/deliveries/alpha.md"     # so the UNBRIEFED tail stays out of line 1
cat > "$T/bin2/gh" <<'EOF'
#!/usr/bin/env bash
# Four open issues, which is what a board fixture needs and all it needs.
[[ "$*" == *"issue list"* ]] || exit 0
echo '[{"number":1,"title":"owned by a running lane"},{"number":2,"title":"the available one"},{"number":3,"title":"really blocked"},{"number":4,"title":"mentions NOT BLOCKED mid-text"}]'
EOF
# AFTER THE SPLIT (2/2): `alpha is running` used to be the `"state": "running"`
# field in the registry entry above. ae3712aae1 (#133) made fleet.py derive
# the running set from `systemctl --user list-units hakux-lane-*` instead,
# because nothing had written that field since the orchestrator role was
# deleted. The fixture moves with it: the fact this fragment needs is
# unchanged -- a lane is running on issue 1 -- only the place fleet.py asks.
# The top-level shim answers `is-active` and nothing else, which lane_units()
# reads as an EMPTY fleet rather than a blind one, so without this the
# "held by a RUNNING lane" check below would pass for the wrong reason.
cat > "$T/bin2/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *list-units*hakux-lane*) echo "hakux-lane-alpha.service loaded active running claude" ;;
    *show*) printf 'Id=hakux-lane-alpha.service\nActiveEnterTimestampMonotonic=1000000\n' ;;
    *is-active*) echo active ;;
esac
exit 0
EOF
chmod +x "$T/bin2/gh" "$T/bin2/systemctl"
board() {   # <variant>: write the fixture board, varying issue 2 only
    python3 - "$BD" "$1" <<'PY'
import os, sys
bd, variant = sys.argv[1], sys.argv[2]
held = "[1, 2]" if variant == "ownedavail" else "[1]"
open(os.path.join(bd, "territory.toml"), "w").write(
    '[lane.alpha]\nfiles = []\nissues = %s\n\n[free]\nnote = "x"\n' % held)
# Issue 4 is the false positive a substring search produces: the board
# recording a wording it had ALREADY corrected. It must read as blocked.
rows = [
    ('1', 'status = "open"\n'
          'status_note = "a lane is on it"\n'
          'blocked_on = ""\n'),
    ('3', 'status = "open"\n'
          'status_note = "n"\n'
          'blocker_tested = "read the spec 2026-09-19"\n'
          'blocked_on = "Blocked on real Xbox hardware, which nobody has."\n'),
    ('4', 'status = "open"\n'
          'status_note = "n"\n'
          'blocker_tested = "2026-09-19"\n'
          'blocked_on = "ORDERED behind lane.alpha. The gate was right to '
          'refuse the earlier wording: I had written NOT BLOCKED and then '
          'left it unallocated, which reads as coverage and is not. Also '
          'DIRTY_MEMORY_NV2A_TEX is test-and-cleared."\n'),
]
two = {
    # the third state, written correctly
    "base":       'status = "open"\ndispatch_state = "available"\nblocked_on = ""\n',
    # same row, but a lane holds it too -- the count must not read zero
    "ownedavail": 'status = "open"\ndispatch_state = "available"\nblocked_on = ""\n',
    # nobody classified it: still a failure, and the gate must say so
    "gap":        'status = "open"\nblocked_on = ""\n',
    # the shape being migrated away from
    "notblocked": 'status = "open"\nblocked_on = "NOT BLOCKED, and it is the '
                  'best offline-implementable prize on the board."\n',
    # the waiting-for-a-slot shape, in the field that means the opposite
    "capacity":   'status = "open"\nblocked_on = "Blocked on local dispatch '
                  'capacity this tick, not on anything technical."\n',
    # a REAL blocker that happens to use the word "cleared" in its first
    # sentence: must pass, or the gate punishes honest prose
    "honest":     'status = "open"\nblocker_tested = "2026-09-19"\n'
                  'blocked_on = "Blocked until the audit has cleared the held '
                  'fold, which is not this lane\'s to do."\n',
    # the same word SHOUTED as a status marker, which is how #89 wrote it
    "shouted":    'status = "open"\nblocker_tested = "2026-09-19"\n'
                  'blocked_on = "CLEARED 2026-09-19: the device run this was '
                  'blocked on is done."\n',
    # finished work reading as available is how an issue gets re-dispatched
    "done":       'status = "fixed-verified"\ndispatch_state = "available"\n'
                  'blocked_on = ""\n',
    "both":       'status = "open"\ndispatch_state = "available"\n'
                  'blocked_on = "Blocked on real hardware."\n',
    "typo":       'status = "open"\ndispatch_state = "avaliable"\n'
                  'blocked_on = ""\n',
    # `done` where it contradicts `status`: a second place to say a row is
    # finished, disagreeing with the first. The mirror of "done" on a closed
    # row is issue 5 below, which the `done_ok` variant adds.
    "done_open":  'status = "open"\ndispatch_state = "done"\n'
                  'blocked_on = ""\n',
    "done_ok":    'status = "open"\nblocker_tested = "2026-09-19"\n'
                  'blocked_on = "Blocked on real Xbox hardware."\n',
}[variant]
rows.append(('2', 'status_note = "n"\n' + two))
if variant == "done_ok":
    # The real shape of the board's own `done`, which is #84: a row the gh
    # shim does NOT list as open, closed in the tracker, `dispatch_state`
    # kept as the record that it was classified. It must be accepted, and it
    # must not touch the open accounting -- a closed row needs no coverage.
    rows.append(('5', 'status = "closed"\nstatus_note = "n"\n'
                      'dispatch_state = "done"\nblocked_on = ""\n'))
out = []
for n, body in sorted(rows, key=lambda r: int(r[0])):
    out.append('[issue.%s]\ntitle = "issue %s"\n%s' % (n, n, body))
open(os.path.join(bd, "nv2a_issues.toml"), "w").write("\n".join(out))
PY
}
cov() { env PATH="$T/bin2:$PATH" HAKUX_BOARD_REF= DISPATCH_DIR="$BDD" \
            python3 "$BD/check_coverage.py" 2>&1; }
flt() { env PATH="$T/bin2:$PATH" HAKUX_BOARD_REF= DISPATCH_DIR="$BDD" \
            python3 "$BD/fleet.py" 2>&1; }
# Every assertion below is on the OUTPUT WORDS, never on the exit code alone:
# the old scripts exit 1 on most of these variants too, for the wrong reason
# (the available row reads as an uncovered gap), so rc is far too coarse to
# tell the fix from the defect.
board base; out=$(cov)
check "an explicitly AVAILABLE row is covered -- the third state" \
    grep -q "^coverage ok (4 open: 1 AVAILABLE, 2 blocked, 1 owned by a lane" <<< "$out"
out=$(flt)
check "fleet calls exactly the available row dispatchable" \
    grep -q "^=== DISPATCHABLE NOW, NOT DISPATCHED (1)$" <<< "$out"
check "...and it is #2, by its structured field and not by its prose" \
    grep -q "^  #2 .*dispatch_state=available" <<< "$out"
check "a mid-text 'NOT BLOCKED' about another row is NOT dispatchable" \
    bash -c '! grep -q "^  #4 " <<< "$1"' _ "$out"
check "nothing is unclassified on a fully classified board" \
    grep -q "^=== NEITHER BLOCKED NOR MARKED AVAILABLE (0)$" <<< "$out"

# EVERY MIGRATED ROW ON THE REAL BOARD IS ALSO HELD BY A LANE, so a count of
# "available and not owned" reads 0 exactly when the state is in use. That was
# the first version of the summary line and it is the reason this variant
# exists: the number must be over ALL open issues, overlap and all.
board ownedavail; out=$(cov)
check "the AVAILABLE count does not read zero when a lane also holds the row" \
    grep -q "^coverage ok (4 open: 1 AVAILABLE, 2 blocked, 2 owned by a lane" <<< "$out"
out=$(flt)
# THE FIXTURE'S OWN SANITY CHECK, and it is not decoration. "Not dispatchable
# because a lane is running on it" passes for free against a fleet that is
# empty, and against one that is BLIND -- and after ae3712aae1 an empty fleet
# is what a systemctl shim answering only `is-active` produces. Assert alpha
# is in RUNNING, and that fleet was not blind, before reading the 0 below as
# the skip doing its job.
check "the fixture's lane really is RUNNING, so the next check is not vacuous" \
    grep -qE '^  alpha ' <<< "$out"
check "...and fleet was not blind, which would suppress the section entirely" \
    bash -c '! grep -q "FLEET-BLIND" <<< "$1"' _ "$out"
check "an available row held by a RUNNING lane is not dispatchable" \
    grep -q "^=== DISPATCHABLE NOW, NOT DISPATCHED (0)$" <<< "$out"

board gap; out=$(cov)
check "an UNCLASSIFIED row still fails -- the gate is not weakened" \
    grep -q "FAIL: 1 open issue(s) with neither a lane nor a blocker" <<< "$out"
check "the failure names all three ways to clear it" \
    grep -q 'dispatch_state = "available"' <<< "$out"
out=$(flt)
check "fleet does not call an unclassified row dispatchable" \
    grep -q "^=== DISPATCHABLE NOW, NOT DISPATCHED (0)$" <<< "$out"
check "fleet reports it as neither blocked nor available instead" \
    grep -q "^  #2 " <<< "$(sed -n '/NEITHER BLOCKED NOR MARKED/,$p' <<< "$out")"
# The old code called this row DISPATCHABLE, which was the wrong description
# and a non-zero exit. Describing it accurately must not turn it into a note:
# the FAIL is the only thing that makes anyone classify it.
check "an unclassified row still costs fleet a FAIL, not just a note" \
    grep -q "FAIL: 1 open issue(s) are NEITHER BLOCKED NOR MARKED AVAILABLE" <<< "$out"

board notblocked; out=$(cov)
check "a blocked_on that OPENS with NOT BLOCKED fails" \
    grep -q "FAIL: 1 .blocked_on. that OPENS BY SAYING IT IS NOT BLOCKED" <<< "$out"
board capacity; out=$(cov)
check "'blocked on dispatch capacity, not on anything technical' fails" \
    grep -q "OPENS BY SAYING IT IS NOT BLOCKED" <<< "$out"
board honest; out=$(cov)
check "a real blocker using the word 'cleared' in prose is NOT flagged" \
    grep -q "^coverage ok (4 open: 0 AVAILABLE, 3 blocked" <<< "$out"
board shouted; out=$(cov)
check "...but CLEARED shouted as a status marker is" \
    grep -q "OPENS BY SAYING IT IS NOT BLOCKED" <<< "$out"
board done; out=$(cov)
check "AVAILABLE on work that is no longer open fails" \
    grep -q '`available` with status' <<< "$out"
board both; out=$(cov)
check "AVAILABLE alongside a blocker fails as the contradiction it is" \
    grep -q '`available` with a non-empty `blocked_on`' <<< "$out"
board typo; out=$(cov)
check "an unrecognised dispatch_state fails rather than reading as classified" \
    grep -q "is not one of available, blocked" <<< "$out"

# `done`, ADDED AFTER THE BOARD WROTE IT. The first enum was (available,
# blocked), and the `available`-on-a-closed-row rule above told the board
# that `available` had stopped holding without giving it a word to replace
# it with. It closed #84 and wrote `dispatch_state = "done"`, which is the
# right word -- and against the two-value enum that is the "unrecognised
# value" FAIL above, red for every lane on the repository over a row nobody
# will ever dispatch. Both directions are pinned, because a value added to
# stop a gate complaining is exactly the failure this schema was written to
# end.
board done_ok; out=$(cov)
# "4 open" against a FIVE-row tracker is the whole assertion: the closed row
# is accepted and is not counted among the rows needing coverage.
check "a closed row carrying dispatch_state = done is accepted, and is not open" \
    grep -q "^coverage ok (4 open: 0 AVAILABLE, 3 blocked" <<< "$out"
board done_open; out=$(cov)
check "done on a row whose status is still open FAILs, mirroring available" \
    grep -q '`done` on a row whose status is still `open`' <<< "$out"
check "...so done cannot cover an open row the way available does" \
    bash -c '! grep -q "^coverage ok" <<< "$1"' _ "$out"
# The fleet half of the same drift, asserted on a LIVE row: issue 2 is in the
# gh shim's open list here, so this really exercises the dispatch loop. The
# `done_ok` variant could not -- its done row is closed, and fleet iterates
# only live issues, so "not dispatchable" would have been true of it however
# fleet were written.
out=$(flt)
check "a live row marked done is not dispatched" \
    grep -q "^=== DISPATCHABLE NOW, NOT DISPATCHED (0)$" <<< "$out"
check "...it is reported as unclassified, since done says nothing about a blocker" \
    grep -q "^  #2 " <<< "$(sed -n '/NEITHER BLOCKED NOR MARKED/,$p' <<< "$out")"
