#!/usr/bin/env python3
"""Run the Android CMakeLists.txt's nv2a_vsh_cpu block in its three cases.

    cmake_patch_test.py CMAKE PRISTINE_LIB_DIR

The block between "# --- nv2a_vsh_cpu" and "# --- libslirp" is lifted out of
android/app/src/main/cpp/CMakeLists.txt verbatim into a small project that
compiles the four library sources, with REPO_ROOT a fake tree under this
worktree (so inside a git repository, as the real build tree is):

  fetch     no subprojects/nv2a_vsh_cpu: FetchContent clones the pinned rev
  local     a pristine local checkout (the copy made from PRISTINE_LIB_DIR)
  premeson  a local checkout that meson already patched through diff_files

Each case must configure, build, name the path it took in its log, compile
the patched nv2a_vsh_cpu.c, and leave the local checkout byte-identical.
A fourth case, `mismatch`, gives the patch a checkout it cannot apply to and
must fail at configure.
"""
import filecmp
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CML = os.path.join(WT, "android/app/src/main/cpp/CMakeLists.txt")
PATCH_REL = "subprojects/packagefiles/nv2a_vsh_cpu/0001-silicon-arithmetic.patch"
SCRATCH = os.path.join(WT, ".scratch", "cmaketest")


def block():
    text = open(CML).read()
    m = re.search(r"# --- nv2a_vsh_cpu.*?(?=# --- libslirp)", text, re.S)
    if "--no-ceiling" in sys.argv:
        # The falsifier: without the ceiling, `git apply` inside this repo is
        # a silent no-op, and the fetch and local cases must now FAIL.
        return re.sub(r'"\$\{CMAKE_COMMAND\}" -E env "GIT_CEILING_DIRECTORIES=[^"]*"\s*', "",
                      m.group(0))
    return m.group(0)


def project(root):
    return """cmake_minimum_required(VERSION 3.30)
project(vshcpu_patch_test LANGUAGES C)
include(FetchContent)
set(REPO_ROOT "%s")
%s
add_library(vshcpu STATIC
  "${NV2A_VSH_CPU_DIR}/src/nv2a_vsh_emulator.c"
  "${NV2A_VSH_CPU_DIR}/src/nv2a_vsh_emulator_execution_state.c"
  "${NV2A_VSH_CPU_DIR}/src/nv2a_vsh_cpu.c"
  "${NV2A_VSH_CPU_DIR}/src/nv2a_vsh_disassembler.c")
target_include_directories(vshcpu PRIVATE "${NV2A_VSH_CPU_DIR}/src")
""" % (root, block())


def run(cmake, case, pristine):
    base = os.path.join(SCRATCH, case)
    shutil.rmtree(base, ignore_errors=True)
    root = os.path.join(base, "root")
    os.makedirs(os.path.join(root, os.path.dirname(PATCH_REL)))
    shutil.copy(os.path.join(WT, PATCH_REL), os.path.join(root, PATCH_REL))
    local = os.path.join(root, "subprojects/nv2a_vsh_cpu")
    if case in ("local", "premeson", "mismatch"):
        shutil.copytree(pristine, local)
    if case == "premeson":
        subprocess.run(["patch", "-p1", "-s", "-i", os.path.join(WT, PATCH_REL)], cwd=local,
                       check=True)
    if case == "mismatch":
        # Every line the patch removes from nv2a_vsh_cpu_mul, changed.
        src = os.path.join(local, "src/nv2a_vsh_cpu.c")
        t = open(src).read().replace("  out[0] = fix_inf_mult(COMP(inputs, 0, _X), COMP(inputs, 1, _X));",
                                     "  out[0] = fix_inf_mult(COMP(inputs, 0, 0), COMP(inputs, 1, 0));")
        open(src, "w").write(t)
    before = os.path.join(base, "before")
    if os.path.isdir(local):
        shutil.copytree(local, before)
    src_dir = os.path.join(base, "src")
    os.makedirs(src_dir)
    open(os.path.join(src_dir, "CMakeLists.txt"), "w").write(project(root))
    bld = os.path.join(base, "build")
    cfg = subprocess.run([cmake, "-S", src_dir, "-B", bld, "-G", "Unix Makefiles"],
                         capture_output=True, text=True)
    log = cfg.stdout + cfg.stderr
    if case == "mismatch":
        ok = cfg.returncode != 0 and "did not apply" in log
        print("%-9s configure rc=%d, refused=%s" % (case, cfg.returncode, ok))
        return ok
    b = subprocess.run([cmake, "--build", bld, "--", "VERBOSE=1"], capture_output=True, text=True)
    blog = b.stdout + b.stderr
    status = [l for l in log.splitlines() if "nv2a_vsh_cpu" in l]
    compiled = [l for l in blog.splitlines() if "nv2a_vsh_cpu.c" in l and " -c " in l]
    patched_dir = os.path.join(bld, "nv2a_vsh_cpu-patched", "src", "nv2a_vsh_cpu.c")
    marker = os.path.exists(patched_dir) and "hakuX #345" in open(patched_dir).read()
    from_patched = bool(compiled) and all("nv2a_vsh_cpu-patched/src/nv2a_vsh_cpu.c" in l
                                          for l in compiled)
    pristine_kept = True
    if os.path.isdir(before):
        cmp = filecmp.dircmp(before, local)
        pristine_kept = not (cmp.diff_files or cmp.left_only or cmp.right_only)
    # A reconfigure must not touch the patched file (no rebuild on reconfigure).
    m0 = os.stat(patched_dir).st_mtime_ns if os.path.exists(patched_dir) else None
    subprocess.run([cmake, "-S", src_dir, "-B", bld], capture_output=True, text=True)
    m1 = os.stat(patched_dir).st_mtime_ns if os.path.exists(patched_dir) else None
    ok = (cfg.returncode == 0 and b.returncode == 0 and marker and from_patched
          and pristine_kept and m0 == m1)
    print("%-9s configure rc=%d build rc=%d marker=%s compiled-from-patched=%s "
          "checkout-untouched=%s reconfigure-keeps-mtime=%s"
          % (case, cfg.returncode, b.returncode, marker, from_patched, pristine_kept, m0 == m1))
    for l in status:
        print("    " + l.strip())
    for l in compiled[:1]:
        print("    compile: ..." + l[l.find(" -c "):][:160])
    return ok


def main():
    cmake, pristine = sys.argv[1], os.path.abspath(sys.argv[2])
    results = [run(cmake, c, pristine) for c in ("fetch", "local", "premeson", "mismatch")]
    print("ALL OK" if all(results) else "FAILED")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
