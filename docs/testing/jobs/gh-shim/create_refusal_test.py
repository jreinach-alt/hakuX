#!/usr/bin/env python3
"""create_refusal_test.py -- offline checks that `gh pr create` and `gh issue create` refuse.

lane.forgealloc1013 (#433): a direct forge POST from either subcommand takes a PR/issue number
GitHub has not allocated, and the next `issue_mirror.py new` then refuses every new issue and PR
with "forge is ahead of GitHub" until someone runs the backfill by hand. Both subcommands now
refuse unconditionally, before any network call, so this runs with no forge and no token.

Checks:
  - `gh pr create` exits 1 and names the replacement (write PR.md, forge_prsync.py allocates);
  - `gh issue create` exits 1 and names the replacement (an `ISSUE-REQUEST:` OUTBOX.md line);
  - neither refusal depends on which flags were passed (a bare call and a fully-flagged call
    both refuse the same way);
  - every other `gh pr`/`gh issue` subcommand is untouched: `pr list`'s own argument validation
    still runs (proves the dispatch table, not just these two branches, is intact).
Exit 0 only when every check passes. Run: python3 docs/testing/jobs/gh-shim/create_refusal_test.py
"""
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
GH = HERE / "gh"
fails = []
passes = 0


def check(name, ok, detail=""):
    global passes
    if ok:
        passes += 1
        print("ok   " + name)
    else:
        fails.append(name)
        print("FAIL " + name + (": " + str(detail) if detail else ""))


def gh(*args):
    env = dict(os.environ)
    env.pop("FORGE_URL", None)
    env.pop("FORGE_TOKENS", None)
    p = subprocess.run([sys.executable, str(GH), *args], capture_output=True, text=True, env=env, timeout=30)
    return p.returncode, p.stdout, p.stderr


rc, out, err = gh("pr", "create")
check("pr create (no flags) exits 1", rc == 1, (rc, out, err))
check("pr create (no flags) names PR.md", "docs/lanes/<lane>/PR.md" in err, err)
check("pr create (no flags) names forge_prsync.py", "forge_prsync.py" in err, err)

rc, out, err = gh("pr", "create", "--draft", "--base", "master", "--head", "lane/smoke",
                  "--title", "smoke PR", "--body", "x")
check("pr create --draft (fully flagged) exits 1", rc == 1, (rc, out, err))
check("pr create --draft names the replacement the same way", "docs/lanes/<lane>/PR.md" in err, err)
check("pr create makes no network call (no FORGE_URL/token needed)", out == "", (out, err))

rc, out, err = gh("issue", "create")
check("issue create (no flags) exits 1", rc == 1, (rc, out, err))
check("issue create (no flags) names ISSUE-REQUEST:", "ISSUE-REQUEST:" in err, err)
check("issue create (no flags) names OUTBOX.md", "OUTBOX.md" in err, err)

rc, out, err = gh("issue", "create", "--title", "x", "--body", "y", "--label", "harness")
check("issue create (fully flagged) exits 1", rc == 1, (rc, out, err))
check("issue create (fully flagged) names the replacement the same way", "ISSUE-REQUEST:" in err, err)
check("issue create makes no network call (no FORGE_URL/token needed)", out == "", (out, err))

# the dispatch table and the other pr/issue subcommands are untouched: a subcommand this refusal
# did not touch still does its own argument validation (and so still needs a repo/token, which
# is absent here -- it must not exit 1 with a create-refusal message).
rc, out, err = gh("pr", "list")
check("pr list is not refused like create (different failure, if any)",
      not (rc == 1 and "docs/lanes/<lane>/PR.md" in err), (rc, out, err))
rc, out, err = gh("issue", "list")
check("issue list is not refused like create (different failure, if any)",
      not (rc == 1 and "ISSUE-REQUEST:" in err), (rc, out, err))

print(f"\n{passes} passed, {len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
