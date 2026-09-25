#!/usr/bin/env bash
#
#   tools/turnip/compare_pkg.sh <a.adpkg.zip> <b.adpkg.zip>
#
# Static shape check of two adrenotools packages before either goes near a
# device: meta.json, ELF machine and type, NEEDED libraries, and the loader
# entry points (vk_icd*) each library exports. A package that differs from the
# fleet's T30 here would fail to load, which says nothing about rendering; the
# rendering control is a device run.
set -euo pipefail
NDK="${NDK:-/home/justin/Android/Sdk/ndk/29.0.14206865}"
R="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
for zip in "$@"; do
    d="$TMP/$(basename "$zip")"
    mkdir -p "$d"
    python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$zip" "$d"
    lib="$d/$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['libraryName'])" "$d/meta.json")"
    echo "== $zip"
    cat "$d/meta.json"; echo
    echo "size: $(stat -c %s "$lib")"
    "$R" -h "$lib" | grep -E "Machine|Type:"
    "$R" -d "$lib" | grep -E "NEEDED|SONAME" || true
    # Android loads a Vulkan HAL through the HMI module symbol; vk_icd* are
    # the desktop loader's and an Android build need not export them.
    echo "entry points: $("$R" --dyn-syms "$lib" | grep -oE ' (HMI|vk_icd[A-Za-z]+|vkGetInstanceProcAddr)$' | sort -u | tr '\n' ' ')"
done
