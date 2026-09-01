from __future__ import annotations

from pathlib import Path
from uuid import uuid4
from urllib import error, parse, request

from .async_image import AsyncImageProvider
from .openai_compatible import ProviderRequestError


class NanobackAsyncImageProvider(AsyncImageProvider):
    """Nanoback /api/v1 异步图片协议适配器。"""

    def __init__(self, *, label: str, base_url: str) -> None:
        normalized_base_url = base_url.rstrip("/")
        if not normalized_base_url.endswith("/api/v1"):
            normalized_base_url = f"{normalized_base_url}/api/v1"
        super().__init__(label=label, base_url=normalized_base_url)

    def list_models(self, *, api_key: str) -> list[dict]:
        payload = self._request_json(
            method="GET",
            path="/models",
            api_key=api_key,
        )
        models = payload.get("models") or payload.get("data") or []
        if not isinstance(models, list):
            return []
        return [row for row in models if isinstance(row, dict)]

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
        if image_urls:
            raise ProviderRequestError(
                f"{self.label} 的 /api/v1/generations 暂不支持参考图上传"
            )
        normalized_resolution = {
            "auto": "1K",
            "512": "1K",
            "0.5k": "1K",
            "1k": "1K",
            "2k": "2K",
            "4k": "4K",
        }.get(str(resolution or "1K").strip().lower(), str(resolution or "1K").strip())
        client_request_id = request_id or f"workbench-{uuid4()}"
        response = self._request_json(
            method="POST",
            path="/generations",
            api_key=api_key,
            payload={
                "request_id": client_request_id,
                "prompt": prompt,
                "model": model,
                "resolution": normalized_resolution,
                "aspectRatio": aspect_ratio or "auto",
            },
        )
        remote_request_id = str(response.get("request_id") or client_request_id)
        if remote_request_id != client_request_id:
            raise ProviderRequestError(
                f"{self.label} 返回的 request_id 与提交值不一致"
            )
        return {
            "id": remote_request_id,
            "status": response.get("status", "queued"),
            "progress": response.get("progress", 0),
            "status_url": response.get("status_url"),
            "estimated_cost": response.get("estimated_cost"),
            "raw": response,
        }

    def poll_generation(
        self,
        *,
        api_key: str,
        task_id: str,
    ) -> dict:
        response = self._request_json(
            method="GET",
            path=f"/generations/{parse.quote(task_id)}",
            api_key=api_key,
        )
        urls = self._extract_image_urls(response.get("images"))
        return {
            "status": response.get("status", "unknown"),
            "progress": response.get("progress", 0),
            "phase": response.get("phase"),
            "error": response.get("error"),
            "result": {"data": [{"url": url} for url in urls]},
            "raw": response,
        }

    def download_result(self, *, api_key: str = "", url: str, destination: Path) -> None:
        absolute_url = parse.urljoin(f"{self.base_url}/", url)
        req = request.Request(
            absolute_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "ai-icon-pipeline/0.1",
            },
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=120) as response:
                destination.write_bytes(response.read())
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderRequestError(
                f"{self.label} download failed: {exc.code} {body or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise ProviderRequestError(f"{self.label} download failed: {exc.reason}") from exc

    def upload_image(self, *, api_key: str, image_path: Path) -> dict:
        raise ProviderRequestError(
            f"{self.label} 的 /api/v1/generations 暂不支持参考图上传"
        )

    def _extract_image_urls(self, images: object) -> list[str]:
        urls: list[str] = []

        def add_url(value: object) -> None:
            if not isinstance(value, str) or not value.strip():
                return
            candidate = value.strip()
            lower = candidate.lower()
            if not (
                candidate.startswith(("http://", "https://", "/"))
                or "/api/v1/images/" in lower
                or lower.endswith((".png", ".jpg", ".jpeg", ".webp"))
            ):
                return
            absolute_url = parse.urljoin(f"{self.base_url}/", candidate)
            if absolute_url not in urls:
                urls.append(absolute_url)

        def walk(value: object) -> None:
            if isinstance(value, str):
                add_url(value)
                return
            if isinstance(value, list):
                for child in value:
                    walk(child)
                return
            if not isinstance(value, dict):
                return
            preferred_keys = (
                "api_url",
                "download_url",
                "image_url",
                "imageUrl",
                "url",
                "path",
                "src",
            )
            before = len(urls)
            for key in preferred_keys:
                add_url(value.get(key))
            if len(urls) == before:
                for child in value.values():
                    walk(child)

        walk(images)
        return urls
