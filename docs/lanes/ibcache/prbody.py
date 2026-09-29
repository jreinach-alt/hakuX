#!/usr/bin/env python3
"""Rewrite PR #591's Files:/Base: lines and the legs table rows from the
branch state, PATCH the body over REST, and read it back (gh pr edit applies
nothing here). Usage: prbody.py <base sha>"""
import json
import subprocess
import sys

PR = "591"
base = sys.argv[1]


def run(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, check=True, **k).stdout


files = run("git", "diff", "--name-only", "origin/master...HEAD").split()
body = run("gh", "pr", "view", PR, "--json", "body", "-q", ".body")
rows = {
    "| 3b pixels": "| 3b pixels, the flip band, three runs per arm | nothing moves outside the measured band | by hand (`bandread.py`): 0 captures self-identical in each arm and different between them; master's arm flips 5 of 67 on its own | **PASS** (`[job.arms]`, all 69 checks, 2026-09-29 08:43 PDT) |",
    "| 4 title soaks": "| 4 title soaks, three titles | gameplay, no new crash or hang | GTA pilot (Thor): gameplay, no crash, both arms thermally paused; runs moved to the Nova 09-29: Crimson Skies: A1 ran (gameplay, no crash or hang, 0.245 J/frame), B, A, B queued; Alien Hominid and GTA wait on their Nova copies | waiting |",
    "| 5 fps and J/frame": "| 5 fps and J/frame | 5a GTA: no regression; 5b below-cap title: fps +5%, J/frame -4% | GTA pilot void (thermal pause 74 s after the mark in both arms); 5a moves to the Nova (GTA copy pending); Crimson queued on the Nova; Forza waits on #583 | waiting |",
}
out = []
for line in body.splitlines():
    if line.startswith("Files:"):
        line = "Files: " + ", ".join(files)
    elif line.startswith("Base:"):
        line = f"Base: master @ {base} (merged; branched from be05285c44)"
    else:
        for k, v in rows.items():
            if line.startswith(k):
                line = v
    out.append(line)
new = "\n".join(out) + "\n"
run("gh", "api", "-X", "PATCH", f"repos/{{owner}}/{{repo}}/pulls/{PR}",
    "--input", "-", input=json.dumps({"body": new}))
back = run("gh", "pr", "view", PR, "--json", "body", "-q", ".body")
fl = [l for l in back.splitlines() if l.startswith("Files:")][0]
got = [f.strip() for f in fl[len("Files:"):].split(",")]
print("Files match diff:", got == files, len(files), "files")
for l in back.splitlines():
    if l.startswith(("Base:", "| 3b", "| 4 ", "| 5 ")):
        print(l)
