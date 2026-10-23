# Werkzeug F-Droid status

The owner chose `xyz.waozi.werk` as a separate Android installation after
reviewing the reinstall requirement on 2026-10-23. Preserve the existing release
signing key and leave legacy Pass installations and data untouched.

- [x] Use the correct Android application ID and Werkzeug display name.
- [x] Open the [new-package draft](https://gitlab.com/fdroid/fdroiddata/-/merge_requests/53912) using the current official new-app template.
- [x] Close the superseded old-ID draft.
- [x] Validate the metadata locally with `fdroid lint` and `fdroid rewritemeta`.
- [ ] Finish source-build and reproducibility verification against the published reference APK.
- [ ] Resolve missing explicit licenses in author-maintained source dependencies.
- [ ] Resolve or explain all GitLab pipeline results and source-library template exceptions.
- [ ] Obtain owner approval before marking the merge request ready for review.
- [ ] Verify catalog publication after maintainers merge and F-Droid publishes it.

[Recipe](metadata/xyz.waozi.werk.yml) · [Merge-request text](MERGE_REQUEST.md)

No F-Droid catalog publication is implied by a source build or draft request.
