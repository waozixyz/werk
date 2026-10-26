#!/usr/bin/env bash
set -euo pipefail

manager=${ANDROID_SDK_MANAGER:-"${ANDROID_HOME:?ANDROID_HOME is required}/cmdline-tools/latest/bin/sdkmanager"}
delay=${ANDROID_SDK_RETRY_DELAY:-10}

accept_licenses() {
    # yes can receive SIGPIPE after sdkmanager exits successfully.
    yes | "$manager" --licenses >/dev/null || test "${PIPESTATUS[1]}" -eq 0
}

retry() {
    local attempt
    for attempt in 1 2 3; do
        if "$@"; then
            return 0
        fi
        if [ "$attempt" -lt 3 ]; then
            echo "Android SDK installer failed; retrying ($attempt/3)" >&2
            sleep "$delay"
        fi
    done
    echo "::error::Android SDK installation failed after three attempts" >&2
    return 1
}

retry accept_licenses
retry "$manager" 'platforms;android-36' 'build-tools;34.0.0' \
    'ndk;28.2.13676358' 'cmake;3.22.1' "$@"
