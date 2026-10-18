#!/usr/bin/env python3
"""Build the public status pages in the stand-in repo.

STATUS.md and its charts go to the `home` branch (GitHub's default, the landing page; owner 10-13: "I want the home
branch to have that link to that status.md, and that is where it should reside"), through home_page.update, which also
sets the README's Playable count from that STATUS.md. The `status` branch keeps IN-FLIGHT.md (the in-flight page), the
full dashboard as index.html/index.svg, and a STATUS.md that points at home's.

Model-free. Sources: pm/playable-accepted.tsv, running hakux-lane-* units, the lane branches' PR.md
titles, master's recent commits, and status/index.html (status.sh's render). Prints the new commits, if any.
"""
import csv, datetime, os, re, subprocess, sys, traceback
from zoneinfo import ZoneInfo

W = "/home/justin/hakux-work"
G = W + "/offline-git/hakuX.git"
PT = ZoneInfo("America/Los_Angeles")
BASE = "https://github.com/jreinach-alt/hakuX"
HOME_STATUS = BASE + "/blob/home/STATUS.md"
LOG = W + "/status/home-page.log"     # the gateway discards this script's output; a failed home update is logged here


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


def public(md):
    """home's STATUS.md is the public page: the 0.6 line, then section 1 (the bars, both charts, the release targets and
    the per-title table). The harness's own parts stay in index.svg on the status branch: the summary lines for
    sections 2-4, section 1's gate and lever notes, the decision note, and sections 2-4 (lanes, what needs a person,
    machine health)."""
    out, body = [], False
    for ln in md.split("\n"):
        if ln.startswith("# "):
            out.append("# hakuX status")
            continue
        if ln.startswith("## 2. ") or ln.startswith("**Gate:**") or ln.startswith("| lever |"):
            break
        if ln.startswith("## "):
            body = True
            ln = re.sub(r"^## \d+\. ", "## ", ln)
        elif not body and re.match(r"[2-9]\. ", ln):
            continue
        elif not body and ln.startswith("1. "):
            ln = ln[3:].split("; ")[0] + "."
        elif ln.startswith("Decided: ") or ln.startswith("Hand-reviewed rows:"):
            continue
        elif ln.startswith("### ") and out and next((o for o in reversed(out) if o.startswith("## ")), "") == "## " + ln[4:]:
            continue
        elif re.match(r"\d+ titles: ", ln):
            ln = ln.split(". ")[0] + "."
        out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(visitor(out)) + "\n"


# Owner 10-16 ("needed if we're going to have visitors"): the public table says what a visitor can act on -- how a
# title runs -- not where it is in the harness. Status words a visitor reads, in this order; a row's next step, its
# pipeline stage, the share-at-bar line, performance mode and reading method stay on the status branch's index.html.
VISITOR = ["\U0001F7E2 Playable", "\U0001F7E1 Below 30 fps", "\U0001F534 Crashes or hangs",
           "\U0001F535 Measured, not rated yet", "⚪ Not tested yet"]
KEY = ("\U0001F7E2 **Playable**: reaches gameplay on a handheld and holds 30 fps (within 5%) for at least 90% of a "
       "timed run, with no crash or hang. \U0001F7E1 **Below 30 fps**: runs, but not at full speed. "
       "\U0001F534 **Crashes or hangs**: crashes, hangs or does not start in a timed run. "
       "\U0001F535 **Measured, not rated yet**: has a frame rate reading; its rating is still to come. "
       "**fps**: the median frame rate during gameplay, the handheld it was measured on, and the date.")
MEASURED = ("Measured: titles with a frame rate reading taken during gameplay, on either handheld. Playable: titles "
            "rated Playable. The charts place each title on the date it first qualified, and the projected dates in "
            "the table assume the last 7 days' pace continues.")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def visitor(lines):
    """The harness's title table and its notes -> the visitor's: one status from VISITOR per title, the fps cell cut
    to the reading, its handheld and date, rows sorted by status then name, the untested titles folded, and no issue
    numbers."""
    rows, out, at = [], [], None
    for ln in lines:
        cells = re.split(r"(?<!\\) \| ", ln[2:-2]) if ln.startswith("| ") and ln.endswith(" |") else []
        if len(cells) == 3 and cells[0] in ("Title and next step", "Title"):
            at = len(out) if at is None else at
            continue
        if ln in ("|---|---|---|", "</details>") or ln.startswith("<details><summary>") and ln.endswith(" more not copied</summary>"):
            continue
        m = re.match(r"\*\*(.+?)\*\*(?:<br>(.*))?$", cells[0]) if len(cells) == 3 else None
        if m:
            rows.append(row(m.group(1), m.group(2) or "", cells[1], cells[2]))
            continue
        if ln.startswith("Key -- "):
            ln = KEY
        elif ln.startswith("Measured: any gameplay fps reading"):
            ln = MEASURED
        elif re.match(r"\d+ titles: ", ln):
            continue
        out.append(re.sub(r" \((#\d+)(, #\d+)*\)", "", ln))
    if at is None:
        return out
    rows.sort(key=lambda r: (r[0], r[1].lower()))
    seen = [r for r in rows if r[0] < 4]
    rest = [r for r in rows if r[0] == 4]
    n = [sum(1 for r in rows if r[0] == k) for k in range(5)]
    table = ["| Title | Status | fps |", "|---|---|---|"] + ["| **%s** | %s | %s |" % (r[1], VISITOR[r[0]], r[2]) for r in seen]
    table += ["", "<details><summary>%d titles not tested yet</summary>" % len(rest), "", "| Title |", "|---|"]
    table += ["| %s |" % r[1] for r in rest] + ["", "</details>", ""]
    table.append("%d titles: %d Playable, %d below 30 fps, %d crash or hang, %d measured but not rated yet, %d not tested "
                 "yet." % (len(rows), *n))
    lines = out[:at] + table + out[at:]
    return [ln for i, ln in enumerate(lines) if ln.strip() or (i and lines[i - 1].strip())]


