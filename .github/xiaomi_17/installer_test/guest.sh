#!/bin/sh
# Run the installer on the guest and print "XT key=value" lines for judge.py.
#
# Usage: guest.sh DIR [SHELL [recovery]]
#
# The target is a missing device node in the last run, which must fail.
# DIR holds what prep.sh wrote. SHELL runs update-binary, sh on Android and busybox ash in the VM.
# With recovery the work directory is left to update-binary, as in a recovery.
W=${1:?DIR}
SH=${2:-sh}
MODE=${3:-}
LOGDIR=$W
[ "$MODE" = recovery ] && LOGDIR=/tmp

say() { echo "XT $*"; }
yn() { if "$@"; then echo yes; else echo no; fi; }
has() { yn grep -q "$1" "$W/out.$2"; }
lacks() { if grep -q -E "$1" "$W/out.$2"; then echo no; else echo yes; fi; }
# Header field at an offset of the image, as an unsigned number.
field() { od -An -tu4 -j"$2" -N4 "$1" | tr -d ' '; }
# Occurrences of a string in the flashed image.
# Lines of the image with the string. grep -F finds nothing in the busybox of the guest.
found() { grep -a -c -- "$1" "$W/boot.img"; }

reset_work() {
  if [ "$MODE" = recovery ]; then
    rm -rf /tmp/anykernel
  else
    AKHOME=$W/ak
    export AKHOME
    rm -rf "$AKHOME"
  fi
}

CASES=${XT_CASES:-stock parity terminal plain custom other none single bad}
want() { case " $CASES " in *" $1 "*) return 0 ;; esac; return 1; }

# run_installer NAME [BINARY ZIP]: run update-binary, and after XT_TIMEOUT seconds say what is still running.
run_installer() {
  : > "$W/out.$1"
  $SH "$W/${2:-update-binary}" 3 1 "$W/${3:-ak.zip}" >> "$W/out.$1" 2>&1 &
  pid=$!
  n=0
  while kill -0 "$pid" 2> /dev/null && [ "$n" -lt "${XT_TIMEOUT:-240}" ]; do
    sleep 2
    n=$((n + 2))
  done
  if kill -0 "$pid" 2> /dev/null; then
    say "$1_hung=$( (ps -A -o PID,ARGS 2> /dev/null || ps -o pid,args 2> /dev/null || ps) | grep -E 'update-binary|anykernel|dd |cat |magiskboot' | grep -v grep | tr '\n' ';')"
    kill -9 "$pid" 2> /dev/null
    rc=124
  else
    wait "$pid"
    rc=$?
  fi
  say "$1_rc=$rc"
  say "$1_secs=$n"
}

# flash NAME OTHER [BOOT]: reset the target to BOOT (stock-less by default), name the other slot
# and run the installer. An empty OTHER means a device without one.
flash() {
  cp "${3:-$W/boot.src}" "$W/boot.img"
  ln -sf "$W/boot.img" /dev/xt_boot
  XI_OTHER_BOOT=$2
  export XI_OTHER_BOOT
  reset_work
  run_installer "$1"
  cp "$LOGDIR/xiaomi_17-install.log" "$W/log.$1" 2> /dev/null
}

stock=$(cat "$W/stock.release")
standin=$(cat "$W/standin.release")
say "kernel=$(uname -r)"
say "shell=$SH"
say "mode=${MODE:-booted}"
say "cases=$CASES"

if want stock; then
  flash stock "$W/other_stock.img"
  say "stock_logo=$(has Installer stock)"
  steps=
  for i in 1 2 3 4 5 6; do steps="$steps$(has "\[$i/6\]" stock)"; done
  say "stock_steps=$steps"
  say "stock_result=$(yn grep -q -E 'Result: (ok|done)' "$W/out.stock")"
  say "stock_upstream_hidden=$(lacks 'TheWildJames|Installing\.\.\.|Done!' stock)"
  say "stock_protocol=$(has '^ui_print ' stock)"
  say "stock_marker_leaked=$(has 'XI[|]' stock)"
  say "stock_credit=$(has 'osm0sis' stock)"
  say "stock_device_warning=$(has 'built and tested' stock)"
  say "stock_other_warning=$(has 'other slot has' stock)"
  say "stock_patched=$(has 'Patched the kernel' stock)"
  say "stock_release_found=$(found "$stock")"
  say "stock_standin_left=$(found "$standin")"
  say "stock_kernel_size=$(field "$W/boot.img" 8)"
  say "want_kernel_size=$(cat "$W/kernel.size")"
  say "stock_ramdisk_size=$(field "$W/boot.img" 12)"
  say "stock_header_version=$(field "$W/boot.img" 40)"
fi

# The same zip without and with the front end must leave the same boot image behind, when the
# front end has nothing to patch: its release is already the one of the other slot.
if want parity; then
  cp "$W/boot.src" "$W/boot.img"
  ln -sf "$W/boot.img" /dev/xt_boot
  reset_work
  run_installer pristine update-binary.pristine ak-pristine.zip
  want_sum=$(sha256sum < "$W/boot.img")
  say "pristine_bad_number=$(has 'bad number' pristine)"
  flash parity "$W/other_same.img"
  say "parity_identical=$(yn test "$(sha256sum < "$W/boot.img")" = "$want_sum")"
  say "parity_already=$(has 'Already identical' parity)"
fi

# The output as plain text, where the output fd is a terminal: no protocol, with or without logo.
for mode in terminal plain; do
  if want $mode; then
    XI_OUTPUT=$mode
    export XI_OUTPUT
    flash $mode "$W/other_stock.img"
    unset XI_OUTPUT
    say "${mode}_result=$(yn grep -q -E 'Result: (ok|done)' "$W/out.$mode")"
    say "${mode}_clean=$(lacks 'ui_print|XI\|' $mode)"
    say "${mode}_logo=$(has '___ _  _____' $mode)"
    say "${mode}_title=$(has 'GKI KernelSU SUSFS Installer' $mode)"
  fi
done

if want custom; then
  flash custom "$W/other_custom.img"
  say "custom_warned=$(has 'root or SUSFS' custom)"
  say "custom_patched=$(has 'Patched the kernel' custom)"
  say "custom_release_found=$(found "$stock")"
fi

if want other; then
  flash other "$W/other_other.img"
  say "other_kept=$(has 'kept as built' other)"
  say "other_standin_left=$(found "$standin")"
fi

if want none; then
  flash none "$W/missing.img"
  say "none_skipped=$(has 'cannot be read' none)"
  say "none_result=$(yn grep -q 'Result: done' "$W/out.none")"
fi

if want single; then
  flash single "" "$W/other_stock.img"
  say "single_label=$(has 'Match the current slot' single)"
  say "single_patched=$(has 'Patched the kernel' single)"
  say "single_release_found=$(found "$stock")"
fi

if want bad; then
  cp "$W/boot.src" "$W/boot.img"
  rm -f /dev/xt_boot
  XI_OTHER_BOOT=$W/other_stock.img
  export XI_OTHER_BOOT
  reset_work
  run_installer bad
  say "bad_report=$(has 'Failed while loading' bad)"
fi

for c in pristine $CASES; do
  [ -f "$W/out.$c" ] && sed "s/^/OUT $c: /" "$W/out.$c"
done
sed "s/^/LOG stock: /" "$W/log.stock" 2> /dev/null
say "done=yes"