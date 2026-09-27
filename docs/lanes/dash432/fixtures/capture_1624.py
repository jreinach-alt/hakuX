#!/usr/bin/env python3
"""Capture the SOURCES status.sh reads, as they stood at the 16:24 PDT build.

The host kept the 16:24 build's OUTPUTS (../1624/*.json, STATUS.md,
index.html). A renderer cannot be re-run on its own outputs, so this copies
the inputs, taken at 16:28-16:40 PDT on 2026-09-26 (the queue, the holds and
the escalations were unchanged since 16:24: the same 23 + 99 request ids as
lanes.json, the same two .why files), and cuts every time-ordered source
at the fixture's clock, NOW = 1790465073 (2026-09-26 16:24:33 PDT):

  board/          territory.toml, nv2a_issues.toml at origin/board e62d272ea7
                  (16:15 PDT, the last board commit before 16:24), trimmed to
                  the rows the page reads, long notes cut to 400 chars
  work/           dispatch queue/running/hold (+ mtimes), the Ghoulies soaks
                  and each device's last results (request/result json, DONE,
                  perf lines only), escalations.md, logs/lane index + each
                  lane's last session result, titlepipe push records, titles,
                  attempts, the hostops digest's last block
  gh.json         the GitHub answers a shim replays: PRs created by NOW (state
                  as of NOW: merged after NOW reads OPEN), 0.5 and parked
                  issue labels, lane.xbox/lane.remote/host comments by NOW
  systemd.json    the lane units and timers in STATUS.md's Host section

Run once, from the worktree root. Private text is not copied: session JSON
is cut to its `result`, request JSON drops `route` and `expect`.
"""
import datetime, glob, json, os, re, shutil, subprocess, sys, tomllib

NOW = 1790465073
NOW_ISO = "2026-09-26T23:24:33Z"
W = "/home/justin/hakux-work"
D = W + "/dispatch"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "1624", "src")
BOARD_SHA = "e62d272ea7"
REPO = "jreinach-alt/hakuX"


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True, check=True).stdout


def put(rel, text, mtime=None):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    if mtime is not None:
        os.utime(p, (mtime, mtime))


WHOLE = ("blocked_on", "status_note", "title")     # the page shows these: never cut them


def cut(v, n=400):
    return v if not isinstance(v, str) or len(v) <= n else v[:n] + " [cut]"


def toml_dump(d, prefix=""):
    """Enough TOML for tables of scalars and string lists."""
    def val(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list):
            return "[" + ", ".join(val(x) for x in v) + "]"
        return json.dumps(str(v), ensure_ascii=False)
    out = []
    for k, v in d.items():
        if not isinstance(v, dict):
            out.append("%s = %s" % (k, val(v)))
    for k, v in d.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                out.append("")
                out.append("[%s.%s]" % (k, k2 if re.match(r"^[\w-]+$", k2) else json.dumps(k2)))
                for k3, v3 in v2.items():
                    out.append("%s = %s" % (k3, val(v3 if k3 in WHOLE else cut(v3))))
    return "\n".join(out) + "\n"


