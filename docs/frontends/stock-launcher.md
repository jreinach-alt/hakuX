# Stock launcher

## AYN odinlauncher (Thor) — tested on the Thor

| | |
|---|---|
| Frontend | AYN odinlauncher, `com.odin.odinlauncher` |
| Device | Thor (AYN handheld), Android 13 (SDK 33) |
| hakuX | 0.4.1-1004-40b62fd533, package `com.jreinach.hakux` |

### Config

None needed. hakuX already shows up in the stock launcher's app drawer and
search under its display name, same as any installed Android app:

![odinlauncher's app drawer with hakuX's three installed variants](images/stock-app-drawer.png)

Searching "hakuX" surfaces all three installed variants — the release build
("hakuX (fork)"), `.debug`, and `.debug2`. Only the release build
("hakuX (fork)") was tested here.

### Steps

1. From the home screen, open Search apps, type "hakuX", tap **hakuX
   (fork)**. This starts the app's default launcher activity,
   `com.jreinach.hakux/com.rfandango.haku_x.GameLibraryActivity` — confirmed
   via `dumpsys activity activities`.
2. hakuX opens to its own in-app Game Library. Pick a game from the list and
   press its play control.
3. Confirmed twice: once from a cold start, once after a full
   `am force-stop com.jreinach.hakux` followed by re-opening the app the same
   way (tap the icon in search again). Both times the tap landed on
   `GameLibraryActivity`, and selecting `41540002-Shin_Megami_Tensei_Nine`
   both times took focus to `MainActivity` and rendered the Atlus splash at
   29 FPS.

   ![Atlus splash screen after launching from the stock launcher twice](images/stock-launch.png)

### What a successful launch looks like

Tapping the app icon opens hakuX's own Game Library screen (not a specific
game) — this is expected for a stock Android launcher, see "Known limits"
below. From there, picking a game and pressing play reaches the game's own
splash/boot screen.

### Known limits

A stock Android launcher has no mechanism to scan a ROM folder or pass a
specific game file as a launch argument the way ES-DE's custom system or a
Daijisho platform definition can — it only knows how to start an app's
default activity. So the stock launcher can only ever open hakuX's own
in-app Game Library; the user always picks the specific game from inside
hakuX, not from the launcher itself. This is a property of generic Android
launchers, not something this wiring could change.

## Retroid stock launcher — not yet tested

The Retroid stock launcher is a different app, installed on the Nova, which
is under an owner-play hold and was not touched by this lane. That section
stays **not yet tested** until it's run on the Nova (tracked separately, not
part of this lane's device access).
