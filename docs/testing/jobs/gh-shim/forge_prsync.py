#!/usr/bin/env python3
"""Keep one forge PR per unfolded lane branch, written from the branch's PR.md.

  forge_prsync.py [--execute] [--repo OWNER/NAME] [--git-dir BARE]

The offline protocol (2026-09-29) made a lane's PR the file
docs/lanes/<lane>/PR.md on its branch:
  * line 1 is `# <title>`;
  * a line reads `State: draft` or `State: ready`;
  * the rest is the body.
This script turns that file into a forge PR. Only the PR.md file is read, so
lanes keep writing it and change nothing else:

  * Branch lane/<x> has docs/lanes/<x>/PR.md and holds commits master lacks,
    and has no open forge PR: open one, as the `lanes` user, head lane/<x>,
    base master.
  * The open PR's title, body or draft state differs from PR.md: update it.
    Draft is Forgejo's "WIP: " title prefix.
  * The branch is folded (its head is an ancestor of master) and the PR is
    still open: close it with a [job.forge-prsync] comment naming the master
    sha. Forgejo's own manual-merge detection usually marks it merged first.
  * PR.md is gone from the branch: report it, and touch nothing.

The bare repo (~/hakux-work/offline-git/hakuX.git) is the source of truth.
The forge copy lags it by about a minute. A branch the forge does not have
yet is skipped and picked up on the next run.

Dry run by default. Exit 1 if any forge call failed.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

FORGE = os.environ.get("FORGE_URL", "http://127.0.0.1:3330")
TOKENS = os.environ.get("FORGE_TOKENS", os.path.expanduser("~/hakux-work/forge/tokens"))
WIP = "WIP: "


def git(gd, *a, check=True):
    p = subprocess.run(["git", "--git-dir", gd] + list(a), capture_output=True, text=True)
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(a)}: {p.stderr.strip()[:200]}")
    return p


class Forge:
    def __init__(self, repo, user):
        self.repo, self.tok = repo, open(os.path.join(TOKENS, user + ".token")).read().strip()

    def call(self, method, path, body=None, query=None, ok404=False):
        url = FORGE + "/api/v1/repos/" + self.repo + path + ("?" + urllib.parse.urlencode(query) if query else "")
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Authorization", "token " + self.tok)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                b = r.read()
                return json.loads(b) if b.strip() else None
        except urllib.error.HTTPError as e:
            if ok404 and e.code == 404:
                return None
            raise RuntimeError(f"HTTP {e.code} {method} {path}: {e.read()[:200]!r}") from None

    def all(self, path, query=None):
        out, page = [], 1
        while True:
            rows = self.call("GET", path, query=dict(query or {}, page=page, limit=50))
            out += rows
            if len(rows) < 50:
                return out
            page += 1


def parse_prmd(text):
    lines = text.splitlines()
    title = re.sub(r"^#\s*", "", lines[0]).strip() if lines and lines[0].startswith("#") else ""
    m = re.search(r"(?mi)^State:\s*(draft|ready)\b", text)
    return title, (m.group(1).lower() if m else "draft"), text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GH_REPO", "jreinach-alt/hakuX"))
    ap.add_argument("--git-dir", default=os.path.expanduser("~/hakux-work/offline-git/hakuX.git"))
    ap.add_argument("--base", default="master")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    gd = a.git_dir
    lanes = Forge(a.repo, "lanes")
    jobs = Forge(a.repo, "jobs")
    errors = 0
    master = git(gd, "rev-parse", f"refs/heads/{a.base}").stdout.strip()
    prs = lanes.all("/pulls", dict(state="all"))
    open_by_head = {}
    for p in prs:
        if p["state"] == "open":
            open_by_head.setdefault(p["head"]["ref"], p)
    refs = git(gd, "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads/lane/").stdout.split("\n")
    seen = 0
    for line in filter(None, refs):
        br, sha = line.split()
        name = br[len("lane/"):]
        prmd = git(gd, "show", f"{sha}:docs/lanes/{name}/PR.md", check=False)
        pr = open_by_head.get(br)
        folded = git(gd, "merge-base", "--is-ancestor", sha, master, check=False).returncode == 0
        if prmd.returncode:
            if pr:
                print(f"{br}: open forge PR #{pr['number']} but no PR.md on the branch; left alone")
            continue
        seen += 1
        title, state, body = parse_prmd(prmd.stdout)
        want_title = (WIP if state == "draft" else "") + (title or br)
        try:
            if folded:
                if pr:
                    print(f"{br}: folded into {a.base} ({master[:10]}); closing #{pr['number']}")
                    if a.execute:
                        jobs.call("POST", f"/issues/{pr['number']}/comments", dict(
                            body=f"[job.forge-prsync] {br} @ {sha[:10]} is in {a.base} @ {master[:10]} "
                                 f"(folded by offline-git/foldqueue.sh); closing."))
                        jobs.call("PATCH", f"/pulls/{pr['number']}", dict(state="closed"))
                continue
            if pr is None:
                if lanes.call("GET", "/branches/" + urllib.parse.quote(br, safe=""), ok404=True) is None:
                    print(f"{br}: not in the forge yet (hakux-forge-sync lag); next run")
                    continue
                print(f"{br}: opening a forge PR ({state}): {title[:90]}")
                if a.execute:
                    p = lanes.call("POST", "/pulls", dict(head=br, base=a.base, title=want_title, body=body))
                    print(f"  -> #{p['number']} {p['html_url']}")
                continue
            if (pr["title"], pr.get("body") or "") != (want_title, body):
                what = [w for w, c in (("title/draft", pr["title"] != want_title), ("body", (pr.get("body") or "") != body)) if c]
                print(f"{br}: #{pr['number']} updating {', '.join(what)} ({state})")
                if a.execute:
                    lanes.call("PATCH", f"/pulls/{pr['number']}", dict(title=want_title, body=body))
        except RuntimeError as e:
            errors += 1
            print(f"{br}: FAILED: {e}", file=sys.stderr)
    print(f"{'EXECUTED' if a.execute else 'DRY RUN'}: {seen} lane branches with PR.md; "
          f"{len(open_by_head)} open forge PRs before this run; {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
