#!/usr/bin/env bash
# Falsifier for lane.stopmarker: run each case against master's lane.sh (old)
# and this branch's (new), in a scratch HAKUX_WORK with stubbed systemd units.
# Usage: bash docs/lanes/stopmarker/falsify.sh [old-ref]   (default origin/master)
top="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
S="$(mktemp -d)"; mkdir -p "$S/bin"
git -C "$top" show "${1:-origin/master}":docs/testing/lane.sh > "$top/docs/testing/lane.old.sh"
trap 'rm -f "$top/docs/testing/lane.old.sh"; rm -rf "$S"' EXIT
cat > "$S/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$S/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "$STARTED"; exit 0
EOF
chmod +x "$S/bin/"*
printf 'wave = 1\n\n[lane.alpha]\nissues = []\nfiles = []\n' > "$S/territory.toml"
git -c init.defaultBranch=master init -q --bare "$S/origin.git"
git -c init.defaultBranch=master clone -q "$S/origin.git" "$S/repo" 2>/dev/null
git -C "$S/repo" -c user.email=s@t -c user.name=s commit -q --allow-empty -m init
git -C "$S/repo" push -q origin master
echo "a brief" > "$S/brief.md"

run() {   # <old|new> <tag> <args...>  -> prints rc, started-count, output
    local which=$1 tag=$2; shift 2
    local sh="$top/docs/testing/lane.sh"; [ "$which" = old ] && sh="$top/docs/testing/lane.old.sh"
    local W="$S/work-$which-$tag"; export STARTED="$S/started-$which-$tag"; : > "$STARTED"
    mkdir -p "$W/briefs"
    [ -n "${PREP:-}" ] && eval "$PREP"
    out=$( ( export PATH="$S/bin:$PATH" HAKUX_WORK="$W" HAKUX_REPO_DIR="$S/repo" HAKUX_TERRITORY="$S/territory.toml"
             bash "$sh" "$@" ) 2>&1 ); rc=$?
    out=${out//$W/\$W}; out=${out//$S/\$S}
    out=$(sed -E 's/[0-9]{8}T[0-9]{6}Z/STAMP/g' <<< "$out")
    printf '%s %-12s rc=%s units=%s | %s\n' "$which" "$tag" "$rc" "$(wc -l < "$STARTED")" "$(tr '\n' ' ' <<< "$out")"
}
M='_stopmarker_test.md.STOPPED-by-owner-19700101T000000Z'
for w in old new; do
  PREP='echo b > "$W/briefs/'$M'"; mkdir -p "$W/wt/_stopmarker_test"' run $w stop-resume resume _stopmarker_test
  PREP='echo b > "$W/briefs/'$M'"' run $w stop-start start _stopmarker_test "$S/brief.md"
  PREP='echo b > "$W/briefs/'$M'"; mkdir -p "$W/wt/_stopmarker_test"' run $w stop-start-wt start _stopmarker_test "$S/brief.md"
  PREP='echo b > "$S/'$M'"' run $w marker-arg start _stopmarker_test "$S/$M"
  PREP='echo b > "$W/briefs/'$M'"' run $w stop-noworkt resume _stopmarker_test
  # Ordinary lanes: no marker anywhere.
  PREP='' run $w plain-start start alpha "$S/brief.md"
  PREP='mkdir -p "$W/wt/alpha"; echo b > "$W/briefs/alpha.md"' run $w plain-resume resume alpha
  PREP='mkdir -p "$W/wt/alpha"' run $w plain-nobrief resume alpha
  PREP='' run $w plain-nowt resume alpha
  # A marker for a DIFFERENT lane must not touch this one.
  PREP='mkdir -p "$W/wt/alpha"; echo b > "$W/briefs/alpha.md"; echo b > "$W/briefs/alphabet.md.STOPPED-by-owner-1"' run $w other-marker resume alpha
  rm -rf "$S/repo/.git/worktrees"; git -C "$S/repo" branch -q -D lane/alpha 2>/dev/null
done
