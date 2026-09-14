from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse


class HttpTransport(Protocol):
    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict | None = None,
    ) -> dict: ...

    def download(self, url: str, destination: Path) -> Path: ...


def _require_https(url: str) -> None:
    if urlparse(url).scheme != "https":
        raise ValueError(f"Only HTTPS provider URLs are allowed: {url}")


class UrllibTransport:
    """Small standard-library transport shared by optional generation providers."""

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict | None = None,
    ) -> dict:
        _require_https(url)
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Provider request failed ({error.code}): {detail}") from error
        if not isinstance(result, dict):
            raise TypeError("Provider response must be a JSON object")
        return result

    def download(self, url: str, destination: Path) -> Path:
        _require_https(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".download", dir=destination.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with urllib.request.urlopen(url) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if temporary.stat().st_size == 0:
                raise RuntimeError(f"Provider returned an empty asset: {url}")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination
