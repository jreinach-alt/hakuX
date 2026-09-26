#!/usr/bin/env bash
# Run the jobs selftest (which sources dispatcher.sh in fragment 51) and keep
# its tail. Usage: bash docs/lanes/blinx372b/run_selftest.sh
cd "$(dirname "$0")/../../.." || exit 2
log=/tmp/blinx372b-selftest.log
timeout 580 bash docs/testing/jobs/selftest.sh > "$log" 2>&1
echo "EXIT=$?"
grep -E "LOGCAT_SPEC|^selftest:" "$log"
grep -iE "^ *(FAIL|BAD)" "$log" | head
