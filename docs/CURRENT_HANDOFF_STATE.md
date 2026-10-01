# Current Google AI Studio Handoff State

## Exact source state

- Repository: `koroper/lotto-recommendation-lab-mobile`
- Branch: `main`
- Last code-changing build-gate commit: `b8a6b6fbbf373ab71cdf884b3e01ab53a8619120`
- CI run: `36817345909`
- CI conclusion: **SUCCESS**

## Verified before AI Studio import

GitHub Actions successfully completed all of the following on the code state above:

1. Python 3.13 setup
2. JDK 17 setup
3. Stable Android SDK 36 installation
4. Gradle 9.3.1 setup
5. Mobile engine regression + frozen Desktop v5.4 parity validation
6. Android static audit
7. `gradle --no-daemon :app:assembleDebug`

Therefore, the imported repository is known to compile into a debug APK in a clean Linux CI environment using the same Gradle version currently provided by Google AI Studio.

## AI Studio compatibility decision

Google AI Studio's current Native Android environment invokes Gradle 9.3.1. Android Gradle Plugin 9.2.x requires Gradle 9.4.1, so the project intentionally pins:

- Android Gradle Plugin `9.1.1`
- Gradle `9.3.1` for CI parity with AI Studio
- Kotlin Compose plugin `2.2.10`
- Chaquopy `17.0.0`
- Python `3.13`

AGP 9.1.1 officially supports Gradle 9.3.1, so this avoids an AI-Studio-only build failure without changing application behavior or the recommendation engine.

## Stable Android / Compose dependency decision

The project intentionally stays on stable `compileSdk = 36`.

The September 2026 Compose line was removed because Compose 1.12 requires compileSdk 37, while the stable SDK manager used by the current CI runner does not expose `platforms;android-37` as an installable stable package.

The project pins:

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

1. import/sync this existing repository in Native Android mode;
2. build the imported source without dependency migration;
3. launch in the browser Android emulator;
4. verify runtime/UI/data/SQLite flows;
5. fix only defects reproduced in the emulator;
6. report exact verification evidence.

No physical-phone install is required for this gate.
