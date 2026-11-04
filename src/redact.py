"""Redact Relay keys and bearer tokens from text.

Library use:
    from redact import redact
    clean = redact(text)

Command line:
    python3 src/redact.py < input.txt > output.txt

    exit 0  redacted text printed to stdout (empty input -> empty output)
    exit 1  a key-like value was still present after redacting;
            nothing is printed to stdout, a short reason goes to stderr
    exit 2  input could not be read (e.g. not valid UTF-8);
            nothing is printed to stdout, a short reason goes to stderr

Standard library only.
"""

import re
import sys

REDACTED = "[REDACTED]"

# One key character.
_KEY_CHAR = r"[A-Za-z0-9]"

# What may sit BETWEEN two key characters: an optional hyphen, then an
# optional line break (a key wrapped onto the next line). It is only allowed
# between characters, never after the last one, so a complete key at the end
# of a line never pulls in the start of the next line.
_SEP = r"-?(?:\r?\n)?"

# An optional line break, allowed inside the prefix itself.
_BR = r"(?:\r?\n)?"

# The prefix "rly_", any case (IGNORECASE below), possibly wrapped between
# any two of its characters, e.g. "rly" at the end of one line and "_KEY..."
# at the start of the next.
_PREFIX = rf"r{_BR}l{_BR}y{_BR}_"

RELAY_KEY = re.compile(
    rf"{_PREFIX}{_BR}"                   # prefix, maybe wrapped, maybe followed by a line break
    rf"(?:{_KEY_CHAR}{_SEP}){{23}}"      # key chars 1-23, each maybe followed by - or a line break
    rf"{_KEY_CHAR}"                      # key char 24
    r"[A-Za-z0-9-]*",                    # anything key-like glued on the end (overlong key)
    re.IGNORECASE,
)

# Any bearer token of 20+ token characters. "Bearer" in any case
# (bearer, BEARER, ...), since HTTP auth schemes are case-insensitive.
BEARER = re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE)

PATTERNS = [RELAY_KEY, BEARER]

# Leftover check, run on the output: the prefix (any case, possibly wrapped
# inside "rly_") directly followed by a key character. "rly_" followed by a
# space, line break or punctuation is not a leftover.
LEFTOVER = re.compile(rf"{_PREFIX}[A-Za-z0-9]", re.IGNORECASE)


def redact(text):
    for p in PATTERNS:
        text = p.sub(REDACTED, text)
    return text


def find_leftovers(text):
    """Return the 1-based line numbers that still hold a key-like value."""
    return sorted({text.count("\n", 0, m.start()) + 1 for m in LEFTOVER.finditer(text)})


def main():
    try:
        text = sys.stdin.buffer.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"redact: could not read input: {type(e).__name__}", file=sys.stderr)
        return 2

    out = redact(text)

    leftovers = find_leftovers(out)
    if leftovers:
        # Never echo the value itself, only where it is.
        lines = ", ".join(str(n) for n in leftovers)
        print(f"redact: key-like value still present after redacting (line {lines}); "
              f"output withheld", file=sys.stderr)
        return 1

    # Write bytes so line endings come out exactly as they went in.
    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
