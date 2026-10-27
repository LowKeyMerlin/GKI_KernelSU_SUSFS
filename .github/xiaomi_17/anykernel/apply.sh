#!/bin/sh
# Put the Xiaomi 17 front end in front of the upstream AnyKernel3 installer at build time.
# anykernel.sh is left alone. tools/ak3-core.sh, which it loads, is moved aside and
# replaced by a shim that loads it and then the front end. update-binary is moved aside the same way
# and replaced by a wrapper that runs it and shows only the front end output.
set -eu

dir=${1:?usage: apply.sh ANYKERNEL_DIR}
here=$(cd "$(dirname "$0")" && pwd)
core=$dir/tools/ak3-core.sh
orig=$dir/tools/ak3.core.orig
ub=$dir/META-INF/com/google/android/update-binary

[ -f "$ub" ] || {
  echo "update-binary not found, review $here/apply.sh" >&2
  exit 1
}
[ -f "$core" ] || {
  echo "tools/ak3-core.sh not found, review $here/apply.sh" >&2
  exit 1
}
if [ -f "$orig" ]; then
  echo "already applied" >&2
  exit 0
fi

mv "$core" "$orig"
mv "$ub" "$ub.orig"
cp "$here/update-binary-wrapper.sh" "$ub"
chmod 755 "$ub"
cp "$here/core-shim.sh" "$core"
cp "$here/xiaomi_17.sh" "$dir/tools/xiaomi_17.sh"

sh -n "$ub"
sh -n "$core"
sh -n "$dir/tools/xiaomi_17.sh"
# A core function that cannot be wrapped is left as it is, but its text must parse.
for fn in split_boot unpack_ramdisk repack_ramdisk write_boot flash_boot flash_generic; do
  def=$(sed -n "/^$fn() {/,/^}/p" "$orig")
  if [ -z "$def" ]; then
    echo "note: $fn not found in the core, it will not be reported" >&2
  else
    printf 'xi_core_%s\n' "$def" | sh -n
  fi
done