# Privacy

This app is a local emulator. It does not have an account system, and it does
not collect or transmit analytics, crash reports, or usage data — there is no
such code in it.

## What stays on the device

Your BIOS/MCPX files, HDD image, game images, save data, settings, and any
captures or diagnostic exports you create stay in storage you chose (picked
through the Android file picker) or in the app's own storage. None of it is
uploaded anywhere by the app. If you share a capture or export, that is
something you do yourself, outside the app.

## Network use

The app requests Android's `INTERNET` permission for two features, both
visible and both optional:

- **Box art lookup.** The game library can show cover art for games it
  recognises by matching the file name against a list bundled in the app —
  that matching never leaves the device — then fetching the matching image
  from `raw.githubusercontent.com/izzy2lost/X1_Covers`. It is off until you
  choose it: the setup wizard asks once, with an unchecked switch, and an
  existing install that finished setup before this question existed is asked
  once with a plain yes/no question the first time it switches the library to
  the cover grid. Turning it on means each
  cover fetched sends GitHub a request naming that game, so GitHub sees your
  device's address and which titles you look up. Change your answer any time
  with **Look up box art online** in the library — with it off, the app makes
  no request for a game's art.
- **Insignia / online networking.** The emulator can give the emulated Xbox a
  network connection, for guest software that expects one (including
  Insignia's Xbox-Live replacement). This is off by default and only takes
  effect if you turn it on in Settings → Online / Insignia. The sign-up and
  guide links in that screen open in your browser; the app does not call out
  to them itself.

Nothing else in the app makes a network request.

## Upstream

This is a fork of [rfandango/hakuX](https://github.com/rfandango/hakuX),
itself descended from izzy2lost's Android port of
[xemu](https://github.com/xemu-project/xemu). This file describes this fork's
code as it stands; it is not a statement about other builds.
