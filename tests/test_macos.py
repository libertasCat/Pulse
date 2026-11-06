"""macOS dispatch, permission fallback and login-item regression."""
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import nullcontext

from pulse.utils import auto_start, window_monitor as monitor


class MacOSMonitorTests(unittest.TestCase):
    def modules(self, trusted=True, title="文档 — Safari"):
        app = SimpleNamespace(processIdentifier=lambda: 42, localizedName=lambda: "Safari")
        workspace = SimpleNamespace(frontmostApplication=lambda: app)

        def attribute(element, name, output):
            return (0, object()) if name == "AXFocusedWindow" else (0, title)

        return {
            "objc": SimpleNamespace(autorelease_pool=nullcontext),
            "AppKit": SimpleNamespace(NSWorkspace=SimpleNamespace(sharedWorkspace=lambda: workspace)),
            "ApplicationServices": SimpleNamespace(
                AXIsProcessTrusted=lambda: trusted,
                AXUIElementCreateApplication=lambda pid: object(),
                AXUIElementSetMessagingTimeout=lambda element, timeout: 0,
                AXUIElementCopyAttributeValue=attribute,
            ),
        }

    def test_frontmost_window_and_unicode_title(self):
        with patch.dict(sys.modules, self.modules()), patch.object(
            monitor, "_process_window_info", return_value=monitor.WindowInfo("Safari", pid=42)
        ), patch.object(monitor.platform, "system", return_value="Darwin"):
            info = monitor.get_active_window()
        self.assertEqual((info.process_name, info.window_title, info.pid), ("Safari", "文档 — Safari", 42))
        self.assertTrue(info.available)

    def test_denied_permission_keeps_app_tracking(self):
        modules = self.modules(trusted=False)
        with patch.dict(sys.modules, modules), patch.object(
            monitor, "_process_window_info", return_value=monitor.WindowInfo("Safari", pid=42)
        ):
            info = monitor._get_macos_active_window()
        self.assertTrue(info.available)
        self.assertEqual(info.window_title, "")

    def test_idle_dispatch(self):
        quartz = SimpleNamespace(
            CGEventSourceSecondsSinceLastEventType=lambda state, event: 321.9,
            kCGEventSourceStateCombinedSessionState=0, kCGAnyInputEventType=0,
        )
        with patch.dict(sys.modules, {"Quartz": quartz}), patch.object(
            monitor.platform, "system", return_value="Darwin"
        ):
            self.assertEqual(monitor.get_idle_seconds(), 321)
        quartz.CGEventSourceSecondsSinceLastEventType = lambda *args: float("inf")
        with patch.dict(sys.modules, {"Quartz": quartz}):
            self.assertEqual(monitor._get_macos_idle_seconds(), 0)

    def test_missing_backend_is_unavailable(self):
        with patch.dict(sys.modules, {"AppKit": None}):
            self.assertFalse(monitor._get_macos_active_window().available)


class MacOSAutoStartTests(unittest.TestCase):
    def test_enable_disable_preserves_argument_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "LaunchAgents" / "pulse.plist"
            command = ["/Applications/Python Env/bin/python", "/Users/test/Pulse 项目/main.py"]
            with patch.object(auto_start.sys, "platform", "darwin"), patch.object(
                auto_start, "_macos_launch_agent", return_value=path
            ), patch.object(auto_start, "_get_pulse_command", return_value=command):
                self.assertTrue(auto_start.set_auto_start(True))
                self.assertEqual(plistlib.loads(path.read_bytes())["ProgramArguments"], command)
                self.assertTrue(auto_start.is_auto_start_enabled())
                self.assertTrue(auto_start.set_auto_start(False))
                self.assertFalse(auto_start.is_auto_start_enabled())

    def test_frozen_app_uses_launch_services(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pulse.plist"
            with patch.object(auto_start, "_macos_launch_agent", return_value=path), patch.object(
                auto_start.sys, "frozen", True, create=True
            ), patch.object(auto_start.sys, "executable", "/Applications/Pulse Test.app/Contents/MacOS/Pulse"):
                self.assertTrue(auto_start._set_macos_auto_start(True))
                args = plistlib.loads(path.read_bytes())["ProgramArguments"]
                self.assertEqual(args, ["/usr/bin/open", "/Applications/Pulse Test.app"])


if __name__ == "__main__":
    unittest.main()
