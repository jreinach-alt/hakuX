# thorbottom800: full-screen game on the Thor's bottom screen (#800)

State: draft

Lane: thorbottom800            Issue: #800
Base: master @ 5e4196fefd
Files: docs/lanes/thorbottom800/NOTES.md, docs/lanes/thorbottom800/PR.md, docs/lanes/thorbottom800/OUTBOX.md, android/app/src/main/java/org/libsdl/app/SDLSurface.java, android/app/src/main/java/org/libsdl/app/SDLActivity.java
Prediction: none: no arm (display sizing on a secondary display; no golden covers it)
Needs device: yes    Needs NDK: yes

In progress: reproduce on the Thor's display 4, find the stage that sizes the surface from the wrong display, bisect, fix.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
