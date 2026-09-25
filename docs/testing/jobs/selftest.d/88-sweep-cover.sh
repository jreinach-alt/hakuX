# Sourced by ../selftest.sh with the harness already built: $T, $HERE,
# $TESTING, $REPO, the shims on PATH, ok/bad/check. Not executable, no
# shebang, no exit -- `fail` is shared and is the run's verdict.
#
# A sweep column counts only what it measured. score_sweep.py writes
# `differing = 0` for a row it could not score (`unreadable`, `size`,
# `no-golden`), and scoreboard.py used to read that 0 as an exact capture --
# the false win PR #249 removed from arm verdicts, still live in the sweep
# columns. A WSL-interop pull truncating 56 W_param PNGs would have scored 56
# exact. docs/lanes/sweepcover/NOTES.md records the falsification run: the old
# scoreboard.py on this fixture prints `3/6 · 1,026` with no void count --
# the unreadable row counted exact, the size row's 1,000 px counted structural.
#
# The fixture is one Fog sheet collected by collect_sweep.sh as a sweep would
# be, into a scratch board (SCOREBOARD_ROOT/_GOLDENS/_MD), never the live one:
#
#   a ok 0            exact
#   b ok 10 (4 1-step) 6 structural
#   c unreadable 0    VOID -- the row the old code called exact
#   d blank 20        scored content, 20 structural
#   e label-differs 0 scored content, exact
#   f size 1000       VOID -- a nonzero `differing`, so "structural px
#                     excludes void rows" is a leg that can fail
#
# Expected cell: 2/4 · 26 · 2 void.

echo "== sweep cover: a void row is not an exact capture"
SC="$T/sweepcover"
mkdir -p "$SC/goldens/Fog" "$SC/board" "$SC/dispatch/results/z-fix-001-Fog"
for t in a b c d e f; do : > "$SC/goldens/Fog/$t.png"; done
{
  printf 'suite\ttest\tsolo\tstatus\tdiffering\tmax_rgb\tmax_a\tpx\toff_by_one\n'
  printf 'Fog\ta\tFalse\tok\t0\t0\t0\t100\t0\n'
  printf 'Fog\tb\tFalse\tok\t10\t3\t0\t100\t4\n'
  printf 'Fog\tc\tFalse\tunreadable\t0\t0\t0\t0\t0\n'
  printf 'Fog\td\tFalse\tblank\t20\t9\t0\t100\t0\n'
  printf 'Fog\te\tFalse\tlabel-differs\t0\t0\t0\t100\t0\n'
  printf 'Fog\tf\tFalse\tsize\t1000\t0\t0\t100\t0\n'
} > "$SC/dispatch/results/z-fix-001-Fog/scores1.tsv"
printf '{"runs":[{"progress_log_proof":true}]}\n' > "$SC/dispatch/results/z-fix-001-Fog/result.json"

SCO=$(SCOREBOARD_ROOT="$SC/board" SCOREBOARD_GOLDENS="$SC/goldens" SCOREBOARD_MD="$SC/SB.md" \
      bash "$TESTING/collect_sweep.sh" fix "$SC/dispatch" 2>&1)
check "collect_sweep took the sheet into the scratch board" [ -s "$SC/board/fix/z-fix-001-Fog.tsv" ]
case "$SCO" in *"2 void row(s)"*"z-fix-001-Fog"*) ok "collect_sweep names the sheet's 2 void rows" ;;
               *) bad "collect_sweep did not name the void rows: $(printf '%s' "$SCO" | head -5)" ;; esac
case "$SCO" in *"2 VOID row(s) in 1 sheet(s)"*) ok "collect_sweep's summary counts them" ;;
               *) bad "collect_sweep's summary has no void count" ;; esac

# The row the board prints for Fog, from the Markdown the collection wrote.
sc_row() { grep -m1 '^| Fog' "$1" 2>/dev/null; }
SCR=$(sc_row "$SC/SB.md")
case "$SCR" in *"| 2/4 · 26 · 2 void |"*) ok "Fog cell is 2/4 · 26 · 2 void ($SCR)" ;;
               *) bad "Fog cell should be '2/4 · 26 · 2 void': got '$SCR'" ;; esac
# Each leg on its own, so a failure says which one moved.
case "$SCR" in *"| 2/4 "*) ok "exact/captures excludes the void rows (2/4, not the old 3/6)" ;;
               *) bad "exact/captures still counts void rows: $SCR" ;; esac
case "$SCR" in *" 2 void |"*) ok "the void count equals the void rows (2)" ;;
               *) bad "the void count is missing or wrong: $SCR" ;; esac
case "$SCR" in *" · 26 "*) ok "structural px excludes the void rows (26, not 1,026)" ;;
               *) bad "structural px counts a void row's differing: $SCR" ;; esac
check "the provenance row reports 4 captures and 2 void, by status" \
    grep -q '| 4 | 2 ⚠️ (size 1, unreadable 1) |' "$SC/SB.md"

# ONE scored-status set: scoreboard.py carries a copy of score_sweep.py's
# (it cannot import it without numpy), and a copy is only safe if it is held.
SCSETS=$(python3 - "$TESTING" <<'PY'
import re, sys
out = []
for f in ("score_sweep.py", "scoreboard.py"):
    m = re.search(r"^SCORED_STATUSES = (\(.*?\))", open(sys.argv[1] + "/" + f).read(), re.M)
    out.append(m.group(1) if m else "MISSING:" + f)
print(len(set(out)), out[1])
PY
)
check "scoreboard.py and score_sweep.py carry one scored-status set ($SCSETS)" [ "${SCSETS%% *}" = 1 ]

# MUTANTS, run on a copy in a scratch directory over the collected column.
sc_mut() {  # sc_mut NAME SED -> path of the mutant, empty if the sed matched nothing
    mkdir -p "$SC/mut/$1"
    sed "$2" "$TESTING/scoreboard.py" > "$SC/mut/$1/scoreboard.py"
    cmp -s "$TESTING/scoreboard.py" "$SC/mut/$1/scoreboard.py" || echo "$SC/mut/$1/scoreboard.py"
}
sc_run() { python3 "$1" --run "fix=$SC/board/fix" --goldens "$SC/goldens" --md "$SC/mut/out.md" >/dev/null 2>&1; sc_row "$SC/mut/out.md"; }
SCM=$(sc_mut unreadable-exact 's|^SCORED_STATUSES = ("ok",|SCORED_STATUSES = ("unreadable", "ok",|')
if [ -z "$SCM" ]; then bad "MUTANT unreadable-as-exact: the sed matched nothing"
else
    SCMR=$(sc_run "$SCM")
    case "$SCMR" in *"| 2/4 · 26 · 2 void |"*) bad "MUTANT unreadable-as-exact: the check stayed green ($SCMR)" ;;
                    *"| 3/5 "*) ok "MUTANT unreadable-as-exact goes red: $SCMR" ;;
                    *) bad "MUTANT unreadable-as-exact: unexpected row '$SCMR'" ;; esac
fi
SCM=$(sc_mut drop-void 's|^    void = f" · {a\[.void.\]} void" if a.get("void") else ""|    void = ""|')
if [ -z "$SCM" ]; then bad "MUTANT drop-void-count: the sed matched nothing"
else
    SCMR=$(sc_run "$SCM")
    case "$SCMR" in *" 2 void |"*) bad "MUTANT drop-void-count: the check stayed green ($SCMR)" ;;
                    *"| 2/4 · 26 |"*) ok "MUTANT drop-void-count goes red: $SCMR" ;;
                    *) bad "MUTANT drop-void-count: unexpected row '$SCMR'" ;; esac
fi
