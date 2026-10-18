# frontends1016c: stock launcher tested on the Nova, Daijisho page rewritten for users (#433)

State: ready

Lane: frontends1016c            Issue: #433
Base: master @ b12a31303301a5c936aa6a25ee6667196f961615
Files: docs/frontends/daijisho.md, docs/frontends/stock-launcher.md, docs/frontends/README.md, docs/frontends/images/retroid-app-list.png, docs/releases/v0.5.1.md, docs/lanes/frontends1016c/PR.md, docs/lanes/frontends1016c/NOTES.md
Prediction: none: docs-only
Needs device: no (the Nova test was run by hand before this branch)

The Retroid launcher on the Nova lists "hakuX CE" in its Apps screen and
launches it (cold start after a force-stop, a game at 59 fps, pause menu,
Exit). `stock-launcher.md` gets a real Retroid section and the "not yet
tested" wording is gone from it, from `docs/frontends/README.md` and from
`docs/releases/v0.5.1.md`. The Nova's default home app was switched to the
Retroid launcher for the test and restored to ES-DE.

`daijisho.md` is rewritten from a test report into "add hakuX CE as an app"
steps for a player. The platform-editor investigation and the DocumentsUI
finding moved to `docs/lanes/frontends1016c/NOTES.md`, together with the
finding that the Stop hook force-stops hakuX and sleeps a device with no
non-battery hold.

Release note (none): docs-only.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
