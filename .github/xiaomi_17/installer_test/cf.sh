# Helpers for the Cuttlefish job. CF is the directory of the fetched build.
FLAGS=(--vm_manager=qemu_cli --cpus=4 --memory_mb=4096 --enable_sandbox=false
  --boot_timeout_secs=2600 --gpu_mode=guest_swiftshader --start_webrtc=false
  --enable_bootanimation=false)
ADB="$CF/bin/adb"
SERIAL=127.0.0.1:6520

# start_device LOGFILE: launch the device in the background and set CREATE_PID.
start_device() {
  sudo -u "$USER" -- env HOME="$HOME" bash -c \
    "cd '$CF' && timeout 2700 cvd create --host_path='$CF' --product_path='$CF' ${FLAGS[*]}" \
    > "$1" 2>&1 &
  CREATE_PID=$!
}

# wait_boot START LIMIT: succeed once adb reports sys.boot_completed=1. A launcher that
# exited gets a minute to leave adb reachable before this fails.
wait_boot() {
  local start=$1 limit=$2 value gone=
  while [ $(($(date +%s) - start)) -lt "$limit" ]; do
    "$ADB" connect "$SERIAL" > /dev/null 2>&1 || true
    value=$("$ADB" -s "$SERIAL" shell getprop sys.boot_completed 2> /dev/null | tr -d '\r' || true)
    [ "$value" = 1 ] && return 0
    if ! kill -0 "$CREATE_PID" 2> /dev/null; then
      gone=${gone:-$(date +%s)}
      [ $(($(date +%s) - gone)) -ge 60 ] && return 1
    fi
    sleep 5
  done
  echo 'processes of the guest:'
  "$ADB" -s "$SERIAL" shell 'ps -A -o PID,ARGS 2>/dev/null | grep -E "guest|update-binary|anykernel|dd |cat |magiskboot"' || true
  "$ADB" -s "$SERIAL" shell 'df -h /data /tmp 2>/dev/null' || true
  return 1
}

stop_device() {
  sudo -u "$USER" -- env HOME="$HOME" bash -c "cd '$CF' && cvd reset -y" > /dev/null 2>&1 || true
}

# push_prep DEST: copy what prep.sh wrote to the guest. The boot image fixtures are mostly zeros,
# so they travel compressed.
push_prep() {
  local stage="$RUNNER_TEMP/prep-gz"
  rm -rf "$stage"
  cp -r "$RUNNER_TEMP/prep" "$stage"
  gzip -f "$stage"/boot.src "$stage"/other_*.img
  echo "push $(du -sh "$stage" | cut -f1) at $(date +%T)"
  "$ADB" -s "$SERIAL" push "$stage/." "$1/" > /dev/null
  echo "pushed at $(date +%T)"
  "$ADB" -s "$SERIAL" shell "cd '$1' && for f in *.gz; do gzip -d \$f; done"
}
# run_guest DIR MODE LOCAL_OUT: run guest.sh on the device, for the stock case only because a software
# emulated device is slow, in the background and copy its output
# every 20 seconds, so a hang shows where it stopped. Returns 1 when it did not finish in 1000 seconds.
run_guest() {
  local t0 now
  "$ADB" -s "$SERIAL" shell "rm -f $1/run.out; nohup sh -c 'XT_CASES=\"stock parity plain\" XT_TIMEOUT=900 sh $1/guest.sh $1 sh $2 > $1/run.out 2>&1; echo finished >> $1/run.out' < /dev/null > /dev/null 2>&1 &"
  t0=$(date +%s)
  while now=$(date +%s); [ $((now - t0)) -lt 1000 ]; do
    sleep 20
    "$ADB" -s "$SERIAL" shell "cat $1/run.out" 2> /dev/null | tr -d '\r' > "$3" || true
    echo "$((now - t0))s: $(wc -l < "$3") lines, last: $(tail -n 1 "$3")"
    if grep -q '^finished' "$3"; then
      return 0
    fi
  done
  echo 'processes of the guest:'
  "$ADB" -s "$SERIAL" shell 'ps -A -o PID,ARGS 2>/dev/null | grep -E "guest|update-binary|anykernel|dd |cat |magiskboot"' || true
  "$ADB" -s "$SERIAL" shell 'df -h /data /tmp 2>/dev/null' || true
  return 1
}