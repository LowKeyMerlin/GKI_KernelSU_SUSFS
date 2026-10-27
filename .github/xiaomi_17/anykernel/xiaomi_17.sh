# Xiaomi 17 front end for the AnyKernel3 installer.
# Loaded by the shim that replaces tools/ak3-core.sh, after the upstream core.
# The core steps are wrapped at run time, so a step that upstream renames or
# drops is only left unwrapped and the installer still works.

XI_CORE=tools/ak3.core.orig
# Next to the work directory: recovery has /tmp, a booted Android does not.
XI_DIR=${AKHOME%/*}
XI_LOG=${XI_DIR:-/tmp}/xiaomi_17-install.log
XI_OUT=${XI_DIR:-/tmp}/xiaomi_17-step.out
XI_STEPS=6
XI_WARNINGS=0
XI_DEPTH=0
XI_LAST=

# Show a line on the screen and keep it in the log.
xi_say() {
  echo "ui_print ${XI_FILTER:+XI|}${1:- }
      ui_print" >> /proc/self/fd/$OUTFD
  printf '%s\n' "$1" >> "$XI_LOG"
}

# Replaces the core ui_print. What the upstream script says is kept in the log
# and only shown when the install fails, as the last message.
ui_print() {
  until [ ! "$1" ]; do
    printf '%s\n' "$1" >> "$XI_LOG"
    XI_LAST=$1
    shift
  done
}

xi_warn() {
  XI_WARNINGS=$((XI_WARNINGS + 1))
  xi_say "  ! $1"
}

xi_step() {
  xi_say " "
  xi_say "[$1/$XI_STEPS] $2"
}

xi_prop() {
  getprop "$1" 2> /dev/null
}

# Release string of the Image in this zip, empty if it cannot be read.
xi_zip_release() {
  grep -a -o -m1 'Linux version [^ ]*' "${AKHOME:-.}/Image" 2> /dev/null | cut -d' ' -f3
}

# Release without the build hash and what follows it, which would wrap on the screen.
xi_short() {
  xi_s=${1%%-g[0-9a-f][0-9a-f][0-9a-f][0-9a-f]*}
  echo "${xi_s:-unknown}"
}

xi_save_log() {
  for xi_dir in /sdcard /data/media/0; do
    if [ -d "$xi_dir" ] && cp "$XI_LOG" "$xi_dir/" 2> /dev/null; then
      xi_say "  Log: $xi_dir/xiaomi_17-install.log"
      return 0
    fi
  done
  xi_say "  The log could not be saved."
}

xi_logo() {
  if [ "$XI_SINK" = plain ]; then
    xi_say '  GKI KernelSU SUSFS Installer'
    return
  fi
  xi_say '  ___ _  _____'
  xi_say ' / __| |/ /_ _|'
  xi_say '| (_ | '"'"' < | |'
  xi_say ' \___|_|\_\___| KernelSU'
  xi_say ' ___ _   _ ___ ___ ___'
  xi_say '/ __| | | / __| __/ __|'
  xi_say '\__ \ |_| \__ \ _|\__ \'
  xi_say '|___/\___/|___/_| |___/ Installer'
}

xi_credits() {
  xi_say "Credits:"
  xi_say "  WildKernels   Kernel images"
  xi_say "  osm0sis       AnyKernel3"
  xi_say "  LowKeyMerlin  Tailoring for"
  xi_say "                Xiaomi 17 series"
}

# Where the zip runs: recovery, or from a booted system.
xi_mode() {
  if { ps -A 2> /dev/null || ps 2> /dev/null; } | grep -v grep | grep -q zygote; then
    echo "booted system"
  else
    echo recovery
  fi
}

xi_base_version() {
  v=$(grep -o 'AK_BASE_VERSION=[0-9]*' "$AKHOME/META-INF/com/google/android/updater-script" 2> /dev/null | cut -d= -f2)
  echo "${v:-unknown}"
}

# Compare the running kernel (1) with the one in the zip (2), full release strings.
xi_compare() {
  if [ -z "$2" ]; then
    xi_warn "cannot read the zip kernel version"
    return
  fi
  if [ "${1%%-*}" != "${2%%-*}" ]; then
    xi_warn "sublevel differs: ${1%%-*} running, ${2%%-*} in zip"
    xi_say "    Flash only if system_dlkm matches the zip."
  fi
  xi_a=${1#*-}
  xi_b=${2#*-}
  [ "${xi_a%%-*}" = "${xi_b%%-*}" ] || xi_warn "KMI differs: ${xi_a%%-*} running, ${xi_b%%-*} in zip"
  [ "${1##*-}" = "${2##*-}" ] || xi_warn "page size differs: ${1##*-} running, ${2##*-} in zip"
  if [ "$1" = "$2" ]; then
    xi_say "  Release   identical, no delta against the running kernel"
  elif [ "${1%%-*}" = "${2%%-*}" ]; then
    xi_warn "build id differs: ${1#*-*-*-} running, ${2#*-*-*-} in zip"
  fi
}

# Release the installed vendor modules were built for, empty if none is found.
xi_modules_release() {
  xi_ko=$(find /system_dlkm /vendor_dlkm -name '*.ko' 2> /dev/null | head -n 1)
  [ -n "$xi_ko" ] && grep -a -o -m1 'vermagic=[^ ]*' "$xi_ko" 2> /dev/null | cut -d= -f2
}

# Show what a core step printed and flag the problems in it.
xi_digest() {
  [ -s "$XI_OUT" ] || return 0
  cat "$XI_OUT" >> "$XI_LOG"
  xi_hits=$(grep -i -E 'error|fail|cannot|can.t|not found|bad number|invalid' "$XI_OUT" 2> /dev/null | head -n 5)
  [ -n "$xi_hits" ] || return 0
  printf '%s\n' "$xi_hits" | while IFS= read -r xi_line; do
    xi_say "  ! $xi_line"
  done
  XI_WARNINGS=$((XI_WARNINGS + $(printf '%s\n' "$xi_hits" | wc -l)))
}

xi_sub() {
  case $1 in
    unpack_ramdisk) xi_say "  Unpacking the ramdisk" ;;
    repack_ramdisk) xi_say "  Repacking the ramdisk" ;;
    flash_boot) xi_say "  Building and signing the image" ;;
    flash_generic) xi_say "  Writing $2" ;;
  esac
}

# Run a core step: xi_run NAME FUNCTION ARGS. Only the outermost call reports.
xi_run() {
  xi_name=$1
  xi_fn=$2
  shift 2
  if [ "$XI_DEPTH" -gt 0 ]; then
    xi_sub "$xi_name" "$1"
    XI_DEPTH=$((XI_DEPTH + 1))
    "$xi_fn" "$@"
    xi_rc=$?
    XI_DEPTH=$((XI_DEPTH - 1))
    return "$xi_rc"
  fi
  case $xi_name in
    split_boot) xi_step 3 "Read boot image" ;;
    write_boot | flash_boot)
      xi_match_release
      xi_step 5 "Write boot image"
      ;;
    *) xi_sub "$xi_name" "$1" ;;
  esac
  XI_DEPTH=1
  "$xi_fn" "$@" > "$XI_OUT" 2>&1
  xi_rc=$?
  XI_DEPTH=0
  xi_digest
  if [ "$xi_rc" != 0 ]; then
    xi_say "  Failed (exit $xi_rc)"
    return "$xi_rc"
  fi
  if [ "$xi_name" = split_boot ]; then
    xi_say "  Partition  ${BLOCK:-unknown}"
    xi_say "  Slot       ${SLOT:-none}"
    [ -f "$SPLITIMG/ramdisk.cpio" ] && xi_say "  Ramdisk    present" || xi_say "  Ramdisk    none"
    xi_say "  Header     v$(xi_u32 "$BOOTIMG" 40)"
    xi_say "  Kernel     $(xi_u32 "$BOOTIMG" 8) bytes now, $(($(wc -c < "$AKHOME/Image" 2> /dev/null))) in the zip"
  fi
  xi_say "  Done"
}

# Shadow a core function with a reporting wrapper around its original body.
xi_wrap() {
  xi_def=$(sed -n "/^$1() {/,/^}/p" "$XI_CORE")
  if [ -z "$xi_def" ]; then
    printf 'not wrapped: %s\n' "$1" >> "$XI_LOG"
    return 0
  fi
  eval "xi_core_$xi_def"
  eval "$1() { xi_run $1 xi_core_$1 \"\$@\"; }"
}

# Unsigned number at a byte offset of a file: xi_u32 FILE OFFSET.
xi_u32() {
  od -An -tu4 -j"$2" -N4 "$1" 2> /dev/null | tr -d ' '
}

xi_hex() {
  printf '%s' "$1" | od -An -v -tx1 | tr -d ' \n'
}

xi_count() {
  grep -a -o -F -- "$1" "$2" 2> /dev/null | wc -l
}

# The "Linux version" line of a raw kernel file, empty if there is none.
xi_banner() {
  grep -a -o -m 1 -E 'Linux version [^ ]+ .*UTC [0-9]{4}' "$1" 2> /dev/null | head -n 1
}

xi_banner_release() {
  printf '%s\n' "$1" | cut -d' ' -f3
}

xi_banner_date() {
  printf '%s\n' "$1" | grep -o -E '[A-Z][a-z]{2} [A-Z][a-z]{2} [ 0-9]{2} [0-9:]{8} UTC [0-9]{4}$'
}

# Warn about what makes a kernel look like something other than a stock one.
xi_stock_check() {
  grep -a -q -i -E 'susfs|kernelsu|ksu_handle|sukisu|ksunext|apatch' "$1" && xi_warn "$xi_ref has root or SUSFS code"
  case $2 in
    *-g[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]-ab*) ;;
    *) xi_warn "$xi_ref has no vendor build id in its release" ;;
  esac
  case $3 in
    *" 1970") xi_warn "$xi_ref has a reproducible build date" ;;
  esac
}

# Replace a string of a file by one of the same length: xi_replace FILE OLD NEW.
xi_replace() {
  [ "${#2}" = "${#3}" ] || return 1
  magiskboot hexpatch "$1" "$(xi_hex "$2")" "$(xi_hex "$3")" > /dev/null 2>&1
  [ "$(xi_count "$2" "$1")" = 0 ]
}

# Give the Image of the zip the release and build date of the kernel that is installed, so
# the slots report the same version. On an A/B device that is the kernel of the other slot,
# otherwise the one in the boot partition about to be replaced. XI_OTHER_BOOT replaces the
# source, for tests.
xi_match_release() {
  xi_ref="other slot"
  xi_other=$XI_OTHER_BOOT
  if [ -z "$xi_other" ]; then
    case $SLOT in
      _a) xi_o=_b ;;
      _b) xi_o=_a ;;
      *) xi_o= ;;
    esac
    if [ -n "$xi_o" ]; then
      xi_other=${BLOCK%"$SLOT"}$xi_o
    else
      xi_other=$BLOCK
      xi_ref="current slot"
    fi
  fi
  xi_step 4 "Match the $xi_ref"
  xi_img=$AKHOME/Image
  if [ ! -f "$xi_img" ]; then
    xi_say "  The kernel is not a raw Image, skipped"
    return 0
  fi
  xi_say "  Source    $xi_other"
  if [ ! -r "$xi_other" ]; then
    xi_warn "the $xi_ref cannot be read, skipped"
    return 0
  fi
  xi_hdr=$XI_DIR/xiaomi_17-other.hdr
  xi_kernel=$XI_DIR/xiaomi_17-other.kernel
  dd if="$xi_other" of="$xi_hdr" bs=4096 count=1 2> /dev/null
  if [ "$(head -c 8 "$xi_hdr")" != "ANDROID!" ]; then
    xi_warn "the $xi_ref has no boot image, skipped"
    return 0
  fi
  xi_ver=$(xi_u32 "$xi_hdr" 40)
  xi_page=4096
  [ "${xi_ver:-0}" -lt 3 ] && xi_page=$(xi_u32 "$xi_hdr" 36)
  xi_size=$(xi_u32 "$xi_hdr" 8)
  if [ "${xi_page:-0}" -le 0 ] || [ "${xi_size:-0}" -le 0 ] || [ "$xi_size" -gt 268435456 ]; then
    xi_warn "the header of the $xi_ref is not usable, skipped"
    return 0
  fi
  dd if="$xi_other" of="$xi_kernel" bs="$xi_page" skip=1 count=$(((xi_size + xi_page - 1) / xi_page)) 2> /dev/null
  xi_ob=$(xi_banner "$xi_kernel")
  if [ -z "$xi_ob" ]; then
    xi_warn "the kernel of the $xi_ref is compressed or unknown, skipped"
    rm -f "$xi_hdr" "$xi_kernel"
    return 0
  fi
  xi_orel=$(xi_banner_release "$xi_ob")
  xi_odate=$(xi_banner_date "$xi_ob")
  xi_say "  Release   $(xi_short "$xi_orel")"
  xi_say "  Build id  ${xi_orel#*-*-*-}"
  xi_say "  Built     $xi_odate"
  xi_stock_check "$xi_kernel" "$xi_orel" "$xi_odate"
  rm -f "$xi_hdr" "$xi_kernel"

  xi_zb=$(xi_banner "$xi_img")
  xi_zrel=$(xi_banner_release "$xi_zb")
  xi_zdate=$(xi_banner_date "$xi_zb")
  if [ -z "$xi_zb" ]; then
    xi_warn "cannot read the version of the zip kernel, skipped"
    return 0
  fi
  if [ "$xi_zrel" = "$xi_orel" ] && [ "$xi_zdate" = "$xi_odate" ]; then
    xi_say "  Already identical"
    return 0
  fi
  xi_zhead=$(printf '%s\n' "$xi_zrel" | cut -d- -f1-3)
  xi_ohead=$(printf '%s\n' "$xi_orel" | cut -d- -f1-3)
  if [ "$xi_zhead" != "$xi_ohead" ]; then
    xi_warn "the $xi_ref is $xi_ohead, the zip $xi_zhead, kept as built"
    return 0
  fi
  if [ "${xi_zrel##*-}" != "${xi_orel##*-}" ]; then
    xi_warn "page size differs: ${xi_orel##*-} there, ${xi_zrel##*-} in the zip, kept as built"
    return 0
  fi
  if [ "${#xi_zrel}" != "${#xi_orel}" ]; then
    xi_warn "the build id has another length (${#xi_zrel} in the zip, ${#xi_orel} there), kept as built"
    return 0
  fi

  cp "$xi_img" "$xi_img.orig"
  if xi_replace "$xi_img" "$xi_zrel" "$xi_orel" && xi_replace "$xi_img" "$xi_zdate" "$xi_odate"; then
    rm -f "$xi_img.orig"
    xi_say "  Patched the kernel: ${xi_zrel#*-*-*-} to ${xi_orel#*-*-*-}"
  else
    mv -f "$xi_img.orig" "$xi_img"
    xi_warn "the kernel could not be patched, kept as built"
  fi
}
# Runs when anykernel.sh ends, with the exit code of the whole install.
xi_exit() {
  xi_rc=$?
  if [ "$xi_rc" != 0 ]; then
    xi_step 6 "Result: failed"
    xi_say "  Exit code  $xi_rc"
    if [ "$XI_DEPTH" -gt 0 ] && [ -s "$XI_OUT" ]; then
      cat "$XI_OUT" >> "$XI_LOG"
      xi_say "  Output of the step:"
      tail -n 3 "$XI_OUT" | while IFS= read -r xi_line; do
        xi_say "    $xi_line"
      done
    fi
    xi_say "  Last message:"
    xi_say "    $XI_LAST"
  else
    [ "$XI_WARNINGS" = 0 ] && xi_status=ok || xi_status="done, $XI_WARNINGS warning(s)"
    xi_step 6 "Result: $xi_status"
    xi_say " "
    xi_say "Reboot to use the new kernel."
    xi_say "If it does not boot, flash the"
    xi_say "stock boot image."
  fi
  xi_save_log
}

xi_begin() {
  : > "$XI_LOG"
  trap xi_exit EXIT
  xi_running=$(uname -r)
  xi_zipped=$(xi_zip_release)
  xi_device=$(xi_prop ro.product.device)

  xi_say " "
  xi_logo
  xi_say " "
  xi_credits

  xi_step 1 "Device check"
  xi_say "  Device    ${xi_device:-unknown}"
  xi_say "  Model     $(xi_prop ro.product.model)"
  xi_say "  Android   $(xi_prop ro.build.version.release), patch $(xi_prop ro.build.version.security_patch)"
  xi_say "  Boot      $(xi_prop ro.boot.verifiedbootstate), slot $(xi_prop ro.boot.slot_suffix)"
  xi_say "  Mode      $(xi_mode)"
  xi_say "  Base      AnyKernel3 $(xi_base_version)"
  if [ -z "$xi_device" ]; then
    xi_warn "device name not readable"
  elif [ "$xi_device" != nezha ]; then
    xi_warn "built and tested on the Xiaomi 17 (nezha), this is $xi_device"
  fi

  xi_step 2 "Kernel check"
  xi_say "  Running   $(xi_short "$xi_running")"
  xi_say "  In zip    $(xi_short "$xi_zipped")"
  xi_modules=$(xi_modules_release)
  xi_say "  Modules   $(xi_short "$xi_modules")"
  xi_compare "$xi_running" "$xi_zipped"
  if [ -n "$xi_modules" ] && [ -n "$xi_zipped" ] && [ "${xi_modules%%-*}" != "${xi_zipped%%-*}" ]; then
    xi_warn "modules are for ${xi_modules%%-*}, the zip is ${xi_zipped%%-*}"
  fi

  for xi_f in split_boot unpack_ramdisk repack_ramdisk write_boot flash_boot flash_generic; do
    xi_wrap "$xi_f"
  done
}