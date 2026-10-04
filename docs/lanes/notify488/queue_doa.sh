#!/bin/sh
# Queue the DOA A/B of docs/testing/predictions/notify488-doa-ab.json in its
# registered order, A1 B1 A2 B2, pinned to the Nova.
cd "$(dirname "$0")/../../.." || exit 1
A=dffb7a8a66
B=9f80bc887a
for arm in A1:$A B1:$B A2:$A B2:$B; do
    name=${arm%%:*}
    ref=${arm#*:}
    env HAKUX_RELEASE_PRIO=1 docs/testing/request.sh --who notify488 \
        --title 54430006-Dead_or_Alive_1_Ultimate.xiso.iso --device nova \
        --route survey --seconds 300 --perflog --ref "$ref" \
        --no-expect "hand-read soak arm $name of docs/testing/predictions/notify488-doa-ab.json; owner priority #488" \
        --purpose "owner priority #488: DOA A/B arm $name (A=master+counter, B=NOTIFY+semaphore without download); gfps and the sem_release counter" \
        2>&1 | tail -3
done
