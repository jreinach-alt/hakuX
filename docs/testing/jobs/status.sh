#!/usr/bin/env bash
#
# The status roll-up: what is in flight, what finished, what the devices are
# doing -- one Markdown page, rewritten in place.
#
#   status.sh            write $WORK/status/STATUS.md and update the GitHub comment
#   status.sh --print    write the page and print it; do not touch GitHub
#
# It is written by every job at the end of its tick and by hakux-status.timer
# every 30 minutes as the floor. It goes to ONE comment on the issue labelled
# `harness-status` (created if none exists), edited in place, so the owner
# has a single URL, readable from a phone, that is never stale by more than
# a tick. The first evening of the job harness the same facts were spread
# over a timer, a service, four logs and two TSVs on the host, and the owner
# could not tell whether anything was running. This is the answer to that.
#
# WHERE THE CLOCK LIVES, AND WHY IT IS NOT ONLY IN THE COMMENT. GitHub renders
# a comment's `created_at` beside the author's name, leaves the comment where
# it was posted in the timeline, and marks an edit with nothing louder than a
# grey "edited" link. An in-place PATCH therefore moves NOTHING a reader sees
# first. On 2026-09-19 that made #107 -- rewritten eleven minutes earlier --
# read as eleven hours old, which is the one confusion this page exists to
# prevent: a jammed fleet and a running fleet rendered identically. So the
# time now goes in the two places GitHub does surface, measured on this repo
# (see docs/lanes/statusfresh/NOTES.md):
#
#   - the issue BODY, which renders above every comment and whose edit makes
#     no timeline event at all. This carries the minute, and is free.
#   - the issue TITLE, which is all the issue LIST shows -- the phone's first
#     screen. A title PATCH that changes the string appends a permanent
#     `renamed` row to the timeline (a PATCH to the SAME string appends
#     nothing), so the title's clock is quantised to $FLOOR: it can never
#     claim freshness finer than the timer promises, and it renames at most
#     twice an hour on a fleet that is otherwise standing still.
#
# Everything here fails soft: a section that cannot be computed says so and
# the rest still renders.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
D="${DISPATCH_DIR:-$WORK/dispatch}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
J="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S="$WORK/status"; mkdir -p "$S"
OUT="$S/STATUS.md"
. "$J/models.env" 2>/dev/null; . "$J/window.sh" 2>/dev/null; [ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
. "$J/localtime.sh"   # say_time/local_ts/tz_abbr: this page is read by a person, so it is shown in the display zone
now=$(date +%s)       # epoch: zone-free by construction, only ever subtracted (see ago())
ago() { local t=${1:-}; [ -n "$t" ] || { echo "never"; return; }; local s=$(( now - t )); if [ $s -lt 120 ]; then echo "${s}s ago"; elif [ $s -lt 7200 ]; then echo "$(( s / 60 ))m ago"; else echo "$(( s / 3600 ))h $(( (s % 3600) / 60 ))m ago"; fi; }
# DATA, NOT DISPLAY -- STAYS UTC, for two independent reasons. It is handed
# to the GitHub API as `since=`, which is specified in UTC; and it is the
# right-hand side of the lexical `$1 >= c` awk comparison below against
# logs/*/index.tsv column 1, which summarise_run.py writes in UTC for exactly
# this reason. Making either side local silently drops or duplicates rows,
# and across the November fall-back it does so in the wrong order.
since_iso() { date -u -d "${1:-24 hours ago}" +%FT%TZ 2>/dev/null; }
# The tail of a logs/*/index.tsv, for a fenced block. Column 1 is written in
# UTC by summarise_run.py (it is what since_iso() filters on) and converted
# here, at the point of printing -- a fenced block on this page is still
# something a person reads, and a UTC line inside a page whose header says
# "every time here is PDT" is the two-zones-in-one-view the conversion exists
# to remove.
tsv_tail() {
    local f=$1 n=$2 ts rest
    tail -n "$n" "$f" | while IFS= read -r line; do
        ts=${line%%$'\t'*}; rest=${line#*$'\t'}
        printf '%s %s\n' "$(local_hm "$ts")" \
            "$(printf '%s' "$rest" | awk -F'\t' '{printf "%s %s turns=%s %ss %s %s",$1,$2,$3,$4,$6,substr($8,1,80)}')"
    done
}

have_gh=0; command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1 && have_gh=1
have_sd=0; systemctl --user list-units >/dev/null 2>&1 && have_sd=1

# ---- how fresh the page can honestly claim to be, and whether it lapsed.
#
# FLOOR is hakux-status.timer's period. Nothing here can report the page's
# CURRENT silence -- a roll-up that is not running writes nothing, by
# definition -- so the page states its own deadline instead and leaves the
# reader a rule: a clock older than the deadline means status.sh has stopped.
# What it CAN report is a lapse that has already ended, and that is the more
# useful half: the window it names is a window in which the fleet was not
# observed, so an absent lane row across it means nothing either way.
FLOOR="${STATUS_FLOOR_SECS:-1800}"
case "$FLOOR" in ''|*[!0-9]*|0) FLOOR=1800 ;; esac   # a junk override must not divide by zero below and abort the tick
STAMP="$S/last-run"
prev_run=$(cat "$STAMP" 2>/dev/null); case "${prev_run:-}" in ''|*[!0-9]*) prev_run=0 ;; esac
lapse=0
[ "$prev_run" -gt 0 ] && [ $(( now - prev_run )) -gt $(( FLOOR * 2 )) ] && lapse=$(( now - prev_run ))
# DISPLAY, so the display zone: this deadline is printed in the body and the
# comment and compared by nothing but a reader's eye.
due=$(local_ts "@$(( now + FLOOR ))")
# The window module's facts and reasons carry UTC instants ("2026-09-21T00:00Z")
# because window.sh compares them; this renders each one in the display zone
# at the point of printing and leaves the variables themselves untouched.
local_instants() {
    local s=$1 m
    while [[ "$s" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(:[0-9]{2})?Z) ]]; do
        m=${BASH_REMATCH[1]}
        s=${s//"$m"/$(local_ts "$m")}
        [[ "$(local_ts "$m")" == "$m" ]] && break     # unparsed: stop rather than loop on it
    done
    printf '%s' "$s"
}

