# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# A soak from a ref before libfolders (10f14d301d) must find its games folder
# on a handheld where a libfolders build has migrated `gamesFolderUri` into
# `gamesFolderUris` and deleted it (fmv303c's 179114986 opened the setup
# wizard on the Thor). ensure_legacy_folder_pref puts the old key back.
#
# A fake adb serves one fake device's x1box_prefs.xml; the dispatcher's own
# functions are called, sourced from dispatcher.sh.
#
# THE FALSIFIER: against master ensure_legacy_folder_pref does not exist, the
# prefs keep no gamesFolderUri, and the first leg goes red on the old build's
# read of the file, not on a missing function name.

echo "== folder pref: a pre-libfolders build still finds its games folder"
FP="$T/folderpref"; rm -rf "$FP"; mkdir -p "$FP/bin" "$FP/dev" "$FP/dispatch/logs"
cat > "$FP/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$FP_DEV/calls"
case "$1" in
    shell) shift; c="$*"
        case "$c" in
            "am force-stop"*) ;;
            *"cat > shared_prefs/x1box_prefs.xml"*) cat > "$FP_DEV/prefs.xml"
                [ -f "$FP_DEV/drop_readback" ] && touch "$FP_DEV/drop_next" ;;
            *"cat shared_prefs/x1box_prefs.xml"*)   # drop_readback: the write lands, its read-back is lost
                if [ -f "$FP_DEV/drop_next" ]; then rm -f "$FP_DEV/drop_next"
                elif [ -f "$FP_DEV/prefs.xml" ]; then cat "$FP_DEV/prefs.xml"; fi ;;
        esac ;;
esac
EOF
chmod +x "$FP/bin/adb"

