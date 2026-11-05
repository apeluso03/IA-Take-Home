"""Run every test in this repo and write one report.

    python3 run_all.py

What it runs:
  1. Unit + command-line tests (tests/test_redact.py, tests/test_cli.py)
     against BOTH the fixed (src/redact.py) and original (original/redact.py).
  2. Rotate-helper tests (tests/test_rotate_key.py), once. They don't depend
     on which redact.py is chosen.
  3. The evidence inputs (evidence/inputs/) through both redactors, both as a
     function and from the command line. Also refreshes evidence/results/
     via evidence/run_evidence.py.
  4. Repo checks: original/ unchanged, the skill's redact.py copy matches
     src/redact.py, and SKILL.md has none of the banned strings.

Writes:  evidence/results/test-report.md
Exit 0 only if everything that is meant to pass does pass (fixed target,
rotate helper, repo checks). The original target is EXPECTED to fail.

Standard library only. No network calls (the rotate tests use a local fake
server on 127.0.0.1).
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import traceback
import unittest
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
TESTS_DIR = ROOT / "tests"
INPUTS_DIR = ROOT / "evidence" / "inputs"
REPORT = ROOT / "evidence" / "results" / "test-report.md"
REDACT = {"fixed": ROOT / "src" / "redact.py", "original": ROOT / "original" / "redact.py"}

# One line per test class, for the report. Test names explain the rest.
CLASS_NOTES = {
    "test_redact.TestMustBeFullyRedacted": "Key and token formats that must come out fully as [REDACTED].",
    "test_redact.TestNormalTextUnchanged": "Ordinary text, including mentions of the rly_ prefix, must be left alone.",
    "test_redact.TestBoundaries": "Redaction must stop at the end of the key and not eat nearby text.",
    "test_cli.TestCommandLine": "redact.py run from the command line: stdin in, redacted text out.",
    "test_cli.TestCommandLineFailSafe": "Command-line fail-safes: exit codes, withheld output, file argument.",
    "test_rotate_key.TestCheck": "rotate_key.py --check: is RELAY_KEY set, without ever printing it.",
    "test_rotate_key.TestRotate": "rotate_key.py rotation against a local fake Relay server.",
    "test_rotate_key.TestBaseUrl": "RELAY_BASE_URL may only point at this machine.",
    "test_rotate_key.TestNoExtraFlags": "The helper has no force, skip, retry, or key flags.",
}


# --------------------------------------------------------------------------
# Worker: runs one set of test files in a fresh process and prints JSON.
# A fresh process is needed because the test modules pick their target
# (REDACT_TARGET) at import time.
# --------------------------------------------------------------------------

class _Collect(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.rows = {}

    def _row(self, test):
        cls = type(test)
        key = test.id()
        if key not in self.rows:
            doc = (getattr(cls, test._testMethodName).__doc__ or "").strip().splitlines()
            self.rows[key] = {
                "module": cls.__module__,
                "cls": cls.__name__,
                "name": test._testMethodName,
                "doc": doc[0] if doc else "",
                "status": "pass",
                "detail": "",
            }
        return self.rows[key]

    def _fail(self, test, err, status):
        exc_type, exc, _ = err
        msg = "".join(traceback.format_exception_only(exc_type, exc)).strip().splitlines()
        row = self._row(test)
        row["status"] = status
        # First line of the message: "got != expected" for assertEqual.
        row["detail"] = (msg[0] if msg else exc_type.__name__)[:200]

    def startTest(self, test):
        super().startTest(test)
        self._row(test)

    def addFailure(self, test, err):
        self._fail(test, err, "fail")

    def addError(self, test, err):
        self._fail(test, err, "error")

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self._fail(test, err, "fail" if issubclass(err[0], test.failureException) else "error")
            row = self._row(test)
            row["detail"] = f"{subtest._subDescription()}: {row['detail']}"[:200]

    def addSkip(self, test, reason):
        row = self._row(test)
        row["status"], row["detail"] = "skip", reason


def worker(modules):
    sys.path.insert(0, str(TESTS_DIR))
    suite = unittest.TestSuite()
    for m in modules:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(m))
    result = _Collect()
    suite.run(result)
    print(json.dumps(list(result.rows.values())))


def run_suite(modules, target):
    env = dict(os.environ, REDACT_TARGET=target, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(
        [sys.executable, str(Path(__file__)), "--worker", *modules],
        env=env, capture_output=True, text=True, timeout=600,
    )
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        sys.exit(f"test worker crashed:\n{proc.stderr[-2000:]}")


# --------------------------------------------------------------------------
# Evidence inputs
# --------------------------------------------------------------------------

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_cli(script, path):
    p = subprocess.run([sys.executable, str(script)], stdin=open(path, "rb"),
                       capture_output=True, timeout=30,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace").strip()


def run_evidence():
    fixed = load_module(REDACT["fixed"], "redact_fixed_report")
    original = load_module(REDACT["original"], "redact_original_report")
    rows = []
    for path in sorted(p for p in INPUTS_DIR.iterdir() if p.is_file()):
        text = path.read_bytes().decode("utf-8")
        out = {"original": original.redact(text), "fixed": fixed.redact(text)}
        rows.append({
            "name": path.name,
            "input": text,
            "out": out,
            # Leftover lines, found with the fixed redactor's check (it also
            # sees a prefix split across a line break).
            "left": {t: fixed.find_leftovers(o) for t, o in out.items()},
            "cli": {t: run_cli(REDACT[t], path) for t in REDACT},
        })
    # Refresh the saved per-input side-by-side files too.
    for target in REDACT:
        subprocess.run([sys.executable, str(ROOT / "evidence" / "run_evidence.py"), "--target", target],
                       capture_output=True, check=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return rows


# --------------------------------------------------------------------------
# Repo checks
# --------------------------------------------------------------------------

def repo_checks():
    checks = []

    try:
        p = subprocess.run(["git", "status", "--porcelain", "--", "original"],
                           cwd=ROOT, capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            raise OSError(p.stderr.strip())
        checks.append(("original/ has no uncommitted changes (git status)",
                       "pass" if not p.stdout.strip() else "fail",
                       p.stdout.strip() or "clean"))
    except (OSError, subprocess.SubprocessError) as e:
        checks.append(("original/ has no uncommitted changes (git status)", "skip", f"git not available: {e}"))

    same = (ROOT / "src" / "redact.py").read_bytes() == (ROOT / "skill" / "scripts" / "redact.py").read_bytes()
    checks.append(("skill/scripts/redact.py is identical to src/redact.py",
                   "pass" if same else "fail", "identical" if same else "files differ"))

    banned = re.compile(r"curl|--force|bearer|retry up to|rly_[A-Za-z0-9]", re.IGNORECASE)
    skill = (ROOT / "skill" / "SKILL.md").read_text(encoding="utf-8")
    hits = [f"line {skill.count(chr(10), 0, m.start()) + 1}: {m.group(0)}" for m in banned.finditer(skill)]
    checks.append(("skill/SKILL.md has no curl, --force, Bearer, 'retry up to', or rly_ + key characters",
                   "fail" if hits else "pass", "; ".join(hits) or "no matches"))

    lines = len(skill.splitlines())
    checks.append(("skill/SKILL.md is under about 80 lines", "pass" if lines <= 80 else "fail", f"{lines} lines"))
    return checks


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

ICON = {"pass": "PASS", "fail": "**FAIL**", "error": "**ERROR**", "skip": "skip", None: "-"}


def esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def describe(row):
    return row["doc"] or row["name"].removeprefix("test_").replace("_", " ")


def count(rows):
    passed = sum(r["status"] == "pass" for r in rows)
    return f"{passed}/{len(rows)} pass"


def fence(text):
    return "````text\n" + (text if text.endswith("\n") or not text else text + "\n") + "````"


def build_report(redact_rows, rotate_rows, evidence, checks, seconds):
    fixed, original = redact_rows["fixed"], redact_rows["original"]
    orig_by_name = {(r["module"], r["cls"], r["name"]): r for r in original}
    ok_fixed = all(r["status"] == "pass" for r in fixed)
    ok_rotate = all(r["status"] == "pass" for r in rotate_rows)
    ok_checks = all(c[1] != "fail" for c in checks)
    orig_fails = any(r["status"] != "pass" for r in original)

    L = []
    L += [
        "# Test report",
        "",
        f"Generated by `python3 run_all.py` on {datetime.now():%Y-%m-%d %H:%M} "
        f"(Python {sys.version.split()[0]}, {sys.platform}). Took {seconds:.0f} s.",
        "",
        "All keys in this report are fake test values.",
        "",
        "## Summary",
        "",
        "| Part | Result | Expected |",
        "|---|---|---|",
        f"| redact tests, fixed `src/redact.py` | {count(fixed)} | all pass |",
        f"| redact tests, original `original/redact.py` | {count(original)} | some fail (shows the original's gaps) |",
        f"| rotate helper tests | {count(rotate_rows)} | all pass |",
        f"| evidence inputs | {len(evidence)} run through both redactors | no pass/fail; read below |",
        f"| repo checks | {sum(c[1] == 'pass' for c in checks)}/{len(checks)} pass | all pass |",
        "",
        f"**Overall: {'PASS' if ok_fixed and ok_rotate and ok_checks and orig_fails else 'FAIL'}**. "
        "That means the fixed target, the rotate helper and the repo checks all pass, "
        "and the original target still fails at least one test.",
        "",
    ]

    # Redact tests, side by side.
    L += [
        "## 1. Redact tests: fixed vs original",
        "",
        "These come from `tests/test_redact.py` (calls `redact()` directly) and `tests/test_cli.py` "
        "(runs `redact.py` as a command). The same tests run against both versions.",
        "",
    ]
    current = None
    for r in fixed:
        group = f"{r['module']}.{r['cls']}"
        if group != current:
            current = group
            L += ["", f"### `{group}`", "", CLASS_NOTES.get(group, ""), "",
                  "| Test | Checks | Fixed | Original | Why the original fails |", "|---|---|---|---|---|"]
        o = orig_by_name.get((r["module"], r["cls"], r["name"]), {"status": None, "detail": ""})
        fixed_cell = ICON[r["status"]] + (f" ({esc(r['detail'])})" if r["status"] != "pass" else "")
        L.append(f"| `{r['name']}` | {esc(describe(r))} | {fixed_cell} | {ICON[o['status']]} | "
                 f"{esc(o['detail']) if o['status'] != 'pass' else ''} |")

    # Rotate tests.
    L += ["", "## 2. Rotate helper tests", "",
          "From `tests/test_rotate_key.py`. They run `skill/scripts/rotate_key.py` against a fake Relay "
          "server on 127.0.0.1. No real network."]
    current = None
    for r in rotate_rows:
        group = f"{r['module']}.{r['cls']}"
        if group != current:
            current = group
            L += ["", f"### `{group}`", "", CLASS_NOTES.get(group, ""), "",
                  "| Test | Checks | Result |", "|---|---|---|"]
        cell = ICON[r["status"]] + (f" ({esc(r['detail'])})" if r["status"] != "pass" else "")
        L.append(f"| `{r['name']}` | {esc(describe(r))} | {cell} |")

    # Evidence.
    L += [
        "", "## 3. Evidence inputs",
        "",
        "These are the hand-written inputs in `evidence/inputs/`. They have no expected answers in the repo, "
        "so this section shows what happened rather than pass/fail.",
        "",
        "- **Changed**: was the output different from the input?",
        "- **Key-like left**: lines in the `redact()` output that still hold `rly_` followed by key "
        "characters. These are found with the fixed redactor's leftover check, which also sees a prefix "
        "split across a line break.",
        "- **CLI**: exit code and stdout when the file is piped to `redact.py` on the command line.",
        "",
        "| Input | Original: changed | Original: key-like left | Original CLI | "
        "Fixed: changed | Fixed: key-like left | Fixed CLI |",
        "|---|---|---|---|---|---|---|",
    ]

    def cli_cell(c):
        code, out, _ = c
        return f"exit {code}, {'stdout empty' if not out else 'stdout has text'}"

    for e in evidence:
        cells = []
        for t in ("original", "fixed"):
            changed = "yes" if e["out"][t] != e["input"] else "no"
            left = ", ".join(f"line {n}" for n in e["left"][t]) or "none"
            cells += [changed, left, cli_cell(e["cli"][t])]
        L.append(f"| `{e['name']}` | " + " | ".join(cells) + " |")

    L += ["", "### Inputs and outputs", ""]
    for e in evidence:
        code, _, err = e["cli"]["fixed"]
        L += [f"#### `{e['name']}`", "", "Input:", "", fence(e["input"]), "",
              "Original `redact()` output:", "", fence(e["out"]["original"]), "",
              "Fixed `redact()` output:", "", fence(e["out"]["fixed"]), ""]
        if code != 0:
            L += [f"Fixed CLI exited {code} and withheld its output: `{esc(err)}`", ""]

    # Repo checks.
    L += ["## 4. Repo checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    for name, status, detail in checks:
        L.append(f"| {esc(name)} | {ICON[status]} | {esc(detail)} |")
    L.append("")
    return "\n".join(L), ok_fixed and ok_rotate and ok_checks and orig_fails


def main():
    start = time.monotonic()
    redact_modules = ["test_redact", "test_cli"]
    print("[1/4] redact tests, fixed ...", flush=True)
    redact_rows = {"fixed": run_suite(redact_modules, "fixed")}
    print("[1/4] redact tests, original ...", flush=True)
    redact_rows["original"] = run_suite(redact_modules, "original")
    print("[2/4] rotate helper tests (about 25 s) ...", flush=True)
    rotate_rows = run_suite(["test_rotate_key"], "fixed")
    print("[3/4] evidence inputs ...", flush=True)
    evidence = run_evidence()
    print("[4/4] repo checks ...", flush=True)
    checks = repo_checks()

    report, ok = build_report(redact_rows, rotate_rows, evidence, checks, time.monotonic() - start)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")

    for label, rows in [("fixed", redact_rows["fixed"]), ("original", redact_rows["original"]),
                        ("rotate", rotate_rows)]:
        print(f"  {label:<9} {count(rows)}")
    print(f"  checks    {sum(c[1] == 'pass' for c in checks)}/{len(checks)} pass")
    print(f"\n{'PASS' if ok else 'FAIL'}  report: {REPORT.relative_to(ROOT).as_posix()}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(sys.argv[2:])
    else:
        sys.exit(main())
