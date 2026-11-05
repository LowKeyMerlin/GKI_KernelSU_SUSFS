#!/usr/bin/env python3
"""Trust one extra manager signing key in BakaSU's kernel, and nothing else.

BakaSU only compiles a custom key (EXPECTED_SIZE/EXPECTED_HASH) when
CONFIG_KSU_MULTI_MANAGER_SUPPORT is on, and that option also trusts the
tiann/KernelSU and KOWX712/KernelSU keys. xiaomi_17 keeps it off so BakaSU's own
key is the single trusted one, which would also reject our spoofed manager, so
append exactly one row to apk_sign_keys[] instead.

Idempotent and anchor-checked: it fails if BakaSU's table moved, rather than
leaving a spoofed manager the kernel silently refuses.

Usage: bakasu_extra_key.py <apk_sign.c> <size-hex> <sha256-hex>
"""

import re
import sys

ANCHOR = "    { EXPECTED_SIZE_BAKASU, EXPECTED_HASH_BAKASU }, /* Baka-SU/BakaSU */\n"
MARK = "/* xiaomi_17 spoofed manager */"


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit("usage: bakasu_extra_key.py <apk_sign.c> <size-hex> <sha256-hex>")
    path, size, sha = sys.argv[1:]
    if not re.fullmatch(r"0x[0-9a-f]{3,6}", size) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        sys.exit(f"ERROR: malformed key material: size={size!r} sha256={sha!r}")

    with open(path, encoding="utf-8") as f:
        src = f.read()
    row = f'    {{ {size}, "{sha}" }}, {MARK}\n'
    if row in src:
        print(f"  {path}: spoofed manager key already present")
        return
    if MARK in src:
        sys.exit(f"ERROR: {path} already carries a different spoofed manager key")
    if src.count(ANCHOR) != 1:
        sys.exit(f"ERROR: BakaSU key table anchor matched {src.count(ANCHOR)} time(s) in {path}")

    with open(path, "w", encoding="utf-8") as f:
        f.write(src.replace(ANCHOR, ANCHOR + row, 1))

    with open(path, encoding="utf-8") as f:
        out = f.read()
    if out.count(MARK) != 1 or "CONFIG_KSU_MULTI_MANAGER_SUPPORT" not in out:
        sys.exit("ERROR: key row was not written as expected")
    print(f"  {path}: trusting spoofed manager key {size} {sha[:12]}")


if __name__ == "__main__":
    main()
