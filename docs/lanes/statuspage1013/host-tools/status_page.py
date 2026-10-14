#!/usr/bin/env python3
"""Build STATUS.md (the public in-flight page) and commit it to the `status` branch of the stand-in repo.

Model-free. Sources: pm/playable-accepted.tsv, running hakux-lane-* units, the lane branches' PR.md
titles, and master's recent commits. Prints the new status commit sha, or nothing if unchanged.
"""
import csv, datetime, os, re, subprocess, sys
from zoneinfo import ZoneInfo

W = "/home/justin/hakux-work"
G = W + "/offline-git/hakuX.git"
PT = ZoneInfo("America/Los_Angeles")


def git(*a, inp=None):
    return subprocess.run(["git", "-C", G, *a], input=inp, capture_output=True, text=True, check=True).stdout.strip()


def lanes():
    out = subprocess.run(["systemctl", "--user", "list-units", "hakux-lane-*", "--no-legend", "--plain"],
                         capture_output=True, text=True).stdout
    names = sorted({m.group(1) for m in re.finditer(r"hakux-lane-([A-Za-z0-9_.-]+)\.service\s+loaded\s+active", out)})
    rows = []
    for n in names:
        ref = "lane/" + n
        try:
            tip = git("rev-parse", "--short=10", ref)
            subj = git("log", "-1", "--format=%s", ref)
            when = git("log", "-1", "--format=%cI", ref)
        except subprocess.CalledProcessError:
            continue
        title = ""
        try:
            pr = git("show", "%s:docs/lanes/%s/PR.md" % (ref, n))
            title = next((l.lstrip("# ").strip() for l in pr.splitlines() if l.strip() and not l.startswith("State")), "")
        except subprocess.CalledProcessError:
            pass
        rows.append((n, ref, tip, title or subj, when))
    return rows


