# NV2A hardware probe (phase one)

A tiny XBE that lets the host read and write NV2A registers on a real console,
so that claims about what the hardware does can be measured instead of assumed.

Phase one is four operations and nothing else: `read32`, `write32`, soft
`reset`, `status`. **No framebuffer capture, no pushbuffer submission, no draw
commands, no DMA.** Those are phase two and they get their own brief. The
`USER` block is write-excluded here precisely because a store into it submits
pushbuffer work.

The console this runs on is documented in
[`../../docs/testing/xbox-console-provenance.md`](../../docs/testing/xbox-console-provenance.md).

## Standing up the toolchain

The suite and the probe share one toolchain: `abaire/nxdk` on the
`nxdk_pgraph_tester` branch, which is already pinned as a submodule of
`nxdk_pgraph_tests`. Use that pin rather than a fresh clone, so the probe and
the pgraph suite are built by the same compiler against the same libraries.

```sh
cd ~/nxdk_pgraph_tests
git submodule update --init --recursive      # ~260 MB, pulls lwip and nvnetdrv
```

### Prerequisites, including the ones this machine did not have

nxdk needs `clang`, `lld`, `llvm-ar`, `llvm-lib`, and `llvm-objcopy`. This host
had clang 18 and the llvm-18 binutils but **no `lld`**, and no passwordless
`sudo` to install one. `apt-get download` needs no root, and `dpkg -x` unpacks
into a prefix of your choosing:

```sh
PREFIX=$HOME/.local/nxdk-tools
mkdir -p $PREFIX/bin
cd /tmp && apt-get download lld-18
dpkg -x lld-18_*.deb $PREFIX/root
ln -sf $PREFIX/root/usr/lib/llvm-18/bin/lld $PREFIX/bin/lld
for t in llvm-ar llvm-lib llvm-objcopy llvm-strip clang clang++; do
    ln -sf /usr/lib/llvm-18/bin/$t $PREFIX/bin/$t
done
```

`nxdk-link` invokes `lld -flavor link`, so the generic `lld` driver is what has
to be on `PATH`, not `ld.lld`.

**`cmake` is not needed and is not installed.** It is pulled in only by
`extract-xiso`, which is only built when a Makefile sets `GEN_XISO`. The probe
is launched from the HDD, never from a disc, so its Makefile omits `GEN_XISO`
and the whole cmake dependency chain disappears. (Unpacking cmake from a .deb
the same way does not work without also unpacking libarchive and friends, which
is why avoiding it is the better answer.)

`nv2a-vsh` (`pip3 install nv2a-vsh`) is needed only to compile vertex shaders.
Phase one has none.

### Build

```sh
export NXDK_DIR=$HOME/nxdk_pgraph_tests/third_party/nxdk
export PATH=$HOME/.local/nxdk-tools/bin:$NXDK_DIR/bin:$PATH
make -C tools/nv2a_probe/probe -j4          # -> probe/bin/default.xbe
```

A `lld: warning: .edata=.rdata: already merged into .edataxb` during link is
normal; the stock nxdk samples emit it too.

## Safety model

**The allow-list is generated, not written.** `gen_window.py` reads the block
table out of `hw/xbox/nv2a/nv2a.c` — this emulator's own device model — and
emits `probe/nv2a_window.h`. A transcribed address cannot be re-verified; a
derived one can:

```sh
python3 tools/nv2a_probe/gen_window.py --check   # fails if the model moved
python3 tools/nv2a_probe/gen_window.py --write   # regenerate
```

It strips C comments first, which is not cosmetic: `nv2a.c` carries a
commented-out `ENTRY(PRAMIN, ...)`, and a regex over raw text puts a block the
tree does not model into the allow-list.

The base address `0xFD000000` is cross-checked against nxdk, which defines
`VIDEO_BASE` as `0xFD000000` in `lib/pbkit/outer.h` and places
`NV_PGRAPH_PARAMETER_A` at `0xFD401A88` — that base plus PGRAPH's `0x400000`
offset from the emulator's table. Two independent sources agree.

Three properties hold in the probe's own code, not in the driver:

1. **The wire carries offsets, not addresses.** The brief spells the commands
   `read32 <addr>`; this accepts an offset and adds the base itself. An access
   outside the BAR is therefore *unrepresentable* rather than merely rejected —
   there is no 32-bit value a confused host can send that reaches flash at
   `0xff000000`. Reads are bounded by the 16 MiB BAR, writes additionally by
   the modelled, write-enabled block list.
