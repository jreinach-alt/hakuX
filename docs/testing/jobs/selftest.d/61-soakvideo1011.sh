# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit.
#
# start_soak_video / stop_soak_video (dispatcher.sh, #433 lane.soakvideo1011):
# a video of the screen during a queued soak, recorded the way
# start_frame_capture records stills. Exercised here against a fake adb (the
# pattern is 58-pull-verify.sh's), never a real device.
#
# sv_env sources dispatcher.sh the way 97-dispatch-snapshot-drive.sh's sd_env
# does: `. dispatcher.sh selftest-not-a-subcommand` falls through the case at
# the bottom to a harmless `sed` and leaves every function defined in the
# current shell, with no worker loop and no device touched except through
# the fake adb this puts first on PATH.

echo "== soakvideo1011: start_soak_video / stop_soak_video against a fake adb"
SV="$T/soakvideo"; rm -rf "$SV"; mkdir -p "$SV/bin" "$SV/dev"

# The fake adb. Dispatched on argv position, not "$*" substring matching:
# the wildcard clear (`shell "rm -f .../hakux_vid_*.mp4"`) arrives as ONE
# quoted word at $4, while the per-segment rm (`shell rm -f "$remote"`)
# arrives as three separate words (rm, -f, remote) -- so $4 alone tells them
# apart without needing to spot a literal asterisk.
cat > "$SV/bin/adb" <<'EOF'
#!/usr/bin/env bash
DEV="$SV_DEV"
case "$3" in
    shell)
        case "$4" in
            date)
                c=$(cat "$DEV/clock" 2>/dev/null || echo 1000)
                [ -e "$DEV/noclock" ] || echo "$c"
                echo $((c + 1)) > "$DEV/clock"
                ;;
            screenrecord)
                # --time-limit is $6; the remote path is always the last arg.
                n="$6"; remote="${@: -1}"
                i=0
                while [ ! -e "$DEV/stop" ] && [ "$i" -lt "$((n * 5))" ]; do
                    sleep 0.2; i=$((i + 1))
                done
                printf 'FAKE-MP4-%s' "$remote" > "$DEV/$(basename "$remote")"
                ;;
            pkill) : > "$DEV/stop" ;;
            rm)
                # $4=rm $5=-f $6=remote: the per-segment rm-after-verified-pull.
                rm -f "$DEV/$(basename "$6")"
                ;;
            "rm -f /sdcard/Download/hakux_vid_*.mp4")
                rm -f "$DEV"/hakux_vid_*.mp4
                ;;
            *)
                case "$4" in
                    stat*)
                        f=$(printf '%s' "$4" | grep -o 'hakux_vid_[0-9]*\.mp4')
                        stat -c %s "$DEV/$f" 2>/dev/null || echo -1
                        ;;
                esac
                ;;
        esac
        ;;
    pull) cp "$DEV/$(basename "$4")" "$5" 2>/dev/null ;;
esac
exit 0
EOF
chmod +x "$SV/bin/adb"

sv_env() {   # <shell> -> sources dispatcher.sh (worker loop never entered), then runs shell
    # dispatcher.sh's SOURCE-TIME line (not inside any function) is
    # `device_env "${SERIAL:-ee317437}" || exit 2` -- an unrecognized serial
    # kills the sourcing subshell outright (devices.sh's table is fixed
    # hardware, "fake" is not in it), which is why this uses the same real
    # serial 97-dispatch-snapshot-drive.sh's sd_env does (ee317437, the
    # Nova) rather than a made-up one; the fake adb below ignores $2 and
    # dispatches on argv position, so which real serial is irrelevant to it.
    ( export SERIAL=ee317437 ADB_QUICK_TIMEOUT=5 SV_DEV="$SV/dev" PATH="$SV/bin:$PATH" \
             DISPATCH_DIR="$SV/d" DISPATCH_SRC="$TESTING" DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$1" )
}
sv_reset_dev() { rm -rf "$SV/dev"; mkdir -p "$SV/dev"; echo 1000 > "$SV/dev/clock"; }
sv_left_on_device() { ls "$SV/dev"/hakux_vid_*.mp4 2>/dev/null | wc -l; }

# --- leg: no route, secs=5, 2s segments -> 3 segments (2, 2, 1), chained,
#     each pulled and its remote deleted before the next one starts recording
#     (the "pull-then-delete order" and "segment chaining" legs together).
sv_reset_dev
RD="$SV/d/results/chain"; mkdir -p "$RD"
out=$(sv_env "export HAKUX_SOAK_VIDEO_SEG=2
rdir=\"$RD\"
start_soak_video \"\$rdir\" 5 0 0 5
wait \"\$VIDEO_PID\"
cat \"\$rdir/video/meta.json\"")
nseg=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["segments"]))' "$RD/video/meta.json" 2>/dev/null)
mark_wall=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["mark_wall"])' "$RD/video/meta.json" 2>/dev/null)
case "$nseg:$mark_wall" in
    "3:1000.0") ok "no-route video: 5s at 2s segments chains to 3 segments, mark_wall from the device clock" ;;
    *) bad "no-route video chaining: got segments=$nseg mark_wall=$mark_wall -- $out" ;;
