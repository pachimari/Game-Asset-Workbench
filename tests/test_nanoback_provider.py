from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_icon_pipeline import pipeline, settings, storage
from ai_icon_pipeline.providers.nanoback import NanobackAsyncImageProvider
from ai_icon_pipeline.providers.openai_compatible import ProviderRequestError
from ai_icon_pipeline.providers.registry import get_async_image_provider


class _FakeDownloadResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return b"png-bytes"


class NanobackProviderTests(unittest.TestCase):
    def test_registry_selects_nanoback_protocol_variant(self) -> None:
        provider = get_async_image_provider(
            "custom_nanoback",
            {
                "provider_type": "async_image",
                "protocol_variant": "nanoback_v1",
                "label": "Nanoback",
                "base_url": "https://nanoback.example.com",
            },
        )

        self.assertIsInstance(provider, NanobackAsyncImageProvider)
        self.assertEqual(provider.base_url, "https://nanoback.example.com/api/v1")

    def test_models_submit_and_poll_are_normalized(self) -> None:
        provider = NanobackAsyncImageProvider(
            label="Nanoback",
            base_url="https://nanoback.example.com/api/v1",
        )
        with patch.object(
            provider,
            "_request_json",
            side_effect=[
                {
                    "defaults": {},
                    "models": [
                        {
                            "id": "gpt-image-2",
                            "resolutions": ["1K"],
                            "aspectRatios": ["auto", "1:1"],
                        }
                    ],
                },
                {
                    "request_id": "workbench-test",
                    "status": "queued",
                    "status_url": "/api/v1/generations/workbench-test",
                    "estimated_cost": 1,
                },
                {
                    "request_id": "workbench-test",
                    "status": "succeeded",
                    "images": [
                        {
                            "api_url": "/api/v1/images/result.png",
                            "url": "",
                        }
                    ],
                },
            ],
        ) as request_mock:
            models = provider.list_models(api_key="secret")
            submitted = provider.submit_generation(
                api_key="secret",
                model="gpt-image-2",
                prompt="prompt",
                aspect_ratio="auto",
                resolution="1k",
                request_id="workbench-test",
            )
            polled = provider.poll_generation(
                api_key="secret",
                task_id="workbench-test",
            )

        self.assertEqual([row["id"] for row in models], ["gpt-image-2"])
        self.assertEqual(submitted["id"], "workbench-test")
        self.assertEqual(submitted["status"], "queued")
        self.assertEqual(polled["status"], "succeeded")
        self.assertEqual(
            polled["result"]["data"],
            [{"url": "https://nanoback.example.com/api/v1/images/result.png"}],
        )
        submit_call = request_mock.call_args_list[1].kwargs
        self.assertEqual(submit_call["path"], "/generations")
        self.assertEqual(
            submit_call["payload"],
            {
                "request_id": "workbench-test",
                "prompt": "prompt",
                "model": "gpt-image-2",
                "resolution": "1K",
                "aspectRatio": "auto",
            },
        )
        self.assertEqual(
            request_mock.call_args_list[2].kwargs["path"],
            "/generations/workbench-test",
        )

    def test_download_uses_bearer_and_reference_upload_is_rejected(self) -> None:
        provider = NanobackAsyncImageProvider(
            label="Nanoback",
            base_url="https://nanoback.example.com/api/v1",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "result.png"
            with patch(
                "ai_icon_pipeline.providers.nanoback.request.urlopen",
                return_value=_FakeDownloadResponse(),
            ) as urlopen_mock:
                provider.download_result(
                    api_key="secret",
                    url="/api/v1/images/result.png",
                    destination=destination,
                )

            req = urlopen_mock.call_args.args[0]
            self.assertEqual(req.headers["Authorization"], "Bearer secret")
            self.assertEqual(destination.read_bytes(), b"png-bytes")
            with self.assertRaises(ProviderRequestError):
                provider.upload_image(api_key="secret", image_path=destination)

    def test_protocol_variant_persists_and_async_statuses_cover_nanoback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "app_settings.json"
            with patch.object(settings, "SETTINGS_DIR", Path(tmpdir)):
                with patch.object(settings, "APP_SETTINGS_PATH", settings_path):
                    settings.create_custom_provider(
                        label="Nanoback",
                        provider_type="async_image",
                        protocol_variant="nanoback_v1",
                        base_url="https://nanoback.example.com/api/v1",
                    )
                    provider = settings.load_global_settings()["custom_providers"][0]

        self.assertEqual(provider["protocol_variant"], "nanoback_v1")
        self.assertIn("unknown", pipeline.PENDING_ASYNC_STATUSES)
        self.assertIn("unknown", storage.PENDING_ASYNC_STATUSES)
        self.assertIn("succeeded", pipeline.SUCCESS_ASYNC_STATUSES)

    def test_async_candidate_suffix_follows_result_url(self) -> None:
        self.assertEqual(
            pipeline._image_suffix_for_url(
                "https://nanoback.example.com/api/v1/images/result.png?token=ignored"
            ),
            ".png",
        )
        self.assertEqual(
            pipeline._image_suffix_for_url("https://example.com/result.webp"),
            ".webp",
        )
        self.assertEqual(
            pipeline._image_suffix_for_url("https://example.com/result"),
            ".jpg",
        )


if __name__ == "__main__":
    unittest.main()
