#!/bin/bash
# Post a comment to the cross-session PR and record its id.
#
# Both sessions post under the same GitHub account, so a watch on the thread
# cannot tell an incoming comment from one it just wrote. It reports every new
# comment whose id is not in the seen file; this script puts its own id there
# on the way out. Excluding by id fails open -- a missed id costs a duplicate
# notification, never a missed comment.
#
#   pr_comment.sh <body-file> [pr-number]
set -euo pipefail
BODY="${1:?usage: pr_comment.sh <body-file> [pr]}"
PR="${2:-45}"
REPO="${PR_REPO:-jreinach-alt/hakuX}"
SEEN="${PR_SEEN_FILE:-/home/justin/hakux-work/pr45-mine.txt}"

url=$(gh pr comment "$PR" --repo "$REPO" --body-file "$BODY")
echo "$url"
id="${url##*-}"
if [[ "$id" =~ ^[0-9]+$ ]]; then
    mkdir -p "$(dirname "$SEEN")"
    echo "$id" >> "$SEEN"
    echo "recorded id $id in $SEEN"
else
    echo "WARNING: could not parse a comment id from '$url'." >&2
    echo "The watch will report this comment back as if it were the remote lane's." >&2
fi
