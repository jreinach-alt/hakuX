# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# ok/bad/check. Not executable, no shebang, no exit -- `fail` is shared.
#
# A handheld's titles may live under more than one root. From 2026-09-26 the
# Thor keeps them on its SD card AND in internal storage (the card was 94%
# full), and the dispatcher's soak check looked only at DEVICE_ISO_ROOT, so a
# title pushed to internal storage came back "title not on device".
#
# Driven against a fake adb whose `shell` runs the command in sh with every
# /storage/ path moved under $IR/fs, so "the device" is that directory. The
# lookup is the dispatcher's own: the soak block is cut out of dispatcher.sh
# (from `local tpath` to the first `fi` after it) and run with the functions
# dispatcher.sh defines, so a check that passed while the serve path still
# looked in one place is not possible.
#
# THE LEGS, and the world in which each one fails:
#   root 2     a title only under the Thor's internal root is found there.
#              Fails on master (one root) and on any lookup that stops at
#              the first root.
#   none       a title under no root: ERROR names the title and BOTH roots.
#              Fails on master (it names one path) and if the message is
#              built from DEVICE_ISO_ROOT.
#   quote      a title with an apostrophe under root 1 is found. Fails on
#              master, which single-quoted the path for the device's shell
#              without escaping the quote.
#   root 1     a title under BOTH roots plays from the SD card. A control
#              master passes; fails if the order is reversed.
#   one root   the Nova: a title under its root is found, a missing one's
#              ERROR names exactly its one root. A control master passes on
#              the first half; fails if the Nova gains a second root.
#   unchanged  DEVICE_ISO_ROOT is still the first root, and `devices.sh
#              <serial>` still prints it (run_disc.sh pushes test discs there).
#   titles     `devices.sh titles thor` lists both roots.
#   launch     soak_title.sh's `am start` hands an apostrophe title's path to
#              the app whole. Fails on master, whose '$ISO' left the quote
#              unbalanced -- a title the lookup now finds would not launch.
# Set IR_TESTING to another docs/testing tree to run these legs against it.

echo "== title roots: a soak finds its title under any of the device's roots"
IR="$T/isoroots"; rm -rf "$IR"; mkdir -p "$IR/bin" "$IR/fs" "$IR/rdir"
IRT="${IR_TESTING:-$TESTING}"
cat > "$IR/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
case "$1" in
    devices) printf 'List of devices attached\nbdc158a5\tdevice\nee317437\tdevice\n' ;;
    shell)   shift; cmd="$*"
             sh -c "${cmd//\/storage\//$IR_FS/storage/}" | sed "s#$IR_FS##g" ;;
esac
exit 0
EOF
chmod +x "$IR/bin/adb"
THOR1=/storage/388C-68F7/ROMS/xbox THOR2=/storage/emulated/0/ROMS/xbox
NOVA1=/storage/E6C6-D7AA/Games/XBox
mkdir -p "$IR/fs$THOR1" "$IR/fs$THOR2" "$IR/fs$NOVA1"
touch "$IR/fs$THOR2/Only Internal (USA).iso" \
      "$IR/fs$THOR1/Both (USA).iso" "$IR/fs$THOR2/Both (USA).iso" \
      "$IR/fs$THOR1/Tom Clancy's Thing (USA).iso" \
      "$IR/fs$NOVA1/Galleon (USA).xiso.iso"

# The dispatcher's soak check, verbatim, as a function: <serial> <title>.
# Prints "FOUND <path>" or "MISS <ERROR text>".
IRBLOCK=$(sed -n '/^        local tpath/,/^        fi$/p' "$IRT/dispatcher.sh")
ir_soak() {
    ( export PATH="$IR/bin:$PATH" IR_FS="$IR/fs" DISPATCH_DIR="$IR/dispatch"
      . "$IRT/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      device_env "$1" >/dev/null || exit 9
      log() { :; }
      eval "ir_block() { local title=\$1 rdir=$IR/rdir req=$IR/req.json
$IRBLOCK
echo \"FOUND \$tpath\"; }"
      rm -f "$IR/rdir/ERROR"; : > "$IR/req.json"
      ADB_RETRIES=0 ir_block "$2"
      [ -f "$IR/rdir/ERROR" ] && echo "MISS $(cat "$IR/rdir/ERROR")" )
}
[ -n "$IRBLOCK" ] && ok "the soak's title check is cut out of dispatcher.sh ($(printf '%s\n' "$IRBLOCK" | wc -l) lines)" \
    || bad "no \`local tpath\` block in $IRT/dispatcher.sh"

