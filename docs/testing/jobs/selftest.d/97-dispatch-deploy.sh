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
#
# A REFERENCE RESOLVES AGAINST THE DIRECTORY OF THE FILE THAT MAKES IT, and x
# may be a path (titles/route.sh, ../perf/pad.sh). This used to read every
# reference against docs/testing/ and only as a bare name, so titles/route.sh
# running $HERE/drive.py and titles/classify.py importing waitfor_match
# looked for docs/testing/drive.py and docs/testing/waitfor_match.py, found
# nothing, and passed -- while no worker could run a `drive` step (#433,
# lane.snapdrive).
#
# And a DIRECTORY a script picks a file from by a variable --
# "$HERE/drive-profiles/${w[1]}.toml" -- ships whole, because which file is
# read is decided by a route nobody has written yet. A selftest/ directory
# under it is fixtures and does not ship.
SHIPPED_ALL="$SNAPPED $(dep_env 'snapshot_globbed' | tr '\n' ' ')"
unshipped() {   # <dir> <shipped...> -> "<ref> <- <file>" for each sibling left out
    python3 - "$@" <<'PY'
import os, re, sys
d, shipped = sys.argv[1], set(sys.argv[2:])
name = r'((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:sh|py))'
ref = re.compile(r'''(?:\$\{?(?:HERE|SNAP)\}?"?/|pwd\)"?/|os\.path\.join\(\s*HERE\s*,\s*["'])''' + name)
dref = re.compile(r'''\$\{?(?:HERE|SNAP)\}?"?/((?:[A-Za-z0-9_-][A-Za-z0-9_.-]*/)+)\$''')
imp = re.compile(r'^\s*(?:import|from)\s+([A-Za-z_]\w*)', re.M)
for f in sorted(shipped):
    if not f.endswith((".sh", ".py")):
        continue
    base = os.path.dirname(f)
    try:
        text = open(os.path.join(d, f), errors="replace").read()
    except OSError:
        continue
    found = {os.path.normpath(os.path.join(base, m.group(1))) for m in ref.finditer(text)} | \
            {os.path.normpath(os.path.join(base, m.group(1) + ".py")) for m in imp.finditer(text)}
    for r in sorted(found - shipped - {f}):
        if os.path.isfile(os.path.join(d, r)):
            print("%s <- %s" % (r, f))
    for sub in sorted({os.path.normpath(os.path.join(base, m.group(1))) for m in dref.finditer(text)}):
        for root, dirs, files in os.walk(os.path.join(d, sub)):
            dirs[:] = sorted(x for x in dirs if x not in ("selftest", "__pycache__"))
            for fn in sorted(files):
                r = os.path.relpath(os.path.join(root, fn), d)
                if r not in shipped:
                    print("%s <- %s (directory %s/)" % (r, f, sub))
PY
}
gap=$(unshipped "$TESTING" $SHIPPED_ALL)
if [ -z "$gap" ]; then
    ok "every sibling a shipped script runs is shipped ($(printf '%s' "$SHIPPED_ALL" | wc -w) files)"
else
    bad "a shipped script runs a sibling the snapshot does not carry -- in a worker it does not exist:"
    printf '%s\n' "$gap" | sed 's/^/       /'
fi
# The profiles are in that set, so the check above is looking at them.
case " $SHIPPED_ALL " in
    *" titles/drive-profiles/sonic-heroes.toml "*" titles/drive-profiles/sonic-heroes/hud.png "*)
        ok "the shipped set holds the drive profiles and their crops" ;;
    *) bad "the shipped set holds no drive profile -- snapshot_globbed gave: $(dep_env 'snapshot_globbed' | head -3 | tr '\n' ' ')" ;;
esac
case " $SHIPPED_ALL " in
    *"/selftest/"*) bad "the shipped set carries drive-profiles/selftest/ fixtures" ;;
    *) ok "  and nothing under drive-profiles/selftest/ (fixtures)" ;;
