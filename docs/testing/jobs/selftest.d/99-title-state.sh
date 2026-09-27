# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# route.sh's `flush`: a first-run's profile reaches the disk only if the app
# flushes before the soak's force-stop. The step backgrounds the app with a
# HOME intent (never `input keyevent`, which exits it) and waits for the
# app's own `deferred bdrv_flush_all completed`, stamped on the DEVICE clock
# at or after the request. A fake adb answers from a scenario file.

echo "== route.sh: flush backgrounds the app and waits for its flush line"
RF="$T/routeflush"; rm -rf "$RF"; mkdir -p "$RF/bin"
cat > "$RF/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$RF_FAKE/calls"
case "$*" in
    "shell date +%s") echo 1790550000 ;;
    *"am start -a android.intent.action.MAIN -c android.intent.category.HOME"*)
        echo "Starting: Intent { act=android.intent.action.MAIN cat=[android.intent.category.HOME] }" ;;
    *"logcat -d -v epoch -s hakuX:I"*)
        n=$(cat "$RF_FAKE/n" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$RF_FAKE/n"
        # scenario: `<from-poll> <epoch>` -- the flush line appears from that
        # poll on, stamped at that epoch. An empty scenario never flushes.
        read -r from at < "$RF_FAKE/scenario"
        echo "1790549000.100  812  812 I hakuX   : android: app entering background, flush requested"
        echo "1790549000.300  812  900 I hakuX   : deferred bdrv_flush_all completed"
        if [ -n "${from:-}" ] && [ "$n" -ge "$from" ]; then
            echo "$at  812  900 I hakuX   : deferred bdrv_flush_all completed"
        fi ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$RF/bin/adb"
printf 'wait 0\nflush 3\nwait 0\n' > "$RF/f.route"
flush_run() {   # <scenario line> -> route.sh stdout
    rm -f "$RF/n" "$RF/calls"; printf '%s\n' "$1" > "$RF/scenario"
    PATH="$RF/bin:$PATH" RF_FAKE="$RF" SERIAL=x PAD_DEV=/dev/input/event9 \
        ROUTE_FRAMES="$RF/frames" timeout 30 bash "$TESTING/titles/route.sh" "$RF/f.route" 2>&1
}
fr=$(flush_run "2 1790550001.250")
case "$fr" in *"flush: bdrv_flush_all completed after 1s"*) ok "a flush line after the request, on the second poll, is waited for and accepted" ;;
              *) bad "the flush was not confirmed: $(printf '%s' "$fr" | grep flush | tr '\n' '|')" ;; esac
grep -qx "shell am start -a android.intent.action.MAIN -c android.intent.category.HOME" "$RF/calls" \
    && ok "flush sends the HOME intent" || bad "flush did not send the HOME intent"
grep -q "input keyevent" "$RF/calls" && bad "flush sent an input keyevent (it exits the app)" \
    || ok "flush sends no input keyevent"
# The impossible row: the buffer already holds a flush line from an EARLIER
# background (1790549000, before the request's 1790550000). It must not count.
fr=$(flush_run "")
case "$fr" in *"flush NOT confirmed"*) ok "a flush line older than the request is not taken for this flush" ;;
              *) bad "a stale flush line was accepted: $(printf '%s' "$fr" | grep flush | tr '\n' '|')" ;; esac
[ "$(cat "$RF/n" 2>/dev/null)" = 4 ] && ok "an unconfirmed flush polls for its timeout (4 polls over 3 s), no longer" \
    || bad "an unconfirmed flush polled $(cat "$RF/n" 2>/dev/null) times, not 4"
case "$fr" in *"ROUTE "*" done"*) ok "an unconfirmed flush does not stop the route" ;;
              *) bad "the route stopped at an unconfirmed flush" ;; esac
rm -rf "$RF"
