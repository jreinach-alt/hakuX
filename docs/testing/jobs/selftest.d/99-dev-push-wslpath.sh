# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# ok/bad/check. Not executable, no shebang, no exit -- `fail` is shared.
#
# dev_push (dispatcher.sh) hands its host-path source to Windows adb.exe
# unchanged. adb.exe cannot open a /mnt/... or a bare /home/... path
# (AGENTS.md, "Disc images live on D:": "Give it the Windows path,
# `adb push "$(wslpath -w "$f")" <device path>`; it cannot stat
# `/mnt/d/...`."). Every staged-disc push failed with "cannot stat" until
# dev_push resolved its source through `wslpath -w` first (#433;
# dispatcher.log:29078-29085 Halo 10-18 06:17, :29292-29294 mkdawhite1018
# 10-18 08:33-08:34; both traced in docs/lanes/mkdawhite1018/NOTES.md
# section 6 and confirmed against the real Nova in
# docs/lanes/dispatchpush1018/NOTES.md section 1).
#
# Driven against a fake `adb` that stubs ONLY the device transport: `push`
# and `shell` (sha256sum/stat/chmod/mv) against a local directory standing
# in for the device, the same technique 99-iso-roots.sh uses. `wslpath` is
# NOT stubbed -- it runs for real, twice: forward (`-w`) inside dev_push
# itself, and backward (`-u`) inside this fake adb's `push` handler, which
# refuses (exactly as the real adb.exe does, "cannot stat") any argument
# that is not already Windows-syntax (`X:\...` or `\\wsl.localhost\...`)
# before it will resolve one back to the real file and copy it. A
# regression that drops dev_push's own `wslpath -w` call hands this fake
# adb the bare Unix path dev_push received, which the fake adb refuses the
# same way the real one does, and dev_push returns 1 where the checks below
# expect 0.
#
# Two legs: a source literally under /mnt/d (a real D: mount here, the
# staging root that broke every title push, #433) and a source under $T
# (stands in for /home, as titles.qcow2's own call site already is -- both
# resolve through wslpath's `\\wsl.localhost\...` form when they are not
# under a mounted drive letter). Each is a small file this fragment alone
# creates and removes.

echo "== dev_push: adb.exe gets a wslpath -w'd source, never a bare /path =="
DP="$T/devpush"; rm -rf "$DP"; mkdir -p "$DP/bin" "$DP/fs"
DPD=/mnt/d/hakux-staging/selftest-dispatchpush1018; rm -rf "$DPD"; mkdir -p "$DPD"

cat > "$DP/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
case "$1" in
    push)
        src="$2"; dst="$3"
        case "$src" in
            [A-Za-z]:\\*|\\\\*) real=$(wslpath -u "$src") || exit 1 ;;
            *) echo "adb: error: cannot stat '$src': No such file or directory" >&2; exit 1 ;;
        esac
        mkdir -p "$(dirname "$DP_FS$dst")" && cp "$real" "$DP_FS$dst"
        exit $? ;;
    shell)
        shift; cmd="$*"
        sh -c "${cmd//\/storage\//$DP_FS/storage/}" | sed "s#$DP_FS##g"
        exit 0 ;;
esac
exit 0
EOF
chmod +x "$DP/bin/adb"

# sanity on the stub itself: an unconverted path is refused exactly like the
# real adb.exe, independent of dev_push -- this is the failure dev_push's
# old, unconverted call would have hit.
out=$(PATH="$DP/bin:$PATH" adb push /mnt/d/hakux-staging/selftest-dispatchpush1018/x.txt /storage/E6C6-D7AA/x 2>&1)
case "$out" in
    *"cannot stat"*) ok "stub: an unconverted /mnt/... source is refused, like the real adb.exe" ;;
    *) bad "stub: an unconverted source got [$out], not a refusal" ;;
esac

dp_push() {   # <src> <device path> -> RC
    ( export PATH="$DP/bin:$PATH" DP_FS="$DP/fs" DISPATCH_DIR="$DP/dispatch" ADB_RETRIES=0
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      log() { :; }
      dev_push "$1" "$2"
      echo "RC=$?" )
}

# leg 1: a source literally on D:, the exact root #433 broke.
printf 'dispatchpush1018 selftest: mnt-d leg\n' > "$DPD/mnt-d-src.txt"
out=$(dp_push "$DPD/mnt-d-src.txt" /storage/E6C6-D7AA/Games/XBox/selftest-dispatchpush1018-mntd.iso)
[ "$out" = "RC=0" ] \
    && [ "$(cat "$DP/fs/storage/E6C6-D7AA/Games/XBox/selftest-dispatchpush1018-mntd.iso" 2>/dev/null)" = "dispatchpush1018 selftest: mnt-d leg" ] \
    && ok "mnt-d: a /mnt/d source pushes through wslpath -w (D:\\...)" \
    || bad "mnt-d: got [$out]"

# leg 2: a source off any drive letter (stands in for /home, titles.qcow2's
# own call site), which wslpath resolves to \\wsl.localhost\...\ instead.
printf 'dispatchpush1018 selftest: home-style leg\n' > "$DP/home-src.txt"
out=$(dp_push "$DP/home-src.txt" /storage/E6C6-D7AA/Games/XBox/selftest-dispatchpush1018-home.iso)
[ "$out" = "RC=0" ] \
    && [ "$(cat "$DP/fs/storage/E6C6-D7AA/Games/XBox/selftest-dispatchpush1018-home.iso" 2>/dev/null)" = "dispatchpush1018 selftest: home-style leg" ] \
    && ok "home: a non-drive-letter source pushes through wslpath -w (\\\\wsl.localhost\\...)" \
    || bad "home: got [$out]"

rm -rf "$DPD"
