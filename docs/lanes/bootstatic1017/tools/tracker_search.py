#!/usr/bin/env python3
"""Step 0 tracker search for lane.bootstatic1017.

Reads nv2a_issues.toml off origin/board and lists every issue whose title or
fields mention a launch-time display mechanism. Prints, per issue:
"<n> | <status> | <title> | <which terms matched, and in which field>".

Usage: tracker_search.py <repo>
"""
import re
import subprocess
import sys
import tomllib

TERMS = [
    r"\bboot", r"launch", r"first frame", r"first present", r"black screen", r"static",
    r"\bgreen", r"flash", r"garbage", r"noise", r"uninitiali", r"splash", r"startup",
    r"start-?up", r"title start", r"\bintro", r"logo", r"swapchain", r"\bpcrtc", r"video mode",
    r"pvideo", r"overlay", r"\byuv", r"blank", r"flicker", r"corrupt",
]


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "/home/justin/hakux-work/wt/bootstatic1017"
    raw = subprocess.run(["git", "-C", repo, "show", "origin/board:nv2a_issues.toml"],
                         check=True, capture_output=True).stdout
    data = tomllib.loads(raw.decode())
    issues = data.get("issue", {})
    print(f"# {len(issues)} issues in origin/board:nv2a_issues.toml")
    for n, row in sorted(issues.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        title = str(row.get("title", ""))
        hits = []
        for t in TERMS:
            if re.search(t, title, re.I):
                hits.append(f"{t}@title")
        # Only the title decides a listing; other fields are scanned for the
        # two looks alone, since every field mentions "launch" or "boot" in
        # passing (a soak's route, a dispatcher note).
        for k, v in row.items():
            if k == "title":
                continue
            s = str(v)
            for t in (r"\bstatic\b", r"\bgreen\b", r"garbage", r"first frame", r"black screen",
                      r"uninitiali", r"\bflash\b"):
                if re.search(t, s, re.I):
                    hits.append(f"{t}@{k}")
        if hits:
            print(f"{n} | {row.get('status', '?')} | {title[:110]} | {', '.join(sorted(set(hits)))}")


if __name__ == "__main__":
    main()
