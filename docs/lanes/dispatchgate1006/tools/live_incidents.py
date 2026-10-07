#!/usr/bin/env python3
"""Replay today's incident requests through admit() against the HOST's real
records. Read-only: the registry is built into a scratch file (never the host's
pm/title-registry.tsv) and no dispatch-log row is written.

    python3 docs/lanes/dispatchgate1006/tools/live_incidents.py [--no-forge]
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "testing"))
import dispatch_gate as G       # noqa: E402
import title_registry as TR     # noqa: E402

scratch = os.path.join(tempfile.mkdtemp(prefix="live-incidents-"), "title-registry.tsv")
ctx = G.Ctx(registry=scratch)
host_reg = ctx.p.registry
before = os.stat(host_reg).st_mtime if os.path.exists(host_reg) else None
rows, unresolved, oi = TR.build(ctx.p, use_forge="--no-forge" not in sys.argv)
TR.write(ctx.p, rows, scratch, open_issues=oi)
hdr, reg = ctx.registry()
cat = TR.build_catalog(ctx.p)
RUNS = "wt/pathfind/docs/lanes/pathfind/runs/"
PLAN = os.path.join(ctx.p.pm, "plan-2026-10-06-replan.md")
print("scratch registry %s: %d rows, forge=%s" % (scratch, len(reg), hdr.get("forge")))


def ask(title, cls, **kw):
    tid, _ = cat.resolve(title)
    q = {"title": title, "class": cls, "device": "nova", "build": "6cef37f426", "seconds": 900,
         "because": ["fix:ab8788c38b"], "input_seq": (reg.get(tid) or {}).get("input_seq") or "discovery",
         "valid_end": "valid-verdict", "caller": "lane.pathfind", "via": "request"}
    q.update(kw)
    d = G.admit(ctx, q, write_log=False, shadow=True)
    print("%-6s %-26s %-17s %s" % ("ALLOW" if d.allow else "DENY", title[:26], cls,
                                   (d.reasons[0] if d.reasons else d.token)[:220]))
    for r in d.reasons[1:]:
        print("%52s+ %s" % ("", r[:200]))


ask("54430001", "PLAYABLE_ATTEMPT", because=["verdict:" + RUNS + "retro-doa3/verdict.json"])
ask("Dino Crisis 3", "PLAYABLE_ATTEMPT", because=["verdict:" + RUNS + "dino-crisis-3-hold/verdict.json"])
ask("4D53000F", "PLAYABLE_ATTEMPT")
ask("Strike Force Bowling", "PLAYABLE_ATTEMPT", plan=PLAN)
for t in ("Tron 2.0: Killer App", "5443000D", "4D530041", "4156002B", "NFL Blitz Pro", "NBA 2K3",
          "AMF Xtreme Bowling", "4541038A"):
    ask(t, "PLAYABLE_ATTEMPT")
print("\n-- the 18:10 review's defect: fix:6cef37f426 (the waitread1006 fold) cited as a fix")
for t in ("54430001", "56550039", "4541003E"):      # DOA3, Hulk Ultimate Destruction, LOTR ROTK
    ask(t, "PLAYABLE_ATTEMPT", because=["fix:6cef37f426"])
print()
ask("Blowout", "VALIDATION", valid_end="condition:reverse walk at the hangar corner",
    because=["run:" + RUNS + "blowout-1006"])
ask("Fight Club", "SCREEN", input_seq="discovery")
ask("Fight Club", "PLAYABLE_ATTEMPT")
ask("RalliSport Challenge", "OWNER_DIAGNOSTIC", order="owner-1006-1450-ralli",
    valid_end="condition:rival cars visible", because=["order:owner-1006-1450-ralli"])
print("\nregistry rows")
for tid in ("5655002F", "4D53000F", "54430001"):
    r = reg.get(cat.canonical(tid)) or {}
    print("  %s %-24s %-14s ledger=%-17s flicker=%-26s holds=%s" % (
        r.get("title_id"), r.get("name", "?")[:24], r.get("status"), r.get("ledger") or "-", r.get("flicker") or "-",
        r.get("holds") or "-"))
print("\nplan_check %s" % os.path.basename(PLAN))
prow, prej = G.plan_check(ctx, PLAN)
for r in prow:
    bad = [x["why"] for x in prej if x["row"] == r["row"]]
    print("  row %-3s %-9s %-17s %-26s %s" % (r["row"], r["tid"] or "-", r["cls"], r["title"][:26],
                                             ("REJECT " + bad[0][:150]) if bad else "ok"))
after = os.stat(host_reg).st_mtime if os.path.exists(host_reg) else None
print("\nhost registry %s untouched: %s" % (host_reg, before == after))
