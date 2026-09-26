#!/bin/sh
# Does brdf315b-psh.diff apply on top of each open PR that holds psh.c?
# Usage: sh overlap.sh PR...   (run from the worktree root)
set -u
DIFF=docs/lanes/brdf315b/brdf315b-psh.diff
SRC=hw/xbox/nv2a/pgraph/glsl/psh.c
for p in "$@"; do
    git fetch -q origin "refs/pull/$p/head:refs/remotes/pr/$p" || continue
    echo "== PR $p head $(git rev-parse --short "pr/$p")"
    git diff --stat "origin/master...pr/$p" -- "$SRC"
    git diff "origin/master...pr/$p" -- "$SRC" | grep -n 'stage_consumed_raw\|BRDF\|tex_bytes16' | head
    tmp=$(mktemp -d)
    git show "pr/$p:$SRC" > "$tmp/psh.c"
    if patch --dry-run -s "$tmp/psh.c" "$DIFF" > "$tmp/out" 2>&1; then
        echo "patch applies on PR $p's psh.c"
    else
        echo "patch does NOT apply on PR $p's psh.c:"; cat "$tmp/out"
    fi
    rm -rf "$tmp"
done
