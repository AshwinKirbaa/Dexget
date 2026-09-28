import unittest

from jarvis.security.permissions import classify_command_risk, redact_secrets, sanitize_path
import tempfile
import os


class SecurityTests(unittest.TestCase):
    def test_destructive_commands_detected(self):
        for cmd in ["del /f C:\\Windows", "format C:", "shutdown /s", "rm -rf /", "diskpart"]:
            self.assertEqual(classify_command_risk(cmd), "destructive", cmd)

    def test_high_risk_commands_detected(self):
        self.assertEqual(classify_command_risk("delete the temp folder contents"), "high")

    def test_low_risk_commands_pass_through(self):
        self.assertEqual(classify_command_risk("dir"), "low")
        self.assertEqual(classify_command_risk("echo hello"), "low")

    def test_sanitize_path_blocks_traversal(self):
        with tempfile.TemporaryDirectory() as allowed:
            escaped = os.path.join(allowed, "..", "etc", "passwd")
            self.assertIsNone(sanitize_path(escaped, [allowed]))

    def test_sanitize_path_allows_inside_root(self):
        with tempfile.TemporaryDirectory() as allowed:
            inside = os.path.join(allowed, "sub", "file.txt")
            result = sanitize_path(inside, [allowed])
            self.assertIsNotNone(result)
            self.assertTrue(result.startswith(os.path.realpath(allowed)))

    def test_redact_secrets(self):
        text = "api_key=sk-12345 password=hunter2 normal text here"
        redacted = redact_secrets(text)
        self.assertNotIn("sk-12345", redacted)
        self.assertNotIn("hunter2", redacted)
        self.assertIn("normal text here", redacted)


if __name__ == "__main__":
    unittest.main()
