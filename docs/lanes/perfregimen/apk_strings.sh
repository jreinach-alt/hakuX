#!/usr/bin/env bash
# Strings in an OEM settings APK's dex that name a fan/perf path or key.
# apk_strings.sh <apk> [extra-regex]
apk="$1"; d="$(mktemp -d)"
( cd "$d" && unzip -qo "$apk" 'classes*.dex' )
cat "$d"/classes*.dex | strings -n 5 | grep -E "${2:-^/sys|^/proc|^/dev|fan|Fan|FAN|performance_mode|perf_mode|persist\.|vendor\.|pwm|gpu|Gpu|cpufreq|min_freq|min_pwr}" | sort -u
rm -rf "$d"
