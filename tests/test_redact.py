"""Tests for redact(text). DRAFT - written by Claude Code for review.

Runs against original/redact.py or src/redact.py, chosen by the
REDACT_TARGET environment variable (default: fixed). Use run_tests.py.
All keys below are made up and only match the Relay format.
"""

import importlib.util
import os
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True  # keep original/ free of __pycache__

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGETS = {
    "original": ROOT / "original" / "redact.py",
    "fixed": ROOT / "src" / "redact.py",
}
TARGET = os.environ.get("REDACT_TARGET", "fixed")

_spec = importlib.util.spec_from_file_location(f"redact_{TARGET}", TARGETS[TARGET])
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
redact = _module.redact

R = "[REDACTED]"
KEY = "rly_TESTq1w2e3r4t5y6u7i8o9p0"           # 24 chars after rly_
KEY_HYPHEN = "rly_TEST-q1w2-e3r4-t5y6-u7i8-o9p0"


class TestMustBeFullyRedacted(unittest.TestCase):
    def assertFullyRedacted(self, text, expected):
        self.assertEqual(redact(text), expected)

    def test_plain(self):
        self.assertFullyRedacted(f"key: {KEY}", f"key: {R}")

    def test_hyphenated(self):
        self.assertFullyRedacted(f"key: {KEY_HYPHEN}", f"key: {R}")

    def test_uppercase_prefix(self):
        self.assertFullyRedacted(f"key: RLY_{KEY[4:]}", f"key: {R}")

    def test_mixed_case_prefix(self):
        self.assertFullyRedacted(f"key: Rly_{KEY[4:]}", f"key: {R}")

    def test_wrapped_lf(self):
        self.assertFullyRedacted(f"key: {KEY[:16]}\n{KEY[16:]}", f"key: {R}")

    def test_wrapped_crlf(self):
        self.assertFullyRedacted(f"key: {KEY[:16]}\r\n{KEY[16:]}", f"key: {R}")

    def test_wrapped_after_hyphen(self):
        self.assertFullyRedacted(f"key: {KEY_HYPHEN[:14]}\n{KEY_HYPHEN[14:]}", f"key: {R}")

    def test_wrapped_inside_prefix_before_underscore(self):
        self.assertFullyRedacted(f"key: rly\n{KEY[3:]}", f"key: {R}")

    def test_wrapped_inside_prefix_crlf(self):
        self.assertFullyRedacted(f"key: rly\r\n{KEY[3:]}", f"key: {R}")

    def test_wrapped_inside_prefix_after_r(self):
        self.assertFullyRedacted(f"key: r\n{KEY[1:]}", f"key: {R}")

    def test_wrapped_inside_prefix_after_rl(self):
        self.assertFullyRedacted(f"key: rl\n{KEY[2:]}", f"key: {R}")

    def test_wrapped_right_after_prefix(self):
        self.assertFullyRedacted(f"key: rly_\n{KEY[4:]}", f"key: {R}")

    def test_wrapped_inside_uppercase_prefix(self):
        self.assertFullyRedacted(f"key: RLY\n_{KEY[4:]}", f"key: {R}")

    def test_overlong(self):
        self.assertFullyRedacted(f"key: {KEY}EXTRA99", f"key: {R}")

    def test_json(self):
        self.assertFullyRedacted(f'{{"new_key":"{KEY}","status":"ok"}}',
                                 f'{{"new_key":"{R}","status":"ok"}}')

    def test_json_hyphenated(self):
        self.assertFullyRedacted(f'{{"new_key":"{KEY_HYPHEN}"}}', f'{{"new_key":"{R}"}}')

    def test_bearer_relay_key(self):
        self.assertFullyRedacted(f"Authorization: Bearer {KEY}", f"Authorization: Bearer {R}")

    def test_bearer_other_token(self):
        self.assertFullyRedacted("Authorization: Bearer abcdefghij.klmnopqrst-uv",
                                 f"Authorization: {R}")

    def test_bearer_lowercase(self):
        self.assertFullyRedacted("authorization: bearer abcdefghij.klmnopqrst-uv",
                                 f"authorization: {R}")

    def test_bearer_uppercase(self):
        self.assertFullyRedacted("AUTHORIZATION: BEARER abcdefghij.klmnopqrst-uv",
                                 f"AUTHORIZATION: {R}")

    def test_two_keys_on_one_line(self):
        other = "rly_ZZZZa9s8d7f6g5h4j3k2l1m0"
        self.assertFullyRedacted(f"{KEY} {other}", f"{R} {R}")


class TestNormalTextUnchanged(unittest.TestCase):
    def assertUnchanged(self, text):
        self.assertEqual(redact(text), text)

    def test_plain_sentence(self):
        self.assertUnchanged("Rotated the key for billing-sync at 14:02. See ticket SUP-5521.\n")

    def test_prefix_mentioned_in_prose(self):
        self.assertUnchanged("The rly_ prefix marks a Relay key.")

    def test_prefix_followed_by_punctuation(self):
        self.assertUnchanged("Keys start with rly_, then 24 characters.")

    def test_url(self):
        self.assertUnchanged("Endpoint: https://relay.example.internal/v1/keys/rotate")

    def test_empty(self):
        self.assertUnchanged("")


class TestBoundaries(unittest.TestCase):
    def test_complete_key_does_not_swallow_next_line(self):
        self.assertEqual(redact(f"key: {KEY}\nNext line stays."), f"key: {R}\nNext line stays.")

    def test_text_after_key_on_same_line_kept(self):
        self.assertEqual(redact(f"key {KEY} was rotated"), f"key {R} was rotated")


if __name__ == "__main__":
    unittest.main()
