from __future__ import annotations

from base64 import b64decode
import json
from urllib import error, request


class ProviderRequestError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(self, *, base_url: str, label: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.label = label

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        api_key: str,
        payload: dict | None = None,
    ) -> dict:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderRequestError(f"{self.label} request failed: {exc.code} {body or exc.reason}") from exc
        except error.URLError as exc:
            raise ProviderRequestError(f"{self.label} request failed: {exc.reason}") from exc

    def list_models(self, *, api_key: str) -> list[dict]:
        payload = self._request_json(method="GET", path="/models", api_key=api_key)
        return payload.get("data", [])

    def generate_json(
        self,
        *,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.4,
        }
        response = self._request_json(method="POST", path="/chat/completions", api_key=api_key, payload=payload)
        content = response["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ProviderRequestError(f"{self.label} returned non-text JSON payload")
        return json.loads(content)

    def generate_images(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        count: int,
    ) -> list[bytes]:
        payload = {
            "model": model,
            "prompt": prompt,
            "response_format": "b64_json",
            "n": count,
        }
        response = self._request_json(method="POST", path="/images/generations", api_key=api_key, payload=payload)
        rows = response.get("data", [])
        images: list[bytes] = []
        for row in rows:
            b64_json = row.get("b64_json")
            if b64_json:
                images.append(b64decode(b64_json))
        return images
