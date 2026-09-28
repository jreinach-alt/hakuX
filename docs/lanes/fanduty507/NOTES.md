# lane.fanduty507 (#507): a per-request fan MODE for soaks

## Attempt 2 (2026-09-28): why attempt 1 did not land

Attempt 1 built `FAN_DUTY=<pwm>`, a raw write to the fan's PWM duty node
(PR #563, branch `lane/fanduty507`). It was finished, proven (Nova probe, a
3-minute soak at 50000, selftest pass and red-with-restore-removed) and
audited clean. The owner then closed it without merging (2026-09-28): "On the
fan, only use available modes. I don't want to test on a fan speed that's
user inaccessible." A duty of 50000 is not a setting any player can pick.
The #563 notes stay on that branch; the two facts carried forward:

- Putting `fan_mode` back returns the duty node to the firmware within a
  second; nothing needs to write the node on the way out (Nova probe,
  2026-09-28).
- `grep -qF` with a two-line mutant anchor matches either line; check a
  mutant's anchor in python.

This attempt replaces the knob with `FAN_MODE=<name>`: only the options the
device's own UI offers, nothing written to the duty node. Work in progress.
