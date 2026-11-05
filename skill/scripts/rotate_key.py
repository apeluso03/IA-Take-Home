"""Rotate a Relay service key. Standard library only.

    python scripts/rotate_key.py --check
    python scripts/rotate_key.py --service <name> --out <path> [--ticket <id>]

The current key is read from the RELAY_KEY environment variable, never from
the command line. No key is ever printed: only the last 4 characters of the
new key, on success.

Every rotation attempt is appended to the audit log (JSON Lines) at
RELAY_AUDIT_LOG, or ~/.relay/rotation-audit.jsonl if that is not set. The log never holds any part of any key. Bad input values are
never logged or printed, only which field was wrong.

Exit codes
    0  --check: RELAY_KEY is set and the audit log can be written.
       rotate: success, new key saved to --out.
    1  --check: RELAY_KEY not set, or the audit log can't be written.
       rotate: bad input or no usable audit log, nothing was sent.
    2  rotate: the server answered with an error status. No key was created.
    3  rotate: outcome unknown (timeout, dropped connection, unreadable
       response, or the new key could not be saved). A key may have been
       created: check Relay before trying again.
    4  rotate: the call finished (ok or unknown) but the audit entry could
       not be written. Do not retry.
"""

import argparse
import getpass
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DEFAULT_BASE_URL = "https://relay.example.internal"
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
ROTATE_PATH = "/v1/keys/rotate"
TIMEOUT_SECONDS = 10
SERVICE_RE = re.compile(r"[a-z0-9-]+")
TICKET_RE = re.compile(r"[A-Z]+-[0-9]+")

EXIT_OK, EXIT_BAD_INPUT, EXIT_FAILED, EXIT_UNKNOWN, EXIT_AUDIT_INCOMPLETE = 0, 1, 2, 3, 4

# Write files as raw bytes on every OS (no \n -> \r\n on Windows).
_O_BINARY = getattr(os, "O_BINARY", 0)


class BadInput(Exception):
    """Something is wrong before any network call.

    `reason` is a fixed code for the audit log. The message names the field
    and never contains the value.
    """

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # urllib follows redirects by default and copies the Authorization header
    # to the new location. Refuse instead: a 3xx becomes an HTTPError (exit 2).
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _ArgParser(argparse.ArgumentParser):
    # argparse's own messages can repeat what was typed (e.g. "unrecognized
    # arguments: <value>"), and that value could be a pasted key. Print a
    # fixed message instead. Also: argparse exits 2, but 2 means "server
    # error" here, so use 1.
    def error(self, message):
        self.print_usage(sys.stderr)
        print("error: invalid command-line arguments (values not shown)", file=sys.stderr)
        _log_rejected("bad_arguments", service=None, ticket=None)
        sys.exit(EXIT_BAD_INPUT)


# --------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------

DEFAULT_AUDIT_LOG = os.path.join("~", ".relay", "rotation-audit.jsonl")


def audit_log_path():
    """RELAY_AUDIT_LOG, or the default path (creating ~/.relay/ if needed).

    Returns None if the default folder can't be found or created. Only the
    default's folder is created; a set RELAY_AUDIT_LOG is used as given.
    """
    override = os.environ.get("RELAY_AUDIT_LOG")
    if override:
        return override
    path = os.path.expanduser(DEFAULT_AUDIT_LOG)
    if path.startswith("~"):
        return None  # no home folder
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    except OSError:
        return None
    return path


def audit_log_writable(log_path):
    """True if the log can be opened for append. Writes nothing."""
    try:
        os.close(os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | _O_BINARY, 0o600))
        return True
    except OSError:
        return False


def _user():
    try:
        return getpass.getuser()
    except Exception:
        return None


def append_audit(log_path, outcome, service, ticket, reason=None):
    """Append one JSON line to the audit log. Return True if it was written.

    Opens, writes, syncs, and closes for every entry, so each entry is on
    disk before the next step. Only these fields are ever written.
    """
    entry = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "service": service,
        "user": _user(),
        "outcome": outcome,
        "ticket": ticket,
    }
    if reason is not None:
        entry["reason"] = reason
    line = (json.dumps(entry) + "\n").encode("utf-8")
    try:
        fd = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | _O_BINARY, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)
        return True
    except OSError:
        return False


def _log_rejected(reason, service, ticket):
    """Record a rejected attempt, if there is a log to record it in."""
    log_path = audit_log_path()
    if log_path and not append_audit(log_path, "rejected", service, ticket, reason):
        print("warning: the audit entry for this rejected attempt could not be written",
              file=sys.stderr)


def _audit_warning():
    print("warning: the rotate call finished, but the audit entry could not be written. "
          "Do not retry.", file=sys.stderr)


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

