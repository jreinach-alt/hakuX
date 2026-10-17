# bindpose1017: THPS4 and Max Payne 2 characters stuck in the bind pose (#1043)

State: draft

Lane: bindpose1017            Issue: #1043
Base: master @ 8d260f39fc
Files: docs/lanes/bindpose1017/PR.md, docs/lanes/bindpose1017/NOTES.md
Prediction: none: analysis-only (so far)
Needs device: yes    Needs NDK: no

Deep dive into the bind-pose regression in Tony Hawk's Pro Skater 4 (41560017) and Max Payne 2 (5454000C). The owner's
hand bisect makes the 10-13 fold 3c2338eb2b (the 0.5.1 A-commits) the first bad build. 4f0111232c is excluded by a
revert run.

Status: Step 0 is done (`NOTES.md`: the Already-tried table, the fold read against the mechanism, the hypothesis
table). By reading, no fold commit changes how vertex data, vertex constants or attribute values reach a draw on a
Vulkan 1.3 device. So the leading hypothesis is that the good anchor is not like-for-like. The anchor is a 10-13
dispatcher run (debug package, goldens HDD), while every bad result is on the owner's installs with shared app data.
The next discriminator is 8455537f10 built as debug2 and installed over the same data.

## Release interim

None yet.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
