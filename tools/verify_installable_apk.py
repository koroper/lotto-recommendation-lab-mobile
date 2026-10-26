#!/usr/bin/env python3
"""Refuse to approve an APK unless its installed-app identity and signer match.

This tool never installs, uninstalls, backs up, or reads private application data.
Requires Android SDK aapt and apksigner on PATH, or their absolute paths as arguments.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path


def normalize_cert(value: str) -> str:
    value = re.sub(r"[^0-9a-fA-F]", "", value).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a 64-hex-digit SHA-256 certificate fingerprint")
    return value


def parse_badging(value: str) -> tuple[str, int]:
    line = next((s for s in value.splitlines() if s.startswith("package: ")), "")
    package = re.search(r"\bname='([^']+)'", line)
    version = re.search(r"\bversionCode='(\d+)'", line)
    if not package or not version:
        raise ValueError("Cannot read package name/versionCode from aapt output")
    return package.group(1), int(version.group(1))


def parse_signer(value: str) -> str:
    matches = re.findall(
        r"Signer #\d+ certificate SHA-256 digest:\s*([0-9a-fA-F:]+)",
        value, re.IGNORECASE
    )
    if len(matches) != 1:
        raise ValueError("Expected exactly one APK signer; got " + str(len(matches)))
    return normalize_cert(matches[0])


def command_output(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            args[0] + " exited " + str(result.returncode) + ": " +
            (result.stderr or result.stdout).strip()[-1200:]
        )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", help="Official APK path, not a preview APK")
    parser.add_argument("--expected-cert", required=True,
                        help="SHA-256 certificate fingerprint from the EXISTING phone app")
    parser.add_argument("--min-version", type=int, default=3)
    parser.add_argument("--aapt", default="aapt")
    parser.add_argument("--apksigner", default="apksigner")
    args = parser.parse_args()
    try:
        expected = normalize_cert(args.expected_cert)
        apk = Path(args.apk)
        if not apk.is_file():
            raise ValueError("APK not found: " + str(apk))
        package, version = parse_badging(command_output(
            [args.aapt, "dump", "badging", str(apk)]
        ))
        cert = parse_signer(command_output(
            [args.apksigner, "verify", "--print-certs", str(apk)]
        ))
        if package != "com.lotto.lab":
            raise ValueError("Wrong package: " + package + " (preview APK is not an update)")
        if version < args.min_version:
            raise ValueError("versionCode below minimum: " + str(version))
        if cert != expected:
            raise ValueError("SIGNATURE MISMATCH: installed-app certificate differs")
        print("PASS: package=com.lotto.lab versionCode=" + str(version))
        print("PASS: signing certificate matches existing phone app: " + cert)
        print("This is a static APK preflight, NOT a completed on-phone installation.")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print("HOLD: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
