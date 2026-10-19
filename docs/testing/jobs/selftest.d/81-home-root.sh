# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# home_page.py / status_md.py (lane homeroot1018, #433): the `home` branch's root
# carried chart.svg, chart2.svg and COPYING.LIB beside its markdown files, which the
# owner called sloppy. The charts move to docs/images/, the licence text to
# docs/licenses/; home's root keeps only LICENSE and COPYING for GitHub to read.
#
# These two scripts are not in this repository (they run from
# /home/justin/hakux-work/host-tools/ on the host); this lane's edited copies live at
# docs/lanes/homeroot1018/host-tools/. This fragment runs them against a throwaway
# git repo standing in for the offline mirror, never the real one, and never pushes
# anything -- home_page.py's own G is pointed at the scratch repo before any call.
#
# Each case runs once on the lane's edited copies and once per mutant that reverts
# one piece of the move back to the pre-fix path; a case that stays green under the
# mutant that removes the behaviour it names checks nothing.
#   root     home's root carries no chart.svg, chart2.svg or COPYING.LIB   (mutant: old STATUS_FILES/RENAME)
#   nested   the charts and the licence land at their docs/ paths          (mutant: old STATUS_FILES/RENAME)
#   links    STATUS.md's chart images point at docs/images/...            (mutant: old link text)
#   rewrite  CONTRIBUTING.md's COPYING.LIB link follows it to docs/licenses/   (mutant: old STATUS_FILES/RENAME)
#   stable   a second update with the same inputs is a no-op (home_page.py's own idempotence; not mutant-sensitive)
#
# Independent of every other fragment: its own scratch repo, work dir and sys.path.

echo "== home_page.py/status_md.py: home's root carries no SVG or .LIB file (#433)"
HR="$T/homeroot"; rm -rf "$HR"; mkdir -p "$HR"
HOST_TOOLS="$REPO/docs/lanes/homeroot1018/host-tools"

hr_seed_master() {   # <repo dir>: a `master` branch with the minimal FILES set home_page.py requires
    local M=$1
    rm -rf "$M"; mkdir -p "$M/.github/ISSUE_TEMPLATE"
    git -C "$M" init -q -b master
    printf '# hakuX\n\nSee [LICENSE](LICENSE), [COPYING](COPYING) and [COPYING.LIB](COPYING.LIB).\n\n## Credits\n\nThanks.\n' > "$M/README.md"
    printf 'Licensed under [LICENSE](LICENSE), [COPYING](COPYING) and [COPYING.LIB](COPYING.LIB). No CLA.\n' > "$M/CONTRIBUTING.md"
    printf 'none\n' > "$M/KNOWN_ISSUES.md"
    printf 'none\n' > "$M/PRIVACY.md"
    printf 'none\n' > "$M/CHANGELOG.md"
    printf 'LICENSE text\n' > "$M/LICENSE"
    printf 'COPYING text\n' > "$M/COPYING"
    printf 'COPYING.LIB text\n' > "$M/COPYING.LIB"
    printf 'none\n' > "$M/.github/FUNDING.yml"
    printf 'none\n' > "$M/.github/pull_request_template.md"
    printf 'none\n' > "$M/.github/ISSUE_TEMPLATE/config.yml"
    printf 'none\n' > "$M/.github/ISSUE_TEMPLATE/feature-request.yml"
    printf 'none\n' > "$M/.github/ISSUE_TEMPLATE/general-issue.yml"
    printf 'none\n' > "$M/.github/ISSUE_TEMPLATE/title-issue.yml"
    git -C "$M" add -A
    git -C "$M" -c user.email=t@example.invalid -c user.name=t commit -q -m seed >/dev/null
}

# A synthetic index.html with two inline charts, just enough of the markup
# status_md.py's parser and chart_svg() need: a <main>, a <style> block (chart_svg
# splits it for inline CSS; empty is fine), and two raw <svg class="chart"> tags.
HR_HTML='<html><style></style><main><div><svg class="chart" viewBox="0 0 1 1"></svg></div><div><svg class="chart" viewBox="0 0 1 1"></svg></div></main></html>'

