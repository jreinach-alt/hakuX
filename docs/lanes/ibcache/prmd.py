#!/usr/bin/env python3
"""Offline PR.md (#507): rewrite its Files: line from `git diff --name-only
origin/master...HEAD` plus any staged/untracked lane files, literally (no
globs), and print whether it matches. Usage: prmd.py"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "PR.md")


def git(*a):
    return subprocess.run(("git",) + a, capture_output=True, text=True,
                          check=True).stdout.split()


files = set(git("diff", "--name-only", "origin/master...HEAD"))
files |= set(git("diff", "--name-only", "--cached"))
files |= set(git("ls-files", "--others", "--exclude-standard", "docs/lanes/ibcache"))
code = sorted(f for f in files if not f.startswith("docs/"))
docs = sorted(f for f in files if f.startswith("docs/"))
line = "Files: " + ", ".join(code + docs)
out = [line if l.startswith("Files:") else l for l in open(P).read().splitlines()]
open(P, "w").write("\n".join(out) + "\n")
print(len(code + docs), "files;", len(code), "outside docs/")
