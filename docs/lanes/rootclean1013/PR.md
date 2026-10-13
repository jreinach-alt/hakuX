# rootclean1013: remove unused upstream files from the repository root (#433)

State: ready

Lane: rootclean1013            Issue: #433
Base: master @ 3c2338eb2b
Files: README.rst, ubuntu-win64-cross/**, .github/workflows/build-xemu-win64-toolchain.yml, docs/ORCHESTRATION-AS-BUILT.md, docs/lanes/rootclean1013/**
Prediction: none (no built file changes)
Needs device: no    Needs NDK: no

## What changed

Three upstream leftovers are deleted. hakuX builds none of them:

- `README.rst` is QEMU's top-level readme. It sat next to `README.md` and showed
  as a second readme at the repository root. Nothing hakuX builds reads it.
- `ubuntu-win64-cross/` (two Dockerfiles, six MXE `.mk` recipes) built xemu's
  Windows cross-compiler image.
- `.github/workflows/build-xemu-win64-toolchain.yml` was the only consumer of
  that directory. It built the image and pushed it to xemu's container
  registry. It has been `workflow_dispatch`-only since localforge, and Actions
  is off.

`docs/ORCHESTRATION-AS-BUILT.md` section 9 describes that workflow's path
trigger. A one-line note there now says the workflow is gone.

## Checked, left alone

- `build.sh`'s `-p win64-cross` mode still works the same. It takes the
  toolchain from `$CROSSPREFIX` and `$CROSSAR` and never reads
  `ubuntu-win64-cross/`. Anyone who wants that build brings their own MXE
  toolchain.
- `qemu.nsi`, QEMU's NSIS installer script, lists `README.rst` in its file and
  uninstall sections. hakuX does not build the NSIS installer (Windows
  packaging is `build.sh`'s `package_windows` / `package_wincross`), so it is
  left as upstream wrote it.
- `docs/lanes/selfdeps/mirror_sources.py` and `docs/lanes/selfdeps/NOTES.md` name
  `ubuntu-win64-cross:*` files as the consumers of some mirrored pins (MXE,
  SDL2, libressl, curl, glib and others). Those names are labels, and no live
  tool runs the mirror script. They stay as the selfdeps record of what was
  mirrored and why.
- The files under `python/` and `docs/` named `README.rst` are separate, and
  untouched.
- The dated handoffs and lane notes that mention the workflow are historical
  and stay as written.

## Proof

```
git grep -n -e ubuntu-win64-cross -e build-xemu-win64-toolchain -- \
  ':!docs/lanes' ':!docs/investigations' ':!docs/ORCHESTRATION-AS-BUILT.md'
```

prints only the dated `docs/handoff/2026-09-18-fold-list.md`. No build file,
script or workflow names the removed paths. The only remaining reference to
the root `README.rst` is in `qemu.nsi`.

Release note (none): repository cleanup.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
