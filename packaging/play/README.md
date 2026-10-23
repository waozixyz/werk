# Google Play testing

The public app is **Werkzeug**, package `xyz.waozi.pass`. Preserve the existing
release certificate. This package updates the existing Pass app
(`xyz.waozi.pass`) in place and keeps its private data. A separate
`xyz.waozi.werk` installation remains separate and untouched.

`make android-bundle` builds a release AAB for both ARM architectures, targeting
Android 16/API 36. Supply the existing `keystore.*` Gradle properties to sign it;
without them it is an unsigned build artifact. Never upload an unsigned bundle.
The manual Play bundle workflow signs with the repository's existing Android
release secrets and retains the candidate as an Actions artifact.

Use `listing.json` and the upstream Fastlane listing to create the app in Play
Console. Start with **Internal testing**, which supports up to 100 testers. The
owner must choose the tester email list or Google Group. Record the actual app
and opt-in URLs after creation. No public production rollout is configured.

Review the exact bundle and testing release before making it available to
testers. Internal testing can begin before the full production listing is
complete, and internal-only releases are exempt from the Data safety section.
Before closed/open testing or production, complete the store text, images,
privacy policy, account-deletion requirements, target audience, ads declaration,
content rating and Data safety answers. Accept Play terms only with owner
authorization. Tools work locally without an account; optional account/sync
connects to the chosen Daochi node. Do not declare that the app never connects
or that the node receives no identifiers. Biometric unlock stays on the device.

If Play App Signing is enabled, preserve the existing signing identity for
cross-store compatibility rather than silently generating a different app key.
An upload key and an app-signing key have different roles.

References: [create an app](https://support.google.com/googleplay/android-developer/answer/9859152),
[testing tracks](https://support.google.com/googleplay/android-developer/answer/9845334),
[target API](https://support.google.com/googleplay/android-developer/answer/11926878).
