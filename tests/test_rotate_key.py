"""Tests for skill/scripts/rotate_key.py. DRAFT - written by Claude Code for review.

Every test talks to a local fake server on 127.0.0.1 (http.server in a
thread). No real network. All keys are made up and start with rly_FAKE.
The helper runs as a subprocess, the same way the skill runs it.
"""

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
HELPER = ROOT / "skill" / "scripts" / "rotate_key.py"

OLD_KEY = "rly_FAKEo1l2d3k4e5y6o7l8d9k0"
NEW_KEY = "rly_FAKEn1e2w3k4e5y6n7e8w9k0"
NEW_LAST4 = NEW_KEY[-4:]
SERVICE = "billing-sync"


class FakeRelay:
    """Local fake Relay. `mode` picks the reply; every request is recorded."""

    def __init__(self, mode="ok"):
        self.mode = mode
        self.requests = []
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


def run_helper(args, key=OLD_KEY, base_url=None):
    env = {k: v for k, v in os.environ.items() if k not in ("RELAY_KEY", "RELAY_BASE_URL")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if key is not None:
        env["RELAY_KEY"] = key
    if base_url is not None:
        env["RELAY_BASE_URL"] = base_url
    cmd = [sys.executable, str(HELPER)] + args
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    result.cmd = cmd
    return result


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = pathlib.Path(self._tmp.name) / "new_key.txt"

    def tearDown(self):
        self._tmp.cleanup()

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


class TestRotate(TempDirTest):
    def rotate(self, fake, service=SERVICE, **kw):
        return run_helper(["--service", service, "--out", str(self.out)],
                          base_url=fake.url, **kw)

    def test_success(self):
        with FakeRelay("ok") as fake:
            r = self.rotate(fake)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.out.read_text(encoding="utf-8"), NEW_KEY)
        self.assertEqual(r.stdout.strip(), f"ok service={SERVICE} last4={NEW_LAST4}")
        self.assertNoKeyInOutput(r)
        self.assertEqual(len(fake.requests), 1)

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

    def test_connection_dropped(self):
        with FakeRelay("drop") as fake:
            r = self.rotate(fake)
        self.assertEqual(r.returncode, 3)
        self.assertEqual(len(fake.requests), 1)
        self.assertNoKeyInOutput(r)

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
                    r = run_helper(["--service", SERVICE, "--out", str(self.out)], base_url=url)
                    self.assertEqual(r.returncode, 1)
                    self.assertFalse(self.out.exists())
            self.assertEqual(len(fake.requests), 0)

    def test_localhost_override_allowed(self):
        with FakeRelay("ok") as fake:
            url = fake.url.replace("127.0.0.1", "localhost")
            r = run_helper(["--service", SERVICE, "--out", str(self.out)], base_url=url)
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
