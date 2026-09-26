#!/usr/bin/env python3
"""The harness dashboard: one static page, rendered from what status.sh gathers.

    status_html.py build  --facts F.tsv --lanes L.json --md STATUS.md --json OUT.json --html OUT.html
    status_html.py render IN.json -o OUT.html
    status_html.py key    OUT.html          # the page's content key, clock masked out
    status_html.py release05 --titles DIR --results DIR --xiso DIR   # the 0.5 panel's facts rows
    status_html.py panel  IN.json           # the 0.5 panel as text

WHY A PAGE AND NOT THE ISSUE. The roll-up lived in a comment on #107. A comment
renders below the issue's timeline, and status.sh retitled the issue every
tick, so by 2026-09-26 the owner scrolled past 304 `renamed` rows (7 days) to
reach it -- and the page only grew. This page is ONE file on an orphan
`gh-pages` branch holding ONE commit: it never accumulates anything.

LAYOUT. The first screen of a 390x844 phone answers "what is going on": the
status strip (devices, queue, lanes, last fold), NEEDS ATTENTION in red, and
the release gate. Everything else (the lane table, sessions, arms, folds,
timers, the window budget) is the Markdown status.sh has always written,
converted below the fold by the small subset renderer at the end of this file.

THE PAGE IS PUBLIC. scrub() runs over every string that reaches it: no email
addresses, no tokens, no home-directory or credential paths, no LAN addresses.

Bash gathers (status.sh); this file lays out. Standard library only.
"""
import datetime
import hashlib
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import localtime
except Exception:                                   # a layout must not die on the clock
    localtime = None

# ------------------------------------------------------------------ public-safety

_SCRUB = [
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|xox[abp]-[A-Za-z0-9-]{10,})"), "[redacted]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email]"),
    # a path that names a credential store goes entirely (a path: it has a slash;
    # the word "token" in prose is not a secret)
    (re.compile(r"(?i)[~\w.-]*/[\w./-]*(\.ssh|\.netrc|\.git-credentials|hosts\.yml|token|secret|credential|password|\.pem|id_rsa|id_ed25519)[\w./-]*"), "[path]"),
    # the owner's home directory is not the reader's business
    (re.compile(r"/home/[A-Za-z0-9_.-]+"), "~"),
    (re.compile(r"/Users/[A-Za-z0-9_.-]+"), "~"),
    # LAN addresses (the console plug, the handhelds' wifi adb)
    (re.compile(r"\b(?:10|127)(?:\.\d{1,3}){3}\b|\b192\.168(?:\.\d{1,3}){2}\b|\b172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}\b"), "[lan]"),
    # MAC addresses
    (re.compile(r"\b[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}\b"), "[mac]"),
]


def scrub(s):
    s = "" if s is None else str(s)
    for rx, rep in _SCRUB:
        s = rx.sub(rep, s)
    return s


def esc(s):
    return html.escape(scrub(s), quote=True)


# ------------------------------------------------------------------ gathering glue

def _local(epoch):
    if not epoch:
        return ""
    t = datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc)
    if localtime:
        return localtime.say_time(t)
    return t.strftime("%Y-%m-%d %H:%M UTC")


def _hm(epoch):
    s = _local(epoch)
    return s[11:] if len(s) > 11 else s                 # "22:40 PDT"


# ------------------------------------------------------------------ the 0.5 panel (#432)
#
# What #433 measures the release by, read from the files that carry it. A
# count with no file behind it is printed as "no source" and names the file
# that would carry it: a zero would read as a measurement.
#   copied    titles/already-on-handhelds.json: the titles on the handhelds.
#             Staged ISOs (the xiso dir's manifest.csv, stage_xiso.py) are
#             counted beside it; nothing records a staged ISO reaching a
#             handheld yet (#430).
#   tested    results/*/verdict.json (title_verdict.py, as titles/table.py
#             reads them): a title with a verdict on either handheld.
#   Playable  the same, the latest verdict per (title, device) passing with a
#             Playable rating, on every handheld that has one.
#   Ghoulies  the newest finished soak per handheld whose request names
#             Grabbed by the Ghoulies: the median of its hakuX-perf gfps over
#             90-240 s from the first perf line (fix311/read_soak.py's clock).
# Printed as facts.tsv rows: `r05<TAB>key<TAB>value` and
# `r05gate<TAB>device<TAB>median<TAB>n<TAB>result id<TAB>ref<TAB>epoch`.

