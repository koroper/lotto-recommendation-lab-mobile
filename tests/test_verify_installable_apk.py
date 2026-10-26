import unittest

from tools.verify_installable_apk import normalize_cert, parse_badging, parse_signer


class ApkPreflightTests(unittest.TestCase):
    def test_accepts_official_badging(self):
        self.assertEqual(
            ("com.lotto.lab", 3),
            parse_badging("package: name='com.lotto.lab' versionCode='3' versionName='1.2-history-fix'\n")
        )

    def test_preview_package_is_distinct(self):
        self.assertEqual(
            ("com.lotto.lab.preview", 3),
            parse_badging("package: name='com.lotto.lab.preview' versionCode='3'\n")
        )

    def test_signer_sha256_normalization(self):
        fingerprint = "6B:97:B6:E0:B3:57:74:3D:4B:EB:68:0F:C2:56:50:7F:ED:E3:99:1F:A3:AF:2C:F0:A2:67:D8:CF:6D:C8:FB:7D"
        output = "Signer #1 certificate SHA-256 digest: " + fingerprint + "\n"
        self.assertEqual(normalize_cert(fingerprint), parse_signer(output))

    def test_refuses_missing_signer(self):
        with self.assertRaises(ValueError):
            parse_signer("Verified using v2 scheme: true")

    def test_refuses_ambiguous_signers(self):
        line = "Signer #1 certificate SHA-256 digest: " + "a" * 64
        with self.assertRaises(ValueError):
            parse_signer(line + "\n" + line.replace("#1", "#2"))

    def test_refuses_invalid_cert_fingerprint(self):
        with self.assertRaises(ValueError):
            normalize_cert("not-a-sha256")

    def test_refuses_invalid_badging(self):
        with self.assertRaises(ValueError):
            parse_badging("application-label:'Lotto'\n")


if __name__ == "__main__":
    unittest.main()
