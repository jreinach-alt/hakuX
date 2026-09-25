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

# ------------------------------------------- the unscoreable list (#295/#296)
echo "== sweep cover: an unscoreable golden is out of the denominator, by name"
# Fog gains a seventh golden, `zz`, that the fixture list calls unscoreable.
# The cell's goldens figure must be 6 (+1 unscoreable), not 7.
: > "$SC/goldens/Fog/zz.png"
printf '{"unscoreable":{"Fog":{"tests":["zz"],"reason":"fixture"}},"not_captured_by_design":{"Nothing_saved":{"tests":3,"reason":"fixture"}}}\n' > "$SC/unscoreable.json"
sc_un() { python3 "$1" --run "fix=$SC/board/fix" --goldens "$SC/goldens" --unscoreable "$SC/unscoreable.json" --md "$SC/un.md" >/dev/null 2>&1; sc_row "$SC/un.md"; }
SCU=$(sc_un "$TESTING/scoreboard.py")
case "$SCU" in *"| 6 (+1 unscoreable) |"*) ok "goldens is 6 (+1 unscoreable): $SCU" ;;
               *) bad "the unscoreable golden is still in the denominator: '$SCU'" ;; esac
check "the not-captured-by-design suite is named" grep -q 'not captured by design: `Nothing_saved` (3 tests)' "$SC/un.md"
SCM=$(sc_mut ignore-list 's|^                dead = unscoreable.get(s, set())|                dead = set()|')
if [ -z "$SCM" ]; then bad "MUTANT ignore-unscoreable: the sed matched nothing"
else
    SCMR=$(sc_un "$SCM")
    case "$SCMR" in *"| 7 |"*) ok "MUTANT ignore-unscoreable goes red: $SCMR" ;;
                    *) bad "MUTANT ignore-unscoreable: expected goldens 7, got '$SCMR'" ;; esac
fi
rm -f "$SC/goldens/Fog/zz.png"
# The committed list: 20 goldens (#295) and two by-design suites (#296).
SCN=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(sum(len(e["tests"]) for e in d["unscoreable"].values()), sorted(d["not_captured_by_design"]))' "$TESTING/unscoreable_goldens.json" 2>&1)
check "unscoreable_goldens.json holds the 20 goldens and Clipping_precision, PVIDEO ($SCN)" \
    [ "$SCN" = "20 ['Clipping_precision', 'PVIDEO']" ]

# ---------------------------------------------------- queue_full_sweep.sh
echo "== sweep cover: queue_full_sweep resolves a tag to a commit and queues its legs apart"
SQ="$SC/q"
mkdir -p "$SQ/repo" "$SQ/goldens/Fog" "$SQ/goldens/Texture_render_target"
: > "$SQ/depth.iso"; : > "$SQ/inter.iso"; : > "$SQ/base6743.iso"
git -C "$SQ/repo" init -q && git -C "$SQ/repo" -c user.name=t -c user.email=t@t commit -q --allow-empty -m one \
    && git -C "$SQ/repo" -c user.name=t -c user.email=t@t tag -a v1 -m tag
SQC=$(git -C "$SQ/repo" rev-parse --short 'v1^{commit}' 2>/dev/null)
SQT=$(git -C "$SQ/repo" rev-parse --short v1 2>/dev/null)
check "fixture: the annotated tag's object differs from its commit ($SQT vs $SQC)" \
    bash -c '[ -n "$1" ] && [ "$1" != "$2" ]' _ "$SQC" "$SQT"
sq_run() {  # sq_run SCRIPT DISPATCH_DIR ARGS... (in the fixture repo)
    local s=$1 d=$2; shift 2
    (cd "$SQ/repo" && DISPATCH_DIR="$d" GOLDENS="$SQ/goldens" DEPTH2025_ISO="$SQ/depth.iso" \
        INTERACTIVE_ISO="$SQ/inter.iso" bash "$s" "$@") 2>&1
}
sq_ref() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["ref"])' "$1" 2>/dev/null; }
sq_leg() {  # sq_leg FILE -> "suite|only|base_iso|arm"
    python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); print("|".join([",".join(r["suites"]), ",".join(r.get("only_tests") or []), r.get("base_iso",""), r["arm"]]))' "$1" 2>&1
}
sq_run "$TESTING/queue_full_sweep.sh" "$SQ/d1" --with-depth-2025 --with-blend-interactive --with-rtloop v1 fix >/dev/null
check "main sweep queued one request per golden suite" \
    bash -c '[ -f "$1/z-fix-001-Fog.req" ] && [ -f "$1/z-fix-002-Texture_render_target.req" ]' _ "$SQ/d1/queue"
