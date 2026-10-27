#!/bin/bash
# Turn a built AnyKernel3 directory into what the guests flash.
#
# Usage: prep.sh ANYKERNEL_DIR OUT_DIR
#
# Writes ak.zip, update-binary, guest.sh, the boot image fixtures and the strings the guest
# checks to OUT_DIR. The zip is a copy in which only the target of the flash is changed, from
# the boot partition to /dev/xt_boot, which guest.sh points at a file. The artifact itself is not
# modified.
set -euo pipefail

ak=${1:?ANYKERNEL_DIR} out=${2:?OUT_DIR}
here=$(cd "$(dirname "$0")" && pwd)

# The upstream files must be exactly what the front end was put in front of.
if grep -q 'xi_\|xiaomi' "$ak/anykernel.sh" "$ak/tools/ak3.core.orig" "$ak/META-INF/com/google/android/update-binary.orig"; then
  echo "the front end leaked into an upstream file" >&2
  exit 1
fi
[ -f "$ak/tools/xiaomi_17.sh" ] || { echo "the front end is not in the zip" >&2; exit 1; }

# The build leaves a stand-in for the vendor build id, the installer swaps it.
banner=$(grep -a -o -m 1 -E 'Linux version [^ ]+ .*UTC [0-9]{4}' "$ak/Image" | head -n 1)
release=$(cut -d' ' -f3 <<< "$banner")
date=$(grep -o -E '[A-Z][a-z]{2} [A-Z][a-z]{2} [ 0-9]{2} [0-9:]{8} UTC [0-9]{4}$' <<< "$banner")
standin=g000000000000-abogki000000000
case $release in
  *"$standin"*) ;;
  *) echo "the kernel release $release has no stand-in build id" >&2; exit 1 ;;
esac
stock=${release/$standin/g75e9b1c7ae7c-abogki463945075}
stock_date='Thu Nov 27 08:45:40 UTC 2025'

mkdir -p "$out"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp -a "$ak/." "$work/"
# The target is a file, not a partition: bound the zero fill of the core to its size.
sed -i -e "s|^block=.*|block=/dev/xt_boot|" -e '/^block=/a customdd="bs=1048576 count=64 conv=notrunc"' "$work/anykernel.sh"
grep -q "^block=/dev/xt_boot\$" "$work/anykernel.sh"
(cd "$work" && python3 -m zipfile -c "$out/ak.zip" *)
[ -s "$out/ak.zip" ]

# The control of the parity case: the same zip with the upstream files back in place, as if the
# front end had never been put in front of them.
cp -a "$work/." "$work.pristine"
mv -f "$work.pristine/tools/ak3.core.orig" "$work.pristine/tools/ak3-core.sh"
mv -f "$work.pristine/META-INF/com/google/android/update-binary.orig" "$work.pristine/META-INF/com/google/android/update-binary"
rm -f "$work.pristine/tools/xiaomi_17.sh"
(cd "$work.pristine" && python3 -m zipfile -c "$out/ak-pristine.zip" *)
cp "$work.pristine/META-INF/com/google/android/update-binary" "$out/update-binary.pristine"
rm -rf "$work.pristine"
cp "$ak/META-INF/com/google/android/update-binary" "$out/update-binary"
cp "$here/guest.sh" "$out/guest.sh"
stat -c %s "$ak/Image" > "$out/kernel.size"
echo "$stock" > "$out/stock.release"
echo "$release" > "$out/standin.release"

python3 "$here/mkboot.py" "$out/boot.src"
python3 "$here/mkboot.py" "$out/other_stock.img" "$stock" "$stock_date"
python3 "$here/mkboot.py" "$out/other_custom.img" "$stock" "$stock_date" "KernelSU susfs_init"
python3 "$here/mkboot.py" "$out/other_same.img" "$release" "$date"
python3 "$here/mkboot.py" "$out/other_other.img" "${stock/-android/.0-android}" "$stock_date"
