#!/usr/bin/env bash
# lane.ibcache (#507): re-queue after the 2026-09-29 16:23-16:29 PDT dispatch
# wipe, which removed every queued .req (no copy survived). Same refs, device,
# lengths and env as the lost requests; Alien Hominid added now that its Nova
# copy is listed.
set -u
here=$(cd "$(dirname "$0")" && pwd)
C="Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso"
bash "$here/queue_leg4.sh" nova 360 BAB crimson-skies "$C" "Crimson Skies"
bash "$here/queue_jcsize.sh" a987e375db:14 9808982fa7:16
bash "$here/queue_leg4.sh" nova 360 BAAB alien-hominid 5A440004-Alien_Hominid.xiso.iso "Alien Hominid"
