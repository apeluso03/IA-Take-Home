"""Run every test in tests/ against one redact.py. DRAFT - for review.

    python3 run_tests.py                    # fixed (src/redact.py)
    python3 run_tests.py --target original  # original/redact.py

Exit code is 0 only if every test passes.
"""

import argparse
import os
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True  # keep original/ and tests/ free of __pycache__


def main():
    parser = argparse.ArgumentParser(description="Run redact.py tests")
    parser.add_argument("--target", choices=["fixed", "original"], default="fixed")
    args = parser.parse_args()

    # tests/test_redact.py and tests/test_cli.py read this to pick the script.
    os.environ["REDACT_TARGET"] = args.target
    # Child processes started by test_cli.py inherit this too.
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    tests_dir = pathlib.Path(__file__).resolve().parent / "tests"
    suite = unittest.defaultTestLoader.discover(str(tests_dir), pattern="test_*.py")
    print(f"target: {args.target}")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
