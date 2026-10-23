# Werkzeug development and data

[Back to Werkzeug](../README.md).

## Privacy

Everything is computed on the device. Werkzeug makes no network requests
unless you set up sync or explicitly request an account or device-link action.
Each tool keeps its own files, readable only by your user:

| Platform | Data |
|---|---|
| Linux | `$XDG_DATA_HOME/werk` (or `~/.local/share/werk`) |
| Android | the app's private storage |
| Browser | IndexedDB on this site |

Auth's accounts are synced records: `otpauth` links in the private
`records/auth.txt`, protected by the file permissions of your account or the
Android app sandbox.

## Sync

Profile uses the shared Self bundle. Desktop Account management shows the
public ID, alias, sync status and queued changes, and provides account creation,
key-file import, backups, device linking and logout. Switching accounts asks
whether to keep and merge local Auth records or replace them. A private rollback
journal preserves the previous key and records if a switch is interrupted.

The account can use a [Daochi](https://github.com/kryonlabs/daochi) node,
`api.waozi.xyz` by default. Tools work locally without an account. Saved nodes
and the preferred node live in Profile → Nodes; choosing a node preserves the
account and its paused state. The sync switch pauses automatic synchronization
and stays paused after restarting. Logout keeps local Auth records.

Desktop key backups retain Werkzeug's Auth vault key as protected recovery
context. Use a passphrase to encrypt the backup. Importing a legacy account key
for the already-connected identity preserves its existing vault key. The shared
QR workflow also preserves that context and asks both devices to compare digits
before connecting. Legacy clients cannot read the extended QR payload when
Werkzeug vault context is included.

Desktop Self and participating native apps share public profile preferences only
for the same verified account ID. Account keys and Auth records stay in the
host's private store. Android retains its existing native Account screen and
legacy device-link flow; browser account sync is unavailable.

The embedded web app (`/app/?mini`) opens on Home with every tool, and also
provides Profile. Use `?mini&app=pass`, `auth`, `calculator` or `clock` to
open a particular tool first. Browser sync is currently unavailable.

- Each record is sealed on the device with XChaCha20-Poly1305 under a random
  vault key that is never sent to the node unencrypted. The seal covers the
  account, the record and the time of the change, so the server can neither
  read nor alter a record or a removal.
- The account key (ML-DSA-44) signs in and signs each sync together with
  the device's own Ed25519 key.
- Desktop device linking uses the shared Self QR/code exchange with X25519
  and encrypted key transfer. Confirm the matching number on both devices.
  Android's existing 12-character connection code remains available in its
  native account screen.
- The server can still withhold changes or serve an older copy to a device
  that has not seen a newer one. A lost device keeps the keys it had: stop
  syncing there if you can, and replace two-factor secrets you care about.

`scripts/sync_e2e_test.sh` runs two devices against a local Daochi node.

## The `werk sync` and `werk auth` commands

On Linux, the same data works without a window, for devices without a
screen and for scripts:

```text
werk sync status | create | show | join [CODE] | key [FILE] | now
werk auth list
werk auth code ID
werk auth import [FILE]
werk auth rename ID SERVICE ACCOUNT
werk auth sites ID [WEBSITE ...]
werk auth remove ID
```

`werk sync show` prints a code for another device to enter; `werk sync join`
reads one from its argument or standard input. `werk sync key` signs in with
an account key from FILE or standard input; for a key with a passphrase, give
FILE and the passphrase on standard input. `werk auth list` prints the
accounts as JSON with their ids and websites, never their secrets.
`werk auth code ID` prints the current code and the seconds it stays valid.
`werk auth import` reads a file, or standard input: otpauth links, Google
Authenticator export links, an unencrypted Aegis export, or a PNG or JPEG of
an export's QR code when GdkPixbuf and ZBar (`libzbar0`) are installed.
Changes sync right away when the device has an account. `werk --app auth`
opens the window on one tool, as Harmony's Auth entry does.

## Tools are separate apps

Each tool lives in `apps/<tool>/` and is built into its own portable bundle,
`build/apps/<tool>.zx`. All four are preinstalled. A tool reaches the host
only through the calls in `shared/werk_app.zi` (its private files,
clipboard, clock, key derivation and device-protected secret), and the host
checks every call a bundle asks for before it runs. Tools never import each
other.

## Build and test

Dependencies and the compiler are pinned in `ziran.lock`. Desktop builds need
SDL2, Cairo, FreeType, Fontconfig, Pango, GTK 3 and X11 development packages.
Workbook uses the installed Gnumeric library; file choosers need Zenity. Browser
builds need Emscripten; Android builds need JDK 21 and the SDK/NDK versions in
`droid/app/build.gradle`. Desktop tests use Xvfb, xdotool, xclip and
ImageMagick on private displays.

```sh
make gui            # build/werk and the app bundles in build/apps
make install-gui    # Werkzeug and each tool in the app menu and on the desktop
make test           # Pass/CLI, Auth, Calculator and private account recovery fixtures
make gui-smoke      # light and dark home screens on a private Xvfb display
make gui-test       # every tool, clipboard and profile on a private display,
                    # and werk auth without one
make site           # build/site: browser app and offline worker
make web-smoke      # private headless Chromium
make android-debug  # ARM32, ARM64 and universal APKs
make android-fdroid # unsigned F-Droid candidate, same Android ID and version
make android-emulator # the x86_64 APK for a private emulator
```

Linux installs include separate Pass, Auth, Calculator, Clock and Workbook
launchers, each with its own icon. They open the selected tool directly and
share Werkzeug's existing private data. `make install-gui` also adds shortcuts
to the desktop folder configured by `xdg-user-dir`; set `DESKTOP_DIR=` to skip
those shortcuts. Debian packages include the same application-menu entries.

F-Droid metadata is maintained in `packaging/fdroid`. The `android-fdroid`
target disables developer signing even when a release keystore is configured
and writes `build/fdroid/werk.apk` for comparison with the signed release. It adds no version or
package suffix, preserving existing installations and reference-APK checks.
The unsigned candidate is for builders, not installation. Werkzeug currently
has no built-in updater: F-Droid or your chosen installer handles updates.
Android requires the same signing certificate for an in-place update; the
F-Droid recipe retains the developer-signature reproducibility requirement.

The [F-Droid TODO](../packaging/fdroid/TODO.md) records completed checks, the
remaining submission/reproducibility steps and the prepared merge-request text.

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
apps/auth/          Auth: TOTP, otpauth links, exports, accounts and screens
apps/calculator/    Calculator
apps/clock/         Clock and stopwatch
shared/             the app interface, protocol and SHA-256/PBKDF2
src/werk.zi     home screen, profile screen and the bar above a tool
src/apps.zi         loads, checks and runs the app bundles
src/platform.zi     files, clock, clipboard and secrets per platform
src/desktop.zi, src/android_main.zi, src/browser.zi   platform main loops
src/command.zi      werk sync and werk auth without a window
```

## License

Copyright © 2026 Waozi. Distributed under the BSD 3-Clause License. See
[`LICENSE`](../LICENSE).
