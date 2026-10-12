#!/usr/bin/env bash
# The bash-callable half of the one reader (#433): models.py does the
# parsing, every bash caller (lane.sh, cloud.sh, mode.sh) execs this instead
# of re-implementing it, so there is one parser, not two.
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/models.py" "$@"
