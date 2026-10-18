#!/usr/bin/env bash
#
# dispatchdoctor1017 Section 2 -- the owner's "it should have sonnet
# reasoning ... troubleshoot and resolve launch failures" (2026-10-17
# ~06:50 PDT). Called by dispatcher.sh's maybe_run_doctor() right before a
# claimed run would end in ERROR from a class a script cannot classify its
# way out of.
#
#   dispatch_doctor.sh classify <rdir>          -> a class name, or exit 1
#   dispatch_doctor.sh gate <label>              -> admit, or "refuse: ..."
#   dispatch_doctor.sh cap <id> <rdir>           -> ok, or "refuse: ..."
#   dispatch_doctor.sh fix push-iso <rdir>       -> ensure_title_staged
#   dispatch_doctor.sh fix attach-route <rdir>   -> ensure_route_attached
#   dispatch_doctor.sh fix restore-profile <rdir>-> ensure_profile_restored
#   dispatch_doctor.sh diagnose <id> <rdir>      -> runs the model, writes
#                                                    doctor.md, prints
#                                                    "VERDICT retry" or
#                                                    "VERDICT give-up: ..."
#
# diagnose is the only one dispatcher.sh calls; classify/gate/cap/fix are
# split out so the selftest (and the model itself, through `fix`) can drive
# each on its own. diagnose never touches the queue -- it decides and
# writes doctor.md; the caller (maybe_run_doctor) requeues on a `retry`
# verdict, the same split as battery_admit.py/jq_get: this script decides,
# the caller acts.
#
# Sources dispatcher.sh for its helpers (jq_get, battery_level, dev_push,
# dev_pull, ensure_title_staged, ensure_route_attached, ensure_profile_restored,
# staging_roots, staging_find_tid, TITLESTATE, SAVES_PY, TITLESTATE_DIR, D) --
# the same fixture idiom 98-dispatch-doctor.sh already uses to test Section
# 1/1b/1c (`. dispatcher.sh selftest-not-a-subcommand`): sourcing with an
# unmatched first argument runs every top-level line (device_env, mkdir -p
# $D/{queue,running,results,logs}) but falls through the final case to its
# `sed -n '3,12p' "$0"` no-op, never `serve` or `status`.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOBS="$HERE/jobs"
. "$HERE/dispatcher.sh" dispatch-doctor-source-only >/dev/null 2>&1

TSV="$D/logs/dispatch-doctor.tsv"
LESSONS="$D/doctor-lessons.md"
mkdir -p "$(dirname "$TSV")"

cmd="${1:?usage: dispatch_doctor.sh classify|gate|cap|fix|diagnose ...}"; shift

# dd_classify <rdir> -> one of the brief's named recoverable classes on
# stdout, exit 0; exit 1 (nothing printed) when the ERROR is not one of
# them, so the caller spends no model turn on a class nobody taught this
# script to recognise (a build failure, a release-apk refusal, ...).
#
# Order matters: the WSL UtilAcceptVsock interop signature is checked
# first, per the brief ("check first for the ... signature, which the
# dispatcher already recognises") -- dispatcher.sh's own one-shot requeue
# (line ~2826) already fires on the FIRST sighting and never reaches this
# script at all (it returns 0 before adb_error runs); what reaches here
# with that signature is always the SECOND, final one, "this was the one
# requeue, so it is final" -- a class the doctor should recognise and give
# up on, not retry into a second loss.
dd_classify() {
    local rdir="$1" err=""
    [ -f "$rdir/ERROR" ] && err=$(head -1 "$rdir/ERROR")
    case "$err" in
        *"this was the one requeue, so it is final"*)
            echo zero-captures-interop-exhausted; return 0 ;;
        # Anywhere in the line, not a prefix: Section 3 puts what staging
        # found ahead of device_title_miss's own text, and history before
        # this lane carries that text bare ("title not on device: ...").
        *"title not on device"*)
            echo title-not-on-device; return 0 ;;
        "install failed"*)
            echo install-failed; return 0 ;;
        *"could not prepare the titles disk"*)
            echo titles-disk-failed; return 0 ;;
        *"could not set the requested env_vars pref"*)
            echo env-vars-failed; return 0 ;;
        "0 captures:"*)
            # dispatcher.sh already found the crash signature itself (grep
            # "emulator started and CRASHED" on run*.log) and folded it into
            # this message -- no logcat lookup needed, it IS the crash case.
            echo zero-captures-crash; return 0 ;;
        "ran but produced 0 captures"*)
            if grep -qm1 -iE "FATAL EXCEPTION|ANR in" "$rdir/logcat.txt" 2>/dev/null; then
                echo zero-captures-crash
            else
                echo zero-captures
            fi
            return 0 ;;
    esac
    return 1
}

