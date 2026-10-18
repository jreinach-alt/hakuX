#!/bin/bash
# Desktop legs across the cut, one after another (#1039). Each leg is
# desk_route.py's r4b recipe (aim by the engine glow, 300 frames, gd, zrep)
# with one switch changed. C: is checked before each leg (>= 40 GB free, the
# brief's rule: a desktop segfault writes ~7.8 GB to wsl-crashes) and the
# crash directory listed after it.
#
# usage: legs.sh OUTROOT NAME=ENV[,ENV...] ...   e.g. e0=HAKUX_REPORT_EARLY=0
here=$(dirname "$(readlink -f "$0")")
root=$1
shift
crash=/mnt/c/Users/Justin/AppData/Local/Temp/wsl-crashes
for leg in "$@"; do
    name=${leg%%=*}
    envs=${leg#*=}
    free=$(df -B1G --output=avail /mnt/c | tail -1 | tr -d ' ')
    echo "LEG $name env $envs C: ${free} GB free $(date +%T)"
    if [ "$free" -lt 40 ]; then
        echo "LEG $name SKIPPED: C: under 40 GB"
        continue
    fi
    python3 "$here/desk_route.py" "$root/$name" --total 1500 \
        --on-bright 0.045 300,images,gd,cap3000 --every 2 --cine 900 --zrep \
        ${envs//,/ }
    echo "LEG $name exit $? $(date +%T)"
    echo "LEG $name crashes: $(ls -1 "$crash" | tr '\n' ' ')"
done
echo "LEGS DONE $(date +%T)"