hr_run() {   # <host-tools dir> <scratch repo dir> <out file>: one home_page.update(), from a fresh master
    local HT=$1 G=$2 OUT=$3
    hr_seed_master "$G"
    HR_HTML="$HR_HTML" python3 - "$HT" "$G" <<'PYEOF' > "$OUT" 2>&1
import os, sys
ht, g = sys.argv[1], sys.argv[2]
sys.path.insert(0, ht)
import home_page, status_md

home_page.G = g
md, charts = status_md.build(os.environ["HR_HTML"])
h = lambda t: home_page.git("hash-object", "-w", "--stdin", inp=t.encode("utf-8")).decode().strip()
# The chart keys status_page.py's dashboard_blobs() would hand to update(): one per chart,
# in STATUS_FILES order (home_page.py's own say for where a chart belongs on home).
chart_names = [p for p in home_page.STATUS_FILES if p != "STATUS.md"]
blobs = {"STATUS.md": h(md)}
for name, svg in zip(chart_names, charts):
    blobs[name] = h(svg)

c1 = home_page.update(blobs, playable=None)
print("commit1", c1)
names = home_page.git("ls-tree", "-r", "--name-only", "home").decode().splitlines()
root = sorted(set(n.split("/", 1)[0] for n in names))
print("root", " ".join(root))
print("names", " ".join(sorted(names)))
status_blob = [n.split()[2] for n in home_page.git("ls-tree", "-r", "home").decode().splitlines() if n.endswith("\tSTATUS.md")][0]
print("status.md-text-begin")
print(home_page.git("cat-file", "blob", status_blob).decode("utf-8"))
print("status.md-text-end")
contrib_blob = [n.split()[2] for n in home_page.git("ls-tree", "-r", "home").decode().splitlines() if n.endswith("\tCONTRIBUTING.md")][0]
print("contributing-text-begin")
print(home_page.git("cat-file", "blob", contrib_blob).decode("utf-8"))
print("contributing-text-end")

c2 = home_page.update(blobs, playable=None)
print("commit2", c2 if c2 else "None")
PYEOF
}

hr_scenario() {   # <host-tools dir> <out file prefix>: writes "<case> ok|FAIL ..." lines, one per case, to <prefix>.txt
    local HT=$1 P=$2
    local RAW="$HR/$P-raw.txt"
    hr_run "$HT" "$HR/repo-$P" "$RAW"
    local names root status contrib
    names=$(sed -n 's/^names //p' "$RAW")
    root=$(sed -n 's/^root //p' "$RAW")
    status=$(sed -n '/^status.md-text-begin$/,/^status.md-text-end$/p' "$RAW")
    contrib=$(sed -n '/^contributing-text-begin$/,/^contributing-text-end$/p' "$RAW")
    {
        if ! grep -qw 'chart.svg' <<< "$root" && ! grep -qw 'chart2.svg' <<< "$root" && ! grep -qw 'COPYING.LIB' <<< "$root"; then
            echo "root ok"
        else echo "root FAIL home's root still carries a bare chart.svg/chart2.svg/COPYING.LIB: $root"; fi
        if grep -q 'docs/images/chart.svg' <<< "$names" && grep -q 'docs/images/chart2.svg' <<< "$names" \
           && grep -q 'docs/licenses/COPYING.LIB' <<< "$names"; then
            echo "nested ok"
        else echo "nested FAIL the docs/ paths are not all in the tree: $names"; fi
        if grep -q '](docs/images/chart.svg)' <<< "$status" && grep -q '](docs/images/chart2.svg)' <<< "$status" \
           && ! grep -q '](chart.svg)' <<< "$status" && ! grep -q '](chart2.svg)' <<< "$status"; then
            echo "links ok"
        else echo "links FAIL STATUS.md's chart links are not docs/images/...: $(tr '\n' '|' <<< "$status")"; fi
        if grep -q '(docs/licenses/COPYING.LIB)' <<< "$contrib" && ! grep -q '](COPYING.LIB)' <<< "$contrib"; then
            echo "rewrite ok"
        else echo "rewrite FAIL CONTRIBUTING.md's COPYING.LIB link did not follow the rename: $(tr '\n' '|' <<< "$contrib")"; fi
        if grep -q '^commit2 None$' "$RAW"; then echo "stable ok"
        else echo "stable FAIL a repeat update() was not a no-op: $(grep '^commit2' "$RAW")"; fi
    } > "$HR/$P.txt"
}

