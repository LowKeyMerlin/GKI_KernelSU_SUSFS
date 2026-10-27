#!/bin/busybox sh
# PID 1 of the VM, see qemu_boot.sh.
/bin/busybox --install -s /bin
export PATH=/bin
mount -t proc proc /proc
mount -t sysfs sys /sys
mount -t devtmpfs dev /dev || mount -t tmpfs dev /dev
mount -t tmpfs tmp /tmp
for n in 'null c 1 3' 'zero c 1 5' 'random c 1 8' 'urandom c 1 9'; do
  set -- $n
  [ -e /dev/$1 ] || mknod /dev/$1 $2 $3 $4
done
/bin/busybox ash /xt/guest.sh /xt "/bin/busybox ash" recovery 2>&1
sync
poweroff -f
