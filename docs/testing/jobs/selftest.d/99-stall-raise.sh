# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# title_registry.py check --stalls (#stallraise1017). Owner 10-17: "the rule
# should be to raise them when you have a title with one measured hitch like
# this, not bury it in some report and then forget about it for days".
# Marvel Nemesis (hold marvel-851) sat 10-06 to 10-17 with no row ever asking
# the owner. This builds a registry (via title_registry.write(), so it is the
# real on-disk format, not a hand-typed guess of it) with one single-stall
# candidate, then exercises pm/stall-raised.tsv against it: raised and within
# grace both pass; the raised row REMOVED -- the exact shape of how Marvel
# Nemesis went unasked -- must go red, naming the title.
#
# Independent of every other fragment: its own root under $T, nothing read
# from the live host's pm/.

echo "== title_registry.py check --stalls: an unraised single-stall candidate goes red"
SX="$T/stallraise"; rm -rf "$SX"; mkdir -p "$SX/pm"
python3 - "$SX" "$TESTING" <<'PY'
import datetime as dt
import sys
sx, testing = sys.argv[1], sys.argv[2]
sys.path.insert(0, testing)
import title_registry as TR

p = TR.Paths(root=sx)
old = TR.iso_z(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3))
recent = TR.iso_z(dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=30))


def row(tid, name, verdict_utc, status="BELOW_BAR", failing_all="hitch"):
    r = dict.fromkeys(TR.COLUMNS, "")
    r.update(title_id=tid, name=name, status=status, status_rule="selftest fixture",
             failing_all=failing_all, verdict_utc=verdict_utc, latest_verdict="fixture/verdict.json")
    return r


rows = [
    row("4D53002D", "Dead or Alive 3 (selftest)", old),            # overdue candidate
    row("544D0011", "Gene Troopers (selftest)", recent),           # within-grace candidate
    row("4E4D0006", "Pac-Man World 2 (selftest)", old,
        status="BELOW_BAR", failing_all="hitch+fps"),              # NOT a candidate: fails more than hitch
]
TR.write(p, rows, out=p.registry, open_issues={}, unresolved=[])
PY
check "the fixture registry really has the overdue candidate as BELOW_BAR/hitch" \
    bash -c "grep -qE '^4D53002D\b.*BELOW_BAR' \"$SX/pm/title-registry.tsv\""

sx_check() {   # <stall-raised.tsv body> -> stdout+rc into $SX/out.txt / $SX/rc
    printf 'title_id\traised_pdt\trun\tstall_ms\tframes\towner_answer\tanswered_pdt\n%s' "$1" > "$SX/pm/stall-raised.tsv"
    python3 "$TESTING/title_registry.py" check --root "$SX" --registry "$SX/pm/title-registry.tsv" --stalls \
        > "$SX/out.txt" 2>&1; echo $? > "$SX/rc"
}

sx_check "4D53002D	2026-10-17 20:00	fixture/overdue	621	LOADING
544D0011	2026-10-17 21:50	fixture/recent	530	PLAY
"
check "a raised overdue candidate does not FAIL" bash -c '! grep -q "STALL NOT RAISED" "$SX/out.txt"'
check "...and check --stalls exits 0" [ "$(cat "$SX/rc")" = 0 ]

sx_check "544D0011	2026-10-17 21:50	fixture/recent	530	PLAY
"
check "an overdue candidate with its raised row removed FAILs, naming the title" \
    grep -qE 'STALL NOT RAISED 4D53002D .*single-stall candidate' "$SX/out.txt"
check "...and check --stalls exits 3" [ "$(cat "$SX/rc")" = 3 ]
check "a candidate still within the 2h grace, never raised, does not FAIL" \
    bash -c '! grep -q "544D0011" "$SX/out.txt"'
check "a BELOW_BAR title failing more than just hitch is never called a candidate" \
    bash -c '! grep -q "4E4D0006" "$SX/out.txt"'

sx_check "4D53002D	not-a-date	fixture/overdue	six-twenty-one	WRONG
544D0011	2026-10-17 21:50	fixture/recent	530	PLAY
"
check "a malformed stall-raised.tsv row is rejected, not silently trusted (3 bad fields caught)" \
    bash -c '[ "$(grep -c "STALL ROW INVALID" "$1")" = 3 ]' _ "$SX/out.txt"
check "...and still exits 3" [ "$(cat "$SX/rc")" = 3 ]
rm -rf "$SX"
