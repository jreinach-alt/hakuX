import sys, os, json, glob, re, collections, time
sys.path.insert(0, "/home/justin/hakuX/docs/testing/titles")
os.environ.setdefault("TITLESTATE_DIR", "/home/justin/hakux-work/dispatch/titlestate")
import titlestate as ts
RD = "/home/justin/hakuX/docs/testing/titles/routes"
R = "/home/justin/hakux-work/dispatch/results"
since = time.time() - 3*86400
runs = collections.defaultdict(list); notitle = collections.Counter(); route_tid = {}
for f in glob.glob(R + "/*/request.json"):
    try: r = json.load(open(f))
    except Exception: continue
    try: ep = int(os.path.basename(os.path.dirname(f)).split("-")[1])
    except ValueError: continue
    if not r.get("title"): continue
    rn = r.get("route_name") or ""
    tid = ts.tid_for_iso(r["title"]) or "?"
    if rn: route_tid.setdefault(rn, tid)
    if ep >= since:
        runs[rn or "(no route)"].append(tid)
rows = []
for p in sorted(glob.glob(RD + "/*.route")):
    name = os.path.basename(p)[:-6]; txt = open(p).read()
    st = ts.route_state(p)
    saved = "mark profile-saved" in txt; gp = bool(re.search(r"^mark gameplay", txt, re.M))
    tid = route_tid.get(name, "?")
    g = ts.golden(tid) if tid != "?" else None
    prof = "yes" if g and ts.save_dirs(ts.disk_tid(tid), g["save"]) else ("data-only" if g else "no")
    rows.append((name, st, tid, prof, "save" if saved else "", "gameplay" if gp else "", len(runs.get(name, []))))
print(f"{'route':38s} {'state':10s} {'tid':9s} {'golden':9s} {'save':5s} {'gp':8s} runs3d")
for r in rows: print(f"{r[0]:38s} {str(r[1]):10s} {r[2]:9s} {r[3]:9s} {r[4]:5s} {r[5]:8s} {r[6]}")
nr = runs.get("(no route)", [])
print("\nno-route title runs in 3 days:", len(nr), "titles:", len(set(nr)))
print("of which title has no profile golden:", sum(1 for t in nr if t == "?" or not (ts.golden(t) and ts.save_dirs(ts.disk_tid(t), ts.golden(t)["save"]))))
