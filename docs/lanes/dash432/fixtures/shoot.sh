#!/usr/bin/env bash
# Screenshot a rendered page at phone width, headless.
#
#   shoot.sh <index.html> <out.png> [width] [height]
#
# CHROME names a headless Chrome. This host has no Linux browser; the lane
# used `npx @puppeteer/browsers install chrome-headless-shell@stable --path
# <scratch>` and pointed CHROME at the binary it printed.
set -u
html=$(cd "$(dirname "$1")" && pwd)/$(basename "$1"); png=$2; w=${3:-400}; h=${4:-2400}
: "${CHROME:?set CHROME to a headless chrome binary}"
mkdir -p "$(dirname "$png")"
png=$(cd "$(dirname "$png")" && pwd)/$(basename "$png")
prof=$(mktemp -d "$(dirname "$png")/.shot-profile.XXXXXX")
timeout 120 "$CHROME" --headless --no-sandbox --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --user-data-dir="$prof" --window-size="$w,$h" --screenshot="$png" "file://$html" > /dev/null 2>&1
rm -rf "$prof"
ls -la "$png"
