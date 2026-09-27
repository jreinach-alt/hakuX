"""Rewrite PR #490's body over REST (gh pr edit applies nothing here) and read it back."""
import json
import subprocess


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True, check=True).stdout


files = sh('git', 'diff', '--name-only', 'origin/master...HEAD').split()
old = sh('gh', 'api', 'repos/:owner/:repo/pulls/490', '-q', '.body')
pred = [l for l in old.splitlines() if l.startswith('Prediction:')][0]
base = sh('git', 'merge-base', 'origin/master', 'HEAD').strip()

body = f"""Lane: notify488            Issue: #488
Base: master @ {base}
Files: {', '.join(files)}
{pred}
Needs device: yes    Needs NDK: no

**Ships: the NV097 NOTIFY notifier write.** hakuX never wrote it (0 of 900 on master). The semaphore-release half was measured on the Nova and taken out (`0b3d108e1b`); the release keeps master's download.

| signal (Nova) | console | A = master | B |
|---|---|---|---|
| NOTIFY written, kick->notify (Tiny / DOA / DOA_Read) | 4.1 us | never (900/900 timeouts) | 23.7 / 16.9 / 15.7 us |
| notifier timestamp vs PTIMER ns | 0.9996 | - | 0.9987 |
| kick->semaphore, ST_Done_DOA (500 quads + RT switch) | 2.7 us | 18.4 us | 15.4 us |
| rep cost with a back-buffer read (submit + sem + read), ST_Done_DOA_Read | - | 32 ms | 123 ms |

**NOTIFY** (`DEF_METHOD(NV097, NOTIFY)`) writes the 16-byte notification at offset 0 of the notifies DMA object: a PTIMER ns timestamp, info32 0, and status 0, written last. WRITE_THEN_AWAKEN also raises `INTR_NOTIFY`, without a FIFO stall. The layout is the one the console's own files show.

**Semaphore half: refuted, not shipped.** It recorded the queued draws instead of downloading at the release.
- On the Nova, master's release is already 18 us after the kick (the Thor's 13.8 ms does not reproduce). The 500 quads are paid in submit in both arms.
- With a CPU read of the back buffer, B's rep costs 4x A's. That is a serializing cost, not a moved one.

**pgraph pair** (Nova, 13 suites, B = NOTIFY + semaphore): 752 of 754 captures byte-identical.
- All of `Texture_CPU_Update` and `ZPass_pixel_count` are identical.
- The 2 that differ, `GeometrySuperscreen_0.5626` and `_0.9990`, take several hashes across earlier arms on builds without this code: noise.
- NOTIFY alone is inert on every pgraph capture, because no suite with goldens sends it.

**DOA A1 B1 A2 B2:** gfps 13 / 13 / 13 / 14. DOA sends about 20 semaphore releases a frame and never sends NOTIFY. No hang, and no thermal on/off.

**Desktop:** not run. This host's desktop channel is GL-only, and no suite with goldens executes NOTIFY.

**Lead for #474:** on master, the next rep's submit costs 93.7 ms when the previous back buffer was not CPU-read, and 8.9 ms when it was. See `docs/lanes/notify488/NOTES.md` section 6.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
"""
subprocess.run(['gh', 'api', '-X', 'PATCH', 'repos/:owner/:repo/pulls/490', '--input', '-', '-q', '.body'],
               input=json.dumps({'body': body}), text=True, check=True, stdout=subprocess.DEVNULL)
back = sh('gh', 'api', 'repos/:owner/:repo/pulls/490', '-q', '.body')
print('read back matches:', back.strip() == body.strip())
print('\n'.join(back.splitlines()[:4]))
