# Update Pass to Werkzeug

This updates the existing `xyz.waozi.pass` F-Droid entry. The owner chose an in-place update: retain the original Android package and author signing certificate, show the app as Werkzeug, and preserve existing Pass data.

The separate-package new-app proposal !53912 is superseded by this update. Do not mark this merge request ready without owner approval.

Werkzeug continues the same upstream project with Pass, Auth, Calculator and Clock. Its source is https://github.com/waozixyz/werk and its listing and screenshots are maintained in Fastlane.

## Candidate and remaining work

- Version 0.4.4 (version code 18) is being prepared with the original `xyz.waozi.pass` package. Its release, exact source pin and reference APK still need verification before the recipe is updated.
- Preserve the existing published Pass build entry and author signing certificate.
- The prior comparison differed only in each native library's build-ID note. The fix disables that note as documented by F-Droid. Both ARM32 and ARM64 libraries rebuilt in different native build directories now match the local candidate APK byte for byte; comparison against the published signed APK in F-Droid remains pending.
- Rerun the update check against the published compatible release tag.
- Resolve the missing explicit licenses in Apps, Entity, Daochi Client and Crypto, and the source-library template exceptions before review.

This remains a Draft update, not an approved or published F-Droid release.