check "the request's ref is the tag's COMMIT ($SQC), not the tag object ($SQT)" \
    [ "$(sq_ref "$SQ/d1/queue/z-fix-001-Fog.req")" = "$SQC" ]
check "depth leg: Depth buffer on the v2025-03-14 disc, its own label" \
    [ "$(sq_leg "$SQ/d1/queue/z-fix.depth2025-001-Depth_buffer.req")" = "Depth buffer||$SQ/depth.iso|fix.depth2025" ]
check "blend leg: Blend tests on the interactive disc, its own label" \
    [ "$(sq_leg "$SQ/d1/queue/z-fix.blend-interactive-001-Blend_tests.req")" = "Blend tests||$SQ/inter.iso|fix.blend-interactive" ]
check "rtloop leg: only RenderTextureLoop, stock disc, its own label" \
    [ "$(sq_leg "$SQ/d1/queue/z-fix.rtloop-001-Texture_render_target.req")" = "Texture render target|Texture render target::RenderTextureLoop||fix.rtloop" ]
sq_run "$TESTING/queue_full_sweep.sh" "$SQ/d2" v1 fix >/dev/null
check "without flags: exactly the 2 main requests, no leg" [ "$(ls "$SQ/d2/queue" | wc -l)" = 2 ]
sq_run "$TESTING/queue_full_sweep.sh" "$SQ/d3" --base-iso "$SQ/base6743.iso" v1 >/dev/null
check "--base-iso: the main request names the disc, and so does the default label" \
    [ "$(sq_leg "$SQ/d3/queue/z-$SQC-iso-base6743-001-Fog.req")" = "Fog||$SQ/base6743.iso|$SQC-iso-base6743" ]
sq_run "$TESTING/queue_full_sweep.sh" "$SQ/d4" --base-iso "$SQ/nope.iso" v1 fix >/dev/null
check "--base-iso on a missing disc is refused and queues nothing" [ ! -d "$SQ/d4/queue" ]
sq_run "$TESTING/queue_full_sweep.sh" "$SQ/d5" v1 fix.leg >/dev/null
check "a '.' in a label is refused (reserved for legs)" [ ! -d "$SQ/d5/queue" ]
# MUTANT: the bare ref, as before defect 12b moved here.
mkdir -p "$SQ/mut"
sed 's|"\$REF^{commit}"|"$REF"|' "$TESTING/queue_full_sweep.sh" > "$SQ/mut/queue_full_sweep.sh"
if cmp -s "$TESTING/queue_full_sweep.sh" "$SQ/mut/queue_full_sweep.sh"; then bad "MUTANT bare-ref: the sed matched nothing"
else
    sq_run "$SQ/mut/queue_full_sweep.sh" "$SQ/dm" v1 fix >/dev/null
    SQM=$(sq_ref "$SQ/dm/queue/z-fix-001-Fog.req")
    case "$SQM" in "$SQC") bad "MUTANT bare-ref: still the commit ($SQM); the check cannot go red" ;;
                   "$SQT") ok "MUTANT bare-ref goes red: the request names the tag object $SQM" ;;
                   *) bad "MUTANT bare-ref: unexpected ref '$SQM'" ;; esac
fi

# collect_sweep takes `z-<label>-NNN-*` only: a leg, and a sweep whose label
# merely starts with this one, stay out of the column.
for x in z-fix.depth2025-001-Depth_buffer z-fix-now-001-Fog; do
    mkdir -p "$SC/dispatch/results/$x"
    cp "$SC/dispatch/results/z-fix-001-Fog/scores1.tsv" "$SC/dispatch/results/z-fix-001-Fog/result.json" "$SC/dispatch/results/$x/"
done
SCO=$(SCOREBOARD_ROOT="$SC/board" SCOREBOARD_GOLDENS="$SC/goldens" SCOREBOARD_MD="$SC/SB.md" \
      bash "$TESTING/collect_sweep.sh" fix "$SC/dispatch" 2>&1)
check "collect_sweep fix takes 1 sheet, not the leg or fix-now ($(printf '%s' "$SCO" | grep -m1 '^collected'))" \
    bash -c '[ "$(ls "$1"/*.tsv | wc -l)" = 1 ]' _ "$SC/board/fix"
