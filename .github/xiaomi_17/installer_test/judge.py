#!/usr/bin/env python3
"""Judge the XT lines of a guest run. Exit 0 pass, 1 fail, 3 no verdict.

Usage: judge.py LOG
"""
import re
import sys

WANT = {
    "stock_rc": "0",
    "stock_logo": "yes",
    "stock_steps": "yes" * 6,
    "stock_result": "yes",
    "stock_upstream_hidden": "yes",
    "stock_marker_leaked": "no",
    "stock_protocol": "yes",
    "terminal_result": "yes",
    "terminal_clean": "yes",
    "terminal_logo": "yes",
    "plain_result": "yes",
    "plain_clean": "yes",
    "plain_logo": "no",
    "plain_title": "yes",
    "stock_credit": "yes",
    "stock_other_warning": "no",
    "stock_patched": "yes",
    "stock_standin_left": "0",
    "stock_ramdisk_size": "0",
    "stock_header_version": "4",
    "pristine_rc": "0",
    "parity_rc": "0",
    "parity_already": "yes",
    "parity_identical": "yes",
    "custom_rc": "0",
    "custom_warned": "yes",
    "custom_patched": "yes",
    "other_rc": "0",
    "other_kept": "yes",
    "single_label": "yes",
    "single_patched": "yes",
    "none_rc": "0",
    "none_skipped": "yes",
    "none_result": "yes",
    "bad_report": "yes",
}


def show(text):
    """Print what the installer said, without the recovery protocol, to the job log."""
    print("::group::installer output", file=sys.stderr)
    for case, line in re.findall(r"^OUT (\w+): (?:ui_print ?)?(.*?)\r?$", text, re.M):
        line = line.rstrip()
        if line.strip() not in ("", "ui_print") and not line.lstrip().startswith(("inflating:", "creating:", "Archive:")):
            print(f"{case:7} {line}", file=sys.stderr)
    print("::endgroup::", file=sys.stderr)


def main():
    text = open(sys.argv[1], errors="replace").read()
    show(text)
    got = dict(re.findall(r"^XT (\w+)=(.*?)\r?$", text, re.M))
    print("| check | wanted | got |\n| --- | --- | --- |")
    if got.get("done") != "yes":
        print("| run finished | yes | no |")
        return 3
    cases = got.get("cases", "").split()
    wants = {k: v for k, v in WANT.items() if ("parity" if k.startswith("pristine") else k.split("_")[0]) in cases}
    if "stock" in cases:
        wants["stock_kernel_size"] = got.get("want_kernel_size")
    bad = False
    for key, want in wants.items():
        ok = got.get(key) == want
        bad |= not ok
        print(f"| {key} | {want} | {got.get(key, 'missing')} {'' if ok else '(wrong)'} |")
    # The release of the other slot must be in the image, once per copy in the kernel.
    for key in ("stock_release_found", "custom_release_found", "single_release_found"):
        if key.split("_")[0] not in cases:
            continue
        ok = got.get(key, "0") not in ("0", "")
        bad |= not ok
        print(f"| {key} | more than 0 | {got.get(key, 'missing')} {'' if ok else '(wrong)'} |")
    if "other" in cases:
        ok = got.get("other_standin_left", "0") not in ("0", "")
        bad |= not ok
        print(f"| other_standin_left | more than 0 | {got.get('other_standin_left', 'missing')} {'' if ok else '(wrong)'} |")
    if "bad" in cases:
        ok = got.get("bad_rc", "0") != "0"
        bad |= not ok
        print(f"| bad_rc | not 0 | {got.get('bad_rc', 'missing')} {'' if ok else '(wrong)'} |")
    print(f"\nUpstream zip alone prints 'bad number': {got.get('pristine_bad_number')}")
    print(f"\nGuest kernel `{got.get('kernel')}`, device warning shown: {got.get('stock_device_warning')}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
