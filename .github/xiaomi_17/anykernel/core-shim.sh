# Xiaomi 17 shim. Loads the upstream core unchanged, then the front end.

# The core can stop while it loads, for example on a missing partition. The front end takes
# over this trap once it is loaded. The wrapper adds the reason after this line.
xi_early() {
  [ $? = 0 ] && return
  echo "ui_print ${XI_FILTER:+XI|}  Failed while loading the installer.
      ui_print" >> /proc/self/fd/$OUTFD
}
trap xi_early EXIT

. tools/ak3.core.orig
. tools/xiaomi_17.sh
xi_begin