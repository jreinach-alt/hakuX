#!/usr/bin/env bash
# lane.ibcache jcsize pilot (#507): Crimson Skies on the Nova, probe on, one run
# per jump-cache size. Legs: docs/lanes/ibcache/NOTES.md, "The jcsize pilot".
# Usage: queue_jcsize.sh <ref>:<bits> ...
set -u
here=$(cd "$(dirname "$0")" && pwd)
req="$here/../../testing/request.sh"
iso="Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso"
NE="jcsize pilot, hand-read against the registered legs in docs/lanes/ibcache/NOTES.md"
for p in "$@"; do
    R=${p%%:*} B=${p##*:}
    bash "$req" --who lane.ibcache --device nova --ref "$R" --title "$iso" \
        --route crimson-skies --seconds 360 --perflog --issue 507 \
        --purpose "#507 lane.ibcache jcsize pilot: Crimson Skies, probe on, TB_JMP_CACHE_BITS $B at $R" \
        --no-expect "$NE"
done
