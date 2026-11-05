"""Tests for skill/scripts/rotate_key.py. DRAFT - written by Claude Code for review.

Every test talks to a local fake server on 127.0.0.1 (http.server in a
thread). No real network. All keys are made up and start with rly_FAKE.
The helper runs as a subprocess, the same way the skill runs it.
"""

import getpass
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
HELPER = ROOT / "skill" / "scripts" / "rotate_key.py"

OLD_KEY = "rly_FAKEo1l2d3k4e5y6o7l8d9k0"
NEW_KEY = "rly_FAKEn1e2w3k4e5y6n7e8w9k0"
NEW_LAST4 = NEW_KEY[-4:]
SERVICE = "billing-sync"
TICKET = "SUP-1234"
ENTRY_FIELDS = {"time", "service", "user", "outcome", "ticket"}


class FakeRelay:
    """Local fake Relay. `mode` picks the reply; every request is recorded.

    `on_request`, if set, is called when a request arrives, before replying.
    """

    def __init__(self, mode="ok"):
        self.mode = mode
        self.requests = []
        self.on_request = None
        self.release = threading.Event()  # lets a sleeping handler finish early
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                fake.requests.append({
                    "method": "POST",
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": body,
                })
                if fake.on_request:
                    fake.on_request()
                if fake.mode == "ok":
                    self._reply(200, {"service": SERVICE, "new_key": NEW_KEY, "status": "ok"})
                elif fake.mode == "error":
                    self._reply(500, {"error": "boom", "echo": OLD_KEY})
                elif fake.mode == "redirect":
                    self.send_response(302)
                    self.send_header("Location", fake.redirect_to)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                elif fake.mode == "sleep":
                    fake.release.wait(timeout=13)  # past the helper's 10 s timeout
                elif fake.mode == "drop":
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)

            def _reply(self, code, payload):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

            def handle(self):
                try:
                    super().handle()
                except OSError:
                    pass  # client already gave up (timeout / drop tests)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()


_FAKE_HOME = None


def setUpModule():
    # Every helper run gets a temporary home folder, so the default audit log
    # (~/.relay/rotation-audit.jsonl) never touches the real one.
    global _FAKE_HOME
    _FAKE_HOME = tempfile.TemporaryDirectory()


def tearDownModule():
    _FAKE_HOME.cleanup()