hr_scenario "$HOST_TOOLS" real
check "real scripts: root"     grep -q '^root ok'     "$HR/real.txt"
check "real scripts: nested"   grep -q '^nested ok'   "$HR/real.txt"
check "real scripts: links"    grep -q '^links ok'    "$HR/real.txt"
check "real scripts: rewrite"  grep -q '^rewrite ok'  "$HR/real.txt"
check "real scripts: stable"   grep -q '^stable ok'   "$HR/real.txt"
grep 'FAIL' "$HR/real.txt" | sed 's/^/    /'

hr_mutant() {   # <name> <file> <python re.sub pattern> <replacement>: a copy of the lane's
                # host-tools with one piece of the move reverted to its pre-fix form
    local NAME=$1 FILE=$2 PAT=$3 REP=$4 M="$HR/mut-$1"
    rm -rf "$M"; mkdir -p "$M"
    cp "$HOST_TOOLS"/*.py "$M/"
    python3 -c '
import re, sys
p, pat, rep = sys.argv[1:4]
s = open(p).read(); t, n = re.subn(pat, rep, s)
if n != 1: sys.exit("mutant pattern matched %d times in %s" % (n, p))
open(p, "w").write(t)' "$M/$FILE" "$PAT" "$REP" || return 2
    hr_scenario "$M" "mut-$NAME"
}
hr_red() {   # <mutant> <case>: the mutant applied, and turned that case red
    hr_mutant "$1" "$3" "$4" "$5" && grep -q "^$2 FAIL" "$HR/mut-$1.txt"
}
hr_mutant_oldpaths() {   # <name>: both RENAME and STATUS_FILES reverted to their pre-fix, root-level form
    local M="$HR/mut-$1"
    rm -rf "$M"; mkdir -p "$M"
    cp "$HOST_TOOLS"/*.py "$M/"
    python3 -c '
import re, sys
p = sys.argv[1]
s = open(p).read()
s, n1 = re.subn(r"RENAME = \{\"COPYING\.LIB\": \"docs/licenses/COPYING\.LIB\"\}", "RENAME = {}", s)
s, n2 = re.subn(r"STATUS_FILES = \(\"STATUS\.md\", \"docs/images/chart\.svg\", \"docs/images/chart2\.svg\"\)",
                "STATUS_FILES = (\"STATUS.md\", \"chart.svg\", \"chart2.svg\")", s)
if (n1, n2) != (1, 1): sys.exit("oldpaths mutant matched %d/%d times in %s" % (n1, n2, p))
open(p, "w").write(s)' "$M/home_page.py" || return 2
    hr_scenario "$M" "mut-$1"
}
hr_oldpaths_root()   { hr_mutant_oldpaths oldpaths  && grep -q "^root FAIL"   "$HR/mut-oldpaths.txt"; }
hr_oldpaths_nested()  { hr_mutant_oldpaths oldpaths2 && grep -q "^nested FAIL" "$HR/mut-oldpaths2.txt"; }
check "mutant: old RENAME/STATUS_FILES -> root goes red"   hr_oldpaths_root
check "mutant: old RENAME/STATUS_FILES -> nested goes red" hr_oldpaths_nested
check "mutant: old RENAME -> rewrite goes red" \
    hr_red oldrename rewrite home_page.py \
    'RENAME = \{"COPYING\.LIB": "docs/licenses/COPYING\.LIB"\}' 'RENAME = {}'
check "mutant: old chart link text -> links goes red" \
    hr_red oldlinks links status_md.py \
    '"!\[Titles over time\]\(docs/images/chart\.svg\)"' '"![Titles over time](chart.svg)"'
