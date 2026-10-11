#!/usr/bin/env python3
"""The title registry: one generated row per title saying what the project's
own records say about it, so nothing that decides a dispatch has to read prose.

    title_registry.py build  [--root W] [--out PATH] [--no-forge]
    title_registry.py check  [--root W] [--registry PATH]      exit 0 fresh, 3 stale/missing
    title_registry.py show   [--root W] [--registry PATH] (TITLE_ID | --status S | --all)
    title_registry.py resolve [--root W] NAME                 what a name resolves to, and from where

W is the host work dir (default /home/justin/hakux-work). The registry is
W/pm/title-registry.tsv. It is GENERATED: never hand-edit it; edit a source
and rebuild. dispatch_gate.py admit() refuses everything while it is stale:
older than STALE_S (15 min), or the sources' digest has moved since it was
built (a new verdict, a ledger row, an owner hold).

WHY (owner order 2026-10-06 ~16:50, four wrong dispatches in one day): the
Excluded lists, plans and briefs were prose copied by hand, and a verdict's
`failing` names only the FIRST failed gate. DOA3's read "menu time" and its
fps miss (fps_ok_share 0.4394) went unseen into a run order.

IDENTITY is the 4-byte hex title_id, never a substring of a name. A record
that carries only a name (the ledger's `-` rows, the held runs of folder ISOs
that have no title-id prefix) is resolved by EXACT equality of a normalised
name against the catalog: ISO stems from the device listings
(`<TID>-<stem>.xiso.iso`), owner-library-done.tsv, the console inventory and
targets.toml. A name that matches no title, or more than one, is reported
UNRESOLVED and attaches to nothing; the build prints every such name.

SOURCES (all read as data):
  pm/playable-accepted.tsv                      the Playable ledger
  wt/pathfind/docs/lanes/pathfind/runs/*/, */*/  held runs (verdict/result/request.json)
  dispatch/results/*/                           dispatcher runs (verdict/request/result.json)
  pm/failure-intake.tsv, pm/pathfind-pool.tsv   crash/hang/menu rows
  pm/owner-holds.tsv                            owner holds and owner orders (lane.local writes it)
  host-tools/blocked-titles.txt                 owner-blocked titles (Galleon)
  pm/title-fixes.tsv                            fixes that answer a named gate of a title (lane.local writes it)
  wt/pathfind/docs/testing/titles/pathknow/paths/<TID>.json   recorded input sequences
  hardware/titlepush/listing-*.txt, pm/*-100?.done            what is staged on which handheld
  the local forge's open issues                 a hold whose release is "issues close". Read over the
                                                Forgejo HTTP API (127.0.0.1:3330, W/forge/tokens/jobs.token),
                                                never `gh` (no GitHub contact). Unreadable: the header says
                                                forge=unreadable and every such hold stays active.
"""
import argparse
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DEFAULT_ROOT = "/home/justin/hakux-work"
FORGE_URL = "http://127.0.0.1:3330"     # the local Forgejo (since 2026-10-02); never GitHub
FORGE_REPO = "jreinach-alt/hakuX"
FORGE_USER = "jobs"
STALE_S = 15 * 60
FPS_SHARE_MIN = 0.90      # targets.toml [defaults] fps_share_min
PLAY_SHARE_MIN = 0.90     # title_verdict.py play_share_min default
AUDIO_MAX = 0.001         # targets.toml [defaults] audio_starve_max_share
PT = dt.timezone(dt.timedelta(hours=-7))   # PDT; every PM record on disk is PDT in October

STATUSES = ("PLAYABLE", "EXCLUDED", "PENDING_OWNER", "CRASH_OR_HANG", "BELOW_BAR",
            "FAILED_HARNESS", "VOID", "UNSCREENED")
PERF_GATES = ("fps", "hitch", "audio")
TID_RE = re.compile(r"^[0-9A-F]{8}$")
ISO_TID = re.compile(r"^([0-9A-Fa-f]{8})-(.+)$")

COLUMNS = ["title_id", "aliases", "name", "status", "status_rule", "ledger", "flicker", "holds", "hold_detail",
           "latest_verdict", "verdict_utc", "fps_ok_share", "fps_window_median", "play_share",
           "play_s", "hitch", "crash", "hang", "void", "failing_all", "cause", "fix_commit",
           "last_run", "last_run_utc", "last_run_build", "runs_total", "runs_today",
           "staged", "input_seq", "notes"]


# ---------------------------------------------------------------- paths

