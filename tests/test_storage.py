from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
import zipfile

from ai_icon_pipeline import storage
from ai_icon_pipeline import api
from ai_icon_pipeline import cli
from ai_icon_pipeline import pipeline
from ai_icon_pipeline import settings
from ai_icon_pipeline import provider_runtime
from ai_icon_pipeline.providers.async_image import AsyncImageProvider
from ai_icon_pipeline.providers.gemini_native import GeminiNativeProvider
from ai_icon_pipeline.providers.registry import ProviderRequestError


class StorageSafetyTests(unittest.TestCase):
    def test_delete_task_rejects_invalid_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                with self.assertRaises(ValueError):
                    storage.delete_task("")

    def test_load_item_recovers_stale_generating_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                with patch.object(storage, "GENERATING_STALE_SECONDS", 1):
                    task = storage.create_task(task_name="Test Task")
                    item = storage.create_item(
                        task["task_id"],
                        title="Test Item",
                        description="desc",
                        category="combat",
                    )

                    stale_item = storage.load_item(task["task_id"], item["item_id"])
                    stale_item["status"] = "prompt_generating"
                    stale_item["updated_at"] = (
                        datetime.now(timezone.utc) - timedelta(minutes=30)
                    ).isoformat()
                    storage.write_json(
                        storage.item_dir(task["task_id"], item["item_id"]) / "item.json",
                        stale_item,
                    )

                    recovered = storage.load_item(task["task_id"], item["item_id"])
                    self.assertEqual(recovered["status"], "failed")
                    metrics = storage.load_metrics(task["task_id"], item["item_id"])
                    self.assertEqual(metrics["status"], "failed")
                    self.assertIsNotNone(metrics["end_time"])

    def test_file_access_is_limited_to_images_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(api, "TASKS_DIR", Path(tmpdir)):
                image_path = Path(tmpdir) / "task_001" / "items" / "item_001" / "images" / "ok.png"
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(b"png")

                export_path = Path(tmpdir) / "task_001" / "exports" / "ok.zip"
                export_path.parent.mkdir(parents=True, exist_ok=True)
                export_path.write_bytes(b"zip")

                blocked_path = Path(tmpdir) / "task_001" / "items" / "item_001" / "item.json"
                blocked_path.parent.mkdir(parents=True, exist_ok=True)
                blocked_path.write_text("{}", encoding="utf-8")

                self.assertEqual(
                    api._safe_file_response_path("task_001/items/item_001/images/ok.png"),
                    image_path.resolve(),
                )
                self.assertEqual(
                    api._safe_file_response_path("task_001/exports/ok.zip"),
                    export_path.resolve(),
                )
                with self.assertRaises(Exception):
                    api._safe_file_response_path("task_001/items/item_001/item.json")

    def test_download_headers_encode_utf8_filename(self) -> None:
        headers = api._download_headers("任务_星标图.zip", "task_starred-images.zip")
        self.assertIn('filename="task_starred-images.zip"', headers["Content-Disposition"])
        self.assertIn("filename*=UTF-8''%E4%BB%BB%E5%8A%A1_%E6%98%9F%E6%A0%87%E5%9B%BE.zip", headers["Content-Disposition"])

    def test_create_custom_provider_accepts_none_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "app_settings.json"
            with patch.object(settings, "SETTINGS_DIR", Path(tmpdir)):
                with patch.object(settings, "APP_SETTINGS_PATH", settings_path):
                    created = settings.create_custom_provider(
                        label="No Key Provider",
                        provider_type="mock",
                        base_url="",
                        api_key=None,
                    )
                    custom = created["custom_providers"][0]
                    self.assertEqual(custom["label"], "No Key Provider")
                    self.assertEqual(custom["api_key"], "")

    def test_update_provider_settings_can_clear_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "app_settings.json"
            with patch.object(settings, "SETTINGS_DIR", Path(tmpdir)):
                with patch.object(settings, "APP_SETTINGS_PATH", settings_path):
                    settings.save_global_settings(settings.default_global_settings())
                    settings.create_custom_provider(
                        label="ToAPIs Smoke",
                        provider_type="async_image",
                        base_url="https://toapis.com/v1",
                        api_key="secret",
                    )
                    provider_id = settings.load_global_settings()["custom_providers"][0]["id"]
                    settings.update_provider_settings(provider_id, last_error="boom")
                    settings.update_provider_settings(provider_id, last_error=None)
                    provider = settings.load_global_settings()["custom_providers"][0]
                    self.assertIsNone(provider["last_error"])

    def test_custom_provider_persists_image_max_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "app_settings.json"
            with patch.object(settings, "SETTINGS_DIR", Path(tmpdir)):
                with patch.object(settings, "APP_SETTINGS_PATH", settings_path):
                    settings.create_custom_provider(
                        label="Async Provider",
                        provider_type="async_image",
                        base_url="https://example.com/v1",
                        api_key="secret",
                        image_max_concurrency=3,
                    )
                    provider = settings.load_global_settings()["custom_providers"][0]
                    self.assertEqual(provider["image_max_concurrency"], 3)

    def test_async_image_provider_normalizes_apimart_submit_and_poll_responses(self) -> None:
        provider = AsyncImageProvider(label="APIMart", base_url="https://api.apimart.ai/v1")

        with patch.object(
            provider,
            "_request_json",
            side_effect=[
                {
                    "code": 200,
                    "data": [
                        {
                            "status": "submitted",
                            "task_id": "task_123",
                        }
                    ],
                },
                ProviderRequestError("APIMart request failed: 404 not found"),
                {
                    "code": 200,
                    "data": {
                        "id": "task_123",
                        "status": "completed",
                        "progress": 100,
                        "result": {
                            "images": [
                                {
                                    "url": ["https://upload.apimart.ai/f/image/result.png"],
                                }
                            ]
                        },
                    },
                },
            ],
        ) as request_mock:
            submit = provider.submit_generation(
                api_key="secret",
                model="gpt-image-2",
                prompt="prompt",
                aspect_ratio="16:9",
                resolution="2K",
            )
            poll = provider.poll_generation(api_key="secret", task_id="task_123")

        self.assertEqual(submit["id"], "task_123")
        self.assertEqual(submit["status"], "submitted")
        self.assertEqual(poll["status"], "completed")
        self.assertEqual(
            poll["result"]["data"],
            [{"url": "https://upload.apimart.ai/f/image/result.png"}],
        )
        submit_payload = request_mock.call_args_list[0].kwargs["payload"]
        self.assertEqual(submit_payload["resolution"], "2k")
        self.assertEqual(submit_payload["size"], "16:9")
        self.assertEqual(request_mock.call_args_list[1].kwargs["path"], "/images/generations/task_123")
        self.assertEqual(request_mock.call_args_list[2].kwargs["path"], "/tasks/task_123")

    def test_local_request_rejects_external_forwarded_client(self) -> None:
        class DummyClient:
            host = "127.0.0.1"

        class DummyRequest:
            client = DummyClient()
            headers = {"x-forwarded-for": "203.0.113.10"}

        self.assertFalse(api._is_local_request(DummyRequest()))

    def test_compute_batch_metrics_summarizes_iterations_and_stars(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                task = storage.create_task(task_name="Metrics Task")
                item = storage.create_item(
                    task["task_id"],
                    title="Test Item",
                    description="desc",
                    category="combat",
                )
                metrics = storage.load_metrics(task["task_id"], item["item_id"])
                metrics["iterations"]["brief_generation"] = 2
                metrics["iterations"]["image_prompt"] = 1
                metrics["iterations"]["image_generation"] = 3
                storage.save_metrics(task["task_id"], item["item_id"], metrics)

                current = storage.load_item(task["task_id"], item["item_id"])
                current["status"] = "image_generated"
                current["starred_image_versions"] = ["v001"]
                current["current_versions"]["image_generation"] = "v001"
                storage.save_item(task["task_id"], current)

                image_dir = storage.item_dir(task["task_id"], item["item_id"]) / "images"
                image_dir.mkdir(parents=True, exist_ok=True)
                (image_dir / "v001_candidate_01.png").write_bytes(b"png")
                storage.write_artifact(
                    task["task_id"],
                    item["item_id"],
                    "image_generation",
                    {
                        "step": "image_generation",
                        "provider": "mock",
                        "model": "mock-image-v1",
                        "created_at": current["created_at"],
                        "output": {
                            "candidates": [
                                {"candidate_id": "candidate_01", "image_path": "v001_candidate_01.png"}
                            ]
                        },
                    },
                    version="v001",
                )

                summary = storage.compute_batch_metrics(task["task_id"])
                self.assertEqual(summary["redo_counts"]["brief_generation"], 1)
                self.assertEqual(summary["redo_counts"]["image_generation"], 2)
                self.assertEqual(summary["starred_images"], 1)
                self.assertEqual(summary["adopted_from_starred"], 1)
                self.assertEqual(summary["stuck_items"], [])
                self.assertEqual(summary["failed_items"], [])
                self.assertEqual(summary["last_error_by_item"], {})
                self.assertEqual(summary["active_provider_requests"], [])

    def test_cli_star_rejects_nonexistent_image_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                task = storage.create_task(task_name="CLI Star Test")
                item = storage.create_item(
                    task["task_id"],
                    title="Test Item",
                    description="desc",
                    category="combat",
                )

                with self.assertRaises(ValueError):
                    cli._set_starred_image_version(task["task_id"], item["item_id"], "ghost_version", starred=True)

    def test_create_item_assigns_unique_ids_under_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                task = storage.create_task(task_name="Concurrent Item Test")
                created_ids: list[str] = []
                errors: list[Exception] = []
                result_lock = threading.Lock()

                def worker(index: int) -> None:
                    try:
                        item = storage.create_item(
                            task["task_id"],
                            title=f"Item {index}",
                            description="desc",
                            category="combat",
                        )
                        with result_lock:
                            created_ids.append(item["item_id"])
                    except Exception as exc:  # pragma: no cover - test helper
                        with result_lock:
                            errors.append(exc)

                threads = [threading.Thread(target=worker, args=(index,)) for index in range(3)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

                self.assertEqual(errors, [])
                self.assertEqual(len(created_ids), 3)
                self.assertEqual(sorted(created_ids), ["item_001", "item_002", "item_003"])
                task_snapshot = storage.load_task(task["task_id"])
                self.assertEqual(task_snapshot["items"], ["item_001", "item_002", "item_003"])

    def test_gemini_native_only_falls_back_on_auth_failures(self) -> None:
        provider = GeminiNativeProvider()
        calls: list[str] = []

        def fail_query(*, method: str, path: str, api_key: str, payload: dict | None = None) -> dict:
            calls.append("query")
            raise OSError("network down")

        def fail_bearer(*, method: str, path: str, api_key: str, payload: dict | None = None) -> dict:
            calls.append("bearer")
            return {}

        with patch.object(provider, "_request_json_with_api_key_query", side_effect=fail_query):
            with patch.object(provider, "_request_json_with_bearer", side_effect=fail_bearer):
                with self.assertRaises(Exception):
                    provider._request_json(method="GET", path="/models", api_key="secret")

        self.assertEqual(calls, ["query"])

    def test_run_pipeline_returns_until_blocked_summary(self) -> None:
        with patch.object(pipeline, "load_task", return_value={"task_id": "task_001", "items": ["item_001", "item_002"]}):
            with patch.object(
                pipeline,
                "run_item_pipeline",
                side_effect=[
                    {"task_id": "task_001", "item_id": "item_001", "status": "image_generating"},
                    {"task_id": "task_001", "item_id": "item_002", "status": "completed"},
                ],
            ):
                with patch.object(
                    pipeline,
                    "refresh_task_summary",
                    return_value={"task_id": "task_001", "status": "in_progress"},
                ):
                    result = pipeline.run_pipeline("task_001")

        self.assertEqual(result["mode"], "until_blocked")
        self.assertEqual(result["image_concurrency"], 1)
        self.assertEqual([row["item_id"] for row in result["blocked_items"]], ["item_001"])

    def test_run_pipeline_reports_requested_image_concurrency(self) -> None:
        with patch.object(pipeline, "load_task", return_value={"task_id": "task_001", "items": ["item_001"]}):
            with patch.object(
                pipeline,
                "run_item_pipeline",
                return_value={"task_id": "task_001", "item_id": "item_001", "status": "completed"},
            ):
                with patch.object(
                    pipeline,
                    "refresh_task_summary",
                    return_value={"task_id": "task_001", "status": "completed"},
                ):
                    result = pipeline.run_pipeline("task_001", image_concurrency=4)

        self.assertEqual(result["image_concurrency"], 4)
        self.assertEqual([row["item_id"] for row in result["terminal_items"]], ["item_001"])
        self.assertIn("async image generation", result["message"])

    def test_run_pipeline_applies_delay_between_batch_items(self) -> None:
        with patch.object(pipeline, "load_task", return_value={"task_id": "task_001", "items": ["item_001", "item_002"]}):
            with patch.object(
                pipeline,
                "run_item_pipeline",
                side_effect=[
                    {"task_id": "task_001", "item_id": "item_001", "status": "completed"},
                    {"task_id": "task_001", "item_id": "item_002", "status": "completed"},
                ],
            ):
                with patch.object(
                    pipeline,
                    "refresh_task_summary",
                    return_value={"task_id": "task_001", "status": "completed"},
                ):
                    with patch.object(pipeline.time, "sleep") as sleep_mock:
                        result = pipeline.run_pipeline("task_001", delay_seconds=2.5)

        sleep_mock.assert_called_once_with(2.5)
        self.assertEqual(result["delay_seconds"], 2.5)

    def test_build_image_generation_payload_retries_transient_async_submit_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                task = storage.create_task(task_name="Retry Image Submit")
                item = storage.create_item(
                    task["task_id"],
                    title="Retry Item",
                    description="desc",
                    category="combat",
                )
                current = storage.load_item(task["task_id"], item["item_id"])
                current["status"] = "prompt_approved"
                current["current_versions"]["image_prompt"] = "v001"
                storage.save_item(task["task_id"], current)
                storage.write_artifact(
                    task["task_id"],
                    item["item_id"],
                    "image_prompt",
                    {
                        "step": "image_prompt",
                        "provider": "manual",
                        "created_at": current["created_at"],
                        "output": {
                            "prompt": "一个金色护盾",
                            "negative_prompt": "不要文字",
                            "constraints": {},
                            "batch_context": {},
                        },
                    },
                    version="v001",
                )

                fake_provider = Mock()
                fake_provider.submit_generation.side_effect = [
                    ProviderRequestError("provider request failed: 429 当前分组上游负载已饱和"),
                    {"id": "remote_123", "status": "queued", "progress": 0},
                ]

                with patch.object(pipeline, "get_async_image_provider", return_value=fake_provider):
                    with patch.object(pipeline.time, "sleep") as sleep_mock:
                        payload, version = pipeline._build_image_generation_payload(
                            task["task_id"],
                            item["item_id"],
                            item=current,
                            provider_id="custom_async",
                            provider_settings={"provider_type": "async_image"},
                            api_key="secret",
                            model_id="image-model",
                            selected_runtime={"provider": "custom_async", "model": "image-model", "source": "task"},
                            runtime_config={
                                "candidate_count": 1,
                                "image_size": "1:1 / 1K",
                                "image_aspect_ratio": "1:1",
                                "image_resolution": "1K",
                            },
                            source="cli",
                        )

        self.assertTrue(version.startswith("v"))
        self.assertEqual(fake_provider.submit_generation.call_count, 2)
        sleep_mock.assert_called_once_with(5.0)
        self.assertEqual(payload["async_job"]["task_id"], "remote_123")
        self.assertEqual(payload["meta"]["submit_attempts"], 2)

    def test_cli_run_pipeline_forwards_delay(self) -> None:
        with patch.object(cli, "run_pipeline", return_value={"ok": True}) as run_pipeline_mock:
            exit_code = cli.main(["run-pipeline", "task_001", "--delay", "3", "--json"])

        self.assertEqual(exit_code, 0)
        run_pipeline_mock.assert_called_once_with(
            "task_001",
            item_id=None,
            auto_approve=True,
            stop_at_status=None,
            parallel=1,
            delay_seconds=3.0,
            image_concurrency=1,
        )

    def test_cli_run_pipeline_forwards_stop_at_and_parallel(self) -> None:
        with patch.object(cli, "run_pipeline", return_value={"ok": True}) as run_pipeline_mock:
            exit_code = cli.main(
                [
                    "run-pipeline",
                    "task_001",
                    "--stop-at",
                    "prompt_approved",
                    "--parallel",
                    "4",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        run_pipeline_mock.assert_called_once_with(
            "task_001",
            item_id=None,
            auto_approve=True,
            stop_at_status="prompt_approved",
            parallel=4,
            delay_seconds=0.0,
            image_concurrency=1,
        )

    def test_run_pipeline_uses_parallel_mode_for_text_stop_at(self) -> None:
        with patch.object(pipeline, "load_task", return_value={"task_id": "task_001", "items": ["item_001", "item_002"]}):
            with patch.object(
                pipeline,
                "run_item_pipeline",
                side_effect=[
                    {"task_id": "task_001", "item_id": "item_001", "status": "prompt_approved"},
                    {"task_id": "task_001", "item_id": "item_002", "status": "prompt_approved"},
                ],
            ):
                with patch.object(
                    pipeline,
                    "refresh_task_summary",
                    return_value={"task_id": "task_001", "status": "prompt_approved"},
                ):
                    result = pipeline.run_pipeline(
                        "task_001",
                        stop_at_status="prompt_approved",
                        parallel=2,
                    )

        self.assertTrue(result["parallel_mode"])
        self.assertEqual(result["parallel"], 2)
        self.assertEqual(result["stop_at_status"], "prompt_approved")

    def test_cli_bulk_approve_uses_all_items(self) -> None:
        with patch.object(cli, "_bulk_step_action", return_value={"ok": True}) as bulk_mock:
            exit_code = cli.main(["approve-step", "task_001", "brief_generation", "--all-items", "--json"])

        self.assertEqual(exit_code, 0)
        bulk_mock.assert_called_once_with("task_001", step="brief_generation", action="approve")

    def test_generate_prompt_output_does_not_append_batch_context_to_prompt_text(self) -> None:
        fake_provider = Mock()
        fake_provider.generate_json.return_value = {
            "prompt": "中心构图，金色护盾，半透明能量边缘，符文碎片环绕",
            "negative_prompt": "文字，水印，模糊",
            "constraints": {"composition": "single centered subject"},
        }
        with patch.object(provider_runtime, "get_provider", return_value=fake_provider):
            result = provider_runtime.generate_prompt_output(
                provider_id="custom_text",
                provider_config={"provider_type": "openai_compatible"},
                api_key="secret",
                model="text-model",
                brief_output={
                    "title": "护盾",
                    "description": "desc",
                    "keywords": ["金色护盾", "法阵", "能量边缘"],
                    "icon_subject": "金色护盾",
                    "visual_focus": "半透明能量边缘与符文碎片",
                    "project_background": "三国阵法技能图标，统一 1:1",
                    "style_requirements": "传统网游风格，无文字",
                },
                style_spec={"style_tags": ["fantasy"], "forbidden_elements": [], "composition_rules": []},
                runtime_config={
                    "candidate_count": 1,
                    "image_size": "1:1 / 1K",
                    "image_aspect_ratio": "1:1",
                    "image_resolution": "1K",
                },
            )

        self.assertEqual(
            result["prompt"],
            "中心构图，金色护盾，半透明能量边缘，符文碎片环绕",
        )
        self.assertEqual(result["batch_context"]["project_background"], "三国阵法技能图标，统一 1:1")

    def test_set_current_image_version_auto_stars_selected_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                task = storage.create_task(task_name="Current Version Stars")
                item = storage.create_item(
                    task["task_id"],
                    title="赵云",
                    description="desc",
                    category="combat",
                )
                image_dir = storage.item_dir(task["task_id"], item["item_id"]) / "images"
                image_dir.mkdir(parents=True, exist_ok=True)
                (image_dir / "v001_candidate_01.png").write_bytes(b"png")
                storage.write_artifact(
                    task["task_id"],
                    item["item_id"],
                    "image_generation",
                    {
                        "step": "image_generation",
                        "provider": "mock",
                        "model": "mock-image-v1",
                        "created_at": item["created_at"],
                        "output": {
                            "candidates": [
                                {"candidate_id": "candidate_01", "image_path": "v001_candidate_01.png"}
                            ]
                        },
                    },
                    version="v001",
                )

                pipeline.set_current_version(
                    task["task_id"],
                    item["item_id"],
                    "image_generation",
                    "v001",
                )

                updated_item = storage.load_item(task["task_id"], item["item_id"])
                self.assertEqual(updated_item["current_versions"]["image_generation"], "v001")
                self.assertIn("v001", updated_item["starred_image_versions"])

    def test_export_starred_images_uses_globally_unique_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                task = storage.create_task(task_name="Export Names")
                item = storage.create_item(
                    task["task_id"],
                    title="锐锋阵·暴击",
                    description="desc",
                    category="combat",
                )
                current = storage.load_item(task["task_id"], item["item_id"])
                current["starred_image_versions"] = ["v001"]
                storage.save_item(task["task_id"], current)

                image_dir = storage.item_dir(task["task_id"], item["item_id"]) / "images"
                image_dir.mkdir(parents=True, exist_ok=True)
                (image_dir / "v001_candidate_01.png").write_bytes(b"png")
                storage.write_artifact(
                    task["task_id"],
                    item["item_id"],
                    "image_generation",
                    {
                        "step": "image_generation",
                        "provider": "mock",
                        "model": "mock-image-v1",
                        "created_at": current["created_at"],
                        "output": {
                            "candidates": [
                                {"candidate_id": "candidate_01", "image_path": "v001_candidate_01.png"}
                            ]
                        },
                    },
                    version="v001",
                )

                archive_path = storage.export_starred_images_zip(task["task_id"])
                with zipfile.ZipFile(archive_path) as archive:
                    names = archive.namelist()

                image_entries = [name for name in names if name.endswith(".png")]
                self.assertEqual(len(image_entries), 2)
                self.assertIn("item_001_锐锋阵·暴击/item_001_锐锋阵·暴击_v001_candidate_01.png", names)
                self.assertIn("flat/item_001_锐锋阵·暴击_v001_candidate_01.png", names)
                self.assertIn("manifest.csv", names)

    def test_provider_set_default_updates_global_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "app_settings.json"
            with patch.object(settings, "SETTINGS_DIR", Path(tmpdir)):
                with patch.object(settings, "APP_SETTINGS_PATH", settings_path):
                    settings.create_custom_provider(
                        label="Gemini Native",
                        provider_type="gemini_native",
                        base_url="https://generativelanguage.googleapis.com",
                        models=[
                            {
                                "id": "models/gemini-3.1-flash-image-preview",
                                "label": "Gemini 3.1 Flash Image Preview",
                            }
                        ],
                    )
                    loaded = settings.load_global_settings()
                    provider_id = loaded["custom_providers"][0]["id"]
                    updated = settings.set_global_default(
                        "image_generation",
                        provider=provider_id,
                        model="models/gemini-3.1-flash-image-preview",
                    )
                    self.assertEqual(updated["defaults"]["image_generation"]["provider"], provider_id)
                    self.assertEqual(
                        updated["defaults"]["image_generation"]["model"],
                        "models/gemini-3.1-flash-image-preview",
                    )

    def test_provider_set_default_rejects_unsupported_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "app_settings.json"
            with patch.object(settings, "SETTINGS_DIR", Path(tmpdir)):
                with patch.object(settings, "APP_SETTINGS_PATH", settings_path):
                    with self.assertRaises(ValueError):
                        settings.set_global_default(
                            "image_generation",
                            provider="typo",
                            model="nope",
                        )

    def test_load_task_backfills_missing_items_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                task_root = Path(tmpdir) / "task_001"
                task_root.mkdir(parents=True, exist_ok=True)
                storage.write_json(
                    task_root / "task.json",
                    {
                        "task_id": "task_001",
                        "task_name": "Legacy Task",
                        "created_at": "2026-04-01T00:00:00+00:00",
                        "updated_at": "2026-04-01T00:00:00+00:00",
                    },
                )
                task = storage.load_task("task_001")
                self.assertEqual(task["items"], [])
                self.assertEqual(task["item_count"], 0)

    def test_list_tasks_returns_created_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                first = storage.create_task(task_name="First Task")
                second = storage.create_task(task_name="Second Task")
                tasks = storage.list_tasks()
                task_ids = {task["task_id"] for task in tasks}
                self.assertIn(first["task_id"], task_ids)
                self.assertIn(second["task_id"], task_ids)

    def test_list_tasks_includes_legacy_task_without_items_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                task_root = Path(tmpdir) / "task_001"
                task_root.mkdir(parents=True, exist_ok=True)
                storage.write_json(
                    task_root / "task.json",
                    {
                        "task_id": "task_001",
                        "task_name": "Legacy Task",
                        "created_at": "2026-04-01T00:00:00+00:00",
                        "updated_at": "2026-04-01T00:00:00+00:00",
                    },
                )
                tasks = storage.list_tasks()
                self.assertEqual(len(tasks), 1)
                self.assertEqual(tasks[0]["items"], [])

    def test_compute_batch_metrics_does_not_mark_active_image_generation_as_stuck(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(storage, "TASKS_DIR", Path(tmpdir)):
                task = storage.create_task(task_name="Async Pending Task")
                item = storage.create_item(
                    task["task_id"],
                    title="Pending Item",
                    description="desc",
                    category="combat",
                )
                current = storage.load_item(task["task_id"], item["item_id"])
                current["status"] = "image_generating"
                storage.save_item(task["task_id"], current)
                storage.write_artifact(
                    task["task_id"],
                    item["item_id"],
                    "image_generation",
                    {
                        "step": "image_generation",
                        "provider": "mock",
                        "model": "mock-image-v1",
                        "created_at": current["created_at"],
                        "async_job": {
                            "status": "processing",
                            "task_id": "remote_123",
                            "updated_at": current["created_at"],
                        },
                        "output": {"candidates": []},
                    },
                    version="v001",
                )
                summary = storage.compute_batch_metrics(task["task_id"])
                self.assertEqual(summary["stuck_items"], [])
                self.assertEqual(len(summary["active_provider_requests"]), 1)


if __name__ == "__main__":
    unittest.main()
