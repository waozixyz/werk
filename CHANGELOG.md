# Changelog

## [0.4.3] - 2026-10-23

- Werkzeug uses its own Android application ID, `xyz.waozi.werk`.
- Werkzeug installs alongside legacy Pass, preserving the older app and its data.

## [0.4.2] - 2026-10-23

- Linux packages include the libraries needed for sync and importing QR-code pictures.
- Packaging a new AppImage preserves previous downloads.

## [0.4.1] - 2026-10-23

- Open Pass, Auth, Calculator, Clock and Workbook directly from the Linux application menu, each with its own icon.
- Desktop installs add shortcuts for Werkzeug and every tool to your configured desktop folder.
- Tool windows show their own names and icons in the desktop switcher.

## [0.4.0] - 2026-10-19

- A new purple W logo across the app, Android and the website.
- Calculator gets a Scientific mode.
- Auth imports Google Authenticator, Aegis and Ente Auth exports, and on the desktop a picture of their QR code.
- Rename an Auth account, note the websites it signs in to, or remove it.
- Choose your own Daochi node, and pause sync without losing your account.
- On the desktop, Profile manages your account: create it, import or back up its key, and link devices by QR code.
- Sign in with a Daochi account key you already have, such as Inbe's.
- `werk sync` and `werk auth` work without a window on Linux.
- Reach every tool from the web app's mini version.
- Fix the web version freezing when Clock opens.
- Show π, √ and other symbols on phones older than Android 10.
- Fix Profile breaking after choosing a file on desktops whose language writes decimals with a comma.
- The `pass` command unlocks vaults whose text is wrapped with spaces or tabs on systems with OpenSSL 3.0.

## [0.3.1] - 2026-10-13

- Fix the web version on itch.io, which opened to a blank page.

## [0.3.0] - 2026-10-13

- Pass is now Werkzeug: a home screen of small private tools, each its own app and all preinstalled.
- A new logo: a wrench with a keyhole. The website moves to werk.waozi.xyz.
- Add Auth for two-factor sign-in codes from otpauth links or secret keys; copied codes clear after 30 seconds.
- Add Calculator, and Clock with a stopwatch.
- Add a profile with your name, a picture and the appearance every tool shares.
- Sync Auth's accounts between your devices from Profile → Sync: create an account, then connect another device with a 12-character code. Accounts are encrypted on the device; the server never sees them.
- Keep your Pass profiles, settings, theme and saved master password when updating.
- On Android, keep every screen clear of the navigation bar and the keyboard.
- Use Inbe's font, Noto Sans, in the browser and on phones older than Android 10.

## [0.2.10] - 2026-10-05

- Introduce the purple password asterisk and keyhole logo across Pass, website icons, Android launchers, and app listings.

## [0.2.9] - 2026-09-05

- Keep bottom navigation, password controls, and dialog icons readable with
  dark tints in light mode and light tints in dark mode.
- Prevent taps in Theme Settings from reaching fields underneath or opening
  the keyboard when saving the theme.

## [0.2.8] - 2026-08-26

- Match LessPass clients for the same site, login, master password, counter,
  character classes, and length settings.
- Limit password length to LessPass's 5 to 35 character range.
- Require Android fingerprint unlock for saved master passwords and store them
  with an authenticated Android Keystore key.
- Use the Sweet Material palette by default, with Sweet-Dark matched colors in
  dark mode, and show generated passwords in a dedicated output field.
- Keep settings controls fully scrollable above the bottom navigation and use
  the available form width while scrolling.
- Keep theme dropdowns from opening the Android soft keyboard.

## [0.2.7] - 2026-08-24

- Fix Android source builds in stricter environments such as F-Droid builders
  while keeping Kry app source generation automatic.

## [0.2.6] - 2026-08-24

- Keep Android source builds self-contained so F-Droid and other source builds
  generate the Kry app sources automatically.