# ---- the one-glance summary, for the title and the body header.
#
# Hoisted above the page because the title is built from the same counts and
# must not re-shell for them; `units` is consumed by the lanes section below.
units=""
[ $have_sd = 1 ] && units=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend --plain 2>/dev/null | awk '{print $1}')
n_lanes=$(printf '%s' "$units" | grep -c . 2>/dev/null || true); n_lanes=${n_lanes:-0}
# The z-* idle tier (the full-corpus sweep) is counted apart: it sorts behind
# everything and waiting for hours is its design, not a backlog.
n_run=$(ls "$D"/running/*.req 2>/dev/null | wc -l); n_z=$(ls "$D"/queue/z-*.req 2>/dev/null | wc -l)
n_q=$(ls "$D"/queue/*.req 2>/dev/null | grep -vc '/z-[^/]*$')
summary="$n_lanes lane$([ "$n_lanes" = 1 ] || echo s) running, $n_run arm$([ "$n_run" = 1 ] || echo s) on a device, $n_q queued$([ "$n_z" = 0 ] || echo " (+$n_z idle-tier sweep)")"

pr_for_branch() { [ $have_gh = 1 ] || return; gh pr list --repo "$GH_REPO" --head "$1" --state all --json number,state,isDraft,url --jq '.[0] | "#\(.number) \(if .isDraft then "draft" else (.state|ascii_downcase) end)"' 2>/dev/null; }
issue_of_brief() { grep -o -m1 '#[0-9]\+' "$WORK/briefs/$1.md" 2>/dev/null | head -1; }

{
echo "## hakuX harness -- live status"
echo
echo "_Rewritten $(say_time) by \`status.sh\` on the host. Every time on this page is $(tz_abbr). Sections that could not be computed say so._"
echo
echo "_Next roll-up due by $due. A clock older than that means \`status.sh\` has stopped: a roll-up that is not running cannot say so itself._"
echo
if [ "$lapse" -gt 0 ]; then
    echo "> [!WARNING]"
    echo "> **The roll-up lapsed for $(ago "$prev_run" | sed 's/ ago$//') before this one** -- previous tick $(local_ts "@$prev_run"), this tick $(say_time). Nothing was observed across that window, so a lane or an arm that started and finished inside it has no row below. The state here is current; the history is not."
    echo
fi

# ---------------------------------------------------------------- lanes
echo "### Lanes running (cap ${LANE_MAX:-2})"
echo
if [ $have_sd = 1 ]; then
    if [ -n "$units" ]; then                     # hoisted to the summary above
        echo "| lane | issue | attempt | model | running for | PR |"; echo "|---|---|---|---|---|---|"
        for u in $units; do
            n=${u#hakux-lane-}; n=${n%.service}
            att=$(cat "$WORK/attempts/$n" 2>/dev/null || echo "?")
            if [ "${att:-0}" -gt "${LANE_ESCALATE_AFTER:-3}" ] 2>/dev/null; then m="${MODEL_LANE_ESCALATED:-fable}"; else m="${MODEL_LANE:-opus}"; fi
            ts=$(systemctl --user show "$u" -p ActiveEnterTimestamp --value 2>/dev/null); t=$(date -d "$ts" +%s 2>/dev/null)
            echo "| $n | $(issue_of_brief "$n") | $att | $m | $(ago "$t") | $(pr_for_branch "lane/$n") |"
        done
    else
        echo "none. The board dispatches up to three per tick when issues are dispatchable and their files are free."
    fi
else
    echo "(systemd --user not reachable from here)"
fi
echo

# ------------------------------------------------------------- every lane
#
# "Lanes running" above lists live units and nothing else, so a lane that had
# stopped with a draft PR and nothing on a device -- idle, with no actor that
# would ever wake it -- appeared nowhere, and so did lane.xbox (an interactive
# session) and lane.remote (a cloud session), which never have a unit at all.
# The owner found each of those by hand (2026-09-26). This table starts from
# the board's claim list instead, territory.toml on origin/board, so a lane is
# on the page for as long as it holds a row, whatever it is doing.
#
# The console meter is read here, once, because it takes the plug's lock and
# the plug must not be polled more than once a minute: every job tick ends in
# this script, so the reading is cached for 60 s under $S.
KASA="$WORK/host-tools/kasa_console.py"
meter="console meter: not available"
if [ -x "$KASA" ]; then
    mc="$S/console-meter"; mt=$(stat -c %Y "$mc" 2>/dev/null || echo 0)
    if [ $(( now - mt )) -ge 60 ]; then
        # "plug KP115 <mac> (Xbox) at <ip>: ON, 66.1 W" -- the reading is the part after the last ": "
        r=$(timeout 75 "$KASA" status --no-find 2>&1 | tail -1 | sed 's/.*: //' | cut -c1-80)
        printf '%s\n' "${r:-no answer}" > "$mc"
    fi
    ma=$(( now - $(stat -c %Y "$mc" 2>/dev/null || echo "$now") )); [ "$ma" -ge 0 ] || ma=0
    meter="console meter: $(cat "$mc" 2>/dev/null) (read ${ma}s ago)"
fi
echo "### Lanes: every row on the board ($(tz_abbr))"
echo
STATUS_METER="$meter" WORK="$WORK" D="$D" REPO="$REPO" GH_REPO="$GH_REPO" J="$J" S="$S" \
HAVE_GH=$have_gh HAVE_SD=$have_sd UNITS="$units" python3 - <<'PY' 2>&1 || echo "(the lane table could not be computed)"
# Everything here fails soft, row by row: a source that cannot be read says so
# and the rest of the table still renders.
import datetime, glob, json, os, re, subprocess, sys
sys.path.insert(0, os.environ["J"])
try:
    import localtime
    def hm(iso):
        s = localtime.local_ts(iso)
        return s[5:16] if s != iso else iso           # "09-25 21:08": the header names the zone
except Exception:
    def hm(iso): return iso
E = os.environ
W, D, REPO, GH_REPO, S = E["WORK"], E["D"], E["REPO"], E["GH_REPO"], E["S"]
have_gh, have_sd = E.get("HAVE_GH") == "1", E.get("HAVE_SD") == "1"
now = datetime.datetime.now(datetime.timezone.utc)

def run(*cmd, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.stdout if p.returncode == 0 else ""
    except Exception:
        return ""

def cell(s, n=90):
    s = " ".join(str(s or "").split())
    return (s[:n] + "...").replace("|", "\\|") if len(s) > n else s.replace("|", "\\|")

def toml_on_board(name):
    try:
        import tomllib
        bd = E.get("STATUS_BOARD_DIR")                  # a fixture's board files; the host reads origin/board
        t = open(os.path.join(bd, name)).read() if bd else run("git", "-C", REPO, "show", "origin/board:" + name)
        return tomllib.loads(t) if t else None
    except Exception:
        return None

terr = toml_on_board("territory.toml")
issues = (toml_on_board("nv2a_issues.toml") or {}).get("issue", {})
units = {u[len("hakux-lane-"):-len(".service")] for u in E.get("UNITS", "").split() if u.startswith("hakux-lane-")}
timers = set()
if have_sd:
    for l in run("systemctl", "--user", "list-timers", "hakux-*", "--no-legend", "--plain").splitlines():
        m = re.search(r"hakux-([\w.-]+)\.timer", l)
        if m: timers.add(m.group(1))

# the last session of each lane, from the index every lane run appends to
last = {}
try:
    for l in open(os.path.join(W, "logs/lane/index.tsv"), encoding="utf-8", errors="replace"):
        f = l.rstrip("\n").split("\t")
        if len(f) >= 8 and f[1].startswith("lane-"):
            last[f[1][5:]] = (f[0], f[-1])
except OSError:
    pass

# device requests, queued and running, by requester
reqs = []
for state in ("queue", "running"):
    for p in glob.glob(os.path.join(D, state, "*.req")):
        try:
            r = json.load(open(p))
            reqs.append((state, r.get("id") or os.path.basename(p)[:-4], r.get("requester") or ""))
        except Exception:
            reqs.append((state, os.path.basename(p)[:-4], ""))
def reqs_of(name):
    pat = re.compile(r"^(lane[.-])?%s$|^arms-%s-" % (re.escape(name), re.escape(name)))
    return [r for r in reqs if pat.search(r[2])]

prs, decision, prs_ok = {}, set(), False
if have_gh:
    try:
        for p in json.loads(run("gh", "pr", "list", "--repo", GH_REPO, "--state", "all", "--limit", "300",
                                "--json", "number,state,isDraft,headRefName,labels")):
            prs.setdefault(p["headRefName"], p)                 # newest first: keep the latest per branch
        prs_ok = True
    except Exception:
        pass
    try:
        decision = {str(i["number"]) for i in json.loads(run("gh", "issue", "list", "--repo", GH_REPO, "--state", "open",
                    "--label", "decision-needed", "--json", "number") or "[]")}
    except Exception:
        pass

def state_of(name, row, standing):
    p = prs.get("lane/" + name)
    labels = {l["name"] for l in (p or {}).get("labels", [])}
    if name in units: return "running"
    rq = reqs_of(name)
    if rq:
        return "waiting on device (%d running, %d queued)" % (sum(r[0] == "running" for r in rq), sum(r[0] == "queue" for r in rq))
    iss = [str(i) for i in row.get("issues", [])]
    dn = [i for i in iss if i in decision] + (["PR"] if "decision-needed" in labels else [])
    if dn: return "blocked: decision-needed on " + ", ".join(("#" + i) if i != "PR" else "its PR" for i in dn)
    if p and p["state"] == "OPEN" and not p.get("isDraft"):
        for lab, say in (("fold-ready", "fold-ready"), ("needs-remediation", "PR needs remediation"),
                         ("needs-rebase", "PR needs rebase"), ("needs-audit-2", "PR in audit (2)"), ("needs-audit-1", "PR in audit (1)")):
            if lab in labels: return say
        return "PR ready, awaiting a label"
    bl = [i for i in iss if issues.get(i, {}).get("status") == "open" and issues.get(i, {}).get("blocked_on")]
    if bl: return "blocked: #%s %s" % (bl[0], cell(issues[bl[0]]["blocked_on"], 50))
    if p and p["state"] == "MERGED": return "folded (row not yet retired)"
    if name in timers: return "job (hakux-%s.timer)" % name
    if standing: return "standing, nothing in flight"
    # Without the PR list, "no PR" is not known -- and a failed query must not
    # flag every lane idle in the issue body.
    return "IDLE" if prs_ok else "not running, nothing on a device (PR state unknown: the PR list could not be read)"

lanes = (terr or {}).get("lane", {})
rows, idle = [], []
for name, row in sorted(lanes.items()):
    if name in ("xbox", "remote"):
        continue                                        # their own rows below: no unit, a comment channel instead
    st = state_of(name, row, row.get("standing", False))
    p = prs.get("lane/" + name)
    prs_s = ("#%d %s" % (p["number"], "draft" if p.get("isDraft") and p["state"] == "OPEN" else p["state"].lower())) if p else "none"
    ts, said = last.get(name, ("", ""))
    if st == "IDLE":
        idle.append(name)
        st = "**:warning: IDLE, NO WORK**"
    rows.append((0 if "IDLE" in st else 1, name, st, " ".join("#" + str(i) for i in row.get("issues", [])), prs_s, hm(ts) if ts else "never", cell(said)))
# a unit running with no row at all is exactly the claim check_territory.py cannot see
for name in sorted(units - set(lanes)):
    ts, said = last.get(name, ("", ""))
    rows.append((1, name, "running, **no territory row**", "", "", hm(ts) if ts else "never", cell(said)))
# retired in the last day, newest first, so a lane that just finished does not vanish mid-conversation
retired = []
for name, row in (terr or {}).get("retired", {}).items():
    ru = row.get("retired_utc", "")
    try:
        age = now - datetime.datetime.strptime(ru, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError):
        continue
    if age.days >= 1 or name in lanes:
        continue
    p = prs.get("lane/" + name)
    ts, said = last.get(name, ("", ""))
    retired.append((ru, (2, name, "retired %s" % hm(ru), " ".join("#" + str(i) for i in row.get("issues", [])),
                     ("#%d %s" % (p["number"], p["state"].lower())) if p else "none", hm(ts) if ts else "never", cell(said))))
retired.sort(reverse=True)
rows += [r for _, r in retired[:16]]

if terr is None:
    print("(territory.toml on origin/board could not be read from `%s`; only running units are listed)" % REPO)
    print()
if idle:
    print("> [!WARNING]")
    print("> **%d lane%s idle with no work:** %s. Unit stopped, nothing queued or running on a device, and its PR is a draft or absent -- nothing will wake it." % (
        len(idle), "" if len(idle) == 1 else "s", ", ".join(idle)))
    print()
print("| lane | state | issue | PR | last session ended | it said |")
print("|---|---|---|---|---|---|")
for r in sorted(rows, key=lambda r: (r[0], r[1] if r[0] < 2 else "")):       # retired rows keep newest-first
    print("| %s |" % " | ".join(r[1:]))
if len(retired) > 16:
    print()
    print("_%d more rows retired in the last 24 h are not listed._" % (len(retired) - 16))

# ---- the two lanes with a comment channel instead of a unit, and the host tick
comments = []
if have_gh:
    since = (now - datetime.timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")      # data: the API's since=, UTC
    for l in run("gh", "api", "repos/%s/issues/comments?since=%s&per_page=100" % (GH_REPO, since), "--paginate",
                 "--jq", '.[] | {c: .created_at, i: (.issue_url | split("/") | last), b: .body}', timeout=120).splitlines():
        try: comments.append(json.loads(l))
        except Exception: pass
comments.sort(key=lambda c: c.get("c", ""))
def is_other(b):
    return b.startswith("[job.") or re.match(r"^`?\[host\]", b) is not None
def last_word(pred):
    m = [c for c in comments if pred(c.get("b") or "")]
    return m[-1] if m else None
def first_line(b):
    return cell(re.sub(r"^`?\[lane\.\w+\]`?\s*[-—:]*\s*", "", (b or "").strip().split("\n")[0]), 110)
def answered_after(marker, t):
    a = [c for c in comments if c.get("c", "") > t and (
        (c.get("b") or "").startswith("[job.deliver] " + marker) or
        (re.match(r"^`?\[host\]", c.get("b") or "") and marker in (c.get("b") or "")))]
    return a[-1] if a else None

print()
if not have_gh:
    print("- **lane.xbox**, **lane.remote**: (gh not available here)")
else:
    xb = last_word(lambda b: not is_other(b) and "[lane.xbox]" in b)
    xr = [r for r in reqs if "xbox" in r[1]]
    print("- **lane.xbox** (interactive session; the console): last `[lane.xbox]` comment %s; %s. Device requests: %s. %s." % (
        ("%s on #%s: %s" % (hm(xb["c"]), xb["i"], first_line(xb["b"]))) if xb else "none in 48h",
        ("host answered %s" % hm(answered_after("lane.xbox", xb["c"])["c"])) if xb and answered_after("lane.xbox", xb["c"]) else "**no host answer after it**" if xb else "",
        ("%d running, %d queued (%s)" % (sum(r[0] == "running" for r in xr), sum(r[0] == "queue" for r in xr), ", ".join(r[1] for r in xr[:4]))) if xr else "none queued or running",
        E.get("STATUS_METER", "console meter: not available")))
    rm = last_word(lambda b: not is_other(b) and "`[lane.remote]`" in b)
    ans = answered_after("lane.remote", rm["c"]) if rm else None
    print("- **lane.remote** (cloud session, one-way): last `` `[lane.remote]` `` comment %s; %s." % (
        ("%s on #%s: %s" % (hm(rm["c"]), rm["i"], first_line(rm["b"]))) if rm else "none in 48h",
        ("host answered %s" % hm(ans["c"])) if ans else ("**NOT ANSWERED YET** -- it cannot hear anything else" if rm else "nothing to answer")))

# ---- the host ops tick: its digest header is "=== <UTC stamp>.json rc=..."
dg = os.path.join(W, "logs/hostops/digest.log")
try:
    txt = open(dg, encoding="utf-8", errors="replace").read()
    blocks = re.split(r"(?m)^=== ", txt)
    blk = blocks[-1] if len(blocks) > 1 else ""
    head, _, body = blk.partition("\n")
    m = re.match(r"(\d{8}T\d{6}Z)", head)
    t = datetime.datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%dT%H:%M:%SZ") if m else ""
    fl = next((l for l in body.splitlines() if l.strip()), "")
    print("- **host ops tick** (`hakux-hostops.timer`, every 20 min): last tick %s: %s" % (hm(t) if t else "unknown", cell(fl, 140)))
except OSError:
    print("- **host ops tick**: not available on this host (`$WORK/logs/hostops/digest.log`)")

try:
    with open(os.path.join(S, "idle-lanes"), "w") as f:
        f.write(", ".join(idle) + ("\n" if idle else ""))
except OSError:
    pass
PY
echo

# ------------------------------------------------- the account's windows
#
# A FLEET THAT GOES QUIET FOR BUDGET REASONS LOOKS EXACTLY LIKE A FLEET THAT
# HAS JAMMED. That is the failure the whole job harness was rebuilt to remove,
# so the reserve says the same thing in three places: this section, the board's
# tick log, and the board session's own brief. If dispatch is held, the reason
# and the resume time are HERE, above the fold, next to the empty lane table
# that would otherwise be the only visible symptom.
echo "### Window budget (the account's five-hour and weekly windows)"
echo
if declare -f window_check >/dev/null 2>&1; then
    window_check
    if [ "${WINDOW_DEFER:-0}" = 1 ]; then
        # The resume time is the one line on this page a person acts on, and the
        # header above promises every time here is the display zone -- so it is
        # converted. So are the UTC instants inside $WINDOW_WHY/$WINDOW_FACTS,
        # by local_instants() at the point of printing: window.sh keeps them
        # UTC for its own comparisons and nothing here writes them back.
        # local_ts falls back to UTC (and then to its own argument) when the
        # zone or the parse is unavailable.
        echo "- **dispatch DEFERRED until $(local_ts "$WINDOW_UNTIL")** -- $(local_instants "$WINDOW_WHY")."
        echo "- This is a budget decision, not a failure. Folds, arms, labels, sessions already running and this page continue; no lane attempt is counted; nothing here needs investigating."
    else
        echo "- dispatching normally. Lanes and audits start as work allows; expanding is the default."
    fi
    echo "- $(local_instants "$WINDOW_FACTS")."
    if [ -s "$WORK/window/limits.tsv" ]; then
        echo "- usage-limit refusals recorded (\`\$WORK/window/limits.tsv\`), most recent last:"
        echo '```'; tail -5 "$WORK/window/limits.tsv" | while IFS= read -r l; do local_instants "$l"; echo; done; echo '```'
    else
        echo "- no session has ever been refused by the account's window on this host. That is the only first-hand evidence of a closed window there is: **the remaining five-hour and weekly balance cannot be queried from here**, so the weekly reserve arms on that evidence, or on \`WEEK_SPEND_BUDGET\` if the owner declares one in \`\$WORK/limits.env\`. Unknown means open, by design."
    fi
else
    echo "(jobs/window.sh not available here)"
fi
echo

echo "### Lane sessions finished (last 24h)"
echo
if [ -f "$WORK/logs/lane/index.tsv" ]; then
    cut=$(since_iso)
    rows=$(awk -F'\t' -v c="$cut" '$1 >= c' "$WORK/logs/lane/index.tsv" | tail -12)
    if [ -n "$rows" ]; then
        echo "| when ($(tz_abbr)) | lane | model | turns | min | result | PR | said |"; echo "|---|---|---|---|---|---|---|---|"
        while IFS=$'\t' read -r ts job model turns secs cost ok log head; do
            # Rows written before the model column existed have eight fields; shift them.
            if [[ "$model" =~ ^[0-9?]+$ ]]; then head="$log"; log="$ok"; ok="$cost"; cost="$secs"; secs="$turns"; turns="$model"; model="-"; fi
            n=${job#lane-}; if [[ "${secs:-}" =~ ^[0-9]+$ ]]; then mins=$(( secs / 60 )); else mins="?"; fi   # a "?" from an unparsed log is not a number, and an arithmetic error here aborted the whole page
            # $ts is UTC on disk and converted HERE, at the point of printing.
            # The column it comes from is what since_iso() filters on above,
            # so the stored field must stay UTC; only the reader sees local.
            echo "| $(local_hm "$ts") | $n | ${model#claude-} | $turns | $mins | $ok | $(pr_for_branch "lane/$n") | $(echo "$head" | cut -c1-90 | sed 's/|/\\|/g') |"
        done <<< "$rows"
    else
        echo "none in the window."
    fi
    echo
    echo "_result: ok = ended on its own; MAXTURNS = cut at the turn cap, work kept; ERR = the session errored. A lane that ended without a ready PR is resumed by the board (attempts 1-${LANE_ESCALATE_AFTER:-3} on ${MODEL_LANE:-opus}, then ${MODEL_LANE_ESCALATED:-fable}, then decision-needed)._"
else
    echo "no lane index yet."
fi
echo

# ---------------------------------------------------------------- cloud
echo "### Cloud-class sessions (hourly, on the host; last 24h from their \`[job.cloud]\` comments)"
echo
if [ $have_gh = 1 ]; then
    # created_at comes back in UTC (the API's own zone, which is also why
    # since= above must stay UTC). It is emitted whole and converted below
    # rather than sliced in jq, so the reader gets the same zone as the rest
    # of the page.
    c=$(gh api "repos/$GH_REPO/issues/comments?since=$(since_iso)&per_page=100" \
          --jq '.[] | select(.body | startswith("[job.cloud]")) | "\(.created_at)\t\(.html_url | sub(".*/(issues|pull)/"; "#") | sub("#issuecomment.*"; "")) \(.body | split("\n")[0] | .[11:120])"' 2>/dev/null | tail -10)
    if [ -n "$c" ]; then
        while IFS=$'\t' read -r cts crest; do
            [ -n "$cts" ] || continue
            echo "- $(local_hm "$cts") $crest"
        done <<< "$c"
    else
        echo "none. cloud.sh runs hourly and claims one \`needs-audit-*\` PR or one \`cloud\` issue per tick; a tick with nothing to claim leaves no comment."
    fi
    [ $have_sd = 1 ] && echo "- running now: $(systemctl --user list-units 'hakux-cloud-*' --state=active,activating --no-legend --plain 2>/dev/null | awk '{printf "%s ", $1}' | sed 's/hakux-//g; s/.service//g')"
    [ -f "$WORK/logs/cloud/index.tsv" ] && { echo; echo '```'; tsv_tail "$WORK/logs/cloud/index.tsv" 4; echo '```'; }
else
    echo "(gh not available here)"
fi
echo

# ---------------------------------------------------------------- board
echo "### Board job (every 20 min)"
echo
if [ -f "$WORK/logs/board/tick.log" ]; then
    echo '```'; tail -6 "$WORK/logs/board/tick.log" | cut -c1-160; echo '```'
    [ -f "$WORK/logs/board/index.tsv" ] && { echo; echo "last model ticks:"; echo '```'; tsv_tail "$WORK/logs/board/index.tsv" 3; echo '```'; }
    echo; echo "board branch: $(git -C "$REPO" log -1 --format='%h %cr -- %s' origin/board 2>/dev/null | cut -c1-120)"
else
    echo "no tick log."
fi
echo

# ---------------------------------------------------------------- arms
echo "### Handhelds and arms"
echo
if command -v adb >/dev/null 2>&1; then
    devs=$(adb devices 2>/dev/null | tr -d '\r' | awk 'NR>1 && $2!=""{printf "%s(%s) ", $1, $2}')
    echo "- adb: ${devs:-no device visible}"
fi
[ $have_sd = 1 ] && echo "- dispatcher: $(systemctl --user is-active hakux-dispatcher.service 2>/dev/null), workers: $(pgrep -fc 'dispatcher.sh worker' 2>/dev/null || echo ?)"
echo "- queue: $n_q waiting, $n_z idle-tier z-* behind them, $n_run running; holds: $(ls "$D"/hold 2>/dev/null | grep -v '\.why$' | grep -v '^lifted$' | tr '\n' ' ')"
for r in "$D"/running/*.req; do [ -f "$r" ] || continue; echo "  - running: $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('requester',''),d.get('ref','')[:10],'--',(d.get('purpose') or '')[:90])" "$r" 2>/dev/null)"; done
[ -f "$D/logs/dispatcher.log" ] && echo "- dispatcher last line: \`$(tail -1 "$D/logs/dispatcher.log" | cut -c1-140)\`"

# ---- affinity: which handheld a pair is pinned to, and when it was not.
#
# `affinity.py`'s whole job is keeping the two arms of an A/B on ONE device,
# and when it cannot it writes a note into `$D/splits/`. Until this section
# NOTHING READ THAT DIRECTORY. On 2026-09-19 #89's pair ran base on the thor
# and fix on the nova; the note saying so was written correctly and was found
# only by someone who already suspected it and knew the path. The note's own
# docstring says it exists "so the DECISION is discoverable rather than
# reconstructed from a pace difference" -- which requires a reader.
#
# Asking affinity.py for `serving` rather than counting files: `$D/lanes/` is
# shared with check_coverage.py's `<lane>.lastbrief` stamps, a different
# feature and a different meaning of "lane", so a file count there would
# report devices that do not exist.
if aff_live=$(python3 "$(dirname "$J")/affinity.py" "$D" --serving 2>/dev/null); then
    if [ -n "$aff_live" ]; then
        echo "- affinity: lanes serving \`$aff_live\` -- an A/B pair queued now is pinned to one of them"
    else
        echo "- affinity: **no device lane is registered** in \`$D/lanes\`. Pinning is inert: an A/B pair queued now can split across two handhelds, and \`ab_compare\` will refuse to attribute the result. Check that \`hakux-dispatcher.service\` is up."
    fi
else
    echo "- affinity: (could not read \`$D/lanes\`)"
fi
sp=$(find "$D/splits" -maxdepth 1 -name '*.txt' -mmin -1440 -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -5 | cut -d' ' -f2-)
if [ -n "$sp" ]; then
    echo "- affinity notes, last 24h (a pair named here may span two devices and cannot isolate run-to-run variation):"
    while read -r f; do
        [ -n "$f" ] || continue
        echo "  - \`$(basename "$f" | sed 's/\.req\.\(blind\.\)\?txt$//' | cut -c1-48)\`: $(tr '\n' ' ' < "$f" | cut -c1-220 | sed 's/|/\\|/g')"
    done <<< "$sp"
fi
A="$WORK/arms"
if [ -d "$A" ]; then
    pend=0; for p in "$A"/pairs/*.json; do [ -f "$p" ] || continue; sha=$(basename "$p" .json); [ -f "$A/judged/$sha" ] || pend=$((pend+1)); done
    echo "- arms job: $pend pair(s) queued or running and not yet judged; $(ls "$A"/judged 2>/dev/null | wc -l) judged; $(ls "$A"/skipped 2>/dev/null | wc -l) skipped (see \`arms.sh list\`); watermark $(local_ts "$(cat "$A/since" 2>/dev/null)") (stored as \`$(cat "$A/since" 2>/dev/null)\`: arms.sh compares that UTC string to registered_utc, so the file stays UTC and only this rendering is local)"
    v=$(ls -t "$A"/judged/* 2>/dev/null | head -5)
    if [ -n "$v" ]; then
        echo; echo "last verdicts:"; echo
        for f in $v; do sha=$(basename "$f"); src=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('source',''))" "$A/pairs/$sha.json" 2>/dev/null); echo "- \`${sha:0:10}\` $src: $(head -1 "$f" | cut -c1-120)"; done
    fi
    [ -f "$WORK/logs/arms/tick.log" ] && { echo; echo '```'; tail -4 "$WORK/logs/arms/tick.log" | cut -c1-160; echo '```'; }
    sk=$(ls -t "$A"/skipped/* 2>/dev/null | head -3)
    if [ -n "$sk" ]; then
        echo; echo "last refusals, in full (a refusal is recorded once; delete the file under \`\$WORK/arms/skipped/\` to retry):"; echo
        for f in $sk; do echo "- \`$(basename "$f" | cut -c1-10)\` $(cat "$f" | cut -c1-600)"; done
    fi
else
    echo "- arms job: not installed yet"
fi
echo

# ---------------------------------------------------------------- fold
echo "### Fold job (every 30 min)"
echo
if [ $have_gh = 1 ]; then
    echo "- fold-ready: $(gh pr list --repo "$GH_REPO" --state open --label fold-ready --json number --jq 'map("#\(.number)") | join(" ")' 2>/dev/null); needs-rebase: $(gh pr list --repo "$GH_REPO" --state open --label needs-rebase --json number --jq 'map("#\(.number)") | join(" ")' 2>/dev/null); needs-remediation: $(gh pr list --repo "$GH_REPO" --state open --label needs-remediation --json number --jq 'map("#\(.number)") | join(" ")' 2>/dev/null)"
    echo "- awaiting audit: needs-audit-1 $(gh pr list --repo "$GH_REPO" --state open --label needs-audit-1 --json number --jq 'map("#\(.number)") | join(" ")' 2>/dev/null); needs-audit-2 $(gh pr list --repo "$GH_REPO" --state open --label needs-audit-2 --json number --jq 'map("#\(.number)") | join(" ")' 2>/dev/null)"
fi
[ -f "$WORK/logs/fold/tick.log" ] && { echo '```'; tail -4 "$WORK/logs/fold/tick.log" | cut -c1-160; echo '```'; } || echo "no fold tick yet."
echo "- master: $(git -C "$REPO" log -1 --format='%h %cr -- %s' origin/master 2>/dev/null | cut -c1-120)"
echo

# ---------------------------------------------------------------- open PRs
echo "### Open lane PRs"
echo
if [ $have_gh = 1 ]; then
    gh pr list --repo "$GH_REPO" --state open --json number,title,isDraft,headRefName,labels,updatedAt \
        --jq '.[] | "- #\(.number) \(if .isDraft then "(draft) " else "" end)`\(.headRefName)` \(.title | .[0:80]) -- labels: \(.labels | map(.name) | join(", ") | if . == "" then "none" else . end)"' 2>/dev/null
fi
echo
echo "### Job errors (last 24h, from the units' logs)"
echo
errs=0
for j in board arms fold cloud status; do
    f="$WORK/logs/$j/systemd.log"; [ -f "$f" ] || continue
    [ "$(( now - $(stat -c %Y "$f") ))" -lt 86400 ] || continue
    e=$(grep -nE 'Traceback|error:|Error|No such file|command not found|REFUSED|FAILED' "$f" | tail -3)
    [ -n "$e" ] || continue
    errs=1; echo "- **$j** (\`$f\`):"; echo '```'; echo "$e" | cut -c1-200; echo '```'
done
[ $errs = 0 ] && echo "none seen."
echo
echo "### Host"
echo
echo "- checkout \`$REPO\` on $(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null), $(git -C "$REPO" rev-list --count HEAD..origin/master 2>/dev/null || echo '?') behind origin/master (jobs run the fetched trunk regardless)"
[ $have_sd = 1 ] && echo "- timers: $(systemctl --user list-timers 'hakux-*' --no-legend --plain 2>/dev/null | awk '{printf "%s next %s; ", $NF, ($1 == "-" ? "-" : $3 " " $4)}' | sed 's/.service//g; s/hakux-//g' | cut -c1-300)"
echo "- attempts: $(for f in "$WORK"/attempts/*; do [ -e "$f" ] && printf '%s=%s ' "$(basename "$f")" "$(cat "$f")"; done)"
} > "$OUT" 2>/dev/null

[ "${1:-}" = "--print" ] && { cat "$OUT"; exit 0; }
echo "$now" > "$STAMP"          # a real tick ran; --print is a dry run and does not count
[ $have_gh = 1 ] || { echo "wrote $OUT (gh unavailable; comment not updated)"; exit 0; }

# ------------------------------------------------- the one comment on GitHub
#
# `--json number,title`: the title comes back in the call we already make, so
# deciding whether to rename costs no extra request.
il=$(gh issue list --repo "$GH_REPO" --label harness-status --state open --json number,title --jq '.[0] | "\(.number) \(.title)"' 2>/dev/null); ilrc=$?
issue=${il%% *}; cur_title=""; [ "$il" != "$issue" ] && cur_title=${il#* }
# An empty list interpolates to the literal "null", which is not empty and used
# to sail into `PATCH /issues/null` -- every call returning 0 while the page
# went nowhere. Treat anything that is not a number as "no issue".
case "${issue:-}" in ''|*[!0-9]*) issue="" ;; esac
if [ -z "$issue" ]; then
    # Only a query that SUCCEEDED and found nothing licenses a second status
    # issue. A network blip must not fork the one page the owner reads.
    [ $ilrc -eq 0 ] || { echo "the harness-status query failed; not creating a second status issue"; exit 0; }
    issue=$(gh issue create --repo "$GH_REPO" --title "harness: live status (auto-updated)" --label harness-status --label harness \
        --body "Rewritten by \`docs/testing/jobs/status.sh\` at the end of every job tick and every 30 minutes. Pin this issue. Do not comment here; the roll-up is the only content, and it is regenerated from the host each time." 2>/dev/null | grep -o '[0-9]*$')
    [ -n "$issue" ] || { echo "could not create the status issue"; exit 0; }
    cur_title=""
    rm -f "$S/comment-id"
fi
cid=$(cat "$S/comment-id" 2>/dev/null)
posted=""
if [ -n "$cid" ] && gh api "repos/$GH_REPO/issues/comments/$cid" --silent >/dev/null 2>&1; then
    gh api -X PATCH "repos/$GH_REPO/issues/comments/$cid" -F body=@"$OUT" --silent >/dev/null 2>&1 && posted="updated #$issue comment $cid"
fi
if [ -z "$posted" ]; then       # no id, a deleted comment, or a PATCH that failed
    cid=$(gh api -X POST "repos/$GH_REPO/issues/$issue/comments" -F body=@"$OUT" --jq .id 2>/dev/null)
    [ -n "$cid" ] && { echo "$cid" > "$S/comment-id"; posted="created #$issue comment $cid"; }
fi
echo "${posted:-could not write the #$issue comment}"

# ---------------------------------------- the body: what the page shows FIRST
#
# Short on purpose. The roll-up stays in the comment -- its URL is deep-linked
# from elsewhere and its content is unchanged -- and this is the header a phone
# lands on: the clock, the counts, the deadline, and the reason not to believe
# the timestamp printed beside the comment.
HDR="$S/HEADER.md"
{
echo "## hakuX harness -- live status"
echo
echo "**Written $(say_time).** $summary."
# The condition the owner kept finding by hand, lifted from the lane table
# below (lanes_section writes it) to the first thing the page shows.
[ -s "$S/idle-lanes" ] && { echo; echo "**Idle with no work:** $(cat "$S/idle-lanes") -- unit stopped, nothing on a device, PR draft or none. See the lane table in the comment."; }
echo
echo "Next roll-up due by **$due** ($(( FLOOR / 60 ))-minute floor, plus one at the end of every job tick). If the clock above is older than that, \`status.sh\` itself has stopped -- the page cannot report its own silence, so judge it by this line."
if [ "$lapse" -gt 0 ]; then
    echo
    echo "> [!WARNING]"
    echo "> **The roll-up lapsed for $(ago "$prev_run" | sed 's/ ago$//') before this one** (previous tick $(local_ts "@$prev_run")). The state below is current; nothing was observed across that window."
fi
echo
[ -n "$cid" ] && echo "The full roll-up is [in the comment below](https://github.com/$GH_REPO/issues/$issue#issuecomment-$cid), rewritten in place every tick."
echo "GitHub shows a comment's *posted* time, not its edited time, and never moves an edited comment -- so read the clock in this body and in the title above it, never the timestamp beside the comment."
echo
# Carried forward from the body this header replaces. It is the page's only
# standing instruction and the first tick after this landed would have been the
# last anyone saw of it.
echo "_Pin this issue. Do not comment here: the roll-up is the only content, and it is regenerated from the host each tick._"
} > "$HDR" 2>/dev/null
gh api -X PATCH "repos/$GH_REPO/issues/$issue" -F body=@"$HDR" --silent >/dev/null 2>&1 \
    && echo "updated #$issue body" || echo "could not update the #$issue body"

# ------------------------------------------ the title: all the issue LIST shows
#
# Quantised to $FLOOR (see the header of this file): a rename is a permanent
# timeline row, a PATCH to an unchanged title is not, and the page must not
# claim to be fresher than the timer that writes it. Reading the stamped time
# as exact therefore errs towards "staler than it is", which is the safe way
# round for the question this page answers.
#
# The clock is the display zone's ("21:00 PDT+"). $q is still quantised in
# epoch seconds, so a whole-hour offset keeps the same boundaries; the one
# rename this costs is the tick after the zone change lands.
q=$(( now - now % FLOOR ))
qt=$(local_ts "@$q")
want="harness: live status -- ${qt#* }+, $summary"
if [ "$want" != "$cur_title" ]; then
    gh api -X PATCH "repos/$GH_REPO/issues/$issue" -f title="$want" --silent >/dev/null 2>&1 \
        && echo "renamed #$issue: $want"
else
    echo "#$issue title unchanged"
fi
exit 0
