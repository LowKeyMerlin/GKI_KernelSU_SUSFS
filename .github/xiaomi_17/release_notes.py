#!/usr/bin/env python3
"""Write release_body.md for the xiaomi_17 workflow.

Reads the resolved pins from OUTPUTS (resolve-sources outputs as JSON),
boot_verified.json for the Tested section and the git history for Changes.
Exits 3 when RELEASE_TYPE is Release and no pin set is boot tested.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = {
    "next": "KernelSU-Next",
    "kernelsu": "KernelSU",
    "bakasu": "BakaSU",
    "sukisu-ultra": "SukiSU-Ultra",
    "finasu": "FinaSU",
    "kowsu": "KowSU",
}
ROOT_URLS = {
    "next": "https://github.com/pershoot/KernelSU-Next/commit/",
    "kernelsu": "https://github.com/tiann/KernelSU/commit/",
    "bakasu": "https://github.com/Baka-SU/BakaSU/commit/",
    "sukisu-ultra": "https://github.com/SukiSU-Ultra/SukiSU-Ultra/commit/",
    "finasu": "https://github.com/LyraVoid/FinaSU/commit/",
    "kowsu": "https://github.com/KOWX712/KernelSU/commit/",
}
ROOT_OUTPUT = {
    "next": "kernelsu_commit",
    "kernelsu": "ksu_commit",
    "bakasu": "bakasu_commit",
    "sukisu-ultra": "sukisu_ultra_commit",
    "finasu": "finasu_commit",
    "kowsu": "kowsu_commit",
}
SUSFS_SUFFIX = {"bakasu": "_bakasu", "sukisu-ultra": "_sukisu_ultra", "kowsu": None}
SUSFS_URL = "https://gitlab.com/simonpunk/susfs4ksu/-/commit/"
NOMOUNT_URL = "https://github.com/maxsteeel/nomount/commit/"
VARIANTS = [
    "android12-5.10", "android13-5.10", "android13-5.15", "android14-5.15",
    "android14-6.1", "android15-6.6", "android16-6.12",
]
SKIP_SUBJECT = re.compile(r"^(docs|test|chore)(\(.*\))?:")


def load(name, default):
    try:
        return json.loads(os.environ.get(name, "") or default)
    except ValueError:
        return json.loads(default)


def link(sha, url):
    return f"[`{sha[:7]}`]({url}{sha})" if len(sha) == 40 else f"`{sha}`"


def selected_variants():
    ver = os.environ.get("KERNEL_BUILD_VERSION", "")
    m = re.match(r"^(\d+\.\d+)\.x-android(\d+)$", ver)
    variant = f"android{m.group(2)}-{m.group(1)}" if m else ""
    return [variant] if variant in VARIANTS else VARIANTS


def flavors(outputs):
    listed = [m.get("flavor", "") for m in load("MANAGER_LIST", "[]") if isinstance(m, dict)]
    found = [f for f in listed if f in LABELS]
    if found:
        return found
    matrix = {m.get("root_flavor", ""): m.get("root_commit", "")
              for m in json.loads(outputs.get("root_matrix") or "[]") if isinstance(m, dict)}
    return [f for f in LABELS if matrix.get(f)]


def root_commit(outputs, flavor):
    matrix = {m.get("root_flavor", ""): m.get("root_commit", "")
              for m in json.loads(outputs.get("root_matrix") or "[]") if isinstance(m, dict)}
    return matrix.get(flavor) or outputs.get(ROOT_OUTPUT[flavor], "")


def susfs_commits(outputs, flavor, variants):
    suffix = SUSFS_SUFFIX.get(flavor, "")
    if suffix is None:
        return {}
    found = {}
    for v in variants:
        sha = outputs.get("susfs_commit_" + v.replace("-", "_").replace(".", "_") + suffix, "")
        if sha:
            found[v] = sha
    return found


def tested_rows(picks):
    try:
        data = json.loads((HERE / "boot_verified.json").read_text(encoding="utf-8"))
        entries = data["verified"]
    except (OSError, ValueError, KeyError):
        return []
    rows = []
    for e in entries:
        for flavor, root, susfs in picks:
            if (e.get("root_flavor") == flavor and e.get("root_commit") == root
                    and e.get("susfs_commit") in susfs):
                rows.append({"device": data.get("device", "unknown"), **e})
                break
    return rows


def git(*args):
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def changes():
    manual = HERE / "CHANGES.md"
    if manual.is_file() and manual.read_text(encoding="utf-8").strip():
        return manual.read_text(encoding="utf-8").strip().splitlines()
    tags = [t for t in git("tag", "--merged", "HEAD", "--sort=-creatordate").splitlines()
            if re.fullmatch(r"r\d+", t)]
    upstream = git("rev-parse", "--verify", "-q", "origin/main")
    excluded = [f"^{ref}" for ref in (tags[:1] + ([upstream] if upstream else []))]
    subjects = git("log", "--no-merges", "--format=%s", "HEAD", *excluded).splitlines()
    lines = [f"- {s}" for s in subjects if s and not SKIP_SUBJECT.match(s)]
    sync = git("rev-parse", "--short", "origin/main")
    if sync:
        lines.append(f"- Synced with upstream `{sync}`")
    return lines or ["- No changes since the previous release"]


def main():
    outputs = load("OUTPUTS", "{}")
    variants = selected_variants()
    roots = flavors(outputs)
    picks, components = [], []
    for f in roots:
        sha = root_commit(outputs, f)
        sus = susfs_commits(outputs, f, variants)
        picks.append((f, sha, set(sus.values())))
        if sha:
            components.append((LABELS[f], link(sha, ROOT_URLS[f])))
        for sha_s in dict.fromkeys(sus.values()):
            where = [v for v, s in sus.items() if s == sha_s]
            name = "SUSFS" if len(where) == len(variants) else f"SUSFS ({', '.join(where)})"
            components.append((name if len(roots) == 1 else f"{name} for {LABELS[f]}", link(sha_s, SUSFS_URL)))
    nomount = outputs.get("nomount_commit", "")
    if os.environ.get("USE_NOMOUNT", "true") == "true" and nomount:
        components.append(("NoMount", link(nomount, NOMOUNT_URL)))

    verified = tested_rows(picks)
    out = ["# GKI KernelSU SUSFS", "", "## Tested", ""]
    if verified:
        out += ["| Device | Kernel | Result |", "| ------ | ------ | ------ |"]
        for e in verified:
            notes = f" Options: {e['options']}." if e.get("options") else ""
            out.append(f"| {e.get('device', 'unknown')} | {e.get('kernel', '')} | "
                       f"{e.get('result', '')}.{notes} Verified {e.get('verified_on', '')}. |")
        out += ["", "Builds without a row above are compiled but not boot tested."]
    else:
        out.append("None of these pins has been boot tested. Treat this build as a pre-release.")
    out += ["", "## Install", "",
            "1. Pick the zip that matches your kernel from the assets below.",
            "2. Check it: `sha256sum -c SHA256SUMS.txt`",
            "3. Flash it with a kernel flasher while rooted, or run `adb sideload <zip>` in recovery.",
            "4. Reboot, then install the manager APK.", "",
            "Back up your stock `boot` image first. To recover, run `fastboot flash boot boot.img`.", "",
            "## Which file do I need", "",
            "- **`*-AnyKernel3.zip`:** the kernel. Choose the one for your kernel sublevel.",
            "- **`*.apk`:** the root manager. A spoofed build uses a different package name.",
            "- **`NoMount-Metamodule.zip`:** optional. Install it from the manager.", "",
            "## Components", "", "| Component | Commit |", "| --------- | ------ |"]
    out += [f"| {name} | {ref} |" for name, ref in components]
    out += ["", "## Changes", ""] + changes()
    text = "\n".join(out) + "\n"
    Path("release_body.md").write_text(text, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text)
    if not verified and os.environ.get("RELEASE_TYPE") == "Release":
        print("::error::A Release needs a boot tested pin set in boot_verified.json. Use Pre-Release.")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
