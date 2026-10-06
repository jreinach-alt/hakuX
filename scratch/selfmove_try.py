"""Run only the claimlive + selfmove selftest legs (the selftest's setup, then those legs)."""
src = open("docs/testing/titles/pathfind_selftest.py").read()
head = src[:src.index('# happy: 2 black')]
pre = src[src.index('PREFIX = '):src.index('PLAY = ')]
legs = src[src.index('# claim (10-06 owner order)'):src.index('# replay abort (10-06 owner order)')]
ns = {"__file__": "/home/justin/hakux-work/wt/pathfind/docs/testing/titles/pathfind_selftest.py"}
exec(head + pre + "real_now, real_sleep = pathfind.now, pathfind.time.sleep\n" + legs, ns)
print("FAILS", ns["fails"])
