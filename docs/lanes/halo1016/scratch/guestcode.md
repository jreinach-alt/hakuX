# Halo: Combat Evolved (4D530004) guest-code read, offline

Source: `/mnt/d/hakux-staging/xiso/4D530004-Halo_Combat_Evolved.xiso.iso` (XDVDFS,
partition base 0, verified by `MICROSOFT*XBOX*MEDIA` at sector 32). `default.xbe`
extracted with the repo's own reader, `docs/lanes/audio1016/tools/xiso_ls.py`
(no new XDVDFS reader needed), to
`/mnt/d/hakux-staging/halo1016/extract/default.xbe` (2,535,424 bytes).
XBE certificate confirms title_id `0x4D530004`, name `"Halo"`. Base = `0x00010000`.
Disassembly: `capstone` 5.0.9, pip-installed into
`/mnt/d/hakux-staging/halo1016/pylibs` (no system capstone, no network block hit).
Scratch scripts live in `/mnt/d/hakux-staging/halo1016/*.py`.

Kernel thunk table (XOR'd with the retail key `0x5B6D40B6`; decrypts to
`0x001d6620`, which lands exactly on `.rdata`'s start VA — confirms retail key
and correct header offsets) has 134 entries. Relevant ordinals and their thunk
slot VAs:

| ordinal | name | thunk slot VA |
|---|---|---|
| 99 | KeDelayExecutionThread | 0x001d6674 |
| 145 | KeSetEvent | 0x001d66ac |
| 159 | KeWaitForSingleObject | 0x001d66b0 |
| 158 | KeWaitForMultipleObjects | 0x001d67f8 |

## Sections (VA ranges, flags)

Flag bits: 0x1 Writable, 0x2 Preload, 0x4 Executable, 0x8 Inserted, 0x10 Head-page RO, 0x20 Tail-page RO.

```
 0 .text        0x00011000-0x00180e40  flags=0x16 (Preload+Exec+HeadRO)      -- not writable
 1 D3D          0x00180e40-0x001925b4  flags=0x07 (Writable+Preload+Exec)
 2 D3DX         0x001925c0-0x00192c7c  flags=0x07
 3 DSOUND       0x00192c80-0x001af3d8  flags=0x07
 4 XNET         0x001af3e0-0x001b6c80  flags=0x26
 5 BINK*        0x001b6c80-0x001cea18  flags=0x36 / 0x16 (several Bink codec sections)
17 XPP          0x001cf4e0-0x001d6608  flags=0x07
18 .rdata       0x001d6620-0x001f1250  flags=0x06 (Preload+Exec, not writable)
19 .data        0x001f1260-0x003a5f88  flags=0x07 (Writable+Preload+Exec)
20 DOLBY        0x003a5fa0-0x003acd38  flags=0x06
21 BINKDATA     0x003acd40-0x003b0f90  flags=0x07
22 $$XTIMAGE    0x003b0fa0-0x003b37a0  flags=0x28
23 $$XSIMAGE    0x003b37a0-0x003b47a0  flags=0x38
```
**D3D and .data are both flagged Writable AND Executable** at the whole-section
level. That is the direct explanation for Q2, below.

All 12 byte patterns given in the prompt were verified to match exactly at
their stated VAs (section mapping + byte checks all `OK`), confirming the
VA→file-offset math before any disassembly was trusted.

## Q1: hot PCs during the slow cinematic

### 0x0001ec3a (`fldcw [ebp+0xc]`) -- function starts at 0x0001ec1f

Not literally `_ftol`; it is an MSVC CRT `_control87`-style helper: merges a
caller-supplied new control word with the current FPU control word under a
caller-supplied mask, then reloads it with `fldcw`, returning the *old* value:

