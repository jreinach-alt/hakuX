#!/bin/bash
# Dry run of capture_gta.sh's regime detector: replay a logcat line by line
# from the mark on (as the live log grows) and report when it fires.
# dryregime.sh <logcat> <mark regex> [SLOW_GFPS]
LC=$1 MARK=$2 SLOW_GFPS=${3:-8}
m=$(grep -n -m1 -- "$MARK" "$LC" | cut -d: -f1)
[ -n "$m" ] || { echo "no mark"; exit 1; }
total=$(wc -l < "$LC")
T=$(mktemp); head -n "$m" "$LC" > "$T"
n0=$(wc -l < "$T")
for k in $(seq $((m + 1)) "$total"); do
    sed -n "${k}p" "$LC" >> "$T"
    case "$(sed -n "${k}p" "$LC")" in *hakuX-perf*gfps=*) ;; *) continue ;; esac
    slow=$(tail -n +$((n0 + 1)) "$T" | grep 'hakuX-perf.*gfps=' | sed 's/.*gfps=\([0-9]*\).*/\1/' | tail -2 | tr '\n' ' ')
    set -- $slow
    if [ $# = 2 ] && [ "$1" -le "$SLOW_GFPS" ] && [ "$2" -le "$SLOW_GFPS" ]; then
        echo "fires at line $k: gfps $slow: $(sed -n "${k}p" "$LC" | cut -c1-18)"; rm -f "$T"; exit 0
    fi
done
echo "never fires (mark at line $m, $total lines)"; rm -f "$T"
