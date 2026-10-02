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
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$src"
cp "$src" "$bin/.gh.new"
chmod 755 "$bin/.gh.new"
mv -f "$bin/.gh.new" "$bin/gh"
echo "installed $bin/gh from $src ($(git -C "$(dirname "$src")" rev-parse --short HEAD 2>/dev/null || echo '?'))"
