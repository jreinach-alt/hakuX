# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# dispatcher deploy: the re-exec trigger must cover everything the snapshot
# ships, or an edit to the rest never reaches a running worker.

echo "== dispatch deploy: src_hash covers every file snapshot_scripts ships"
# WHY. A worker runs from $SNAP, and the ONLY thing that refreshes $SNAP is
# the worker re-execing itself when src_hash changes. src_hash hashes
# $SCRIPT_DEPS; snapshot_scripts copies its own list. Those were different
# sets: four files against nine.
#
# So affinity.py, devices.sh, captures.py, make_test_iso.py and
# extract_results.py could each be edited, committed and folded without
# moving the hash. No worker re-execed, so no worker re-snapshotted, so every
# worker kept executing the copy that was in $SNAP when it last restarted.
#
# That is not a hypothetical. 37af3f02fe changed affinity.py to keep handheld
# work off the desktop lane. The running workers never saw it and kept a
# 09-19 copy that pinned every queued A/B to `desktop` -- a lane no
# dispatcher worker serves. serve_one skips a pin that is not its own, and it
# does so silently by design, so both handhelds passed over those requests on
# every tick and logged nothing. Four arms sat unclaimed, the oldest for
# eighteen hours, with two healthy devices idle, while the arms job refused
# to queue more at ARMS_QUEUE_MAX=4.
#
# lane_blind_check cannot catch that: it fires only when NO lane is
# registered, and `desktop` is registered.
#
# The invariant is one line -- the two sets are the same set -- and nothing
# asserted it. This does.
export DD="$T/deploy"; mkdir -p "$DD"
dep_env() {   # run shell inside a sourced dispatcher.sh, against a scratch dir
    ( export DISPATCH_DIR="$DD" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$1" )
}

# `declare -f` normalises the body onto one line per statement, so this parse
# survives however the list is wrapped in the source.
DEPS=$(dep_env 'printf "%s\n" $SCRIPT_DEPS' | LC_ALL=C sort -u | tr '\n' ' ')
SNAPPED=$(dep_env 'declare -f snapshot_scripts' \
          | sed -n 's/^[[:space:]]*for f in \(.*\);[[:space:]]*$/\1/p' \
          | tr ' ' '\n' | grep -v '^$' | LC_ALL=C sort -u | tr '\n' ' ')

# BOTH LISTS MUST BE NON-EMPTY FIRST. A parse that silently yields nothing
# would make the equality below true forever, which is the failure mode this
# whole fragment exists to prevent -- a check that is green because it is
# looking at nothing.
check "SCRIPT_DEPS parsed non-empty"            test -n "$DEPS"
check "snapshot_scripts list parsed non-empty"  test -n "$SNAPPED"
# And an anchor member, so a parse that yields one stray token is not enough.
case " $DEPS " in    *" dispatcher.sh "*) ok "SCRIPT_DEPS contains dispatcher.sh" ;;
                     *) bad "SCRIPT_DEPS contains dispatcher.sh -- parsed: $DEPS" ;; esac
case " $SNAPPED " in *" dispatcher.sh "*) ok "snapshot_scripts ships dispatcher.sh" ;;
                     *) bad "snapshot_scripts ships dispatcher.sh -- parsed: $SNAPPED" ;; esac

if [ "$DEPS" = "$SNAPPED" ]; then
    ok "src_hash covers exactly what snapshot_scripts ships ($(printf '%s' "$DEPS" | wc -w) files)"
else
    bad "src_hash and snapshot_scripts disagree -- a change to the difference never reaches a worker"
    echo "       hashed:   $DEPS"
    echo "       shipped:  $SNAPPED"
    echo "       only shipped (edits to these deploy silently late): $(comm -13 <(printf '%s\n' $DEPS | sort -u) <(printf '%s\n' $SNAPPED | sort -u) | tr '\n' ' ')"
    echo "       only hashed (harmless, but the lists have drifted):  $(comm -23 <(printf '%s\n' $DEPS | sort -u) <(printf '%s\n' $SNAPPED | sort -u) | tr '\n' ' ')"
