#!/usr/bin/env python3
"""Write a boot image with a header v4 and a dummy kernel, padded to a partition size.

Usage: mkboot.py OUT [RELEASE DATE [EXTRA]]

With a release and a build date the kernel starts with the line a kernel prints as its version.
EXTRA is appended to the kernel, for example text that marks a rooted kernel.
"""
import os
import struct
import sys

PAGE = 4096
SIZE = 64 << 20


def main():
    out = sys.argv[1]
    kernel = b""
    if len(sys.argv) > 3:
        release, date = sys.argv[2], sys.argv[3]
        kernel = f"Linux version {release} (kleaf@build-host) (clang version 19.0.1) #1 SMP PREEMPT {date}\n".encode()
        kernel += sys.argv[4].encode() + b"\0" if len(sys.argv) > 4 else b""
    kernel += os.urandom(1 << 20)
    header = b"ANDROID!" + struct.pack("<II", len(kernel), 0)
    header += struct.pack("<I", 0)  # os_version
    header += struct.pack("<I", 1580)  # header_size
    header += struct.pack("<4I", 0, 0, 0, 0)  # reserved
    header += struct.pack("<I", 4)  # header_version
    header += b"\0" * 1536  # cmdline
    header += struct.pack("<I", 0)  # signature_size
    header = header.ljust(PAGE, b"\0")
    image = header + kernel
    image = image.ljust(-(-len(image) // PAGE) * PAGE, b"\0")
    with open(out, "wb") as f:
        f.write(image)
        f.truncate(SIZE)


if __name__ == "__main__":
    main()
