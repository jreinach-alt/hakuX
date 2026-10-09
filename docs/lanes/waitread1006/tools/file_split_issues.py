#!/usr/bin/env python3
"""File the drafts in issues/split-drafts.md as forge issues, once each.

Usage: file_split_issues.py [--dry-run]

Each "## N. [#parent] title" section becomes one issue. The body is the
section's text after its title line, with the "Parent:" line kept as the first
line of the body. Prints the issue URL that gh returns for each draft, so the
numbers can be copied into OUTBOX.md.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(HERE, "..", "issues", "split-drafts.md")
HEAD = re.compile(r"^## \d+\. (\[#\d+\] .+)$")


def sections(text):
    out = []
    cur = None
    for line in text.splitlines():
        m = HEAD.match(line)
        if m:
            if cur:
                out.append(cur)
            cur = {"title": m.group(1), "body": []}
        elif line.strip() == "---":
            continue
        elif cur is not None:
            cur["body"].append(line)
    if cur:
        out.append(cur)
    for s in out:
        s["body"] = "\n".join(s["body"]).strip() + "\n"
    return out


def main(dry):
    with open(DRAFTS) as f:
        items = sections(f.read())
    for s in items:
        if dry:
            print("DRY", s["title"][:90])
            continue
        proc = subprocess.run(
            ["gh", "issue", "create", "--title", s["title"], "--body", s["body"]],
            capture_output=True, text=True)
        print("rc=%d %s %s" % (proc.returncode, s["title"][:70], (proc.stdout or proc.stderr).strip()))


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
