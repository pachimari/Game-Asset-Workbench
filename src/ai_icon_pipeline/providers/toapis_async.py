from __future__ import annotations

import json
from pathlib import Path
from urllib import error, parse, request

from .openai_compatible import ProviderRequestError


class ToApisAsyncImageProvider:
    def __init__(self, *, label: str, base_url: str) -> None:
        self.label = label
        self.base_url = base_url.rstrip("/")

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        api_key: str,
        payload: dict | None = None,
    ) -> dict:
        if not self.base_url:
            raise ProviderRequestError(f"{self.label} 未配置 base_url")
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ai-icon-pipeline/0.1",
        }
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=120) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderRequestError(f"{self.label} request failed: {exc.code} {body or exc.reason}") from exc
        except error.URLError as exc:
            raise ProviderRequestError(f"{self.label} request failed: {exc.reason}") from exc

    def submit_generation(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        aspect_ratio: str,
        resolution: str,
    ) -> dict:
        normalized_resolution = {
            "auto": "1K",
            "512": "0.5K",
            "1k": "1K",
            "2k": "2K",
            "4k": "4K",
        }.get(str(resolution or "1K").strip().lower(), resolution or "1K")
        payload = {
            "model": model,
            "prompt": prompt,
            "size": aspect_ratio or "1:1",
            "n": 1,
            "metadata": {
                "resolution": normalized_resolution,
            },
        }
        response = self._request_json(
            method="POST",
            path="/images/generations",
            api_key=api_key,
            payload=payload,
        )
        task_id = response.get("id")
        if not task_id:
            raise ProviderRequestError(f"{self.label} 未返回任务 id")
        return response

    def poll_generation(
        self,
        *,
        api_key: str,
        task_id: str,
    ) -> dict:
        return self._request_json(
            method="GET",
            path=f"/images/generations/{parse.quote(task_id)}",
            api_key=api_key,
        )

    def download_result(self, *, url: str, destination: Path) -> None:
        req = request.Request(url, headers={"User-Agent": "ai-icon-pipeline/0.1"}, method="GET")
        try:
            with request.urlopen(req, timeout=120) as response:
                destination.write_bytes(response.read())
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderRequestError(f"{self.label} download failed: {exc.code} {body or exc.reason}") from exc
        except error.URLError as exc:
            raise ProviderRequestError(f"{self.label} download failed: {exc.reason}") from exc
