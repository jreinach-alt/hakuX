#!/usr/bin/env bash
# Queue the fix's Nova soaks (NOTES section 6). Run from the worktree root.
#   queue_fix.sh forza   B of forzadecay414-fix-forza.json (A is the queued master arm, -3394871)
#   queue_fix.sh auf     both arms of forzadecay414-fix-auf.json (past the 30-min pilot line:
#                        only after pilots/forzadecay414.ok is written from the first soaks)
# The pixel file needs nothing here: the arms job queues it.
set -u
R=docs/testing/request.sh
q() { # ref prediction title seconds purpose
    env HAKUX_RELEASE_PRIO=1 "$R" --who forzadecay414 --device nova --ref "$1" \
        --title "$3" --route survey --seconds "$4" --perflog \
        --expect "docs/testing/predictions/$2" --purpose "#414 fix: $5"
}
FORZA='4D53006E-Forza_Motorsport.xiso.iso'
AUF='4541000D-007_Agent_Under_Fire.xiso.iso'
case "${1:-}" in
    forza) q 10fe2f59a7 forzadecay414-fix-forza.json "$FORZA" 360 "Forza arm B, the fix, Nova, perflog" ;;
    auf)
        q 85347ffbd1 forzadecay414-fix-auf.json "$AUF" 420 "AUF arm A, master, Nova, perflog"
        q 10fe2f59a7 forzadecay414-fix-auf.json "$AUF" 420 "AUF arm B, the fix, Nova, perflog" ;;
    *) echo "usage: $0 forza|auf" >&2; exit 2 ;;
esac
