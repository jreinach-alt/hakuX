# gta3fps1017: GTA III fps, R2/R3 copy-count remedies from an on-foot census, with R1 (#1049)

State: draft

Lane: gta3fps1017            Issue: #1049 #433
Base: master @ 6295705f20
Files: docs/lanes/gta3fps1017/NOTES.md, docs/lanes/gta3fps1017/PR.md, docs/testing/predictions/gta3fps1017-*, hw/xbox/nv2a/pgraph/vk/texture.c
Prediction: none yet (registered before any device run that claims pixels)
Needs device: yes    Needs NDK: yes
Selftest: none -- the change is hw/xbox/nv2a/pgraph/vk/texture.c and this lane's docs; no selftest.d fragment reads either

Release note (performance): pending the census and the pick.

Work in progress. R1 (no #474 drain ahead of a plain colour surface-to-texture copy, b7d7243392 + c6ca5296fd) and the
perflog copy census (bd2bf354bb's texture.c hunk) are cherry-picked from lane/gta3drive1017. Next: the desktop suites
with R1 on and off, then the census on foot on the Nova (on the owner's hold now).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
