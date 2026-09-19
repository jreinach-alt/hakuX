import json, os

print(open("/home/justin/hakux-work/logs/lane/index.tsv").read())
names = [
    "blit83.20260919T000056Z.json",
    "stencil99.20260919T000102Z.json",
    "tier81fix.20260919T000045Z.json",
    "toolsmith.20260919T000051Z.json",
]
keys = ("is_error", "subtype", "num_turns", "duration_ms", "session_id", "total_cost_usd")
for n in names:
    p = os.path.join("/home/justin/hakux-work/logs/lane", n)
    s = open(p).read()
    print("=====", n)
    try:
        j = json.loads(s)
        print(dict((k, j.get(k)) for k in keys))
        print(str(j.get("result", ""))[:1200])
    except Exception as e:
        print("not json:", e)
        print(s[:1200])