def run_helper(args, key=OLD_KEY, base_url=None, audit_log=None, home=None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("RELAY_KEY", "RELAY_BASE_URL", "RELAY_AUDIT_LOG")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["HOME"] = env["USERPROFILE"] = str(home or _FAKE_HOME.name)
    if key is not None:
        env["RELAY_KEY"] = key
    if base_url is not None:
        env["RELAY_BASE_URL"] = base_url
    if audit_log is not None:
        env["RELAY_AUDIT_LOG"] = str(audit_log)
    cmd = [sys.executable, str(HELPER)] + args
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    result.cmd = cmd
    return result


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)
        self.out = self.dir / "new_key.txt"
        self.log = self.dir / "audit.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def rotate(self, fake, service=SERVICE, ticket=None, out=None, **kw):
        args = ["--service", service, "--out", str(out or self.out)]
        if ticket is not None:
            args += ["--ticket", ticket]
        kw.setdefault("audit_log", self.log)
        return run_helper(args, base_url=fake.url, **kw)

    def entries(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def outcomes(self):
        return [e["outcome"] for e in self.entries()]

    def assertNoKeyInOutput(self, result):
        for key in (OLD_KEY, NEW_KEY):
            self.assertNotIn(key, result.stdout)
            self.assertNotIn(key, result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class TestCheck(TempDirTest):
    def test_key_set(self):
        r = run_helper(["--check"], key=OLD_KEY)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNoKeyInOutput(r)
        self.assertNotIn(OLD_KEY[-4:], r.stdout + r.stderr)  # not even partly

    def test_key_unset(self):
        r = run_helper(["--check"], key=None)
        self.assertEqual(r.returncode, 1)
        self.assertNoKeyInOutput(r)

    def test_key_empty(self):
        r = run_helper(["--check"], key="")
        self.assertEqual(r.returncode, 1)
        self.assertNoKeyInOutput(r)

    def test_log_not_writable(self):
        self.log.mkdir()  # a directory can't be opened for append
        r = run_helper(["--check"], audit_log=self.log)
        self.assertEqual(r.returncode, 1)
        self.assertNoKeyInOutput(r)

    def test_default_log_folder_created_no_entry(self):
        home = self.dir / "home"
        home.mkdir()
        r = run_helper(["--check"], home=home)
        self.assertEqual(r.returncode, 0, r.stderr)
        default_log = home / ".relay" / "rotation-audit.jsonl"
        self.assertTrue(default_log.parent.is_dir())
        self.assertEqual(default_log.read_text(encoding="utf-8"), "")  # --check logs nothing


class TestRotate(TempDirTest):
    def test_success(self):
        with FakeRelay("ok") as fake:
            r = self.rotate(fake)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.out.read_text(encoding="utf-8"), NEW_KEY)
        self.assertEqual(r.stdout.strip(), f"ok service={SERVICE} last4={NEW_LAST4}")
        self.assertNoKeyInOutput(r)
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(self.outcomes(), ["started", "ok"])

    def test_request_shape(self):
        with FakeRelay("ok") as fake:
            self.rotate(fake)
        req = fake.requests[0]
        self.assertEqual(req["method"], "POST")
        self.assertEqual(req["path"], "/v1/keys/rotate")
        self.assertEqual(json.loads(req["body"]), {"service": SERVICE})

    def test_key_sent_in_header_not_command_line(self):
        with FakeRelay("ok") as fake:
            r = self.rotate(fake)
        self.assertEqual(fake.requests[0]["headers"].get("Authorization"), f"Bearer {OLD_KEY}")
        self.assertFalse(any(OLD_KEY in arg for arg in r.cmd))

    def test_bad_service_name(self):
        for bad in ["Billing-Sync", "billing_sync", "billing sync", "a/b", "x;rm"]:
            with self.subTest(service=bad), FakeRelay("ok") as fake:
                r = self.rotate(fake, service=bad)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(len(fake.requests), 0)
                self.assertFalse(self.out.exists())

    def test_server_error(self):
        with FakeRelay("error") as fake:
            r = self.rotate(fake)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.strip(), f"failed service={SERVICE} status=500")
        self.assertEqual(len(fake.requests), 1)
        self.assertNoKeyInOutput(r)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.outcomes(), ["started", "failed"])

    def test_timeout(self):
        start = time.monotonic()
        with FakeRelay("sleep") as fake:
            r = self.rotate(fake)
        self.assertLess(time.monotonic() - start, 15)
        self.assertEqual(r.returncode, 3)
        self.assertIn(f"unknown service={SERVICE}", r.stdout)
        self.assertEqual(len(fake.requests), 1)
        self.assertNoKeyInOutput(r)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.outcomes(), ["started", "unknown"])

    def test_connection_dropped(self):
        with FakeRelay("drop") as fake:
            r = self.rotate(fake)
        self.assertEqual(r.returncode, 3)
        self.assertEqual(len(fake.requests), 1)
        self.assertNoKeyInOutput(r)
        self.assertEqual(self.outcomes(), ["started", "unknown"])

    def test_out_already_exists(self):
        self.out.write_text("rly_FAKEkeepme000000000000000", encoding="utf-8")
        with FakeRelay("ok") as fake:
            r = self.rotate(fake)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(fake.requests), 0)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "rly_FAKEkeepme000000000000000")

    def test_redirect_not_followed(self):
        with FakeRelay("ok") as target, FakeRelay("redirect") as fake:
            fake.redirect_to = target.url + "/v1/keys/rotate"
            r = self.rotate(fake)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(len(target.requests), 0)
        self.assertNoKeyInOutput(r)

    def test_key_unset_sends_nothing(self):
        with FakeRelay("ok") as fake:
            r = self.rotate(fake, key=None)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(fake.requests), 0)


