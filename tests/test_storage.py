from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from ai_icon_pipeline import storage
from ai_icon_pipeline import api
from ai_icon_pipeline import settings


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


if __name__ == "__main__":
    unittest.main()
