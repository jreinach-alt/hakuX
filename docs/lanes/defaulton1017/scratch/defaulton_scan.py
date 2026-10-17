#!/usr/bin/env python3
"""Open forge PRs: grep the lane files each one changes for "default-on" / "default on".

Reads the branch's own changes (origin/master...origin/<head>), so lanes already
folded to master do not show up as candidates.
"""
import json
import os
import re
import subprocess
import urllib.request

W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
FORGE = "http://127.0.0.1:3330/api/v1/repos/jreinach-alt/hakuX"
TOK = open(os.path.expanduser("~/hakux-work/forge/tokens/lanes.token")).read().strip()
PAT = re.compile(r"default[- ]on", re.I)


def get(path):
    req = urllib.request.Request(FORGE + path, headers={"Authorization": "token " + TOK})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def git(*a):
    return subprocess.run(["git", "-C", W, *a], capture_output=True, text=True).stdout


prs, page = [], 1
while True:
    got = get(f"/pulls?state=open&limit=50&page={page}")
    if not got:
        break
    prs += got
    page += 1

for p in prs:
    ref = p["head"]["ref"]
    if ref == "lane/defaulton1017":
        continue
    files = git("diff", "--name-only", f"origin/master...origin/{ref}").split()
    lane = [f for f in files if f.startswith("docs/lanes/") and f.endswith((".md",))]
    hits = []
    for f in lane:
        body = git("show", f"origin/{ref}:{f}")
        for i, ln in enumerate(body.splitlines(), 1):
            if PAT.search(ln):
                hits.append(f"{f}:{i}: {ln.strip()[:180]}")
    print(f"#{p['number']} {ref} ({len(files)} files, {len(hits)} default-on lines)")
    for h in hits[:8]:
        print("    " + h)