def live():
    D = W + "/dispatch"
    out = ["## Right now", ""]
    units = subprocess.run(["systemctl", "--user", "list-units", "hakux-lane-*", "--no-legend", "--plain"],
                           capture_output=True, text=True).stdout
    names = sorted({m.group(1) for m in re.finditer(r"hakux-lane-([A-Za-z0-9_.-]+)\.service\s+loaded\s+active", units)})
    if names:
        out += ["| Lane | Model | Running for | Working on |", "|---|---|---|---|"]
        for n in names:
            u = "hakux-lane-%s.service" % n
            def show(prop):
                return subprocess.run(["systemctl", "--user", "show", u, "-p", prop, "--value"], capture_output=True, text=True).stdout
            m = re.search(r"--model '([^']+)'", show("ExecStart"))
            try:
                t = datetime.datetime.strptime(show("ActiveEnterTimestamp").strip().rsplit(" ", 1)[0], "%a %Y-%m-%d %H:%M:%S")
                mins = int((datetime.datetime.now() - t).total_seconds() // 60)
                age = "%dh %dm" % (mins // 60, mins % 60) if mins >= 60 else "%d min" % mins
            except ValueError:
                age = "-"
            topic = next((r[3] for r in lanes() if r[0] == n), "")
            out.append("| `%s` | %s | %s | %s |" % (n, m.group(1) if m else "-", age, topic.replace("|", "/")[:110]))
    else:
        out.append("No lane session is running.")
    out.append("")
    def n_req(d):
        try:
            return len([f for f in os.listdir(D + "/" + d) if f.endswith(".req")])
        except OSError:
            return 0
    def hold(dev):
        try:
            who = open(D + "/hold/" + dev).read().strip()
            if not who or who == "lifted":
                return None
            try:
                why = open(D + "/hold/" + dev + ".why").read().strip()
            except OSError:
                why = ""
            return (who, re.sub(r"^\S+Z \S+?: ", "", why))
        except OSError:
            return None
    devs = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout.splitlines()[1:]
    up = len([d for d in devs if d.strip().endswith("device")])
    out.append("- **Handhelds:** %d connected." % up)
    for dev, label in (("nova", "Nova"), ("thor", "Thor")):
        h = hold(dev)
        out.append("  - %s: %s" % (label, "held by `%s`" % h[0] if h else "free for the queue"))
    out.append("- **Device queue:** %d waiting, %d running." % (n_req("queue"), n_req("running")))
    try:
        rows = [r for r in csv.DictReader(open(W + "/pm/github-release-sync.tsv"), delimiter="\t")
                if r["tag"].startswith("nightly-") and r["status"].startswith("published")]
        if rows:
            r = max(rows, key=lambda x: x["tag"])
            out.append("- **Latest nightly:** `%s`, build `%s`." % (r["tag"], r["target_sha"][:10]))
    except OSError:
        pass
    out.append("")
    return out


def dashboard_blobs():
    """The rendered harness dashboard (status/index.html, built by status.sh) as index.html plus an
    index.svg that browsers display rendered when served raw. Empty if the render is stale or degraded.

    #433: status_md.build() now returns a list of chart SVGs (one per chart on
    the page -- "How close is 0.6?" then "How close is 1.0?"), not a single
    chart. chart.svg keeps its name for anything already linking it; a second
    chart, if present, is chart2.svg.
    """
    S, J = W + "/status", "/home/justin/hakuX/docs/testing/jobs"
    try:
        if datetime.datetime.now().timestamp() - os.stat(S + "/index.html").st_mtime > 2700:
            return {}
        r = subprocess.run(["python3", J + "/status_html.py", "degraded", S + "/render-facts.json", S + "/pages-facts.json"],
                           capture_output=True, text=True)
        if r.returncode == 1:
            return {}
        html = open(S + "/index.html", encoding="utf-8").read()
        sys.path.insert(0, W + "/host-tools")
        import status_md, status_svg
        md, charts = status_md.build(html)
        md += ("\n---\n\nThe per-title detail and the original layout: [index.svg]"
               "(index.svg) opens as the full page; "
               "[IN-FLIGHT.md](IN-FLIGHT.md) lists the work in progress and recent folds.\n")
        h = lambda t: git("hash-object", "-w", "--stdin", inp=t)
        blobs = {"STATUS.md": h(md), "index.html": h(html), "index.svg": h(status_svg.build(html))}
        if charts:
            blobs["chart.svg"] = h(charts[0])
        if len(charts) > 1:
            blobs["chart2.svg"] = h(charts[1])
        return blobs
    except (OSError, subprocess.CalledProcessError):
        return {}


def main():
    now = datetime.datetime.now(PT)
    led = list(csv.DictReader(open(W + "/pm/playable-accepted.tsv"), delimiter="\t"))
    today = [r for r in led if r["date_pdt"].startswith(now.strftime("%Y-%m-%d"))]
    unchecked = sum(1 for r in led if "UNCHECKED" in r["evidence"].upper())
    L = ["# hakuX status", "",
         "What is in flight right now. Generated from the working tree and updated as work lands.", "",
         "The harness dashboard is [STATUS.md](STATUS.md).", "",
         ] + live() + [
         "## 0.5 release: Playable titles", "",
         "**%d titles are confirmed Playable** (%d today), toward the 0.5 goal of 50. Each one ran for 10 minutes on a "
         "handheld at or above the frame-rate bar, and every kept frame was reviewed." % (len(led), len(today)), "",
         "| Confirmed | Title | Result |", "|---|---|---|"]
    for r in reversed(led):
        ev = r["evidence"]
        dev = "Nova" if "Nova" in ev else ("Thor" if "Thor" in ev else "")
        m = re.search(r"(?:median (\d+(?:\.\d+)?)|(\d+(?:\.\d+)?) median)", ev)
        fps = (m.group(1) or m.group(2)) if m else ""
        if ev.lower().startswith("accepted") or "accepted on" in ev or ev.startswith("verdict FAIL on play share only") or ev.lower().startswith("owner"):
            res = "Playable, accepted on review"
        else:
            res = "Playable, 10-minute run" + (" on the " + dev if dev else "")
        if fps:
            res += ", median %s fps" % fps
        L.append("| %s | %s | %s |" % (r["date_pdt"][:10], r["title"], res))
    if unchecked:
        L += ["", "%d of these still await the owner's flicker check." % unchecked]
    L += ["", "## Work in progress", ""]
    ls = lanes()
    if ls:
        L += ["| Branch | Topic | Tip | Last change |", "|---|---|---|---|"]
        for n, ref, tip, title, when in ls:
            L.append("| `%s` | %s | `%s` | %s |" % (ref, title.replace("|", "/")[:120], tip, when[:16].replace("T", " ")))
    else:
        L.append("No branch is being worked right now.")
    L += ["", "## Recently landed on master", ""]
    for line in git("log", "-60", "--format=%h %cs %s", "master").splitlines():
        h, d, s = line.split(" ", 2)
        m = re.match(r"fold: lane/\S+ \(offline\) -- (.*)", s)
        if not m:
            continue
        t = m.group(1).split("; ")[0]
        if t.startswith("State"):
            continue
        L.append("- %s %s" % (d, t[:160]))
        if len([x for x in L if x.startswith("- 20")]) >= 12:
            break
    L += ["", "_Updated %s. Rebuilt on the host every 15 minutes and pushed here at most every 30._" % now.strftime("%Y-%m-%d %H:%M %Z"), ""]
    body = "\n".join(L)

    blob = git("hash-object", "-w", "--stdin", inp=body)
    try:
        parent = git("rev-parse", "--verify", "-q", "refs/heads/status")
    except subprocess.CalledProcessError:
        parent = ""
    files = {"IN-FLIGHT.md": blob}
    if parent:
        for ln in git("ls-tree", parent).splitlines():
            meta, name = ln.split("\t", 1)
            if name in ("STATUS.md", "chart.svg", "chart2.svg", "index.html", "index.svg"):
                files[name] = meta.split()[2]
    files.update(dashboard_blobs())
    tree = git("mktree", inp="".join("100644 blob %s\t%s\n" % (b, n) for n, b in sorted(files.items())))
    if parent and git("rev-parse", parent + "^{tree}") == tree:
        return
    env = dict(os.environ, GIT_AUTHOR_NAME="hakuX status", GIT_AUTHOR_EMAIL="status@hakux.invalid",
               GIT_COMMITTER_NAME="hakuX status", GIT_COMMITTER_EMAIL="status@hakux.invalid")
    args = ["git", "-C", G, "commit-tree", tree, "-m", "status: %s" % now.strftime("%Y-%m-%d %H:%M %Z")]
    if parent:
        args[4:4] = ["-p", parent]
    c = subprocess.run(args, capture_output=True, text=True, check=True, env=env).stdout.strip()
    git("update-ref", "refs/heads/status", c, *( [parent] if parent else [] ))
    print(c)


if __name__ == "__main__":
    sys.exit(main())
