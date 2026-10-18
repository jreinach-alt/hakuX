#!/usr/bin/env python3
"""Forge issue search with the lanes token, and one write: a comment on an issue.

usage: forgeq.py search <words...>      issues (open and closed) whose title/body match
       forgeq.py issue <n>              one issue's title, state and body
       forgeq.py comments <n> [last]    its comments (the last N, default 5)
       forgeq.py prs <words...>         open PRs whose title/body mention all the words
       forgeq.py post <n> <body-file>   post the file as a comment on issue <n>; prints the comment id
"""
import json
import os
import sys
import urllib.parse
import urllib.request

FORGE = "http://127.0.0.1:3330/api/v1/repos/jreinach-alt/hakuX"
TOK = open(os.path.expanduser("~/hakux-work/forge/tokens/lanes.token")).read().strip()


def get(path, **q):
    url = FORGE + path + ("?" + urllib.parse.urlencode(q) if q else "")
    req = urllib.request.Request(url, headers={"Authorization": "token " + TOK})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    cmd = sys.argv[1]
    if cmd == "search":
        q = " ".join(sys.argv[2:])
        for st in ("open", "closed"):
            for it in get("/issues", state=st, type="issues", q=q, limit=50):
                print(f"#{it['number']} [{st}] {it['title']}")
    elif cmd == "issue":
        it = get(f"/issues/{sys.argv[2]}")
        print(f"#{it['number']} [{it['state']}] {it['title']}\n")
        print(it["body"])
    elif cmd == "prs":
        # open PRs whose title or body mentions every given word (case-insensitive)
        words = [w.lower() for w in sys.argv[2:]]
        page = 1
        while True:
            prs = get("/pulls", state="open", limit=50, page=page)
            if not prs:
                break
            for p in prs:
                text = (p["title"] + "\n" + (p["body"] or "")).lower()
                if all(w in text for w in words):
                    hits = [ln.strip() for ln in (p["body"] or "").splitlines()
                            if words and words[0] in ln.lower()]
                    print(f"#{p['number']} {p['head']['ref']} {p['title']}")
                    for ln in hits[:4]:
                        print(f"    {ln[:200]}")
            page += 1
    elif cmd == "post":
        body = json.dumps({"body": open(sys.argv[3]).read()}).encode()
        req = urllib.request.Request(FORGE + f"/issues/{sys.argv[2]}/comments", data=body, method="POST",
                                     headers={"Authorization": "token " + TOK,
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            c = json.load(r)
        print(f"posted comment {c['id']} on #{sys.argv[2]}")
    elif cmd == "comments":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        cs = get(f"/issues/{sys.argv[2]}/comments", limit=50)
        for c in cs[-n:]:
            print(f"--- {c['id']} {c['created_at']} {c['user']['login']}\n{c['body']}\n")


if __name__ == "__main__":
    main()
