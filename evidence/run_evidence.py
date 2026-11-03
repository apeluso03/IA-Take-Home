"""Evidence runner (SPEC Task 1).

Runs a chosen redact.py (original or fixed) over every file in
evidence/inputs/ and writes the input and output side by side to
evidence/results/<target>/.

Usage:
    python3 evidence/run_evidence.py --target original
    python3 evidence/run_evidence.py --target fixed

Standard library only. No network calls. Input files are opened read-only
and their SHA-256 is checked before and after the run.
"""

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path

# Importing original/redact.py must not create original/__pycache__.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
INPUTS_DIR = ROOT / "evidence" / "inputs"
RESULTS_DIR = ROOT / "evidence" / "results"
TARGETS = {
    "original": ROOT / "original" / "redact.py",
    "fixed": ROOT / "src" / "redact.py",
}
MARKER = "[REDACTED]"


def load_redact(path):
    """Load redact() from the given file without touching sys.modules names
    used elsewhere. Returns the function, or raises SystemExit with a clear
    message if the file has no usable redact()."""
    if not path.is_file():
        raise SystemExit(f"error: {path} does not exist")
    spec = importlib.util.spec_from_file_location(f"redact_under_test_{path.parent.name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, "redact", None)
    if not callable(func):
        raise SystemExit(f"error: {path} does not define a redact(text) function")
    return func


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_text(path):
    # newline="" keeps \r\n and \n exactly as they are in the file.
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def side_by_side(input_text, output_text):
    """Pair input and output line by line and mark each pair."""
    in_lines = input_text.splitlines()
    out_lines = output_text.splitlines()
    rows = []
    for i in range(max(len(in_lines), len(out_lines))):
        a = in_lines[i] if i < len(in_lines) else "<no line>"
        b = out_lines[i] if i < len(out_lines) else "<no line>"
        status = "UNCHANGED" if a == b else "CHANGED"
        rows.append(f"line {i + 1}  [{status}]")
        rows.append(f"  IN : {a}")
        rows.append(f"  OUT: {b}")
    if len(in_lines) != len(out_lines):
        rows.append(f"NOTE: line count differs (input {len(in_lines)}, output {len(out_lines)})")
    return "\n".join(rows)


def leftover_rly(output_text):
    """Lines in the output that still contain 'rly_' in any case.
    This is only a pointer for manual review, not a verdict: 'rly_' can
    appear legitimately (e.g. plain prose about the prefix)."""
    return [
        (n, line)
        for n, line in enumerate(output_text.splitlines(), 1)
        if "rly_" in line.lower()
    ]


def build_report(name, target, target_path, input_text, output_text):
    count = output_text.count(MARKER) - input_text.count(MARKER)
    leftovers = leftover_rly(output_text)
    parts = [
        f"input file : evidence/inputs/{name}",
        f"redact.py  : {target} ({target_path.relative_to(ROOT).as_posix()})",
        f"changed    : {'yes' if input_text != output_text else 'NO - output identical to input'}",
        f"{MARKER} markers added: {count}",
        f"lines still containing 'rly_' (any case): {len(leftovers)}",
    ]
    for n, line in leftovers:
        parts.append(f"  line {n}: {line}")
    parts += [
        "",
        "=== SIDE BY SIDE ===",
        side_by_side(input_text, output_text),
        "",
        "=== RAW INPUT ===",
        input_text,
        "=== END RAW INPUT ===",
        "",
        "=== RAW OUTPUT ===",
        output_text,
        "=== END RAW OUTPUT ===",
        "",
    ]
    return "\n".join(parts), count, leftovers


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", choices=sorted(TARGETS), required=True,
                        help="which redact.py to run")
    args = parser.parse_args()

    target_path = TARGETS[args.target]
    redact = load_redact(target_path)

    inputs = sorted(p for p in INPUTS_DIR.iterdir() if p.is_file())
    if not inputs:
        raise SystemExit(f"error: no files in {INPUTS_DIR}")

    before = {p: sha256(p) for p in inputs}

    out_dir = RESULTS_DIR / args.target
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = [
        f"# Evidence results: {args.target}",
        "",
        f"redact.py: `{target_path.relative_to(ROOT).as_posix()}`",
        "",
        "| input | changed | markers added | lines still containing `rly_` |",
        "|---|---|---|---|",
    ]
    for path in inputs:
        input_text = read_text(path)
        try:
            output_text = redact(input_text)
        except Exception as e:  # record the failure as evidence, keep going
            output_text = f"<redact() raised {type(e).__name__}: {e}>"
        report, count, leftovers = build_report(
            path.name, args.target, target_path, input_text, output_text)
        with open(out_dir / path.name, "w", encoding="utf-8", newline="") as f:
            f.write(report)
        changed = "yes" if input_text != output_text else "**no**"
        summary.append(f"| {path.name} | {changed} | {count} | {len(leftovers)} |")
        print(f"{path.name:<22} changed={changed.strip('*'):<4} markers={count} rly_left={len(leftovers)}")

    summary += [
        "",
        "`rly_` count is a pointer for manual review only; it can be a legitimate",
        "mention of the prefix. Read each result file before drawing conclusions.",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")

    after = {p: sha256(p) for p in inputs}
    modified = [p.name for p in inputs if before[p] != after[p]]
    if modified:
        raise SystemExit(f"error: input files changed during run: {modified}")

    print(f"\n{len(inputs)} inputs processed, inputs unchanged (sha256 checked).")
    print(f"results: {out_dir.relative_to(ROOT).as_posix()}/")


if __name__ == "__main__":
    main()
