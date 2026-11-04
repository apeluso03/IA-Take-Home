import os
import pathlib
import subprocess
import sys
import tempfile
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


# DRAFT - added by Claude Code for Task 2, for review.
class TestCommandLineFailSafe(unittest.TestCase):
    def test_leftover_key_exits_nonzero_with_no_stdout(self):
        # Too short to be a full key, so it is not redacted; the leftover
        # check must catch it.
        result = run_cli("partial key: rly_TESTq1w2e3\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertNotEqual(result.stderr.strip(), "")

    def test_leftover_with_wrapped_prefix_exits_nonzero(self):
        # Short partial key whose prefix is split across a line break.
        result = run_cli("partial key: rly\n_TESTq1w2e3\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_leftover_reason_does_not_echo_value(self):
        result = run_cli("partial key: rly_TESTq1w2e3\n")
        self.assertNotIn("rly_TESTq1w2e3", result.stderr)

    def test_prefix_in_prose_is_not_leftover(self):
        text = "The rly_ prefix marks a Relay key.\n"
        result = run_cli(text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, text)

    def test_empty_input_gives_empty_output_and_exit_0(self):
        result = run_cli("")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def run_file(self, text):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "summary.txt"
            path.write_bytes(text.encode("utf-8"))
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                capture_output=True, text=True, timeout=10,
            )

    def test_file_argument_matches_stdin_clean(self):
        text = f"service=billing-sync outcome=success key={FAKE_KEY}\n"
        from_stdin, from_file = run_cli(text), self.run_file(text)
        self.assertEqual(from_file.returncode, 0, from_file.stderr)
        self.assertEqual(from_file.returncode, from_stdin.returncode)
        self.assertEqual(from_file.stdout, from_stdin.stdout)
        self.assertNotIn(FAKE_KEY, from_file.stdout)

    def test_file_argument_matches_stdin_leftover(self):
        text = "partial key: rly_FAKEq1w2e3\n"
        from_stdin, from_file = run_cli(text), self.run_file(text)
        self.assertNotEqual(from_file.returncode, 0)
        self.assertEqual(from_file.returncode, from_stdin.returncode)
        self.assertEqual(from_file.stdout, "")
        self.assertEqual(from_stdin.stdout, "")

    def test_missing_file_argument_exits_nonzero_with_no_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(pathlib.Path(d) / "missing.txt")],
                capture_output=True, text=True, timeout=10,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertNotEqual(result.stderr.strip(), "")

    def test_unreadable_input_exits_nonzero_with_no_stdout(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=b"key: \xff\xfe not utf-8\n",
            capture_output=True,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertNotEqual(result.stderr.strip(), b"")


if __name__ == "__main__":
    unittest.main()