U1='content://com.android.externalstorage.documents/tree/primary%3AXbox'
U2='content://com.android.externalstorage.documents/tree/1234-5678%3AGames'
# What a libfolders build leaves: Android's JSONArray escapes "/" as "\/" and
# its XML serializer writes the quotes as &quot;. No gamesFolderUri.
migrated() {
    cat > "$FP/dev/prefs.xml" <<EOF
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <boolean name="setup_complete" value="true" />
    <string name="gamesFolderUris">[&quot;${U1//\//\\/}&quot;,&quot;${U2//\//\\/}&quot;]</string>
    <string name="hddPath">/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box/hdd.img</string>
</map>
EOF
}
fp_env() {
    ( export DISPATCH_DIR="$FP/dispatch" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO" \
             FP_DEV="$FP/dev" ADB_RETRY_SLEEP=0 PATH="$FP/bin:$PATH"
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$1" )
}
# What a pre-libfolders build reads: the unescaped text of gamesFolderUri.
old_build_reads() {
    python3 -c 'import sys, xml.etree.ElementTree as E
for e in E.parse(sys.argv[1]).getroot():
    if e.get("name") == "gamesFolderUri": print(e.text)' "$FP/dev/prefs.xml"
}
# What a libfolders build reads: gamesFolderUris, parsed.
new_build_reads() {
    python3 -c 'import json, sys, xml.etree.ElementTree as E
for e in E.parse(sys.argv[1]).getroot():
    if e.get("name") == "gamesFolderUris": print(" ".join(json.loads(e.text)))' "$FP/dev/prefs.xml"
}

# -------------------------------------------------- the migrated handheld
migrated; cp "$FP/dev/prefs.xml" "$FP/prefs.orig.xml"; : > "$FP/dev/calls"
st=$(fp_env 'ensure_legacy_folder_pref >/dev/null 2>&1; rc=$?; echo "$rc|$FOLDER_PREF_STATE"')
check "a migrated handheld: ensure succeeds and says it added the key (got: $st)" \
      [ "$st" = "0|added: gamesFolderUri from gamesFolderUris[0]" ]
check "  ... a pre-libfolders build now reads the first folder (got: $(old_build_reads))" \
      [ "$(old_build_reads)" = "$U1" ]
check "  ... a libfolders build still reads both folders, in order" \
      [ "$(new_build_reads)" = "$U1 $U2" ]
changed=$(diff "$FP/prefs.orig.xml" "$FP/dev/prefs.xml" | grep '^[<>]')
check "  ... the one changed line is the added key; every other byte is kept (got: $changed)" \
      [ "$changed" = ">     <string name=\"gamesFolderUri\">$U1</string>" ]
check "  ... the app was stopped before the read" eval 'head -1 "$FP/dev/calls" | grep -q "am force-stop"'
cp "$FP/dev/prefs.xml" "$FP/prefs.fixed.xml"

: > "$FP/dev/calls"
st=$(fp_env 'ensure_legacy_folder_pref >/dev/null 2>&1; rc=$?; echo "$rc|$FOLDER_PREF_STATE"')
check "the next soak: nothing to do (got: $st)" [ "$st" = "0|kept: no change needed" ]
check "  ... and nothing written" eval '! grep -q "cat >" "$FP/dev/calls" && cmp -s "$FP/prefs.fixed.xml" "$FP/dev/prefs.xml"'

# ---------------------------------------- an un-migrated handheld (.debug2)
cat > "$FP/dev/prefs.xml" <<EOF
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="gamesFolderUri">$U2</string>
</map>
EOF
cp "$FP/dev/prefs.xml" "$FP/prefs.legacy.xml"; : > "$FP/dev/calls"
st=$(fp_env 'ensure_legacy_folder_pref >/dev/null 2>&1; rc=$?; echo "$rc|$FOLDER_PREF_STATE"')
check "a handheld that still has only the old key: left alone (got: $st)" \
      eval '[ "$st" = "0|kept: no change needed" ] && ! grep -q "cat >" "$FP/dev/calls" && cmp -s "$FP/prefs.legacy.xml" "$FP/dev/prefs.xml"'

# ---------------------------------------------- no folders, unreadable list
for body in '' '<string name="gamesFolderUris">[]</string>' '<string name="gamesFolderUris">not json</string>'; do
    printf '<?xml version="1.0" ?>\n<map>\n    %s\n</map>\n' "$body" > "$FP/dev/prefs.xml"
    cp "$FP/dev/prefs.xml" "$FP/prefs.none.xml"; : > "$FP/dev/calls"
    st=$(fp_env 'ensure_legacy_folder_pref >/dev/null 2>&1; rc=$?; echo "$rc|$FOLDER_PREF_STATE"')
    check "no folder to copy (${body:-no key}): no write, the run goes on (got: $st)" \
          eval '[ "${st%%|*}" = 0 ] && ! grep -q "cat >" "$FP/dev/calls" && cmp -s "$FP/prefs.none.xml" "$FP/dev/prefs.xml"'
done

rm -f "$FP/dev/prefs.xml"; : > "$FP/dev/calls"
st=$(fp_env 'ensure_legacy_folder_pref >/dev/null 2>&1; rc=$?; echo "$rc|$FOLDER_PREF_STATE"')
check "no prefs file at all: warned, not written, the run goes on (got: $st)" \
      eval '[ "${st%%|*}" = 0 ] && case "$st" in *unread*) true ;; *) false ;; esac && ! grep -q "cat >" "$FP/dev/calls"'

# ------------------------------------------------- a write that is not seen
migrated; touch "$FP/dev/drop_readback"
st=$(fp_env 'ensure_legacy_folder_pref >/dev/null 2>&1; echo "$?"')
rm -f "$FP/dev/drop_readback" "$FP/dev/drop_next"
check "a write whose read-back is lost fails the request (rc=$st)" [ "$st" = 1 ]

# --------------------------------------------------------- the wiring
echo "== folder pref: serve_one calls it before every soak"
body=$(fp_env 'declare -f serve_one')
order=$(printf '%s\n' "$body" | grep -v '^[[:space:]]*#' | grep -n -o 'ensure_legacy_folder_pref\|titles_disk_prepare\|soak_title.sh' \
        | cut -d: -f2 | uniq | tr '\n' ' ')
check "ensure, then the titles disk, then the soak (got: $order)" \
      [ "$order" = "ensure_legacy_folder_pref titles_disk_prepare soak_title.sh " ]
check "result.json records it" eval 'grep -q "folder_pref=os.environ.get(\"FOLDER_PREF_STATE\"" "$TESTING/dispatcher.sh"'
