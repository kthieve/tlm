"""Unit tests for Playwright web backend."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from tlm.settings import UserSettings
from tlm.web.playwright_backend import is_playwright_available, playwright_fetch, build_playwright_run_fn

class TestPlaywrightBackend(unittest.TestCase):
    @patch("importlib.import_module")
    def test_is_playwright_available(self, mock_import):
        # We test both success and failure by mocking import behavior
        # But for now, let's just check if it returns a boolean
        res = is_playwright_available()
        self.assertIsInstance(res, bool)

    @patch("tlm.web.playwright_backend.is_playwright_available")
    @patch("tlm.web.playwright_backend._ensure_pw")
    @patch("tlm.web.playwright_backend._ensure_md")
    def test_playwright_fetch_mocked(self, mock_md, mock_pw, mock_avail):
        mock_avail.return_value = True
        
        # We mock the entire playwright context
        with patch("tlm.web.playwright_backend._pw_sync") as mock_sync:
            mock_p = mock_sync.return_value.__enter__.return_value
            mock_browser = mock_p.chromium.launch.return_value
            mock_context = mock_browser.new_context.return_value
            mock_page = mock_context.new_page.return_value
            mock_page.content.return_value = "<html><body>Hello</body></html>"
            
            with patch("tlm.web.playwright_backend._md") as mock_md_fn:
                mock_md_fn.return_value = "Hello"
                
                code, body = playwright_fetch("https://example.com")
                
                self.assertEqual(code, 0)
                self.assertEqual(body, "Hello")
                mock_page.goto.assert_called_once_with("https://example.com", timeout=30000)

    def test_build_run_fn(self):
        s = UserSettings()
        run_fn = build_playwright_run_fn(s)
        self.assertTrue(callable(run_fn))
        
        # Test it calls playwright_fetch (mocked)
        with patch("tlm.web.playwright_backend.playwright_fetch") as mock_fetch:
            mock_fetch.return_value = (0, "Mocked result")
            argv = ["tlm-web", "fetch", "https://test.com"]
            code, body = run_fn(argv)
            
            self.assertEqual(code, 0)
            self.assertEqual(body, "Mocked result")
            mock_fetch.assert_called_once()
            # Verify URL was extracted correctly from the end of argv
            args, kwargs = mock_fetch.call_args
            self.assertEqual(args[0], "https://test.com")

if __name__ == "__main__":
    unittest.main()