2. **A write that was not journalled cannot execute.** `mmio_commit_write()` is
   the only store to the BAR and it takes a `write_grant_t`, which only
   `journal_acquire_grant()` produces, and only after the host has fsynced the
   intent and acknowledged that sequence number. Remove the journal call and it
   does not compile.
3. **The journal lives on the host.** The console's drive is untouched during a
   run, which is what makes a probe run safe to power-cycle out of.

The SMC, SMBus and EEPROM are not reachable by construction: they are I2C
devices behind I/O ports (`smbus_xbox_smc_init(smbus, 0x10)` in
`hw/xbox/xbox.c`), and this probe issues no I/O port access at all. The SMC
owning fan control is the reason that matters.

### Tests

```sh
./tools/nv2a_probe/run_tests.sh                       # allow-list, mutation-checked
python3 tools/nv2a_probe/host/test_driver_loopback.py # host driver, no console
```

`run_tests.sh` rebuilds the suite against five deliberately broken allow-lists
and requires every one to go red. A safety check that has never been seen to
fail is not evidence. The loopback suite drives a simulated probe that wedges
on a nominated register, so the hang-attribution and poison paths — which a
healthy run never reaches — are exercised deliberately.

## Recovery

Tiered, because most hangs never reach the hardware:

| failure | what happens |
|---|---|
| bad register hangs the GPU, CPU alive | probe stays responsive; host issues `X`, a soft `HalReturnToFirmware(HalRebootRoutine)` |
| probe's main loop wedges | watchdog thread resets after 20 s with no command |
| processor fully wedged | needs a human at the power button — a relay across the front panel is a later improvement, not part of phase one |

On a dead socket the host marks the in-flight write `suspected_hang`, adds it
to the poison list, and resumes from the next register. A poisoned
`(offset, value)` is never issued twice, so a resumed sweep walks past what
killed it rather than into it again.

## The wire protocol

The console dials out to the host; nothing listens on the console. That gives a
boot announcement for free and turns a wedge into a dead socket rather than
silence.

```
probe -> host   HELLO 1 nv2a-probe base=FD000000 size=01000000 ...
host  -> probe  R <off>                 read32
      <- probe  OK R <off> <val> <BLOCK>      | ERR <code> <text>
host  -> probe  W <off> <val>           write32
      <- probe  JOURNAL <seq> W <off> <val>   -- probe blocks here
host  -> probe  ACK <seq>                     -- host has fsynced the intent
      <- probe  OK W <off> <val>              | ERR <code> <text>
host  -> probe  S | P | X               status | ping | soft reset
```

## Running the first experiment

Writable-bit discovery: per register, read the original, write all ones and
read back, write all zeros and read back, restore. `writable = ones & ~zeros`.
Bits set in both readbacks are read-only ones; clear in both, read-only zeros —
reported separately, because "not writable" and "wired high" are different
facts.

```sh
python3 tools/nv2a_probe/host/sweep_writable_bits.py \
    --workdir ~/hakux-work/hardware/probe/pmc --block PMC \
    --start 0x000000 --end 0x001000
# then, on the console: Applications -> NV2AProbe

python3 tools/nv2a_probe/host/compare_masks.py \
    --results ~/hakux-work/hardware/probe/pmc/results.jsonl --block PMC
```

`compare_masks.py` separates two questions that a header-only comparison
conflates: which bits `nv2a_regs.h` has a *name* for, and which registers the
block's `.c` file actually *switches on*. A register can be fully declared and
entirely unimplemented — writes silently dropped — and that combination is the
one worth finding.

It reads C with regular expressions, so a register handled by a range check or
a helper will look unimplemented. Every row is a claim to confirm against the
handler, not a verdict.

## Networking

The console is at `192.168.50.1` static; this host is `192.168.50.2` on the
same link (`eth2`). WSL is in `networkingMode=mirrored`, so the host holds a
real address on that segment and the console's dial-out reaches it directly —
there is no NAT between them in this direction. If the probe never appears,
suspect the Windows firewall on that interface before suspecting the probe.

Journals, sweep results and poison lists live under `~/hakux-work/` and stay
out of git.