esac
# The check must be able to fail, once per form it claims to read. Each
# mutant is a copy of the shipped files with one reference appended to one of
# them, pointing at an EMPTY placeholder: the copies are only read, never
# run, and there is nothing in the placeholder to run if they were.
DM="$T/deploy-mutant"
mut_copy() {
    local f
    rm -rf "$DM"; mkdir -p "$DM"
    for f in $SHIPPED_ALL; do mkdir -p "$DM/$(dirname "$f")"; cp "$TESTING/$f" "$DM/$f" 2>/dev/null; done
}
for form in '$HERE/probe_only.sh' \
            '$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/probe_only.sh' \
            'os.path.join(HERE, "probe_only.py")' \
            'import probe_only'; do
    mut_copy
    : > "$DM/probe_only.sh"; : > "$DM/probe_only.py"
    printf '\n%s\n' "$form" >> "$DM/dispatcher.sh"
    case "$(unshipped "$DM" $SHIPPED_ALL)" in
        *"probe_only."*" <- dispatcher.sh"*) ok "the closure check sees a sibling run as: $form" ;;
        *) bad "the closure check is BLIND to a sibling run as: $form" ;;
    esac
done
# In a subdirectory, against that subdirectory: the two forms the drive step
# uses (route.sh's $HERE/drive.py, classify.py's import of waitfor_match).
for form in '$HERE/probe_only.sh' 'from probe_only import X'; do
    mut_copy
    : > "$DM/titles/probe_only.sh"; : > "$DM/titles/probe_only.py"
    printf '\n%s\n' "$form" >> "$DM/titles/classify.py"
    case "$(unshipped "$DM" $SHIPPED_ALL)" in
        *"titles/probe_only."*" <- titles/classify.py"*) ok "the closure check sees a subdirectory sibling run as: $form" ;;
        *) bad "the closure check is BLIND to a subdirectory sibling run as: $form" ;;
    esac
done
# A file in the directory route.sh picks profiles from that is not shipped
# (what a profile outside the globs would be), and one under selftest/, which
# must not be asked for.
mut_copy
mkdir -p "$DM/titles/drive-profiles/probe" "$DM/titles/drive-profiles/selftest"
: > "$DM/titles/drive-profiles/probe/crop.png"; : > "$DM/titles/drive-profiles/selftest/fixture.jpg"
got=$(unshipped "$DM" $SHIPPED_ALL)
case "$got" in
    *"titles/drive-profiles/probe/crop.png <- titles/route.sh"*)
        ok "the closure check sees an unshipped file in the directory route.sh picks profiles from" ;;
    *) bad "the closure check is BLIND to an unshipped file in drive-profiles/: $got" ;;
esac
case "$got" in
    *fixture.jpg*) bad "the closure check asks for drive-profiles/selftest/ fixtures to ship" ;;
    *) ok "  and leaves drive-profiles/selftest/ fixtures out" ;;
esac
# And on the real tree, the two members the drive step was missing: drop one
# from the shipped set and the check must name it and who needs it.
got=$(unshipped "$TESTING" $(printf '%s\n' $SHIPPED_ALL | grep -vx 'titles/waitfor_match.py'))
case "$got" in
    *"titles/waitfor_match.py <- titles/classify.py"*) ok "unshipped waitfor_match.py is caught as classify.py's import" ;;
    *) bad "unshipped waitfor_match.py was not caught as classify.py's import: $got" ;;
esac
got=$(unshipped "$TESTING" $(printf '%s\n' $SHIPPED_ALL | grep -vx 'titles/drive-profiles/sonic-heroes.toml'))
case "$got" in
    *"titles/drive-profiles/sonic-heroes.toml <- titles/route.sh"*) ok "an unshipped profile is caught as route.sh's" ;;
    *) bad "an unshipped profile was not caught: $got" ;;
esac
rm -rf "$DM"
unset DD DM gap got SHIPPED_ALL
