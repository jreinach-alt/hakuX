# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check, and the live prediction's
# fixtures. Not executable, no shebang, no exit -- `fail` is shared and is
# the run's verdict.
#
# version_stamp.sh: every build says which commit it is (#433). dispatcher.sh
# guard_not_release_apk: the dispatcher must never install the owner's stable
# channel (com.jreinach.hakux, no suffix) over a lane's run.

echo "== version_stamp.sh: <base>-<MMDD>-<shortsha>[-variant][-dirty]"
VS="$TESTING/version_stamp.sh"
BS="$T/buildstamp"; rm -rf "$BS"; mkdir -p "$BS"

git -c init.defaultBranch=master init -q "$BS"
git -C "$BS" config user.email s@t; git -C "$BS" config user.name s
echo one > "$BS/f"; git -C "$BS" add f
GIT_AUTHOR_DATE="2026-07-04T12:00:00" GIT_COMMITTER_DATE="2026-07-04T12:00:00" \
    git -C "$BS" commit -q -m "base"
SHA=$(git -C "$BS" rev-parse --short HEAD)

OUT=$(bash "$VS" "$BS")
check "  base: 0.4.1-0704-$SHA" [ "$OUT" = "0.4.1-0704-$SHA" ]

OUT=$(bash "$VS" "$BS" perflog)
check "  +perflog suffix" [ "$OUT" = "0.4.1-0704-$SHA-perflog" ]

echo two >> "$BS/f"
OUT=$(bash "$VS" "$BS")
check "  a tracked edit: +dirty" [ "$OUT" = "0.4.1-0704-$SHA-dirty" ]

OUT=$(bash "$VS" "$BS" perflog)
check "  dirty AND perflog: both suffixes, in order" [ "$OUT" = "0.4.1-0704-$SHA-perflog-dirty" ]

git -C "$BS" checkout -q -- f
echo untracked > "$BS/scratch"
OUT=$(bash "$VS" "$BS")
check "  an untracked file alone is not dirty" [ "$OUT" = "0.4.1-0704-$SHA" ]

check "  refuses a non-git tree rather than printing a bogus stamp" \
    bash -c '! bash "$1" "$2"' _ "$VS" "$T"

echo "== dispatcher.sh: never installs the release package (com.jreinach.hakux)"
BZ="$T/buildstamp-apks"; rm -rf "$BZ"; mkdir -p "$BZ"
mkapk() {   # <path> <applicationId>
    python3 -c '
import sys, zipfile
path, appid = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(path, "w") as z:
    z.writestr("AndroidManifest.xml", appid.encode("utf-16-le"))
' "$1" "$2"
}
mkapk "$BZ/release.apk" "com.jreinach.hakux"
mkapk "$BZ/debug.apk" "com.jreinach.hakux.debug"
mkapk "$BZ/debug2.apk" "com.jreinach.hakux.debug2"
mkapk "$BZ/lookalike.apk" "com.jreinach.hakuxextra"
: > "$BZ/empty.apk"

( export DISPATCH_DIR="$T/work/dispatch" SERIAL=ee317437
  . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
  check "  refuses the bare release id" bash -c '! guard_not_release_apk "$1"' _ "$BZ/release.apk"
  check "  allows the .debug id" guard_not_release_apk "$BZ/debug.apk"
  check "  allows the .debug2 id" guard_not_release_apk "$BZ/debug2.apk"
  check "  a different id sharing the release id's prefix is not mistaken for it" \
      guard_not_release_apk "$BZ/lookalike.apk"
  check "  an apk zipfile cannot open (a selftest placeholder) is not refused" \
      guard_not_release_apk "$BZ/empty.apk"
)

echo "== dispatcher.sh: the install-step guard refuses serve_one's own path to install"
# dispatcher.sh sources sibling files by $HERE (its own location), so a
# mutant copied to a bare tmp file breaks at `. devices.sh` before it ever
# reaches serve_one -- which would read as "the guard held" for the wrong
# reason. So the mutant gets the real tree's siblings as symlinks around it,
# the same shape 51-dispatch-hardening.sh's dhmut uses; the real docs/testing
# is never written.
bsdh_tree() {   # <sed-expr for dispatcher.sh, or ""> <name> -> echoes the tree dir
    local expr="$1" dir="$T/build-stamp-dh-$2"
    rm -rf "$dir"; mkdir -p "$dir/jobs"
    local x
    for x in "$TESTING"/*; do [ "$(basename "$x")" = jobs ] || ln -s "$x" "$dir/$(basename "$x")"; done
    for x in "$TESTING"/jobs/*; do ln -s "$x" "$dir/jobs/$(basename "$x")"; done
    rm -f "$dir/dispatcher.sh"
    if [ -n "$expr" ]; then
        sed "$expr" "$TESTING/dispatcher.sh" > "$dir/dispatcher.sh"
        cmp -s "$dir/dispatcher.sh" "$TESTING/dispatcher.sh" && return 1
    else
        cp "$TESTING/dispatcher.sh" "$dir/dispatcher.sh"
    fi
    chmod +x "$dir/dispatcher.sh"
    printf '%s\n' "$dir"
}
dh_fixture() {   # <tree dir> <tag> -> dispatch dir, after one serve_one over it
    local dh="$1/dispatcher.sh" dd="$T/work/dispatch-$2"
    rm -rf "$dd"; mkdir -p "$dd"/{queue,running,results,logs}
    printf '{"id":"relcheck","requester":"selftest","purpose":"p","ref":"HEAD","runs":1}\n' \
        > "$dd/queue/relcheck.req"
    ( export DISPATCH_DIR="$dd" SERIAL=ee317437 BATTERY_ADMIT=off
      . "$dh" selftest-not-a-subcommand >/dev/null 2>&1
      build_ref() { echo "$BZ/release.apk"; }
      device_present() { return 1; }   # stop just after the guard would have fired
      serve_one "$dd/queue/relcheck.req" >/dev/null 2>&1 )
    echo "$dd"
}

REAL_TREE=$(bsdh_tree "" real)
DD=$(dh_fixture "$REAL_TREE" real)
check "  REAL: a release apk is refused before the device is even asked for" \
    [ ! -f "$DD/queue/relcheck.req" ]
check "  REAL: the refusal names the release id" \
    grep -q com.jreinach.hakux "$DD/results/relcheck/ERROR"

# THE MUTANT: dropping the install-step guard (the thing #433 actually added)
# must turn the refusal above into a pass-through -- otherwise the checks
# above are pinning something dispatcher.sh never does anyway.
MUT_TREE=$(bsdh_tree '/^    if ! guard_not_release_apk "\$apk"; then$/,/^    fi$/d' mutant)
check "  MUTANT differs from the real file" [ -n "$MUT_TREE" ]
DD=$(dh_fixture "$MUT_TREE" mutant)
check "  MUTANT: with the guard removed, a release apk reaches the device-presence check (requeued, not refused)" \
    [ -f "$DD/queue/relcheck.req" ]
