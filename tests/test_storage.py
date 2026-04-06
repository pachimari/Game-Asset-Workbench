from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from ai_icon_pipeline import storage


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


if __name__ == "__main__":
    unittest.main()
