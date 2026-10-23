# New app: Werkzeug

Draft until the owner explicitly approves review. Android application ID: `xyz.waozi.werk`.
This new package replaces the superseded old-ID draft !53909; it installs separately from legacy Pass and never clears its data.
The candidate is Werkzeug 0.4.3, pinned to the full upstream source revision. The normal release workflow is producing its reference APK.

## Abstract for new app inclusion

### Please introduce the functions and usage of your app in summary, and also attach some screenshots.

Werkzeug brings Pass, Auth, Calculator and Clock together. Generate passwords from a master password and saved site profiles, manage two-factor codes, calculate and keep time. The Linux desktop also includes Workbook and separate tool launchers.

Screenshots are in the [upstream Fastlane listing](https://github.com/waozixyz/werk/tree/master/fastlane/metadata/android/en-US/images/phoneScreenshots).

### Please elaborate why you wrote this app. Please highlight the unique functions it provides over other similar apps in F-Droid.

A collection of small free tools, implemented with the open-source Ziran compiler and Kryon UI. Password generation works locally and Auth supports importing existing account exports. Optional account/node services are explicit features.

## Review notes

- Exact locked source dependencies are fetched as F-Droid source libraries. Automatic recipe generation is disabled because each release requires the complete updated dependency lock.
- The inclusion-policy review found missing explicit license files in four author-maintained dependencies (Apps, Entity, Daochi Client, Crypto). Licensing approval is pending; the policy checkbox remains open until resolved.
- `Binaries` and the existing author signing certificate configure reproducible-build verification. A successful full source build and comparison remain pending.
- Universal ARM32/ARM64 APK retained. Managed source libraries differ from the template's preferred submodule arrangement; maintainer review is still required.
- No RFP issue is claimed or automatically closed.

## Checklist

### Policy

* [ ] The app complies with the [inclusion criteria](https://f-droid.org/docs/Inclusion_Policy).
* [x] The original app author has been notified (and does not oppose the inclusion). If you are not the author, please paste the link of the reply from the author.
* [x] The upstream app source code repo contains the app metadata in a [Fastlane](https://gitlab.com/snippets/1895688) or [Triple-T](https://gitlab.com/snippets/1901490) folder structure. The summary and description must be included and images, icon, and changelog should also be provided for better user experience. The `en-US` locale must be included.

### Docs

* [x] Please read [the guide](https://gitlab.com/fdroid/fdroiddata/-/blob/master/CONTRIBUTING.md) first if this is your first contribution.
* [ ] Please make sure your metadata follows the best practice in [our templates](https://gitlab.com/fdroid/fdroiddata/tree/master/templates).
* [x] Please read the [Build Metadata Reference](https://f-droid.org/docs/Build_Metadata_Reference/) and make sure your metadata is valid.
* [x] Please read the [Quick Start Guide](https://f-droid.org/en/docs/Submitting_to_F-Droid_Quick_Start_Guide/).

### Merge Request Setup

* [x] The title of this merge request should follow "New app: app name" format.
* [x] Please make sure your fdroiddata fork is public and your branch is not protected. See <https://docs.gitlab.com/user/project/repository/branches/protected/>.
* [ ] Please read [our Git guide](https://gitlab.com/fdroid/wiki/-/wikis/Tips-for-fdroiddata-contributors/Git-Usage) if you don't know how to rebase your branch. Don't rebase your branch if there is no conflict.
* [ ] All related [fdroiddata](https://gitlab.com/fdroid/fdroiddata/issues) and [RFP issues](https://gitlab.com/fdroid/rfp/issues) have been referenced in this merge request
* [x] Please only submit one app in one MR.

### Metadata

* [x] Metadata must be put in `metadata/<applicationId>.yml`.
* [x] Metadata must be a valid YAML file.
* [x] Metadata must use LF as line ending.
* [x] Don't add summary/description/changelog/images or anything that should be provided in upstream repo. Please check the Changes tab to make sure there is no other unrelated files added in the MR.
* [x] Releases are tagged and auto update is enabled unless there is a special reason.
* [x] There is an issue tracker and contact info of the author so that we can report bugs and contact the author.
* [x] An AuthorName must be added. It doesn't need to be the real name.
* [ ] External repos are added as git submodules instead of srclibs. You can update git submodules without opening an MR in this repo and the submodule is covered by our scanner.
* [x] Enable [Reproducible Builds](https://f-droid.org/docs/Reproducible_Builds). We'll use your signature for improved security/reliability, also allowing users to switch between different channels. Do note that if you don't enable reproducible build then the apk will be signed with our key so you can't enable it later. If you can't enable this, please add the reasons here.
* [ ] Setup abi split if the APK is large and the splitted ones can be much smaller.
* [x] Only the latest versions should be kept in the metadata before it's merged. If you update the metadata, please replace the old versions with the new ones.
* [x] Don't add any disabled versions in the metadata.
* [x] The `commit` field should be the full hash. Please don't use tag or branch in commit.

### Pipeline

* [ ] All pipelines should pass.
* [ ] All warnings and errors in the Reports tab should be fixed or explained.
* [x] F-Droid CI runners are under GitLab's FOSS program, so there's no need for you to pay for any CI time. If Gitlab starts asking for phone numbers or credit cards don't submit anything, just leave a note in the MR so we know we need to trigger the CI.

---------------------
