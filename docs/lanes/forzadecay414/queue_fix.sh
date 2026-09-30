#!/usr/bin/env bash
# Queue the fix's Nova soaks (NOTES section 6). Run from the worktree root.
#   queue_fix.sh forza   B of forzadecay414-fix-forza.json (A is the queued master arm, -3394871)
#   queue_fix.sh forza2  B of forzadecay414-fix-forza2.json (A is hostops' re-run of the master
#                        arm, -3394871-r4)
#   queue_fix.sh auf     both arms of forzadecay414-fix-auf.json (past the 30-min pilot line:
#                        only after pilots/forzadecay414.ok is written from the first soaks)
#   queue_fix.sh forza3  forzadecay414-fix-forza3.json: the merged head, Nova, 420 s (B only)
#   queue_fix.sh pixels3 both arms of forzadecay414-fix-pixels3.json, hard-pinned to the Nova. The
#                        arms job queued pixels and pixels2 itself; it queues nothing while GitHub
#                        is unreachable, and its same-device re-run of pixels2 found no device.
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
    forza2) q 10fe2f59a7 forzadecay414-fix-forza2.json "$FORZA" 360 "Forza arm B, the fix, second run under the re-cut legs, Nova, perflog" ;;
    auf)
        q 85347ffbd1 forzadecay414-fix-auf.json "$AUF" 420 "AUF arm A, master, Nova, perflog"
        q 10fe2f59a7 forzadecay414-fix-auf.json "$AUF" 420 "AUF arm B, the fix, Nova, perflog" ;;
    forza3) q eec025dd37 forzadecay414-fix-forza3.json "$FORZA" 420 "Forza, the fix on master 146b8887db, full window, Nova, perflog" ;;
    pixels3)
        P=docs/testing/predictions/forzadecay414-fix-pixels3.json
        SU=$(python3 -c 'import json,sys; print(",".join(json.load(open(sys.argv[1]))["disc"]["suites"]))' "$P")
        for arm in "base 146b8887db" "fix eec025dd37"; do
            set -- $arm
            env HAKUX_RELEASE_PRIO=1 "$R" --who "arms-forzadecay414-$1" --ref "$2" --suites "$SU" \
                --skip-tests Texture_render_target::RenderTextureLoop --device nova --hard-pin --runs 2 \
                --expect "$P" --purpose "#414 fix-pixels3 ${1^^} arm at $2, Nova-only pair, queued by lane.forzadecay414"
        done ;;
    *) echo "usage: $0 forza|forza2|auf|forza3|pixels3" >&2; exit 2 ;;
esac