# dd_owner_playing: the release package (no .debug suffix) is on this
# device's process list. guard_not_release_apk already draws exactly this
# line for installs (the dispatcher may only install a debug-suffixed
# build); the owner's own release build is what ES-DE launches when they
# attach to play (owner-play-attach-never-launch), so a running release
# process that the dispatcher never installed can only be the owner's.
# "pidof <pkg>:xemu matches nothing, use ps -A -o NAME | grep -x" (AGENTS.md
# hard-won fact) -- same grep here.
dd_owner_playing() {
    adb_call "${ADB_QUICK_TIMEOUT:-30}" "owner-play check" shell ps -A -o NAME 2>/dev/null \
        | tr -d '\r' | grep -qx 'com\.jreinach\.hakux:xemu'
}

# dd_gate <label> -> "admit", or "refuse: <reason>" (stdout either way).
# Three refusals, in the brief's order: a hold (which is also how a Halo
# priority window is expressed in this codebase today -- there is no
# separate Halo-priority marker; see NOTES.md), owner-play, and battery
# below the admit floor. Reads FLOOR_BY_LABEL/FLOOR/MARGIN out of
# battery_admit.py as a library (not edited, not duplicated) rather than
# re-deriving the policy -- that file is outside this lane's territory.
# Anything uncertain (hold file half-written, battery unreadable, the
# import itself failing) FAILS CLOSED: the doctor is a best-effort extra,
# never worth admitting on a guess the way a real run sometimes must be.
dd_gate() {
    local label="$1" why lvl floor
    if [ -e "$D/hold/$label" ]; then
        why=$(cat "$D/hold/$label.why" 2>/dev/null)
        echo "refuse: device held${why:+: $why}"
        return 1
    fi
    if dd_owner_playing; then
        echo "refuse: owner is playing ($label is running the release package)"
        return 1
    fi
    lvl=$(battery_level)
    if [ -z "$lvl" ]; then
        echo "refuse: battery level unreadable; failing closed"
        return 1
    fi
    floor=$(python3 -c '
import sys
sys.path.insert(0, sys.argv[2])
import battery_admit as ba
print(ba.FLOOR_BY_LABEL.get(sys.argv[1], ba.FLOOR) + ba.MARGIN)
' "$label" "$HERE" 2>/dev/null)
    if [ -z "$floor" ]; then
        echo "refuse: could not read the admit floor; failing closed"
        return 1
    fi
    if python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) < float(sys.argv[2]) else 1)" "$lvl" "$floor"; then
        echo "refuse: battery $lvl% is below the admit floor ($floor%) on $label"
        return 1
    fi
    echo admit
}

# dd_cap <id> <rdir> -> "ok", or "refuse: <reason>". Two independent caps,
# both read from logs/dispatch-doctor.tsv (time, request id, class,
# verdict, seconds -- one row per doctor session that actually ran):
#   hourly   at most N (DISPATCH_DOCTOR_HOURLY_CAP, default 3) sessions in
#            any trailing hour, so a dead device cannot spin the meter.
#   per-id   at most one doctor session per request id. A `retry` verdict
#            requeues the SAME id (maybe_run_doctor in dispatcher.sh, same
#            idiom as the existing one-shot WSL-interop requeue -- never a
#            new id), so a request that failed the doctor's fix once gets
#            no second session on the retry: the id already has a row.
dd_cap() {
    local id="$1" rdir="$2" now cutoff hourly maxn
    now=$(date +%s); cutoff=$((now - 3600))
    hourly=$(awk -F'\t' -v c="$cutoff" '$1+0 >= c {n++} END{print n+0}' "$TSV" 2>/dev/null)
    maxn="${DISPATCH_DOCTOR_HOURLY_CAP:-3}"
    if [ "${hourly:-0}" -ge "$maxn" ]; then
        echo "refuse: $hourly doctor session(s) already in the last hour (cap $maxn)"
        return 1
    fi
    if awk -F'\t' -v r="$id" '$2==r{f=1} END{exit !f}' "$TSV" 2>/dev/null; then
        echo "refuse: request $id already used its one doctor attempt"
        return 1
    fi
    echo ok
}

# dd_req_field <rdir> <field> [<default>]
dd_req_field() { jq_get "$1/request.json" "$2" "${3:-}" 2>/dev/null; }

