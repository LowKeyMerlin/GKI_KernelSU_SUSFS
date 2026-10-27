#!/usr/bin/env python3
"""Fail if the build makes a module built-in that stock ships as =m.

The device keeps its stock system_dlkm, so a built-in copy collides with the .ko at boot.
Options listed in the allow file are accepted.

Usage: config_guard.py --config .config --stock stock.config --allow allow.txt [--mode fail|warn]
Exit codes: 0 ok, 1 new flip (mode fail), 2 check could not run.
"""
import argparse
import pathlib
import re
import sys

LINE = re.compile(r"^(CONFIG_[A-Za-z0-9_]+)=(.*)$")


def parse(path):
    out = {}
    for raw in (
        pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    ):
        m = LINE.match(raw.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def parse_allow(path):
    p = pathlib.Path(path)
    if not p.exists():
        return set()
    return {
        l.split("#", 1)[0].strip()
        for l in p.read_text(encoding="utf-8").splitlines()
        if l.split("#", 1)[0].strip()
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--stock", required=True)
    ap.add_argument("--allow", required=True)
    ap.add_argument("--mode", choices=("fail", "warn"), default="fail")
    a = ap.parse_args()

    try:
        built, stock = parse(a.config), parse(a.stock)
    except OSError as exc:
        print(f"::warning title=config guard skipped::{exc}")
        return 2
    if len(built) < 1000 or len(stock) < 1000:
        print("::warning title=config guard skipped::config files look empty/truncated")
        return 2

    allow = parse_allow(a.allow)
    flips = sorted(k for k, v in stock.items() if v == "m" and built.get(k) == "y")
    new = [k for k in flips if k not in allow]
    stale = sorted(allow - set(flips))

    print(
        f"stock =m, built =y: {len(flips)} total, {len(flips) - len(new)} allowed, {len(new)} new"
    )
    for k in flips:
        print(f"  {'NEW    ' if k in new else 'allowed'} {k}")
    for k in stale:
        print(
            f"::notice title=stale allow entry::{k} is allowed but no longer flips; consider removing it"
        )

    if not new:
        return 0
    msg = (
        "built-in/module flips vs stock (stock system_dlkm still ships the .ko, it will collide): "
        + ", ".join(new)
    )
    print(f"::{'error' if a.mode == 'fail' else 'warning'} title=config guard::{msg}")
    return 1 if a.mode == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
