# release052c: the 0.5.2 release page tells the story since v0.3.1, and the driver notice says handheld (#433)

State: ready

Lane: release052c            Issue: #433
Base: master @ 07b7b6d996
Files: README.md, CHANGELOG.md, docs/COMPATIBILITY.md, docs/gpu-driver.md, docs/releases/README.md, docs/releases/v0.4.0-j1.md, docs/releases/v0.4.1-j1.md, docs/releases/v0.5.0.md, docs/releases/v0.5.1.md, docs/releases/v0.5.2.md, docs/testing/nightly_build.sh, docs/testing/compat_page.py, docs/lanes/release052c/PR.md
Prediction: none: public text
Needs device: no    Needs NDK: no
Selftest: 10-arms-list 55-localtime 86-nightly-notes 86-release-build 87-nightly-trunk 88-nightly-sign 99-release-note-line -- the change edits one echo line in nightly_build.sh and one string in compat_page.py; these are the fragments that run or read nightly_build.sh (10-arms-list only writes the tick log that 55-localtime reads).

Release note (none): public docs only.

`docs/releases/v0.5.2.md` now covers the release and everything since the official v0.3.1: title-specific fixes and
frame-rate changes for each version, the X1 BOX fixes carried into 0.5.1, and the install requirements. The Crimson
Skies intro-skip fix (shipped in v0.4.0-j1) is added to that version's notes and the CHANGELOG, and Mortal Kombat:
Shaolin Monks to the 0.5.2 CHANGELOG entry. The GPU driver notice and gpu-driver.md say "handheld's own driver"
instead of "phone's own driver" in every file that carries them.
