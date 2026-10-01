# Google AI Studio — FIRST BUILD + EMULATOR AUDIT PROMPT

Use this only if the master handoff has already been given and the repository is loaded.

---

Execute the first build gate now.

Constraints:
- Zero budget. Free tier only.
- Do not enable billing or paid APIs.
- Do not deploy/publish.
- Do not add Gemini API to the app.
- Do not touch any repository other than the currently imported Lotto mobile repository.
- Do not ask me to install an APK on a physical phone.
- Preserve the recommendation algorithm unless a verified build/runtime defect requires a minimal fix.

Required work:
1. Build the current project.
2. Resolve only confirmed build blockers.
3. Launch it in the browser Android emulator.
4. Test first-run data download and fallback behavior where feasible.
5. Verify default recommendation renders 5 games, six unique 1..45 numbers per game.
6. Verify Recommendation, Research, Records, and Settings navigation.
7. Run quick research and verify the UI returns to a stable state.
8. Confirm the current purchase plan and verify persistence after an app restart/relaunch.
9. Change a recommendation-affecting setting and verify the UI no longer treats the changed recommendation as the already-confirmed one.
10. Test a compact phone viewport and a normal phone viewport for clipping/overflow.
11. Rebuild after fixes.

Do not add new features in this pass.

At the end, give me:
- exact files changed;
- exact build result;
- emulator device/API level;
- each tested flow with PASS/FAIL;
- unresolved defects;
- confirmation that no paid service or billing was enabled;
- a suggested commit message.