# fix push-iso <rdir>: Section 1's own fast path, by hand, for a title the
# claim already tried and missed. ensure_title_staged does the sha-sidecar
# lookup, the floor/make_room_for_push dance and the dev_push; this just
# supplies its three arguments from the failed request sitting in rdir.
dd_fix_push_iso() {
    local rdir="$1" title
    title=$(dd_req_field "$rdir" title "")
    [ -n "$title" ] || { echo "fix push-iso: request names no title"; return 1; }
    if ensure_title_staged "$title" "$rdir" "$rdir/request.json"; then
        echo "fix push-iso: pushed $title"
        return 0
    fi
    echo "fix push-iso: $title not pushed -- $(sed -n 's/^disc: NOT STAGED: //p' "$rdir/inputs.txt" 2>/dev/null | tail -1)"
    return 1
}

# fix attach-route <rdir>: Section 1b, by hand. Mutates rdir/request.json
# in place exactly as the live claim path does -- a later retry built from
# this file inherits the attached route the same way a user's own --route
# would have been inherited.
dd_fix_attach_route() {
    local rdir="$1" ttid title
    title=$(dd_req_field "$rdir" title "")
    ttid=$(dd_req_field "$rdir" title_id "")
    [ -n "$ttid" ] || ttid=$(python3 "$TITLESTATE" tid-for-iso "$title" 2>/dev/null)
    [ -n "$ttid" ] || { echo "fix attach-route: no title_id for $title"; return 1; }
    if ! ensure_route_attached "$ttid" "$title" "$rdir" "$rdir/request.json"; then
        echo "fix attach-route: refused, $(cat "$rdir/route.refused" 2>/dev/null) -- a route lane's to repair, not a retry"
        return 1
    fi
    local now; now=$(dd_req_field "$rdir" route_name "")
    if [ -n "$now" ] && [ "$now" != survey ]; then
        echo "fix attach-route: attached '$now' for $ttid"
        return 0
    fi
    echo "fix attach-route: no proven or recorded route resolves for $ttid; leaving it on survey"
    return 1
}

# fix restore-profile <rdir>: Section 1c, by hand. Promotes a found backup
# to this title's FIRST golden only (ensure_profile_restored never passes
# --replace); writes rdir/profile-backup.json naming where it looked either
# way, which dd_build_brief already surfaces to the model before this runs.
dd_fix_restore_profile() {
    local rdir="$1" ttid title tstate
    title=$(dd_req_field "$rdir" title "")
    ttid=$(dd_req_field "$rdir" title_id "")
    [ -n "$ttid" ] || ttid=$(python3 "$TITLESTATE" tid-for-iso "$title" 2>/dev/null)
    tstate=$(dd_req_field "$rdir" title_state any)
    [ -n "$ttid" ] || { echo "fix restore-profile: no title_id for $title"; return 1; }
    ensure_profile_restored "$ttid" "$tstate" "$rdir" "$rdir/request.json"
    local restored
    restored=$(python3 -c '
import json, sys
try:
    print("1" if json.load(open(sys.argv[1])).get("restored") else "")
except Exception:
    print("")
' "$rdir/profile-backup.json" 2>/dev/null)
    if [ -n "$restored" ]; then
        echo "fix restore-profile: restored a backup as $ttid's first golden"
        return 0
    fi
    echo "fix restore-profile: $(cat "$rdir/profile-backup.json" 2>/dev/null || echo "no backup found for $ttid")"
    return 1
}

dd_fix() {
    local action="$1" rdir="$2"
    case "$action" in
        push-iso)        dd_fix_push_iso "$rdir" ;;
        attach-route)    dd_fix_attach_route "$rdir" ;;
        restore-profile) dd_fix_restore_profile "$rdir" ;;
        *) echo "fix: unknown action '$action' (push-iso, attach-route, restore-profile)"; return 2 ;;
    esac
}

