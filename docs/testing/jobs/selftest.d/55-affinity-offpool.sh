# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, and ok/bad/check. Not executable, no shebang,
# no exit -- `fail` is shared and is the run's verdict.
#
# The desktop channel is an execution target that is NOT a handheld, and the
# scheduler must never choose it.
#
# WHY. affinity.py rule 3 hashes an unpinned A/B pair over `serving()`, which
# is every lane with a live pid in $D/lanes/. The desktop worker registers
# there like any other, so the moment it exists the modulus goes from 2 to 3
# and ONE UNPINNED PAIR IN THREE lands on OpenGL/llvmpipe instead of the
# Adreno. The failure has no symptom at any stage: the hash is deterministic,
# so BOTH arms go together and the pair is never split; the run completes; the
# captures are scored against goldens produced by the Adreno Vulkan path; and
# every capture that differs for renderer reasons reads as a defect the arm
# introduced. Nothing between the queue and the report would have said a word.
#
# So: rule 1 (an explicit `device` field) is the only route onto the desktop,
# and these checks are what says so. The routing check below FAILS against the
# affinity.py this replaces -- it hashed over all three lanes.

echo "== affinity/devices: the desktop channel is off-pool and reachable only by name"
export OP="$T/offpool"; mkdir -p "$OP"/{lanes,running,results,splits}
OPAFF="$TESTING/affinity.py"; OPDEV="$TESTING/devices.sh"
sleep 600 & OPLIVE=$!                       # a pid that is certainly alive
printf '%s\n' "$OPLIVE" > "$OP/lanes/nova"
printf '%s\n' "$OPLIVE" > "$OP/lanes/thor"
printf '%s\n' "$OPLIVE" > "$OP/lanes/desktop"

# --- the label registry. `desktop` has no adb serial, so it has no row in the
# serial-keyed table and no regex over that table can find it; devices.sh has
# to enumerate it. Both of these fail against the old file, which had no
# `labels` subcommand at all.
check "devices.sh labels lists the two handhelds and the desktop" \
    [ "$(bash "$OPDEV" labels | sort | tr '\n' ' ')" = "desktop nova thor " ]
check "devices.sh pool lists ONLY the handhelds" \
    [ "$(bash "$OPDEV" pool | sort | tr '\n' ' ')" = "nova thor " ]

# --- rule 3. Sixty distinct prediction keys, none of which names a sibling,
# so every one of them reaches the hash. Counted rather than spot-checked: a
# single key that happens to miss the desktop proves nothing about a modulus.
opr() {  # affinity's answer for a request with no `device` field
    printf '{"requester":"r","expect":"/p/%s.json"}\n' "$1" > "$OP/q.req"
    python3 "$OPAFF" "$OP" "$OP/q.req" 2>/dev/null
}
opdesk=0; opnova=0; opthor=0; opother=0
for i in $(seq 0 59); do
    case "$(opr "k$i")" in
        desktop) opdesk=$((opdesk+1)) ;;
        nova)    opnova=$((opnova+1)) ;;
        thor)    opthor=$((opthor+1)) ;;
        *)       opother=$((opother+1)) ;;
    esac
done
check "rule 3 sends NO unpinned pair to the desktop (0 of 60)" [ "$opdesk" -eq 0 ]
# The instrument has to be able to see a desktop answer at all, or the check
# above is satisfied by affinity printing nothing for every key -- which is
# what a broken pool, an empty lanes/ or a crashed script all look like. These
# two say the 60 keys really were routed, and routed to BOTH handhelds.
check "and it did route them: every one of the 60 went to a handheld" \
    [ "$((opnova + opthor))" -eq 60 ]
check "over both handhelds, not all to one" \
    [ "$opnova" -gt 0 -a "$opthor" -gt 0 ]

# --- the two ways in that must still work. CONTROLS: both pass against the
# old file too, and are here to show the fix did not buy its safety by making
# the desktop unreachable.
printf '{"requester":"r","device":"desktop","expect":"/p/e1.json"}\n' > "$OP/q.req"
check "CONTROL: rule 1, an explicit --device desktop, is honoured" \
    [ "$(python3 "$OPAFF" "$OP" "$OP/q.req" 2>/dev/null)" = "desktop" ]
