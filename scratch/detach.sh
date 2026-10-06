#!/usr/bin/env bash
# detach.sh <log> <cmd...>: run a command in its own session, output to <log>, and return at once.
log=$1; shift
setsid nohup "$@" > "$log" 2>&1 < /dev/null &
echo "detached pid $!"
