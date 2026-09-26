"""Write this lane's board request into $DISPATCH_DIR/board-requests/brdf315b.md."""
import os

DISPATCH = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
BODY = """# board request: lane.brdf315b (#315, PR #375)

**Request:** a grant of `hw/xbox/nv2a/pgraph/glsl/psh.c` for one commit, once
lane.fog278 (PR #373) and lane.y16bump10 (PR #367) have folded. Or route the
patch to whichever lane holds psh.c at that point.

**What it carries:** `docs/lanes/brdf315b/brdf315b-psh.diff` on lane/brdf315b.
That is brdf315's BRDF hunk plus a `PS_TEXTUREMODES_BRDF` case in
`stage_consumed_raw()`. Without that case, #283's `tex_bytes16` hands the
BRDF stage bytes instead of 16-bit fields. It applies at master 6550967a5e
and on both holders' heads (`overlap.sh 373 367`), and it passes
`-fsyntax-only`.

**Why it is worth a grant:** the refuted arm's capture (e3b13f5b45) is
reproduced 598/610 whole-texel by the fitted rule with byte inputs. All 12
misses are boundary ties, and each one lands on the golden's texel under
field inputs. Predicted: Texture_BRDF x3, 614 -> <= 4 each. The prediction
legs are in docs/lanes/brdf315b/NOTES.md section 4. Register after the
committer's last rebase, a_ref = parent, b_ref = the commit.

No tracker or territory edit is needed beyond the grant itself.
"""
path = os.path.join(DISPATCH, "board-requests", "brdf315b.md")
with open(path, "w") as f:
    f.write(BODY)
print("wrote", path)
