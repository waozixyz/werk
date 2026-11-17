"""Regression tests for private Android startup readiness."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import android_startup


class StartupTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "build/android-startup-test"
        root.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.frame = self.output / "frame.png"
        self.frame.write_bytes(b"mock screenshot")
        self.now = 0
        self.clock = patch.object(android_startup.time, "monotonic", lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.sleep = patch.object(android_startup.time, "sleep", self.advance)
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def advance(self, seconds):
        self.now += seconds

    def result(self, code=0, data=b""):
        return subprocess.CompletedProcess([], code, data, b"")

    def launch(self, adb, timeout=5):
        android_startup.launch_home(adb, self.output, "xyz.waozi.pass", "launch", timeout)

    def test_delayed_home_after_android_launch_metric_timeout(self):
        adb = Mock(return_value=self.result(data=b"Status: timeout\n"))
        with patch.object(android_startup, "label_position",
                          side_effect=lambda frame, word: (10, 20) if self.now >= 3 and word == "Pass" else None):
            self.launch(adb)
        self.assertEqual(self.now, 3)
        self.assertIn("-W", adb.call_args_list[0].args)
        self.assertEqual((self.output / "launch.txt").read_text(), "Status: timeout\n")

    def test_missing_home_fails_within_deadline(self):
        adb = Mock(return_value=self.result())
        with patch.object(android_startup, "label_position", return_value=None):
            with self.assertRaisesRegex(AssertionError, "did not become visible"):
                self.launch(adb, timeout=2)
        self.assertEqual(self.now, 2)

    def test_default_deadline_allows_cold_home_after_105_seconds(self):
        adb = Mock(return_value=self.result())
        with patch.object(android_startup, "label_position",
                          side_effect=lambda frame, word: (10, 20) if self.now >= 105 and word == "Pass" else None):
            android_startup.launch_home(adb, self.output, "xyz.waozi.pass", "launch")
        self.assertEqual(self.now, 105)

    def test_default_deadline_still_rejects_absent_home(self):
        adb = Mock(return_value=self.result())
        with patch.object(android_startup, "label_position", return_value=None):
            with self.assertRaisesRegex(AssertionError, "did not become visible"):
                android_startup.launch_home(adb, self.output, "xyz.waozi.pass", "launch")
        self.assertEqual(self.now, 180)

    def test_launch_command_failure_remains_failure(self):
        adb = Mock(side_effect=subprocess.CalledProcessError(1, ["adb"]))
        with self.assertRaises(subprocess.CalledProcessError):
            self.launch(adb)
        adb.assert_called_once()

    def test_wait_only_for_exact_system_ui_dialog(self):
        for title, expected in (("System UI isn&apos;t responding", True),
                                ("Werkzeug isn&apos;t responding", False),
                                ("Calculator isn&apos;t responding", False)):
            with self.subTest(title=title):
                tree = ('<hierarchy><node text="' + title +
                        '"/><node text="Wait" bounds="[0,20][100,60]"/></hierarchy>')
                adb = Mock(return_value=self.result(data=tree.encode()))
                with patch.object(android_startup, "label_position", return_value=(50, 40)):
                    self.assertEqual(android_startup.wait_for_system_ui(adb, self.frame, self.output), expected)
                taps = [call for call in adb.call_args_list if call.args[:3] == ("shell", "input", "tap")]
                self.assertEqual(len(taps), int(expected))
                if expected:
                    self.assertEqual(taps[0].args[-2:], ("50", "40"))
                    self.assertEqual((self.output / "system-ui-dialog.png").read_bytes(), self.frame.read_bytes())

    def test_failed_fresh_dump_never_reads_stale_tree(self):
        adb = Mock(side_effect=[self.result(), self.result(1)])
        with patch.object(android_startup, "label_position", return_value=(50, 40)):
            self.assertFalse(android_startup.wait_for_system_ui(adb, self.frame, self.output))
        self.assertEqual(adb.call_count, 2)
        self.assertEqual(adb.call_args_list[0].args[:3], ("shell", "rm", "-f"))

    def test_failed_read_or_malformed_tree_never_taps(self):
        for result in (self.result(1, b"System UI isn't responding"),
                       self.result(data=b"System UI isn't responding but not XML")):
            adb = Mock(side_effect=[self.result(), self.result(), result])
            with patch.object(android_startup, "label_position", return_value=(50, 40)):
                self.assertFalse(android_startup.wait_for_system_ui(adb, self.frame, self.output))
            self.assertEqual(adb.call_count, 3)

    def test_persistent_overlay_allows_one_wait_then_fails(self):
        adb = Mock(return_value=self.result())
        with patch.object(android_startup, "label_position", return_value=None), \
                patch.object(android_startup, "wait_for_system_ui", return_value=True) as wait:
            with self.assertRaisesRegex(AssertionError, "did not become visible"):
                self.launch(adb, timeout=2)
        wait.assert_called_once()


if __name__ == "__main__":
    unittest.main()
