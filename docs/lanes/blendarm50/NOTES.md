# lane.blendarm50 -- does 771c8eb4f1 flush move stack C on device?

Issue #50. In progress.

docs/lanes/swatchorder50/NOTES.md (PR #186) settled the mechanism offline:
stack C blit shows the render target DrawColorStack left at the same guest
address. Readings 1 and 2 are dead (9/1120 vs aliasing 1119/1120). This lane
does not re-open that. It asks the one thing that lane left open: whether the
landed flush 771c8eb4f1 actually moves the captures on device.

Status: setting up the arm.
