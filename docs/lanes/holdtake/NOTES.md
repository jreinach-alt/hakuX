# lane.holdtake

A single take/release helper for device holds, where only the taker can remove a hold.

## The defect

`$DISPATCH_DIR/hold/<label>` stops the dispatcher claiming on a handheld.
Every writer and remover of it was ad hoc (`touch`/`rm`, inline
`os.remove()`). Nothing refused a take on a held device, and nothing checked
that a hold belonged to you before removing it. On 2026-09-26 at 16:58:52 PDT
the host update window held the Thor. At 17:00:19 a lane took the Thor
(checking only `running/*.owner`), overwrote `hold/thor.why`, and at 17:02:28
removed `hold/thor`. At 17:02:43 the Thor claimed a request inside the window.

## What landed

- `docs/testing/jobs/hold.sh` with `take | release | who | wait`.
  - `take` creates `hold/<label>` with `O_CREAT|O_EXCL`, so of several
    concurrent takers exactly one wins. The file holds the tag. The winner
    writes `.why` afterwards via tmp + rename. If the device is already held,
    `take` prints the holder and exits 3.
  - `release` removes both files only if the hold holds exactly the tag.
    Otherwise it exits 3 and removes nothing. A bare `touch`ed hold (empty)
    matches no tag, so whoever placed it by hand removes it by hand.
  - A request already running on the device does not block `take`, because a
    hold only stops new claims. The usage text says so.
  - DISPATCH_DIR resolves the same way it does in dispatcher.sh/request.sh.
    `HOLD_WAIT_INTERVAL` (default 15) is exposed only so the selftest can use 1 s.
- `docs/testing/jobs/selftest.d/99-hold-take.sh`: legs (a)-(f) over a private
  `$T/holdtake/dispatch`, so it never touches the harness's shared dir or the
  real `hold/`. `SELFTEST_HOLD_SH` points the legs at another implementation.
- `docs/testing/jobs/roles/lane.md`: one "Never" rule, which says holds go
  through `jobs/hold.sh` only.

## Proof

`bash -n` passes on both files. Fragment run standalone (the full selftest also
passed; see the PR):

| implementation | passed | failed |
|---|---|---|
| `jobs/hold.sh` | 25 | 0 |
| naive touch/rm (below) | 11 | 14 |

The naive version is what hosts and lanes were actually doing:

```bash
take)    printf '%s\n' "$3" > "$D/hold/$label"; echo "${*:4}" > "$D/hold/$label.why" ;;
release) rm -f "$D/hold/$label" "$D/hold/$label.why" ;;
```

Its failing legs:

```
  FAIL (a) hold/thor.why carries the reason          (format only; not a defect)
  FAIL (b) take on a held device exits 3
  FAIL (b) hold/thor is byte-identical after the refused take
  FAIL (b) hold/thor.why is byte-identical after the refused take
  FAIL (c) release with the wrong tag exits 3
  FAIL (c) hold/thor survives the wrong-tag release
  FAIL (c) hold/thor.why survives the wrong-tag release
  FAIL (c) an untagged (touched) hold is released by no tag
  FAIL (c) the touched hold survives
  FAIL (e) exactly one of eight concurrent takes exits 0 (got 8)
  FAIL (e) the other seven exit 3 (got 0)
  FAIL (e) hold/thor names the one winner
  FAIL (f) wait on a held device times out with exit 3
  FAIL (f) the timed-out wait left the holder's tag
```

Legs (b) and (c) are the incident's two halves: the lane overwrote the host's
`.why`, then removed the host's hold.

## Not done / for the next lane

- The existing ad hoc callers are not migrated: host-tools' update window,
  `hold_device.sh`, and any lane tool that writes `hold/` inline. This brief
  keeps dispatcher.sh, devices.sh and stop-emulator.sh out of scope. A
  follow-up should switch the host update window to
  `hold.sh take thor hostupd-<pid>`. Until then its hold is a plain file, and
  `hold.sh take` still refuses it because O_EXCL sees any file.
- `release` has a read-then-unlink gap. While the file exists no other taker
  can create it, so only a hand `rm` in that gap could make release remove
  someone else's newer hold. Closing it would require a rename dance that
  briefly un-holds the device, which is worse.
