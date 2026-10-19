# Werkzeug F-Droid TODO

Updated 2026-10-19. The recipe now targets the public Werkzeug 0.4.0 release
(Android versionCode 14) with new store text and screenshots. GitLab
authentication is still blocked and no new merge request has been created.

## Prepared and verified

- [x] Confirm the [original Pass submission](https://gitlab.com/fdroid/fdroiddata/-/merge_requests/46404)
  was merged and its [0.2.9 reproducible build](https://monitor.f-droid.org/builds/log/xyz.waozi.pass/10) succeeded.
- [x] Rename the listing to Werkzeug and pin 0.4.0's toolchain and nine
  source dependencies, including Self and its QR code library.
- [x] Drop 0.3.0 and 0.3.1: their locks pin dependency commits that the
  2026-10-19 history rewrite removed upstream, so they cannot be rebuilt.
- [x] Replace the old Pass screenshots with Werkzeug's home screen and tools.
- [x] Verify the public 0.4.0 universal APK: package `xyz.waozi.pass`,
  versionCode 14, label Werkzeug, both ARM ABIs and the allowed signing
  certificate. The recipe pins its tagged commit. `make android-fdroid`
  builds the unsigned F-Droid candidate from the same lock.

## Resume the F-Droid submission

1. [ ] Restore GitLab sign-in. The existing ThinkPad spare-browser viewer
   is paused for manual sign-in; resume automation after the owner confirms.
2. [ ] Refresh upstream metadata and search open merge requests for an
   existing Werkzeug update before creating another one.
3. [ ] Submit the metadata and source-library definitions as a **draft**
   using [the prepared merge-request text](MERGE_REQUEST.md). Record its URL here.
4. [ ] Run the full F-Droid source build and reproducibility comparison
   against the signed public 0.4.0 reference APK. Resolve any CI/build differences.
5. [ ] Verify update compatibility: preserve `xyz.waozi.pass`, the existing
   allowed signing certificate, and the release's versionName/versionCode.
   Keep `-fdroid` in the output filename only.
6. [ ] Once reproducibility and CI pass, request maintainer review. Track
   the merge and verify Werkzeug's actual catalog availability separately.

Merge request URL: pending submission.

## Later

- [ ] Unfinished Clock/alarm work waits in the git stash "clock features
  WIP 2". It is not part of 0.4.0; preserve it.

## Handoff files

- [Build metadata](metadata/xyz.waozi.pass.yml)
- [Pinned source-library definitions](srclibs/)
- [Draft merge-request text](MERGE_REQUEST.md)
- Local unsigned candidate: `make android-fdroid`

The unsigned candidate is a build artifact, not an installable release.