esac
check "  each of the 3 local segment files was actually pulled (nonzero size)" \
    bash -c 'for f in "$1"/video/v0000{1,2,3}.mp4; do [ -s "$f" ] || exit 1; done' _ "$RD"
check "  and nothing is left on the fake device afterward" \
    bash -c '[ "$(ls "$1"/dev/hakux_vid_*.mp4 2>/dev/null | wc -l)" = 0 ]' _ "$SV"

# --- leg: a long request, stopped early (SIGINT) -- only the segment that
#     was recording when the stop lands is finalized and pulled; stop_soak_video
#     must not return until that pull is done, and the device must be clear.
sv_reset_dev
RD="$SV/d/results/early"; mkdir -p "$RD"
sv_env "rdir=\"$RD\"
  start_soak_video \"\$rdir\" 100 0 0 100
  sleep 0.5
  stop_soak_video
  cat \"\$rdir/video/meta.json\" > \"$RD/.out\""
nseg=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["segments"]))' "$RD/.out" 2>/dev/null)
case "$nseg" in
    1) ok "SIGINT early stop: exactly the one in-flight segment was finalized and pulled" ;;
    *) bad "SIGINT early stop: expected 1 segment, got '$nseg' (a 100s/60s-default request left to run would make 2)" ;;
esac
check "  its one local segment file was pulled" test -s "$RD/video/v00001.mp4"
check "  and nothing is left on the fake device" \
    bash -c '[ "$(ls "$1"/dev/hakux_vid_*.mp4 2>/dev/null | wc -l)" = 0 ]' _ "$SV"

# --- leg: a route whose mark never comes before the soak ends -- no segment
#     is ever recorded, and the reason is specific ("no mark line", not a
#     generic skip), so a route-soak timeout is not confused with "video off".
sv_reset_dev
RD="$SV/d/results/nomark"; mkdir -p "$RD"
: > "$RD/run.log"
sv_env "rdir=\"$RD\"
start_soak_video \"\$rdir\" 30 0 1 1
wait \"\$VIDEO_PID\""
reason=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("skipped"))' "$RD/video/meta.json" 2>/dev/null)
nseg=$(sv_left_on_device)
case "$reason" in
    "no mark line seen in run.log before the soak ended") ok "no mark in run.log before the (1s) hold ends: video skipped, with that reason" ;;
    *) bad "no-mark leg: got reason='$reason'" ;;
esac
check "  and no screenrecord call was ever made (nothing on the fake device)" test "$nseg" = 0

# --- leg: the mark line IS in run.log -- recording proceeds, mark_wall comes
#     from the device clock (not the string's own timestamp).
sv_reset_dev
RD="$SV/d/results/withmark"; mkdir -p "$RD"
echo 'ROUTE 09:26:13.399 mark gameplay' > "$RD/run.log"
sv_env "export HAKUX_SOAK_VIDEO_SEG=1
rdir=\"$RD\"
start_soak_video \"\$rdir\" 1 0 1 5
wait \"\$VIDEO_PID\""
mark_wall=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["mark_wall"])' "$RD/video/meta.json" 2>/dev/null)
case "$mark_wall" in
    1000.0) ok "mark line present: recording proceeds, mark_wall is the device's clock reading (not the mark line's own timestamp)" ;;
    *) bad "with-mark leg: got mark_wall='$mark_wall'" ;;
