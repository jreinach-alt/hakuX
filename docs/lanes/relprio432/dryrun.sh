#!/usr/bin/env bash
# Name two requests with request.sh, without and with HAKUX_RELEASE_PRIO, into
# a scratch queue that no dispatcher serves. Proves the naming; queues nothing.
#   bash docs/lanes/relprio432/dryrun.sh
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
S="$(mktemp -d "$ROOT/.relprio-dry.XXXXXX")"
trap 'rm -rf "$S"' EXIT
mkdir -p "$S/queue"
for v in "" 1; do
    echo "--- HAKUX_RELEASE_PRIO='$v'"
    HAKUX_RELEASE_PRIO="$v" DISPATCH_DIR="$S" DISPATCH_TREE="$ROOT" \
        bash "$ROOT/docs/testing/request.sh" --who relprio-dry --suites "Blend surface" \
        --no-expect "naming dry run into a scratch queue" --purpose "relprio432 naming dry run" 2>/dev/null
    echo "exit $?"
done
echo "--- scratch queue in the dispatcher's glob order (LC_ALL=C)"
( cd "$S/queue" && LC_ALL=C; for f in *.req; do echo "$f"; done )
