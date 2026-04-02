from __future__ import annotations

from base64 import b64decode
import json
import socket
from urllib import error, parse, request

from .openai_compatible import ProviderRequestError

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover - optional dependency at runtime
    genai = None
    types = None


class GeminiNativeProvider:
    REQUEST_TIMEOUT_SECONDS = 300

    def __init__(
        self,
        *,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        label: str = "Gemini Native",
    ) -> None:
        normalized = base_url.rstrip("/")
        if not normalized.endswith("/v1beta"):
            normalized = f"{normalized}/v1beta"
        self.base_url = normalized
        self.label = label

    def _request_json_with_api_key_query(
        self,
        *,
        method: str,
        path: str,
        api_key: str,
        payload: dict | None = None,
    ) -> dict:
        query = f"?key={parse.quote(api_key)}"
        url = f"{self.base_url}{path}{query}"
        headers = {"Content-Type": "application/json"}
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=headers, method=method)
        with request.urlopen(req, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))

    def _request_json_with_bearer(
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
            "Accept": "application/json",
            "User-Agent": "ai-icon-pipeline/0.1",
        }
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=headers, method=method)
        with request.urlopen(req, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        api_key: str,
        payload: dict | None = None,
    ) -> dict:
        last_error: Exception | None = None
        request_attempts = (
            self._request_json_with_api_key_query,
            self._request_json_with_bearer,
        )
        for request_attempt in request_attempts:
            try:
                return request_attempt(
                    method=method,
                    path=path,
                    api_key=api_key,
                    payload=payload,
                )
            except error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                last_error = ProviderRequestError(
                    f"{self.label} request failed: {exc.code} {body or exc.reason}"
                )
            except error.URLError as exc:
                last_error = ProviderRequestError(f"{self.label} request failed: {exc.reason}")
            except socket.timeout:
                last_error = ProviderRequestError(
                    f"{self.label} request timed out after {self.REQUEST_TIMEOUT_SECONDS}s"
                )
        raise last_error or ProviderRequestError(f"{self.label} request failed")

    def list_models(self, *, api_key: str) -> list[dict]:
        payload = self._request_json(method="GET", path="/models", api_key=api_key)
        rows = []
        for model in payload.get("models", []):
            model_name = model.get("name")
            if not model_name:
                continue
            rows.append(
                {
                    "id": model_name,
                    "display_name": model.get("displayName") or model_name,
                    "supported_generation_methods": model.get("supportedGenerationMethods", []),
                }
            )
        return rows

    def generate_images(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        count: int,
        aspect_ratio: str | None = None,
        image_resolution: str | None = None,
    ) -> list[bytes]:
        normalized_model = model.removeprefix("models/")
        if normalized_model.startswith("imagen-"):
            return self._generate_imagen_images(
                api_key=api_key,
                model=normalized_model,
                prompt=prompt,
                count=count,
                aspect_ratio=aspect_ratio,
                image_resolution=image_resolution,
            )
        return self._generate_gemini_images(
            api_key=api_key,
            model=normalized_model,
            prompt=prompt,
            count=count,
            aspect_ratio=aspect_ratio,
            image_resolution=image_resolution,
        )

    def _generate_gemini_images(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        count: int,
        aspect_ratio: str | None,
        image_resolution: str | None,
    ) -> list[bytes]:
        use_sdk_stream = (
            model.startswith("gemini-3")
            and genai is not None
            and types is not None
            and self.base_url.startswith("https://generativelanguage.googleapis.com")
        )
        if use_sdk_stream:
            return self._generate_gemini_images_via_sdk(
                api_key=api_key,
                model=model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                image_resolution=image_resolution,
            )

        image_config: dict[str, str] = {}
        if aspect_ratio:
            image_config["aspectRatio"] = aspect_ratio
        # Older Gemini image models tend to reject imageSize; keep it for newer preview models only.
        if image_resolution and image_resolution != "auto" and "2.5-flash-image" not in model:
            image_config["imageSize"] = image_resolution

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "candidateCount": count,
            },
        }
        if image_config:
            payload["generationConfig"]["imageConfig"] = image_config

        response = self._request_json(
            method="POST",
            path=f"/models/{model}:generateContent",
            api_key=api_key,
            payload=payload,
        )

        images: list[bytes] = []
        for candidate in response.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                inline = part.get("inlineData", {})
                data = inline.get("data")
                if data:
                    images.append(b64decode(data))
        if not images:
            raise ProviderRequestError(f"{self.label} returned no image data for {model}")
        return images

    def _generate_gemini_images_via_sdk(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        aspect_ratio: str | None,
        image_resolution: str | None,
    ) -> list[bytes]:
        client = genai.Client(api_key=api_key)
        image_config_kwargs = {}
        if aspect_ratio:
            image_config_kwargs["aspect_ratio"] = aspect_ratio

        config_kwargs = {
            "response_modalities": ["IMAGE", "TEXT"],
        }
        if image_config_kwargs:
            config_kwargs["image_config"] = types.ImageConfig(**image_config_kwargs)

        stream = client.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )

        images: list[bytes] = []
        for chunk in stream:
            parts = getattr(chunk, "parts", None) or []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                data = getattr(inline_data, "data", None) if inline_data else None
                if data:
                    images.append(data)
        if not images:
            raise ProviderRequestError(f"{self.label} SDK stream returned no image data for {model}")
        return images

    def _generate_imagen_images(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        count: int,
        aspect_ratio: str | None,
        image_resolution: str | None,
    ) -> list[bytes]:
        parameters: dict[str, str | int] = {
            "sampleCount": count,
            "personGeneration": "dont_allow",
        }
        if aspect_ratio:
            parameters["aspectRatio"] = aspect_ratio
        if image_resolution and image_resolution != "auto":
            if "fast" in model:
                if image_resolution == "1K":
                    parameters["imageSize"] = image_resolution
            elif image_resolution in {"1K", "2K"}:
                parameters["imageSize"] = image_resolution

        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": parameters,
        }
        response = self._request_json(
            method="POST",
            path=f"/models/{model}:predict",
            api_key=api_key,
            payload=payload,
        )

        images: list[bytes] = []
        for prediction in response.get("predictions", []):
            data = prediction.get("bytesBase64Encoded")
            if data:
                images.append(b64decode(data))
        if not images:
            raise ProviderRequestError(f"{self.label} returned no image data for {model}")
        return images
