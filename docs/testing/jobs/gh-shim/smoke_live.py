#!/usr/bin/env python3
"""Live smoke test of the gh shim against the local forge.

  python3 docs/testing/jobs/gh-shim/smoke_live.py [path/to/gh]

It recreates a throwaway repo, jreinach-alt/shim-smoke, and runs the
harness's own command lines through the shim:
  * the exact --json field lists and --jq filters copied from board, status,
    fold, handback, arms, pr-sweep, issue-sweep, comment_sweep, gh-label.sh
    and gh_rest.py;
  * the failure modes: not implemented, refused merge, forge unreachable,
    a 404.
It never touches jreinach-alt/hakuX, whose issue numbers are reserved for
the import. Setup uses the forgeadmin token; the calls run as `jobs`.
Exit 0 only when every check passes.
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "gh")
FORGE = os.environ.get("FORGE_URL", "http://127.0.0.1:3330")
TOK = os.environ.get("FORGE_TOKENS", os.path.expanduser("~/hakux-work/forge/tokens"))
R = "jreinach-alt/shim-smoke"
ADMIN = open(os.path.join(TOK, "forgeadmin.token")).read().strip()
ENV = dict(os.environ, GH_REPO=R, FORGE_USER="jobs", GH_SHIM_LOG=os.path.join(tempfile.mkdtemp(), "shim.log"))
ENV.pop("HAKUX_ROLE", None)
fails = []
passes = 0


def api(method, path, body=None):
    req = urllib.request.Request(FORGE + "/api/v1" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", "token " + ADMIN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            return r.status, (json.loads(b) if b.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def gh(*args, env=None, stdin=None):
    p = subprocess.run([GH] + list(args), capture_output=True, text=True, env=env or ENV, input=stdin, timeout=300)
    return p.returncode, p.stdout, p.stderr


def check(name, cond, detail=""):
    global passes
    if cond:
        passes += 1
        print(f"ok   {name}")
    else:
        fails.append(name)
        print(f"FAIL {name}: {detail}")


def put_file(path, text, branch="master", new_branch=None, msg="smoke"):
    st, cur = api("GET", f"/repos/{R}/contents/{path}?ref={branch}")
    body = dict(content=base64.b64encode(text.encode()).decode(), message=msg, branch=branch)
    if new_branch:
        body["new_branch"] = new_branch
    if st == 200:
        body["sha"] = cur["sha"]
        st2, j = api("PUT", f"/repos/{R}/contents/{path}", body)
    else:
        st2, j = api("POST", f"/repos/{R}/contents/{path}", body)
    assert st2 in (200, 201), (st2, j)
    return j["commit"]["sha"]


def tmpfile(text):
    fd, p = tempfile.mkstemp()
    os.write(fd, text.encode())
    os.close(fd)
    return p


# ------------------------------------------------------------------ setup
api("DELETE", f"/repos/{R}")
st, j = api("POST", "/orgs/jreinach-alt/repos", dict(name="shim-smoke", private=True, auto_init=True,
                                                    default_branch="master", readme="Default"))
assert st == 201, (st, j)
put_file("a.txt", "base\n")
put_file("b.txt", "lane change\n", new_branch="lane/smoke")
put_file("a.txt", "theirs\n", new_branch="lane/conflict")
put_file("a.txt", "ours\n")  # master moves: lane/conflict now conflicts
put_file("c.txt", "other\n", new_branch="lane/closed")

# ------------------------------------------------------------------ auth / version
rc, out, err = gh("auth", "status")
check("auth status rc 0", rc == 0, err)
rc, out, err = gh("--version")
check("--version", rc == 0 and "forge-shim" in out, out)

# ------------------------------------------------------------------ labels (ensure-labels.sh form)
for name, color, desc in [("fold-ready", "0e8a16", "ready to fold"), ("harness-status", "ededed", "status"),
                          ("harness", "ededed", "harness"), ("claimed:cloud", "5319e7", "claimed"),
                          ("needs-rebase", "b60205", "rebase"), ("decision-needed", "d93f0b", "decide")]:
    rc, out, err = gh("label", "create", name, "--repo", R, "--color", color, "--description", desc, "--force")
    check(f"label create {name}", rc == 0, err)
rc, out, err = gh("label", "create", "fold-ready", "--repo", R, "--color", "000000", "--description", "x", "--force")
check("label create --force on existing", rc == 0, err)
rc, out, err = gh("label", "create", "fold-ready", "--repo", R, "--color", "000000")
check("label create existing without --force fails", rc == 1 and "already exists" in err, (rc, err))

# ------------------------------------------------------------------ issues (status.sh forms)
rc, out, err = gh("issue", "create", "--repo", R, "--title", "harness: live status (auto-updated)",
                  "--label", "harness-status", "--label", "harness", "--body", "status body")
m = re.search(r"([0-9]+)$", out.strip())
check("issue create prints URL ending in number", rc == 0 and m, (rc, out, err))
inum = int(m.group(1)) if m else 0
rc, out, err = gh("issue", "list", "--repo", R, "--label", "harness-status", "--state", "open", "--json", "number",
                  "--jq", ".[0].number")
check("issue list --label --jq .[0].number (comment_sweep)", rc == 0 and out.strip() == str(inum), (rc, out, err))
rc, out, err = gh("issue", "list", "--repo", R, "--label", "harness-status", "--state", "open", "--json", "number,title",
                  "--jq", '.[0] | "\\(.number) \\(.title)"')
check("issue list number,title (status.sh:615)", rc == 0 and out.strip() == f"{inum} harness: live status (auto-updated)", out)
rc, out, err = gh("issue", "list", "--repo", R, "--state", "open", "--limit", "200", "--json", "number,title,labels")
j = json.loads(out) if rc == 0 else []
check("issue list --json number,title,labels (board.sh)", rc == 0 and j and j[0]["labels"] and "name" in j[0]["labels"][0], out[:200])
rc, out, err = gh("issue", "list", "--repo", R, "--label", "no-such-label", "--state", "open", "--json", "number")
check("issue list unknown label: [] + warning", rc == 0 and json.loads(out) == [] and "does not exist" in err, (out, err))
rc, out, err = gh("issue", "list", "--repo", R, "--state", "open", "--limit", "300", "--json", "number,labels",
                  "--jq", '.[] | ([.labels[].name | select(startswith("blocked:"))] | join(",")) as $l | "\\(.number)\\t\\($l)"')
check("issue list blocked: jq (handback.sh:490)", rc == 0 and out == f"{inum}\t\n", repr(out))
rc, out, err = gh("issue", "view", str(inum), "--repo", R, "--json", "state")
check("issue view --json state", rc == 0 and json.loads(out)["state"] == "OPEN", out)

# ------------------------------------------------------------------ comments via api (status.sh / comment_sweep.sh)
since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
bf = tmpfile("[job.status] first body\nline two\twith tab")
rc, out, err = gh("api", "-X", "POST", f"repos/{R}/issues/{inum}/comments", "-F", f"body=@{bf}", "--jq", ".id")
check("api POST comment -F body=@file --jq .id", rc == 0 and out.strip().isdigit(), (rc, out, err))
cid = out.strip()
rc, out, err = gh("api", f"repos/{R}/issues/comments/{cid}", "--silent")
check("api GET comment --silent (exists)", rc == 0 and out == "", (rc, out, err))
rc, out, err = gh("api", f"repos/{R}/issues/comments/99999999", "--silent")
check("api GET missing comment fails loudly", rc == 1 and "404" in err, (rc, err))
bf2 = tmpfile("[job.status] edited body")
rc, out, err = gh("api", "-X", "PATCH", f"repos/{R}/issues/comments/{cid}", "-F", f"body=@{bf2}", "--silent")
check("api PATCH comment -F body=@file", rc == 0, err)
rc, out, err = gh("api", "-X", "PATCH", f"repos/{R}/issues/comments/{cid}", "-f", "body=[job.status] raw -f body", "--silent")
check("api PATCH comment -f body=", rc == 0, err)
rc, out, err = gh("api", "-X", "PATCH", f"repos/{R}/issues/{inum}", "-f", "title=harness: live status (auto-updated)", "--silent")
check("api PATCH issue -f title=", rc == 0, err)
rc, out, err = gh("api", "-X", "PATCH", f"repos/{R}/issues/{inum}", "-F", f"body=@{bf}", "--silent")
check("api PATCH issue -F body=@file", rc == 0, err)
jqA = '''.[] | [.created_at,
                       (.issue_url | split("/") | last),
                       .user.login,
                       .html_url,
                       (.body | gsub("[\\r\\n\\t]"; " ") | .[0:400])] | @tsv'''
rc, out, err = gh("api", f"repos/{R}/issues/comments?since={since}&sort=created&direction=desc&per_page=100",
                  "--paginate", "--jq", jqA)
rows = [l.split("\t") for l in out.strip().splitlines()]
check("comment_sweep jq (A): issue number, author, Z time", rc == 0 and rows and rows[0][1] == str(inum)
      and rows[0][2] == "jobs" and rows[0][0].endswith("Z") and "#issuecomment-" + cid in rows[0][3], (rc, out, err))
jqD = '.[] | select(.body | startswith("[job.status]")) | "\\(.created_at)\\t\\(.html_url | sub(".*/(issues|pull)/"; "#") | sub("#issuecomment.*"; "")) \\(.body | split("\\n")[0] | .[11:120])"'
rc, out, err = gh("api", f"repos/{R}/issues/comments?since={since}&per_page=100", "--jq", jqD)
check("status.sh jq (D): '#N' from html_url", rc == 0 and f"\t#{inum} " in out, (rc, out, err))

# ------------------------------------------------------------------ labels via api (gh-label.sh)
rc, out, err = gh("api", "-X", "POST", f"repos/{R}/issues/{inum}/labels", "-f", "labels[]=claimed:cloud",
                  "-f", "labels[]=auto-made-label")
check("label_add -f labels[]= (incl. auto-create)", rc == 0, err)
rc, out, err = gh("api", f"repos/{R}/issues/{inum}/labels", "--jq", ".[].name")
names = out.split()
check("label_rm read --jq .[].name", rc == 0 and "claimed:cloud" in names and "auto-made-label" in names, out)
rc, out, err = gh("api", "-X", "DELETE", f"repos/{R}/issues/{inum}/labels/claimed%3Acloud")
check("label_rm DELETE urlencoded name", rc == 0, err)
rc, out, err = gh("api", f"repos/{R}/issues/{inum}", "--jq", ".labels[].name")
check("arms.sh: api issues/N --jq .labels[].name", rc == 0 and "claimed:cloud" not in out.split() and "harness" in out.split(), out)
rc, out, err = gh("api", "-X", "DELETE", f"repos/{R}/issues/{inum}/labels/claimed%3Acloud")
check("DELETE label not on issue fails", rc == 1, (rc, err))

# ------------------------------------------------------------------ PRs
body = tmpfile("Lane: smoke\nFiles: b.txt\n\nCloses #%d\n" % inum)
rc, out, err = gh("pr", "create", "--draft", "--base", "master", "--head", "lane/smoke", "--title", "smoke PR",
                  "--body-file", body)
m = re.search(r"/pulls/(\d+)$", out.strip())
check("pr create --draft", rc == 0 and m, (rc, out, err))
pn = int(m.group(1)) if m else 0
rc, out, err = gh("pr", "create", "--draft", "--base", "master", "--head", "lane/smoke", "--title", "dup", "--body", "x")
check("pr create duplicate refused", rc == 1 and "already exists" in err, (rc, err))
rc, out, err = gh("pr", "create", "--base", "master", "--head", "lane/conflict", "--title", "conflict PR", "--body", "c")
pc = int(re.search(r"(\d+)$", out.strip()).group(1)) if rc == 0 else 0
check("pr create (non-draft)", rc == 0, err)
rc, out, err = gh("pr", "create", "--base", "master", "--head", "lane/closed", "--title", "to close", "--body", "c")
pz = int(re.search(r"(\d+)$", out.strip()).group(1)) if rc == 0 else 0
rc, out, err = gh("pr", "close", str(pz))
check("pr close", rc == 0, err)

rc, out, err = gh("pr", "list", "--repo", R, "--state", "open", "--limit", "100", "--json",
                  "number,headRefName,headRefOid,isDraft,mergeable,labels,updatedAt,statusCheckRollup,title")
prs = {p["number"]: p for p in json.loads(out)} if rc == 0 else {}
p = prs.get(pn, {})
check("pr-sweep list: draft PR fields", p.get("isDraft") is True and p.get("title") == "smoke PR"
      and re.fullmatch(r"[0-9a-f]{40}", p.get("headRefOid") or "") and p.get("updatedAt", "").endswith("Z")
      and p.get("mergeable") == "MERGEABLE" and p.get("statusCheckRollup") == [], p)
check("pr list: conflicting PR is CONFLICTING", prs.get(pc, {}).get("mergeable") == "CONFLICTING", prs.get(pc))
check("pr list: closed PR not in --state open", pz not in prs, list(prs))
rc, out, err = gh("pr", "list", "--repo", R, "--state", "all", "--limit", "300", "--json", "number,state,headRefName",
                  "--jq", '.[] | "\\(.headRefName)\\t\\(.state)"')
check("handback.sh:417 --state all", rc == 0 and "lane/closed\tCLOSED" in out and "lane/smoke\tOPEN" in out, out)
rc, out, err = gh("pr", "list", "--repo", R, "--head", "lane/smoke", "--state", "open", "--json", "number", "--jq", ".[0].number")
check("arms.sh:416 --head --jq .[0].number", rc == 0 and out.strip() == str(pn), (out, err))
rc, out, err = gh("pr", "list", "--repo", R, "--head", "lane/smoke", "--state", "all", "--json", "number,state,isDraft,url",
                  "--jq", '.[0] | "#\\(.number) \\(if .isDraft then "draft" else (.state|ascii_downcase) end)"')
check("status.sh:130", rc == 0 and out.strip() == f"#{pn} draft", out)
fold6 = 'sort_by(.number)[] | "\\(.number)\\t\\(.headRefName)\\t\\(.headRefOid)\\t\\(.isDraft)\\t\\(.mergeable)\\t\\([.labels[].name] | join(","))"'
rc, out, err = gh("pr", "list", "--repo", R, "--state", "open", "--limit", "200", "--json",
                  "number,headRefName,headRefOid,isDraft,mergeable,labels", "--jq", fold6)
check("fold.sh:630 tsv", rc == 0 and re.search(rf"^{pn}\tlane/smoke\t[0-9a-f]{{40}}\ttrue\tMERGEABLE\t$", out, re.M), out)

CI_STATE_JQ = '''def ci_state: [.statusCheckRollup[]? | (.conclusion // .state // "PENDING")] as $c
              | if ($c | length) == 0 then "NONE"
                elif ($c | all(. == "SUCCESS" or . == "SKIPPED" or . == "NEUTRAL")) then "GREEN"
                elif ($c | any(. == "FAILURE" or . == "ERROR" or . == "CANCELLED" or . == "TIMED_OUT")) then "RED"
                else "PENDING" end; '''
hb10 = CI_STATE_JQ + '''sort_by(.number)[] | select(.isDraft) | select(.headRefName | startswith("lane/")) | ci_state as $ci | "\\(.number)\\t\\(.headRefName)\\t\\(.headRefOid)\\tisDraft=\\(.isDraft) ci=\\($ci) quiet=\\((now - (.updatedAt | fromdateiso8601)) | floor)\\t\\(.labels | map(.name) | join(","))"'''
rc, out, err = gh("pr", "list", "--repo", R, "--state", "open", "--limit", "100", "--json",
                  "number,headRefName,headRefOid,isDraft,labels,updatedAt,statusCheckRollup", "--jq", hb10)
check("handback.sh:1029 (fromdateiso8601 on updatedAt) ci=NONE", rc == 0 and re.search(rf"^{pn}\tlane/smoke\t.*ci=NONE quiet=\d+", out, re.M), (out, err))

head = prs.get(pn, {}).get("headRefOid", "")
st, _ = api("POST", f"/repos/{R}/statuses/{head}", dict(state="pending", context="jobs-selftest", description="running"))
rc, out, err = gh("pr", "view", str(pn), "--repo", R, "--json", "headRefOid,statusCheckRollup", "--jq",
                  CI_STATE_JQ + '"\\(.headRefOid)\\t\\(ci_state)"')
check("handback.sh:1077 PENDING", rc == 0 and out.strip() == f"{head}\tPENDING", out)
rc, out, err = gh("pr", "checks", str(pn))
check("pr checks pending exits 8", rc == 8, (rc, out, err))
st, _ = api("POST", f"/repos/{R}/statuses/{head}", dict(state="success", context="jobs-selftest", description="ok"))
fold_green = '''
        [.statusCheckRollup[]? | (.conclusion // .state // "PENDING")] as $c
        | if ($c | length) == 0 then "NONE"
          elif ($c | all(. == "SUCCESS" or . == "SKIPPED" or . == "NEUTRAL")) then "GREEN"
          elif ($c | any(. == "FAILURE" or . == "ERROR" or . == "CANCELLED" or . == "TIMED_OUT")) then "RED"
          else "PENDING" end'''
rc, out, err = gh("pr", "view", str(pn), "--repo", R, "--json", "statusCheckRollup", "--jq", fold_green)
check("fold.sh:683 ci_green GREEN", rc == 0 and out.strip() == "GREEN", out)
CHECK_ROWS_JQ = '.statusCheckRollup[]? | [ (.name // .context // "check"), (if (.conclusion // "") != "" then .conclusion elif (.state // "") != "" then .state else "PENDING" end), (.startedAt // .createdAt // "") ] | @tsv'
rc, out, err = gh("pr", "view", str(pn), "--repo", R, "--json", "statusCheckRollup", "--jq", CHECK_ROWS_JQ)
check("fold.sh:788 CHECK_ROWS_JQ", rc == 0 and out.startswith("jobs-selftest\tSUCCESS\t20"), out)
TRUNK_CI_JQ = '''[.check_runs[]? | if .status != "completed" then "PENDING" else ((.conclusion // "") | ascii_upcase) end] as $all
        | [$all[] | select(. != "CANCELLED")] as $c
        | if ($all | length) == 0 then "NONE"
          elif ($c | length) == 0 then "CANCELLED"
          elif ($c | any(. == "FAILURE" or . == "TIMED_OUT" or . == "STARTUP_FAILURE" or . == "ACTION_REQUIRED")) then "RED"
          elif ($c | all(. == "SUCCESS" or . == "SKIPPED" or . == "NEUTRAL")) then "GREEN"
          else "PENDING" end'''
rc, out, err = gh("api", f"repos/{R}/commits/{head}/check-runs", "--jq", TRUNK_CI_JQ)
check("fold.sh:1044 TRUNK_CI_JQ via check-runs", rc == 0 and out.strip() == "GREEN", (out, err))
rc, out, err = gh("pr", "checks", str(pn))
check("pr checks green exits 0", rc == 0, (rc, out, err))
st, _ = api("POST", f"/repos/{R}/statuses/{head}", dict(state="failure", context="android", description="bad"))
rc, out, err = gh("api", f"repos/{R}/commits/{head}/check-runs", "--jq", TRUNK_CI_JQ)
check("TRUNK_CI_JQ RED", out.strip() == "RED", out)

rc, out, err = gh("pr", "comment", str(pn), "--repo", R, "--body-file", tmpfile("[lane.smoke] waiting: CI"))
check("pr comment --body-file prints #issuecomment- URL", rc == 0 and re.search(r"#issuecomment-\d+$", out.strip()), (out, err))
rc, out, err = gh("pr", "comment", str(pn), "--repo", R, "--body", "[job.cloud] claimed for audit")
check("pr comment --body", rc == 0, err)
hb4 = '[.comments[] | .body | ltrimstr("`") | select(startswith("[lane.smoke] ") or startswith("[job.handback] Resumed"))] | last // ""'
rc, out, err = gh("pr", "view", str(pn), "--repo", R, "--json", "comments", "--jq", hb4)
check("handback.sh:376 comments jq", rc == 0 and out.strip() == "[lane.smoke] waiting: CI", out)
rc, out, err = gh("pr", "view", str(pn), "--repo", R, "--json", "comments", "--jq",
                  '[.comments[] | select(.body | startswith("[job.cloud] claimed"))] | last | .body')
check("pr-sweep.sh:382", rc == 0 and out.strip() == "[job.cloud] claimed for audit", out)
rc, out, err = gh("pr", "view", str(pn), "--repo", R, "--json", "body", "--jq", ".body")
check("pr view --json body", rc == 0 and out.startswith("Lane: smoke"), out)
rc, out, err = gh("pr", "view", str(pn), "--repo", R, "--json", "body,closingIssuesReferences,files")
j = json.loads(out) if rc == 0 else {}
check("cloud.sh:719 closingIssuesReferences + files", j.get("closingIssuesReferences") == [{"number": inum}]
      and [f["path"] for f in j.get("files", [])] == ["b.txt"], j)
rc, out, err = gh("pr", "view", str(pn), "--repo", R, "--json", "mergeable", "--jq", ".mergeable")
check("fold.sh:637 mergeable", out.strip() == "MERGEABLE", out)
rc, out, err = gh("pr", "view", "lane/smoke", "--repo", R, "--json", "number", "--jq", ".number")
check("pr view by branch", out.strip() == str(pn), (out, err))
rc, out, err = gh("api", "-X", "POST", f"repos/{R}/issues/{pn}/labels", "-f", "labels[]=fold-ready")
rc, out, err = gh("pr", "list", "--repo", R, "--state", "open", "--label", "fold-ready", "--json", "number",
                  "--jq", 'map("#\\(.number)") | join(" ")')
check("status.sh:383 --label fold-ready", rc == 0 and out.strip() == f"#{pn}", out)
rc, out, err = gh("api", f"repos/{R}/issues/{pn}/events?per_page=100", "--paginate", "--jq",
                  '.[] | select(.event == "labeled" and .label.name == "fold-ready") | .created_at')
check("status_html.py:1714 issue events labeled", rc == 0 and out.strip().endswith("Z"), (out, err))
rc, out, err = gh("api", f"repos/{R}/issues/{pn}/events?&per_page=100&page=1")
check("gh_rest _paged events (leading ?&)", rc == 0 and any(e.get("event") == "labeled" for e in json.loads(out)), out[:300])
rc, out, err = gh("pr", "ready", str(pn))
rc2, out2, _ = gh("pr", "view", str(pn), "--json", "isDraft,title", "--jq", '"\\(.isDraft) \\(.title)"')
check("pr ready clears draft", rc == 0 and out2.strip() == "false smoke PR", (out2, err))
rc, out, err = gh("pr", "ready", str(pn), "--undo")
rc2, out2, _ = gh("pr", "view", str(pn), "--json", "isDraft", "--jq", ".isDraft")
check("pr ready --undo makes a draft", out2.strip() == "true", out2)

# gh_rest.py shapes
rc, out, err = gh("api", f"repos/{R}/issues?state=open&per_page=100&page=1")
j = json.loads(out) if rc == 0 else []
check("gh_rest open_issues: PRs carry pull_request", any(i.get("pull_request") for i in j) and any(i.get("pull_request") is None for i in j), [(i["number"], bool(i.get("pull_request"))) for i in j])
rc, out, err = gh("api", f"repos/{R}/pulls?state=open&per_page=100&page=1")
j = json.loads(out) if rc == 0 else []
check("gh_rest open_prs: head.ref, draft, updated_at Z", j and all("ref" in p["head"] and "draft" in p and p["updated_at"].endswith("Z") for p in j), out[:200])
rc, out, err = gh("api", f"repos/{R}/pulls/{pn}", "--jq", ".head.ref")
check("cloud.sh:427 pulls/N --jq .head.ref", out.strip() == "lane/smoke", out)
rc, out, err = gh("api", f"repos/{R}/commits/master", "--jq", ".sha")
check("status.sh:461 commits/<ref> --jq .sha", re.fullmatch(r"[0-9a-f]{40}", out.strip()), (out, err))
rc, out, err = gh("api", f"repos/{R}/pages", "--jq", ".html_url")
check("status.sh:608 pages -> loud 404", rc == 1 and "404" in err and out.strip() in ("", "null") or rc == 1, (rc, out, err))

# release / run
rc, out, err = gh("release", "create", "v0.5-smoke", tmpfile("apk bytes"), "--repo", R, "--prerelease",
                  "--title", "smoke", "--notes-file", tmpfile("notes"), "--target", "master")
check("release create with asset", rc == 0, err)
rc, out, err = gh("release", "list", "--repo", R, "--limit", "30", "--json", "tagName", "--jq",
                  '.[] | .tagName | select(startswith("v0.5"))')
check("status.sh:458 release list", rc == 0 and out.strip() == "v0.5-smoke", (out, err))
rc, out, err = gh("run", "list", "--repo", R, "--branch", "master", "--limit", "20", "--json",
                  "workflowName,status,conclusion,headSha,createdAt")
check("status.sh:449 run list (no runs -> [])", rc == 0 and json.loads(out) == [], (rc, out, err))

# loud failures
rc, out, err = gh("pr", "merge", str(pn))
check("pr merge refused", rc == 2 and "foldqueue" in err, (rc, err))
rc, out, err = gh("repo", "view")
check("unknown op exits 64", rc == 64 and err.startswith("gh-shim: not implemented: repo view"), (rc, err))
rc, out, err = gh("pr", "list", "--search", "is:open")
check("unknown flag exits 64", rc == 64, (rc, err))
rc, out, err = gh("api", "graphql", "-f", "query={viewer{login}}")
check("graphql exits 64", rc == 64, (rc, err))
rc, out, err = gh("pr", "list", "--json", "nosuchfield")
check("unknown --json field fails", rc == 1 and "unknown JSON field" in err, (rc, err))
rc, out, err = gh("issue", "list", env=dict(ENV, FORGE_URL="http://127.0.0.1:9"))
check("forge down: rc 1 and 'unreachable'", rc == 1 and "unreachable" in err and out == "", (rc, out, err))
rc, out, err = gh("issue", "list", env=dict(ENV, GH_REPO="jreinach-alt/no-such-repo"))
check("missing repo: loud 404", rc == 1 and "404" in err, (rc, err))
rc, out, err = gh("issue", "list", env=dict(ENV, FORGE_USER="nobody"))
check("missing token: rc 4", rc == 4 and "no forge token" in err, (rc, err))
log = [json.loads(l) for l in open(ENV["GH_SHIM_LOG"])]
check("every call logged", len(log) >= 60 and any(r["rc"] == 64 for r in log) and all("argv" in r for r in log), len(log))

api("DELETE", f"/repos/{R}")
print(f"\n{passes} passed, {len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
