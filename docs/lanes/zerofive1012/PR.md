# zerofive1012 (2): a returning route for Ghoulies, so the 0.5 release gate can be queued (#433)

State: ready

Lane: zerofive1012        Issue: #433
Base: master @ f6cd2bee82
Files: docs/lanes/zerofive1012/**, docs/testing/titles/routes/ghoulies.returning.route
Prediction: none: no arm (a route file; no emulator code)
Needs device: yes (one Nova soak, already run)    Needs NDK: no

The 0.5 release gate is a Ghoulies soak: median gfps over 90-240 s at or above 25. Ghoulies has a kept profile
(55758513a9e3) and only `ghoulies.route`, which declares `# state: first-run`, so request.sh refuses the gate's soak
under the profile gate (no repeat profile creation).

`ghoulies.returning.route` is `ghoulies.route` with `# state: returning`. The inputs are unchanged: the route's own
header documents the later-run path, where slot 1 already holds "My Game" and the same A presses open the Play screen,
start Chapter 1 and skip the storybook. Request with `--route ghoulies.returning`.

Verified on the Nova, 1-1791826297-lane.local-4125680 (480 s, master 755ac97c96, the kept profile): the route reached
the Grand Hallway with Cooper moving and Ghoulies on screen (route-frames/104011-moved2.png), and the 90-240 s
window's median gfps was 29.0 over 73 readings.

Release note: none
