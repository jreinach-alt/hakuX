#!/usr/bin/env bash
#
#   queue_full_sweep.sh <ref> [label]
#
# Queue one idle-priority request per golden suite, so the whole corpus is
# scored against one binary.
#
# Why this is a script and not a loop someone types
# -------------------------------------------------
#
# The sweep is the campaign's headline measurement and it is easy to get
# subtly wrong. On 2026-09-12 the collected column turned out to have been
# built from a binary 22 -- then 31, then 35 -- commits behind the tip as the
# day's fixes landed, and it was labelled `today-partial`. Every row carried a
# consistent `apk_sha`, so the existing mixed-binary warning saw nothing:
# consistency is not currency. The column read as though the day's work had
# achieved nothing.
#
# So the ref is a REQUIRED argument and is resolved to a concrete sha here.
# `HEAD` in a queued request is a moving target -- the queue is served later,
# and a sweep that takes hours would otherwise span several binaries while
# every row claimed to be one.
#
# The `z-` prefix is load-bearing. The dispatcher serves its queue in filename
# order, so `z-*` sorts after every epoch-prefixed request and the sweep is
# pre-empted by any agent measurement. That is the whole reason a full sweep
# can run during active work instead of blocking it.
#
# Requests are written directly rather than through request.sh, because
# request.sh names its requests by epoch and they would jump the queue. They
# carry `no_expect` for the same reason request.sh demands it: a sweep is a
# survey, not an A/B arm, and nothing should later read it as a confirmation
# of anything.
set -u

REF="${1:?usage: queue_full_sweep.sh <ref> [label]}"
LABEL="${2:-sweep}"
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
GOLDENS="${GOLDENS:-/home/justin/goldens/results}"

SHA=$(git rev-parse --short "$REF") || { echo "cannot resolve $REF" >&2; exit 2; }
[ "$SHA" = "$REF" ] || echo "resolved $REF to $SHA" >&2

BEHIND=$(git rev-list --count "$SHA..HEAD" -- hw/ 2>/dev/null || echo '?')
if [ "$BEHIND" != "0" ]; then
    echo "NOTE: $SHA is $BEHIND hw/ commit(s) behind HEAD. The column will be" >&2
    echo "      labelled stale by collect_sweep.sh, correctly." >&2
fi

mkdir -p "$D/queue"
n=0
for dir in "$GOLDENS"/*/; do
    suite_fs=$(basename "$dir")
    [ -d "$dir" ] || continue
    suite=${suite_fs//_/ }
    n=$((n+1))
    id=$(printf 'z-%s-%03d-%s' "$LABEL" "$n" "$suite_fs")
    python3 - "$D/queue/$id.req" "$id" "$suite" "$SHA" "$LABEL" <<'PY'
import datetime, json, sys
p, i, suite, ref, label = sys.argv[1:6]
json.dump({"id": i, "requester": "full-sweep", "arm": label,
           "purpose": "full-corpus sweep of %s at %s" % (suite, ref),
           "suites": [suite], "tests": [], "ref": ref, "runs": 1,
           "title": "", "seconds": 0, "pull_glob": "",
           "expect": "", "expect_sha": "", "no_expect":
           "full-corpus survey at one pinned binary, not an A/B arm",
           "queued_utc": datetime.datetime.now(datetime.timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%SZ")},
          open(p, "w"), indent=2)
PY
done
echo "queued $n idle-priority suite requests at $SHA (label $LABEL)"
echo "collect with: docs/testing/collect_sweep.sh $LABEL"
