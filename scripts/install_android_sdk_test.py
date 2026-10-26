"""Exercise installer retry and failure propagation without network or an SDK."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AndroidSdkInstallerTest(unittest.TestCase):
    def install(self, failures):
        temporary = tempfile.TemporaryDirectory(prefix="werk-sdk-installer-")
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        manager = directory / "sdkmanager"
        manager.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
root = Path(__file__).parent
if sys.argv[1:] == ['--licenses']:
    raise SystemExit(0)
log = root / 'calls.json'
calls = json.loads(log.read_text()) if log.exists() else []
calls.append(sys.argv[1:])
log.write_text(json.dumps(calls))
raise SystemExit(1 if len(calls) <= int(os.environ['SDK_TEST_FAILURES']) else 0)
""")
        manager.chmod(0o700)
        environment = os.environ | {"ANDROID_SDK_MANAGER": str(manager),
                                    "ANDROID_SDK_RETRY_DELAY": "0",
                                    "SDK_TEST_FAILURES": str(failures)}
        result = subprocess.run(["bash", str(ROOT / "scripts/install_android_sdk.sh"),
                                 "platforms;android-30"], env=environment,
                                capture_output=True, text=True, timeout=10)
        calls = json.loads((directory / "calls.json").read_text())
        return result, calls

    def test_success_does_not_repeat_installation(self):
        result, calls = self.install(0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], ["platforms;android-36", "build-tools;34.0.0",
                                   "ndk;28.2.13676358", "cmake;3.22.1", "platforms;android-30"])

    def test_transient_download_failure_recovers(self):
        result, calls = self.install(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(calls[1], calls[2])

    def test_permanent_failure_stops_the_job(self):
        result, calls = self.install(3)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 3)
        self.assertIn("failed after three attempts", result.stderr)


if __name__ == "__main__":
    unittest.main()