class Paths:
    def __init__(self, root=DEFAULT_ROOT):
        self.root = root
        self.pm = os.path.join(root, "pm")
        self.registry = os.path.join(self.pm, "title-registry.tsv")
        self.ledger = os.path.join(self.pm, "playable-accepted.tsv")
        self.holds = os.path.join(self.pm, "owner-holds.tsv")
        self.intake = os.path.join(self.pm, "failure-intake.tsv")
        self.pool = os.path.join(self.pm, "pathfind-pool.tsv")
        self.asks = os.path.join(self.pm, "owner-asks.tsv")
        self.blocked = os.path.join(root, "host-tools", "blocked-titles.txt")
        self.pf = os.path.join(root, "wt", "pathfind")
        self.pf_runs = os.path.join(self.pf, "docs", "lanes", "pathfind", "runs")
        self.fixes = os.path.join(self.pm, "title-fixes.tsv")
        self.pf_paths = os.path.join(self.pf, "docs", "testing", "titles", "pathknow", "paths")
        self.dispatch = os.path.join(root, "dispatch")
        self.results = os.path.join(self.dispatch, "results")
        self.titlepush = os.path.join(root, "hardware", "titlepush")
        self.inventory = sorted(glob.glob(os.path.join(root, "titles", "console-inventory-*.csv")))
        self.xemu = sorted(glob.glob(os.path.join(root, "titles", "xemu-compat-*.csv")))
        self.targets = os.path.join(HERE, "titles", "targets.toml")
        self.routes = os.path.join(HERE, "titles", "routes")
        self.forge_token = os.path.join(root, "forge", "tokens", FORGE_USER + ".token")

    def source_files(self):
        """Every file whose change makes a built registry stale. Sorted."""
        fs = [self.ledger, self.holds, self.intake, self.pool, self.asks, self.blocked,
              self.fixes, self.targets] + self.inventory + self.xemu
        fs += glob.glob(os.path.join(self.titlepush, "listing-*.txt"))
        fs += [os.path.join(self.titlepush, "owner-library-done.tsv")]
        fs += glob.glob(os.path.join(self.pm, "*-100?.done"))
        for pat in ("*/verdict.json", "*/*/verdict.json", "*/result.json", "*/*/result.json"):
            fs += glob.glob(os.path.join(self.pf_runs, pat))
        fs += glob.glob(os.path.join(self.results, "*", "verdict.json"))
        fs += glob.glob(os.path.join(self.pf_paths, "*.json"))
        return sorted(set(f for f in fs if os.path.isfile(f)))


def sources_digest(paths):
    h = hashlib.sha256()
    files = paths.source_files()
    for f in files:
        st = os.stat(f)
        h.update(("%s\0%d\0%d\n" % (os.path.relpath(f, paths.root), st.st_size, int(st.st_mtime))).encode())
    return h.hexdigest()[:16], len(files)


# ---------------------------------------------------------------- small readers

def read_tsv(path, header=True):
    """Rows of a TSV as dicts (header=True) or lists. '#' lines are comments,
    except a first line '# a<TAB>b' which is the header (owner-asks.tsv)."""
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip("\n") for l in f]
    if not header:
        return [l.split("\t") for l in lines if l.strip() and not l.startswith("#")]
    hdr = None
    out = []
    for l in lines:
        if not l.strip():
            continue
        if hdr is None:
            if l.startswith("#") and "\t" not in l:
                continue          # a comment above the header
            hdr = l.lstrip("# ").split("\t")
            continue
        if l.startswith("#"):
            continue
        cells = l.split("\t")
        out.append(dict(zip(hdr, cells + [""] * (len(hdr) - len(cells)))))
    return out


