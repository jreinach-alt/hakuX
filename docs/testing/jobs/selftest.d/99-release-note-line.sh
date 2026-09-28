# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, ok/bad/check. Not executable, no shebang, no exit.
#
# roles/lane.md asks an emulator PR for one body line,
#   Release note (<category>): <what a player notices>
# and nightly_build.sh files the change by it (body_line, then norm_cat).
# Without it a speed fix is filed by keyword guess. This pins the two to
# each other: the doc's example line, with each category it lists put in,
# must come back out of the parser as that category and that text. A reword
# of the doc or a change to the regex fails here, not in a published note.
#
# nightly_build.sh is not run: its two functions are lifted out of the source
# by name and run in a child shell, with NIGHTLY_PR_BODIES pointed at a temp
# dir so body_line never reaches for gh.

echo "== roles/lane.md: the Release note line parses in nightly_build.sh"
RN="$T/relnote"
rm -rf "$RN"; mkdir -p "$RN"

# <doc> <nightly_build.sh> <category> -> 0 when the doc's example line, with
# <category> in it, parses to <category> and the example's text.
cat > "$RN/round_trip.sh" <<'RT'
set -u
doc=$1 nightly=$2 want=$3 dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT
ex=$(grep -oE '`Release note \([a-z|]+\): [^`]+`' "$doc" | tr -d '`')
[ "$(printf '%s\n' "$ex" | grep -c .)" = 1 ] || { echo "doc: not exactly one example line" >&2; exit 1; }
cats=$(sed -E 's/^Release note \(([a-z|]+)\): .*/\1/' <<<"$ex")
text=$(sed -E 's/^Release note \([a-z|]+\): //' <<<"$ex")
[ "$(tr '|' '\n' <<<"$cats" | sort | tr '\n' ' ')" = "none other performance rendering stability " ] \
    || { echo "doc lists categories: $cats" >&2; exit 1; }
eval "$(awk '/^(body_line|norm_cat)\(\) *\{/,/^\}/' "$nightly")"
declare -F body_line >/dev/null && declare -F norm_cat >/dev/null \
    || { echo "nightly_build.sh: body_line or norm_cat not found" >&2; exit 1; }
line=${ex/"($cats)"/"($want)"}
printf '%s\n' "Lane: example            Issue: #1" "" "$line" "" "Body text." > "$dir/1.md"
got=$(NIGHTLY_PR_BODIES="$dir" body_line 1)
[ "$got" = "$want"$'\t'"$text" ] || { echo "body_line gave: $got" >&2; exit 1; }
[ "$(norm_cat "${got%%$'\t'*}")" = "$want" ] || { echo "norm_cat moved $want" >&2; exit 1; }
RT
round_trips() { bash "$RN/round_trip.sh" "$@"; }

DOC="$HERE/roles/lane.md"
NIGHTLY="$TESTING/nightly_build.sh"
for c in performance stability rendering other none; do
    check "the doc's example line parses as $c" round_trips "$DOC" "$NIGHTLY" "$c"
done

# ------------------------------------------------------------ falsifications
# The doc drifts: the category moves out of the parentheses.
sed 's/`Release note (performance|/`Release note: (performance|/' "$DOC" > "$RN/doc-drift.md"
check "falsification ran: the drifted doc differs from the doc" \
    bash -c '! cmp -s "$1" "$2"' _ "$DOC" "$RN/doc-drift.md"
check "FALSIFIED: a reworded example line fails the round trip" \
    bash -c '! bash "$1" "$2" "$3" performance' _ "$RN/round_trip.sh" "$RN/doc-drift.md" "$NIGHTLY"
# The parser drifts: body_line takes the category in brackets, not parentheses.
sed 's/( \\((\[A-Za-z \]+)\\))?:/( \\[([A-Za-z ]+)\\])?:/' "$NIGHTLY" > "$RN/nightly-drift.sh"
check "falsification ran: the drifted parser differs from nightly_build.sh" \
    bash -c '! cmp -s "$1" "$2"' _ "$NIGHTLY" "$RN/nightly-drift.sh"
check "FALSIFIED: a parser that wants the category in brackets fails the round trip" \
    bash -c '! bash "$1" "$2" "$3" performance' _ "$RN/round_trip.sh" "$DOC" "$RN/nightly-drift.sh"
