# visitordocs1016: security policy, code of conduct, getting your Xbox files

State: draft

Lane: visitordocs1016          Issue: #433
Base: master @ fb6ebcff40
Files: SECURITY.md, CODE_OF_CONDUCT.md, docs/xbox-files.md, docs/lanes/visitordocs1016/PR.md
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

Three pages a visitor to the repository looks for, which it did not have
(owner 10-16: "needed if we're going to have visitors").

- `SECURITY.md`: how to report a vulnerability privately (GitHub's private
  vulnerability reporting, with an issue asking for a contact as the
  fallback), what counts as a security problem in an emulator (reaching
  outside the emulated Xbox or the chosen folders; the online features
  exposing the device), and which versions are supported (the latest
  release; not test builds). GitHub shows it on the Security tab.
- `CODE_OF_CONDUCT.md`: short rules, including no piracy, and how to report
  a comment (GitHub's "Report content", to the repository admins).
- `docs/xbox-files.md`: the four things setup asks for (MCPX boot ROM,
  flash ROM, hard disk image, games), what the app accepts for each, and
  what to do after setup (System Files, Export HDD Image and Export EEPROM,
  Recreate Hard Disk, Import Dashboard). It links xemu's guides for how to
  copy them from a console. Checked against the setup wizard and Settings
  screens in android/app (file types, ROM sizes, menu names).

Two GitHub settings make the reporting paths work: private vulnerability
reporting (Settings, Code security) and reported content (Settings,
Moderation options). Both are the owner's to switch on.

`host-tools/home_page.py` (live on the host) already lists SECURITY.md and
CODE_OF_CONDUCT.md as optional landing-page files, so they appear on
`home` at its next build after this fold. CODE_OF_CONDUCT.md links
docs/xbox-files.md, so the three land together.

Fold: root docs and docs/ only, so no selftest and no device run.

Release note (other): none -- docs only, no emulator/app code touched.
