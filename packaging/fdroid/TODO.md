# Werkzeug F-Droid update status

The owner's latest request is an update of the existing Pass app. Keep `xyz.waozi.pass`, the existing author signing certificate and private app data. The visible name remains Werkzeug. Preserve any separate `xyz.waozi.werk` installation as well.

- [x] Prepare the original Android application ID and matching artifact verifiers.
- [x] Prepare 0.4.4 with version code 18 through `update_version.sh`.
- [x] Build the compatible ARM and private-emulator candidates with matching ZX dependencies and current app bundles.
- [x] Verify both ARM native libraries match byte for byte after independent builds in different directories.
- [ ] Publish the compatible candidate through the normal release workflow and pin its exact source revision in the recipe.
- [ ] Complete source-build and reproducibility verification against its reference APK.
- [ ] Resolve missing explicit dependency licenses and remaining GitLab pipeline results.
- [ ] Obtain owner approval before marking the update ready for review.
- [ ] Verify catalog publication after maintainers merge and F-Droid publishes it.

[Update draft](https://gitlab.com/fdroid/fdroiddata/-/merge_requests/53909) · [Recipe](metadata/xyz.waozi.pass.yml) · [Merge-request text](MERGE_REQUEST.md)

The local recipe is being prepared; its source pin still needs the verified compatible candidate. A Draft or a successful source build does not imply F-Droid catalog publication.
