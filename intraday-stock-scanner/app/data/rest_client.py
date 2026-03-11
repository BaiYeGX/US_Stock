from __future__ import annotations

import time

import httpx


class RestClient:
    def __init__(self, retries: int = 3, backoff: float = 0.3) -> None:
        self.client = httpx.Client(timeout=10)
        self.retries = retries
        self.backoff = backoff

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        err = None
        for i in range(self.retries):
            try:
                resp = self.client.get(url, params=params)
                resp.raise_for_status()
                return resp
            except Exception as exc:
                err = exc
                time.sleep(self.backoff * (2**i))
        raise RuntimeError(f"GET failed after retries: {url}") from err
