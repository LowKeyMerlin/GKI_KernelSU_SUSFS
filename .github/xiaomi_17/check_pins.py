#!/usr/bin/env python3
"""Compare the resolved pins with boot_verified.json.

A match prints a notice, anything else a warning. The build is never failed.
"""
import argparse
import json
import pathlib

LOCK = pathlib.Path(__file__).with_name("boot_verified.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root-flavor", default="bakasu")
    ap.add_argument("--kernel-commit", required=True)
    ap.add_argument("--susfs-commit", required=True)
    a = ap.parse_args()

    entries = json.loads(LOCK.read_text(encoding="utf-8"))["verified"]
    for e in entries:
        if (e["root_flavor"], e["root_commit"], e["susfs_commit"]) == (
            a.root_flavor,
            a.kernel_commit,
            a.susfs_commit,
        ):
            print(
                f"::notice title=Pins are boot-verified::{a.root_flavor} {a.kernel_commit[:8]} + "
                f"SUSFS {a.susfs_commit[:8]} passed the boot test ({e['verified_on']}, run {e['build_run']})"
            )
            return
    print(
        f"::warning title=Pins not boot-verified::{a.root_flavor} {a.kernel_commit[:8]} + SUSFS "
        f"{a.susfs_commit[:8]} has no entry in .github/xiaomi_17/boot_verified.json. Boot-test the "
        f"build (fastboot boot) before flashing, then add the entry."
    )


if __name__ == "__main__":
    main()
