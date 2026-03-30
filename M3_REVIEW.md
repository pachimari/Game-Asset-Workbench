# M3 Streamlit Workspace PR Review

**PR:** [#1 M3: add Streamlit workspace for batch and item flows](https://github.com/pachimari/ai-icon-pipeline/pull/1)
**Branch:** `codex/m3-streamlit-workspace` → `main`
**Changes:** +1689 / -44 across 8 files
**Reviewer:** opencode (mimo-v2-pro-free)
**Date:** 2026-03-23
**Updated:** 2026-03-23 — 二次审查，2/3 问题已修复
**Final:** 2026-03-23 — 接受风险，PR 合并

---

## Summary

PR 添加了基于 Streamlit 的本地工作台，支持批次管理、条目编辑、批量粘贴导入、设计说明/出图指令预览、候选图浏览等功能。架构清晰，功能完整。

**Scope Check: CLEAN**
- Intent: 添加 Streamlit 工作台用于批次和条目管理
- Delivered: 完整的 UI + 后端支持，无范围漂移

---

## Review Result: 3 issues → 1 remaining

### Pass 1 — CRITICAL

#### 1. XSS 漏洞 — `unsafe_allow_html=True` 未转义用户输入

**状态: ✅ 已修复**

添加了 `_esc()` 辅助函数（`ui.py:204-206`），所有用户输入经 `html.escape()` 转义后再拼接 HTML。受影响位置均已修复。

---

#### 2. 竞态条件 — `update_item` 非原子操作

**状态: ❌ 未修复**

**严重程度:** CRITICAL (数据一致性)

**位置:** `storage.py:258-281`

**问题:** `update_item` 函数仍是 load → modify → save 模式：

```python
item = load_item(task_id, item_id)          # 读取
updated_fields = { ... }                     # 修改
item.update(updated_fields)                  # 更新
save_item(task_id, item)                     # 保存
```

两个并发调用同时 load → 各自修改 → 后写入覆盖先写入，数据丢失。

**修复建议:**
- 方案 A: 加文件锁（`filelock` 库或 `fcntl.flock`）
- 方案 B: 使用临时文件 + `os.replace()` 原子替换

**受影响文件:** `src/ai_icon_pipeline/storage.py`

---

### Pass 2 — INFORMATIONAL

#### 3. 枚举值未全覆盖 — `failed` / `archived` 状态未处理

**状态: ✅ 已修复**

- `_item_main_action` 添加了 `failed` / `archived` 映射
- `_run_main_action` 添加了 `if status in {"completed", "failed", "archived"}: return`
- `_run_secondary_action` 同上

---

## Files Changed

| 文件 | 变更 | 说明 |
|------|------|------|
| `src/ai_icon_pipeline/ui.py` | +1338 (new) | Streamlit 工作台主界面 |
| `src/ai_icon_pipeline/ui_launcher.py` | +18 (new) | UI 启动器 |
| `src/ai_icon_pipeline/storage.py` | +190/-7 | 新增 `create_item`、`update_item`、`list_tasks` 等 |
| `src/ai_icon_pipeline/cli.py` | +55/-20 | 新增 `create-item`、`update-item` 命令 |
| `src/ai_icon_pipeline/mock_providers.py` | +33/-9 | 支持 `project_background`、`style_requirements` |
| `src/ai_icon_pipeline/pipeline.py` | +13/-2 | 适配新字段 |
| `pyproject.toml` | +5/-1 | 添加 streamlit 依赖和 UI 入口 |
| `README.md` | +37/-5 | 更新文档 |

---

## Action Items

- [x] ~~修复 XSS 漏洞~~ — 已添加 `_esc()` 转义所有用户输入
- [ ] 修复竞态条件 — `update_item` 添加原子性保证（filelock 或 os.replace）
- [x] ~~修复枚举完整性~~ — 已处理 `failed` / `archived` 状态

---

## Verdict

**剩余 1 个 CRITICAL 问题（竞态条件）**。该问题在单用户本地场景下风险较低，但建议在合并前修复或确认接受风险。

- 如果接受风险：可以合并，后续添加文件锁
- 如果需要修复：加 `filelock` 依赖，`update_item` 加锁即可
