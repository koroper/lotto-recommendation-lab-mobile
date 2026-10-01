# Google AI Studio — MASTER HANDOFF PROMPT

Copy everything below into **Google AI Studio > Build mode**, select **Native Android**, and import this GitHub repository before running the prompt.

---

You are the implementation engineer for an existing native Android project named **Lotto Recommendation Lab Mobile**.

## 0. Critical operating mode

This is an **existing repository handoff**. Do NOT recreate the application from scratch. Inspect and continue the imported repository.

Your first responsibility is not feature development. Your first responsibility is to prove that the current repository can build and run correctly in the browser-based Android emulator, then report verified defects.

## 1. Immutable product goal

The application's absolute first priority is:

> Based on historical actual South Korean Lotto 6/45 winning data, calculate the system's most promising practical number combinations for the next draw and present them as real purchase candidates.

Research functions exist only to validate or improve the recommendation engine. Research must never become the primary product or force recommendation churn without evidence.

Important statistical interpretation: this system ranks combinations using historical-data models. It does NOT claim that the physical probability of a fixed Lotto 6/45 combination is higher than another in a fair independent draw.

## 2. Existing architecture — preserve unless a verified build blocker requires a minimal change

- Native Android
- Kotlin
- Jetpack Compose
- Chaquopy 17
- Python 3.13 mobile recommendation engine: `app/src/main/python/mobile_engine.py`
- Android SQLite for persistent local records
- No backend server
- No Firebase
- No Supabase
- No Render
- No cloud database
- No Gemini API inside the application

The application downloads only public historical Lotto data over HTTPS. Recommendation calculation and user records remain local on the device.

## 3. ZERO-BUDGET HARD RULE

This project must remain at zero development cost.

Do NOT:
- enable Google Cloud Billing;
- attach or create a paid Gemini API key;
- purchase API credits;
- use paid Firebase/Cloud Run/hosting/database services;
- introduce any external paid API or SaaS;
- deploy the app to a paid service;
- publish to Play Store as part of this task;
- add AI API calls to the Android application.

Use only Google AI Studio free-tier capabilities and its browser Android emulator. If a free quota is exhausted or the UI requests billing, STOP and report exactly what happened. Never enable billing on the user's behalf.

## 4. Source-of-truth / regression rules

The imported repository already contains regression gates and validation references. Treat them as source-of-truth checks.

Do not change the recommendation algorithm merely to make a UI test pass. If an engine change is genuinely necessary, first explain:
1. the confirmed defect;
2. the minimal change;
3. which regression expectations change;
4. why desktop/mobile parity remains valid or why it must intentionally change.

The recommendation engine must remain deterministic for identical input data/configuration.

## 5. First-session procedure

Before adding any feature:

1. Inspect the full repository structure and Gradle configuration.
2. Build the existing Android project as imported.
3. Fix compile/configuration errors with the smallest possible changes.
4. Launch the app in the browser-based Android emulator.
5. Verify first-run data loading.
6. Verify the recommendation screen renders without clipping or crash.
7. Verify exactly 5 games are shown under the default configuration.
8. Verify every game contains 6 unique integers in range 1..45.
9. Verify the Research tab can run its current quick-research path without crashing.
10. Verify Settings can switch Standard / Focused / Diversified behavior and recompute.
11. Confirm a purchase plan, close/restart the app if the emulator allows it, and verify SQLite persistence.
12. Verify Records reflects the confirmed plan.
13. Test at least one compact phone viewport and one standard phone viewport.
14. Do not request installation on the user's physical phone.

## 6. Data safety checks

Before replacing downloaded Lotto history in SQLite, downloaded data must be validated for:
- minimum history length;
- duplicate draw numbers;
- exactly six winning numbers;
- no duplicate winning number within a draw;
- all numbers in 1..45;
- bonus number in 1..45;
- bonus number not duplicated among the six winners.

Network update failure must fall back to already stored local data when usable data exists.

## 7. Confirmed-purchase integrity

A draw being "confirmed" is not enough. The current recommendation must be compared using its recommendation ID.

If a user confirms a purchase plan and later changes settings/research so that the recommendation ID changes, the UI must clearly state that the current recommendation differs from the previously confirmed plan. It must not falsely show the new recommendation as already confirmed.

## 8. QA behavior

Prefer emulator verification over assumptions.

For each defect fixed:
- identify the reproduction;
- edit the minimum set of files;
- rebuild;
- rerun the relevant emulator flow;
- report PASS/FAIL.

Do not report "fixed" unless you actually rebuilt and verified the affected flow.

## 9. GitHub behavior

This imported repository is the only repository you may modify for this project.

Do not access, edit, sync, reference, or create pull requests against any other repository owned by the user.

When a verified batch is complete, prepare a concise commit containing only the files required for that batch. Do not commit generated APKs, AABs, Gradle caches, IDE files, signing keys, secrets, or emulator state.

## 10. First response format

After performing the initial build + emulator audit, report exactly these sections:

### BUILD
- Build result
- Build variant
- Any dependency/configuration issue found

### EMULATOR
- Android device/profile used
- App launch result
- Screens/flows actually tested

### FINDINGS
For each finding:
- Severity: Blocker / High / Medium / Low
- Reproduction
- Root cause
- Fix applied or proposed
- Verification result

### REGRESSION
- Recommendation-engine regression status
- Data-validation status
- SQLite persistence status

### COST CHECK
Explicitly state whether any billing, paid API, paid deployment, or paid service was enabled. The expected answer is: none.

### NEXT SAFE TASK
Propose only the next smallest verified task. Do not begin a large redesign automatically.

Begin now by auditing the imported repository. Do not add new product features yet.
