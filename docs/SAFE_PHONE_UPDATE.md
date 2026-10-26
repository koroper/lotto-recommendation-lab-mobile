# Device update: signing-identity safety gate

This document is for an **existing Android app** with important confirmed-ticket records. The app's official package is `com.lotto.lab`. The independently installed emulator package is `com.lotto.lab.preview`.

## Never do these

- Do not uninstall or clear data for `com.lotto.lab` on the real phone.
- Do not assume an emulator's signing certificate matches the real phone.
- Do not install a `.preview` APK as a device update.
- Do not commit, push, paste into AI prompts, or publish `debug.keystore`, `*.base64`, signing passwords, private keys, or phone backups.
- Do not call the update a PASS until the real phone's saved confirmed tickets have been checked after installation.

## 1. Obtain the actual installed phone certificate (read-only)

Connect the **real phone** to a Windows computer with USB debugging permitted, and the Android SDK platform tools/build tools available. In PowerShell:

```powershell
adb devices
adb shell pm path com.lotto.lab
```

The second command returns at least one `package:/data/app/.../base.apk` path. Copy only that **base.apk** path (without the `package:` prefix) for:

```powershell
adb pull "<exact remote base.apk path>" .\lotto-installed-base.apk
& "<Android SDK build-tools path>\apksigner.bat" verify --print-certs .\lotto-installed-base.apk
```

Record the existing app's **Signer #1 certificate SHA-256 digest**. This pulls the APK only, **not** the private SQLite DB. If `adb pull` is blocked by phone permissions, STOP. Do not root the phone or delete the app.

A previous *emulator* used certificate `F0:0E:03:7C:...` and the **locally preserved** project key reports `6B:97:B6:E0:...`. We do **not** know the real phone's certificate yet.

If the real phone has `F0:0E:...` and that private key cannot be recovered, ordinary in-place update using `6B:97:...` is impossible. Mark **HOLD** and preserve the data.

## 2. Build an official package with the preserved project key

Only after checking the installed cert, use a local machine or AI Studio workspace that privately retains the **matching** root `debug.keystore`. This file is excluded by `.gitignore` and must not go to the public GitHub repository.

The default debug build in CI is **not** approved for real-phone distribution. To opt in to the safe device-update signing mode:

```bash
gradle --no-daemon :app:assembleDebug -PlottoDeviceUpdate=true
```

The opt-in mode:
- produces package `com.lotto.lab` (no preview suffix);
- requires root `debug.keystore`, refusing to build if it is missing;
- signs with the preserved debug alias (`androiddebugkey`, standard local debug passwords by default);
- accepts optional **local process environment** variables `LOTTO_KEYSTORE_PASSWORD`, `LOTTO_KEY_ALIAS`, `LOTTO_KEY_PASSWORD`, never GitHub-committed values.

For a **separate emulator preview**, use `-PlottoPreview=true` instead. These two build flags cannot be combined.

## 3. Verify the generated APK against the real phone

Use the EXACT full SHA-256 value observed in section 1:

```bash
python tools/verify_installable_apk.py app/build/outputs/apk/debug/app-debug.apk --expected-cert "FULL_INSTALLED_PHONE_SHA256"
```

The preflight calls Android SDK `aapt dump badging` and `apksigner verify --print-certs`, refusing a wrong package, undersized versionCode or mismatched certificate. Supply `--aapt` and `--apksigner` with full executable paths if these are not on PATH.

**This static preflight is necessary, not sufficient**: it cannot test the actual phone's installer or prove preservation of SQLite data. Check device compatibility (Android SDK >= 26 and an ABI in `arm64-v8a` or `x86_64`), and confirm the phone-installed versionCode is below or equal to the APK's.

## 4. Only after preflight PASS: update in place, never uninstall

Transfer the official `com.lotto.lab` APK to the phone, tap **Update**, or run `adb install -r <path to verified APK>`. If installation fails, STOP: keep the existing app installed and collect the failure reason.

After a successful in-place update, verify:
1. existing confirmed purchase records and research settings still exist;
2. latest 1247 results (2026-10-24) are downloaded;
3. recommended target is 1248 (as of 2026-10-26);
4. Settings refresh, Research and Records all work;
5. close/reopen the app and confirm records persist.

Only then mark **DEVICE UPDATE PASS**.

## Developer state

- GitHub is authoritative for the build code.
- The `local-work-step3a` AI Studio branch remains a separate local backup and must not be overwritten or blindly merged.
- GitHub CI uses the ordinary secret-free `assembleDebug` as a compilation gate. Its ephemeral debug certificate cannot be assumed safe for real-device updates.
- The original project keystore must be backed up in a private secure location; GitHub `.gitignore` prevents accidental tracking but is **not** a secure backup.