out=$(ir_soak bdc158a5 "Only Internal (USA).iso")
[ "$out" = "FOUND $THOR2/Only Internal (USA).iso" ] && ok "root 2: a title only in Thor internal storage is found there" \
    || bad "root 2: got [$out]"

out=$(ir_soak bdc158a5 "Absent (USA).iso")
case "$out" in
    MISS*"Absent (USA).iso"*"$THOR1"*"$THOR2"*) ok "none: the ERROR names the title and both Thor roots" ;;
    *) bad "none: got [$out]" ;;
esac

out=$(ir_soak bdc158a5 "Tom Clancy's Thing (USA).iso")
[ "$out" = "FOUND $THOR1/Tom Clancy's Thing (USA).iso" ] && ok "quote: a title with an apostrophe is found" \
    || bad "quote: got [$out]"

out=$(ir_soak bdc158a5 "Both (USA).iso")
[ "$out" = "FOUND $THOR1/Both (USA).iso" ] && ok "root 1: a title under both roots plays from the SD card" \
    || bad "root 1: got [$out]"

out=$(ir_soak ee317437 "Galleon (USA).xiso.iso")
[ "$out" = "FOUND $NOVA1/Galleon (USA).xiso.iso" ] && ok "one root: the Nova finds a title under its root" \
    || bad "one root: got [$out]"
out=$(ir_soak ee317437 "Only Internal (USA).iso")
case "$out" in
    MISS*"searched $NOVA1") ok "one root: a Nova miss names exactly its one root" ;;
    *) bad "one root: a Nova miss got [$out]" ;;
esac

# launch: the soak's own `am start` line, cut out of soak_title.sh and run
# with `adb shell` replaced by the host's sh and `am` by a function recording
# its last argument -- the rom_path the app would receive.
IRAM=$(grep -m1 '^a shell "am start' "$IRT/soak_title.sh")
ir_launch() {   # <iso path> -> rom_path as the device's shell parses it
    ( . "$IRT/devices.sh"; ISO=$1 ACT=pkg/.Act
      a() { [ "$1" = shell ] && IR_AM="$IR/am.out" sh -c 'am() { while [ $# -gt 1 ]; do shift; done; printf "%s\n" "$1" > "$IR_AM"; }; '"$2"; }
      rm -f "$IR/am.out"; eval "$IRAM"; cat "$IR/am.out" 2>/dev/null )
}
out=$(ir_launch "$THOR1/Tom Clancy's Thing (USA).iso")
[ "$out" = "$THOR1/Tom Clancy's Thing (USA).iso" ] && ok "launch: am start receives an apostrophe title's full path" \
    || bad "launch: rom_path arrived as [$out]"

out=$(PATH="$IR/bin:$PATH" bash "$IRT/devices.sh" bdc158a5)
[ "$out" = "bdc158a5 thor $THOR1" ] && ok "unchanged: \`devices.sh bdc158a5\` still prints the SD root" \
    || bad "unchanged: got [$out]"

out=$(PATH="$IR/bin:$PATH" IR_FS="$IR/fs" bash "$IRT/devices.sh" titles thor)
case "$out" in
    *"=== thor (bdc158a5)  $THOR1"*"Both (USA).iso"*"=== thor (bdc158a5)  $THOR2"*"Only Internal (USA).iso"*)
        ok "titles: \`devices.sh titles thor\` lists both roots" ;;
    *) bad "titles: got [$out]" ;;
esac
