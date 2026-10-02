#!/usr/bin/env bash
# lane.ibcache (#507): read one env A/B leg end to end.
# Usage: readleg.sh <name> <request id> ...
# Writes out/{soakread,headread,idleread,legtable}-<name>.out and prints the table.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
name=$1; shift
o="$here/out"
python3 "$here/soakread.py" "$@" > "$o/soakread-$name.out"
python3 "$here/headread.py" "$@" > "$o/headread-$name.out"
python3 "$here/idleread.py" "$@" > "$o/idleread-$name.out"
python3 "$here/legtable.py" "$o/soakread-$name.out" "$o/headread-$name.out" \
    "$o/idleread-$name.out" > "$o/legtable-$name.out"
cat "$o/legtable-$name.out"
