"""Run only the claimlive selftest leg (the selftest's setup, then the leg)."""
import sys
src = open("docs/testing/titles/pathfind_selftest.py").read()
head = src[:src.index('# happy: 2 black')]
pre = src[src.index('PREFIX = '):src.index('PLAY = ')]
ns = {"__file__": "/home/justin/hakux-work/wt/pathfind/docs/testing/titles/pathfind_selftest.py"}
exec(head + pre, ns)
pf = ns["pathfind"]
CLOCK = [1000.0]
pf.now = lambda: CLOCK[0]
pf.time.sleep = lambda s: CLOCK.__setitem__(0, CLOCK[0] + s)
GAME, run, check = ns["GAME"], ns["run"], ns["check"]
REF = {"gameplay": True, "responded": False, "why": "the probe did not move the scene"}
n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
bud = sys.argv[2] if len(sys.argv) > 2 else "0.25"
rc, res, steps, calls = run("claimlive", ns["PREFIX"] + [("game", 0)] * 400, [GAME, REF] + [GAME] * n,
                            ["--no-record", "--no-replay", "--hold-s", "200", "--budget-min", bud])
print("RES", res.get("result"), res.get("claim_budget_live"), res.get("reason"), len(steps), len(calls),
      "hold", bool(res.get("hold")))
check("claimlive", res.get("claim_budget_live") is True and res.get("result") == "gameplay"
      and res.get("hold") is not None, "leg")
print("FAILS", ns["fails"])