def read_key():
    """Return RELAY_KEY, or raise BadInput. Never includes the value."""
    key = os.environ.get("RELAY_KEY", "")
    if not key:
        raise BadInput("missing_relay_key", "RELAY_KEY is not set")
    if any(c.isspace() or not c.isprintable() for c in key):
        raise BadInput("invalid_relay_key", "RELAY_KEY contains whitespace or control characters")
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
        raise BadInput("invalid_base_url", "RELAY_BASE_URL is not a valid URL")
    if (parts.scheme != "http"
            or parts.hostname not in LOCAL_HOSTS
            or parts.username is not None
            or parts.path not in ("", "/")
            or parts.query or parts.fragment):
        raise BadInput("invalid_base_url",
                       "RELAY_BASE_URL may only be http://127.0.0.1 or http://localhost")
    return override.rstrip("/")


def check():
    try:
        read_key()
    except BadInput as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_BAD_INPUT
    log_path = audit_log_path()
    if not log_path or not audit_log_writable(log_path):
        print("error: the audit log can't be written (RELAY_AUDIT_LOG or "
              "~/.relay/rotation-audit.jsonl)", file=sys.stderr)
        return EXIT_BAD_INPUT
    print("ok RELAY_KEY is set, audit log is writable")
    return EXIT_OK


# --------------------------------------------------------------------------
# Rotate
# --------------------------------------------------------------------------

def rotate(service, out_path, ticket):
    log_path = audit_log_path()
    if not log_path:
        # Nowhere to record anything, so nothing may happen.
        print("error: the default audit log folder (~/.relay) can't be created; nothing was sent",
              file=sys.stderr)
        return EXIT_BAD_INPUT

    # --- Local checks only; no network yet. Valid values are kept for the
    # log as they pass; a value that fails is never logged or printed. ---
    logged_service = logged_ticket = None
    fd = None
    try:
        if not SERVICE_RE.fullmatch(service):
            raise BadInput("invalid_service_name",
                           "invalid service name (not shown): use lowercase letters, digits, and hyphens")
        logged_service = service
        if ticket is not None:
            if not TICKET_RE.fullmatch(ticket):
                raise BadInput("invalid_ticket_id",
                               "invalid ticket ID (not shown): use uppercase letters, a hyphen, digits, e.g. SUP-5521")
            logged_ticket = ticket
        url = base_url() + ROTATE_PATH
        key = read_key()

        # Create --out now (exclusive: fails if it exists, never overwrites),
        # so a bad path is caught before a key is created. Owner-only.
        try:
            fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_BINARY, 0o600)
        except FileExistsError:
            raise BadInput("out_exists", "--out already exists; refusing to overwrite it")
        except OSError as e:
            raise BadInput("out_not_creatable", f"cannot create --out file ({type(e).__name__})")
    except BadInput as e:
        print(f"error: {e}", file=sys.stderr)
        if not append_audit(log_path, "rejected", logged_service, logged_ticket, e.reason):
            print("warning: the audit entry for this rejected attempt could not be written",
                  file=sys.stderr)
        return EXIT_BAD_INPUT

    saved = False
    try:
        # The "started" entry must be on disk before anything is sent.
        if not append_audit(log_path, "started", service, ticket):
            print("error: the audit log could not be written; nothing was sent", file=sys.stderr)
            return EXIT_BAD_INPUT

        outcome, code = _send_once(url, key, service, fd)
        if code == EXIT_OK:
            fd = None  # _send_once closed it after writing the key
            saved = True

        if not append_audit(log_path, outcome, service, ticket):
            _audit_warning()
            # Exit 4 means "the call went through, the record is missing".
            # A failed call created no key, so it keeps exit 2.
            return EXIT_FAILED if outcome == "failed" else EXIT_AUDIT_INCOMPLETE
        return code
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if not saved:
            # Don't leave an empty or partial key file behind.
            try:
                os.remove(out_path)
            except OSError:
                pass


def _send_once(url, key, service, fd):
    """Make exactly one request. Print the outcome line. Return (outcome, exit code)."""
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
            return "failed", EXIT_FAILED
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
        except OSError:
            print(f"unknown service={service}: a new key was created but could not be "
                  f"saved to --out, check Relay before retrying")
            return "unknown", EXIT_UNKNOWN
        print(f"ok service={service} last4={new_key[-4:]}")
        return "ok", EXIT_OK
    except Exception:
        # Anything unexpected after "started": the call may have gone out.
        return _unknown(service)


def _unknown(service):
    print(f"unknown service={service}: a key may have been created, check Relay before retrying")
    return "unknown", EXIT_UNKNOWN


def main(argv=None):
    parser = _ArgParser(description="Rotate a Relay service key. Reads the key from RELAY_KEY.")
    parser.add_argument("--check", action="store_true", help="confirm RELAY_KEY is set")
    parser.add_argument("--service", help="service name: lowercase letters, digits, hyphens")
    parser.add_argument("--out", help="new file to save the new key to (must not exist)")
    parser.add_argument("--ticket", help="optional ticket ID for the audit log, e.g. SUP-5521")
    args = parser.parse_args(argv)

    if args.check:
        if args.service or args.out or args.ticket:
            parser.error("--check cannot be combined with other options")
        return check()
    if not (args.service and args.out):
        parser.error("--service and --out are both required")
    return rotate(args.service, args.out, args.ticket)


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
