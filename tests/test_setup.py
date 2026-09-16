import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class SetupTest(unittest.TestCase):
    def request(self, path, data=None):
        body = None if data is None else json.dumps(data).encode()
        request = Request(
            self.base_url + path, data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def start_server(self, database):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        log = tempfile.TemporaryFile(mode="w+")
        self.addCleanup(log.close)
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "DATABASE_URL": f"sqlite:///{database}"},
            stdout=log, stderr=log,
        )
        self.addCleanup(self.stop_server, process)
        for _ in range(100):
            if process.poll() is not None:
                break
            try:
                if self.request("/health") == (200, {"status": "ok"}):
                    return process
            except (URLError, TimeoutError):
                pass
            time.sleep(0.05)
        log.seek(0)
        self.fail(f"API did not start: {log.read()}")

    @staticmethod
    def stop_server(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def test_setup_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "test.db"
            process = self.start_server(database)
            try:
                self.assertEqual(self.request("/")[0], 200)
                self.assertEqual(self.request("/openapi.json")[0], 200)
                user = {"name": " Alice ", "email": "alice@example.com"}
                status, created = self.request("/users/", user)
                self.assertEqual(status, 201)
                self.assertEqual(created["name"], "Alice")
                self.assertIsInstance(created["id"], int)
                self.assertEqual(self.request("/users/", user)[0], 409)
                for invalid in [
                    {"name": "   ", "email": "a@example.com"},
                    {"name": "Alice", "email": "invalid"},
                    {"name": "A" * 101, "email": "a@example.com"},
                ]:
                    self.assertEqual(self.request("/users/", invalid)[0], 422)
                self.assertEqual(self.request("/users/", {"name": "Bob", "email": "bob@example.com"})[0], 201)
            finally:
                self.stop_server(process)
            process = self.start_server(database)
            try:
                self.assertEqual(self.request("/users/", user)[0], 409)
            finally:
                self.stop_server(process)


if __name__ == "__main__":
    unittest.main()
