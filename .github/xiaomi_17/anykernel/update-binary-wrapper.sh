#!/sbin/sh
# Xiaomi 17 wrapper around the upstream update-binary, which is shipped next to it as
# update-binary.orig and runs unchanged. Of everything it prints, only the lines the front
# end marks reach the screen. When the install stops before the front end has reported,
# the last upstream message is shown as the reason.
#   $1 recovery api version, $2 output fd, $3 zip file
#
# Recoveries and flasher apps read a "ui_print" protocol from the output fd and strip it, so
# that is what they get. When the output fd is a terminal there is nothing to strip it, so the
# text is printed as it is. XI_OUTPUT forces a choice: protocol, terminal (plain text with the
# logo) or plain (plain text, no logo).

case $0 in
  */*) xi_dir=${0%/*} ;;
  *) xi_dir=. ;;
esac
XI_ORIG=$xi_dir/update-binary.orig

# Run the original with the shell this one runs in.
xi_exe=$(readlink /proc/$$/exe 2> /dev/null)
case ${xi_exe##*/} in
  "") xi_sh=sh ;;
  busybox*) xi_sh="$xi_exe ash" ;;
  toybox*) xi_sh="$xi_exe sh" ;;
  *) xi_sh=$xi_exe ;;
esac

unzip -p "$3" META-INF/com/google/android/update-binary.orig > "$XI_ORIG" 2> /dev/null
if [ ! -s "$XI_ORIG" ]; then
  rm -f "$XI_ORIG"
  printf 'ui_print Installer files could not be read from the zip.\nui_print\n' >> /proc/self/fd/$2
  exit 1
fi

# How the output is shown: protocol, terminal or plain.
case $XI_OUTPUT in
  protocol | terminal | plain) xi_sink=$XI_OUTPUT ;;
  *)
    if [ -t "$2" ]; then
      xi_sink=terminal
      # No logo on a terminal that cannot draw it.
      xi_cols=$(stty size 2> /dev/null < /proc/self/fd/$2 | cut -d' ' -f2)
      if [ "${TERM:-dumb}" = dumb ] || [ "${xi_cols:-80}" -lt 40 ] 2> /dev/null; then
        xi_sink=plain
      fi
    else
      xi_sink=protocol
    fi
    ;;
esac

xi_filter() {
  xi_rc=1 xi_keep=0 xi_result=0 xi_last=
  while IFS= read -r xi_line; do
    case $xi_line in
      "xi-rc "*) xi_rc=${xi_line#xi-rc } ;;
      "ui_print XI|"*)
        xi_text=${xi_line#"ui_print XI|"}
        if [ "$xi_sink" = protocol ]; then
          printf 'ui_print %s\n' "$xi_text" >> /proc/self/fd/$2
        else
          printf '%s\n' "$xi_text" >> /proc/self/fd/$2
        fi
        case $xi_line in *Result*) xi_result=1 ;; esac
        xi_keep=1
        ;;
      *)
        if [ "$xi_keep" = 1 ]; then
          [ "$xi_sink" = protocol ] && printf '%s\n' "$xi_line" >> /proc/self/fd/$2
          xi_keep=0
        else
          case $xi_line in
            "ui_print "?*) xi_last=${xi_line#ui_print } ;;
          esac
        fi
        ;;
    esac
  done
  if [ "$xi_rc" != 0 ] && [ "$xi_result" = 0 ]; then
    if [ "$xi_sink" = protocol ]; then
      printf 'ui_print Stopped: %s\nui_print\n' "${xi_last:-no message}" >> /proc/self/fd/$2
    else
      printf 'Stopped: %s\n' "${xi_last:-no message}" >> /proc/self/fd/$2
    fi
  fi
  exit "$xi_rc"
}

export XI_FILTER=1 XI_SINK=$xi_sink
{
  $xi_sh "$XI_ORIG" "$1" 1 "$3"
  echo "xi-rc $?"
} | xi_filter "$@"
xi_rc=$?
rm -f "$XI_ORIG"
exit $xi_rc