esac

# --- leg: the mark is seen, but the device clock cannot be read (3 flaky
#     reads) -- a DIFFERENT reason than "no mark", so the two causes are
#     never conflated in result.json (see _device_epoch / mark_seen in
#     dispatcher.sh and docs/lanes/soakvideo1011/NOTES.md).
sv_reset_dev
: > "$SV/dev/noclock"
RD="$SV/d/results/noclock"; mkdir -p "$RD"
echo 'ROUTE 09:26:13.399 mark gameplay' > "$RD/run.log"
sv_env "rdir=\"$RD\"
start_soak_video \"\$rdir\" 30 0 1 5
wait \"\$VIDEO_PID\""
reason=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("skipped"))' "$RD/video/meta.json" 2>/dev/null)
case "$reason" in
    "mark seen, but the device clock could not be read") ok "mark seen but 3 flaky device-clock reads: skipped with the clock-specific reason, not 'no mark'" ;;
    *) bad "clock-unreadable leg: got reason='$reason'" ;;
esac
rm -f "$SV/dev/noclock"

# --- leg: video off (seconds=0) -- result.json's video dict still exists,
#     with its own reason, for the cost-comparability rule (frames.every's
#     own precedent: a field a reader has to see even when nothing ran).
sv_reset_dev
RD="$SV/d/results/off"; mkdir -p "$RD"
sv_env "rdir=\"$RD\"; start_soak_video \"\$rdir\" 0 30 0 60"
reason=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("skipped"), d["mark_wall"], d["segments"])' "$RD/video/meta.json" 2>/dev/null)
case "$reason" in
    "off None []") ok "video off (seconds=0): meta.json says so, with no mark_wall and no segments" ;;
    *) bad "video-off leg: got '$reason'" ;;
esac

rm -rf "$SV"
unset SV RD out nseg mark_wall reason waiter

echo "== soakvideo1011: _mp4_info() reads duration/samples from an mp4's own moov boxes (no ffmpeg/ffprobe here)"
# A hand-built mp4 with a v0 mvhd (timescale/duration) and a constant-size
# stsz (sample_count at its 4th 4-byte field, same offset whether or not a
# per-sample table follows) -- the two boxes _mp4_info actually reads.
MP="$T/mp4info"; mkdir -p "$MP"
python3 - "$MP/synthetic.mp4" <<'PY'
import struct, sys

def box(typ, payload):
    return struct.pack(">I", 8 + len(payload)) + typ + payload

mvhd = box(b"mvhd", b"\0" * 12 + struct.pack(">II", 600, 1800) + b"\0" * 80)  # 600 Hz, 1800 ticks = 3.0s
stsz = box(b"stsz", struct.pack(">III", 0, 1024, 90))  # constant size 1024, 90 samples
stbl = box(b"stbl", stsz)
minf = box(b"minf", stbl)
mdia = box(b"mdia", minf)
trak = box(b"trak", mdia)
moov = box(b"moov", mvhd + trak)
open(sys.argv[1], "wb").write(moov)
PY
out=$(python3 -c '
import sys
sys.path.insert(0, sys.argv[2])
import re
src = open(sys.argv[3]).read()
m = re.search(r"def _mp4_info\(path\):.*?\n(?=def _video\(rdir\):)", src, re.S)
assert m, "the _mp4_info anchor in dispatcher.sh moved"
ns = {}
exec("import os\n" + m.group(0), ns)
print(ns["_mp4_info"](sys.argv[1]))
' "$MP/synthetic.mp4" "$TESTING" "$TESTING/dispatcher.sh")
case "$out" in
    "(3.0, 90)") ok "_mp4_info reads a hand-built mp4's real moov/mvhd duration and moov/trak/mdia/minf/stbl/stsz sample count" ;;
    *) bad "_mp4_info: got $out, want (3.0, 90)" ;;
