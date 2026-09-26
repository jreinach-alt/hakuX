#!/usr/bin/env bash
# launch_session.sh <label> <outdir> [title]: run held_session.sh under
# systemd-run --user, so it outlives the tool call that started it.
# Output in <outdir>/session.out. Unit name perfregimen-<label>.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
mkdir -p "$2"; out="$(cd "$2" && pwd)"
systemd-run --user --unit="perfregimen-$1" --collect \
    --setenv=PATH="$PATH" --setenv=HOME="$HOME" \
    --setenv=ARMS="${ARMS:-rest max rest}" --setenv=SKIP_IDLE="${SKIP_IDLE:-0}" \
    --setenv=PILOT_TITLE="${3:-4D530013-Blinx_The_Time_Sweeper.xiso.iso}" \
    --working-directory="$repo" \
    bash -c "exec bash '$here/held_session.sh' '$1' '$out' > '$out/session.out' 2>&1"
