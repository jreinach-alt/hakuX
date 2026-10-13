# Releases

This directory holds the notes published with each versioned release (see
`v0.4.0-j1.md` and `v0.4.1-j1.md` for examples).

## How a versioned release is built

A versioned release is built from a tagged commit with
`docs/testing/release_build.sh <version>`, which checks out tag `v<version>`
and produces the APK for that release. Unlike a nightly or a working build,
a versioned release ships with the pause menu's Debug Capture tool turned
off by default, since it is meant for players rather than contributors.
Anyone who wants it can still turn it on from **Settings > Debug Tools**.
