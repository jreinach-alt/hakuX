# The project's original Xbox: what it is, and how we know

This records the identity of the physical console used for hardware
measurements, and how its EEPROM backup was produced. It exists so that a
measurement taken on real silicon can cite *which* silicon, and so that a
future reader can tell our console's data from data that merely sits on our
console's disk.

Cross-reference: issue #112, `xbox-hardware: the experiments that need real
silicon, in the order they pay`. Anything on that list runs on this machine
unless it says otherwise.

Nothing secret is recorded here. The EEPROM image, serial number, MAC address,
online key, confounder and HDD password live on the host only, outside this
repository. This file carries the fields a measurement legitimately needs to
cite, and nothing else.

## What this console is

| Field | Value | How it was established |
|---|---|---|
| Mainboard revision | reported `V1.1 (0b)` — see caveat below | console system-info screen |
| BIOS | ind-BIOS (not a retail BIOS) | console system-info screen |
| Kernel | `1.0.5003.67` | console system-info screen |
| GPU (NV2A) revision | 163 (`0xA3`) | console system-info screen |
| MCP revision | 212 (`0xD4`) | console system-info screen |
| RAM | 64 MB | stock for this board class; see pending |
| Video standard | NTSC-M | console system-info screen |
| XBE region | 1 | console system-info screen |
| Manufacture date | 2003-08-24 | case sticker |
| HDD | 2 TB upgrade, **unlocked** (HDD key all zeros) | owner; drive is not the factory unit |
| DVD drive model | *pending* | requires the EEPROM dump's info file |
| Dashboard | UnleashX (`C:\evoxdash.xbe`) | XBE title `UnleashX Xbox Launcher`; FTP banner `220 UnleashX FTP ready.` |
| Partitions | C E F G X Y Z | FTP enumeration |

### Cite the silicon revision, not the version string

Prefer **GPU revision 163 and MCP revision 212** when a measurement needs to
say what it ran on. Those are read directly off the hardware. The friendly
`V1.1` string is *derived* from them by the dashboard, and the derivation is
lossy: dashboard-level detection does not cleanly separate the v1.1–v1.5
boards, which share the PCI revision IDs the check keys on.

There is an open question worth flagging rather than smoothing over: a
manufacture date of 2003-08-24 is late for a v1.1, which was largely a 2002
board. Either the sticker and the board disagree (a refurbished or swapped
mainboard is common on a 20-year-old console), or the detection is reporting
v1.1 for a later board. **The DVD drive model discriminates between them** —
drive vendor tracks board revision fairly tightly — which is one more reason
the pending row above matters. Until it is resolved, treat `V1.1` as a label,
not a measurement, and cite the revisions.

## How the EEPROM backup was produced

> **Status: the dump has not been taken yet.** Everything below that is
> written in the past tense has happened; the three steps marked PENDING need
> the owner at the console with a controller, because launching an application
> cannot be done over the network. This block is removed once the dump
> verifies.

Date produced: *pending.*

The console runs UnleashX, which has **no EEPROM backup function**. That is not
a recollection: the dashboard's action table was read out of the XBE and is
complete —

```
CopyDVD PAL60 PAL50 UnRar unzip Delete Rename Move copy format
X2IGR_ON X2IGR_OFF XeniumOS TextEditor SetClock PrepareHD
trayopen trayclose netreset ftpstart ftpstop ftpreset
shutdown powercycle reset restart reboot
GameManager SavesManager LaunchDVD
```

plus `Settings`, `Skins`, `FileManager`, `AskUser`, `MessageBox` and `Format`
from the live `C:\Config.xml`. There is no EEPROM verb anywhere in it. The only
EEPROM string in the whole binary is the settings label `Video Mode (EEPROM
Safe)`.

No EEPROM tool was installed on the drive either. A full walk of all seven
partitions (258,583 entries) found none, and a separate sweep for files of
**exactly 256 bytes** — the size of an Xbox EEPROM image, whatever the file is
named — found 287, every one of them inside a game or emulator directory
except the foreign artifact described below.

So ConfigMagic v1.0 (Team Assembly) is the tool. All 18 files of the package
were downloaded and verified against their published MD5s — all matched — and
are staged on the host for upload to `E:\Apps\ConfigMagic\`. UnleashX
auto-populates its Applications menu from `E:\Apps`, so no dashboard
configuration change is needed. *(PENDING: the upload itself.)* The
`Data\` folder of the package is **deliberately not installed**: it contains
only a template `.cfg` and two blank EEPROM images, which feed the *write*
paths and would have added two more 256-byte files to confuse later
verification.

*(PENDING)* The backup is to be taken with `Load XBOX EEPROM` followed by
`Create Backup Files`, which are read-only; the adjacent `Update XBOX EEPROM`,
`Load EEPROM from .BIN File` and `Lock HDD` must not be touched. `Lock HDD` in particular would have
locked a drive whose unlocked state is worth preserving.

Verification to be applied to the result: the image must be exactly 256 bytes, and its
serial and MAC are decoded straight out of the image (the serial is plaintext
ASCII at offset `0x34`, the MAC at `0x40`) and must match the console's own
system-info screen. Decoding the image directly means verification does not
depend on trusting the tool's own text output — a decoder that reads the
correct serial and MAC out of the *foreign* image was used to confirm the
decoder itself works before it was trusted on ours.

Copies will be held in two places on the host, outside this repository, plus
one off-machine copy.

## A stale artifact that reads as authoritative

This is the finding worth carrying forward, and it is a clean worked example of
a failure mode this project keeps meeting.

The drive arrived with these three files sitting in the root of `E:`:

```
EEPROMBackupBeforeUpdate.bin      256 bytes
EEPROMBackupBeforeUpdate.cfg
EEPROMBackupBeforeUpdate.TXT
```

They are a genuine ConfigMagic backup, correctly formatted, internally
consistent, and **they describe a different console**: a V1.6 running kernel
`1.0.5838.1`, with a stock 10 GB Seagate drive and a Philips DVD unit. This
console is reported V1.1, runs ind-BIOS `1.0.5003.67`, and has a 2 TB drive.
The mismatch is not subtle once the two are placed side by side — but nothing
about the files themselves advertises it. The filename is plausible, the
format is correct, the contents parse.

The mechanism is visible in ConfigMagic itself. Its configured output path is
the root of `E:`, and it writes `EEPROMBackupBeforeUpdate.*` automatically
immediately before it modifies an EEPROM. So these files are the seller's own
build machine backing itself up before being modified, and they were then
carried onto this drive when the partition was cloned for sale. Restoring them
to this console would have written another machine's identity over ours.

Two things follow, and the second is the one that generalises.

**The file had already been believed once.** A byte-identical copy of that
image was sitting untracked in the repository working directory when this task
started — same MD5, `a0c84f7098da87af29719479eeac4146`. It had been pulled off
the console and kept as though it were ours. It has been moved out of the
repository and renamed to carry its own warning. Being 256 bytes and parsing
cleanly is not evidence of whose console it is; it is only evidence that it is
an EEPROM.

**Renaming comes before the dump, not after.** *(PENDING)* The files on the
console are to be renamed to `FOREIGN-CONSOLE-DO-NOT-RESTORE.{bin,cfg,TXT}`
*before* ConfigMagic is installed — renamed, not deleted, because they are the
evidence for this finding. The ordering is the point. ConfigMagic writes its output to the same
directory those files occupied, so with them still in place, a run that
silently failed to produce anything would leave a plausible, correctly-named,
correctly-sized EEPROM backup in exactly the spot the new one is expected, and
re-reading the stale file would look like success. Clearing the
namespace first converts that failure from *detectable* to *impossible*: after
the rename, no file of that name exists, so anything found there afterwards is
new by construction.

That is the general lesson. Checking a result against the stale value catches
the error only if you remember to check. Removing the stale value from the
place the result will appear means there is nothing to mistake it for.

## Talking to the console

Direct ethernet, static `192.168.50.1`. FTP is `xbox` / `xbox`.

**Passive mode only.** The console cannot open an inbound connection to a NATed
WSL2 address, so active mode hangs.

```
curl -s --list-only ftp://xbox:xbox@192.168.50.1/E/
```

Two things that cost time here, recorded so they do not cost it again:

- **`LIST <path>` silently ignores its argument** and lists the current
  directory. A recursive walk written the obvious way re-lists the root at every
  level and reports a large, entirely fictional entry count while finding
  nothing. Use `CWD` and then a bare `LIST`. The tell is a keyword sweep that
  returns zero hits when you already know a matching file is present — which is
  why a sweep like that should always carry a positive control.
- **FTP concurrency is capped, and an abandoned session is not reclaimed
  promptly.** `Config.xml` shipped with `MaxUsers = 2` (since raised to 25 —
  note the on-disk value may still read 2, so the change may not survive a
  reboot). After a recursive walk died mid-transfer, every connection was
  refused with `421 Too many users` for roughly fifteen minutes. The mechanism
  was *not* established, and the tidy explanation is recorded here as refuted
  rather than quietly dropped: the theory that the rejected retries were
  themselves holding the slots was tested directly — two sessions held, three
  unclosed rejected attempts outstanding, then the two good sessions closed —
  and a new connection was admitted immediately, so rejected attempts hold
  nothing. What is established is only that the cap is real and that recovery
  is not instant. Close sessions in a `finally`, and do not run two walks at
  once. `System > Misc > Reset FTP` clears it from the dashboard.

  The wider point cost about twenty minutes here: a retry loop reports *that*
  you are blocked, never *why*, and it is easy to start explaining a blocker to
  someone else before testing whether the explanation is true.

The console's clock is wrong — files date to December 20 — so **no timestamp on
anything pulled off this drive is evidence of anything**.
