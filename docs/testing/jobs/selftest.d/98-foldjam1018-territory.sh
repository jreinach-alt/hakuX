# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# check_territory.py (#433, foldjam1018 item C): a widening lane that hits
# "listed FREE but claimed" had to work out for itself that [free] is the
# stale half and that releasing the file there, in the SAME commit that adds
# it to its own row, is the fix -- nothing said so. Depends on no other
# fragment: it copies check_territory.py and board_files.py into a scratch
# dir with its own synthetic territory.toml, so it never touches this
# repository's own board state.

echo "== check_territory.py: a FREE-but-claimed overlap names its own fix"
FT="$T/foldjamterr"; rm -rf "$FT"; mkdir -p "$FT"
cp "$REPO/docs/testing/check_territory.py" "$FT/"
cp "$REPO/docs/testing/board_files.py" "$FT/"

cat > "$FT/territory.toml" <<'EOF'
wave = 1

[lane.widener]
issues = ["1"]
standing = false
files = ["some/widened/file.c"]

[free]
files = ["some/widened/file.c"]
EOF

(cd "$FT" && HAKUX_BOARD_REF= python3 check_territory.py > out.txt 2>&1); rc=$?
check "  overlap still FAILs the gate" bash -c "[ $rc -ne 0 ]"
check "  names the exact file and the lane holding it" \
    grep -qF 'some/widened/file.c is listed FREE but claimed by widener' "$FT/out.txt"
check "  names the fix: release it from [free] in the same commit" \
    grep -qF 'release it from [free] in the same commit that adds it to [lane.widener]' "$FT/out.txt"

# A row with no overlap at all must still read ok -- the message only appears
# when there is something to fix.
cat > "$FT/territory.toml" <<'EOF'
wave = 1

[lane.widener]
issues = ["1"]
standing = false
files = ["some/widened/file.c"]

[free]
files = ["some/other/file.c"]
EOF
(cd "$FT" && HAKUX_BOARD_REF= python3 check_territory.py > out2.txt 2>&1); rc2=$?
check "  a row with no overlap passes clean" bash -c "[ $rc2 -eq 0 ]"
check "  and prints no FREE-but-claimed fix text" bash -c \
    "! grep -qF 'release it from [free]' '$FT/out2.txt'"
