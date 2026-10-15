#!/usr/bin/env python3
"""prequeue.py <title name fragment or title_id> -- the prior-test-log check lane.local runs before any title is queued (owner 10-06).
Reads RAW records (ledger, every verdict.json, intake/pool, owner holds), then the generated registry as a cross-check.
Prints evidence and one line: BLOCK / REVIEW / CLEAR. A queue request is relayed only on CLEAR, or on REVIEW after the cited rows are read and answered."""
import csv, glob, json, os, sys, datetime
W = "/home/justin/hakux-work"
q = " ".join(sys.argv[1:]).strip().lower()
if not q:
    sys.exit("usage: prequeue.py <title or id>")
def rows(path, delim="\t"):
    try:
        return [r for r in csv.DictReader((l for l in open(path) if not l.startswith("#")), delimiter=delim)]
    except OSError:
        return []
def hit(r, *keys):
    return any(q in (r.get(k) or "").lower() for k in keys)
verd = []
NAMES = [r["name"].lower().replace(":", "").replace("'", "") for r in rows(W + "/pm/title-registry.tsv") if hit(r, "title_id", "name", "aliases")]
for p in glob.glob(W + "/wt/pathfind/docs/lanes/pathfind/runs/**/verdict.json", recursive=True) + glob.glob(W + "/wt/*/docs/lanes/*/runs/**/verdict.json", recursive=True):
    try:
        d = json.load(open(p))
    except Exception:
        continue
    slug = p.split("runs/")[-1].lower()
    if any(n and (n.replace(" ", "-") in slug or n.replace(" ", "") in slug) for n in NAMES) or q in str(d.get("title", "")).lower() or q in str(d.get("name", "")).lower() or q == str(d.get("title_id", "")).lower():
        verd.append((os.stat(p).st_mtime, p, d))
seen = {}
for v in sorted(verd):
    seen[(v[2].get("judged_utc"), v[2].get("fps_ok_share"), v[2].get("gameplay_s"), v[2].get("request_id"))] = v
verd = sorted(seen.values())
reg = [r for r in rows(W + "/pm/title-registry.tsv") if hit(r, "title_id", "name", "aliases")]
tid = {r["title_id"] for r in reg} | {d.get("title_id") for _, _, d in verd}
led = [r for r in rows(W + "/pm/playable-accepted.tsv") if hit(r, "title", "title_id")]
hold = [r for r in rows(W + "/pm/owner-holds.tsv") if q in (r.get("match") or "").lower() or any(t and t.lower() in (r.get("match") or "").lower() for t in tid) or q in (r.get("quote") or "").lower()]
intake = [r for f in ("failure-intake", "pathfind-pool") for r in rows(W + "/pm/%s.tsv" % f) if hit(r, "title", "title_id")]
block, review = [], []
print("== registry")
for r in reg:
    print("  %s %s status=%s (%s) runs_today=%s last_run=%s %s fix=%s" % (r["title_id"], r["name"], r["status"], r["status_rule"][:90], r["runs_today"], r["last_run_utc"], r["last_run_build"], r["fix_commit"] or "-"))
    if r["status"] in ("PLAYABLE", "EXCLUDED", "PENDING_OWNER", "CRASH_OR_HANG", "BELOW_BAR", "FAILED_HARNESS", "VOID"):
        (block if r["status"] in ("PLAYABLE", "EXCLUDED", "PENDING_OWNER", "CRASH_OR_HANG") else review).append("registry status " + r["status"])
print("== ledger (Playable already banked; the registry's own PLAYABLE status above already blocks on this -- #433)")
for r in led:
    print("  %s %s: %s" % (r["date_pdt"], r["title"], r["evidence"][:140]))
print("== owner holds / orders matching")
for r in hold:
    print("  %s [%s] %s: %s" % (r["id"], r["kind"], r["classes"], r["quote"][:140])); block.append("owner hold " + r["id"])