class TestAuditLog(TempDirTest):
    def test_entry_fields_and_utc_time(self):
        with FakeRelay("ok") as fake:
            self.rotate(fake)
        for e in self.entries():
            self.assertEqual(set(e), ENTRY_FIELDS)
            self.assertEqual(e["service"], SERVICE)
            self.assertEqual(e["user"], getpass.getuser())
            self.assertEqual(datetime.fromisoformat(e["time"]).utcoffset(), timedelta(0))

    def test_ticket_recorded(self):
        with FakeRelay("ok") as fake:
            r = self.rotate(fake, ticket=TICKET)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([e["ticket"] for e in self.entries()], [TICKET, TICKET])

    def test_no_ticket_records_null(self):
        with FakeRelay("ok") as fake:
            self.rotate(fake)
        self.assertEqual([e["ticket"] for e in self.entries()], [None, None])

    def test_started_is_written_before_the_request(self):
        seen = []
        with FakeRelay("ok") as fake:
            fake.on_request = lambda: seen.append(self.outcomes())
            self.rotate(fake)
        self.assertEqual(seen, [["started"]])

    def test_invalid_ticket_rejected(self):
        for bad in ["sup-1234", "SUP1234", "SUP-12a", "SUP-1234 ", "-1234"]:
            with self.subTest(ticket=bad), FakeRelay("ok") as fake:
                self.log.unlink(missing_ok=True)
                r = self.rotate(fake, ticket=bad)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(len(fake.requests), 0)
                (entry,) = self.entries()
                self.assertEqual(entry["outcome"], "rejected")
                self.assertEqual(entry["reason"], "invalid_ticket_id")
                self.assertEqual(entry["ticket"], None)
                self.assertEqual(entry["service"], SERVICE)  # the valid field is kept
                self.assertEqual(set(entry), ENTRY_FIELDS | {"reason"})

    def test_bad_service_name_rejected_and_value_not_logged(self):
        bad = "Billing_Sync"
        with FakeRelay("ok") as fake:
            r = self.rotate(fake, service=bad, ticket=TICKET)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(fake.requests), 0)
        (entry,) = self.entries()
        self.assertEqual(entry["outcome"], "rejected")
        self.assertEqual(entry["reason"], "invalid_service_name")
        self.assertEqual(entry["service"], None)
        self.assertNotIn(bad, self.log.read_text(encoding="utf-8"))
        self.assertNotIn(bad, r.stdout + r.stderr)

    def test_fake_key_as_input_appears_nowhere(self):
        pasted = "rly_FAKEp1a2s3t4e5d6k7e8y9z0"
        cases = {
            "as service": dict(service=pasted),
            "as ticket": dict(ticket=pasted),
        }
        for label, kw in cases.items():
            with self.subTest(label), FakeRelay("ok") as fake:
                self.log.unlink(missing_ok=True)
                r = self.rotate(fake, **kw)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(len(fake.requests), 0)
                self.assertNotIn(pasted, self.log.read_text(encoding="utf-8"))
                self.assertNotIn(pasted, r.stdout)
                self.assertNotIn(pasted, r.stderr)
        with self.subTest("as an unknown argument"), FakeRelay("ok") as fake:
            r = run_helper(["--service", SERVICE, "--out", str(self.out), pasted],
                           base_url=fake.url, audit_log=self.log)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(len(fake.requests), 0)
            self.assertNotIn(pasted, r.stdout + r.stderr)
            self.assertNotIn(pasted, self.log.read_text(encoding="utf-8"))

    def test_log_unset_uses_default_path(self):
        home = self.dir / "home"
        home.mkdir()
        with FakeRelay("ok") as fake:
            r = self.rotate(fake, audit_log=None, home=home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.log = home / ".relay" / "rotation-audit.jsonl"
        self.assertEqual(self.outcomes(), ["started", "ok"])

    def test_default_folder_not_creatable_sends_nothing(self):
        home = self.dir / "home-is-a-file"
        home.write_text("x", encoding="utf-8")  # ~/.relay can't be created under a file
        with FakeRelay("ok") as fake:
            r = self.rotate(fake, audit_log=None, home=home)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(fake.requests), 0)
        self.assertFalse(self.out.exists())

    def test_log_not_writable_sends_nothing(self):
        self.log.mkdir()  # a directory can't be opened for append
        with FakeRelay("ok") as fake:
            r = self.rotate(fake)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(fake.requests), 0)
        self.assertFalse(self.out.exists())

    def test_two_runs_append(self):
        with FakeRelay("ok") as fake:
            self.rotate(fake, out=self.dir / "first.txt")
            first = self.log.read_text(encoding="utf-8")
            self.rotate(fake, out=self.dir / "second.txt")
        after = self.log.read_text(encoding="utf-8")
        self.assertTrue(after.startswith(first))
        self.assertEqual(self.outcomes(), ["started", "ok", "started", "ok"])

    def test_no_key_material_in_log(self):
        with FakeRelay("ok") as fake:
            self.rotate(fake, ticket=TICKET)
        with FakeRelay("error") as fake:
            self.rotate(fake, out=self.dir / "other.txt")
        text = self.log.read_text(encoding="utf-8")
        for secret in (OLD_KEY, NEW_KEY, NEW_LAST4, OLD_KEY[-4:]):
            self.assertNotIn(secret, text)

    def _break_log(self):
        # Swap the log for a directory once the request is in flight, so the
        # final entry can't be written.
        self.log.unlink()
        self.log.mkdir()

    def test_final_entry_fails_after_success_exits_4(self):
        with FakeRelay("ok") as fake:
            fake.on_request = self._break_log
            r = self.rotate(fake)
        self.assertEqual(r.returncode, 4)
        self.assertEqual(r.stdout.strip(), f"ok service={SERVICE} last4={NEW_LAST4}")
        self.assertIn("audit entry could not be written", r.stderr)
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(self.out.read_text(encoding="utf-8"), NEW_KEY)  # key still saved
        self.assertNoKeyInOutput(r)

    def test_final_entry_fails_after_server_error_keeps_exit_2(self):
        with FakeRelay("error") as fake:
            fake.on_request = self._break_log
            r = self.rotate(fake)
        self.assertEqual(r.returncode, 2)
        self.assertIn("audit entry could not be written", r.stderr)
        self.assertEqual(len(fake.requests), 1)


