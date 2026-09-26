#!/usr/bin/env bash
# Print the 30 s timeline of each result id given.
TIMELINE=1 exec python3 "$(dirname "$0")/vcpu_judge.py" --one "$@"