mkdir -p "$OP/results/r-desk"
printf '{"expect":"/p/e2.json"}\n'      > "$OP/results/r-desk/request.json"
printf '{"device_label":"desktop"}\n'   > "$OP/results/r-desk/result.json"
printf '{"requester":"r","expect":"/p/e2.json"}\n' > "$OP/q.req"
check "CONTROL: rule 2 still follows a sibling that actually ran on the desktop" \
    [ "$(python3 "$OPAFF" "$OP" "$OP/q.req" 2>/dev/null)" = "desktop" ]

# --- --serving still reports the desktop lane as alive. The pool shrank; the
# roll-up's view of who is up must not, or a live channel reads as down.
check "--serving still shows all three lanes" \
    [ "$(python3 "$OPAFF" "$OP" --serving 2>/dev/null | wc -w)" = 3 ]
check "--serving-pooled shows the two the scheduler may choose" \
    [ "$(python3 "$OPAFF" "$OP" --serving-pooled 2>/dev/null)" = "nova thor" ]

# --- the duplication. affinity.py carries OFFPOOL as a constant because the
# scheduler runs on every claim and must not depend on reading a file; that is
# a defensible choice only while something checks the two still agree.
#
# EQUALITY ALONE IS NOT THE CHECK. Written as `[ "$a" = "$b" ]` this passed
# against the pre-lane code, where affinity has no OFFPOOL and devices.sh has
# no `offpool`: both sides errored to the empty string and compared equal. So
# assert the contents as well -- a check two absences satisfy has measured
# nothing.
OPAFFSET="$(python3 -c "
import sys; sys.path.insert(0, '$TESTING')
import affinity; print(' '.join(sorted(affinity.OFFPOOL)))" 2>/dev/null)"
OPDEVSET="$(bash "$OPDEV" offpool 2>/dev/null | sort | tr '\n' ' ' | sed 's/ $//')"
check "affinity.OFFPOOL names the desktop" [ "$OPAFFSET" = "desktop" ]
check "devices.sh offpool names the desktop" [ "$OPDEVSET" = "desktop" ]
check "and the two have not drifted apart" [ "$OPAFFSET" = "$OPDEVSET" ]

# --- request.sh's gate, at queue time. A misspelt label is refused (it always
# was); `desktop` must NOT be, and the discriminator is the message rather than
# the exit code, because this invocation is incomplete on purpose and exits
# non-zero either way.
#
# The substring tests are FUNCTIONS CALLED BY `check`, not `bash -c '[[ ... ]]'`.
# A child shell does not inherit `opreq`, so a negative written that way is
# green against absolutely anything -- including against the very code it is
# supposed to fail on.
opreq() { ( export DISPATCH_DIR="$OP/disp"; mkdir -p "$OP/disp"/{queue,running,results,expect}
            bash "$TESTING/request.sh" --who selftest --suites Clear --device "$1" 2>&1 ) }
ophas()  { case "$2" in *"$1"*) return 0;; *) return 1;; esac; }
opnot()  { case "$2" in *"$1"*) return 1;; *) return 0;; esac; }
OPBAD="$(opreq desktopp)"; OPOK="$(opreq desktop)"
check "request.sh refuses a misspelt device label" \
    ophas "unknown --device" "$OPBAD"
check "request.sh does NOT refuse --device desktop at the device gate" \
    opnot "unknown --device" "$OPOK"
# ... and got far enough to prove it was the device gate it passed, rather
# than dying earlier for an unrelated reason. Both invocations are incomplete
# on purpose, so the exit code cannot tell these two apart.
check "request.sh carries --device desktop through to the expect gate" \
    ophas "needs --expect" "$OPOK"

kill "$OPLIVE" 2>/dev/null; wait "$OPLIVE" 2>/dev/null
unset OP OPAFF OPDEV OPLIVE OPBAD OPOK OPAFFSET OPDEVSET
unset opdesk opnova opthor opother
unset -f opr ophas opnot opreq