```
0x0001ec1f: push ebp
0x0001ec20: mov ebp, esp
0x0001ec22: push ecx
0x0001ec23: wait
0x0001ec24: fnstcw [ebp-4]            ; old cw
0x0001ec27: mov eax,[ebp+0xc]         ; mask
0x0001ec2a: mov ecx,[ebp+8]           ; newctrl
0x0001ec2d: and ecx,[ebp+0xc]         ; newctrl & mask
0x0001ec30: not eax
0x0001ec32: and eax,[ebp-4]           ; oldcw & ~mask
0x0001ec35: or eax, ecx
0x0001ec37: mov [ebp+0xc], eax        ; merged cw
0x0001ec3a: fldcw [ebp+0xc]   <==
0x0001ec3d: movsx eax,[ebp-4]         ; return old cw
0x0001ec41: leave
0x0001ec42: ret
```
i.e. `_control87(newctrl, mask)`.

**Callers**: 11 static `call` sites to `0x1ec1f`, all inside `.text` (none in
D3D/XNET/etc), clustering in two floating-point compiler-support idioms, not
game logic directly: (a) NaN-safe comparison dispatch (`0x19e8e`/`0x19ed8`/
`0x19f17`, `0x1b341`/`0x1b3ca`) -- `fcomp`/`fnstsw`/`test ah,0x44`/`jp`
("unordered" check) followed by `push 0xffff; push <ctrl>; call 0x1ec1f`; and
(b) round/classify helpers next to `frndint` (`0x1e97f`, `0x1ea0e`, `0x1eaac`,
and one outlier at `0x23dd3`) with the same `push 0xffff; push <ctrl>; call`
idiom. Only 11 static sites but ~1.3M calls/2s means this is reached from a
very hot, probably per-vertex or per-object, floating-point path (comparisons
and/or round-to-int), not a rare setup call.

### The other 10 PCs

| VA | section | what it is |
|---|---|---|
| 0x00019f23 | .text | `test bl,0x20` inside the same NaN-safe compare dispatcher that calls 0x1ec1f (see 0x19f17 above) -- same fp-compare library cluster. |
| 0x00086ffe | .text | `mov ecx,[esp+0x28]; movss/movhps xmm1,...; subps/mulps/shufps/addss` -- an SSE squared-distance computation (`dx²+dy²+dz²`), typical of a culling/LOS/physics distance check. |
| 0x00183ffa | D3D | `mov dword ptr [edi-4], 0x800b80` then `rep movsd` in a 0x20-dword chunked loop -- a push-buffer bulk-copy routine (stream vertex/index data into the push buffer in 128-byte chunks, re-writing a method header each chunk). This is D3D's stream-copy/"MakeSpace"-adjacent inner loop. |
| 0x000a3fff | .text | `jl 0xa3c42`, the backward branch closing a `fld/fmul/faddp/fadd/fstp` loop -- a per-vertex multiply-accumulate (matrix transform / skinning blend). |
| 0x0005ff9d | .text | `mov al,[0x2e34e4]; test al,al; jne ...; mov byte[0x2e34e4],1` -- a trivial "run once" static-init guard. Hot only because of call volume, not work done. |
| 0x00171ffc | .text | `mov ecx,[0x278248]` as part of incrementing two global tick counters and setting a dirty-byte flag -- per-frame/tick bookkeeping. |
| 0x00022121 | .text | `jmp dword ptr [ebx]` jump-table dispatch into FP classification code using `fxam` (NaN/Inf/denormal test) -- same fp-support cluster as 0x1ec1f, reached via a type-dispatch table. |
| 0x00180ce2 | .text | `fldcw [ebp-0xa4]` -- another control-word-restore tail, right at the very end of `.text` (0x180e40 is where D3D begins), same fp-compare family. |
| 0x000222df | .text | `fldcw [esp+6]` after masking a status word with `0x300`/`0x7f` -- rounding-mode setter, part of the same fp-support cluster. |
| 0x00022388 | .text | `fldcw [esp]` -- same family again; sits right next to a `f2xm1`/`fscale` pair at 0x222b8-0x222cc (classic 2^x-1 transcendental building block, i.e. an exp/log/pow helper). |

**Page-boundary proximity** ("several sit just before a 4KB boundary" -- true for 4 of the 10):
- `0x00086ffe`: 2 bytes before the boundary (`0x87000`)
- `0x00183ffa`: 6 bytes before (`0x184000`)
- `0x000a3fff`: 1 byte before (`0xa4000`) -- the literal last byte of the page
- `0x00171ffc`: 4 bytes before (`0x172000`)

