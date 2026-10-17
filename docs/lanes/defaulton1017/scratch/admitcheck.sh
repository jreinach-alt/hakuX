#!/bin/bash
# Ask the profile gate (titlestate.py admit, as request.sh calls it) whether each
# screen row would be admitted on the Nova. Read-only: admit decides, it queues nothing.
W=/home/justin/hakux-work/wt/defaulton1017
export TITLESTATE_DIR=/home/justin/hakux-work/dispatch/titlestate
a() {
    local id=$1 route=$2 dir=$3
    echo "== $id $route"
    TITLE_ROUTES="$dir" python3 "$W/docs/testing/titles/titlestate.py" admit --title-id "$id" --route "$route" --device nova 2>&1 | head -c 600
    echo
}
cd "$W" || exit 1
a 4D530004 halo-cinematic docs/lanes/halo1016/routes
a 4D570029 fps1015-mksm docs/lanes/fps1015/routes
a 4D530035 fps1015-topspin docs/lanes/fps1015/routes
a 4541007B nfs-mw-quickrace docs/testing/titles/routes
a 4D53000F rallisport-804g docs/lanes/accuracy804
a 4D530002 fuzion-frenzy docs/testing/titles/routes
a 56550015 simpsons-hit-run docs/testing/titles/routes
a 4D530041 amped2 docs/testing/titles/routes