def load_json(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def parse_pdt(s):
    """'2026-10-05 15:55:44 PDT' or '2026-10-05 15:55' (PDT) -> aware datetime, else None."""
    if not s:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if not m:
        m2 = re.match(r"(\d{4}-\d{2}-\d{2})$", s.strip())
        if m2:
            return dt.datetime.strptime(m2.group(1), "%Y-%m-%d").replace(tzinfo=PT)
        return None
    d, hh, mm, ss = m.groups()
    return dt.datetime.strptime("%s %02d:%s:%s" % (d, int(hh), mm, ss or "00"),
                                "%Y-%m-%d %H:%M:%S").replace(tzinfo=PT)


def parse_utc(s):
    if not s:
        return None
    try:
        return dt.datetime.strptime(s.rstrip("Z")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def iso_z(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else ""


# ---------------------------------------------------------------- identity

def norm_name(s):
    """Normalise a title name or ISO file name for EXACT comparison: drop the
    extension, a leading title-id, (region) groups, then everything but a-z0-9."""
    s = s or ""
    s = os.path.basename(s)
    s = re.sub(r"(\.xiso)?\.(iso|7z|zip)$", "", s, flags=re.I)
    m = ISO_TID.match(s)
    if m:
        s = m.group(2)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.replace("_", " ")
    return re.sub(r"[^a-z0-9]", "", s.lower())


class Catalog:
    """Identity. `canon` maps a regional title_id to xemu's canonical one
    (titles/xemu-compat-*.csv, the key onhand.py's one-copy rule uses), so a
    USA and a European disc of one game are one registry row. `names` holds a
    display name per canonical id that has a reason to be a row (on a device
    listing, in the inventory, the ledger or a run); `by_norm` maps an exact
    normalised name to {canonical id: [where]}."""

    def __init__(self):
        self.names = {}
        self.by_norm = {}
        self.canon = {}
        self.aliases = {}

    def canonical(self, tid):
        tid = (tid or "").upper()
        return self.canon.get(tid, tid)

    def add(self, tid, name, where, row=True):
        if not tid or not TID_RE.match(tid.upper()):
            return
        tid = tid.upper()
        c = self.canonical(tid)
        self.aliases.setdefault(c, set()).add(tid)
        if row and name and (c not in self.names or where.startswith("listing")):
            if where.startswith("listing") or c not in self.names:
                self.names[c] = name
        n = norm_name(name)
        if n:
            self.by_norm.setdefault(n, {}).setdefault(c, []).append(where)

    def resolve(self, name):
        """(canonical tid|None, why). Exact normalised equality only; a name that
        matches two different games is unresolved."""
        if name and TID_RE.match(name.strip().upper()):
            return self.canonical(name.strip()), "is a title id"
        m = ISO_TID.match(os.path.basename(name or ""))
        if m:
            return self.canonical(m.group(1)), "title-id prefix of the ISO name"
        hits = self.by_norm.get(norm_name(name), {})
        if len(hits) == 1:
            tid = next(iter(hits))
            return tid, "exact name match (%s)" % hits[tid][0]
        if not hits:
            return None, "no catalog title has this exact name"
        return None, "ambiguous: %s" % ", ".join("%s (%s)" % (t, w[0]) for t, w in sorted(hits.items()))


def build_catalog(p):
    cat = Catalog()
    # canonical ids first, so every later add() lands on the canonical row
    xemu = []
    for xf in p.xemu:
        with open(xf, encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                tid = (r.get("title_id") or "").upper()
                c = (r.get("canonical_title_id") or tid).upper()
                if TID_RE.match(tid) and TID_RE.match(c):
                    cat.canon[tid] = c
                    xemu.append((tid, r.get("name"), os.path.basename(xf)))
    for tid, name, where in xemu:      # resolution only: an xemu title is not a row by itself
        cat.add(tid, name, where, row=False)
    for lf in sorted(glob.glob(os.path.join(p.titlepush, "listing-*.txt"))):
        dev = os.path.basename(lf)[len("listing-"):-len(".txt")]
        for line in open(lf, errors="replace"):
            m = ISO_TID.match(line.strip())
            if m:
                cat.add(m.group(1), m.group(2).replace(".xiso.iso", "").replace("_", " "), "listing-%s" % dev)
    for row in read_tsv(os.path.join(p.titlepush, "owner-library-done.tsv"), header=False):
        if len(row) >= 3:
            m = re.search(r"\bok ([0-9A-Fa-f]{8})\b", row[2])
            if m:
                cat.add(m.group(1), row[0], "owner-library-done.tsv")
    for inv in p.inventory:
        with open(inv, encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                tid = (r.get("title_id") or "").upper()
                cat.add(tid, r.get("xbe_title_name"), os.path.basename(inv))
                for alt in (r.get("xemu_name") or "").split(" ~ "):
                    cat.add(tid, alt, os.path.basename(inv) + ":xemu_name")
    if os.path.isfile(p.targets):
        cur = None
        for line in open(p.targets, errors="replace"):
            m = re.match(r'\[titles\."([0-9A-Fa-f]{8})"\]', line)
            if m:
                cur = m.group(1)
                continue
            m = re.match(r'name\s*=\s*"(.*)"', line)
            if m and cur:
                cat.add(cur, m.group(1), "targets.toml")
    return cat


# ---------------------------------------------------------------- verdict gates

def recompute_gates(v):
    """Every gate's outcome from the verdict's VALUES, not from `failing`/`failures`.
    Returns (failing_all [gate names], detail dict)."""
    fails = []
    if v.get("void"):
        fails.append("void")
    if v.get("crash"):
        fails.append("crash")
    if v.get("hang"):
        fails.append("hang")
    rg = v.get("reached_gameplay")
    if rg is not True:
        fails.append("reached_gameplay")
    need = v.get("confirmation_need_s") or 600.0
    gs = v.get("gameplay_s")
    if rg is True and gs is not None and gs < need:
        fails.append("duration")
    tl = v.get("timeline") if isinstance(v.get("timeline"), dict) else None
    ps = tl.get("play_share") if tl else None
    if tl and rg is True and not v.get("void") and v.get("pass_kind", "confirmation") == "confirmation" \
            and (ps is None or ps < PLAY_SHARE_MIN):
        fails.append("menu_time")
    fos = v.get("fps_ok_share")
    if fos is None:
        if rg is True and not v.get("void"):
            fails.append("fps")
    elif fos < FPS_SHARE_MIN:
        fails.append("fps")
    if rg is True and v.get("audio_measured") is False:
        fails.append("audio")
    elif v.get("audio_starve_share") is not None and v["audio_starve_share"] > AUDIO_MAX:
        fails.append("audio")
    hitch = None
    if rg is True and not v.get("void") and isinstance(v.get("hitches"), dict):
        try:
            import hitch_report
            hf, hitch = hitch_report.hitch_fail(v["hitches"], v.get("hitch_allowance"))
            if hf:
                fails.append("hitch")
            for fn, gate, key in (("static_window_fail", "static", "static_window"),
                                  ("static_window_unmeasured", "window_unmeasured", "static_window"),
                                  ("position_fail", "position", "position")):
                if isinstance(v.get(key), dict):
                    bad, _ = getattr(hitch_report, fn)(v[key])
                    if bad:
                        fails.append(gate)
        except Exception as e:   # hitch_report unimportable: say so, never pass silently
            fails.append("hitch_unreadable")
            hitch = "hitch_report: %s" % e
    detail = dict(fps_ok_share=fos, fps_window_median=v.get("fps_window_median"),
                  play_share=ps, play_s=(tl or {}).get("play_s"),
                  hitch=(v.get("hitches") or {}).get("worst_ms") if isinstance(v.get("hitches"), dict) else None,
                  crash=bool(v.get("crash")), hang=bool(v.get("hang")), void=v.get("void"))
    return fails, detail


# ---------------------------------------------------------------- runs

class Run:
    __slots__ = ("tid", "name", "where", "t", "verdict", "gates", "detail", "build", "source", "resolved_by", "device")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def _run_dirs(base):
    """Every directory under a runs root that holds a result.json or verdict.json,
    excluding `provisional/` (superseded by its parent's final verdict) and `claim/`."""
    out = []
    for pat in ("*/", "*/*/"):
        for d in glob.glob(os.path.join(base, pat)):
            d = d.rstrip("/")
            leaf = os.path.basename(d)
            if leaf in ("provisional", "claim", "frames", "route-frames", "hang"):
                continue
            if os.path.isfile(os.path.join(d, "result.json")) or os.path.isfile(os.path.join(d, "verdict.json")):
                out.append(d)
    return sorted(set(out))


def collect_runs(p, cat, unresolved):
    runs = []
    for d in _run_dirs(p.pf_runs):
        req = load_json(os.path.join(d, "request.json")) or {}
        res = load_json(os.path.join(d, "result.json")) or {}
        v = load_json(os.path.join(d, "verdict.json"))
        name = res.get("name") or req.get("title") or (v or {}).get("title")
        tid = res.get("title_id") or req.get("title_id") or (v or {}).get("title_id")
        how = "title_id in result/request.json"
        if not tid:
            tid, how = cat.resolve(res.get("iso") or req.get("iso") or "")
            if not tid:
                tid, how = cat.resolve(name or "")
        rel = os.path.relpath(d, p.root)
        if not tid:
            unresolved.append((rel, name, how))
            continue
        t = parse_utc((v or {}).get("judged_utc")) or parse_pdt(res.get("started")) or \
            dt.datetime.fromtimestamp(os.path.getmtime(d), dt.timezone.utc)
        gates, detail = recompute_gates(v) if v else (None, None)
        runs.append(Run(tid=cat.canonical(tid), name=name, where=rel, t=t, verdict=v, gates=gates, detail=detail,
                        build=(v or {}).get("apk_sha") or (v or {}).get("ref") or "", source="pathfind",
                        resolved_by=how, device=res.get("device") or req.get("device") or ""))
    for vp in glob.glob(os.path.join(p.results, "*", "verdict.json")):
        d = os.path.dirname(vp)
        req = load_json(os.path.join(d, "request.json")) or {}
        res = load_json(os.path.join(d, "result.json")) or {}
        v = load_json(vp) or {}
        title = req.get("title") or res.get("title") or v.get("title") or ""
        if not title:
            continue          # a pgraph suite run, not a title
        # NOT hdd.title_id: it names the disk's last title (Tron's run reads GTA's 54540082).
        tid, how = cat.resolve(title)
        rel = os.path.relpath(d, p.root)
        if not tid:
            unresolved.append((rel, title, how))
            continue
        t = parse_utc(v.get("judged_utc")) or dt.datetime.fromtimestamp(os.path.getmtime(vp), dt.timezone.utc)
        gates, detail = recompute_gates(v)
        runs.append(Run(tid=tid, name=title, where=rel, t=t, verdict=v, gates=gates, detail=detail,
                        build="%s/%s" % (req.get("ref") or v.get("ref") or "", res.get("apk_sha") or v.get("apk_sha") or ""),
                        source="dispatcher", resolved_by=how, device=req.get("device") or v.get("device") or ""))
    return runs


# ---------------------------------------------------------------- holds

HOLD_COLS = ["id", "kind", "match", "classes", "since", "by", "quote", "release", "issues", "released", "source", "value"]
HOLD_KINDS = ("exclude", "pending", "crash", "below_bar", "order", "window", "device", "build_floor")
TITLE_HOLD_KINDS = ("exclude", "pending", "crash", "below_bar")


def load_holds(p):
    """pm/owner-holds.tsv rows (see the seed's header for the schema), plus
    host-tools/blocked-titles.txt as `exclude` rows."""
    rows = []
    for r in read_tsv(p.holds):
        if r.get("id") and r.get("kind") in HOLD_KINDS:
            rows.append(r)
    for row in read_tsv(p.blocked, header=False):
        if row and row[0].strip():
            rows.append(dict(id="blocked:" + row[0].strip(), kind="exclude", match=row[0].strip(),
                             classes="ALL", since="", by="owner", quote=(row[1] if len(row) > 1 else ""),
                             release="the named issues close, or the owner's word", issues="",
                             released="", source=os.path.relpath(p.blocked, p.root)))
    return rows


def hold_matches(h, tid, name, cat=None):
    m = (h.get("match") or "").strip()
    if not m:
        return False
    if m == "*":
        return True
    if m.startswith("device:"):
        return False
    if m.startswith("genre:"):
        rx = GENRES.get(m[len("genre:"):])
        return bool(rx and rx.search(" " + (name or "").replace("_", " ").lower() + " "))
    canon = cat.canonical if cat else (lambda x: x.strip().upper())
    return any(canon(x.strip()) == tid for x in m.split(",") if x.strip())


# pathfind.py e383da4992's football rule, applied to the catalog name.
GENRES = {"football": re.compile(r"\b(nfl|madden|football|gridiron)\b")}


def hold_active(h, open_issues):
    """A hold is active until `released` is filled (lane.local records the owner's
    word), or -- when its release is 'issues close' -- every named issue is closed.
    An issue state that could not be read keeps the hold active."""
    if (h.get("released") or "").strip():
        return False
    iss = [int(x) for x in re.findall(r"\d+", h.get("issues") or "")]
    if iss and "issues close" in (h.get("release") or "") and open_issues is not None:
        return any(i in open_issues for i in iss)
    return True


def forge_open_issues(p, use_forge=True, url=FORGE_URL):
    """{number: title} of the local forge's open issues (pull requests excluded), read
    over its HTTP API with W/forge/tokens/jobs.token; None if anything is unreadable
    (no token, refused, a bad page). Never shells out to `gh`: GitHub is not contacted,
    and the forge is reached only at `url`."""
    if not use_forge:
        return None
    try:
        tok = open(p.forge_token).read().strip()
    except OSError:
        return None
    out = {}
    try:
        for page in range(1, 201):
            q = urllib.request.Request("%s/api/v1/repos/%s/issues?state=open&type=issues&limit=50&page=%d"
                                       % (url, FORGE_REPO, page))
            q.add_header("Authorization", "token " + tok)
            with urllib.request.urlopen(q, timeout=30) as r:
                items = json.load(r)
            if not items:
                return out
            for x in items:
                if x.get("pull_request") is None:
                    out[int(x["number"])] = x.get("title") or ""
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
        return None
    return None             # 200 pages and no empty one: not a listing to trust


# ---------------------------------------------------------------- the build

def staged_map(p, cat):
    st = {}
    for lf in sorted(glob.glob(os.path.join(p.titlepush, "listing-*.txt"))):
        dev = os.path.basename(lf)[len("listing-"):-len(".txt")]
        for line in open(lf, errors="replace"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tid, _ = cat.resolve(line)
            if tid:
                st.setdefault(tid, set()).add(dev)
    for f in glob.glob(os.path.join(p.pm, "*-100?.done")):
        for line in open(f, errors="replace"):
            tok = line.split()
            if tok and ("pushed" in tok or line.count(".iso")):
                tid, _ = cat.resolve(tok[0])
                if tid:
                    st.setdefault(tid, set()).add("nova:" + os.path.basename(f))
    return st


def input_sequences(p, cat):
    """{tid: 'path:<TID>@<sha12>'} for a recorded, complete path that reached gameplay."""
    out = {}
    for f in glob.glob(os.path.join(p.pf_paths, "*.json")):
        j = load_json(f) or {}
        tid = (j.get("title_id") or os.path.basename(f)[:-5]).upper()
        if j.get("complete") and j.get("result") == "gameplay":
            sha = hashlib.sha256(open(f, "rb").read()).hexdigest()[:12]
            out[cat.canonical(tid)] = "path:%s@%s" % (tid, sha)
    return out


FIX_COLS = ["title_id", "gate", "fix_commit", "set_by", "date", "why"]


def load_title_fixes(p):
    """pm/title-fixes.tsv rows: lane.local's record that a commit answers a named failed
    gate of a title. Whether a row counts is dispatch_gate._answering_fix's decision."""
    return [r for r in read_tsv(p.fixes) if (r.get("title_id") or "").strip()]


def fix_commits(p, cat):
    """title_id -> 'sha(gate),...' from pm/title-fixes.tsv, for the fix_commit column."""
    out = {}
    for r in load_title_fixes(p):
        tid = r["title_id"].strip().upper()
        if TID_RE.match(tid) and (r.get("fix_commit") or "").strip():
            out.setdefault(cat.canonical(tid), []).append(
                "%s(%s)" % (r["fix_commit"].strip(), (r.get("gate") or "").strip()))
    return {k: ",".join(v) for k, v in out.items()}


def build(p, now=None, use_forge=True, forge_url=FORGE_URL):
    now = now or dt.datetime.now(dt.timezone.utc)
    today_pt = now.astimezone(PT).date()
    cat = build_catalog(p)
    unresolved = []
    notes = {}

    ledger = {}
    for r in read_tsv(p.ledger):
        tid = (r.get("title_id") or "").strip().upper()
        how = "title_id column"
        if not TID_RE.match(tid):
            tid, how = cat.resolve(r.get("title") or "")
        if not tid:
            unresolved.append(("pm/playable-accepted.tsv", r.get("title"), how))
            continue
        tid = cat.canonical(tid)
        ledger[tid] = r
        cat.add(tid, r.get("title"), "playable-accepted.tsv")

    runs = collect_runs(p, cat, unresolved)
    by_tid = {}
    for r in runs:
        by_tid.setdefault(r.tid, []).append(r)
        cat.names.setdefault(r.tid, r.name)

    intake = {}
    for src in (p.intake, p.pool):
        for r in read_tsv(src):
            tid = (r.get("title_id") or "").upper()
            if not TID_RE.match(tid):
                tid, how = cat.resolve(r.get("title") or "")
                if not tid:
                    unresolved.append((os.path.relpath(src, p.root), r.get("title"), how))
                    continue
            tid = cat.canonical(tid)
            intake.setdefault(tid, []).append(dict(r, _src=os.path.basename(src), _t=parse_utc(r.get("utc"))))

    holds = load_holds(p)
    open_issues = forge_open_issues(p, use_forge, forge_url)
    staged = staged_map(p, cat)
    for r in runs:       # a run found the ISO on that device (the 10-04 listings predate later pushes)
        if r.device in ("nova", "thor"):
            staged.setdefault(r.tid, set()).add(r.device + ":run")
    seqs = input_sequences(p, cat)
    fixes = fix_commits(p, cat)

    tids = set(cat.names) | set(ledger) | set(by_tid) | set(intake)
    rows = []
    for tid in sorted(tids):
        name = (ledger.get(tid) or {}).get("title") or cat.names.get(tid) or ""
        rs = sorted(by_tid.get(tid, []), key=lambda r: r.t)
        judged = [r for r in rs if r.verdict]
        scored = [r for r in judged if r.detail["fps_ok_share"] is not None and not r.detail["void"]]
        latest = scored[-1] if scored else (judged[-1] if judged else None)
        last_run = rs[-1] if rs else None
        my_holds = [h for h in holds if hold_matches(h, tid, name, cat) and h["kind"] in TITLE_HOLD_KINDS]
        active = [h for h in my_holds if hold_active(h, set(open_issues) if open_issues is not None else None)]
        crash_rows = [x for x in intake.get(tid, []) if x.get("class") in ("crash", "hang")]
        last_judged = judged[-1] if judged else None

        status, rule = None, None
        if tid in ledger:
            status, rule = "PLAYABLE", "in pm/playable-accepted.tsv (%s)" % ledger[tid].get("date_pdt", "")
        elif any(h["kind"] == "exclude" for h in active):
            h = next(h for h in active if h["kind"] == "exclude")
            status, rule = "EXCLUDED", "owner hold %s (%s)" % (h["id"], h.get("source", ""))
        elif any(h["kind"] == "pending" for h in active):
            h = next(h for h in active if h["kind"] == "pending")
            status, rule = "PENDING_OWNER", "owner ruling pending: hold %s" % h["id"]
        elif any(h["kind"] == "crash" for h in active):
            h = next(h for h in active if h["kind"] == "crash")
            status, rule = "CRASH_OR_HANG", "hold %s (issues %s open)" % (h["id"], h.get("issues"))
        elif last_judged and (last_judged.detail["crash"] or last_judged.detail["hang"]):
            status, rule = "CRASH_OR_HANG", "latest run %s: %s" % (
                last_judged.where, "crash" if last_judged.detail["crash"] else "hang")
        elif crash_rows and (not judged or (crash_rows[-1]["_t"] and crash_rows[-1]["_t"] > judged[-1].t)):
            status, rule = "CRASH_OR_HANG", "%s %s row %s (no later verdict)" % (
                crash_rows[-1]["_src"], crash_rows[-1]["class"], crash_rows[-1].get("utc"))
        elif latest and latest in scored and any(g in latest.gates for g in PERF_GATES):
            status, rule = "BELOW_BAR", "latest scored verdict %s fails %s" % (
                latest.where, "+".join(g for g in latest.gates if g in PERF_GATES))
        elif any(h["kind"] == "below_bar" for h in active):
            h = next(h for h in active if h["kind"] == "below_bar")
            status, rule = "BELOW_BAR", "hold %s" % h["id"]
        elif latest and latest in scored:
            status, rule = "FAILED_HARNESS", ("latest scored verdict %s fails %s (no perf gate)" % (
                latest.where, "+".join(latest.gates)) if latest.gates else
                "latest scored verdict %s is a harness PASS not in the ledger (frame review owed or refused)"
                % latest.where)
        elif judged and any(r.detail["void"] for r in judged):
            status, rule = "VOID", "every verdict is void or unscored; latest %s" % judged[-1].where
        elif rs or intake.get(tid):
            status, rule = "FAILED_HARNESS", "ran (%d run dir(s), %d intake row(s)) but no scored window" % (
                len(rs), len(intake.get(tid, [])))
        else:
            status, rule = "UNSCREENED", "no run, verdict or intake row on record"

        if not name and status == "UNSCREENED":
            continue
        g = latest.gates if latest else None
        d = latest.detail if latest else {}
        runs_today = sum(1 for r in rs if r.t.astimezone(PT).date() == today_pt)
        cause = ""
        if latest and latest.verdict:
            fl = latest.verdict.get("failures") or []
            cause = " | ".join(fl)[:400]
            if g is not None and len(fl) != len(g):
                notes.setdefault(tid, []).append(
                    "recomputed %d failing gate(s), verdict lists %d" % (len(g), len(fl)))
        rows.append(dict(
            title_id=tid, aliases=",".join(sorted(cat.aliases.get(tid, set()) - {tid})), name=name, status=status, status_rule=rule,
            ledger=(ledger[tid].get("date_pdt", "") if tid in ledger else ""),
            flicker=flicker_state(ledger.get(tid), active),
            holds=",".join(h["id"] for h in active),
            hold_detail=" || ".join("%s %s: %s; release: %s" % (h.get("since", ""), h.get("by", ""),
                                                                 h.get("quote", ""), h.get("release", ""))
                                     for h in active)[:600],
            latest_verdict=latest.where + "/verdict.json" if latest else "",
            verdict_utc=iso_z(latest.t) if latest else "",
            fps_ok_share=_f(d.get("fps_ok_share")), fps_window_median=_f(d.get("fps_window_median")),
            play_share=_f(d.get("play_share")), play_s=_f(d.get("play_s")), hitch=_f(d.get("hitch")),
            crash=_b(d.get("crash")), hang=_b(d.get("hang")), void=(d.get("void") or "") if d else "",
            failing_all="+".join(g) if g else "", cause=cause, fix_commit=fixes.get(tid, ""),
            last_run=last_run.where if last_run else "", last_run_utc=iso_z(last_run.t) if last_run else "",
            last_run_build=(last_run.build or "unrecorded") if last_run else "",
            runs_total=str(len(rs)), runs_today=str(runs_today),
            staged=",".join(sorted(staged.get(tid, []))), input_seq=seqs.get(tid, ""),
            notes="; ".join(notes.get(tid, []))))
    return rows, unresolved, open_issues


def flicker_state(ledger_row, active_holds):
    """The owner's flicker check (owner-only, by eye): HOLD:<id> while an owner flicker hold
    is active; for a ledger row, what its evidence records -- CLEARED only on the words
    'flicker cleared by owner', UNCHECKED on 'flicker UNCHECKED', else unrecorded."""
    h = next((h for h in active_holds if "flicker" in h["id"]), None)
    if h:
        return "HOLD:" + h["id"]
    if not ledger_row:
        return ""
    ev = " ".join((ledger_row.get(k) or "") for k in ("result", "evidence"))
    if re.search(r"flicker cleared by owner", ev, re.I):
        return "CLEARED"
    if re.search(r"flicker UNCHECKED", ev):
        return "UNCHECKED"
    return "unrecorded"


def _f(x):
    return "" if x is None else ("%g" % x if isinstance(x, float) else str(x))


def _b(x):
    return "" if x is None else ("1" if x else "0")


def write(p, rows, out=None, now=None, open_issues=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    digest, n = sources_digest(p)
    out = out or p.registry
    tmp = out + ".tmp"
    with open(tmp, "w") as f:
        f.write("# title-registry v1 generated_utc=%s sources_digest=%s sources=%d forge=%s\n"
                % (iso_z(now), digest, n, "ok" if open_issues is not None else "unreadable"))
        f.write("# GENERATED by docs/testing/title_registry.py build -- never hand-edit; edit a source and rebuild\n")
        f.write("\t".join(COLUMNS) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c, "")).replace("\t", " ").replace("\n", " ") for c in COLUMNS) + "\n")
    os.replace(tmp, out)
    return out


def read_registry(path):
    """(header dict, {tid: row}) or (None, {}) if missing/unparseable."""
    if not os.path.isfile(path):
        return None, {}
    with open(path, encoding="utf-8", errors="replace") as f:
        first = f.readline()
        if not first.startswith("# title-registry v1 "):
            return None, {}
        hdr = dict(kv.split("=", 1) for kv in first[len("# title-registry v1 "):].split() if "=" in kv)
        rows = {}
        cols = None
        for line in f:
            if line.startswith("#"):
                continue
            cells = line.rstrip("\n").split("\t")
            if cols is None:
                cols = cells
                continue
            r = dict(zip(cols, cells))
            rows[r["title_id"]] = r
    return hdr, rows


def freshness(p, path=None, now=None):
    """(fresh: bool, why). Stale = missing, older than STALE_S, or sources moved."""
    path = path or p.registry
    hdr, rows = read_registry(path)
    if hdr is None:
        return False, "registry %s missing or not a generated registry" % path
    now = now or dt.datetime.now(dt.timezone.utc)
    t = parse_utc(hdr.get("generated_utc"))
    if t is None:
        return False, "registry has no generated_utc stamp"
    age = (now - t).total_seconds()
    if age > STALE_S:
        return False, "registry is %.0f min old (limit %d min)" % (age / 60, STALE_S // 60)
    digest, _ = sources_digest(p)
    if digest != hdr.get("sources_digest"):
        return False, "registry sources changed since it was built (digest %s, now %s)" % (
            hdr.get("sources_digest"), digest)
    return True, "registry built %s, %.0f s old, sources unchanged" % (hdr["generated_utc"], age)


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["build", "check", "show", "resolve"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--registry")
    ap.add_argument("--out")
    ap.add_argument("--no-forge", action="store_true")
    ap.add_argument("--status")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    p = Paths(a.root)
    if a.cmd == "build":
        rows, unresolved, oi = build(p, use_forge=not a.no_forge)
        out = write(p, rows, a.out, open_issues=oi)
        counts = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        print("wrote %s: %d rows; %s" % (out, len(rows), ", ".join("%s %d" % (s, counts.get(s, 0)) for s in STATUSES)))
        if oi is None:
            print("forge: open issues UNREADABLE -- every issue-released hold stays active")
        for where, name, why in unresolved:
            print("UNRESOLVED %s: %r -- %s" % (where, name, why))
        return 0
    if a.cmd == "check":
        ok, why = freshness(p, a.registry)
        print(("FRESH " if ok else "STALE ") + why)
        return 0 if ok else 3
    if a.cmd == "resolve":
        cat = build_catalog(p)
        tid, why = cat.resolve(a.arg or "")
        print("%s\t%s" % (tid or "-", why))
        return 0 if tid else 1
    hdr, rows = read_registry(a.registry or p.registry)
    if hdr is None:
        print("no registry at %s" % (a.registry or p.registry))
        return 3
    sel = [r for r in rows.values() if (a.all or (a.status and r["status"] == a.status)
                                        or (a.arg and r["title_id"] == a.arg.upper()))]
    for r in sel:
        if a.arg:
            for c in COLUMNS:
                print("%-18s %s" % (c, r.get(c, "")))
        else:
            print("\t".join([r["title_id"], r["status"], r["name"], r["fps_ok_share"], r["status_rule"]]))
    return 0 if sel else 1


if __name__ == "__main__":
    sys.exit(main())
