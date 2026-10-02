#!/usr/bin/env bash
# Install the gh shim where the harness's PATH finds it before /usr/bin/gh.
#
#   bash docs/testing/jobs/gh-shim/install.sh            # from this tree
#
# Target: ~/hakux-work/forge/shim/bin/gh (FORGE_SHIM_BIN overrides). The copy is
# atomic, so a job mid-call keeps the old file. Nothing is put on any PATH
# here. Which units see the shim is decided by their drop-ins
# (docs/lanes/localforge/NOTES.md, "Which jobs use the forge").
set -eu
src="$(cd "$(dirname "$0")" && pwd)/gh"
bin="${FORGE_SHIM_BIN:-$HOME/hakux-work/forge/shim/bin}"
mkdir -p "$bin"
tools="${FORGE_TOOLS_BIN:-$HOME/hakux-work/forge/bin}"
mkdir -p "$tools"
put() {  # put <src> <dest>: syntax-check, then an atomic replace
    python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$1"
    cp "$1" "$2.new" && chmod 755 "$2.new" && mv -f "$2.new" "$2"
}
put "$src" "$bin/gh"
put "$(dirname "$src")/forge_prsync.py" "$tools/forge_prsync.py"
echo "installed $bin/gh and $tools/forge_prsync.py from $(dirname "$src") ($(git -C "$(dirname "$src")" rev-parse --short HEAD 2>/dev/null || echo '?'))"
