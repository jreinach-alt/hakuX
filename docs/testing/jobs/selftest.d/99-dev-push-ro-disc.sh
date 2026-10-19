# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# ok/bad/check. Not executable, no shebang, no exit -- `fail` is shared.
#
# dev_push's mode-660 check (THE DISK MUST BE MODE 660, dispatcher.sh:801-812)
# is written for titles.qcow2, a disk inside the app's x1box directory that
# xemu opens read-write. DEVICE_ISO_ROOT (the Nova's SD card) has its modes
# synthesized by the mount: `chmod 660` is a no-op there and the mode always
# reads back 770. xemu opens a disc read-only, so 770 is fine for a disc --
# but dev_push refused it anyway, blocking every staged-disc push (#433;
# dispatcher.log, mkdawhite1018 10-18 11:05, docs/lanes/mkdawhite1018/
# NOTES.md section 7.1). dev_push now takes an optional `ro` third argument
# that skips dev_make_660 and the final mode check (the sha check still
# runs); ensure_title_staged's one disc-push call site (dispatcher.sh:1260)
# passes it. Every other caller -- titles.qcow2 (:1680) and the hdd-guard
# push (:1813) -- omits it and must still require 660.
#
# Driven against a fake adb whose `chmod` is a no-op and whose `stat -c %a`
# always answers 770, standing in for a mount that ignores chmod (the same
# fake-transport technique as 99-dev-push-wslpath.sh). Two legs: a disc push
# with `ro` must succeed under it; a titles-disk-style push without `ro`
# must still fail the same way it does today -- before the rename, so the
# device never ends up with a half-named file.

echo "== dev_push: ro skips the 660 check for a disc on a mount that ignores chmod =="
DR="$T/devpushro"; rm -rf "$DR"; mkdir -p "$DR/bin" "$DR/fs"
DRD=/mnt/d/hakux-staging/selftest-devpushro1018; rm -rf "$DRD"; mkdir -p "$DRD"

cat > "$DR/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
case "$1" in
    push)
        src="$2"; dst="$3"
        case "$src" in
            [A-Za-z]:\\*|\\\\*) real=$(wslpath -u "$src") || exit 1 ;;
            *) echo "adb: error: cannot stat '$src': No such file or directory" >&2; exit 1 ;;
        esac
        mkdir -p "$(dirname "$DR_FS$dst")" && cp "$real" "$DR_FS$dst"
        exit $? ;;
    shell)
        shift; cmd="$*"
        case "$cmd" in
            "chmod 660 "*) exit 0 ;;                     # the mount ignores it
            "stat -c %a "*) echo 770; exit 0 ;;           # ... and always reads back 770
            *) sh -c "${cmd//\/storage\//$DR_FS/storage/}" | sed "s#$DR_FS##g" ;;
        esac
        exit 0 ;;
esac
exit 0
EOF
chmod +x "$DR/bin/adb"

dr_push() {   # <src> <device path> [ro] -> RC
    ( export PATH="$DR/bin:$PATH" DR_FS="$DR/fs" DISPATCH_DIR="$DR/dispatch" ADB_RETRIES=0
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      log() { :; }
      dev_push "$1" "$2" "${3:-}"
      echo "RC=$?" )
}

# leg 1: a disc push with `ro` succeeds even though chmod never takes and
# stat always reads back 770.
DISC=/storage/E6C6-D7AA/Games/XBox/selftest-devpushro1018-disc.iso
printf 'devpushro1018 selftest: disc leg\n' > "$DRD/disc-src.txt"
out=$(dr_push "$DRD/disc-src.txt" "$DISC" ro)
[ "$out" = "RC=0" ] \
    && [ "$(cat "$DR/fs$DISC" 2>/dev/null)" = "devpushro1018 selftest: disc leg" ] \
    && ok "disc: a push with ro succeeds on a mount that always reads back 770" \
    || bad "disc: got [$out]"

# leg 2: a titles-disk-style push without `ro` still fails under the same
# mount, the same way it does today -- and the destination is never written.
TITLES=/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box/selftest-devpushro1018-titles.qcow2
printf 'devpushro1018 selftest: titles-disk leg\n' > "$DRD/titles-src.txt"
out=$(dr_push "$DRD/titles-src.txt" "$TITLES")
[ "$out" = "RC=1" ] && [ ! -e "$DR/fs$TITLES" ] \
    && ok "titles-disk: a push without ro still fails on the same mount, before the rename" \
    || bad "titles-disk: got [$out], expected RC=1 and no $TITLES"

rm -rf "$DRD"
