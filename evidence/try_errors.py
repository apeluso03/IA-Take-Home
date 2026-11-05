"""Try the rotate helper's error cases against a local fake Relay server.

    python evidence/try_errors.py

Starts a fake server on 127.0.0.1, runs skill/scripts/rotate_key.py the way
the skill does, and prints for each case: the expected and actual exit code,
what the helper printed, and the audit log entries it wrote. Also checks that
no key ever shows up in the output or the log.

Everything runs in a temporary folder (including a temporary home folder for
the default audit log). Fake keys only. No real network. Takes about 25 s
because two cases wait out the helper's 10-second timeout.
"""

import json
import pathlib
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_rotate_key import FakeRelay, run_helper, OLD_KEY, NEW_KEY  # noqa: E402

PASTED = "rly_FAKEp1a2s3t4e5d6k7e8y9z0"  # a fake key someone pasted in the wrong place
SECRETS = (OLD_KEY, NEW_KEY, PASTED)


def main():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="try_errors_"))
    home = tmp / "home"
    home.mkdir()
    log = tmp / "audit.jsonl"
    out = tmp / "new_key.txt"
    existing = tmp / "existing.txt"
    existing.write_text("rly_FAKEkeepme000000000000000", encoding="utf-8")
    not_a_file = tmp / "log-is-a-folder"
    not_a_file.mkdir()

    def break_log():  # make the final audit entry fail mid-call
        log.unlink()
        log.mkdir()

    rotate = ["--service", "billing-sync", "--out", str(out)]
    # (description, server mode, args, extra run_helper options, expected exit, server hook)
    cases = [
        ("--check with RELAY_KEY unset", "ok", ["--check"], {"key": None}, 1, None),
        ("--check with an unwritable audit log", "ok", ["--check"], {"audit_log": not_a_file}, 1, None),
        ("Bad service name", "ok", ["--service", "Billing_Sync", "--out", str(out)], {}, 1, None),
        ("Bad ticket ID", "ok", rotate + ["--ticket", "sup-1234"], {}, 1, None),
        ("A key pasted as the service name", "ok", ["--service", PASTED, "--out", str(out)], {}, 1, None),
        ("A key pasted as the ticket ID", "ok", rotate + ["--ticket", PASTED], {}, 1, None),
        ("--out file already exists", "ok", ["--service", "billing-sync", "--out", str(existing)], {}, 1, None),
        ("RELAY_BASE_URL pointing off this machine", "ok", rotate, {"base_url": "http://example.com"}, 1, None),
        ("A --force flag", "ok", ["--force"] + rotate, {}, 1, None),
        ("Server error (500)", "error", rotate, {}, 2, None),
        ("Timeout (server never answers)", "sleep", rotate, {}, 3, None),
        ("Connection dropped mid-call", "drop", rotate, {}, 3, None),
        ("Rotation ok, but the audit entry can't be written", "ok", rotate, {}, 4, break_log),
    ]

    all_ok = True
    for i, (desc, mode, args, opts, expected, hook) in enumerate(cases, 1):
        for p in (log, out):  # fresh log and --out for each case
            if p.is_dir():
                p.rmdir()
            elif p.exists():
                p.unlink()
        with FakeRelay(mode) as fake:
            fake.on_request = hook
            if "base_url" not in opts:
                opts = dict(opts, base_url=fake.url)
            r = run_helper(args, home=home, **{"audit_log": log, **opts})
        entries = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []
        seen = r.stdout + r.stderr + (log.read_text(encoding="utf-8") if log.is_file() else "")
        leaked = [s for s in SECRETS if s in seen]
        ok = r.returncode == expected and not leaked
        all_ok &= ok

        print(f"\n[{i:2}] {desc}")
        print(f"     expected exit {expected}, got {r.returncode}   requests sent: {len(fake.requests)}"
              f"   {'OK' if ok else 'MISMATCH'}")
        for stream in (r.stdout, r.stderr):
            for line in stream.strip().splitlines():
                if not line.startswith(("usage:", " ")):  # skip argparse's usage block
                    print(f"     | {line}")
        for e in entries:
            extra = f" reason={e['reason']}" if "reason" in e else ""
            print(f"     log: {e['outcome']:<8} service={e['service']} ticket={e['ticket']}{extra}")
        if leaked:
            print("     !! a key appeared in the output or the log")

    print(f"\n{'All cases behaved as expected.' if all_ok else 'Some cases did NOT behave as expected.'}")
    print(f"Temporary files: {tmp}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
