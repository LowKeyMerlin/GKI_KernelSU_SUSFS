#!/usr/bin/env python3
"""Describe the spoofed-manager signing key for the kernel and the manager build.

BakaSU stopped publishing a spoofed manager, so xiaomi_17 builds its own and signs
it with a key kept in repository secrets. The kernel only trusts a manager whose
signing certificate matches a built-in (size, sha256) pair, so both sides need the
same numbers. They are derived here once, from the keystore, instead of being
copied around by hand.

The package name is derived from the certificate hash. It is random-looking, which
is the point of a spoofed package, but stable across builds, so an installed
spoofed manager updates in place instead of appearing as a new app every release.

Environment:
  SPOOF_KEYSTORE           base64 of the keystore (JKS or PKCS12); empty means
                           "not configured" and the script prints nothing, exit 0
  SPOOF_KEYSTORE_PASSWORD  keystore password
  SPOOF_KEY_ALIAS          key alias

Output: one line "<size> <sha256> <package>" where size is hex like the kernel
macros (0x0377). Exit 1 if the keystore is set but unusable, so a typo in a
secret fails loudly instead of shipping a manager the kernel will not trust.

The kernel rejects certificates over 1024 bytes (apk_sign.c CERT_MAX_LENGTH), so
use RSA 2048; a 4096-bit certificate is too large and the manager would never be
trusted. This script enforces the limit.

One-time key creation (keep the file private, then store it base64-encoded):
  keytool -genkeypair -alias spoof -keyalg RSA -keysize 2048 -validity 36500 \
      -storetype PKCS12 -keystore spoof.p12
  base64 -w0 spoof.p12   # -> SPOOF_KEYSTORE; alias -> SPOOF_KEY_ALIAS
"""

import base64
import hashlib
import os
import subprocess
import sys
import tempfile


def package_name(cert_sha256: str) -> str:
    """Derive a stable three-segment package name from the certificate hash.

    Args:
        cert_sha256: lowercase hex sha256 of the DER certificate.

    Returns:
        A name such as "abcdef.ghijkl.mnopqr"; every segment starts with a letter,
        as Android requires.
    """
    digest = hashlib.sha256(cert_sha256.encode()).digest()
    letters = [chr(ord("a") + b % 26) for b in digest[:18]]
    return ".".join("".join(letters[i : i + 6]) for i in (0, 6, 12))


def export_cert(keystore: bytes, alias: str, password: str) -> bytes:
    """Export the DER certificate for `alias` with keytool.

    Raises:
        SystemExit: keytool failed (wrong alias, password or file).
    """
    with tempfile.TemporaryDirectory() as tmp:
        ks, der = os.path.join(tmp, "ks"), os.path.join(tmp, "cert.der")
        with open(ks, "wb") as f:
            f.write(keystore)
        run = subprocess.run(
            ["keytool", "-exportcert", "-alias", alias, "-keystore", ks,
             "-storepass:env", "SPOOF_KEYSTORE_PASSWORD", "-file", der],
            capture_output=True, text=True, check=False,
        )
        if run.returncode != 0:
            sys.exit(f"ERROR: keytool could not read the spoof keystore: {run.stderr.strip() or run.stdout.strip()}")
        with open(der, "rb") as f:
            return f.read()


def main() -> None:
    b64 = os.environ.get("SPOOF_KEYSTORE", "").strip()
    if not b64:
        return
    alias = os.environ.get("SPOOF_KEY_ALIAS", "")
    if not alias or not os.environ.get("SPOOF_KEYSTORE_PASSWORD"):
        sys.exit("ERROR: SPOOF_KEYSTORE is set but SPOOF_KEY_ALIAS or SPOOF_KEYSTORE_PASSWORD is empty")
    try:
        keystore = base64.b64decode(b64, validate=False)
    except ValueError as exc:
        sys.exit(f"ERROR: SPOOF_KEYSTORE is not valid base64: {exc}")
    cert = export_cert(keystore, alias, os.environ["SPOOF_KEYSTORE_PASSWORD"])
    if len(cert) >= 1024:
        sys.exit(f"ERROR: spoof certificate is {len(cert)} bytes; the kernel rejects 1024 or more - use RSA 2048")
    sha = hashlib.sha256(cert).hexdigest()
    print(f"0x{len(cert):04x} {sha} {package_name(sha)}")


if __name__ == "__main__":
    main()
