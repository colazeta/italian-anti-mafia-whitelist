"""Temporary runner-local compatibility shim for the Bari finalizer.

This file is intentionally removed before the production pull request. It exists
only because the temporary finalizer uses the requests Session interface while
requests is not a project dependency.
"""
from urllib.request import Request, urlopen


class Response:
    def __init__(self, body: bytes, status: int):
        self.content = body
        self.status_code = status
        self.text = body.decode("utf-8", errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Session:
    def get(self, url: str, *, headers=None, timeout=30):
        request = Request(url, headers=headers or {})
        with urlopen(request, timeout=timeout) as response:
            return Response(response.read(), int(getattr(response, "status", 200)))