fi

# Every shipped file must actually exist in $SRC, or the cp is a silent no-op
# and the worker keeps a stale copy of THAT file for the same reason.
for f in $SNAPPED; do
    check "snapshot source exists: $f" test -f "$TESTING/$f"
done

echo "== dispatch deploy: the snapshot is closed under what its scripts run"
# WHY. Equality of the two lists is not the invariant the deploy needs (audit
# pass 1 on #206, M2). A worker execs $SNAP/dispatcher.sh, so $HERE IS $SNAP
# for everything it runs, and a sibling that is not copied there does not
# exist. preempt_sweep ran `bash "$HERE/sweep_queue.sh" pause`, which was in
# neither list: exit 127, nothing checked it, and the sweep was never parked
# before the dispatcher installed over its device. The check above was green
# the whole time, because both lists agreed on leaving it out.
#
# So: every sibling a shipped file runs from its own directory must be
# shipped. The four ways they do it here: $HERE/x (or $SNAP/x), the inline
# `$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/x` that soak_title.sh and
# run_disc.sh source devices.sh through, os.path.join(HERE, "x") in Python,
# and a Python import, which resolves against the script's own directory.
# Only names of files that exist beside the scripts count; a comment naming
# one counts too, which errs towards shipping more.
unshipped() {   # <dir> <shipped...> -> "<ref> <- <file>" for each sibling left out
    python3 - "$@" <<'PY'
import os, re, sys
d, shipped = sys.argv[1], set(sys.argv[2:])
ref = re.compile(r'''(?:\$\{?(?:HERE|SNAP)\}?"?/|pwd\)"?/|os\.path\.join\(\s*HERE\s*,\s*["'])([A-Za-z0-9_.-]+\.(?:sh|py))''')
imp = re.compile(r'^\s*(?:import|from)\s+([A-Za-z_]\w*)', re.M)
for f in sorted(shipped):
    try:
        text = open(os.path.join(d, f), errors="replace").read()
    except OSError:
        continue
    found = {m.group(1) for m in ref.finditer(text)} | \
            {m.group(1) + ".py" for m in imp.finditer(text)}
    for r in sorted(found - shipped - {f}):
        if os.path.isfile(os.path.join(d, r)):
            print("%s <- %s" % (r, f))
PY
}
gap=$(unshipped "$TESTING" $SNAPPED)
if [ -z "$gap" ]; then
    ok "every sibling a shipped script runs is shipped ($(printf '%s' "$SNAPPED" | wc -w) files)"
else
    bad "a shipped script runs a sibling the snapshot does not carry -- in a worker it does not exist:"
    printf '%s\n' "$gap" | sed 's/^/       /'
fi
# The check must be able to fail, once per form it claims to read. Each
# mutant is a copy of the shipped files with one reference appended to its
# dispatcher.sh, pointing at an EMPTY placeholder: the copies are only read,
# never run, and there is nothing in the placeholder to run if they were.
DM="$T/deploy-mutant"
for form in '$HERE/probe_only.sh' \
            '$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/probe_only.sh' \
            'os.path.join(HERE, "probe_only.py")' \
            'import probe_only'; do
    rm -rf "$DM"; mkdir -p "$DM"
    for f in $SNAPPED; do cp "$TESTING/$f" "$DM/$f" 2>/dev/null; done
    : > "$DM/probe_only.sh"; : > "$DM/probe_only.py"
    printf '\n%s\n' "$form" >> "$DM/dispatcher.sh"
    case "$(unshipped "$DM" $SNAPPED)" in
        *"probe_only."*" <- dispatcher.sh"*) ok "the closure check sees a sibling run as: $form" ;;
        *) bad "the closure check is BLIND to a sibling run as: $form" ;;
    esac
done
rm -rf "$DM"
unset DD DM gap
