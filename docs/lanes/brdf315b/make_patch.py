"""Build brdf315b-psh.diff: brdf315's BRDF hunk plus the stage_consumed_raw case
that keeps the BRDF stage's two inputs as 16-bit fields.

psh.c is held by another lane, so this never writes the tree's psh.c: it
applies both edits to a copy in memory and prints a unified diff against the
worktree's own file.

Usage: python3 make_patch.py > brdf315b-psh.diff
"""
import difflib
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = "hw/xbox/nv2a/pgraph/glsl/psh.c"
BRDF315 = os.path.join(WT, "docs/lanes/brdf315/brdf315-psh.diff")

OLD = """/* Does a later stage read stage i's texel as raw bytes (a bump map or a
 * dot-product input)?  Those paths apply the channel signs themselves. */
static bool stage_consumed_raw(const struct PixelShader *ps, int i)
{
    for (int j = i + 1; j < 4; j++) {
"""
NEW = """/* Does a later stage read stage i's texel as raw bytes (a bump map or a
 * dot-product input)?  Those paths apply the channel signs themselves. */
static bool stage_consumed_raw(const struct PixelShader *ps, int i)
{
    for (int j = i + 1; j < 4; j++) {
        /* BRDF reads the two stages before it, not input_tex[j], and indexes
         * its volume with their whole 16-bit fields.  Split into bytes by
         * tex_bytes16 it would sample the theta field's low byte and the phi
         * field's high byte instead: that reading reproduces the #315 arm's
         * capture at e3b13f5b45 on 598 of 610 wedge px, and the golden on
         * none (docs/lanes/brdf315b/NOTES.md). */
        if (ps->tex_modes[j] == PS_TEXTUREMODES_BRDF && j - i <= 2) {
            return true;
        }
"""


def patched_text():
    orig = open(os.path.join(WT, SRC)).read()
    with tempfile.TemporaryDirectory() as d:
        copy = os.path.join(d, "psh.c")
        open(copy, "w").write(orig)
        subprocess.run(["patch", "-s", copy, BRDF315], check=True)
        text = open(copy).read()
    assert text.count(OLD) == 1, "stage_consumed_raw header moved"
    return orig, text.replace(OLD, NEW)


def main():
    orig, new = patched_text()
    if len(sys.argv) > 1 and sys.argv[1] == "--emit":
        sys.stdout.write(new)
        return
    sys.stdout.writelines(difflib.unified_diff(
        orig.splitlines(True), new.splitlines(True),
        "a/" + SRC, "b/" + SRC))


if __name__ == "__main__":
    main()