# dd_build_brief <id> <rdir> <cls>: a read-only snapshot written once, before
# the model starts, so the model needs no live adb access to see the result
# dir, the device state or the staging/profile inventory the brief
# requires. Trimmed to what each class could plausibly need, not every file
# every time -- a doctor session is billed.
dd_build_brief() {
    local id="$1" rdir="$2" cls="$3" ttid title
    title=$(dd_req_field "$rdir" title "")
    ttid=$(dd_req_field "$rdir" title_id "")
    [ -n "$ttid" ] || ttid=$(python3 "$TITLESTATE" tid-for-iso "$title" 2>/dev/null)
    cat <<EOF
# dispatch doctor brief -- request $id, class $cls

You are diagnosing one failed hakuX dispatch request. Read the material
below, decide whether one of the three available fixes applies, run it
if so, then write a verdict to \`$rdir/doctor.md\`.

## What failed

Class: $cls
Title: ${title:-"(none -- not a title soak)"}
TitleID: ${ttid:-"(unknown)"}
Result dir: $rdir

### request.json
\`\`\`
$(cat "$rdir/request.json" 2>/dev/null)
\`\`\`

### ERROR
\`\`\`
$(cat "$rdir/ERROR" 2>/dev/null)
\`\`\`

### inputs.txt (what the claim found and did for the disc, the route, the profile)
\`\`\`
$(cat "$rdir/inputs.txt" 2>/dev/null || echo "(none written: the claim ended before its title steps)")
$(for f in console-stage.result room.log route.refused; do [ -f "$rdir/$f" ] && echo "-- $f --" && cat "$rdir/$f"; done)
\`\`\`

### run.log (tail)
\`\`\`
$(tail -n 40 "$rdir"/run*.log 2>/dev/null)
\`\`\`

### dispatcher.log (lines naming this request)
\`\`\`
$(grep -F "$id" "$D/logs/dispatcher.log" 2>/dev/null | tail -n 40)
\`\`\`

### logcat.txt (tail)
\`\`\`
$(tail -n 60 "$rdir/logcat.txt" 2>/dev/null)
\`\`\`

### route.txt (recorded route this run was given, if any)
\`\`\`
$(cat "$rdir/route.txt" 2>/dev/null)
\`\`\`
route_name on the request: $(dd_req_field "$rdir" route_name "(none)")

### profile-backup.json (Section 1c's own search, if it ran)
\`\`\`
$(cat "$rdir/profile-backup.json" 2>/dev/null || echo "(did not run, or the title already had a golden)")
\`\`\`

### hdd.json / hdd.plan / hdd.refused / hdd.verify.json
\`\`\`
$(for f in hdd.json hdd.plan hdd.refused hdd.verify.json; do [ -f "$rdir/$f" ] && echo "-- $f --" && cat "$rdir/$f"; done)
\`\`\`

### this title's recorded/proven route (titlestate.py suggest-route)
\`\`\`
$([ -n "$ttid" ] && python3 "$TITLESTATE" suggest-route --title-id "$ttid" 2>&1)
\`\`\`

### this title's backup candidates (titlestate.py backup-candidates)
\`\`\`
$([ -n "$ttid" ] && python3 "$TITLESTATE" backup-candidates --title-id "$ttid" --json 2>&1)
\`\`\`

### staging roots and whether this title is on one of them
\`\`\`
$(staging_roots 2>/dev/null)
$([ -n "$ttid" ] && echo "staging_find_tid $ttid -> $(staging_find_tid "$ttid" 2>&1)")
\`\`\`

## The fixes available to you (and only these)

Run with: \`bash $HERE/dispatch_doctor.sh fix <action> $rdir\`

- \`push-iso\`         -- the title's disc image is on a staging root but not
  on the device; stages and pushes it.
- \`attach-route\`      -- the title has a proven or recorded route this
  request did not carry (it ran on \`survey\` or no route at all); attaches it.
- \`restore-profile\`   -- the title has a findable backup that is not yet
  this title's golden; promotes it (never replaces an existing golden).

Pick AT MOST ONE, the one the evidence above actually supports. Do not run
a fix the evidence does not support, and do not run more than one -- if two
look plausible, say so in doctor.md and give up; a later session with a
narrower question can retry.

## What you may NOT do

Inject input to a running emulator, force-stop or launch any app, clear app
data, uninstall anything, change a profile or golden other than through
\`restore-profile\` above, touch Halo's queue priority, or run anything
outside the allowed tools. You have no direct adb access by design: every
fact you need is already above, and the only actions you may take are the
three named here.

## Writing \`doctor.md\`

End the file with exactly one of these two lines, the LAST line:

    retry
    give-up: <one sentence, the reason>

\`retry\` means: you ran a fix above and it reported success. The dispatcher
requeues this same request once; it never fixes a no-progress run by
repeating it unchanged, so \`retry\` with no fix applied is not a valid verdict.
Before that line, say in a few sentences what failed, what (if anything) you
tried, and why.
EOF
}

# dd_append_lesson <cls> <verdict>: one line per failure class and the fix
# that worked (or the reason it did not), so the NEXT doctor session reads
# this file first instead of re-deriving the same answer from the same
# evidence. The brief: "The fixes that repeat get promoted into the
# deterministic fast path by a later lane; this file is how you find them."
dd_append_lesson() {
    local cls="$1" verdict="$2"
    [ -f "$LESSONS" ] || cat > "$LESSONS" <<'EOF'
# dispatch doctor lessons

One line per doctor session: the failure class, the verdict, and (on a
retry) which fix it ran. Read this file first; a class that keeps needing
the same fix belongs in the deterministic fast path (Section 1/1b/1c), not
in a model session every time.
EOF
    printf -- '- %s UTC %s -> %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$cls" "$verdict" >> "$LESSONS"
}

# dd_diagnose <id> <rdir>: the one entry point dispatcher.sh calls.
dd_diagnose() {
    local id="$1" rdir="$2" cls gr cr model t0 log secs verdict
    cls=$(dd_classify "$rdir") || { echo "VERDICT give-up: not a class the doctor recognises"; return 0; }
    gr=$(dd_gate "${DEVICE_LABEL:-}")
    if [ "$gr" != admit ]; then
        printf '%s: the doctor did not run -- %s\n' "$cls" "$gr" > "$rdir/doctor.md"
        echo "VERDICT give-up: $gr"
        return 0
    fi
    cr=$(dd_cap "$id" "$rdir")
    if [ "$cr" != ok ]; then
        printf '%s: the doctor did not run -- %s\n' "$cls" "$cr" > "$rdir/doctor.md"
        echo "VERDICT give-up: $cr"
        return 0
    fi
    local brief="$rdir/doctor-brief.md"
    dd_build_brief "$id" "$rdir" "$cls" > "$brief"
    model="${HAKUX_MODEL:-$(bash "$JOBS/models.sh" model dispatchdoctor)}"
    log="$D/logs/dispatch-doctor/$id.json"
    mkdir -p "$(dirname "$log")"
    . "$JOBS/window.sh"
    t0=$(date +%s)
    HAKUX_ROLE=dispatchdoctor HAKUX_BRIEF="$brief" \
    timeout "${DOCTOR_TIMEOUT:-10m}" claude -p "$(cat "$brief")" \
        --model "$model" \
        --max-turns "${DOCTOR_TURNS:-12}" \
        --output-format json \
        --permission-mode acceptEdits \
        --allowedTools "$(cat "$JOBS/allowed-tools.doctor")" \
        --append-system-prompt-file "$JOBS/roles/dispatchdoctor.md" \
        > "$log" 2>&1
    secs=$(( $(date +%s) - t0 ))
    # A closed account window is not evidence about this failure at all; say
    # so, record it the same way run-claude-job.sh does, and give up WITHOUT
    # spending one of the hourly/chain caps' slots on a session that never
    # got to look (dd_cap already wrote its one allowed row for this id, so
    # the TSV append below still happens -- the cap is "one doctor attempt
    # per request", and a window-blocked attempt is still the one attempt).
    if window_limit_hit "$log"; then
        window_note_limit dispatchdoctor "$log"
        verdict="give-up: hit the account's usage window (exit 75), not this failure"
        printf '%s: the doctor did not finish -- %s\n' "$cls" "$verdict" > "$rdir/doctor.md"
        printf '%s\t%s\t%s\t%s\t%s\n' "$t0" "$id" "$cls" "$verdict" "$secs" >> "$TSV"
        dd_append_lesson "$cls" "$verdict"
        echo "VERDICT $verdict"
        return 0
    fi
    verdict=""
    [ -f "$rdir/doctor.md" ] && verdict=$(grep -oE '^(retry|give-up:.*)$' "$rdir/doctor.md" | tail -1)
    if [ -z "$verdict" ] && grep -q '"subtype": *"error_max_turns"' "$log" 2>/dev/null; then
        verdict="give-up: hit the turn cap (--max-turns ${DOCTOR_TURNS:-12}) before writing a verdict"
    fi
    [ -n "$verdict" ] || verdict="give-up: the doctor session wrote no doctor.md verdict line"
    printf '%s\t%s\t%s\t%s\t%s\n' "$t0" "$id" "$cls" "$verdict" "$secs" >> "$TSV"
    dd_append_lesson "$cls" "$verdict"
    echo "VERDICT $verdict"
}

case "$cmd" in
    classify) dd_classify "$1" ;;
    gate)     dd_gate "$1" ;;
    cap)      dd_cap "$1" "$2" ;;
    fix)      dd_fix "$1" "$2" ;;
    diagnose) dd_diagnose "$1" "$2" ;;
    *) echo "usage: dispatch_doctor.sh classify|gate|cap|fix|diagnose ..." >&2; exit 2 ;;
esac
