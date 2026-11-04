import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGETS = {
    "original": ROOT / "original" / "redact.py",
    "fixed": ROOT / "src" / "redact.py",
}
SCRIPT = TARGETS[os.environ.get("REDACT_TARGET", "fixed")]

FAKE_KEY = "rly_FAKEa1b2c3d4e5f6g7h8i9j0"


def run_cli(text):
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=text,
        capture_output=True,
        text=True,
        timeout=10,
    )


class TestCommandLine(unittest.TestCase):
    def test_key_on_stdin_is_redacted_on_stdout(self):
        result = run_cli(f"New key issued: {FAKE_KEY}\n")
        self.assertIn("[REDACTED]", result.stdout)
        self.assertNotIn(FAKE_KEY, result.stdout)

    def test_normal_text_passes_through_unchanged(self):
        text = "Rotated the key for billing-sync. See ticket SUP-5521.\n"
        result = run_cli(text)
        self.assertEqual(result.stdout, text)

    def test_exits_with_success_code(self):
        result = run_cli("hello\n")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()