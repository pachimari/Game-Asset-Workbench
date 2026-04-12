from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from ai_icon_pipeline import storage
from ai_icon_pipeline import api
from ai_icon_pipeline import cli
from ai_icon_pipeline import pipeline
from ai_icon_pipeline import settings
from ai_icon_pipeline.providers.gemini_native import GeminiNativeProvider


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
        self.assertEqual([row["item_id"] for row in result["blocked_items"]], ["item_001"])
        self.assertEqual([row["item_id"] for row in result["terminal_items"]], ["item_002"])
        self.assertIn("async image generation", result["message"])

    def test_provider_set_default_updates_global_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "app_settings.json"
            with patch.object(settings, "SETTINGS_DIR", Path(tmpdir)):
                with patch.object(settings, "APP_SETTINGS_PATH", settings_path):
                    updated = settings.set_global_default(
                        "image_generation",
                        provider="gemini",
                        model="models/gemini-3.1-flash-image-preview",
                    )
                    self.assertEqual(updated["defaults"]["image_generation"]["provider"], "gemini")
                    self.assertEqual(
                        updated["defaults"]["image_generation"]["model"],
                        "models/gemini-3.1-flash-image-preview",
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


if __name__ == "__main__":
    unittest.main()