def main():
    board_only = os.environ.get("BOARD_ONLY") == "1"       # the board is a fixed sha: safe to redo; the rest is not
    for sub in (("board",) if board_only else ("board", "work")):          # systemd.json is written by hand, from STATUS.md
        if os.path.exists(os.path.join(OUT, sub)):
            shutil.rmtree(os.path.join(OUT, sub))
    # ---- board
    terr = tomllib.loads(sh("git", "show", BOARD_SHA + ":territory.toml"))
    now = datetime.datetime.fromtimestamp(NOW, datetime.timezone.utc)
    ret = {}
    for n, r in terr.get("retired", {}).items():
        try:
            t = datetime.datetime.strptime(r.get("retired_utc", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
        if 0 <= (now - t).total_seconds() < 86400:
            ret[n] = r
    t2 = {"wave": terr.get("wave", 0), "lane": terr["lane"], "retired": ret}
    put("board/territory.toml", toml_dump(t2))
    issues = tomllib.loads(sh("git", "show", BOARD_SHA + ":nv2a_issues.toml"))["issue"]
    want = set()
    for r in list(terr["lane"].values()) + list(ret.values()):
        want |= {str(i) for i in r.get("issues", [])}
    want |= {str(i) for i in range(424, 434)} | {"397", "412", "413", "414", "372", "303"}
    put("board/nv2a_issues.toml", toml_dump({"issue": {k: issues[k] for k in sorted(want, key=int) if k in issues}}))

    if board_only:
        return 0
    # ---- dispatch
    for st in ("queue", "running", "hold"):
        for p in sorted(glob.glob(os.path.join(D, st, "*"))):
            if os.path.isdir(p):
                continue
            b = os.path.basename(p)
            txt = open(p, encoding="utf-8", errors="replace").read()
            if b.endswith(".req"):
                j = json.loads(txt)
                for k in ("route", "expect"):
                    if j.get(k):
                        j[k] = "(not copied)"
                txt = json.dumps(j, indent=1) + "\n"
            put("work/dispatch/%s/%s" % (st, b), txt, os.path.getmtime(p))
    # Back to 16:24. The capture ran at ~16:40, after the Nova's hold (taken at
    # 16:19:50 by the host's #427 profile, dispatcher.log "HELD by .../hold/nova")
    # was lifted at 16:31:12 and the dispatcher claimed the next run. At 16:24
    # nothing ran (lanes.json: arms_running 0) and the Nova was held with the
    # .why text lanes.json quotes. Anything queued after NOW is dropped.
    for p in glob.glob(os.path.join(OUT, "work/dispatch/running/*")):
        if p.endswith(".req"):
            j = json.load(open(p))
            if j.get("queued_utc", "") <= NOW_ISO:
                shutil.move(p, os.path.join(OUT, "work/dispatch/queue", os.path.basename(p)))
                continue
        os.remove(p)
    for p in glob.glob(os.path.join(OUT, "work/dispatch/queue/*.req")):
        if json.load(open(p)).get("queued_utc", "") > NOW_ISO:
            os.remove(p)
    # The Thor's hold (lane.titlestate's nav.py pilot, taken 16:13:44) was lifted
    # before the last capture; its text is the one lanes.json quotes.
    put("work/dispatch/hold/thor", "lane.titlestate\n", 1790464424)
    put("work/dispatch/hold/thor.why", "lane.titlestate (PR #442): HELD Thor pilot of nav.py on Burnout 3 and Black, "
        "granted by hostops 15:38 PDT (board-requests/titlestate.md item 1). Taken 16:13 PDT, until 16:41 PDT at the latest.\n",
        1790464424)
    put("work/dispatch/hold/nova", "host\n", 1790464790)
    put("work/dispatch/hold/nova.why", "host (buildflags427): A/B simpleperf profile, two APKs, ~20 min; "
        "profile_ab.sh lifts it on every exit path.\n", 1790464790)
    # results: every Ghoulies soak finished by NOW, and each device's last three results
    keep, per_dev = [], {}
    for rd in glob.glob(os.path.join(D, "results", "*")):
        dn = os.path.join(rd, "DONE")
        if not os.path.exists(dn) or os.path.getmtime(dn) > NOW:
            continue
        try:
            q = json.load(open(os.path.join(rd, "request.json")))
        except Exception:
            continue
        if "ghoulies" in str(q.get("title") or "").lower():
            keep.append(rd)
        try:
            dev = json.load(open(os.path.join(rd, "result.json"))).get("device_label") or q.get("device")
        except Exception:
            dev = q.get("device")
        if dev:
            per_dev.setdefault(dev, []).append((os.path.getmtime(dn), rd))
    for dev, l in per_dev.items():
        keep += [rd for _, rd in sorted(l)[-3:]]
    for rd in sorted(set(keep)):
        b = os.path.basename(rd)
        q = json.load(open(os.path.join(rd, "request.json")))
        for k in ("route", "expect"):
            if q.get(k):
                q[k] = "(not copied)"
        put("work/dispatch/results/%s/request.json" % b, json.dumps(q, indent=1) + "\n")
        try:
            r = json.load(open(os.path.join(rd, "result.json")))
            put("work/dispatch/results/%s/result.json" % b, json.dumps(
                {k: r.get(k) for k in ("requester", "purpose", "ref", "device_label", "apk_sha")}, indent=1) + "\n")
        except Exception:
            pass
        for lc in glob.glob(os.path.join(rd, "logcat*.txt")):
            lines = [l for l in open(lc, encoding="utf-8", errors="replace") if "hakuX-perf" in l and "gfps=" in l]
            put("work/dispatch/results/%s/%s" % (b, os.path.basename(lc)), "".join(lines))
        put("work/dispatch/results/%s/DONE" % b, "", os.path.getmtime(os.path.join(rd, "DONE")))

    # ---- host files
    for rel in ("host-tools/escalations.md", "titles/already-on-handhelds.json", "recovery/needs-hands.txt"):
        p = os.path.join(W, rel)
        if os.path.exists(p):
            put("work/" + rel, open(p, encoding="utf-8").read(), os.path.getmtime(p))
    for p in glob.glob(W + "/logs/titlepipe/batch-*.tsv"):
        put("work/logs/titlepipe/" + os.path.basename(p), open(p).read(), os.path.getmtime(p))
    for p in glob.glob(W + "/attempts/*"):
        put("work/attempts/" + os.path.basename(p), open(p).read())
    idx = [l for l in open(W + "/logs/lane/index.tsv", encoding="utf-8", errors="replace") if l[:20] <= NOW_ISO]
    put("work/logs/lane/index.tsv", "".join(idx[-400:]))
    lastjson = {}
    for l in idx:
        f = l.rstrip("\n").split("\t")
        if len(f) >= 8 and f[1].startswith("lane-"):
            lastjson[f[1][5:]] = next((x for x in f if x.endswith(".json")), "")
    for n, js in lastjson.items():
        p = os.path.join(W, "logs/lane", js)
        try:
            r = json.load(open(p)).get("result") or ""
        except Exception:
            continue
        put("work/logs/lane/" + js, json.dumps({"result": r}, indent=1) + "\n")
    for j in ("arms", "fold", "handback", "pr-sweep", "issue-sweep", "cloud"):
        try:
            tl = open("%s/logs/%s/tick.log" % (W, j), encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        keep_l = []
        for l in tl:
            m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) PDT", l)
            if m and m.group(1) > "2026-09-26 16:24:33":
                break
            keep_l.append(l)
        put("work/logs/%s/tick.log" % j, "\n".join(keep_l[-30:]) + "\n")
    bi = [l for l in open(W + "/logs/board/index.tsv", encoding="utf-8", errors="replace") if l[:20] <= NOW_ISO]
    put("work/logs/board/index.tsv", "".join(bi[-5:]))
    dg = open(W + "/logs/hostops/digest.log", encoding="utf-8", errors="replace").read()
    blocks = [b for b in re.split(r"(?m)^(?==== )", dg) if b.startswith("=== ")]
    blocks = [b for b in blocks if b[4:20] <= datetime.datetime.fromtimestamp(NOW, datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")]
    put("work/logs/hostops/digest.log", blocks[-1] if blocks else "")

    # ---- GitHub, as of NOW
    prs = json.loads(sh("gh", "pr", "list", "--repo", REPO, "--state", "all", "--limit", "300", "--json",
                        "number,state,isDraft,headRefName,labels,createdAt,mergedAt,title,url"))
    prs = [p for p in prs if p["createdAt"] <= NOW_ISO]
    for p in prs:
        if p.get("mergedAt") and p["mergedAt"] > NOW_ISO:
            p["state"], p["mergedAt"] = "OPEN", None
    iss = json.loads(sh("gh", "issue", "list", "--repo", REPO, "--state", "open", "--label", "0.5", "--limit", "50",
                        "--json", "number,title,labels"))
    parked = json.loads(sh("gh", "issue", "list", "--repo", REPO, "--state", "open", "--label", "blocked:after-0.5",
                           "--limit", "100", "--json", "number,title,labels"))
    since = (now - datetime.timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cm = []
    for l in sh("gh", "api", "repos/%s/issues/comments?since=%s&per_page=100" % (REPO, since), "--paginate", "--jq",
                '.[] | {c: .created_at, i: (.issue_url | split("/") | last), b: .body}').splitlines():
        c = json.loads(l)
        b = c.get("b") or ""
        if c["c"] <= NOW_ISO and ("[lane.xbox]" in b or "[lane.remote]" in b or re.match(r"^`?\[host\]", b)
                                  or b.startswith("[job.deliver]") or b.startswith("[job.arms]")):
            c["b"] = b[:3000]
            cm.append(c)
    put("gh.json", json.dumps({"now": NOW, "prs": prs, "issues_05": iss, "issues_parked": parked,
                               "decision_needed": [], "comments": cm, "releases": ["v0.4.1-j1"]}, indent=1) + "\n")


if __name__ == "__main__":
    sys.exit(main())
