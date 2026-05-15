"""Unit tests for web backend selection."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from tlm.settings import UserSettings
from tlm.web.backend import resolve_web_backend

class TestWebBackend(unittest.TestCase):
    def test_explicit_selection(self):
        s = UserSettings(web_backend="playwright")
        self.assertEqual(resolve_web_backend(s), "playwright")
        
        s.web_backend = "lightpanda"
        self.assertEqual(resolve_web_backend(s), "lightpanda")

    @patch("sys.platform", "win32")
    @patch("tlm.web.playwright_backend.is_playwright_available")
    def test_windows_auto_preference(self, mock_pw_avail):
        s = UserSettings(web_backend="auto")
        
        # If playwright is available on Windows, prefer it
        mock_pw_avail.return_value = True
        self.assertEqual(resolve_web_backend(s), "playwright")
        
        # If not available, fallback to lightpanda (WSL/path)
        mock_pw_avail.return_value = False
        self.assertEqual(resolve_web_backend(s), "lightpanda")

    @patch("sys.platform", "linux")
    @patch("tlm.web.lightpanda.resolve_binary")
    @patch("tlm.web.playwright_backend.is_playwright_available")
    def test_linux_auto_preference(self, mock_pw_avail, mock_lp_resolve):
        s = UserSettings(web_backend="auto")
        
        # If lightpanda is found on Linux, prefer it
        mock_lp_resolve.return_value = "/usr/bin/lightpanda"
        self.assertEqual(resolve_web_backend(s), "lightpanda")
        
        # If lightpanda is NOT found, but playwright IS, use playwright
        mock_lp_resolve.return_value = None
        mock_pw_avail.return_value = True
        self.assertEqual(resolve_web_backend(s), "playwright")

if __name__ == "__main__":
    unittest.main()
