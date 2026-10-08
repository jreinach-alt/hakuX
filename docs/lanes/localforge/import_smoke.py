#!/usr/bin/env python3
"""Smoke test of forge_import.py on a throwaway repo (jreinach-alt/import-smoke).

Seed-only run with ceiling 9, a second run that must change nothing, then a
run with a fake recon set that upgrades #3 to a recovered PR (2 comments) and
#6 to a recovered issue, then a repeat that must post no comment twice.
"""
import json, os, subprocess, sys, tempfile, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
FORGE = "http://127.0.0.1:3330"
TOK = os.path.expanduser("~/hakux-work/forge/tokens")
R = "jreinach-alt/import-smoke"
ADMIN = open(f"{TOK}/forgeadmin.token").read().strip()
fails = []


def api(method, path, body=None):
    req = urllib.request.Request(FORGE + "/api/v1" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", "token " + ADMIN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            return json.loads(b) if b.strip() else None
    except urllib.error.HTTPError as e:
        return {"_err": e.code}


def run(*extra):
    p = subprocess.run([sys.executable, os.path.join(HERE, "forge_import.py"), "--repo", R, "--ceiling", "9", "--through", "9",
                        "--execute"] + list(extra), capture_output=True, text=True)
    print(p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr)
    return p


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f": {detail}"))
    if not cond:
        fails.append(name)


api("DELETE", f"/repos/{R}")
api("POST", "/orgs/jreinach-alt/repos", dict(name="import-smoke", private=True, auto_init=True, default_branch="master"))
os.environ["FORGE_IMPORT_TEST"] = "1"
p = run()
check("seed run rc 0 and 9 created", p.returncode == 0 and "created 9" in p.stdout, p.stdout + p.stderr)
iss = {i["number"]: i for i in api("GET", f"/repos/{R}/issues?state=all&type=issues&limit=50")}
check("numbers 1..9 exist", sorted(iss) == list(range(1, 10)), sorted(iss))
check("#4 seeded from board, title kept", "seeded from the board" in iss[4]["body"] and not iss[4]["title"].startswith("#4"), iss[4]["title"])
check("#5 not recovered, closed", iss[5]["title"] == "#5: not recovered" and iss[5]["state"] == "closed", iss[5])
p = run()
check("re-run changes nothing", p.returncode == 0 and "created 0, updated 0" in p.stdout and "comments 0" in p.stdout, p.stdout)

d = tempfile.mkdtemp()
os.makedirs(f"{d}/issues")
json.dump(dict(number=3, kind="pr", title="a recovered PR", body="PR body", state="merged", labels=["fold-ready"],
               author="jreinach-alt", created_at="2026-09-01T00:00:00Z",
               comments=[dict(id=111, author="jreinach-alt", created_at="2026-09-01T01:00:00Z", body="[job.fold] folded", source="t1"),
                         dict(id=110, author="owner", created_at="2026-09-01T00:30:00Z", body="first", source="t2")]),
          open(f"{d}/issues/3.json", "w"))
json.dump(dict(number=6, kind="issue", title="recovered six", body="six body", state="open", labels=[],
               author=dict(login="jreinach"), comments=[dict(id=222, author="x", body="c")]), open(f"{d}/issues/6.json", "w"))
p = run("--recon", d)
check("recon run: updated 2, comments 3", p.returncode == 0 and "updated 2" in p.stdout and "comments 3" in p.stdout, p.stdout + p.stderr)
i3 = api("GET", f"/repos/{R}/issues/3")
c3 = api("GET", f"/repos/{R}/issues/3/comments")
check("#3 is a closed [GitHub PR] with labels", i3["title"] == "[GitHub PR] a recovered PR" and i3["state"] == "closed"
      and {"github-pr", "fold-ready", "github-import"} <= {l["name"] for l in i3["labels"]}, i3["title"])
check("#3 comments in time order with author header", len(c3) == 2 and "first" in c3[0]["body"] and "@owner" in c3[0]["body"]
      and "github-comment:111" in c3[1]["body"], [c["body"][:80] for c in c3])
i6 = api("GET", f"/repos/{R}/issues/6")
check("#6 recovered body + board row kept in details", "six body" in i6["body"] and "<details>" in i6["body"] and i6["state"] == "open", i6["body"][:200])
p = run("--recon", d)
check("recon re-run: no duplicate comments", "comments 0" in p.stdout and "updated 0" in p.stdout, p.stdout)
# a job's label survives a re-import
lab = api("POST", f"/repos/{R}/labels", dict(name="needs-rebase", color="#d93f0b"))
api("POST", f"/repos/{R}/issues/6/labels", dict(labels=[lab["id"]]))
json.dump(dict(number=6, kind="issue", title="recovered six v2", body="six body", state="open", labels=[],
               author="jreinach", comments=[]), open(f"{d}/issues/6.json", "w"))
p = run("--recon", d)
i6 = api("GET", f"/repos/{R}/issues/6")
check("update keeps a job-added label", i6["title"] == "recovered six v2" and "needs-rebase" in {l["name"] for l in i6["labels"]}, i6["labels"])
# a forge-native issue (#10) inside a raised range is left alone; numbers after it still line up
api("POST", f"/repos/{R}/issues", dict(title="forge-native"))
p = subprocess.run([sys.executable, os.path.join(HERE, "forge_import.py"), "--repo", R, "--ceiling", "12", "--through", "12", "--execute"],
                   capture_output=True, text=True)
i10 = api("GET", f"/repos/{R}/issues/10")
i12 = api("GET", f"/repos/{R}/issues/11")
i3 = api("GET", f"/repos/{R}/issues/3")
check("forge-native #10 untouched, #11-#12 created, no downgrade without --recon",
      p.returncode == 0 and "foreign 1" in p.stdout and "created 2" in p.stdout and "updated 0" in p.stdout
      and i10["title"] == "forge-native" and i12["title"] == "#11: not recovered"
      and i3["title"] == "[GitHub PR] a recovered PR", (p.stdout, p.stderr, i12["title"], i3["title"]))
api("DELETE", f"/repos/{R}")
print(f"\n{len(fails)} failed" if fails else "\nall passed")
sys.exit(1 if fails else 0)
