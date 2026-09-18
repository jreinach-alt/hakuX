#!/usr/bin/env bash
#
# Create the orphan `board` branch from the current board files, once.
#
#   docs/testing/jobs/bootstrap-board-branch.sh [source-ref]
#
# After this, board_files.py reads territory.toml and nv2a_issues.toml from
# origin/board and the copies on master are a fallback that the board job
# stops updating. Refuses to run if origin/board already exists.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SRC="${1:-HEAD}"
cd "$REPO"
git fetch -q origin
if git rev-parse --verify --quiet refs/remotes/origin/board >/dev/null; then
    echo "origin/board already exists; nothing to do" >&2; exit 0
fi
tmp=$(mktemp -d)
git worktree add --quiet --detach "$tmp" "$SRC"
(
  cd "$tmp"
  git checkout -q --orphan board
  git rm -rfq . >/dev/null
  git show "$SRC:docs/testing/territory.toml" > territory.toml
  git show "$SRC:docs/testing/nv2a_issues.toml" > nv2a_issues.toml
  mkdir -p briefs
  cat > README.md <<'MD'
# The hakuX board branch

Orphan branch. Holds the derived views of the board -- `territory.toml` and
`nv2a_issues.toml` -- plus `briefs/<lane>.md`. Written by the board job only.
Lanes read it with `git show origin/board:<file>`; `docs/testing/board_files.py`
does that for the checkers. Never merged into master; never carried by a lane.
MD
  git add -A
  git -c user.name="hakux-board" -c user.email="board@hakux.invalid" commit -q -m "board: bootstrap from $(git rev-parse --short "$SRC")"
  git push -q origin board
)
git worktree remove --force "$tmp"
echo "origin/board created from $SRC"
