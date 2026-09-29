#!/usr/bin/env bash
# Queue lane.forzadecay414's three Nova Forza soaks (NOTES section 5). Run from
# the worktree root. A is shared by both predictions: it is queued under the
# bisect file; the master arm names the master file.
set -u
R=docs/testing/request.sh
FORZA='4D53006E-Forza_Motorsport.xiso.iso'
q() { # ref prediction purpose
    env HAKUX_RELEASE_PRIO=1 "$R" --who forzadecay414 --device nova --ref "$1" \
        --title "$FORZA" --route survey --seconds 360 --perflog \
        --expect "docs/testing/predictions/$2" --purpose "#414 decay: $3"
}
q f82e7e87fe forzadecay414-bisect.json "arm A, master before #517 (also A of forzadecay414-master), Nova, perflog"
q 09050ddbe5 forzadecay414-bisect.json "arm B, the #517 fold, Nova, perflog"
q 85347ffbd1 forzadecay414-master.json "arm B, master 85347ffbd1, Nova, perflog"
