#!/usr/bin/env bash
#
# Run the pgraph test disc on a desktop xemu build and extract the captures.
#
# This is the driver for docs/testing/extract_results.py. The extractor was in
# the repo and this was not, so a capture run could only be reproduced by
# someone who already had a container it had been run in -- which is the same
# defect as a number nobody can re-run. It is committed so a fresh machine with
# the firmware and a disc can reproduce one.
#
# WHY THE CONFIG IS REDIRECTED
#
# xemu locates its config via SDL_GetPrefPath("xemu","xemu"), which on Linux
# honours XDG_DATA_HOME. Pointing that at a per-run directory moves the config,
# the SPIR-V cache and the shader-module keys with it. Without that, a run can
# be served a previous build's compiled shader and "measure" the old code --
# the failure mode is silent and the numbers look plausible.
#
# The firmware stays in the shared directory: it is the machine's, not the
# run's. Only the caches are private.
#
# Usage:
#   pgraph_capture_run.sh <binary> <iso> <tag> [results-dir-on-E]
#
# Environment:
#   RENDERER   OPENGL | VULKAN                    (default VULKAN)
#   OUTDIR     where runs and captures land       (default /tmp/pgraph-run)
#   XEMU_DATA  firmware directory, holding
#              mcpx_1.0.bin, flash.bin, eeprom.bin
#                          (default ~/.local/share/xemu/xemu)
#   PRISTINE   blank HDD image to copy per run    (default $OUTDIR/pristine.qcow2)
#   VALIDATION non-empty turns on Vulkan validation layers
#   TIMEOUT    seconds before the run is killed   (default 2400)
#
# Exits non-zero if the emulator did not finish or no captures came out.

set -u

BIN="${1:?usage: pgraph_capture_run.sh <binary> <iso> <tag> [results-dir-on-E]}"
ISO="${2:?missing iso}"
TAG="${3:?missing tag}"
DISCDIR="${4:-}"   # directory on E:; auto-detected when omitted

RENDERER="${RENDERER:-VULKAN}"
OUTDIR="${OUTDIR:-/tmp/pgraph-run}"
XEMU_DATA="${XEMU_DATA:-$HOME/.local/share/xemu/xemu}"
PRISTINE="${PRISTINE:-$OUTDIR/pristine.qcow2}"
TIMEOUT="${TIMEOUT:-2400}"

die() { echo "pgraph_capture_run: $*" >&2; exit 1; }

# The run cd's into the binary's directory, so every path that is read after
# that point -- the binary, the disc, the HDD -- has to be absolute first.
# A relative one silently resolves against the wrong directory.
abspath() { case "$1" in /*) printf '%s\n' "$1";; *) printf '%s/%s\n' "$PWD" "$1";; esac; }
BIN=$(abspath "$BIN"); ISO=$(abspath "$ISO")

[ -x "$BIN" ]      || die "no such binary: $BIN"
[ -r "$ISO" ]      || die "no such disc image: $ISO"
OUTDIR=$(abspath "$OUTDIR"); PRISTINE=$(abspath "$PRISTINE"); XEMU_DATA=$(abspath "$XEMU_DATA")
[ -r "$PRISTINE" ] || die "no pristine HDD image: $PRISTINE"
for f in mcpx_1.0.bin flash.bin eeprom.bin; do
    [ -r "$XEMU_DATA/$f" ] || die "missing firmware: $XEMU_DATA/$f (console firmware is not in this repo and cannot be)"
done
command -v xvfb-run >/dev/null || die "xvfb-run not on PATH"

XHOME="$OUTDIR/xemu-home-$TAG"
CFGDIR="$XHOME/xemu/xemu"
HDD="$OUTDIR/hdd_$TAG.qcow2"
LOG="$OUTDIR/run_$TAG.log"

mkdir -p "$OUTDIR"

# A fresh cache every run. This directory is created by this script, so
# clearing it cannot destroy anything a person put there, and it is what stops
# a stale shader from being served to a new binary.
rm -rf "$XHOME"
mkdir -p "$CFGDIR"

cp "$PRISTINE" "$HDD" || die "could not stage the HDD image"

{
    printf '[general]\nshow_welcome = false\n\n'
    printf "[display]\nrenderer = '%s'\n" "$RENDERER"
    [ -n "${VALIDATION:-}" ] && printf '\n[display.vulkan]\nvalidation_layers = true\n'
    printf "\n[sys.files]\n"
    printf "bootrom_path = '%s'\n" "$XEMU_DATA/mcpx_1.0.bin"
    printf "flashrom_path = '%s'\n" "$XEMU_DATA/flash.bin"
    printf "eeprom_path = '%s'\n" "$XEMU_DATA/eeprom.bin"
    printf "hdd_path = '%s'\n" "$HDD"
    printf "dvd_path = '%s'\n" "$ISO"
} > "$CFGDIR/xemu.toml"

start=$(date +%s)
( cd "$(dirname "$BIN")" && ulimit -c unlimited &&
  XDG_DATA_HOME="$XHOME" SDL_AUDIODRIVER=dummy \
      xvfb-run -a --server-args="-screen 0 640x480x24" \
      timeout -k 5 "$TIMEOUT" "$BIN" -machine xbox -display none ) > "$LOG" 2>&1
rc=$?
elapsed=$(( $(date +%s) - start ))

# The renderer xemu actually selected, not the one that was asked for: a
# request for OPENGL on a host with no usable GL context silently continues on
# Vulkan, and a run mislabelled that way is worse than no run.
got=$(grep -m1 '^nv2a: renderer:' "$LOG" | cut -d' ' -f3-)
echo "$TAG: exit=$rc in ${elapsed}s, renderer requested=$RENDERER got=${got:-UNKNOWN}"
[ -n "$got" ] || { tail -20 "$LOG" >&2; die "the emulator never reported a renderer -- see $LOG"; }

EXTRACT="$(dirname "$0")/extract_results.py"
SCORE="$OUTDIR/score_$TAG"
rm -rf "$SCORE"; mkdir -p "$SCORE"

# Which directory on E: the suite wrote to is a property of the DISC, not of
# this script. extract_results.py defaults to "nxdk_pgraph_tests", but a
# purpose-built disc names its own -- iso_surf1.iso writes to "surf1". Getting
# this wrong reads as "the run produced nothing" when the run was fine, so when
# the caller did not say, look rather than guess.
if [ -z "$DISCDIR" ]; then
    DISCDIR=$(python3 "$EXTRACT" "$HDD" --list -d "" 2>/dev/null |
              awk '$1 == "dir" { print $NF }')
    case "$(printf '%s' "$DISCDIR" | wc -w)" in
        0) die "nothing on E: -- the suite wrote no results. See $LOG" ;;
        1) echo "$TAG: results directory on E: is '$DISCDIR'" ;;
        *) die "several directories on E: ($(echo $DISCDIR)) -- pass one as the 4th argument" ;;
    esac
fi

python3 "$EXTRACT" "$HDD" -o "$SCORE/$TAG" -d "$DISCDIR" 2>&1 | tail -1

n=$(find "$SCORE/$TAG" -name '*.png' 2>/dev/null | wc -l)
echo "$TAG: $n captures in $SCORE/$TAG"
[ "$n" -gt 0 ] || die "no captures extracted -- see $LOG"
exit $rc
