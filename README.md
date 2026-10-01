# Lotto Recommendation Lab Mobile

Native Android version of a personal South Korean Lotto 6/45 historical-data recommendation research tool.

## Current stage

**Mobile v1.1 Audited — pre-emulator integration stage**

The project is intentionally local-first:

- Kotlin + Jetpack Compose
- Chaquopy + Python 3.13 recommendation engine
- SQLite local persistence
- No backend server
- No paid cloud service
- No Gemini API inside the app

The immutable product priority is to produce practical next-draw purchase combinations from historical draw data. Research functions are subordinate validation tools and do not represent literal physical winning probabilities.

## Development workflow

1. Python engine regression / desktop parity
2. Android static audit
3. Gradle APK build gate
4. Google AI Studio browser Android emulator QA
5. Physical-device install only for stable candidates

See:

- [`README_KR.md`](README_KR.md) — detailed Korean project documentation
- [`ZERO_COST_POLICY.md`](ZERO_COST_POLICY.md) — zero-budget development constraints
- [`docs/AI_STUDIO_MASTER_HANDOFF_PROMPT.md`](docs/AI_STUDIO_MASTER_HANDOFF_PROMPT.md) — first Google AI Studio handoff
- [`docs/AI_STUDIO_FIRST_BUILD_AUDIT_PROMPT.md`](docs/AI_STUDIO_FIRST_BUILD_AUDIT_PROMPT.md) — first emulator audit task
- [`SELF_VALIDATION_REPORT.md`](SELF_VALIDATION_REPORT.md) — prior local audit notes

## Important

This is a historical-data ranking/research project. In a fair independent Lotto 6/45 draw, every fixed six-number combination has the same physical first-prize probability.

No license is granted by the repository unless a license file is added later by the owner.
