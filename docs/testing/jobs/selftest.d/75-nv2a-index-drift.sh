# Sourced by ../selftest.sh with the harness already built: $T, $REPO,
# ok/bad/check. Not executable, no shebang, no exit.
#
# nv2a_index.py check: a line shift is not an index change.
#
# The index records every site as file:LINE. When `check` compared bytes, four
# lines inserted at the top of psh.c made CI demand a 125-line index rewrite,
# every lane touching a hot file committed one, and any two open PRs touching
# the same source file then conflicted in the index even when their code never
# met. GitHub runs no CI on a conflicting PR, and on 2026-09-26 four PRs froze
# behind that. Now a site whose anchor (file, role, line text) still matches
# may sit on another line; everything else still fails.
#
# Runs the real cmd_check over a synthetic emulator tree, tests tree and
# tracker, so the suite and tracker halves run too and must stay green.

echo "== nv2a_index.py check: line drift passes, a real site change fails"
DT="$T/drift"; mkdir -p "$DT/emu/hw/xbox/nv2a" "$DT/tests/src/tests"
cat > "$DT/emu/hw/xbox/nv2a/nv2a_regs.h" <<'EOF'
#define NV097_FOO 0x00000100
#define NV097_BAR 0x00000104
#define NV097_BAZ 0x00000108
EOF
cat > "$DT/emu/hw/xbox/nv2a/a.c" <<'EOF'
void f(void)
{
    x = NV097_FOO;
    y = NV097_BAR;
    y = NV097_BAR;
}
void g(void)
{
    w = NV097_BAZ;
}
EOF
cat > "$DT/emu/hw/xbox/nv2a/b.c" <<'EOF'
case NV097_FOO:
    break;
EOF
cat > "$DT/tests/src/tests/foo_tests.cpp" <<'EOF'
static const char *kSuiteName = "Foo suite";
void t() { Push(NV097_FOO); }
EOF
cat > "$DT/issues.toml" <<'EOF'
[issue.1]
title = "fixture"
disposition = "defect"
suites = ["Foo suite"]
EOF
cp -r "$DT/emu" "$DT/pristine"

idx() {   # <build|check|exact> -> check's return code on the first line, its output after
    python3 - "$REPO/docs/testing/nv2a_index.py" "$DT" "$1" <<'PYDRIFT'
import contextlib, importlib.util, io, json, sys
spec = importlib.util.spec_from_file_location("nv2a_index", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
dt, mode = sys.argv[2], sys.argv[3]
m.INDEX_PATH = dt + "/index.json"
m.ISSUES_PATH = dt + "/issues.toml"
if mode == "build":
    with open(m.INDEX_PATH, "w") as fh:
        json.dump(m.build_index(dt + "/emu", dt + "/tests"), fh, indent=1, sort_keys=True)
    print(0)
    sys.exit()
out = io.StringIO()
with contextlib.redirect_stdout(out):
    rc = m.cmd_check(dt + "/emu", dt + "/tests", exact=(mode == "exact"))
print(rc)
print(out.getvalue())
PYDRIFT
}
reset() { rm -rf "$DT/emu"; cp -r "$DT/pristine" "$DT/emu"; }
edit() {  # <file under nv2a/> <python expression over the list `L` of lines>
    python3 - "$DT/emu/hw/xbox/nv2a/$1" "$2" <<'PYEDIT'
import sys
L = open(sys.argv[1]).read().split("\n")
exec(sys.argv[2])
open(sys.argv[1], "w").write("\n".join(L))
PYEDIT
}
rc_of() { idx "$1" | head -1; }

idx build >/dev/null
check "the freshly built index checks" [ "$(rc_of check)" = 0 ]
check "and checks under --exact" [ "$(rc_of exact)" = 0 ]

edit a.c 'L[0:0] = ["/* one */", "", "/* three */", ""]'
out=$(idx check)
check "a pure line shift passes check" [ "$(printf '%s\n' "$out" | head -1)" = 0 ]
check "and is reported as INFO line drift" grep -q "INFO line drift only" <<<"$out"
check "a pure line shift FAILS --exact (the fold's regeneration trigger)" [ "$(rc_of exact)" = 1 ]
reset

edit nv2a_regs.h 'L[0:0] = ["/* header */"]'
check "a line shift in nv2a_regs.h (defined_at) passes check" [ "$(rc_of check)" = 0 ]
reset

edit a.c 'L[0:10] = L[6:10] + L[0:6]'
check "reordering functions within a file passes check" [ "$(rc_of check)" = 0 ]
reset

edit a.c 'L.insert(9, "    v = NV097_BAZ + 1;")'
out=$(idx check)
check "an added site fails check" [ "$(printf '%s\n' "$out" | head -1)" = 1 ]
check "and is named as a new site" grep -q "NV097_BAZ: new REF site in hw/xbox/nv2a/a.c" <<<"$out"
reset

edit b.c 'L[0:2] = ["void h(void) {}"]'
out=$(idx check)
check "a removed site fails check" [ "$(printf '%s\n' "$out" | head -1)" = 1 ]
check "and names the anchor that is gone" grep -q "NV097_FOO: DISPATCH site in hw/xbox/nv2a/b.c: anchor no longer found" <<<"$out"
reset

edit a.c 'del L[4]'
check "removing one of two IDENTICAL lines fails check" [ "$(rc_of check)" = 1 ]
reset

edit a.c 'L[8] = "    w = NV097_BAZ + 0;"'
out=$(idx check)
check "a changed anchor (same line, new text) fails check" [ "$(printf '%s\n' "$out" | head -1)" = 1 ]
check "and names it as an anchor no longer found" grep -q "NV097_BAZ: REF site in hw/xbox/nv2a/a.c: anchor no longer found" <<<"$out"
reset

edit a.c 'L[3] = "    y = NV097_BAZ;"'
check "a renamed site (one symbol's reference becomes another's) fails check" [ "$(rc_of check)" = 1 ]
reset

edit a.c 'del L[8]'
edit b.c 'L.append("    w = NV097_BAZ;")'
out=$(idx check)
check "a site moved to another file fails check" [ "$(printf '%s\n' "$out" | head -1)" = 1 ]
check "and is named as a move across files" grep -q "moved to another file: hw/xbox/nv2a/a.c -> hw/xbox/nv2a/b.c" <<<"$out"
reset

edit nv2a_regs.h 'L[1] = "#define NV097_BAR 0x00000108"'
check "a changed symbol value fails check" [ "$(rc_of check)" = 1 ]
reset

edit a.c 'L[0:0] = ["", ""]'
printf 'static const char *kSuiteName = "Bar suite";\n' > "$DT/tests/src/tests/bar_tests.cpp"
out=$(idx check)
check "line drift does not mask a suite change: check still fails" [ "$(printf '%s\n' "$out" | head -1)" = 1 ]
check "and names the suite" grep -q "Bar suite" <<<"$out"
rm -f "$DT/tests/src/tests/bar_tests.cpp"
reset
