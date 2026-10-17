# Security policy

_Last updated 2026-10-16, for version 0.5.0._

## Supported versions

Security fixes go into the next release. Only the latest release is
supported; test builds (`com.jreinach.hakux.debug`) are not.

## Reporting a vulnerability

Please report it privately, not in a public issue.

1. On the repository's **Security** tab, choose
   [**Report a vulnerability**](https://github.com/jreinach-alt/hakuX/security/advisories/new).
   Only the maintainer sees the report.
2. If that option is not there, open an issue titled "Security contact
   request", with no details, and a private way to send them will be
   arranged.

Include the app version and build, your device, what an attacker could do,
and the steps or the file that shows it.

## What counts

hakuX CE runs the code on a game disc inside an emulated Xbox. A problem is
a security issue when it reaches outside that, for example:

- a game image, save, save state or settings file that makes the app run
  code outside the emulated Xbox, or read or write files outside the folders
  you chose;
- the online features (box art and online play) exposing your device or
  your files to the network.

A game that crashes, hangs or draws wrongly inside the emulator is a bug:
[report it as one](docs/reporting-bugs.md).

## What happens next

You get a reply as soon as possible. A confirmed problem is fixed in the next
release, and the advisory is published once that release is out.
