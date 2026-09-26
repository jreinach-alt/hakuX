#!/usr/bin/env python3
"""The harness dashboard: one static page, rendered from what status.sh gathers.

    status_html.py build  --facts F.tsv --lanes L.json --md STATUS.md --json OUT.json --html OUT.html
    status_html.py render IN.json -o OUT.html
    status_html.py key    OUT.html          # the page's content key, clock masked out

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


def build(facts_path, lanes_path, md_path):
    """Merge status.sh's facts.tsv, the lane block's lanes.json and STATUS.md."""
    f = {"devices": [], "attention": [], "blockers": [], "timers": []}
    kv = {}
    try:
        for line in open(facts_path, encoding="utf-8", errors="replace"):
            p = line.rstrip("\n").split("\t")
            if not p or not p[0]:
                continue
            if p[0] == "attn" and len(p) >= 3:
                f["attention"].append({"kind": p[1], "text": p[2]})
            elif p[0] == "blocker" and len(p) >= 3:
                f["blockers"].append({"number": p[1], "title": p[2]})
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
    att = []
    # the lane block's findings come first: they are the ones the owner kept finding by hand
    idle = lanes.get("idle", [])
    if idle:
        att.append({"kind": "idle", "text": "%d lane%s idle with no work: %s. Unit stopped, nothing on a device, PR draft or none: nothing will wake %s" % (
            len(idle), "" if len(idle) == 1 else "s", ", ".join(idle), "it" if len(idle) == 1 else "them")})
    for b in lanes.get("blocked", []):
        att.append({"kind": "blocked", "text": "lane %s: %s" % (b.get("lane", "?"), b.get("state", ""))})
    for s in lanes.get("fold_stuck", []):
        att.append({"kind": "fold", "text": "PR #%s fold-ready for %s and not folded: %s" % (s.get("number"), s.get("age", "?"), s.get("reason", "?"))})
    q = lanes.get("queued_old", [])
    if q:
        o = q[0]
        att.append({"kind": "queue", "text": "%d run%s queued over 60 min; oldest %s (%s, for %s)" % (
            len(q), "" if len(q) == 1 else "s", o.get("id", "?"), o.get("age", "?"), o.get("requester", "?"))})
    att += f["attention"]

    devices = lanes.get("devices", [])
    if kv.get("console"):
        m = re.match(r"(.*?)\s*\((read .*)\)\s*$", kv["console"])     # "ON, 66.2 W (read 41s ago)"
        devices = devices + [{"name": "console", "state": m.group(1) if m else kv["console"],
                              "detail": ("plug meter, " + m.group(2)) if m else "plug meter"}]
    return {
        "schema": 1,
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
        "attention": att,
        "release": {
            "name": kv.get("release_name", ""),
            "gate": kv.get("release_gate", ""),
            "candidate": kv.get("release_candidate", ""),
            "blockers": f["blockers"],
            "blockers_known": kv.get("blockers_known", "0") == "1",
            "blocker_label": kv.get("blocker_label", "release-blocker"),
        },
        "details_md": md,
    }


# ------------------------------------------------------------------ rendering

CSS = """
:root{--bg:#fff;--fg:#1b1f24;--mut:#59636e;--card:#f6f8fa;--line:#d1d9e0;--red:#cf222e;--redbg:#ffebe9;--grn:#1a7f37;--grnbg:#dafbe1;--amb:#9a6700;--ambbg:#fff8c5;--link:#0969da}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--mut:#9198a1;--card:#151b23;--line:#3d444d;--red:#ff7b72;--redbg:#3c1618;--grn:#3fb950;--grnbg:#12261e;--amb:#d29922;--ambbg:#2e2410;--link:#4493f8}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:10px 12px 40px}
a{color:var(--link)}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin-bottom:8px}
header h1{font-size:18px;margin:0}
#age{color:var(--mut);font-size:13px}
#age.stale{color:var(--red);font-weight:600}
.strip{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px;margin-bottom:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:5px 8px;min-width:0}
.tile .k{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
.tile .v{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tile .d{font-size:12px;color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tile.run .v{color:var(--grn)} .tile.held .v{color:var(--amb)}
.att{border:2px solid var(--red);background:var(--redbg);border-radius:8px;padding:6px 10px;margin-bottom:10px}
.att h2{color:var(--red);font-size:15px;margin:0 0 4px;letter-spacing:.04em}
.att ul{margin:0;padding-left:18px} .att li{margin:2px 0}
.att .kind{font-size:11px;font-weight:700;text-transform:uppercase;color:var(--red);margin-right:4px}
.ok{border:1px solid var(--grn);background:var(--grnbg);color:var(--grn);border-radius:8px;padding:6px 10px;margin-bottom:10px;font-weight:600}
.rel{border:1px solid var(--line);background:var(--card);border-radius:8px;padding:6px 10px;margin-bottom:10px;font-size:14px}
.rel b.block{color:var(--red)}
.fold{border-top:1px dashed var(--line);margin:18px 0 6px;color:var(--mut);font-size:12px;text-align:center}
section.md h3{font-size:16px;margin:18px 0 6px;border-bottom:1px solid var(--line);padding-bottom:2px}
section.md h4{font-size:14px;margin:12px 0 4px}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;font-size:13px;min-width:100%}
th,td{border:1px solid var(--line);padding:3px 6px;text-align:left;vertical-align:top;min-width:4.5em}
td:last-child{min-width:18em}
th{background:var(--card)}
pre{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 8px;overflow-x:auto;font-size:12px;line-height:1.3}
code{font:12px/1.3 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--card);padding:0 3px;border-radius:3px;overflow-wrap:anywhere}
pre code{background:none;padding:0}
blockquote{margin:6px 0;padding:4px 10px;border-left:4px solid var(--amb);background:var(--ambbg)}
blockquote.warn{border-color:var(--red);background:var(--redbg)}
section.md ul{padding-left:20px;margin:4px 0} section.md li{margin:2px 0;overflow-wrap:anywhere}
section.md p{margin:6px 0;overflow-wrap:anywhere}
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
        return "never"
    s = max(0, now - t)
    if s < 120:
        return "%ds ago" % s
    if s < 7200:
        return "%dm ago" % (s // 60)
    return "%dh %dm ago" % (s // 3600, (s % 3600) // 60)


def tile(k, v, d="", cls=""):
    return '<div class="tile %s"><div class="k">%s</div><div class="v" title="%s">%s</div>%s</div>' % (
        cls, esc(k), esc(v), esc(v), ('<div class="d" title="%s">%s</div>' % (esc(d), esc(d))) if d else "")


def render(j):
    now = int(j.get("now") or 0)
    st = j.get("strip", {})
    stale = int(j.get("heartbeat_secs") or 1800) + int(j.get("floor_secs") or 1800) + 600
    out = ['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           '<meta http-equiv="refresh" content="60">',
           '<meta name="color-scheme" content="light dark">',
           '<title>hakuX harness status</title><style>%s</style></head><body><main>' % CSS]
    out.append('<header><h1>hakuX harness</h1><span id="age" data-t="%d" data-stale="%d" data-at="%s">updated %s</span></header>' % (
        now, stale, esc(j.get("generated", "")), esc(j.get("generated", ""))))

    # ---- the strip
    out.append('<div class="strip">')
    for d in st.get("devices", []):
        state = d.get("state", "")
        cls = "run" if state == "running" else "held" if state.startswith("held") else ""
        name = d.get("name", "?")
        label = {"thor": "Thor", "nova": "Nova", "console": "Console"}.get(name, name)
        out.append(tile(label, state, d.get("detail", ""), cls))
    q = "%d queued" % st.get("queue", 0)
    out.append(tile("Queue", q, "%d running%s" % (st.get("arms_running", 0),
                    (", +%d idle-tier" % st["queue_idle"]) if st.get("queue_idle") else "")))
    out.append(tile("Lanes", "%d of %d running" % (st.get("lanes_running", 0), st.get("lane_cap", 0)),
                    st.get("window", ""), "run" if st.get("lanes_running") else ""))
    lf = st.get("last_fold") or 0
    out.append(tile("Last fold", ("%s (%s)" % (_hm(lf), _ago(now, lf))) if lf else "none seen", st.get("last_fold_subject", "")))
    out.append("</div>")

    # ---- NEEDS ATTENTION
    att = j.get("attention", [])
    if att:
        out.append('<div class="att"><h2>NEEDS ATTENTION (%d)</h2><ul>' % len(att))
        for a in att[:10]:
            out.append('<li><span class="kind">%s</span>%s</li>' % (esc(a.get("kind", "")), esc(a.get("text", ""))))
        if len(att) > 10:
            out.append("<li>%d more: see the sections below</li>" % (len(att) - 10))
        out.append("</ul></div>")
    else:
        out.append('<div class="ok">Nothing needs attention.</div>')

    # ---- release
    r = j.get("release", {})
    bl = r.get("blockers", [])
    bits = ["<b>Release %s gate:</b> %s" % (esc(r.get("name") or "0.5"), esc(r.get("gate") or "(not stated)"))]
    bits.append("Candidate: %s" % esc(r.get("candidate") or "none cut yet"))
    if not r.get("blockers_known"):
        bits.append("Open blockers: could not be read")
    elif bl:
        bits.append('<b class="block">Open blockers:</b> ' + ", ".join(
            "#%s %s" % (esc(b.get("number")), esc(b.get("title", ""))[:70]) for b in bl))
    else:
        bits.append("Open blockers: none labelled <code>%s</code>" % esc(r.get("blocker_label", "release-blocker")))
    out.append('<div class="rel">%s</div>' % "<br>".join(bits))

    out.append('<div class="fold">details</div>')
    out.append('<section class="md">%s</section>' % md_to_html(_below_fold(j.get("details_md", ""))))
    out.append('<footer>Written by <code>docs/testing/jobs/status.sh</code> on the host every job tick and every %d min; '
               'republished when the content changes (at most every 10 min) and at least every %d min. '
               'Every time here is %s. Next tick due by %s.</footer>' % (
                   int(j.get("floor_secs") or 1800) // 60, int(j.get("heartbeat_secs") or 1800) // 60,
                   esc(j.get("tz", "")), esc(j.get("next_due", "") or "?")))
    out.append("<script>%s</script></main></body></html>" % JS)
    return "\n".join(out) + "\n"


def _below_fold(md):
    """STATUS.md minus its own title block: the page header already says it."""
    i = md.find("\n### ")
    return md[i + 1:] if i >= 0 else md


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