## [0.2.5] - 2026-08-24

- Add Android appearance settings for following device colors, choosing
  light or dark mode, selecting a color palette, and switching widget style.
- Use Android system Material colors for the app theme, with a stable Material
  fallback instead of the bright pink accent some devices report.
- Recalculate the Android layout cleanly when rotating between portrait and
  landscape, keeping controls clear of system bars and navigation insets.

## [0.2.4] - 2026-08-22

- Save and reuse Android master-password defaults, with fingerprint unlock
  available from the generator and settings screens.
- Clear unlocked master-password text and generated passwords from the Android
  screen after a short timeout.
- Autosave Android generator defaults when length, counter, character classes,
  excluded characters, or biometric display settings change.
- Keep Android form fields visible while the keyboard is open, with better
  spacing around settings and excluded-character controls.
- Run the real Pass app at pass.waozi.xyz/app through the Kryon canvas UI,
  replacing the standalone browser form.
- Publish Android releases as a universal APK plus per-ABI APKs.

## [0.2.3] - 2026-08-21

- Verify every download: releases now ship a SHA256SUMS file covering the
  command-line, desktop, Android, and browser downloads.
- The Android app now builds entirely from source with no developer signing
  key, clearing the way for F-Droid distribution.

## [0.2.2] - 2026-08-20

- Install pass on Android: a signed APK is now downloadable from
  pass.waozi.xyz alongside the desktop, terminal, and browser downloads.
- Fix the Android master-password fingerprint and secure storage so the
  stored master password unlocks reliably across launches.

## [0.2.1] - 2026-08-19

- The desktop GUI now checks for new releases and can update itself: AppImage
  builds download the checksum-verified update and restart straight into it,
  while tarball and Debian package installs get a link to the release page.

## [0.2.0] - 2026-08-18

- Copy passwords through a built-in pure-Go X11 clipboard on Linux, with no
  external clipboard tool required; other systems keep using wl-copy, xclip,
  xsel, pbcopy, or clip.exe.
- Clear copied passwords automatically after a delay with `--clear-after`;
  by default they stay until another application takes the clipboard.
- Read the master password from an OpenSSL-encrypted vault with `--vault`;
  the vault passphrase is asked for on the terminal or read from piped input,
  so the master password never appears in argv or the environment.
- Save named profiles (a login plus default settings) in an optional
  configuration file and generate with `--profile`.
- Print the current clipboard contents with `--read-clipboard`.
- Install the binary as `pass` to use the compact `pass PROFILE SITE` form,
  which copies without printing.

## [0.1.3] - 2026-08-17

- Generate passwords directly on the website's home page: the full browser
  generator now runs in the front-page card, with no separate page to open.
- The browser generator loads only when you start using it, keeping the
  front page fast for everyone else.
- The standalone web app page remains available with the same generator.

## [0.1.2] - 2026-08-17

- Make keyboard navigation reliable: click a field, then use Tab and Shift+Tab
  to move through the form.
- Keep one pass window open by default; launching it again replaces the
  existing window.
- Keep long editing sessions responsive and stable.

## [0.1.1] - 2026-08-17

- Keep text entry responsive and stable during prolonged use.
- Render password symbols and emoji correctly without repeatedly rebuilding fonts.
- Support selecting and replacing text in password and regular text fields.
- Use `xyz.waozi.pass` consistently as the desktop and Android application ID.

## [0.1.0] - 2026-08-17

- Generate deterministic, LessPass-compatible passwords from site, login, and
  master password inputs.
- Configure length, counter, character classes, and excluded characters.
- Read a master password without terminal echo or from an environment variable.
- Copy generated passwords with common desktop clipboard tools.
- Use the optional Kryon desktop interface to generate and briefly copy
  passwords without passing the master password to another process.
- Generate passwords locally in a browser at pass.waozi.xyz.
- Download separate CLI and desktop builds for supported processor
  architectures from the project website.
