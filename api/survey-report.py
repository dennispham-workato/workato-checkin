# Turns a Qualtrics training-survey CSV into the Workato-branded PDF report.
# POST /api/survey-report  (Content-Type: application/json, X-Report-Key)
#   body: { ett_key, csv, summaries?, flags?, timezone? }
#   200 -> application/pdf, attachment "ETT-<n> Survey Report.pdf"
#   400 / 401 / 500 -> { ok:false, message }
# Called by the Workato survey recipe, not the browser. The report logic lives
# in api/_lib/survey_report.py (underscore folder, so it isn't a route).
#
# Gate: X-Report-Key must match REPORT_API_KEY (constant-time compare). When
# REPORT_API_KEY is unset the endpoint is open (demo mode), mirroring how the
# other endpoints behave without SIGNING_SECRET. Always set it on Vercel.

import hmac
import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lib"))

import survey_report  # noqa: E402

MAX_BODY_BYTES = 4 * 1024 * 1024  # Vercel caps request bodies at 4.5 MB anyway


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        expected = os.environ.get("REPORT_API_KEY", "")
        if expected:
            supplied = self.headers.get("X-Report-Key", "")
            # compare_digest on bytes: constant-time for equal lengths and
            # never short-circuits on the first differing byte.
            if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
                self._json(401, "Missing or invalid X-Report-Key.")
                return
        # else: demo mode, no key configured, so the endpoint is open.

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._json(400, "Request body is required.")
            return
        if length > MAX_BODY_BYTES:
            self._json(400, "Request body is too large.")
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, "Body must be valid JSON.")
            return

        try:
            filename, pdf = survey_report.build_report(payload)
        except survey_report.ReportInputError as e:
            self._json(400, str(e))
            return
        except Exception:
            # Log the stack only (never the request body: it holds survey data).
            traceback.print_exc(file=sys.stderr)
            self._json(500, "Report generation failed.")
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % filename)
        self.send_header("Content-Length", str(len(pdf)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(pdf)

    def do_GET(self):
        self._json(405, "Method not allowed.", allow="POST")

    do_PUT = do_PATCH = do_DELETE = do_GET

    def _json(self, status, message, allow=None):
        body = json.dumps({"ok": False, "message": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if allow:
            self.send_header("Allow", allow)
        self.end_headers()
        self.wfile.write(body)
