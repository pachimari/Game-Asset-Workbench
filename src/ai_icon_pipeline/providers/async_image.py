from __future__ import annotations

import json
import http.client
import mimetypes
from pathlib import Path
from uuid import uuid4
from urllib import error, parse, request

from .openai_compatible import ProviderRequestError


class AsyncImageProvider:
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
                payload = json.loads(body) if body else {}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderRequestError(f"{self.label} request failed: {exc.code} {body or exc.reason}") from exc
        except error.URLError as exc:
            raise ProviderRequestError(f"{self.label} request failed: {exc.reason}") from exc
        except (TimeoutError, ConnectionError, http.client.HTTPException) as exc:
            raise ProviderRequestError(f"{self.label} request failed: {exc}") from exc
        if int(payload.get("code", 200) or 200) >= 400:
            message = payload.get("error", {}).get("message") or payload
            raise ProviderRequestError(f"{self.label} request failed: {message}")
        return payload

    def submit_generation(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        aspect_ratio: str,
        resolution: str,
        image_urls: list[str] | None = None,
        request_id: str | None = None,
    ) -> dict:
        normalized_resolution = {
            "auto": "1K",
            "512": "0.5K",
            "1k": "1K",
            "2k": "2K",
            "4k": "4K",
        }.get(str(resolution or "1K").strip().lower(), resolution or "1K")
        resolution_field = normalized_resolution.lower()
        if resolution_field == "0.5k":
            resolution_field = "1k"
        payload = {
            "model": model,
            "prompt": prompt,
            "size": aspect_ratio or "1:1",
            "resolution": resolution_field,
            "n": 1,
            "metadata": {
                "resolution": normalized_resolution,
            },
        }
        if image_urls:
            payload["image_urls"] = list(image_urls)
        response = self._request_json(
            method="POST",
            path="/images/generations",
            api_key=api_key,
            payload=payload,
        )
        data = response.get("data")
        first_data = data[0] if isinstance(data, list) and data else {}
        task_id = response.get("id") or first_data.get("task_id") or first_data.get("id")
        if not task_id:
            raise ProviderRequestError(f"{self.label} 未返回任务 id")
        if response.get("id"):
            return response
        return {
            "id": task_id,
            "status": first_data.get("status", response.get("status", "queued")),
            "progress": first_data.get("progress", response.get("progress", 0)),
            "raw": response,
        }

    def upload_image(self, *, api_key: str, image_path: Path) -> dict:
        if not self.base_url:
            raise ProviderRequestError(f"{self.label} 未配置 base_url")
        if not image_path.is_file():
            raise ProviderRequestError(f"Reference image not found: {image_path}")
        content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        boundary = f"ai-icon-pipeline-{uuid4().hex}"
        prefix = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
        body = prefix + image_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
        req = request.Request(
            f"{self.base_url}/uploads/images",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
                "User-Agent": "ai-icon-pipeline/0.1",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as response:
                response_body = response.read().decode("utf-8")
                payload = json.loads(response_body) if response_body else {}
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderRequestError(
                f"{self.label} upload failed: {exc.code} {response_body or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise ProviderRequestError(f"{self.label} upload failed: {exc.reason}") from exc
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        image_url = data.get("url") if isinstance(data, dict) else None
        if not image_url:
            raise ProviderRequestError(f"{self.label} upload did not return an image URL")
        return {"url": str(image_url), "raw": payload}

    def list_models(self, *, api_key: str) -> list[dict]:
        payload = self._request_json(
            method="GET",
            path="/models",
            api_key=api_key,
        )
        return payload.get("data", [])

    def poll_generation(
        self,
        *,
        api_key: str,
        task_id: str,
    ) -> dict:
        try:
            response = self._request_json(
                method="GET",
                path=f"/images/generations/{parse.quote(task_id)}",
                api_key=api_key,
            )
        except ProviderRequestError as exc:
            if "404" not in str(exc) and "405" not in str(exc):
                raise
            response = self._request_json(
                method="GET",
                path=f"/tasks/{parse.quote(task_id)}",
                api_key=api_key,
            )
        if "status" in response or "result" in response:
            return response

        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        images = ((data.get("result") or {}).get("images") or [])
        urls: list[str] = []
        for image in images:
            raw_url = image.get("url") if isinstance(image, dict) else None
            if isinstance(raw_url, list):
                urls.extend(str(url) for url in raw_url if url)
            elif raw_url:
                urls.append(str(raw_url))
        return {
            "status": data.get("status", response.get("status", "queued")),
            "progress": data.get("progress", response.get("progress", 0)),
            "error": data.get("error") or response.get("error"),
            "result": {"data": [{"url": url} for url in urls]},
            "raw": response,
        }

    def download_result(self, *, api_key: str = "", url: str, destination: Path) -> None:
        req = request.Request(url, headers={"User-Agent": "ai-icon-pipeline/0.1"}, method="GET")
        try:
            with request.urlopen(req, timeout=120) as response:
                destination.write_bytes(response.read())
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderRequestError(f"{self.label} download failed: {exc.code} {body or exc.reason}") from exc
        except error.URLError as exc:
            raise ProviderRequestError(f"{self.label} download failed: {exc.reason}") from exc
