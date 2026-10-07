#!/usr/bin/env python3
"""The dispatch gate's daily review: what reached a handheld without the gate,
what the gate refused, and what device time went to titles the records say
should not have run.

    dispatch_audit.py [--root W] [--hours 24] [--max-lines N]

Three sections, each from records on disk:

  UNGATED      every title run that started in the window with no gate token:
               a dispatcher soak whose request.json has no `gate_token`, or whose
               token has no ALLOW row in pm/dispatch-log.tsv; a pathfind held run
               (wt/pathfind/.../runs/*/result.json `started`) with no ALLOW or
               HOLD-GATED row for its title on its device in the 6 h before it.
  REFUSED      every DENY / SHADOW-DENY / HOLD-DENY / SHADOW-HOLD-UNGATED row of
               pm/dispatch-log.tsv in the window, with its reasons.
  WASTED       every Nova minute in the window spent on a title the registry now
               marks BELOW_BAR, EXCLUDED, PENDING_OWNER or CRASH_OR_HANG, unless the
               run was a gated TELEMETRY/VALIDATION/OWNER_DIAGNOSTIC dispatch.
               Minutes = verdict judged_utc - result started (claim + hold +
               judge), else result.json `minutes`, else the request's seconds.

The hourly report prints it as its DISPATCH GATE section
(host-tools/hourly_report.sh; patches/hourly_report.sh.patch in lane
dispatchgate1006). Exit 0 always: it is a report, not a gate.
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import title_registry as TR  # noqa: E402

FLAGGED = ("BELOW_BAR", "EXCLUDED", "PENDING_OWNER", "CRASH_OR_HANG")
REFUSALS = ("DENY", "SHADOW-DENY", "HOLD-DENY", "SHADOW-HOLD-UNGATED")
EXEMPT_CLASSES = ("TELEMETRY", "VALIDATION", "OWNER_DIAGNOSTIC")


def runs_in_window(p, cat, since):
    """[(t_start, minutes, device, tid, name, where, gate_token|None, source)]"""
    out = []
    for d in TR._run_dirs(p.pf_runs):
        res = TR.load_json(os.path.join(d, "result.json")) or {}
        req = TR.load_json(os.path.join(d, "request.json")) or {}
        v = TR.load_json(os.path.join(d, "verdict.json")) or {}
        t0 = TR.parse_pdt(res.get("started"))
        if not t0 or t0 < since:
            continue
        tid = res.get("title_id") or req.get("title_id")
        if not tid:
            tid, _ = cat.resolve(res.get("iso") or req.get("iso") or "")
        if not tid:
            tid, _ = cat.resolve(res.get("name") or req.get("title") or "")
        t1 = TR.parse_utc(v.get("judged_utc"))
        mins = (t1 - t0).total_seconds() / 60 if t1 and t1 > t0 else float(res.get("minutes") or 0)
        out.append((t0, mins, res.get("device") or req.get("device") or "", cat.canonical(tid) if tid else None,
                    res.get("name") or req.get("title") or "", os.path.relpath(d, p.root), None, "pathfind"))
    for rq_path in glob.glob(os.path.join(p.results, "*", "request.json")):
        rq = TR.load_json(rq_path) or {}
        if not rq.get("title"):
            continue
        res = TR.load_json(os.path.join(os.path.dirname(rq_path), "result.json")) or {}
        t0 = dt.datetime.fromtimestamp(os.path.getmtime(rq_path), dt.timezone.utc)
        if t0 < since:
            continue
        # the ISO it booted is the title; request.json's title_id has been stale (10-05 Tron: 54540082)
        tid, _ = cat.resolve(rq.get("title") or "")
        if not tid and rq.get("title_id"):
            tid, _ = cat.resolve(rq["title_id"])
        mins = float(res.get("seconds") or rq.get("seconds") or 0) / 60
        out.append((t0, mins, rq.get("device") or res.get("device_label") or "", tid, rq.get("title"),
                    os.path.relpath(os.path.dirname(rq_path), p.root), rq.get("gate_token"), "dispatcher"))
    return sorted(out, key=lambda r: r[0])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=TR.DEFAULT_ROOT)
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--max-lines", type=int, default=0, help="cap each section (0 = all)")
    ap.add_argument("--now", help="UTC ISO time to audit as of (tests)")
    ap.add_argument("--no-refresh", action="store_true", help="read the registry as it is, even if stale")
    a = ap.parse_args(argv)
    p = TR.Paths(a.root)
    now = TR.parse_utc(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(hours=a.hours)
    cat = TR.build_catalog(p)
    if not a.no_refresh and not TR.freshness(p, now=now)[0] and not a.now:
        rows, _, oi = TR.build(p)              # a report reads current statuses; the gate refreshes the same way
        TR.write(p, rows, open_issues=oi)
    hdr, reg = TR.read_registry(p.registry)
    log = TR.read_tsv(os.path.join(p.pm, "dispatch-log.tsv"))
    fresh, why = TR.freshness(p, now=now) if hdr else (False, "no registry")
    mode = "enforce" if (open(os.path.join(p.pm, "dispatch-gate.mode")).read().strip() == "enforce"
                         if os.path.isfile(os.path.join(p.pm, "dispatch-gate.mode")) else False) else "shadow"
    cap = (lambda xs: xs[-a.max_lines:] if a.max_lines else xs)

    print("  gate mode %s; registry %s (%s)" % (mode, (hdr or {}).get("generated_utc", "missing"),
                                                "fresh" if fresh else "STALE: " + why))
    allows = [r for r in log if r.get("decision") in ("ALLOW", "HOLD-GATED")]
    tokens = {r.get("token") for r in log if r.get("decision") == "ALLOW"}
    runs = runs_in_window(p, cat, since)

    ungated = []
    for t0, mins, dev, tid, name, where, tok, src in runs:
        if src == "dispatcher":
            if tok and tok in tokens:
                continue
            why_u = "request has no gate_token" if not tok else "gate_token has no ALLOW row"
        else:
            hit = [r for r in allows if r.get("title_id") == tid and r.get("device") == dev
                   and TR.parse_utc(r.get("utc")) and dt.timedelta(0) <= t0 - TR.parse_utc(r["utc"]) <= dt.timedelta(hours=6)]
            if hit:
                continue
            why_u = "no ALLOW/HOLD-GATED row for %s on %s in the 6 h before it" % (tid or "?", dev or "?")
        ungated.append("  %s %-5s %-9s %-34s %5.1f min  %s (%s)" % (
            t0.astimezone(TR.PT).strftime("%m-%d %H:%M"), dev, tid or "?", (name or "")[:34], mins, why_u, where))
    print("--- UNGATED: %d title run(s) in the last %g h reached a handheld without a gate token" % (len(ungated), a.hours))
    for line in cap(ungated):
        print(line)

    refused = [r for r in log if r.get("decision") in REFUSALS and (TR.parse_utc(r.get("utc")) or now) >= since]
    print("--- REFUSED: %d decision(s) the gate refused or would have refused (%s mode)" % (len(refused), mode))
    for r in cap(refused):
        print("  %s %-19s %-9s %-16s %-5s by %s: %s" % (
            (TR.parse_utc(r["utc"]) or now).astimezone(TR.PT).strftime("%m-%d %H:%M"), r.get("decision"),
            r.get("title_id"), r.get("class"), r.get("device"), r.get("caller"), (r.get("reasons") or "")[:220]))

    wasted, total, known_total = [], 0.0, 0.0
    gated_ok = {(r.get("title_id"), r.get("device")) for r in log
                if r.get("decision") == "ALLOW" and r.get("class") in EXEMPT_CLASSES}
    holds = {h["id"]: h for h in TR.load_holds(p)}
    for t0, mins, dev, tid, name, where, tok, src in runs:
        row = reg.get(tid or "")
        if dev != "nova" or not row or row.get("status") not in FLAGGED or (tid, dev) in gated_ok:
            continue
        # KNOWN: the record that flags it existed before the run started (its latest scored
        # verdict, or the owner hold's `since`); otherwise this run is what found it.
        vt = TR.parse_utc(row.get("verdict_utc"))
        hs = [TR.parse_pdt(holds[h].get("since")) for h in (row.get("holds") or "").split(",") if h in holds]
        known = (row["status"] in ("BELOW_BAR",) and vt and vt < t0) or any(x and x < t0 for x in hs)
        total += mins
        known_total += mins if known else 0
        wasted.append("  %s %-5s %-9s %-34s %5.1f min  now %s (%s) -- %s" % (
            t0.astimezone(TR.PT).strftime("%m-%d %H:%M"), "KNOWN" if known else "found", tid, (name or "")[:34],
            mins, row["status"], (row.get("status_rule") or "")[:90], where))
    print("--- WASTED: %.1f Nova min in the last %g h on titles the registry now marks %s; %.1f of them KNOWN "
          "(flagged by a verdict or owner hold before the run started)" % (total, a.hours, "/".join(FLAGGED), known_total))
    for line in cap(wasted):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
