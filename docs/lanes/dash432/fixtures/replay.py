#!/usr/bin/env python3
"""Replay the 16:24 fixture's GitHub and systemd answers: `gh`, `systemctl`, `adb`.

Installed by run_fixture.sh as three wrappers on PATH that name their tool
as the first argument. FIXTURE_SRC names the fixture's src/.
"""
import json, os, subprocess, sys

SRC = os.environ["FIXTURE_SRC"]
tool, a = sys.argv[1], sys.argv[2:]


def opt(name, default=None):
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def emit(obj):
    jq = opt("--jq") or opt("-q")
    s = json.dumps(obj)
    if jq is None:
        print(s)
        return
    p = subprocess.run(["jq", "-r", "-c", jq], input=s, capture_output=True, text=True)
    sys.stdout.write(p.stdout)


def gh():
    g = json.load(open(os.path.join(SRC, "gh.json")))
    cmd = " ".join(a[:2])
    if cmd == "auth status":
        return 0
    if cmd == "pr list":
        prs = g["prs"]
        if opt("--head"):
            prs = [p for p in prs if p["headRefName"] == opt("--head")]
        if opt("--state") == "open":
            prs = [p for p in prs if p["state"] == "OPEN"]
        if opt("--label"):
            prs = [p for p in prs if opt("--label") in {l["name"] for l in p.get("labels", [])}]
        emit(prs)
        return 0
    if cmd == "issue list":
        lab = opt("--label")
        emit({"0.5": g["issues_05"], "blocked:after-0.5": g["issues_parked"],
              "decision-needed": g["decision_needed"]}.get(lab, []))
        return 0
    if cmd == "release list":
        emit([{"tagName": t} for t in g.get("releases", [])])
        return 0
    if cmd in ("run list",):
        emit([])
        return 0
    if a and a[0] == "api":
        path = next((x for x in a[1:] if not x.startswith("-") and "/" in x), "")
        if "issues/comments?since=" in path:
            since = path.split("since=")[1].split("&")[0]
            emit([{"created_at": c["c"], "issue_url": "https://api.github.com/repos/x/y/issues/" + c["i"],
                   "body": c["b"], "html_url": "https://github.com/jreinach-alt/hakuX/issues/%s" % c["i"]}
                  for c in g["comments"] if c["c"] >= since])
            return 0
        if "/events" in path:
            emit([])
        return 0
    return 0


def systemctl():
    s = json.load(open(os.path.join(SRC, "systemd.json")))
    b = [x for x in a if x != "--user"]
    if not b:
        return 0
    if b[0] == "list-units":
        pat = next((x for x in b[1:] if not x.startswith("-")), "")
        if pat.startswith("hakux-lane-") and "failed" not in " ".join(b):
            for u in sorted(x for x in s["units"] if x.startswith("hakux-lane-")):
                print("%s loaded active running %s" % (u, u))
        return 0
    if b[0] == "list-timers":
        for n, (nxt, last) in sorted(s["timers"].items()):
            print("%s %s %s %s hakux-%s.timer hakux-%s.service" % (
                nxt, "-" if nxt == "-" else "5min left", last or "-", "ago" if last else "-", n, n))
        return 0
    if b[0] == "show":
        u = b[1]
        print(s["units"].get(u, ""))
        return 0
    if b[0] == "is-active":
        on = b[1] in s["units"] or b[1] in s.get("active", [])
        print("active" if on else "inactive")
        return 0 if on else 3
    return 0


def adb():
    if a[:1] == ["devices"]:
        print("List of devices attached\nbdc158a5\tdevice\nee317437\tdevice\n")
    return 0


if __name__ == "__main__":
    sys.exit({"gh": gh, "systemctl": systemctl, "adb": adb}.get(tool, lambda: 0)())
