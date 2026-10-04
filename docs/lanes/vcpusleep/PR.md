# lane.vcpusleep (#507): name what the vCPU sleeps on in Simpsons Hit & Run, and remove it

State: draft

Lane: vcpusleep            Issue: #507
Base: master @ 425ffe1ad1
Files: docs/lanes/vcpusleep/NOTES.md, docs/lanes/vcpusleep/OUTBOX.md, docs/lanes/vcpusleep/PR.md, docs/lanes/vcpusleep/WAITING, docs/lanes/vcpusleep/capture_simpsons_offcpu.sh
Prediction: none yet: R1 is a profile, not an arm; a fix registers before its arm
Needs device: yes (one host-run Nova capture, lane.local)    Needs NDK: no (until a fix)

R1 (vcpu60 rank 1): one off-CPU capture of the Simpsons vCPU thread in free
roam, which names the site of its 9.4 ms/frame sleep. State and numbers are in
`docs/lanes/vcpusleep/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
