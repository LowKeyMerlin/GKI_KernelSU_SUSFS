#!/usr/bin/env python3
"""Merge upstream changes into the xiaomi_17 workflow clones.

Each clone is 3-way merged against its base snapshot and the current upstream file, then
the snapshot is refreshed. Run after merging main. Conflicts are left as markers.
"""
import pathlib
import subprocess
import sys

import harden

ROOT = pathlib.Path(__file__).resolve().parents[2]
GH = ROOT / ".github"
WF = GH / "workflows"
BASE = GH / "xiaomi_17" / "base"
# clone, upstream file, base snapshot
PAIRS = [
    (WF / "xiaomi_17.yml", WF / "main.yml", "main.yml"),
    (WF / "xiaomi_17_prepare.yml", WF / "prepare.yml", "prepare.yml"),
    (WF / "xiaomi_17_build.yml", WF / "build.yml", "build.yml"),
    (GH / "actions/xiaomi_17-susfs/action.yml", GH / "actions/susfs/action.yml", "susfs-action.yml"),
    (GH / "actions/xiaomi_17-susfs-patches/action.yml", GH / "actions/susfs-patches/action.yml", "susfs-patches-action.yml"),
    (GH / "actions/xiaomi_17-networking/action.yml", GH / "actions/networking/action.yml", "networking-action.yml"),
]


def lf(path):
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def main():
    # normalise to LF, CRLF checkouts would conflict on every line
    conflicts = 0
    for clone, upstream, base_name in PAIRS:
        base = BASE / base_name
        # hardening is stripped before the merge and reapplied after
        clone.write_bytes(harden.unharden_text(lf(clone)).encode("utf-8"))
        base.write_bytes(lf(base).encode("utf-8"))
        theirs = base.with_name(base_name + ".new")
        theirs.write_bytes(lf(upstream).encode("utf-8"))
        rc = subprocess.run(
            ["git", "merge-file", "-L", "xiaomi_17", "-L", "base", "-L", "upstream",
             str(clone), str(base), str(theirs)],
            cwd=ROOT,
        ).returncode
        if rc < 0 or rc > 127:
            sys.exit(f"git merge-file failed for {clone.name}")
        print(f"{clone.relative_to(ROOT)}: {'CONFLICTS (%d)' % rc if rc else 'merged cleanly'}")
        if not rc:
            clone.write_bytes(harden.harden_text(lf(clone)).encode("utf-8"))
        conflicts += rc
        theirs.replace(base)  # new base
    if conflicts:
        print("Resolve the <<<<<<< markers in the clone(s), then run "
              "`python .github/xiaomi_17/harden.py harden <clone files>` and commit.")
        sys.exit(1)


if __name__ == "__main__":
    main()