class TestBaseUrl(TempDirTest):
    def test_non_local_override_refused(self):
        with FakeRelay("ok") as fake:
            port = fake.url.rsplit(":", 1)[1]
            for url in [
                "https://relay.example.internal",       # even the real one, as an override
                "http://example.com",
                f"https://127.0.0.1:{port}",            # local host but not plain http
                f"http://localhost@example.com:{port}",  # userinfo trick
                f"http://127.0.0.1.example.com:{port}",
                f"http://127.0.0.1:{port}/elsewhere",
            ]:
                with self.subTest(url=url):
                    r = run_helper(["--service", SERVICE, "--out", str(self.out)],
                                   base_url=url, audit_log=self.log)
                    self.assertEqual(r.returncode, 1)
                    self.assertFalse(self.out.exists())
            self.assertEqual(len(fake.requests), 0)
        self.assertEqual(set(self.outcomes()), {"rejected"})

    def test_localhost_override_allowed(self):
        with FakeRelay("ok") as fake:
            url = fake.url.replace("127.0.0.1", "localhost")
            r = run_helper(["--service", SERVICE, "--out", str(self.out)],
                           base_url=url, audit_log=self.log)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(len(fake.requests), 1)


class TestNoExtraFlags(unittest.TestCase):
    def test_no_force_skip_or_retry_flags(self):
        for flag in ["--force", "--skip", "--retry", "--yes", "--key"]:
            with self.subTest(flag=flag):
                r = run_helper([flag, "--service", SERVICE, "--out", "x"], base_url="http://127.0.0.1:9")
                self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