def _jload(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _soak_median(rdir, lo=90.0, hi=240.0):
    """(median gfps over lo..hi s, n) from a result dir's logcat, or (None, 0)."""
    stamp = re.compile(r"(\d\d-\d\d \d\d:\d\d:\d\d\.\d+).*?hakuX-perf.*?\bgfps=(\d+(?:\.\d+)?)")
    perf = []
    for p in sorted(os.listdir(rdir)):
        if not (p.startswith("logcat") and p.endswith(".txt")):
            continue
        try:
            fh = open(os.path.join(rdir, p), encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                m = stamp.match(line)
                if m:
                    try:
                        t = datetime.datetime.strptime("2026-" + m.group(1), "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        continue
                    perf.append((t, float(m.group(2))))
    if not perf:
        return None, 0
    perf.sort()
    t0 = perf[0][0]
    win = sorted(g for t, g in perf if lo <= (t - t0).total_seconds() <= hi)
    if not win:
        return None, 0
    n = len(win)
    med = win[n // 2] if n % 2 else (win[n // 2 - 1] + win[n // 2]) / 2
    return med, n


def release05(titles, results, xiso, devices=("thor", "nova")):
    """The panel's facts, as (kind, fields...) tuples."""
    out = []
    oh = _jload(os.path.join(titles, "already-on-handhelds.json"))
    if isinstance(oh, list):
        out.append(("r05", "copied", str(len(oh))))
    else:
        out.append(("r05", "copied", "no source: titles/already-on-handhelds.json"))
    man = os.path.join(xiso, "manifest.csv")
    try:
        with open(man, encoding="utf-8", newline="") as fh:
            import csv
            out.append(("r05", "staged", str(sum(1 for _ in csv.DictReader(fh)))))
    except OSError:
        out.append(("r05", "staged", "no source: <xiso dir>/manifest.csv"))

    latest = {}
    for p in _glob(results, "verdict.json"):
        v = _jload(p)
        if not isinstance(v, dict):
            continue
        key = (v.get("name") or v.get("title") or "?", v.get("device") or "?")
        order = (v.get("judged_utc") or "", v.get("request_id") or "")
        if key not in latest or order > latest[key][0]:
            latest[key] = (order, v)
    by_title = {}
    for (title, dev), (_, v) in latest.items():
        by_title.setdefault(title, {})[dev] = bool(v.get("pass")) and \
            str(v.get("rating_candidate") or "").startswith("Playable")
    if not os.path.isdir(results):
        out.append(("r05", "tested", "no source: dispatch results/*/verdict.json"))
        out.append(("r05", "playable", "no source: dispatch results/*/verdict.json"))
    else:
        out.append(("r05", "tested", str(len(by_title))))
        out.append(("r05", "playable", str(sum(1 for d in by_title.values() if d and all(d.values())))))

    # Newest first per handheld, and the first one with gfps in the window
    # wins: a soak on an APK that logs no hakuX-perf (the v0.4.1-j1 candidate,
    # 2026-09-26) cannot be read, and saying "no gfps" there would hide the
    # newest soak that can. The ones passed over are counted, never dropped.
    soaks = {}
    try:
        names = os.listdir(results)
    except OSError:
        names = []
    for n in names:
        rdir = os.path.join(results, n)
        q = _jload(os.path.join(rdir, "request.json"))
        if not isinstance(q, dict) or "ghoulies" not in str(q.get("title") or "").lower():
            continue
        try:
            t = os.path.getmtime(os.path.join(rdir, "DONE"))
        except OSError:
            continue
        soaks.setdefault(q.get("device") or "?", []).append((t, n, rdir, q))
    for dev in devices:
        found, unread = None, 0
        for t, n, rdir, q in sorted(soaks.get(dev, []), reverse=True)[:12]:
            med, cnt = _soak_median(rdir)
            if med is not None:
                found = (t, n, q, med, cnt)
                break
            unread += 1
        if not found:
            out.append(("r05gate", dev, "", "0", "", "", "", str(unread)))
            continue
        t, n, q, med, cnt = found
        out.append(("r05gate", dev, "%g" % med, str(cnt), n, str(q.get("ref") or "")[:10],
                    str(int(t)), str(unread)))
    return out


def _glob(d, leaf):
    try:
        names = os.listdir(d)
    except OSError:
        return []
    return [os.path.join(d, n, leaf) for n in names if os.path.exists(os.path.join(d, n, leaf))]


# ================================================================== the first screen (#432)
#
# The owner, 2026-09-26 16:20 PDT: "The goal is for me or any outsider to look
# at that and know what's going on." Four questions, answered in this order
# from the first screen: how close is 0.5, what is happening now, what needs a
# person, are the machines healthy. gather() computes all four from FACTS --
# units, the dispatch dirs, PR state and labels, territory.toml and the tracker
# on origin/board, the lane logs, and for the two sessions without a unit their
# GitHub comments -- and never from a free-text blocker string: `blocked_on`
# is shown as detail and parsed into nothing. The board writes
# `dispatch_state = blocked` on EVERY owned issue so it will not start a second
# lane; reading that word as "stuck" put four healthy lanes in the attention
# box at 16:14.
#
# Every value carries where it came from and when (`src`, `at`): a number
# without a date is a defect of this page.

STATES = ("running", "waiting on device", "in a device session", "waiting on audit", "waiting on a file",
          "waiting on owner", "parked until 0.5 ships", "finished", "stranded")

_ZONES = {"PDT": -7, "PST": -8, "UTC": 0, "GMT": 0, "Z": 0, "MST": -7, "MDT": -6, "EST": -5, "EDT": -4}


def _stamp(s):
    """Epoch of "Sat 2026-09-26 16:13:18 PDT", "2026-09-26 16:20:31 PDT" or an ISO UTC string; else None."""
    s = (s or "").strip()
    if not s:
        return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?\s*(Z|[A-Z]{3,4})?", s)
    if not m:
        return None
    zone = m.group(3) or ("Z" if s.endswith("Z") else "")
    fmt = "%Y-%m-%d %H:%M:%S" if m.group(2).count(":") == 2 else "%Y-%m-%d %H:%M"
    try:
        t = datetime.datetime.strptime(m.group(1) + " " + m.group(2), fmt)
    except ValueError:
        return None
    if zone in _ZONES:
        return int((t - datetime.timedelta(hours=_ZONES[zone])).replace(tzinfo=datetime.timezone.utc).timestamp())
    try:                                   # an unknown abbreviation: GNU date knows more zones than this table
        import subprocess
        p = subprocess.run(["date", "-d", s, "+%s"], capture_output=True, text=True, timeout=5)
        return int(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip().isdigit() else None
    except Exception:
        return None


def _lt(epoch, fmt="hm"):
    """An epoch in the display zone: "16:24", or "09-26 16:24" when not today."""
    if not epoch:
        return ""
    t = datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc)
    s = localtime.say_time(t) if localtime else t.strftime("%Y-%m-%d %H:%M UTC")   # "2026-09-26 16:24 PDT"
    if fmt == "full":
        return s
    return s[11:16] if fmt == "hm" else s[5:16]


def _dur(secs):
    secs = int(max(0, secs or 0))
    if secs < 90:
        return "%d s" % secs
    if secs < 5400:
        return "%d min" % round(secs / 60.0)
    return "%d h %02d min" % (secs // 3600, (secs % 3600) // 60)


_ABBR = re.compile(r"(?:\b(?:e\.g|i\.e|vs|etc|approx|cf|No|Fig|al|St|Mr|Ms|Dr)|\b[A-Z])\.$")


def first_sentence(text, complete=True):
    """The first whole sentence of `text`, never cut mid-word or mid-clause.

    `complete` says whether `text` is the WHOLE source: a lane's session result
    is, so a text with no terminator is itself one sentence. An excerpt (the
    120-character head in logs/lane/index.tsv) is not: only what ends at a
    terminator inside it counts, and otherwise the answer is "" rather than a
    fragment.
    """
    s = " ".join(str(text or "").split())
    s = re.sub(r"^`?\[(lane|job|host)[.\w-]*\]`?\s*[-:\u2013\u2014]*\s*", "", s)
    s = re.sub(r"^(#+\s+|>\s*)+", "", s.replace("**", "")).strip()
    if not s:
        return ""
    tick = 0
    for i, ch in enumerate(s):
        if ch == "`":
            tick ^= 1
            continue
        if tick or ch not in ".!?":
            continue
        nxt = s[i + 1:i + 3]
        # a stop is a sentence end when a space and anything but a lower-case word follow it
        if i + 1 < len(s) and not (nxt[:1] == " " and (len(nxt) < 2 or not nxt[1].islower())):
            continue
        if ch == "." and _ABBR.search(s[max(0, i - 6):i + 1]):
            continue
        out = s[:i + 1]
        if len(out) >= 12:
            return out
    if complete:
        return s if s[-1:] in ".!?" else s + "."
    return ""


def _ev(E, k, d=""):
    return E.get(k) or d


class Facts:
    """Every source the first screen reads, each read once, each failing soft."""

    def __init__(self, E):
        self.E = E
        self.W, self.D = E.get("WORK", ""), E.get("D", "")
        self.REPO, self.GH_REPO = E.get("REPO", ""), E.get("GH_REPO", "")
        self.have_gh, self.have_sd = E.get("HAVE_GH") == "1", E.get("HAVE_SD") == "1"
        self.now = int(E.get("STATUS_NOW") or datetime.datetime.now().timestamp())
        self.errors = []

    def run(self, *cmd, timeout=60):
        import subprocess
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return p.stdout if p.returncode == 0 else ""
        except Exception:
            return ""

    def read(self, *parts):
        try:
            with open(os.path.join(*parts), encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return None

    def mtime(self, *parts):
        try:
            return int(os.path.getmtime(os.path.join(*parts)))
        except OSError:
            return None

    def board(self, name):
        try:
            import tomllib
        except ImportError:
            return None
        bd = self.E.get("STATUS_BOARD_DIR")
        t = self.read(bd, name) if bd else self.run("git", "-C", self.REPO, "show", "origin/board:" + name)
        try:
            return tomllib.loads(t) if t else None
        except Exception:
            return None

    def gh_json(self, *args, default=None):
        if not self.have_gh:
            return default
        out = self.run("gh", *args, timeout=120)
        try:
            return json.loads(out) if out.strip() else default
        except ValueError:
            return default


def _conf(E):
    """release-0.5.toml, and the path it was read from."""
    here = os.path.dirname(os.path.abspath(__file__))
    p = E.get("STATUS_RELEASE_CONF") or os.path.join(here, "..", "..", "lanes", "dash432", "release-0.5.toml")
    try:
        import tomllib
        with open(p, "rb") as fh:
            return tomllib.load(fh), os.path.normpath(p)
    except Exception:
        return {}, os.path.normpath(p)


def _expected_secs(r):
    """A request's expected wall time: its title seconds plus install, boot and
    pull (~3 min), or ~5 min per suite run. An estimate, labelled so."""
    runs = max(1, int(r.get("runs") or 1)) if str(r.get("runs") or "1").isdigit() else 1
    secs = int(r.get("seconds") or 0) if str(r.get("seconds") or "0").isdigit() else 0
    return (secs + 180) * runs if secs else 300 * runs


def _hold_of(F, dev):
    """dispatch/hold/<dev>: who holds it, why, since when, until when."""
    hp = os.path.join(F.D, "hold", dev)
    if not os.path.exists(hp):
        return None
    who = (F.read(hp) or "").strip().splitlines()
    why = (F.read(hp + ".why") or "").strip()
    start = F.mtime(hp + ".why") or F.mtime(hp)
    holder = who[0].strip() if who and who[0].strip() else ""
    m = re.match(r"^\s*([\w.-]+(?:\s*\([^)]*\))?)\s*:\s*(.*)$", why, re.S)
    if m:
        holder = holder or m.group(1).split("(")[0].strip()
        purpose = m.group(2)
        via = m.group(1)
    else:
        purpose, via = why, ""
    purpose = " ".join(purpose.split()).rstrip(".")
    end, end_src = None, ""
    # "until 16:41 PDT", "until 16:41" (the display zone, same day as the hold)
    mu = re.search(r"\buntil\s+(\d{1,2}):(\d{2})\s*([A-Z]{3,4})?", why)
    md = re.search(r"~\s*(\d+)\s*min", why)
    if mu and start:
        st_local = _lt(start, "full")                               # "2026-09-26 16:13 PDT"
        cand = _stamp("%s %02d:%s %s" % (st_local[:10], int(mu.group(1)), mu.group(2), mu.group(3) or st_local[17:]))
        if cand is not None:
            end, end_src = cand, "stated"
    elif md and start:
        end, end_src = start + int(md.group(1)) * 60, "start + stated duration"
    return {"holder": holder or "unknown", "via": via, "purpose": purpose, "start": start, "end": end,
            "end_src": end_src, "why": why}


def gather(E):
    F = Facts(E)
    now = F.now
    conf, conf_path = _conf(E)
    rel_name = str(conf.get("name") or E.get("STATUS_RELEASE_NAME") or "0.5")
    terr = F.board("territory.toml")
    tracker = (F.board("nv2a_issues.toml") or {}).get("issue", {})
    lanes_rows = (terr or {}).get("lane", {})
    board_src = "territory.toml and nv2a_issues.toml on origin/board" if not E.get("STATUS_BOARD_DIR") else "the board files in STATUS_BOARD_DIR"

    # ---- units: live sessions, with their start
    units = {}
    for u in E.get("UNITS", "").split():
        if u.startswith("hakux-lane-") and u.endswith(".service"):
            n = u[len("hakux-lane-"):-len(".service")]
            ts = F.run("systemctl", "--user", "show", u, "-p", "ActiveEnterTimestamp", "--value") if F.have_sd else ""
            units[n] = _stamp(ts)

    # ---- timers: the automation box
    timers = {}
    if F.have_sd:
        for l in F.run("systemctl", "--user", "list-timers", "hakux-*", "--all", "--no-legend", "--plain").splitlines():
            m = re.search(r"hakux-([\w.-]+)\.timer", l)
            if not m:
                continue
            st = re.findall(r"\w{3} \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [A-Z]{2,5}", l)
            if l.strip().startswith(("-", "n/a")):
                nxt, last = None, (_stamp(st[0]) if st else None)
            else:
                nxt = _stamp(st[0]) if st else None
                last = _stamp(st[1]) if len(st) > 1 else None
            timers[m.group(1)] = {"next": nxt, "last": last}

    # ---- the dispatch dirs
    reqs = []
    for state in ("running", "queue"):
        for p in sorted(glob_(os.path.join(F.D, state), ".req")):
            try:
                r = json.load(open(p, encoding="utf-8"))
            except Exception:
                r = {}
            rid = r.get("id") or os.path.basename(p)[:-4]
            reqs.append({"state": state, "id": rid, "file": os.path.basename(p)[:-4],
                         "requester": r.get("requester") or "", "purpose": " ".join(str(r.get("purpose") or "").split()),
                         "device": r.get("device") or "", "title": r.get("title") or "",
                         "owner": (F.read(p[:-4] + ".owner") or "").strip(),
                         "queued": _stamp(r.get("queued_utc") or "") or F.mtime(p),
                         "since": F.mtime(p), "expected": _expected_secs(r)})
    devices_all = E.get("STATUS_DEVICES", "thor nova").split()
    holds = {d: _hold_of(F, d) for d in devices_all}

    # ---- GitHub: PRs, labels, comments
    prs, prs_ok = {}, False
    pl = F.gh_json("pr", "list", "--repo", F.GH_REPO, "--state", "all", "--limit", "300",
                   "--json", "number,state,isDraft,headRefName,labels,mergedAt,title", default=None)
    if isinstance(pl, list):
        prs_ok = True
        for p in pl:
            prs.setdefault(p.get("headRefName", ""), p)
    def issue_list(label):
        v = F.gh_json("issue", "list", "--repo", F.GH_REPO, "--state", "open", "--label", label,
                      "--limit", "100", "--json", "number,title,labels", default=None)
        return v if isinstance(v, list) else None
    r05_issues = issue_list(rel_name)
    parked_label = str(conf.get("parked_label") or "blocked:after-0.5")
    parked_issues = issue_list(parked_label)
    dn_issues = issue_list("decision-needed") or []
    r05_nums = {str(i["number"]) for i in (r05_issues or [])}
    parked_nums = {str(i["number"]) for i in (parked_issues or [])}
    dn_nums = {str(i["number"]) for i in dn_issues}
    comments = []
    if F.have_gh:
        since = datetime.datetime.fromtimestamp(now - 48 * 3600, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for l in F.run("gh", "api", "repos/%s/issues/comments?since=%s&per_page=100" % (F.GH_REPO, since), "--paginate",
                       "--jq", '.[] | {c: .created_at, i: (.issue_url | split("/") | last), b: .body, u: .html_url}',
                       timeout=120).splitlines():
            try:
                c = json.loads(l)
            except ValueError:
                continue
            if (_stamp(c.get("c")) or 0) <= now:
                comments.append(c)
    comments.sort(key=lambda c: c.get("c", ""))

    # ---- lane session logs: the last session per lane, and its full result
    last = {}
    idx = F.read(F.W, "logs/lane/index.tsv") or ""
    for l in idx.splitlines():
        f = l.split("\t")
        if len(f) >= 8 and f[1].startswith("lane-"):
            js = next((x for x in f if x.endswith(".json")), "")
            last[f[1][5:]] = {"at": _stamp(f[0]), "json": js, "head": f[-1]}

    def said(name):
        """(one complete sentence, source) from the lane's last session."""
        l = last.get(name)
        if not l:
            return "", ""
        if l["json"]:
            try:
                r = json.loads(F.read(F.W, "logs/lane", l["json"]) or "{}").get("result") or ""
            except ValueError:
                r = ""
            s = first_sentence(r, complete=True)
            if s:
                return s, "logs/lane/" + l["json"]
        return first_sentence(l["head"], complete=False), "logs/lane/index.tsv"

    def attempts(name):
        a = (F.read(F.W, "attempts", name) or "").strip()
        return int(a) if a.isdigit() else None

    def reqs_of(name):
        pat = re.compile(r"^(lane[.-])?%s$|^arms-%s-" % (re.escape(name), re.escape(name)))
        return [r for r in reqs if pat.search(r["requester"])]

    # ---- the queue, as the dispatcher will drain it: file order, a pinned
    # request only on its device, each device free when its run or hold ends.
    free = {}
    for d in devices_all:
        run_d = [r for r in reqs if r["state"] == "running" and r["owner"] == d]
        t = now
        if run_d:
            t = max(t, (run_d[0]["since"] or now) + run_d[0]["expected"])
        h = holds.get(d)
        if h:
            t = max(t, h["end"] or now)
        free[d] = t
    order = sorted([r for r in reqs if r["state"] == "queue"], key=lambda r: r["file"])
    pos = 0
    for r in order:
        if r["file"].startswith("z-"):
            r["pos"], r["eta"] = None, None
            continue
        pos += 1
        r["pos"] = pos
        el = [r["device"]] if r["device"] in free else list(free)
        if not el:
            r["eta"] = None
            continue
        d = min(el, key=lambda x: free[x])
        r["eta"], r["eta_dev"] = free[d], d
        free[d] += r["expected"]

    lane_issue = {}
    for n, row in lanes_rows.items():
        for i in row.get("issues", []):
            lane_issue.setdefault(str(i), []).append(n)

    def is05(requester):
        m = re.match(r"^(?:lane[.-])?([\w-]+?)(?:$|-(?:base|fix)$)", requester.replace("arms-", "", 1) if requester.startswith("arms-") else requester)
        n = m.group(1) if m else requester
        return any(str(i) in r05_nums for i in lanes_rows.get(n, {}).get("issues", []))
    for r in reqs:
        r["r05"] = is05(r["requester"])

    def issue_words(i):
        t = tracker.get(str(i), {}).get("title") or next((x["title"] for x in (r05_issues or []) if str(x["number"]) == str(i)), "")
        return ("#%s %s" % (i, t)).strip()

    # ---- file waits: an owned issue's board note names a path another live lane holds
    held_by = {}
    for n, row in lanes_rows.items():
        rel = set(row.get("released", []))
        for f in row.get("files", []):
            if f not in rel and "*" not in f:
                held_by[f] = n
    def file_wait(name, row):
        for i in row.get("issues", []):
            t = tracker.get(str(i), {})
            if t.get("status") not in ("open", None) or t.get("status") is None and not t:
                continue
            note = " ".join(str(t.get(k) or "") for k in ("blocked_on", "status_note"))
            for path in re.findall(r"[\w./-]+/[\w.-]+\.\w+", note):
                for f, who in held_by.items():
                    if who != name and (f == path or f.endswith("/" + path)) and f not in row.get("files", []):
                        return f, who, str(i)
        return None

    # ---- each lane, one state from the fixed vocabulary
    rows, parked, finished, stranded = [], [], [], []
    jobs = set(timers)
    for name, row in sorted(lanes_rows.items()):
        if name in ("xbox", "remote"):
            continue
        iss = [str(i) for i in row.get("issues", [])]
        p = prs.get("lane/" + name)
        labels = {l["name"] for l in (p or {}).get("labels", [])}
        standing = bool(row.get("standing"))
        if name in jobs or (standing and not iss and not p and name not in units):
            continue                                            # a job's row, not a lane: the automation box
        s, l_ago = said(name)
        base = {"lane": name, "kind": "local lane", "issues": iss,
                "issue": "; ".join(issue_words(i) for i in iss) if iss else "(harness work, no tracker issue)",
                "pr": ("#%d" % p["number"]) if p else "", "pr_state": (("draft" if p.get("isDraft") else p["state"].lower()) if p else "none"),
                "attempt": attempts(name), "result": s, "result_src": l_ago,
                "result_at": (last.get(name) or {}).get("at"), "detail": ""}
        rq = reqs_of(name)
        fw = file_wait(name, row)
        if name in units:
            st = dict(base, state="running", waiting="", since=units[name] or None,
                      step="session %s" % (base["attempt"] or 1))
        elif iss and all(i in parked_nums for i in iss):
            parked.append(dict(base, state="parked until %s ships" % rel_name, gate=str(conf.get("parked_gate") or "#433 closes")))
            continue
        elif [i for i in iss if i in dn_nums] or "decision-needed" in labels:
            q = [i for i in iss if i in dn_nums]
            st = dict(base, state="waiting on owner", waiting="decision on " + (issue_words(q[0]) if q else "PR " + base["pr"]),
                      since=base["result_at"], step="")
        elif fw:
            st = dict(base, state="waiting on a file", waiting="%s, held by lane.%s" % (fw[0], fw[1]),
                      since=base["result_at"], step="")
        elif p and p.get("state") == "MERGED":
            finished.append(dict(base, state="finished", merged=_stamp(p.get("mergedAt")), src="PR %s merged" % base["pr"]))
            continue
        elif rq:
            nr = [r for r in rq if r["state"] == "running"]
            nq = sorted([r for r in rq if r["state"] == "queue"], key=lambda r: r["file"])
            if nr:
                w = "running on the %s: %s" % (nr[0]["owner"] or "?", nr[0]["purpose"] or nr[0]["id"])
            else:
                w = ""
            if nq:
                f0 = nq[0]
                w += ("; " if w else "") + "%d run%s queued, first at position %s%s" % (
                    len(nq), "" if len(nq) == 1 else "s", f0.get("pos") or "?",
                    (", estimated start %s" % _lt(f0["eta"])) if f0.get("eta") else "")
            st = dict(base, state="waiting on device", waiting=w, since=min(r["queued"] or now for r in rq), step="")
        elif any(h and h["holder"] in ("lane." + name, name) for h in holds.values()):
            d = next(d for d, h in holds.items() if h and h["holder"] in ("lane." + name, name))
            st = dict(base, state="in a device session", waiting="holds the %s: %s" % (d, holds[d]["purpose"]),
                      since=holds[d]["start"], step="")
        elif p and p.get("state") == "OPEN" and not p.get("isDraft"):
            for lab, say in (("needs-audit-1", "audit pass 1"), ("needs-audit-2", "audit pass 2"), ("fold-ready", "the fold"),
                             ("needs-remediation", "remediation of the audit's findings"), ("needs-rebase", "a merge of master")):
                if lab in labels:
                    break
            else:
                say = "an audit label (the PR is ready and unlabelled)"
            st = dict(base, state="waiting on audit", waiting="PR %s: %s" % (base["pr"], say), since=base["result_at"], step="")
        else:
            why = "no session, nothing queued or running on a device, not parked"
            if not prs_ok:
                st = dict(base, state="waiting on audit", waiting="(PR state unknown: the PR list could not be read)",
                          since=base["result_at"], step="")
            else:
                st = dict(base, state="stranded", waiting=why + ("; PR %s is a %s" % (base["pr"], base["pr_state"]) if p else "; no PR"),
                          since=base["result_at"], step="")
                stranded.append(name)
        # the board's own words, as detail only
        bo = [tracker.get(i, {}).get("blocked_on") for i in iss if tracker.get(i, {}).get("blocked_on")]
        st["note"] = " ".join(bo[0].split()) if bo else ""
        rows.append(st)
    for name in sorted(set(units) - set(lanes_rows)):
        s, src = said(name)
        rows.append({"lane": name, "kind": "local lane", "issues": [], "issue": "(no territory row)", "pr": "", "pr_state": "",
                     "attempt": attempts(name), "result": s, "result_src": src, "result_at": (last.get(name) or {}).get("at"),
                     "state": "running", "waiting": "", "since": units[name], "step": "session %s" % (attempts(name) or 1),
                     "detail": "running with no territory row"})

    # retired within the day: Finished today
    for name, row in (terr or {}).get("retired", {}).items():
        ru = _stamp(row.get("retired_utc", ""))
        if not ru or now - ru > 86400 or name in lanes_rows:
            continue
        p = prs.get("lane/" + name)
        s, src = said(name)
        finished.append({"lane": name, "kind": "local lane", "issues": [str(i) for i in row.get("issues", [])],
                         "issue": "; ".join(issue_words(i) for i in row.get("issues", [])) or "(harness work)",
                         "pr": ("#%d" % p["number"]) if p else "", "state": "finished",
                         "merged": _stamp((p or {}).get("mergedAt")) or ru,
                         "src": ("PR #%d merged" % p["number"]) if p and p.get("mergedAt") else "row retired",
                         "result": s, "result_src": src})
    finished.sort(key=lambda r: -(r.get("merged") or 0))
    today = _lt(now, "full")[:10]                        # "today" is the reader's day, in the display zone
    finished = [r for r in finished if r.get("merged") and _lt(r["merged"], "full")[:10] == today]

    # ---- the two sessions without a unit
    def is_other(b):
        return b.startswith("[job.") or re.match(r"^`?\[host\]", b) is not None
    def last_word(marker):
        m = [c for c in comments if not is_other(c.get("b") or "") and marker in (c.get("b") or "")]
        return m[-1] if m else None
    def answered_after(name, t):
        a = [c for c in comments if (c.get("c") or "") > t and (
            (c.get("b") or "").startswith("[job.deliver] lane." + name) or
            (re.match(r"^`?\[host\]", c.get("b") or "") and ("lane." + name) in (c.get("b") or "")))]
        return a[-1] if a else None

    push = _title_push(F, now)
    for name, marker, kind in (("xbox", "[lane.xbox]", "console session"), ("remote", "`[lane.remote]`", "cloud session")):
        row = lanes_rows.get(name, {})
        iss = [str(i) for i in row.get("issues", [])]
        lw = last_word(marker) if F.have_gh else None
        ans = answered_after(name, lw["c"]) if lw else None
        r = {"lane": name, "kind": kind, "issues": iss,
             "issue": "; ".join(issue_words(i) for i in iss if i in r05_nums) or "; ".join(issue_words(i) for i in iss[:2]),
             "pr": "", "attempt": None, "detail": "",
             "result": first_sentence(lw["b"], complete=True) if lw else "",
             "result_src": ("comment on #%s" % lw["i"]) if lw else "", "result_url": (lw or {}).get("u", ""),
             "result_at": _stamp(lw["c"]) if lw else None}
        if name == "xbox" and push.get("active"):
            r.update(state="running", step=push["progress"], waiting="", since=push.get("since"),
                     detail="title push unit hakux-xbox-titlepush active" + (
                         "; the host has not answered its %s comment" % _lt(_stamp(lw["c"])) if lw and not ans else ""))
        elif lw and not ans:
            r.update(state="waiting on host", step="", waiting="the host has not answered its %s comment" % _lt(_stamp(lw["c"])),
                     since=_stamp(lw["c"]))
        elif lw:
            r.update(state="running", step=push.get("progress", "") if name == "xbox" else "",
                     waiting="", since=_stamp(lw["c"]), detail="host answered %s" % _lt(_stamp(ans["c"])))
        else:
            r.update(state="no word in 48 h" if F.have_gh else "unknown (gh not available)", step="", waiting="", since=None)
        rq = reqs_of(name)
        if rq:
            r["waiting"] = (r["waiting"] + "; " if r["waiting"] else "") + "%d device run%s queued" % (len(rq), "" if len(rq) == 1 else "s")
        rows.append(r)
    rank = {"running": 0, "waiting on device": 1, "in a device session": 2, "waiting on audit": 3, "waiting on a file": 4,
            "waiting on owner": 5, "waiting on host": 6, "stranded": -1}
    rows.sort(key=lambda r: (rank.get(r["state"], 7), r["kind"] != "local lane", r["lane"]))

    # ---- automation
    automation = _automation(F, timers, lanes_rows, now)

    # ---- devices
    devices = []
    for d in devices_all:
        run_d = [r for r in reqs if r["state"] == "running" and r["owner"] == d]
        h = holds.get(d)
        if run_d:
            r = run_d[0]
            devices.append({"name": d, "state": "running", "who": r["requester"], "purpose": r["purpose"] or r["id"],
                            "since": r["since"], "expected": r["expected"], "id": r["id"],
                            "held_after": bool(h), "src": "dispatch/running/%s.req" % r["file"]})
        elif h:
            devices.append({"name": d, "state": "in use", "who": h["holder"], "purpose": h["purpose"],
                            "since": h["start"], "until": h["end"], "until_src": h["end_src"],
                            "src": "dispatch/hold/%s.why" % d})
        else:
            dl = _last_done(F, d)
            devices.append({"name": d, "state": "idle", "since": dl, "src": "dispatch/results (newest DONE)"})

    # ---- the queue
    nz = [r for r in reqs if r["state"] == "queue" and not r["file"].startswith("z-")]
    zq = [r for r in reqs if r["state"] == "queue" and r["file"].startswith("z-")]
    q05 = [r for r in nz if r["r05"]]
    busy = [d for d in devices if d["state"] != "idle"]
    ends = [r["eta"] + r["expected"] for r in nz if r.get("eta")]
    drain = (max(ends) - now) if ends else 0
    if not nz:
        constraint = "no queue: the devices are not the constraint"
    elif len(busy) == len(devices):
        constraint = "device-bound: %d run%s queued, %s" % (len(nz), "" if len(nz) == 1 else "s",
                                                       "both devices busy" if len(devices) == 2 else "every device busy")
    else:
        constraint = "%d run%s queued while %s idle" % (len(nz), "" if len(nz) == 1 else "s",
                                                     " and ".join(d["name"] for d in devices if d["state"] == "idle"))
    oldest05 = min((r["queued"] for r in q05 if r["queued"]), default=None)
    queue = {"queued": len(nz), "queued_05": len(q05), "idle_tier": len(zq), "running": sum(r["state"] == "running" for r in reqs),
             "oldest_05": oldest05, "oldest_05_age": (now - oldest05) if oldest05 else None,
             "drain_secs": drain, "constraint": constraint,
             "src": "dispatch/queue and running; durations estimated (title seconds + 3 min, 5 min per suite run)"}

    # ---- what needs a person
    person = []
    esc_src = os.path.join(F.W, "host-tools/escalations.md")
    for l in (F.read(esc_src) or "").splitlines():       # one decision per line, whole
        l = l.strip()
        if not l or l.startswith("#") or "RESOLVED" in l:
            continue
        l = re.sub(r"^[-*]\s+", "", l)
        m = re.match(r"^(OWNER ONLY[^(:]*)?\(([^)]*)\)\s*:\s*(.*)$", l)
        at = None
        if m:
            meta, text = m.group(2), m.group(3)
            mt = re.search(r"(\d{2}-\d{2}) (\d{1,2}:\d{2}) ?([A-Z]{3})?", meta)
            if mt:
                at = _stamp("%s-%s %s %s" % (_lt(now, "full")[:4], mt.group(1), mt.group(2), mt.group(3) or "PDT"))
        else:
            meta, text = "", l
        person.append({"kind": "decision", "who": "owner", "action": text, "src": "host-tools/escalations.md" + (", %s" % meta if meta else ""), "at": at})
    for i in dn_issues:
        person.append({"kind": "decision", "who": "owner", "action": "decide #%s: %s" % (i["number"], i["title"]),
                       "src": "issue #%s, label decision-needed" % i["number"], "at": None})
    for r in rows:
        if r["state"] == "stranded":
            person.append({"kind": "stranded lane", "who": "host",
                           "action": "lane.%s has no session, nothing on a device and is not parked (PR %s %s); nothing will wake it. Give it what it waits for and resume it, or retire its row." % (
                               r["lane"], r["pr"] or "none", r["pr_state"]),
                           "detail": ("its last word: " + r["result"]) if r["result"] else "",
                           "src": "territory row, no unit, no request, " + ("PR " + r["pr"] if r["pr"] else "no PR"), "at": r.get("since")})
    for d in devices:
        if d["state"] == "in use" and d.get("until") and now > d["until"] + 300:
            person.append({"kind": "device", "who": d["who"], "action": "the %s hold passed its stated end %s (%s ago): lift it (dispatch/hold/%s) or restate its end" % (
                d["name"], _lt(d["until"]), _dur(now - d["until"]), d["name"]), "src": d["src"], "at": d["until"]})
        if d["state"] == "running" and d.get("since") and now - d["since"] > 2 * d["expected"]:
            person.append({"kind": "device", "who": "host", "action": "run %s on the %s has run %s, over twice its expected %s: check the dispatcher" % (
                d["id"], d["name"], _dur(now - d["since"]), _dur(d["expected"])), "src": d["src"], "at": d["since"]})
        if d["state"] == "idle":
            runnable = [r for r in nz if r["device"] in ("", d["name"])]
            if runnable and d.get("since") and now - d["since"] > 300:
                person.append({"kind": "device", "who": "host", "action": "the %s has been idle %s with %d runnable run%s queued: check hakux-dispatcher.service" % (
                    d["name"], _dur(now - d["since"]), len(runnable), "" if len(runnable) == 1 else "s"), "src": d["src"], "at": d["since"]})
    nh = _needs_hands(F, E, now, [p["action"] for p in person if p["kind"] == "decision"])
    person += nh

    return {"now": now, "conf": conf, "conf_path": conf_path, "release_name": rel_name,
            "lanes": rows, "parked": parked, "finished": finished, "stranded": stranded,
            "automation": automation, "devices": devices, "queue": queue, "person": person,
            "console": {"meter": E.get("STATUS_METER", ""), "push": push},
            "levers": _levers(conf, tracker, lanes_rows, prs, comments, reqs, lane_issue, now),
            "titles": titles05(F, conf, conf_path, now),
            "r05_issues": r05_issues, "board_ok": terr is not None, "prs_ok": prs_ok, "board_src": board_src,
            "reqs": reqs}


def glob_(d, ext):
    try:
        return [os.path.join(d, n) for n in os.listdir(d) if n.endswith(ext)]
    except OSError:
        return []


def _last_done(F, dev):
    """When the device last finished a run: the newest results/*/DONE whose result names it."""
    best = None
    rd = os.path.join(F.D, "results")
    try:
        names = os.listdir(rd)
    except OSError:
        return None
    for n in names:
        t = F.mtime(rd, n, "DONE")
        if not t or t > F.now or (best and t <= best):
            continue
        r = _jload(os.path.join(rd, n, "result.json")) or {}
        q = _jload(os.path.join(rd, n, "request.json")) or {}
        if (r.get("device_label") or q.get("device")) == dev:
            best = t
    return best


def _title_push(F, now):
    """lane.xbox's #430 title push: pushes recorded tonight, the batch size, the unit."""
    out = {"active": False, "progress": "", "src": "logs/titlepipe/batch-xbox-*.tsv", "pushed": []}
    files = sorted(glob_(os.path.join(F.W, "logs/titlepipe"), ".tsv"))
    for p in files:
        b = os.path.basename(p)
        if not b.startswith("batch-"):
            continue
        for l in (F.read(p) or "").splitlines()[1:]:
            f = l.split("\t")
            if len(f) >= 5 and re.match(r"^\d+$", f[0]) and re.match(r"^\d{2}-\d{2} \d{2}:\d{2}$", f[-1]):
                out["pushed"].append({"name": f[2], "device": f[3], "at": f[-1], "batch": b})
    tonight = [x for x in out["pushed"] if x["batch"].startswith("batch-xbox-")]
    target = None
    log = F.read(F.W, "logs/titlepipe/xbox-push.out") or ""
    m = re.findall(r"=== batch start: (\d+) titles", log)
    if m:
        target = int(m[-1])
    if tonight:
        latest = sorted(x["batch"] for x in tonight)[-1]
        tn = [x for x in tonight if x["batch"] == latest]
        out["progress"] = "%d%s titles pushed in %s, the last at %s" % (
            len(tn), (" of %d" % target) if target else "", latest, tn[-1]["at"])
    if F.have_sd:
        st = F.run("systemctl", "--user", "is-active", "hakux-xbox-titlepush.service").strip()
        out["active"] = st in ("active", "activating")
        if out["active"]:
            out["since"] = _stamp(F.run("systemctl", "--user", "show", "hakux-xbox-titlepush.service", "-p",
                                        "ActiveEnterTimestamp", "--value"))
    return out


def _needs_hands(F, E, now, decisions):
    """recovery/needs-hands.txt, only while it belongs to this boot (as attention.sh shows it)."""
    p = os.path.join(F.W, "recovery/needs-hands.txt")
    t = F.mtime(p)
    if not t:
        return []
    boot = E.get("STATUS_BOOT_EPOCH")
    if not boot:
        try:
            boot = now - int(float(open("/proc/uptime").read().split()[0]))
        except (OSError, ValueError, IndexError):
            boot = 0
    if t < int(boot):
        return []
    out = []
    def words(s):
        return {w for w in re.findall(r"[a-z]{4,}", s.lower())}
    for l in (F.read(p) or "").splitlines():
        l = l.strip()
        if not l or l.startswith("(") or "RESOLVED" in l:
            continue
        w = words(l)
        # the same ask already on the owner's list is one item, not two
        if any(w and len(w & words(d)) >= 0.6 * len(w) for d in decisions):
            continue
        out.append({"kind": "recovery", "who": "owner", "action": l, "src": "recovery/needs-hands.txt", "at": t})
    return out


def _automation(F, timers, lanes_rows, now):
    """The timer jobs: last run, next run, last outcome."""
    names = sorted(set(timers) | {n for n in ("arms", "fold", "board", "hostops", "handback", "pr-sweep", "issue-sweep", "cloud")
                                  if os.path.isdir(os.path.join(F.W, "logs", n))})
    out = []
    for n in names:
        t = timers.get(n, {})
        last, outcome, src = t.get("last"), "", ""
        if n == "board":
            rows = [l.split("\t") for l in (F.read(F.W, "logs/board/index.tsv") or "").splitlines() if l.strip()]
            rows = [r for r in rows if len(r) >= 8 and (_stamp(r[0]) or 0) <= now]
            if rows:
                last = max(last or 0, _stamp(rows[-1][0]) or 0) or None
                outcome, src = first_sentence(rows[-1][-1], complete=False), "logs/board/index.tsv"
        elif n == "hostops":
            txt = F.read(F.W, "logs/hostops/digest.log") or ""
            blocks = re.split(r"(?m)^=== ", txt)
            if len(blocks) > 1:
                head, _, body = blocks[-1].partition("\n")
                m = re.match(r"(\d{8}T\d{6}Z)", head)
                if m:
                    lt = int(datetime.datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=datetime.timezone.utc).timestamp())
                    last = max(last or 0, lt)
                # the digest's body can open mid-sentence (the tick's own summary is cut to fit):
                # the first line that starts like a sentence, then its first sentence
                cand = [re.sub(r"^[-*\s]+", "", l) for l in body.splitlines() if l.strip()]
                outcome = first_sentence(next((l for l in cand if re.match(r"^(\*\*)?[A-Z#]", l)), ""), complete=True)
                src = "logs/hostops/digest.log"
        else:
            tl = F.read(F.W, "logs", n, "tick.log")
            if tl:
                top = [l for l in tl.splitlines() if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [A-Z]{3,4} \S", l)]
                top = [l for l in top if (_stamp(l[:24]) or 0) <= now]
                if top:
                    l = top[-1]
                    last = max(last or 0, _stamp(l[:24]) or 0) or None
                    outcome = " ".join(l.split()[3:])
                    src = "logs/%s/tick.log" % n
        out.append({"job": n, "last": last, "next": t.get("next"), "outcome": outcome, "src": src or "systemctl --user list-timers",
                    "timer": n in timers})
    return out


def _levers(conf, tracker, lanes_rows, prs, comments, reqs, lane_issue, now):
    """One line per performance lever: words, owner lane, measured effect so far."""
    out = []
    for i in [str(x) for x in conf.get("levers", [])]:
        t = tracker.get(i, {})
        lanes = lane_issue.get(i, [])
        lane = lanes[0] if lanes else ""
        words = re.sub(r"^Performance:\s*", "", t.get("title") or "#" + i)
        p = prs.get("lane/" + lane) if lane else None
        verdicts = []
        if p:
            for c in comments:
                b = c.get("b") or ""
                if c.get("i") == str(p["number"]) and b.startswith("[job.arms] VERDICT"):
                    verdicts.append((c["c"], first_sentence(b, complete=True), c.get("u", "")))
        rq = [r for r in reqs if lane and re.search(r"^(lane[.-])?%s$|^arms-%s-" % (re.escape(lane), re.escape(lane)), r["requester"])]
        if t.get("status") == "closed":
            eff = first_sentence(t.get("status_note") or "closed", complete=True)
            eff_src = "board: issue #%s closed" % i
        elif verdicts:
            v = verdicts[-1]
            eff = "arm " + v[1]
            eff_src = "[job.arms] on PR #%s, %s" % (p["number"], _lt(_stamp(v[0]), "md"))
        elif rq:
            eff = "not measured yet: %d device run%s queued for it" % (len(rq), "" if len(rq) == 1 else "s")
            eff_src = "dispatch/queue"
        elif not lane:
            eff = "not measured yet: no lane holds it (%s)" % (first_sentence(t.get("blocked_on") or "", complete=True) or "not dispatched")
            eff_src = "board: issue #%s" % i
        else:
            eff = "not measured yet: no arm or device run registered"
            eff_src = "arms comments, dispatch/queue"
        out.append({"issue": i, "words": words, "lane": ("lane." + lane) if lane else "none",
                    "expected": t.get("impact_basis", "").replace("0.5 performance lever: ", ""),
                    "effect": eff, "src": eff_src, "pr": ("#%d" % p["number"]) if p else ""})
    return out


def titles05(F, conf, conf_path, now):
    """The 0.5 test list: one row per title on either handheld, with its measurements.

    Rows: titles/already-on-handhelds.json (device not recorded), plus every
    title lane.xbox's pushes recorded (logs/titlepipe/batch-*.tsv), plus the
    backfill's titles. Measurements: title_verdict.py's results/*/verdict.json
    (newest per title and device), else the backfill's hand-reviewed rows.
    The counts are computed from these rows and nothing else.
    """
    tdir = F.E.get("STATUS_TITLES_DIR") or os.path.join(F.W, "titles")
    titles, where, srcs = [], {}, []
    oh = _jload(os.path.join(tdir, "already-on-handhelds.json"))
    if isinstance(oh, list):
        srcs.append("titles/already-on-handhelds.json")
        for n in oh:
            if n not in where:
                titles.append(n)
                where[n] = set()
    push = _title_push(F, now)
    if push["pushed"]:
        srcs.append("logs/titlepipe/batch-*.tsv")
    for x in push["pushed"]:
        if x["name"] not in where:
            titles.append(x["name"])
            where[x["name"]] = set()
        where[x["name"]].add(x["device"])
    bf_path = os.path.join(os.path.dirname(conf_path), str(conf.get("backfill") or "pass1-backfill.json"))
    bf = _jload(bf_path) or {}
    prov = bf.get("provenance", {})
    meas = {}
    for r in bf.get("rows", []):
        n = r.get("title")
        if n not in where:
            titles.append(n)
            where[n] = set()
        if r.get("device"):
            where[n].add(r["device"])
        meas.setdefault(n, {})[r.get("device") or "?"] = dict(r, src=prov.get("label", "backfill"), ref=prov.get("ref", ""),
                                                             mode=prov.get("mode", "unrecorded"), at=_stamp(prov.get("source_utc")),
                                                             url=prov.get("source", ""))
    # title_verdict.py's verdicts supersede the backfill for the same title and device
    latest = {}
    for p in _glob(os.path.join(F.D, "results"), "verdict.json"):
        v = _jload(p)
        if not isinstance(v, dict):
            continue
        n, d = v.get("name") or v.get("title") or "?", v.get("device") or "?"
        k = (v.get("judged_utc") or "", v.get("request_id") or "")
        if (n, d) not in latest or k > latest[(n, d)][0]:
            latest[(n, d)] = (k, v, p)
    for (n, d), (_, v, p) in latest.items():
        if n not in where:
            titles.append(n)
            where[n] = set()
        where[n].add(d)
        ok = bool(v.get("pass")) and str(v.get("rating_candidate") or "").startswith("Playable")
        reached = v.get("reached")
        meas.setdefault(n, {})[d] = {
            "device": d, "reached": "yes" if reached or v.get("fps_median") is not None else ("no" if reached is False else "yes"),
            "fps_median": v.get("fps_median") or v.get("median_fps"), "share_30": v.get("share_30") or v.get("share_at_30"),
            "soak": v.get("soak") or "", "verdict": "Playable" if ok else ("fails: " + str(v.get("fail") or v.get("first_fail") or v.get("rating_candidate") or "not Playable")),
            "issue": str(v.get("issue") or ""), "src": "title_verdict.py", "ref": str(v.get("ref") or "")[:10],
            "mode": v.get("perf_mode") or v.get("mode") or "unrecorded", "at": _stamp(v.get("judged_utc")),
            "url": ""}
    rows = []
    for n in titles:
        m = meas.get(n, {})
        rows.append({"title": n, "devices": sorted(where[n]) or [], "measured": [m[d] for d in sorted(m)]})
    def tested(r):
        return any(x.get("reached") in ("yes", "no", "late") for x in r["measured"])
    def reached(r):
        return any(x.get("reached") == "yes" for x in r["measured"])
    def playable(r):
        t = [x for x in r["measured"] if x.get("reached") in ("yes", "no", "late")]
        return bool(t) and all(x.get("verdict") == "Playable" for x in t)
    counts = {"on_handhelds": len(rows), "tested": sum(map(tested, rows)), "reached": sum(map(reached, rows)),
              "playable": sum(map(playable, rows))}
    def key(r):
        best = max([x.get("fps_median") or 0 for x in r["measured"]] or [0])
        return (not tested(r), not reached(r), -best, r["title"].lower())
    rows.sort(key=key)
    return {"rows": rows, "counts": counts, "sources": srcs + ([os.path.basename(bf_path)] if bf else []),
            "backfill": prov, "list_rule": conf.get("test_list", "")}


def _fold_stuck(F, prs, now):
    """Fold-ready PRs not folded within the hour, and why. The 2026-09-26 jam: a
    CONFLICTING head gets no CI run from GitHub, fold.sh waits for CI forever,
    and every surface said "waiting" for 2.5 h. `gh pr list` reports mergeable
    UNKNOWN, so each PR is asked on its own."""
    out = []
    if not F.have_gh:
        return out
    for br, p in prs.items():
        if p.get("state") != "OPEN" or p.get("isDraft") or "fold-ready" not in {l["name"] for l in p.get("labels", [])}:
            continue
        n = p["number"]
        la = F.run("gh", "api", "repos/%s/issues/%d/events?per_page=100" % (F.GH_REPO, n), "--paginate", "--jq",
                   '.[] | select(.event == "labeled" and .label.name == "fold-ready") | .created_at').split()
        t = _stamp(la[-1]) if la else None
        if t is None or now - t < 3600:
            continue
        v = F.gh_json("pr", "view", str(n), "--repo", F.GH_REPO, "--json", "mergeable,statusCheckRollup", default={}) or {}
        roll = v.get("statusCheckRollup") or []
        bad = sorted({c.get("name") or c.get("context") or "?" for c in roll
                      if (c.get("conclusion") or c.get("state") or "").upper() in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE")})
        pend = [c for c in roll if (c.get("status") or "").upper() in ("QUEUED", "IN_PROGRESS", "PENDING", "WAITING") or (c.get("state") or "").upper() == "PENDING"]
        mg = (v.get("mergeable") or "UNKNOWN").upper()
        if mg == "CONFLICTING":
            why = "CONFLICTING with master; GitHub runs no CI on it, so the fold waits forever. Merge master into it"
        elif not v:
            why = "its mergeability and CI could not be read"
        elif not roll:
            why = "CI never ran on its head"
        elif bad:
            why = "CI red (%s)" % ", ".join(bad)[:80]
        elif pend:
            why = "CI still running"
        elif mg == "UNKNOWN":
            why = "GitHub has not computed mergeability yet"
        else:
            why = "green and mergeable, yet unfolded; read the fold job's log"
        out.append({"number": n, "branch": br, "age": _dur(now - t), "reason": why})
    return out


def _md(s):
    return " ".join(scrub(s).split()).replace("|", "\\|")


def lanes_main(E, out_json, idle_path):
    """status.sh's lane block: the first screen's facts to lanes.json, the lane
    sections of STATUS.md to stdout, the stranded lanes to `idle-lanes` (the
    #107 body header reads it)."""
    g = gather(E)
    F = Facts(E)
    now = g["now"]
    prs = {}
    pl = F.gh_json("pr", "list", "--repo", F.GH_REPO, "--state", "open", "--label", "fold-ready",
                   "--json", "number,state,isDraft,headRefName,labels", default=[]) if F.have_gh else []
    for p in pl or []:
        prs[p.get("headRefName", "")] = p
    fold_stuck = _fold_stuck(F, prs, now)
    queued_old = sorted([{"id": r["id"], "requester": r["requester"], "age": _dur(now - r["queued"]), "device": r["device"], "_a": now - r["queued"]}
                         for r in g["reqs"] if r["state"] == "queue" and not r["file"].startswith("z-") and r["queued"] and now - r["queued"] > 3600],
                        key=lambda x: -x["_a"])
    for q in queued_old:
        q.pop("_a")
    first = {k: v for k, v in g.items() if k not in ("reqs", "conf")}
    first["conf"] = {k: v for k, v in g["conf"].items() if isinstance(v, (str, int, float, list))}
    doc = {"idle": g["stranded"], "blocked": [], "fold_stuck": fold_stuck, "queued_old": queued_old,
           "devices": [{"name": d["name"], "state": d["state"], "detail": _device_words(d, now)} for d in g["devices"]],
           "prs_ok": g["prs_ok"], "terr_ok": g["board_ok"], "first": first}
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    os.replace(tmp, out_json)
    try:
        with open(idle_path, "w") as fh:
            fh.write(", ".join(g["stranded"]) + ("\n" if g["stranded"] else ""))
    except OSError:
        pass

    # ---- the Markdown: what the #107 comment and --print show
    tz = _lt(now, "full")[-3:]
    if not g["board_ok"]:
        print("(territory.toml on origin/board could not be read; only running units and the two sessions are listed)")
        print()
    if g["stranded"]:
        print("> [!WARNING]")
        print("> **Stranded:** %s. No session, nothing on a device, not parked: nothing will wake %s." % (
            ", ".join("lane." + s for s in g["stranded"]), "it" if len(g["stranded"]) == 1 else "them"))
        print()
    print("| lane | kind | issue | state | waiting on | since (%s) | latest result |" % tz)
    print("|---|---|---|---|---|---|---|")
    for r in g["lanes"]:
        print("| %s |" % " | ".join(_md(x) for x in (
            r["lane"], r["kind"], r["issue"], r["state"] + ((" (" + r["step"] + ")") if r.get("step") else ""),
            r.get("waiting") or "-", _lt(r["since"], "md") if r.get("since") else "-", r.get("result") or "-")))
    if g["parked"]:
        print()
        print("**Parked until %s ships** (gate: %s): %s." % (g["release_name"], g["parked"][0]["gate"], "; ".join(
            "lane.%s (%s)" % (r["lane"], r["issue"]) for r in g["parked"])))
    print()
    print("### Finished today")
    print()
    if g["finished"]:
        print("| lane | issue | PR | merged (%s) | result |" % tz)
        print("|---|---|---|---|---|")
        for r in g["finished"]:
            print("| %s |" % " | ".join(_md(x) for x in (r["lane"], r["issue"], r["pr"] or "-", _lt(r["merged"], "md"), r.get("result") or "-")))
    else:
        print("nothing merged or retired in the last 24 h.")
    print()
    print("### Automation (timer jobs; not lanes)")
    print()
    print("| job | last run | next run | last outcome |")
    print("|---|---|---|---|")
    for a in g["automation"]:
        print("| %s |" % " | ".join(_md(x) for x in (a["job"], _lt(a["last"], "md") if a["last"] else "not recorded",
                                                    _lt(a["next"], "md") if a["next"] else ("running now" if a["timer"] else "no timer"),
                                                    a["outcome"] or "-")))
    return 0


def _device_words(d, now):
    if d["state"] == "running":
        return "%s for %s since %s" % (d["purpose"], d["who"], _lt(d["since"]))
    if d["state"] == "in use":
        return "in use by %s: %s (since %s, until %s)" % (d["who"], d["purpose"], _lt(d["since"]),
                                                         _lt(d["until"]) if d.get("until") else "no end time stated")
    return "idle" + ((" since %s" % _lt(d["since"])) if d.get("since") else "")


def build(facts_path, lanes_path, md_path):
    """Merge status.sh's facts.tsv, the lane block's lanes.json and STATUS.md."""
    f = {"devices": [], "attention": [], "blockers": [], "timers": []}
    kv = {}
    r05 = {"facts": {}, "gate": [], "issues": [], "issues_known": False}
    try:
        for line in open(facts_path, encoding="utf-8", errors="replace"):
            p = line.rstrip("\n").split("\t")
            if not p or not p[0]:
                continue
            if p[0] == "attn" and len(p) >= 3:
                f["attention"].append({"kind": p[1], "text": p[2]})
            elif p[0] == "blocker" and len(p) >= 3:
                f["blockers"].append({"number": p[1], "title": p[2]})
            elif p[0] == "r05" and len(p) >= 3:
                r05["facts"][p[1]] = p[2]
            elif p[0] == "r05gate" and len(p) >= 7:
                r05["gate"].append(dict(zip(("device", "median", "n", "id", "ref", "at", "unread"), p[1:8])))
            elif p[0] == "r05issue" and len(p) >= 4:
                r05["issues"].append({"number": p[1], "lane": p[2], "title": p[3]})
            elif p[0] == "r05issues_known":
                r05["issues_known"] = True
            elif len(p) >= 2:
                kv[p[0]] = p[1]
    except OSError:
        f["attention"].append({"kind": "page", "text": "status.sh wrote no facts file; the strip below is empty"})
    lanes = {}
    try:
        lanes = json.load(open(lanes_path, encoding="utf-8"))
    except Exception:
        f["attention"].append({"kind": "page", "text": "the lane table could not be computed this tick"})
    md = ""
    try:
        md = open(md_path, encoding="utf-8", errors="replace").read()
    except OSError:
        pass

    def num(k, d=0):
        try:
            return int(kv.get(k, d))
        except ValueError:
            return d

    now = num("now") or int(datetime.datetime.now().timestamp())
    first = lanes.get("first") or {}
    try:
        gmin = float(kv.get("release_gate_min") or (first.get("conf") or {}).get("gate_min") or 25)
    except ValueError:
        gmin = 25.0
    gate = _gate(r05["gate"], kv, gmin, now)

    # WHAT NEEDS A PERSON: only what no automated job will handle, each with who
    # acts. The lane block's owner decisions and alarms come first; then this
    # tick's machine alarms from status.sh (CI red on master, a failed timer, a
    # lapse of this page) and a fold-ready PR the fold cannot land. An owned or
    # in-flight issue, a file wait, parked work, and a queue that is long only
    # because the devices are busy are never listed.
    who = {"ci": "host", "timer": "host", "page": "host"}
    person = list(first.get("person", []))
    for s in lanes.get("fold_stuck", []):
        person.append({"kind": "fold", "who": "host", "action": "PR #%s has been fold-ready for %s and is not folded: %s" % (
            s.get("number"), s.get("age", "?"), s.get("reason", "?")), "src": "fold-ready label events, PR checks", "at": None})
    for a in f["attention"]:
        person.append({"kind": a["kind"], "who": who.get(a["kind"], "host"), "action": a["text"], "src": "status.sh, this tick", "at": now})
    if gate.get("fails_on_candidate"):
        person.append({"kind": "release gate", "who": "owner", "action": "the %s gate fails on the candidate %s: %s" % (
            kv.get("release_name", "0.5"), gate["candidate"], gate["summary"]), "src": "Ghoulies soaks", "at": now})
    # a decision first, then the alarms in the order above
    person.sort(key=lambda p: 0 if p.get("kind") == "decision" else 1)

    devices = lanes.get("devices", [])
    if kv.get("console"):
        m = re.match(r"(.*?)\s*\((read .*)\)\s*$", kv["console"])     # "ON, 66.2 W (read 41s ago)"
        devices = devices + [{"name": "console", "state": m.group(1) if m else kv["console"],
                              "detail": ("plug meter, " + m.group(2)) if m else "plug meter"}]
    return {
        "schema": 2,
        "now": now,
        "generated": _local(now),
        "tz": (_local(now).split(" ")[-1] if _local(now) else "UTC"),
        "floor_secs": num("floor_secs", 1800),
        "heartbeat_secs": num("heartbeat_secs", 1800),
        "next_due": kv.get("next_due", ""),
        "strip": {
            "devices": devices,
            "queue": num("queue"), "queue_idle": num("queue_idle"), "arms_running": num("arms_running"),
            "lanes_running": num("lanes_running"), "lane_cap": num("lane_cap", 2),
            "last_fold": num("last_fold"), "last_fold_subject": kv.get("last_fold_subject", ""),
            "window": kv.get("window", ""),
        },
        "attention": person,
        "first": first,
        "release": {
            "name": kv.get("release_name", "") or first.get("release_name", "0.5"),
            "gate": kv.get("release_gate", "") or (first.get("conf") or {}).get("gate", ""),
            "gate_result": gate,
            "candidate": kv.get("release_candidate", ""),
            "blockers": f["blockers"],
            "blockers_known": kv.get("blockers_known", "0") == "1",
            "blocker_label": kv.get("blocker_label", "release-blocker"),
            "panel": dict(r05, gate_min=kv.get("release_gate_min", "25")),
        },
        "details_md": md,
    }


def _gate(rows, kv, gmin, now):
    """The Ghoulies gate from status.sh's r05gate rows, stated plainly."""
    cand = kv.get("release_candidate", "") or "none cut yet"
    cand_sha = kv.get("release_candidate_sha", "")
    out = {"min": gmin, "candidate": cand, "devices": [], "met": None, "fails_on_candidate": False}
    if not rows:
        out["summary"] = "not measured this tick (no soak results were read)"
        return out
    met = True
    for g in rows:
        try:
            med = float(g.get("median"))
        except (TypeError, ValueError):
            med = None
        un = int(g.get("unread") or 0) if str(g.get("unread") or "0").isdigit() else 0
        at = int(g.get("at") or 0) if str(g.get("at") or "").isdigit() else 0
        ref = g.get("ref") or ""
        on_cand = bool(cand_sha and ref and cand_sha.startswith(ref))
        d = {"device": g.get("device", "?"), "median": med, "n": g.get("n"), "id": g.get("id"), "ref": ref,
             "at": at, "unread": un, "on_candidate": on_cand}
        out["devices"].append(d)
        if med is None or med < gmin:
            met = False
    out["met"] = met
    on = [d for d in out["devices"] if d["on_candidate"]]
    if cand == "none cut yet":
        out["verdict"] = "no candidate is cut yet, so no soak is on the candidate's APK; on the newest soaks it is %s" % ("met" if met else "NOT met")
    elif len(on) == len(out["devices"]):
        out["verdict"] = "%s on the candidate %s" % ("MET" if met else "FAILS", cand)
        out["fails_on_candidate"] = not met
    else:
        out["verdict"] = "the newest soaks are not on the candidate %s's ref; on them it is %s" % (cand, "met" if met else "NOT met")
    out["summary"] = "; ".join(
        ("%s %s gfps (n=%s, %s, ref %s, %s ago)" % (d["device"], ("%g" % d["median"]) if d["median"] is not None else "no reading",
                                                    d["n"], d["id"], d["ref"] or "?", _dur(now - d["at"]) if d["at"] else "?"))
        for d in out["devices"])
    return out


# ------------------------------------------------------------------ rendering

CSS = """
:root{--bg:#fff;--fg:#1b1f24;--mut:#59636e;--card:#f6f8fa;--line:#d1d9e0;--red:#cf222e;--redbg:#ffebe9;--grn:#1a7f37;--grnbg:#dafbe1;--amb:#9a6700;--ambbg:#fff8c5;--link:#0969da}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--mut:#9198a1;--card:#151b23;--line:#3d444d;--red:#ff7b72;--redbg:#3c1618;--grn:#3fb950;--grnbg:#12261e;--amb:#d29922;--ambbg:#2e2410;--link:#4493f8}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:10px 12px 40px}
a{color:var(--link)}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin-bottom:6px}
header h1{font-size:18px;margin:0}
#age{color:var(--mut);font-size:13px}
#age.stale{color:var(--red);font-weight:600}
.glance{border:1px solid var(--line);background:var(--card);border-radius:8px;padding:6px 10px;margin-bottom:10px}
.glance ol{margin:0;padding-left:20px} .glance li{margin:2px 0}
section.q{margin:0 0 14px}
section.q>h2{font-size:16px;margin:12px 0 6px;padding-bottom:2px;border-bottom:2px solid var(--line)}
section.q h3{font-size:14px;margin:10px 0 4px}
.src{color:var(--mut);font-size:12px}
.big{font-size:15px;font-weight:600}
.bad{color:var(--red);font-weight:600} .good{color:var(--grn);font-weight:600} .warnc{color:var(--amb);font-weight:600}
.att{border:2px solid var(--red);background:var(--redbg);border-radius:8px;padding:6px 10px}
.att ol{margin:0;padding-left:20px} .att li{margin:4px 0}
.who{font-size:12px;font-weight:700;text-transform:uppercase;color:var(--red);margin-right:4px}
.ok{border:1px solid var(--grn);background:var(--grnbg);color:var(--grn);border-radius:8px;padding:6px 10px;font-weight:600}
.dev{border:1px solid var(--line);background:var(--card);border-radius:8px;padding:5px 8px;margin:4px 0}
.dev b{margin-right:4px}
.fold{border-top:1px dashed var(--line);margin:18px 0 6px;color:var(--mut);font-size:12px;text-align:center}
section.md h3{font-size:16px;margin:18px 0 6px;border-bottom:1px solid var(--line);padding-bottom:2px}
section.md h4{font-size:14px;margin:12px 0 4px}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;font-size:13px;min-width:100%}
th,td{border:1px solid var(--line);padding:3px 6px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
th{background:var(--card)}
section.md td{min-width:4.5em} section.md td:last-child{min-width:18em}
/* phone first: a first-screen table becomes one card per row, each cell labelled */
@media (max-width:640px){
 table.cards,table.cards tbody,table.cards tr,table.cards td{display:block;width:100%}
 table.cards tr:first-child{display:none}
 table.cards tr{border:1px solid var(--line);border-radius:8px;margin:0 0 6px;padding:3px 6px;background:var(--bg)}
 table.cards td{border:0;padding:1px 0}
 table.cards td[data-l]:before{content:attr(data-l) ": ";color:var(--mut);font-size:12px}
 table.cards td.h{font-weight:600}
 table.lanes td{display:inline;padding:0}
 table.lanes td:not(:last-child):not(:first-child):after{content:" \00b7 ";color:var(--mut)}
 table.lanes td:first-child{display:block}
 table.lanes td:last-child{display:block;margin-top:2px;color:var(--mut)}
 table.lanes td[data-l]:before{content:none}
 table.lanes td.lbl:before{content:attr(data-l) " "}
}
details.note{display:inline} details.note summary{display:inline;cursor:pointer;color:var(--mut);font-size:12px}
details.note[open]{display:block;font-size:12px;color:var(--mut)}
pre{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 8px;overflow-x:auto;font-size:12px;line-height:1.3}
code{font:12px/1.3 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--card);padding:0 3px;border-radius:3px;overflow-wrap:anywhere}
pre code{background:none;padding:0}
blockquote{margin:6px 0;padding:4px 10px;border-left:4px solid var(--amb);background:var(--ambbg)}
blockquote.warn{border-color:var(--red);background:var(--redbg)}
section.md ul,section.q ul{padding-left:20px;margin:4px 0} section.md li,section.q li{margin:2px 0;overflow-wrap:anywhere}
section.md p,section.q p{margin:6px 0;overflow-wrap:anywhere}
footer{color:var(--mut);font-size:12px;margin-top:20px}
"""

# "updated N min ago" is the one line that must move between publishes: the
# page is republished on a content change or at the heartbeat, not every tick.
# Inline and tiny; with scripts off the absolute time above still reads.
JS = """
(function(){var e=document.getElementById('age');if(!e)return;var t=+e.dataset.t,st=+e.dataset.stale;
function f(){var s=Math.max(0,Math.floor(Date.now()/1000-t)),m=Math.floor(s/60),x;
x=m<1?'just now':m<120?m+' min ago':Math.floor(m/60)+'h '+(m%60)+'m ago';
e.textContent='updated '+x+' ('+e.dataset.at+')'+(s>st?' -- STALE: the host has stopped publishing':'');
e.className=s>st?'stale':''}f();setInterval(f,30000)})();
"""


def _ago(now, t):
    if not t:
        return "not recorded"
    s = max(0, now - t)
    if s < 120:
        return "%ds ago" % s
    if s < 7200:
        return "%dm ago" % (s // 60)
    return "%dh %dm ago" % (s // 3600, (s % 3600) // 60)


def tile(k, v, d="", cls=""):
    return '<div class="tile %s"><div class="k">%s</div><div class="v" title="%s">%s</div>%s</div>' % (
        cls, esc(k), esc(v), esc(v), ('<div class="d" title="%s">%s</div>' % (esc(d), esc(d))) if d else "")


def panel_lines(p, name, now):
    """The Ghoulies gate and the 0.5 issues as plain lines (`status_html.py panel`)."""
    lines = ["Release %s: the Ghoulies gate" % name]
    try:
        gmin = float(p.get("gate_min") or 25)
    except ValueError:
        gmin = 25.0
    gate = p.get("gate", [])
    if not gate:
        lines.append("Ghoulies gate (median gfps 90-240 s >= %g, both handhelds): not gathered this tick" % gmin)
    else:
        bits, verdict = [], True
        for g in gate:
            dev = g.get("device", "?")
            un = int(g.get("unread") or 0) if str(g.get("unread") or "0").isdigit() else 0
            skipped = ("; %d newer soak%s logged no gfps in 90-240 s" % (un, "" if un == 1 else "s")) if un else ""
            try:
                med = float(g.get("median"))
            except (TypeError, ValueError):
                med = None
            if not g.get("id") or med is None:
                bits.append("%s no finished Ghoulies soak with gfps in 90-240 s%s" % (dev, skipped))
                verdict = False
                continue
            at = int(g.get("at") or 0)
            bits.append("%s %g (n=%s; %s, ref %s, %s%s)" % (dev, med, g.get("n"), g.get("id"), g.get("ref") or "?",
                                                           _ago(now, at) if now else _local(at), skipped))
            verdict = verdict and med >= gmin
        lines.append("Ghoulies gate (median gfps 90-240 s >= %g, both handhelds): %s -- %s" % (
            gmin, "met on these soaks (check the ref is the candidate's)" if verdict else "NOT MET", "; ".join(bits)))
    iss = p.get("issues", [])
    if not p.get("issues_known"):
        lines.append("%s issues: could not be read" % name)
    elif not iss:
        lines.append("%s issues: none open" % name)
    else:
        lines.append("%s issues (%d open): %s" % (name, len(iss), "; ".join(
            "#%s %s -- %s" % (i.get("number"), i.get("lane") or "no lane", (i.get("title") or "")[:50]) for i in iss)))
    return lines


def _tbl(head, rows, labels=None, cls="cards", lbl=()):
    """A first-screen table: cards on a phone, a table on a desk. Cells are HTML already.
    `lbl` names the columns whose label a compact phone row still prints."""
    labels = labels or head
    out = ['<div class="tw"><table class="%s"><tr>%s</tr>' % (cls, "".join("<th>%s</th>" % esc(h) for h in head))]
    for r in rows:
        out.append("<tr>%s</tr>" % "".join(
            '<td%s data-l="%s">%s</td>' % (' class="h"' if i == 0 else (' class="lbl"' if head[i] in lbl else ""), esc(labels[i]), c)
            for i, c in enumerate(r)))
    out.append("</table></div>")
    return "".join(out)


def _when(now, t, fmt="md"):
    if not t:
        return "not recorded"
    return "%s (%s)" % (_lt(t, fmt), _ago(now, t))


def _q1(j, now):
    fs = j.get("first") or {}
    conf = fs.get("conf") or {}
    r = j.get("release", {})
    name = r.get("name") or "0.5"
    t = fs.get("titles") or {}
    c = t.get("counts") or {}
    out = ['<section class="q" id="q1"><h2>1. How close is %s?</h2>' % esc(name)]
    if conf.get("target"):
        out.append('<p class="big">%s</p><p class="src">Target: %s. Read from <code>%s</code>.</p>' % (
            esc(conf["target"]), esc(conf.get("decided") or "source not stated"), esc(os.path.basename(fs.get("conf_path") or "release-0.5.toml"))))
    else:
        out.append('<p class="bad">No target is stated: <code>%s</code> could not be read.</p>' % esc(fs.get("conf_path") or "release-0.5.toml"))
    if conf.get("numeric_target"):
        out.append("<p><b>Numeric target:</b> %s <span class=\"src\">(%s)</span></p>" % (esc(conf["numeric_target"]), esc(conf.get("numeric_decided") or "")))
    else:
        out.append('<p><b>Numeric target:</b> not set yet; the owner has the question (see 3).</p>')
    # the counts, computed from the table below
    if t.get("rows") is not None:
        out.append('<p class="big">%d titles on the handhelds; %d tested; %d reached gameplay; <span class="%s">%d Playable</span>.</p>' % (
            c.get("on_handhelds", 0), c.get("tested", 0), c.get("reached", 0), "good" if c.get("playable") else "bad", c.get("playable", 0)))
        out.append('<p class="src">Counted from the table below. The list: %s. Sources: %s.</p>' % (
            esc(t.get("list_rule") or "every title on either handheld"), esc(", ".join(t.get("sources") or []) or "none")))
    # the gate
    g = r.get("gate_result") or {}
    gl = ['<b>Gate:</b> %s.' % esc(r.get("gate") or conf.get("gate") or "(not stated)")]
    if g.get("devices"):
        gl.append('<span class="%s">%s.</span>' % ("good" if g.get("met") else "bad", esc(g.get("verdict", ""))))
        gl.append("<br>" + "<br>".join(
            "%s: <b>%s</b> gfps median (n=%s), soak <code>%s</code>, ref <code>%s</code>, %s%s" % (
                esc(d["device"]), esc("%g" % d["median"]) if d["median"] is not None else "no reading", esc(d["n"]), esc(d["id"]),
                esc(d["ref"] or "?"), esc(_when(now, d["at"])),
                (", %d newer soak%s logged no gfps" % (d["unread"], "" if d["unread"] == 1 else "s")) if d["unread"] else "")
            for d in g["devices"]))
    else:
        gl.append(esc(g.get("summary") or "not measured this tick"))
    gl.append('<br><span class="src">Candidate: %s. Measured from each handheld\'s newest Ghoulies soak with perf lines, 90-240 s after the first.</span>' % esc(g.get("candidate") or r.get("candidate") or "none cut yet"))
    out.append("<p>%s</p>" % " ".join(gl))
    # the title table
    rows = t.get("rows") or []
    tested = [x for x in rows if any(m.get("reached") in ("yes", "no", "late") for m in x["measured"])]
    listed = [x for x in rows if x not in tested]
    if rows:
        out.append("<h3>The %s titles (%d)</h3>" % (esc(name), len(rows)))
        body, legend = [], []
        for x in tested + [x for x in listed if x["measured"]]:
            for m in x["measured"] or [{}]:
                reached = {"yes": "yes", "no": "no: " + (m.get("blocker") or "blocker not recorded"),
                           "late": "late: " + (m.get("blocker") or ""), "not run": "not run: " + (m.get("blocker") or "")}.get(m.get("reached"), "not run")
                fps = ("%g" % m["fps_median"]) if m.get("fps_median") is not None else "-"
                s30 = ("%d%%" % round(100 * m["share_30"])) if m.get("share_30") is not None else "-"
                iss = ("#" + m["issue"]) if m.get("issue") else "-"
                meas_t = "%s, %s, ref %s, mode %s" % (m.get("src", ""), _lt(m.get("at"), "md")[:5] if m.get("at") else "?",
                                                      m.get("ref") or "?", m.get("mode") or "unrecorded")
                if meas_t not in legend:
                    legend.append(meas_t)
                meas = "[%d]" % (legend.index(meas_t) + 1)
                if m.get("url"):
                    meas = '<a href="%s">%s</a>' % (esc(m["url"]), meas)
                body.append([esc(x["title"]), esc(m.get("device") or "-"), esc(reached), esc(fps), esc(s30),
                             esc(m.get("soak") or "not run"), esc(m.get("verdict") or "-"), esc(iss), meas])
        out.append(_tbl(["title", "device", "reached gameplay", "median fps (1x)", "play at 30+", "20-min soak", "verdict", "issue", "measured"],
                        body, cls="titles"))
        out.append('<p class="src">%s</p>' % "<br>".join("[%d] %s" % (i + 1, esc(l)) for i, l in enumerate(legend)))
        nr = {}
        for x in listed:
            if x["measured"]:
                continue
            nr.setdefault(", ".join(x["devices"]) or "device not recorded", []).append(x["title"])
        if nr:
            out.append("<p><b>Not run yet (%d):</b> %s</p>" % (sum(map(len, nr.values())), " ".join(
                "<br><i>%s</i> (%d): %s." % (esc(k), len(v), esc("; ".join(v))) for k, v in sorted(nr.items()))))
        bp = t.get("backfill") or {}
        if bp:
            out.append('<p class="src">Hand-reviewed rows: %s (<a href="%s">%s, %s</a>); the devices\' performance mode was not recorded then.</p>' % (
                esc(bp.get("what", "")), esc(bp.get("source", "")), esc(bp.get("source_author", "")), esc(_lt(_stamp(bp.get("source_utc")), "full"))))
    # the levers
    lv = fs.get("levers") or []
    if lv:
        out.append("<h3>Performance levers</h3><ul>")
        for x in lv:
            out.append("<li><b>#%s</b> %s. <i>Owner:</i> %s%s. <i>Effect:</i> %s <span class=\"src\">(%s%s)</span></li>" % (
                esc(x["issue"]), esc(x["words"]), esc(x["lane"]), (", PR " + esc(x["pr"])) if x.get("pr") else "",
                esc(x["effect"]), esc(x["src"]), ("; expected " + esc(x["expected"])) if x.get("expected") else ""))
        out.append("</ul>")
    iss = fs.get("r05_issues")
    if iss is not None:
        owned = {i for r_ in fs.get("lanes", []) + fs.get("parked", []) + fs.get("finished", []) for i in r_.get("issues", [])}
        free = [i for i in iss if str(i["number"]) not in owned]
        out.append('<p class="src">%d open %s issues; %s.</p>' % (len(iss), esc(name), "every one has a lane" if not free else
                   "every one has a lane except " + "; ".join("#%s %s" % (i["number"], esc(i["title"])) for i in free)))
    out.append("</section>")
    return "\n".join(out)


def _q2(j, now):
    fs = j.get("first") or {}
    out = ['<section class="q" id="q2"><h2>2. What is happening right now?</h2>']
    rows = fs.get("lanes") or []
    counts = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    out.append("<p>%s.</p>" % esc("; ".join("%d %s" % (v, k) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])) or "no lanes"))
    body = []
    for r in rows:
        st = r["state"] + ((" (%s)" % r["step"]) if r.get("step") else "")
        cls = "bad" if r["state"] == "stranded" else "good" if r["state"] == "running" else ""
        res = esc(r.get("result") or "-")
        if r.get("result_url"):
            res = '<a href="%s">%s</a>' % (esc(r["result_url"]), res)
        elif r.get("pr"):
            res += ' <span class="src">(%s)</span>' % esc("PR " + r["pr"])
        note = ('<details class="note"><summary>board note</summary>%s</details>' % esc(r["note"])) if r.get("note") else ""
        body.append(["<b>%s</b> %s" % (esc("lane." + r["lane"]), note), esc(r["kind"]), esc(r["issue"]),
                     '<span class="%s">%s</span>' % (cls, esc(st)) + ((' <span class="src">%s</span>' % esc(r["detail"])) if r.get("detail") else ""),
                     esc(r.get("waiting") or "-"), esc(_lt(r["since"], "md")) if r.get("since") else "-", res])
    out.append(_tbl(["lane", "kind", "issue", "state", "waiting on", "since", "latest result"], body,
                    cls="cards lanes", lbl=("waiting on", "since")))
    pk = fs.get("parked") or []
    if pk:
        out.append("<p><b>Parked until %s ships</b> (gate: %s): %s.</p>" % (esc(fs.get("release_name", "0.5")), esc(pk[0].get("gate", "")), esc("; ".join(
            "lane.%s, %s" % (r["lane"], r["issue"]) for r in pk))))
    fin = fs.get("finished") or []
    out.append("<h3>Finished today (%d)</h3>" % len(fin))
    if fin:
        def frow(r):
            return [esc("lane." + r["lane"]), esc(r["issue"]), esc(r.get("pr") or "-"), esc(_lt(r.get("merged"))), esc(r.get("result") or "-")]
        head = ["lane", "issue", "PR", "merged", "result"]
        out.append(_tbl(head, [frow(r) for r in fin[:6]], cls="cards lanes", lbl=("merged",)))
        if len(fin) > 6:        # every row is on the page; the older ones fold so 3 and 4 stay near the top
            out.append("<details><summary>%d more finished earlier today</summary>%s</details>" % (
                len(fin) - 6, _tbl(head, [frow(r) for r in fin[6:]], cls="cards lanes", lbl=("merged",))))
    else:
        out.append("<p>nothing merged or retired today.</p>")
    out.append('<p class="src">States from units, dispatch/queue, running and hold, PR state and labels, %s, logs/lane, and for the two sessions their GitHub comments. The board\'s free-text blocker is detail only. Timer jobs are in the Automation box (4).</p>' % esc(fs.get("board_src", "the board")))
    out.append("</section>")
    return "\n".join(out)


def _q3(j, now):
    person = j.get("attention") or []
    out = ['<section class="q" id="q3"><h2>3. What needs a person?</h2>']
    if not person:
        out.append('<div class="ok">Nothing needs a person.</div>')
    else:
        out.append('<div class="att"><ol>')
        for p in person:
            out.append('<li><span class="who">%s</span>%s%s <span class="src">(%s%s)</span></li>' % (
                esc(p.get("who", "host")), esc(p.get("action", "")),
                (" " + esc(p["detail"][:1].upper() + p["detail"][1:])) if p.get("detail") else "", esc(p.get("src", "")),
                (", " + _lt(p["at"], "md")) if p.get("at") and p.get("kind") != "decision" else ""))
        out.append("</ol></div>")
    out.append('<p class="src">Listed: the owner\'s open decisions (host-tools/escalations.md, issues labelled decision-needed), then the alarms no job handles: a stranded lane, a device idle with runnable work, a hold past its end, a run past twice its expected time, a failing gate on the candidate, CI red on master, a failed timer. Never listed: owned or in-flight work, a file wait, parked work, a queue that is long because both devices are busy.</p>')
    out.append("</section>")
    return "\n".join(out)


def _q4(j, now):
    fs = j.get("first") or {}
    out = ['<section class="q" id="q4"><h2>4. Are the machines healthy?</h2>']
    for d in fs.get("devices") or []:
        label = {"thor": "Thor", "nova": "Nova"}.get(d["name"], d["name"])
        if d["state"] == "running":
            txt = '<span class="good">running</span> %s, for %s, since %s' % (esc(d["purpose"]), esc(d["who"]), esc(_when(now, d["since"], "hm")))
        elif d["state"] == "in use":
            end = d.get("until")
            late = end and now > end + 300
            txt = '<span class="warnc">in use by %s</span>: %s. Since %s, until %s%s' % (
                esc(d["who"]), esc(d["purpose"]), esc(_lt(d["since"])) if d.get("since") else "?",
                ('<span class="bad">%s, %s ago</span>' % (esc(_lt(end)), esc(_dur(now - end)))) if late else (esc(_lt(end)) if end else "no end time stated"),
                (' <span class="src">(%s)</span>' % esc(d["until_src"])) if end and d.get("until_src") != "stated" else "")
        else:
            txt = "idle" + (" since %s" % esc(_when(now, d["since"], "hm")) if d.get("since") else "")
        out.append('<div class="dev"><b>%s</b>%s <span class="src">(%s)</span></div>' % (esc(label), txt, esc(d.get("src", ""))))
    q = fs.get("queue") or {}
    if q:
        out.append("<p><b>Queue:</b> %s. %d queued, %d of them %s work%s; the %d-run idle tier (the z- sweeps) waits behind them by design. Estimated drain: %s.</p>" % (
            esc(q.get("constraint", "")), q.get("queued", 0), q.get("queued_05", 0), esc(fs.get("release_name", "0.5")),
            ("; the oldest %s run has waited %s" % (esc(fs.get("release_name", "0.5")), esc(_dur(q["oldest_05_age"])))) if q.get("oldest_05_age") else "",
            q.get("idle_tier", 0), esc(_dur(q.get("drain_secs"))) if q.get("drain_secs") else "nothing to drain"))
        out.append('<p class="src">%s.</p>' % esc(q.get("src", "")))
    con = fs.get("console") or {}
    if con:
        pu = con.get("push") or {}
        out.append("<p><b>Console:</b> %s. Title push: %s.</p>" % (
            esc((con.get("meter") or "meter not available").replace("console meter: ", "plug meter ")),
            esc(pu.get("progress") or "no push recorded") + (" (unit running)" if pu.get("active") else "")))
    au = fs.get("automation") or []
    if au:
        out.append("<h3>Automation</h3>")
        out.append(_tbl(["job", "last run", "next run", "last outcome"], [
            [esc(a["job"]), esc(_lt(a["last"], "md")) if a.get("last") else "not recorded",
             esc(_lt(a["next"], "md")) if a.get("next") else ("running now" if a.get("timer") else "no timer"),
             esc(a.get("outcome") or "-")] for a in au]))
    out.append("</section>")
    return "\n".join(out)


def _glance(j, now):
    """One line per question, in order: the first thing on the page."""
    fs = j.get("first") or {}
    c = (fs.get("titles") or {}).get("counts") or {}
    name = (j.get("release") or {}).get("name") or "0.5"
    g = (j.get("release") or {}).get("gate_result") or {}
    rows = fs.get("lanes") or []
    by = {}
    for r in rows:
        by[r["state"]] = by.get(r["state"], 0) + 1
    q = fs.get("queue") or {}
    person = j.get("attention") or []
    dec = sum(1 for p in person if p.get("kind") == "decision")
    devs = "; ".join("%s %s" % (d["name"], "running" if d["state"] == "running" else ("in use by " + d.get("who", "?")) if d["state"] == "in use" else "idle")
                     for d in fs.get("devices") or [])
    lines = [
        '<a href="#q1">%s</a>: %d of %d titles tested, %d reached gameplay, %d Playable; gate %s.' % (
            esc(name), c.get("tested", 0), c.get("on_handhelds", 0), c.get("reached", 0), c.get("playable", 0),
            esc("met on the newest soaks, no candidate yet" if g.get("met") and g.get("candidate") == "none cut yet" else (g.get("verdict") or "not measured"))),
        '<a href="#q2">Now</a>: %d lanes: %s.' % (len(rows), esc(", ".join("%d %s" % (v, k) for k, v in sorted(by.items(), key=lambda kv: -kv[1])))),
        '<a href="#q3">Needs a person</a>: %s.' % (esc("nothing") if not person else esc("%d item%s (%d owner decision%s)" % (
            len(person), "" if len(person) == 1 else "s", dec, "" if dec == 1 else "s"))),
        '<a href="#q4">Machines</a>: %s; %s.' % (esc(devs or "no devices"), esc(q.get("constraint") or "queue not read")),
    ]
    return '<div class="glance"><ol>%s</ol></div>' % "".join("<li>%s</li>" % l for l in lines)


def render(j):
    now = int(j.get("now") or 0)
    stale = int(j.get("heartbeat_secs") or 1800) + int(j.get("floor_secs") or 1800) + 600
    out = ['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           '<meta http-equiv="refresh" content="60">',
           '<meta name="color-scheme" content="light dark">',
           '<title>hakuX harness status</title><style>%s</style></head><body><main>' % CSS]
    out.append('<header><h1>hakuX harness</h1><span id="age" data-t="%d" data-stale="%d" data-at="%s">updated %s</span></header>' % (
        now, stale, esc(j.get("generated", "")), esc(j.get("generated", ""))))
    if (j.get("strip") or {}).get("window"):
        out.append('<p class="warnc">%s</p>' % esc(j["strip"]["window"]))
    out.append(_glance(j, now))
    out.append(_q1(j, now))
    out.append(_q2(j, now))
    out.append(_q3(j, now))
    out.append(_q4(j, now))
    out.append('<div class="fold">details</div>')
    out.append('<section class="md">%s</section>' % md_to_html(_below_fold(j.get("details_md", ""))))
    out.append('<footer>Written by <code>docs/testing/jobs/status.sh</code> on the host every job tick and every %d min; '
               'republished when the content changes (at most every 10 min) and at least every %d min. '
               'Every time here is %s. Next tick due by %s.</footer>' % (
                   int(j.get("floor_secs") or 1800) // 60, int(j.get("heartbeat_secs") or 1800) // 60,
                   esc(j.get("tz", "")), esc(j.get("next_due", "") or "?")))
    out.append("<script>%s</script></main></body></html>" % JS)
    return "\n".join(out) + "\n"


# The sections the first screen already answers are not repeated below the fold.
_ON_FIRST_SCREEN = ("Lanes running", "Lanes: what each one is doing", "Finished today", "Automation")


def _below_fold(md):
    """STATUS.md minus its own title block and the sections shown above the fold."""
    i = md.find("\n### ")
    md = md[i + 1:] if i >= 0 else md
    parts = re.split(r"(?m)^(?=### )", md)
    return "".join(p for p in parts if not any(p.startswith("### " + h) for h in _ON_FIRST_SCREEN))


# ------------------------------------------------------------------ Markdown, the subset status.sh writes

_CODE = re.compile(r"``\s?(.+?)\s?``|`([^`]+)`")


def _inline(s):
    s = scrub(s)
    codes = []

    def keep(m):
        codes.append("<code>%s</code>" % html.escape(m.group(1) if m.group(1) is not None else m.group(2)))
        return "\x00%d\x00" % (len(codes) - 1)
    s = _CODE.sub(keep, s)
    s = s.replace("\\|", "|")
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda m: '<a href="%s">%s</a>' % (m.group(2).replace('"', "%22"), m.group(1)), s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<i>\1</i>", s)
    s = re.sub(r"(?<![\w])_([^_\s][^_]*?)_(?![\w])", r"<i>\1</i>", s)
    s = s.replace(":warning:", "&#9888;")
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)


def _cells(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def md_to_html(md):
    lines = md.splitlines()
    out, i, n = [], 0, len(lines)
    while i < n:
        l = lines[i]
        if l.startswith("```"):
            j = i + 1
            buf = []
            while j < n and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            out.append("<pre><code>%s</code></pre>" % html.escape(scrub("\n".join(buf))))
            i = j + 1
            continue
        m = re.match(r"^(#{2,4})\s+(.*)", l)
        if m:
            lv = min(len(m.group(1)) + 1, 4)
            out.append("<h%d>%s</h%d>" % (lv, _inline(m.group(2)), lv))
            i += 1
            continue
        if l.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|?\s*$", lines[i + 1]):
            head = _cells(l)
            i += 2
            rows = []
            while i < n and lines[i].startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            t = ['<div class="tw"><table><tr>%s</tr>' % "".join("<th>%s</th>" % _inline(c) for c in head)]
            for r in rows:
                t.append("<tr>%s</tr>" % "".join("<td>%s</td>" % _inline(c) for c in r))
            out.append("".join(t) + "</table></div>")
            continue
        if l.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip())
                i += 1
            warn = bool(buf) and buf[0].upper() in ("[!WARNING]", "[!CAUTION]", "[!IMPORTANT]")
            if warn:
                buf = buf[1:]
            out.append('<blockquote class="%s">%s</blockquote>' % ("warn" if warn else "", "<br>".join(_inline(b) for b in buf)))
            continue
        if re.match(r"^\s*[-*] ", l):
            out.append("<ul>")
            while i < n and re.match(r"^\s*[-*] ", lines[i]):
                ind = len(lines[i]) - len(lines[i].lstrip())
                out.append('<li%s>%s</li>' % (' style="margin-left:%dpx"' % (ind * 8) if ind else "",
                                              _inline(re.sub(r"^\s*[-*] ", "", lines[i]))))
                i += 1
            out.append("</ul>")
            continue
        if not l.strip():
            i += 1
            continue
        buf = []
        while i < n and lines[i].strip() and not re.match(r"^(#{2,4}\s|\||>|```|\s*[-*] )", lines[i]):
            buf.append(lines[i])
            i += 1
        out.append("<p>%s</p>" % _inline(" ".join(buf)))
    return "\n".join(out)


# ------------------------------------------------------------------ the content key

# Everything that moves with the clock alone: times of day, dates, durations,
# "read 41s ago", the meter's watts. A page whose key is unchanged is not
# republished (GitHub Pages branch builds are soft-limited to 10 an hour), so
# this must mask the clock and nothing else -- a lane changing state, a count
# moving, a new tick-log line all still change the key.
_VOLATILE = [
    re.compile(r'data-t="\d+"'),
    re.compile(r"\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?Z?)?"),
    re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b"),
    re.compile(r"\b\d+h \d+m\b"),
    re.compile(r"\b\d+ (second|minute|hour|day|week|month)s? ago\b"),        # git's %cr
    re.compile(r"\b\d+(\.\d+)?\s?(s|m|h|min|mins|sec|secs|W)\b"),
]


def content_key(page):
    s = page
    for rx in _VOLATILE:
        s = rx.sub("#", s)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main(argv):
    if len(argv) >= 2 and argv[1] == "key":
        print(content_key(open(argv[2], encoding="utf-8").read()))
        return 0
    if len(argv) >= 2 and argv[1] == "render":
        j = json.load(open(argv[2], encoding="utf-8"))
        dst = argv[argv.index("-o") + 1] if "-o" in argv else None
        page = render(j)
        if dst:
            _write(dst, page)
        else:
            sys.stdout.write(page)
        return 0
    if len(argv) >= 2 and argv[1] == "release05":
        a = dict(zip(argv[2::2], argv[3::2]))
        for row in release05(a.get("--titles", ""), a.get("--results", ""), a.get("--xiso", "")):
            print("\t".join(str(x).replace("\t", " ").replace("\n", " ") for x in row))
        return 0
    if len(argv) >= 2 and argv[1] == "panel":
        j = json.load(open(argv[2], encoding="utf-8"))
        r = j.get("release", {})
        print("\n".join(panel_lines(r.get("panel") or {}, r.get("name") or "0.5", int(j.get("now") or 0))))
        return 0
    if len(argv) >= 2 and argv[1] == "lanes":
        a = dict(zip(argv[2::2], argv[3::2]))
        return lanes_main(os.environ, a.get("--json", "lanes.json"), a.get("--idle", os.devnull))
    if len(argv) >= 2 and argv[1] == "build":
        a = dict(zip(argv[2::2], argv[3::2]))
        j = build(a.get("--facts", ""), a.get("--lanes", ""), a.get("--md", ""))
        if a.get("--json"):
            _write(a["--json"], json.dumps(j, indent=1, sort_keys=True) + "\n")
        if a.get("--html"):
            _write(a["--html"], render(j))
        return 0
    sys.stderr.write(__doc__)
    return 2


def _write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
