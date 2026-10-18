# frontends1016b: Pegasus tested, Daijisho integrated via its Apps tab (#433)

State: ready

Lane: frontends1016b            Issue: #433
Base: master @ 8cd408688e5eb0cb129f9439d941326dcf704cac
Files: docs/frontends/pegasus.md, docs/frontends/daijisho.md, docs/frontends/README.md, docs/frontends/images/pegasus-android-collection.png, docs/frontends/images/pegasus-launch-cold.png, docs/frontends/images/pegasus-launch-second.png, docs/frontends/images/daijisho-apps-tab.png, docs/frontends/images/daijisho-documentsui-glitch.png, docs/frontends/images/daijisho-launch-cold.png, docs/frontends/images/daijisho-launch-second.png, docs/lanes/frontends1016b/PR.md, docs/lanes/frontends1016b/NOTES.md
Prediction: none: analysis-only
Needs device: yes (Thor, bdc158a5, by hand)

Pegasus is installed on the Thor (`alpha16-82-gc3462e68`, versionCode 1945)
and wires up through its built-in Android collection, which lists hakuX
alongside every other installed app. Launched the game twice from Pegasus's
own UI (cold, then after `am force-stop`), both confirmed via
`dumpsys activity recents`/`activities` and screenshotted. `pegasus.md`
rewritten in the house style, "blocked" wording removed, with one finding
recorded: a one-time transient DocumentsUI-recovery glitch on the very first
post-setup-wizard launch, self-resolved on retry, not reproducible.

Daijisho is now **integrated**, not just written up: it has its own Apps
tab (a generic installed-app list, the same mechanism as Pegasus's Android
collection), which lists hakuX CE directly — no custom Platform entry or
"Default player" field needed, so the first lane's keyboard-hidden
autocomplete blocker (`docs/lanes/frontends1016/NOTES.md`) never had to be
solved. Launched the game twice from Daijisho's own UI the same way as
Pegasus, both confirmed and screenshotted. `daijisho.md` rewritten in the
house style, "blocked" wording and the NEED: removed; the first lane's
ruled-out Platform-editor investigation is kept under "What was tried and
ruled out" for whoever wants a fuller platform-card integration later. One
finding recorded, shared with Pegasus: across four force-stop/relaunch
attempts through both frontends, two landed cleanly on the Game Library and
two instead opened Android's DocumentsUI picker — confirmed via
`dumpsys activity recents`/`activities` to be hakuX's own `LauncherActivity`
re-running a games-folder recovery flow, not a frontend problem; always
self-resolved by backing out and relaunching. No NEED: for either frontend.

`docs/frontends/README.md`'s status table updated: all four frontends now
read "Tested on the Thor" (Daijisho and Pegasus changed from their prior
"blocked" status).

Release note (none): docs-only lane, no emulator/app code touched.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
