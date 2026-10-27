#!/bin/bash
# Boot a GKI kernel in QEMU and run the installer in it.
#
# Usage: qemu_boot.sh KERNEL_IMAGE PREP_DIR OUT_DIR BUSYBOX
#
# PREP_DIR is what prep.sh wrote. The console goes to OUT_DIR/console.log.
set -euo pipefail

kernel=${1:?KERNEL_IMAGE} prep=${2:?PREP_DIR} out=${3:?OUT_DIR} busybox=${4:?BUSYBOX}
here=$(cd "$(dirname "$0")" && pwd)

mkdir -p "$out"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

root=$work/root
mkdir -p "$root"/{bin,proc,sys,dev,tmp,xt}
install -m 0755 "$busybox" "$root/bin/busybox"
cp "$prep"/{ak.zip,ak-pristine.zip,update-binary,update-binary.pristine,guest.sh,kernel.size,stock.release,standin.release} "$root/xt/"
for img in boot.src other_stock.img other_custom.img other_same.img other_other.img; do
  cp --sparse=always "$prep/$img" "$root/xt/$img"
done
install -m 0755 "$here/init.sh" "$root/init"
(cd "$root" && find . | cpio -o -H newc -R 0:0 --quiet | gzip -1) > "$work/initrd.gz"

rc=0
timeout --foreground -k 10 900 qemu-system-aarch64 \
  -machine virt -cpu max -m 3072 -smp 2 -nographic -no-reboot -nic none \
  -kernel "$kernel" -initrd "$work/initrd.gz" \
  -append "console=ttyAMA0 panic=-1 loglevel=4 rdinit=/init" \
  > "$out/console.log" 2>&1 || rc=$?
echo "$rc" > "$out/qemu.rc"
echo "qemu exited with $rc after $(grep -c . "$out/console.log") console lines"
