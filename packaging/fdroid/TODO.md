# Werkzeug F-Droid TODO

Updated 2026-10-15. The recipe update is prepared locally. Draft submission
is approved, but GitLab authentication is still blocked and no new merge
request has been created. Nothing from this work has been released.

## Prepared and verified

- [x] Confirm the [original Pass submission](https://gitlab.com/fdroid/fdroiddata/-/merge_requests/46404)
  was merged and its [0.2.9 reproducible build](https://monitor.f-droid.org/builds/log/xyz.waozi.pass/10) succeeded.
- [x] Prepare the rename and recipe for the public Werkzeug 0.3.1 release
  (Android versionCode 13), including pinned toolchain/source dependencies.
- [x] Validate metadata formatting, lint, source pins, prebuild commands and
  the public reference APK's identity, label, ABIs and signing certificate.
- [x] Implement and test the selected logo, all-tools mini navigation,
  optional Daochi/custom-node settings, persistent sync pause and unsigned
  F-Droid build mode in the local 0.4.0 app (versionCode 14).

The local app checks cover source/core/CLI compatibility, desktop and browser
UI, encrypted two-device sync, Android builds, and private-emulator input,
node settings and update/data preservation. They do **not** establish that
F-Droid can reproducibly build the 0.3.1 recipe.

## Resume the F-Droid submission

1. [ ] Restore GitLab sign-in. The existing ThinkPad spare-browser viewer
   is paused for manual sign-in; resume automation after the owner confirms.
2. [ ] Refresh upstream metadata and search open merge requests for an
   existing Werkzeug update before creating another one.
3. [ ] Submit the metadata and source-library definitions as a **draft**
   using [the prepared merge-request text](MERGE_REQUEST.md). Record its URL here.
4. [ ] Run the full F-Droid source build and reproducibility comparison
   against the signed public reference APK. Resolve any CI/build differences.
5. [ ] Verify update compatibility: preserve `xyz.waozi.pass`, the existing
   allowed signing certificate, and the release's versionName/versionCode.
   Keep `-fdroid` in the output filename only.
6. [ ] Once reproducibility and CI pass, request maintainer review. Track
   the merge and verify Werkzeug's actual catalog availability separately.

Merge request URL: pending submission.

## Later 0.4.0 release

- [ ] Coordinate the separate, uncommitted Clock/alarm work and verify the
  final release source. Preserve that work during the handoff.
- [ ] Obtain owner approval before publishing the 0.4.0 app release.
- [ ] After that signed release is public, update the recipe to its full
  upstream commit and versioned APK, then repeat the reproducibility checks.
  The current draft must continue to reference public 0.3.1 until then.

## Handoff files

- [Build metadata](metadata/xyz.waozi.pass.yml)
- [Pinned source-library definitions](srclibs/)
- [Draft merge-request text](MERGE_REQUEST.md)
- Local unsigned candidate: `make android-fdroid`

The unsigned candidate is a build artifact, not an installable release.