esac
check "_mp4_info on a missing file returns (0.0, 0), not an exception" \
    python3 -c '
import sys, re
src = open(sys.argv[2]).read()
m = re.search(r"def _mp4_info\(path\):.*?\n(?=def _video\(rdir\):)", src, re.S)
ns = {}
exec("import os\n" + m.group(0), ns)
assert ns["_mp4_info"](sys.argv[1]) == (0.0, 0)
' "$MP/does-not-exist.mp4" "$TESTING/dispatcher.sh"
rm -rf "$MP"
unset MP out

echo "== request.sh: --video-seconds / --video-after queue-time refusals"
rq_video() {   # <dispatch dir> <extra request.sh args...> -> output
    local d="$1"; shift
    mkdir -p "$d"/queue "$d"/running "$d"/results "$d"/expect
    env DISPATCH_DIR="$d" bash "$TESTING/request.sh" --who sv --purpose "soakvideo1011 selftest" \
        --no-expect "selftest" --seconds 120 "$@" 2>&1
}
RQ="$T/rqvideo"
# --suites (not --title) is a valid, --title-less soak request on its own
# (line 196's `--suites OR --title` gate), so this is the one way to reach
# the video-specific "needs --title" refusal rather than the generic one.
out=$(rq_video "$RQ/a" --suites selftest --video-seconds 30)
case "$out" in
    *"--video-seconds is a SOAK option (--title)"*) ok "refused with --suites but no --title: video needs a disc, not a suite run" ;;
    *) bad "no-title refusal: $out" ;;
esac
out=$(rq_video "$RQ/b" --title "Sonic Heroes.iso" --video-seconds abc)
case "$out" in
    *"--video-seconds wants a whole number of seconds, got 'abc'"*) ok "refused: --video-seconds must be a whole number" ;;
    *) bad "non-numeric --video-seconds: $out" ;;
esac
out=$(rq_video "$RQ/c" --title "Sonic Heroes.iso" --video-seconds 30 --video-after xyz)
case "$out" in
    *"--video-after wants a whole number of seconds, got 'xyz'"*) ok "refused: --video-after must be a whole number" ;;
    *) bad "non-numeric --video-after: $out" ;;
esac
out=$(HAKUX_SOAK_VIDEO_CAP=300 rq_video "$RQ/d" --title "Sonic Heroes.iso" --video-seconds 301)
case "$out" in
    *"--video-seconds 301 exceeds"*"HAKUX_SOAK_VIDEO_CAP (300)"*) ok "refused: --video-seconds over HAKUX_SOAK_VIDEO_CAP" ;;
    *) bad "over-cap --video-seconds: $out" ;;
esac
out=$(rq_video "$RQ/e" --title "Sonic Heroes.iso" --video-after 100 --video-seconds 50)
case "$out" in
    *"--video-after 100 + --video-seconds 50 is more than the 120s soak can hold"*) ok "refused: --video-after + --video-seconds cannot fit even with the mark at t=0" ;;
    *) bad "hold-too-small refusal: $out" ;;
esac
# --find-route: this is a video-option fit check, not a profile-gate one, and
# "Sonic Heroes.iso" (unlike the real on-device file name) resolves to no
# TitleID at all -- the profile gate (lane.profilegate1011, #433) refuses an
# unidentifiable title outright unless the run is finding a route.
out=$(rq_video "$RQ/f" --title "Sonic Heroes.iso" --find-route "selftest: video fit, not a profile check" \
      --video-seconds 60 --video-after 30)
if ls "$RQ/f/queue/"*.req >/dev/null 2>&1; then
    ok "a fitting --video-seconds/--video-after is queued"
    vs=$(python3 -c 'import json,glob,sys; print(json.load(open(glob.glob(sys.argv[1]+"/queue/*.req")[0]))["video_seconds"])' "$RQ/f" 2>/dev/null)
    check "  and the request carries video_seconds=60" test "$vs" = 60
else
    bad "a fitting --video-seconds/--video-after was refused: $out"
fi
rm -rf "$RQ"
unset RQ out vs