print("== the latest 4 of %d distinct verdicts on disk (oldest first;" % len(verd) + " ALL failure gates, not only the first)")
today = datetime.date.today().isoformat()
for mt, p, d in verd[-4:]:
    t = datetime.datetime.fromtimestamp(mt).strftime("%m-%d %H:%M")
    print("  %s %s pass=%s fps_ok=%s median=%s play=%ss hitches=%s crash=%s hang=%s void=%s ref=%s\n      failing=%s | %s" % (
        t, p.split("runs/")[1].rsplit("/verdict.json", 1)[0], d.get("pass"), d.get("fps_ok_share"), d.get("fps_window_median"), d.get("gameplay_s"),
        (d.get("hitches") or {}).get("n_after_warmup") if isinstance(d.get("hitches"), dict) else d.get("hitches"), bool(d.get("crash")), bool(d.get("hang")), d.get("void"), (d.get("ref") or "-")[:10],
        d.get("failing"), "; ".join(str(x)[:110] for x in (d.get("failures") or [])[:4])))
    if d.get("crash"): block.append("crash on record (" + t + ")")
    if d.get("hang"): block.append("hang on record (" + t + ")")
if verd and not any(d.get("pass") for _, _, d in verd):
    last = verd[-1][2]
    review.append("every verdict on disk is a FAIL; last: %s" % last.get("failing"))
    if last.get("fps_ok_share", 1) is not None and last.get("fps_ok_share", 1) < 0.9: block.append("last verdict missed the fps bar: telemetry and a fix, not a retest (owner 10-03)")
print("== intake / pool rows")
for r in intake:
    print("  %s %s %s -> %s: %s" % (r["utc"][:16], r["class"], r["handoff"], r["result"][:30], r["evidence"][:140]))
    if r["class"] in ("hang", "crash", "perf", "below-bar"): review.append("intake class " + r["class"])

import re, subprocess
print("== prose mentions (pathfind OUTBOX/NOTES, PM plans, lane.local log): up to 8 lines naming the title (pathfind OUTBOX/NOTES last); READ them, the structured records do not carry these")
names = sorted({n for n in NAMES if len(n) > 3} | ({q} if len(q) > 3 and not re.fullmatch(r"[0-9a-f]{8}", q) else set()))
files = [W + "/wt/pathfind/docs/lanes/pathfind/OUTBOX.md", W + "/wt/pathfind/docs/lanes/pathfind/NOTES.md", W + "/pm/lanelocal-log.md", W + "/briefs/pathfind.md"] + sorted(glob.glob(W + "/pm/plan-2026-10-0[3-9]-*.md"))[-4:]
ids = sorted({t.lower() for t in tid if t})
hits = []
for f in files:
    try:
        for n, l in enumerate(open(f, errors="replace"), 1):
            ll = l.lower()
            if any(x in ll for x in names + ids):
                hits.append((f.replace(W + "/", "")[-48:], n, l.strip()[:300]))
    except OSError:
        pass
hits.sort(key=lambda h: ("OUTBOX" in h[0] or "NOTES" in h[0]))
for f, n, l in hits[-8:]:
    print("  %s:%d: %s" % (f, n, l))
if hits:
    kw = re.compile(r"can.t.path|will not re-?queue|not re-?queue|do not|never(?![-_ ]?run)|crash|hang|fps|stuck|below|exclude|drop|blocked|refus|issue", re.I)
    if any(kw.search(l) for _, _, l in hits):
        review.append("prose mentions with failure/skip language (%d lines; last cited above)" % len(hits))
print()
for b in sorted(set(block)): print("BLOCK  ", b)
for b in sorted(set(review) - set(block)): print("REVIEW ", b)
print("RESULT: " + ("BLOCK" if block else "REVIEW" if review else "CLEAR (no record found)" if not (reg or verd or led or intake) else "CLEAR"))
sys.exit(2 if block else 1 if review else 0)
