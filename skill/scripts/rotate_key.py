"""Rotate a Relay service key. Standard library only.

    python scripts/rotate_key.py --check
    python scripts/rotate_key.py --service <name> --out <path>

The current key is read from the RELAY_KEY environment variable, never from
the command line. No key is ever printed: only the last 4 characters of the
new key, on success.

Exit codes
    0  --check: RELAY_KEY is set.   rotate: success, new key saved to --out.
    1  --check: RELAY_KEY not set.  rotate: bad input, nothing was sent.
    2  rotate: the server answered with an error status. No key was created.
    3  rotate: outcome unknown (timeout, dropped connection, unreadable
       response, or the new key could not be saved). A key may have been
       created: check Relay before trying again.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = "https://relay.example.internal"
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
ROTATE_PATH = "/v1/keys/rotate"
TIMEOUT_SECONDS = 10
SERVICE_RE = re.compile(r"[a-z0-9-]+")

EXIT_OK, EXIT_BAD_INPUT, EXIT_FAILED, EXIT_UNKNOWN = 0, 1, 2, 3


class BadInput(Exception):
    """Something is wrong before any network call. Message never holds a key."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # urllib follows redirects by default and copies the Authorization header
    # to the new location. Refuse instead: a 3xx becomes an HTTPError (exit 2).
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _ArgParser(argparse.ArgumentParser):
    # argparse exits 2 on bad arguments; 2 means "server error" here, so use 1.
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"error: {message}", file=sys.stderr)
        sys.exit(EXIT_BAD_INPUT)


def read_key():
    """Return RELAY_KEY, or raise BadInput. Never includes the value."""
    key = os.environ.get("RELAY_KEY", "")
    if not key:
        raise BadInput("RELAY_KEY is not set")
    if any(c.isspace() or not c.isprintable() for c in key):
        raise BadInput("RELAY_KEY contains whitespace or control characters")
    return key


def base_url():
    """Default URL, or a RELAY_BASE_URL override that points at this machine."""
    override = os.environ.get("RELAY_BASE_URL")
    if override is None:
        return DEFAULT_BASE_URL
    try:
        parts = urllib.parse.urlsplit(override)
        parts.port  # raises ValueError on a bad port
    except ValueError:
        raise BadInput("RELAY_BASE_URL is not a valid URL")
    if (parts.scheme != "http"
            or parts.hostname not in LOCAL_HOSTS
            or parts.username is not None
            or parts.path not in ("", "/")
            or parts.query or parts.fragment):
        raise BadInput("RELAY_BASE_URL may only be http://127.0.0.1 or http://localhost")
    return override.rstrip("/")


def check():
    try:
        read_key()
    except BadInput as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_BAD_INPUT
    print("ok RELAY_KEY is set")
    return EXIT_OK


def rotate(service, out_path):
    # --- Everything below until the request is local; no network yet. ---
    if not SERVICE_RE.fullmatch(service):
        raise BadInput("service name must be lowercase letters, digits, and hyphens")
    url = base_url() + ROTATE_PATH
    key = read_key()

    # Create --out now (exclusive: fails if it exists, never overwrites), so
    # a bad path is caught before a key is created. Owner-only permissions.
    try:
        fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise BadInput("--out already exists; refusing to overwrite it")
    except OSError as e:
        raise BadInput(f"cannot create --out file ({type(e).__name__})")

    saved = False
    try:
        request = urllib.request.Request(
            url,
            data=json.dumps({"service": service}).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        handlers = [_NoRedirect()]
        if url.startswith("http://"):
            # Local test server only: don't route the key through any proxy.
            handlers.append(urllib.request.ProxyHandler({}))
        opener = urllib.request.build_opener(*handlers)

        # --- Exactly one request. No retries anywhere. ---
        try:
            with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                body = response.read()
        except urllib.error.HTTPError as e:
            e.close()  # body is never read or printed
            print(f"failed service={service} status={e.code}")
            return EXIT_FAILED
        except Exception:
            # Timeout, dropped connection, anything else after we tried to send.
            return _unknown(service)

        try:
            new_key = json.loads(body)["new_key"]
        except Exception:
            return _unknown(service)
        if (not isinstance(new_key, str) or len(new_key) < 8
                or any(c.isspace() or not c.isprintable() for c in new_key)):
            return _unknown(service)

        try:
            os.write(fd, new_key.encode("utf-8"))
            os.close(fd)
            fd = None
        except OSError:
            print(f"unknown service={service}: a new key was created but could not be "
                  f"saved to --out, check Relay before retrying")
            return EXIT_UNKNOWN
        saved = True
        print(f"ok service={service} last4={new_key[-4:]}")
        return EXIT_OK
    finally:
        if fd is not None:
            os.close(fd)
        if not saved:
            # Don't leave an empty or partial key file behind.
            try:
                os.remove(out_path)
            except OSError:
                pass


def _unknown(service):
    print(f"unknown service={service}: a key may have been created, check Relay before retrying")
    return EXIT_UNKNOWN


def main(argv=None):
    parser = _ArgParser(description="Rotate a Relay service key. Reads the key from RELAY_KEY.")
    parser.add_argument("--check", action="store_true", help="confirm RELAY_KEY is set")
    parser.add_argument("--service", help="service name: lowercase letters, digits, hyphens")
    parser.add_argument("--out", help="new file to save the new key to (must not exist)")
    args = parser.parse_args(argv)

    if args.check:
        if args.service or args.out:
            parser.error("--check cannot be combined with --service or --out")
        return check()
    if not (args.service and args.out):
        parser.error("--service and --out are both required")
    try:
        return rotate(args.service, args.out)
    except BadInput as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_BAD_INPUT


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException as e:
        if isinstance(e, SystemExit):
            raise
        # Last resort: never let a traceback print (it could hold header values).
        # Treated as unknown, because we can't tell whether the request was sent.
        print(f"unknown: unexpected {type(e).__name__}, check Relay before retrying",
              file=sys.stderr)
        sys.exit(EXIT_UNKNOWN)
