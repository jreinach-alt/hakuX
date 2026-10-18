#!/usr/bin/env python3
"""Step 0 forge-issue search for lane.bootstatic1017 (read-only GETs).

Searches the local forge's issues (open and closed) for each launch-time term,
with the `lanes` token. Prints "<term>: #<n> [state] <title>" per hit, deduped
per term. Never writes to the forge.

Usage: forge_search.py
"""
import json
import pathlib
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:3330/api/v1/repos/jreinach-alt/hakuX/issues"
TOKEN = pathlib.Path("/home/justin/hakux-work/forge/tokens/lanes.token").read_text().strip()
TERMS = ["boot", "launch", "first frame", "black screen", "static", "green", "flash", "garbage",
         "noise", "splash", "startup", "start-up", "intro", "logo", "blank", "corrupt", "distortion",
         "title start", "pvideo", "overlay", "swapchain", "video mode"]


def get(term, page):
    q = urllib.parse.urlencode({"state": "all", "type": "issues", "limit": 50, "page": page, "q": term})
    req = urllib.request.Request(f"{BASE}?{q}", headers={"Authorization": f"token {TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    for term in TERMS:
        seen = {}
        for page in range(1, 6):
            rows = get(term, page)
            if not rows:
                break
            for row in rows:
                seen[row["number"]] = (row["state"], row["title"])
        print(f"=== {term}: {len(seen)}")
        for n in sorted(seen):
            st, title = seen[n]
            print(f"#{n} [{st}] {title[:120]}")


if __name__ == "__main__":
    main()
