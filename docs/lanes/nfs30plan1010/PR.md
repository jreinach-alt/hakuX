# lane.nfs30plan1010: what has to be reworked for NFS Most Wanted's race start to hold 30 fps -- analysis and remediation plan (#433, 0.5)

State: draft

Lane: nfs30plan1010          Issue: none (#433 umbrella; owner's escalation 10-10 ~09:10 PDT)
Base: master @ 07937793af
Files: docs/lanes/nfs30plan1010/PR.md, docs/lanes/nfs30plan1010/NOTES.md, docs/lanes/nfs30plan1010/PLAN.md, docs/lanes/nfs30plan1010/briefs/*, docs/lanes/nfs30plan1010/nfs-mw-quickrace.route, docs/lanes/nfs30plan1010/startread.py, docs/lanes/nfs30plan1010/WAITING
Prediction: none (telemetry)
Needs device: yes (Nova, used)    Needs NDK: no
Release note (none): analysis and plan

Analysis-only lane. Accounts for one heavy NFS Most Wanted race-start frame end to end (guest vCPU,
PFIFO, render/submit, GPU, present) with the countdown included, and writes PLAN.md: per subsystem,
what has to be reworked to fit ~2,000 draws in 33.3 ms, its measured cost on the critical path, the
ms it removes, P(lands), lane-days, accuracy risk, and the combination in order. First lanes drafted
under briefs/.

In progress: corpus read and architecture notes first; measurement runs on the Nova batched.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
