#!/usr/bin/env bash
# Read-only: the perf/fan system settings and the battery, per attached handheld.
for s in ${SERIALS:-bdc158a5 ee317437}; do
    echo "== $s"
    timeout 20 adb -s "$s" shell 'settings list system | grep -iE "perf|fan|mode|cool|gear" ; settings list global | grep -iE "perf|fan|cool" ; settings list secure | grep -iE "perf|fan|cool"; dumpsys battery | grep -E "level|powered|status"' 2>&1 | tr -d '\r'
done
