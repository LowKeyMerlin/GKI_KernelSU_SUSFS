#!/usr/bin/env python3
"""Pin external actions to commit SHAs and stop checkouts persisting credentials.

harden applies it, unharden restores the upstream text, check fails on unpinned actions.
The edits are marked so both directions are exact and sync_clones can merge cleanly.

Usage: harden.py harden|unharden|check FILE...
"""
import re
import subprocess
import sys

MARK = "# xiaomi_17-hardened"
KEEP_CREDENTIALS = {"update-verified-pins", "nightly-release"}  # these run git push

USES = re.compile(
    r"^(?P<pre>\s*(?:-\s+)?uses:\s*)(?P<action>[^\s@#]+)@(?P<ref>[^\s#]+)(?P<rest>.*)$"
)
PINNED = re.compile(r"^[0-9a-f]{40}$")
JOB = re.compile(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$")
_cache = {}


def is_external(action):
    return not action.startswith("./") and action.count("/") >= 1


def resolve(action, ref):
    repo = "/".join(action.split("/")[:2])
    key = (repo, ref)
    if key not in _cache:
        url = f"https://github.com/{repo}.git"
        out = subprocess.run(
            [
                "git",
                "ls-remote",
                url,
                f"refs/tags/{ref}^{{}}",
                f"refs/tags/{ref}",
                f"refs/heads/{ref}",
            ],
            capture_output=True,
            text=True,
        )
        if out.returncode != 0:
            sys.exit(f"cannot resolve {repo}@{ref}: {out.stderr.strip()}")
        rows = [l.split("\t") for l in out.stdout.splitlines() if l.strip()]
        peeled = [r for r in rows if r[1].endswith("^{}")]
        pick = (peeled or rows or [None])[0]
        if not pick or not PINNED.match(pick[0]):
            sys.exit(f"{repo}@{ref} not found")
        _cache[key] = pick[0]
    return _cache[key]


def unharden_text(text):
    out = []
    for line in text.split("\n"):
        if (
            MARK in line
            and "persist-credentials" in line
            or line.rstrip().endswith(MARK + "-added")
        ):
            continue
        m = USES.match(line)
        if m and PINNED.match(m["ref"]):
            tag = re.match(r"\s*#\s*(\S+)(?:\s*\|\s*(.*))?$", m["rest"])
            if tag:
                line = f"{m['pre']}{m['action']}@{tag.group(1)}"
                if tag.group(2):
                    line += f" # {tag.group(2)}"
        out.append(line)
    return "\n".join(out)


def _step_end(lines, start, key_indent):
    """Index just past the step that begins at `start` (first line dedented below its keys)."""
    i = start + 1
    while i < len(lines):
        s = lines[i]
        if (
            s.strip()
            and not s.lstrip().startswith("#")
            and (len(s) - len(s.lstrip())) < key_indent
        ):
            break
        i += 1
    return i


def harden_text(text):
    lines = unharden_text(text).split("\n")
    out, job, i = [], None, 0
    in_jobs = False
    while i < len(lines):
        line = lines[i]
        if line.startswith("jobs:"):
            in_jobs = True
        if in_jobs:
            jm = JOB.match(line)
            if jm:
                job = jm.group(1)
        m = USES.match(line)
        if not m or not is_external(m["action"]):
            out.append(line)
            i += 1
            continue
        action, ref = m["action"], m["ref"]
        if not PINNED.match(ref):
            note = re.match(r"\s*#\s*(.*)$", m["rest"])
            line = f"{m['pre']}{action}@{resolve(action, ref)} # {ref}" + (
                f" | {note.group(1)}" if note and note.group(1) else ""
            )
        out.append(line)
        if action == "actions/checkout" and job not in KEEP_CREDENTIALS:
            key_indent = (
                len(m["pre"])
                - len(m["pre"].lstrip())
                + (2 if m["pre"].lstrip().startswith("-") else 0)
            )
            end = _step_end(lines, i, key_indent)
            step = lines[i + 1 : end]
            if not any("persist-credentials" in s for s in step):
                pad = " " * key_indent
                with_idx = next(
                    (k for k, s in enumerate(step) if s.startswith(pad + "with:")), None
                )
                if with_idx is None:
                    out.append(f"{pad}with:  {MARK}-added")
                    out.append(f"{pad}  persist-credentials: false  {MARK}")
                else:
                    step.insert(
                        with_idx + 1, f"{pad}  persist-credentials: false  {MARK}"
                    )
                out.extend(step)
                i = end
                continue
        i += 1
    return "\n".join(out)


def unpinned(text):
    bad = []
    for n, line in enumerate(text.split("\n"), 1):
        m = USES.match(line)
        if m and is_external(m["action"]) and not PINNED.match(m["ref"]):
            bad.append((n, m["action"], m["ref"]))
    return bad


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("harden", "unharden", "check"):
        sys.exit(__doc__)
    mode, paths = sys.argv[1], sys.argv[2:]
    failed = False
    for p in paths:
        text = open(p, encoding="utf-8", newline="").read().replace("\r\n", "\n")
        if mode == "check":
            for n, action, ref in unpinned(text):
                print(f"{p}:{n}: {action}@{ref} is not pinned to a sha")
                failed = True
            continue
        new = harden_text(text) if mode == "harden" else unharden_text(text)
        open(p, "w", encoding="utf-8", newline="").write(new)
        print(f"{mode}: {p}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