The rest (`0x19f23`, `0x5ff9d`, `0x22121`, `0x180ce2`, `0x222df`, `0x22388`)
are not near a page boundary (0xdd-0xedf bytes away).

**Overall picture**: 6 of the 11 PCs (including the `0x1ec3a` helper itself)
belong to one tight cluster of MSVC floating-point compiler-support code
(control-word toggle, NaN-safe compare, round-to-int, transcendental building
blocks) concentrated in `.text` between roughly `0x19e00` and `0x23e00`,
reached from very few static call sites but executed at enormous dynamic
frequency -- i.e. a hot per-vertex/per-object math path is making heavy use
of IEEE-correct float comparisons and roundings. Two PCs are genuine vector
math (`0x86ffe` distance², `0xa3fff` transform loop). One is a D3D
push-buffer bulk copy (`0x183ffa`). Two are cheap bookkeeping made hot purely
by call volume (`0x5ff9d`, `0x171ffc`).

## Q2: guest writes landing on pages that also hold code

Both VAs are in the **zero-filled BSS tail** of their section (past the
section's raw file data, inside its virtual size) -- confirmed by
`va - section_vaddr >= raw_size` for both:

- `0x002f9a4c` (writes at offsets 0xa4c..0xb40 of its page): section **.data**,
  flags `0x07` = Writable + Preload + **Executable**. `.data` ends its raw
  (file-backed) content at VA `0x0025f67c`; `0x2f9a4c` is ~0xFA000 further
  into the section's zero-initialized tail.
- `0x00191ba4` (writes at 0xba4..0xba8): section **D3D**, flags `0x07` =
  Writable + Preload + **Executable**. D3D's raw data ends at `0x0018f14c`;
  `0x191ba4` is in its zero-initialized tail too.

So in both cases the XBE's own section table marks the whole section
Executable *and* Writable simultaneously: `.data` is nominally "code" even
though it is Halo's largest data segment, and `D3D` is nominally "writable"
even though most of it is Direct3D's statically-linked driver code. Both
guest-write addresses are ordinary global variables (zeroed at load, never
present in the file) living in the BSS tail of these dual-flagged sections.
If the emulator tracks "this page once held translated code" (or trusts the
section Executable flag) at page granularity rather than the precise
code/data split within a section, a routine per-frame write to these
variables looks exactly like self-modifying code and discards the
translation for that page -- explaining the thousands-per-second
invalidations without any actual code being patched.

## Q3: push-buffer "callback" NOP + GPU wait

Searched the raw image for push-buffer method headers of the form
`(count<<18)|(subchannel<<13)|method`. Found 11 occurrences of header
`0x00040100` (count=1, subchannel=0, method=0x100 = `NV097_NO_OPERATION`),
8 of them inside the **D3D** section and 3 inside **.text** itself (so Halo's
own code, not just the linked D3D library, writes raw push-buffer commands).
Representative site, `0x00182d11` (D3D):

```
0x00182d0e: mov dword ptr [eax+0x10], ecx
0x00182d11: mov dword ptr [eax+0x14], 0x40100   ; NOP header, count=1
0x00182d18: mov edx, 0x320                      ; non-zero payload = token/seq#
0x00182d1d: mov dword ptr [eax+0x18], edx
0x00182d26: mov dword ptr [eax+0x1c], 0x81d8c
0x00182d2d: mov dword ptr [eax+0x20], 0x400b80
0x00182d37: mov dword ptr [eax+0x28], 0x40100
```
Each site writes the NOP header immediately followed by a small, distinct
integer payload (0x300, 0x304, 0x310, 0x31c, 0x320...) -- i.e. a fence/sequence
token riding on a NOP, interleaved with other method writes (0x110, 0x12c,
and a bulk-data header `0x400b80`/`0x800b80`) in the same flush/kick
sequence. This matches **InsertCallback**-style fence insertion as part of
normal state-flush/kick, not a dedicated single-purpose function.

**GPU wait path**, found via the kernel thunk slots:
`call dword ptr [0x1d66b0]` (KeWaitForSingleObject) appears once inside D3D,
at `0x0018118d`:
```
0x00181187: add eax, 0x24f0             ; &device's wait/event object
0x0018118c: push eax
0x0018118d: call dword ptr [0x1d66b0]   ; KeWaitForSingleObject(obj,6,1,0,0)
```
Timeout is `0` (NULL => infinite wait): an *unconditional, indefinite* block,
not a polled/timeout wait. `KeSetEvent` (`call dword ptr [0x1d66ac]`) is
called from two places in D3D, both reached through a tight MMIO poll loop
just above them:
```
0x0018a350: mov dword ptr [edi+0x600100], ebx
0x0018a356: test dword ptr [edi+0x100], 0x1000000
0x0018a360: jne 0x18a350                 ; spin until the status bit clears
0x0018a36c: call dword ptr [0x1d66ac]    ; KeSetEvent(&device event)
```
This is the completion side: something (interrupt handler or poll routine)
waits for an nv2a MMIO status bit at BAR offset `0x100` to clear, then signals
the same per-device event object `0x181170`'s KeWaitForSingleObject blocks on.

**Which one serializes CPU/GPU**: the `0x181170` wait has `Timeout=NULL`
(block forever) and only 6 static call sites -- consistent with an explicit
**BlockOnFence/Synchronize**-style call that makes the CPU wait until the GPU
has drained the push buffer up to the point a specific fence token
(`InsertCallback`, above) was inserted: CPU/GPU serialization, not a
frame-ahead throttle (a frames-in-flight limiter would more typically use a
short/periodic timeout or a counting object polled once per frame, not an
unconditional indefinite wait reached from several sites in state-flush
code). No ASCII/UTF-16 debug strings for `BlockOnTime`/`KickOff`/`Present`
etc. exist anywhere in the image (checked, zero hits -- stripped retail
build), so names above are behavioral labels, not recovered symbols.

## Q4: per-frame GPU readback

Searched for push-buffer headers encoding method `0x17cc`
(`NV097_GET_REPORT`, used for occlusion/ZPASS queries) across count=1..4,
subchannel=0..7. One real hit, `header=0x000817cc` (count=2, subchannel=0),
inside **D3D** at `0x00181c5d`:
```
0x00181c4a: push edi
0x00181c4b: mov edi, dword ptr [0x192390]
0x00181c52: call 0x188660
0x00181c57: and esi, 0x2ffffff
0x00181c5d: mov dword ptr [eax], 0x817cc      ; NV097_GET_REPORT, count=2
0x00181c63: mov dword ptr [eax+4], 0           ; param 1 (report type?)
0x00181c6a: or esi, 0x1000000
0x00181c70: mov dword ptr [eax+8], esi         ; param 2 (notifier index | flag)
0x00181c73: add eax, 0xc
0x00181c78: mov dword ptr [edi], eax
0x0018187a: call 0x188180
```
This is a wrapper (entered around `0x00181c2f`, guarded by a failure path
returning `0x8007000e`, the standard D3D "out of memory/space" HRESULT) that
emits a `GET_REPORT` command into the push buffer with a notifier-index
payload. This is the clearest evidence of per-frame GPU readback: Halo (or
the D3D runtime on its behalf) issues occlusion/ZPASS queries through this
path. I did not find any `CopyRects`-style bulk surface-to-system-memory copy
or an explicit render-target `Lock` pattern in the areas sampled -- absence
here is not proof of absence (would need broader coverage of D3D's ~70 KB to
rule it out definitively), but no evidence for it turned up in the search
patterns used (string search for `Lock`/`CopyRect`/`BackBuffer` debug names:
zero hits, as expected for a stripped retail XBE).

## What would sharpen this further

No symbol/debug info survives in this retail XBE, so all function identities
above are inferred from instruction patterns, not recovered names. The Q1 PCs
were given, not independently profiled here -- this explains what each PC
does and who calls it, but did not re-run the emulator to confirm the
1.3M/2s figure. Q4's `GET_REPORT` finding is a single static site; a full
occlusion-query call count would need runtime tracing, not static search.
