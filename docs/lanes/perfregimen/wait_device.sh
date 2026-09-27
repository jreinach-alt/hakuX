#!/usr/bin/env bash
# Poll until a handheld can be held for the session: the Thor at >= 51%
# battery, or the Nova's hold (another lane's) gone and its battery >= 51%.
# Prints the first label that qualifies, or nothing after MAX_S seconds.
D="${DISPATCH_DIR:-$HOME/hakux-work/dispatch}"
end=$(( $(date +%s) + ${MAX_S:-540} ))
lvl() { timeout 20 adb -s "$1" shell dumpsys battery 2>/dev/null | tr -d '\r' | sed -n 's/^ *level: //p'; }
while [ "$(date +%s)" -lt "$end" ]; do
    t=$(lvl bdc158a5); n=$(lvl ee317437)
    held=""; [ -f "$D/hold/nova" ] && held="nova-held"
    echo "$(date +%H:%M:%S) thor=${t:-?}% nova=${n:-?}% $held" >&2
    [ "${t:-0}" -ge 51 ] && { echo thor; exit 0; }
    [ -z "$held" ] && [ "${n:-0}" -ge 51 ] && { echo nova; exit 0; }
    sleep 60
done
exit 1
