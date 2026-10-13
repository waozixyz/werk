# Werkzeug repository rules

Werkzeug (formerly Pass) is a public repository. Read `~/Projects/AGENTS.md`
first.

## Tools are separate apps

- Each tool lives in `apps/<tool>/` and builds into its own bundle,
  `build/apps/<tool>.zib`. A tool reaches the host only through
  `shared/werkzeug_app.zi`; the host (`src/apps.zi`) checks every call a
  bundle asks for and keeps each tool's files, assets and secret separate.
- Tools never import another tool's modules. Code two tools need goes in
  `shared/`, as SHA-256 and PBKDF2 do.
- Keep the host interface small and generic (files, clock, clipboard,
  key derivation, device secret, input). A new host call needs a new host
  build before any bundle can use it.
- Work the portable interpreter cannot do fast enough, such as Pass's
  100,000 PBKDF2 rounds, is a native host capability, never a step-limit
  increase.

## Data and secrets

- Never commit, print or log a real master password, Auth secret, otpauth
  link, export file or current code. Tests use fixture values only, such as
  the RFC 6238 keys.
- Keep Pass's on-disk formats and the Android package `xyz.waozi.pass`:
  existing installations update in place and keep their saved master
  password. `src/migrate.zi` moves Pass's old files once; keep it.
- Every file Werkzeug writes is private (0600 in 0700 folders).

## Platforms and tests

- Ziran only: C, Wasm and the browser loaders are compiler outputs. The
  Android app has no Java (`hasCode=false`); it reaches the platform through
  JNI from Ziran.
- Desktop tests run on private Xvfb displays (`make gui-smoke gui-test`),
  the browser test in private headless Chromium (`make web-smoke`), and
  Android tests only on a private emulator (`make android-input-test`),
  never on a connected phone.
- Run `make test` and `ziran fmt --check` before committing.
- Releases follow `~/Projects/AGENTS.md`: add the numeric entry to
  `CHANGELOG.md` and run `./update_version.sh`; only the release workflow
  creates tags.
