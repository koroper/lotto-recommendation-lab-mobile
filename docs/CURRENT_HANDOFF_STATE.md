# Current Google AI Studio Handoff State

## Exact source state

- Repository: `koroper/lotto-recommendation-lab-mobile`
- Branch: `main`
- Build-gate commit: `988a96e4104b197d326a277c504351d68ad51085`
- CI run: `36807990158`
- CI conclusion: **SUCCESS**

## Verified before AI Studio import

GitHub Actions successfully completed all of the following on the exact commit above:

1. Python 3.13 setup
2. JDK 17 setup
3. Stable Android SDK 36 installation
4. Gradle 9.4.1 setup
5. Mobile engine regression + frozen Desktop v5.4 parity validation
6. Android static audit
7. `gradle --no-daemon :app:assembleDebug`

Therefore, the imported repository is already known to compile into a debug APK in a clean Linux CI environment.

## Important dependency decision

The project intentionally stays on stable `compileSdk = 36`.

The September 2026 Compose line was removed because Compose 1.12 requires compileSdk 37, while the stable SDK manager used by the current CI runner does not expose `platforms;android-37` as an installable stable package.

The project now pins:

- Compose UI `1.9.5`
- Compose Foundation `1.9.5`
- Material3 `1.4.0`
- Activity Compose `1.12.0`
- Lifecycle `2.10.0`
- targetSdk `36`
- compileSdk `36`

Do not upgrade these simply because newer versions exist. Upgrade only when a verified feature need or security/build requirement justifies it and a stable SDK/CI path exists.

## AI Studio first-session goal

Do not redesign the app and do not redo dependency migration.

The first AI Studio session is strictly:

1. import this existing repository;
2. select Native Android;
3. build the exact imported commit;
4. launch in the browser Android emulator;
5. verify runtime/UI/data/SQLite flows;
6. fix only defects reproduced in the emulator;
7. report exact verification evidence.

No physical-phone install is required for this gate.
