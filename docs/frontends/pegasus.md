# Pegasus

**Status: not installed — blocked on APK source.**

Pegasus is not on the Thor (confirmed with `pm list packages`). Per this
lane's rules, the first step was checking whether `pegasus-frontend.org`
itself hosts the Android APK, since this lane is not permitted to fetch
anything from GitHub.

It does not. The site's own "Downloads" section is a static page where every
platform row (Windows, Linux, Android, etc.) shows `loading...` until
client-side JavaScript (`js/app.js`) fetches
`https://api.github.com/repos/mmatyas/pegasus-frontend/releases/latest`
(and `.../tags/continuous`) and fills in the row with the
`browser_download_url` pulled straight out of the GitHub API response. There
is no independently-hosted APK anywhere on pegasus-frontend.org — the site's
own fallback text, shown if that API call fails, says so directly: "See all
releases HERE," linking to `github.com/mmatyas/pegasus-frontend/releases`.

## NEED:

Pegasus's Android APK has no source other than GitHub. Per the brief ("If
the only source is GitHub, write NEED: and carry on with the other three; do
not hit GitHub"), this lane did not fetch it and did not install or
configure Pegasus.

If the owner (or a lane with GitHub access) places the APK somewhere else
reachable — for example under `/home/justin/hakux-work/release/` or a
non-GitHub mirror — Pegasus wiring and testing can be picked up from here
without repeating the check above.
