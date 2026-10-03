#!/bin/bash
# Every selftest fragment that loads titlestate.py or status_html.py, through
# selftest.sh (they need its check() and fake host).
cd "$(dirname "$0")/../../../.." || exit 2
env SELFTEST_ONLY="64-status-html 65-status-objective 66-status-titles 67-status-measured 85-savestate 99-hdd-split 99-status-degraded 99-status-escalations 99-status-escalation-items 99-status-fullwindow" \
    bash docs/testing/jobs/selftest.sh
