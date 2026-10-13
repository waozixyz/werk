<p align="center">
  <a href="https://f-droid.org/packages/xyz.waozi.pass/">
    <img src="assets/app/badge-f-droid.png" alt="Get it on F-Droid" height="56">
  </a>
</p>

# Werkzeug

Small private tools in one app. The home screen opens each one:

- **Pass**: a stateless password generator. The same site, login, master
  password and settings always give the same password, so there is no
  password database to keep. It is an independent implementation of the
  LessPass algorithm; compatibility does not imply endorsement by or
  affiliation with the LessPass project.
- **Auth**: two-factor sign-in codes (TOTP, RFC 6238, with SHA-1, SHA-256 or
  SHA-512 and 6 to 8 digits). Add accounts by pasting `otpauth://` links, one
  or many such as an authenticator's plain-text export, or by entering the
  secret key. Tap a code to copy it; it is cleared from the clipboard after
  30 seconds.
- **Calculator**: arithmetic with brackets, powers and percent, by keypad or
  keyboard.
- **Clock**: the local time and date, and a stopwatch that keeps running
  while the app is closed.

The profile holds your name, a picture and the appearance every tool shares:
system, light or dark, an accent color and Material or Classic widgets.

Werkzeug was previously Pass. On its first start it moves Pass's saved
profiles, settings and theme into the new layout; the Android app keeps
Pass's package, so it updates in place and keeps a saved master password.

## Privacy

Everything is computed on the device. Werkzeug makes no network requests and
has no accounts. Each tool keeps its own files, readable only by your user:

| Platform | Data |
|---|---|
| Linux | `$XDG_DATA_HOME/werkzeug` (or `~/.local/share/werkzeug`) |
| Android | the app's private storage |
| Browser | IndexedDB on this site |

Auth's secret keys are stored in its private `accounts.txt` as `otpauth`
links, protected by the file permissions of your account or the Android app
sandbox. Back up that file, or keep your original export, to move accounts to
another device.

## Tools are separate apps

Each tool lives in `apps/<tool>/` and is built into its own portable bundle,
`build/apps/<tool>.zib`. All four are preinstalled. A tool reaches the host
only through the calls in `shared/werkzeug_app.zi` (its private files,
clipboard, clock, key derivation and device-protected secret), and the host
checks every call a bundle asks for before it runs. Tools never import each
other.

## Build and test

Dependencies and the compiler are pinned in `ziran.lock`. Desktop builds need
SDL2, Cairo, FreeType, Fontconfig and Pango development packages; browser
builds need Emscripten; Android builds need JDK 21 and the SDK/NDK versions in
`droid/app/build.gradle`. Desktop tests use Xvfb, xdotool, xclip and
ImageMagick on private displays.

```sh
make gui            # build/werkzeug and the app bundles in build/apps
make test           # Pass core and CLI, Pass state, Auth codes, Calculator
make gui-smoke      # light and dark home screens on a private Xvfb display
make gui-test       # every tool, clipboard and profile on a private display
make site           # build/site: browser app and offline worker
make web-smoke      # private headless Chromium
make android-debug  # ARM32, ARM64 and universal APKs
make android-emulator # the x86_64 APK for a private emulator
```

For development with the real project repositories, create an ignored
`ziran.local.toml`:

```toml
[overrides]
kryon = "../../kryonlabs/kryon"
ziran = "../../ziranlang/ziran"
```

## The `pass` command

```text
pass [OPTIONS] SITE LOGIN [MASTER_PASSWORD]
pass [OPTIONS] PROFILE SITE
```

`make cli` builds it and `make install-cli` installs it. The default password
has 16 characters and includes lowercase letters, uppercase letters, digits
and symbols. Length must be between 5 and 35, matching LessPass clients. The
default counter is 1.

Passing a master password as an argument can expose it to process inspection
and shell history. Omitting it is safer: `pass` first checks
`LESSPASS_MASTER_PASSWORD`, then reads one line from standard input. Use
`--prompt` to bypass the environment and read from standard input:

```sh
pass --prompt example.com alice
pass --length 24 --counter 2 example.com alice
pass --no-symbols --exclude '0O1Il' example.com alice
```

The Linux CLI also reads saved identities from
`$XDG_CONFIG_HOME/pass/profiles.json` (or `~/.config/pass/profiles.json`).
`pass w example.com` and `pass --profile w example.com` use the saved login
and generation options. Existing OpenSSL-encrypted vaults are unlocked with
a hidden `Vault passphrase:` prompt. A configured vault takes precedence over
`LESSPASS_MASTER_PASSWORD`; `--prompt` bypasses it. Explicit flags override
profile defaults. Profiles and vaults are read without changing them.

`--copy` or a profile's `copy` setting copies through `xclip` on X11;
`--clear-after 90s` releases that clipboard selection after the given time
without erasing a later copy from another application. Use `--no-copy` to
print the generated password instead. Run `pass --help` for all flags.

## Source layout

```text
apps/pass/          Pass: LessPass core, settings and profiles, screens, CLI
apps/auth/          Auth: TOTP, otpauth links, accounts and screens
apps/calculator/    Calculator
apps/clock/         Clock and stopwatch
shared/             the app interface, protocol and SHA-256/PBKDF2
src/werkzeug.zi     home screen, profile screen and the bar above a tool
src/apps.zi         loads, checks and runs the app bundles
src/platform.zi     files, clock, clipboard and secrets per platform
src/desktop.zi, src/android_main.zi, src/browser.zi   platform main loops
```

## License

Copyright © 2026 Waozi. Distributed under the BSD 3-Clause License. See
[`LICENSE`](LICENSE).
