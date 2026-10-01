# Zero-Cost Development Policy

This public repository is intended to stay within zero-cost development paths.

- Do not add paid cloud services.
- Do not add Firebase, Supabase, Render, Gemini API, or other hosted runtime dependencies to the app.
- The Android app must remain standalone and local-first.
- Internet access is only for retrieving public Lotto draw data.
- GitHub Actions must use standard public-repository hosted runners only.
- If a workflow or external tool would require billing, stop before enabling it.
- Google AI Studio is used only as a development/build/QA assistant; do not embed a Gemini API dependency in the application.
