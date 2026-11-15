#!/usr/bin/env python3
"""Self-test for check_links.py, against a small local web server. Standard library only.

Run: python3 site/tools/test_check_links.py
"""
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CHECKER = Path(__file__).with_name("check_links.py")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body=b"<title>ok</title>", headers=()):
        self.send_response(code)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path
        if p == "/ok":
            self.send(200)
        elif p == "/missing":
            self.send(404)
        elif p == "/cf":
            self.send(403, b"<title>Attention</title>", [("cf-mitigated", "challenge")])
        elif p == "/cf503":
            self.send(503, b"<html><head><title>Just a moment...</title></head></html>")
        elif p == "/cf200":
            self.send(200, b"<html><head><title>Just a moment...</title></head></html>")
        elif p == "/blocked":
            self.send(403)
        elif p == "/login":
            self.send(302, b"", [("Location", "/users/sign_in")])
        elif p == "/users/sign_in":
            self.send(200)
        elif p == "/caf%C3%A9":
            self.send(200)
        elif p == "/slow":
            time.sleep(4)
            self.send(200)
        else:
            self.send(404)


class Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_on(self, paths, *args, env=None):
        with tempfile.TemporaryDirectory() as tmp:
            links = "".join(f'<a href="{self.base}{p}">x</a>' for p in paths)
            Path(tmp, "index.html").write_text(f"<html><body>{links}</body></html>", encoding="utf-8")
            r = subprocess.run([sys.executable, str(CHECKER), tmp, *args], capture_output=True, text=True,
                               env=env, timeout=60)
        return r.returncode, r.stdout + r.stderr

    def line(self, out, path):
        for l in out.splitlines():
            if l.split()[-1:] and f"{self.base}{path} " in l + " ":
                return l
        self.fail(f"{path} not in output:\n{out}")

    def test_ok(self):
        code, out = self.run_on(["/ok"])
        self.assertTrue(self.line(out, "/ok").startswith("ok "))
        self.assertEqual(code, 0)

    def test_cloudflare_header_is_check(self):
        code, out = self.run_on(["/cf"])
        self.assertTrue(self.line(out, "/cf").startswith("CHECK (Cloudflare)"), out)

    def test_cloudflare_503_is_check(self):
        code, out = self.run_on(["/cf503"])
        self.assertTrue(self.line(out, "/cf503").startswith("CHECK (Cloudflare)"), out)

    def test_cloudflare_page_with_200_is_not_ok(self):
        code, out = self.run_on(["/cf200"])
        self.assertTrue(self.line(out, "/cf200").startswith("CHECK (Cloudflare)"), out)

    def test_403_is_check(self):
        self.assertTrue(self.line(self.run_on(["/blocked"])[1], "/blocked").startswith("CHECK 403"))

    def test_404_fails_only_with_strict(self):
        code, out = self.run_on(["/missing"])
        self.assertTrue(self.line(out, "/missing").startswith("FAIL 404"))
        self.assertEqual(code, 0)
        code, out = self.run_on(["/missing"], "--strict")
        self.assertEqual(code, 1)

    def test_sign_in(self):
        self.assertTrue(self.line(self.run_on(["/login"])[1], "/login").startswith("SIGN-IN"))

    def test_non_ascii_address_does_not_crash(self):
        code, out = self.run_on(["/café"])
        self.assertNotIn("Traceback", out)
        self.assertTrue(self.line(out, "/café").startswith("ok"), out)

    def test_actions_warning(self):
        import os
        code, out = self.run_on(["/missing", "/ok"], "--strict", env={**os.environ, "GITHUB_ACTIONS": "true"})
        warnings = [l for l in out.splitlines() if l.startswith("::warning")]
        self.assertEqual(len(warnings), 1, out)
        self.assertIn("/missing", warnings[0])

    def test_time_limit(self):
        start = time.monotonic()
        code, out = self.run_on(["/slow", "/ok"], "--max-seconds", "1")
        self.assertLess(time.monotonic() - start, 3.5)
        self.assertTrue(self.line(out, "/slow").startswith("CHECK (time limit)"), out)
        self.assertEqual(code, 0)

    def test_bad_arguments(self):
        r = subprocess.run([sys.executable, str(CHECKER)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