def row(name, step, status, fps):
    """(VISITOR index, name, fps cell) for one harness row."""
    parts = fps.split("<br>")
    cell = ""
    if re.fullmatch(r"\*\*[\d.]+\*\*", parts[0]):
        cell = parts[0]
        m = next((re.match(r"(\w+) · (\d\d)-(\d\d)", p) for p in parts[1:] if re.match(r"\w+ · \d\d-\d\d", p)), None)
        if m:
            cell += "<br>%s, %s %d" % (m.group(1), MONTHS[int(m.group(2)) - 1], int(m.group(3)))
    if "Playable" in status:
        k = 0
    elif "below 30" in status:
        k = 1
    elif "blocked" in status and re.search(r"blocked: (crash|hang|booted)\b", step):
        k = 2
    else:
        k = 3 if cell else 4
    return k, name, cell


def dashboard_blobs():
    """The rendered harness dashboard (status/index.html, built by status.sh), split by branch:
    ({"STATUS.md", "docs/images/chart.svg", "docs/images/chart2.svg"} for home, {"index.html", "index.svg"} for
    status). Both empty if the render is stale or degraded. STATUS.md's links to the status branch's files are
    absolute: it is read on home."""
    S, J = W + "/status", "/home/justin/hakuX/docs/testing/jobs"
    try:
        if datetime.datetime.now().timestamp() - os.stat(S + "/index.html").st_mtime > 2700:
            return {}, {}
        r = subprocess.run(["python3", J + "/status_html.py", "degraded", S + "/render-facts.json", S + "/pages-facts.json"],
                           capture_output=True, text=True)
        if r.returncode == 1:
            return {}, {}
        html = open(S + "/index.html", encoding="utf-8").read()
        sys.path.insert(0, W + "/host-tools")
        import status_md, status_svg
        md, charts = status_md.build(html)
        md = public(md)     # no link to the harness board: the public page is for visitors (owner 10-16)
        h = lambda t: git("hash-object", "-w", "--stdin", inp=t)
        home = {"STATUS.md": h(md)}
        if charts:
            home["docs/images/chart.svg"] = h(charts[0])
        if len(charts) > 1:
            home["docs/images/chart2.svg"] = h(charts[1])
        return home, {"index.html": h(html), "index.svg": h(status_svg.build(html))}
    except (OSError, subprocess.CalledProcessError):
        return {}, {}


def main():
    now = datetime.datetime.now(PT)
    led = list(csv.DictReader(open(W + "/pm/playable-accepted.tsv"), delimiter="\t"))
    today = [r for r in led if r["date_pdt"].startswith(now.strftime("%Y-%m-%d"))]
    unchecked = sum(1 for r in led if "UNCHECKED" in r["evidence"].upper())
    L = ["# hakuX status", "",
         "What is in flight right now. Generated from the working tree and updated as work lands.", "",
         "The harness dashboard, with each release's targets and the progress charts, is [STATUS.md](%s)." % HOME_STATUS, "",
         ] + live() + [
         "## Playable titles", "",
         "**%d titles are confirmed Playable** (%d today). Each one ran for 10 minutes on a "
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

    home_blobs, status_blobs = dashboard_blobs()
    pointer = ("# hakuX status\n\nThe status page, with its charts, is on the home branch: [STATUS.md](%s).\n\n"
               "[IN-FLIGHT.md](IN-FLIGHT.md) lists the work in progress and recent folds.\n" % HOME_STATUS)
    files = {"IN-FLIGHT.md": git("hash-object", "-w", "--stdin", inp=body),
             "STATUS.md": git("hash-object", "-w", "--stdin", inp=pointer)}
    try:
        parent = git("rev-parse", "--verify", "-q", "refs/heads/status")
    except subprocess.CalledProcessError:
        parent = ""
    if parent:
        for ln in git("ls-tree", parent).splitlines():
            meta, name = ln.split("\t", 1)
            if name in ("index.html", "index.svg"):
                files[name] = meta.split()[2]
    files.update(status_blobs)
    tree = git("mktree", inp="".join("100644 blob %s\t%s\n" % (b, n) for n, b in sorted(files.items())))
    if not (parent and git("rev-parse", parent + "^{tree}") == tree):
        env = dict(os.environ, GIT_AUTHOR_NAME="hakuX status", GIT_AUTHOR_EMAIL="status@hakux.invalid",
                   GIT_COMMITTER_NAME="hakuX status", GIT_COMMITTER_EMAIL="status@hakux.invalid")
        args = ["git", "-C", G, "commit-tree", tree, "-m", "status: %s" % now.strftime("%Y-%m-%d %H:%M %Z")]
        if parent:
            args[4:4] = ["-p", parent]
        c = subprocess.run(args, capture_output=True, text=True, check=True, env=env).stdout.strip()
        git("update-ref", "refs/heads/status", c, *( [parent] if parent else [] ))
        print(c)

    try:
        sys.path.insert(0, W + "/host-tools")
        import home_page
        c = home_page.update(home_blobs or None)
        if c:
            print(c)
    except Exception:
        with open(LOG, "a") as fh:
            fh.write("%s home update failed\n%s\n" % (now.strftime("%Y-%m-%d %H:%M %Z"), traceback.format_exc()))
        return 1


if __name__ == "__main__":
    sys.exit(main())
