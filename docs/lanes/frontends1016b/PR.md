# frontends1016b: Pegasus tested, Daijisho integrated or written up (#433)

State: draft

Lane: frontends1016b            Issue: #433
Base: master @ beb9daa755d3a869768ce8232ac755b53e15a7c3
Files: docs/frontends/pegasus.md, docs/frontends/daijisho.md, docs/frontends/README.md, docs/frontends/images/pegasus-android-collection.png, docs/frontends/images/pegasus-launch-cold.png, docs/frontends/images/pegasus-launch-second.png, docs/lanes/frontends1016b/PR.md, docs/lanes/frontends1016b/NOTES.md
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

Daijisho work (integration attempts, then fallback instructions if none
land) is in progress — this PR will be updated as that lands.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
