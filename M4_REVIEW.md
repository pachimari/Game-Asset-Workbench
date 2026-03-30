# M4 Provider Runtime & CLI PR Review

**PR:** [#2 M4: add provider runtime, async image jobs, and agent-friendly CLI](https://github.com/pachimari/ai-icon-pipeline/pull/2)
**Branch:** `codex/m4-provider-runtime` → `main`
**Changes:** +5071 / -329 across 18 files
**Reviewer:** opencode (mimo-v2-pro-free)
**Date:** 2026-03-30

---

## Summary

PR 添加了：
1. **Provider Runtime** — Gemini/DeepSeek/自定义 Provider 支持
2. **异步图片任务** — submit/poll/cancel 完整异步协议
3. **Agent 友好 CLI** — JSON 输出、capabilities/schema 发现、状态机发现
4. **设置管理** — 本地 API Key 存储（`.local/app_settings.json`）
5. **Chat Control** — 受限命令规划器

**Scope Check: CLEAN**
- Intent: 添加 Provider Runtime、异步图片、Agent CLI
- Delivered: 所有功能实现，无范围漂移

---

## Review Result: 1 informational issue

### Pass 1 — CRITICAL

**无关键安全问题** ✅

- API Key 存储在 `.local/` 目录，已加入 `.gitignore`
- API Key 输入使用 `type="password"`
- CLI `provider-show` 输出已掩码 (`xxx...xxx` 格式)
- Chat Control 使用白名单命令
- 所有 Provider 请求使用参数化 API Key

---

### Pass 2 — INFORMATIONAL

#### 1. User-Agent 硬编码版本号

**位置:** `providers/toapis_async.py:18`

```python
"User-Agent": "ai-icon-pipeline/0.1",
```

**问题:** 版本号硬编码会随时间变得不准确，需要手动维护。

**修复建议:** 从 `pyproject.toml` 动态读取版本：

```python
from importlib.metadata import version
__version__ = version("ai-icon-pipeline")
```

或定义全局版本常量并引用。

---

#### 2. Async Status 检测可能遗漏新状态

**位置:** `pipeline.py` 中的 `PENDING_ASYNC_STATUSES`

**问题:** 若第三方 Provider 新增状态（如 "rendering"），需要手动同步。

**修复建议:**
- 文档化需同步的状态列表
- 或在 provider 类中添加抽象方法获取 pending 状态集合

---

## Files Changed Summary

| 类别 | 文件 |
|------|------|
| 新增 Provider | `gemini_native.py`, `openai_compatible.py`, `toapis_async.py`, `registry.py` |
| 新增 Runtime | `settings.py`, `provider_runtime.py`, `chat_control.py` |
| CLI 增强 | `cli.py` 大幅重构，支持分组命令、JSON 输出、capabilities/schema |
| UI 增强 | `ui.py` 添加 Provider 管理、Settings 界面 |
| 文档 | `CLI_INTERFACE.md` (426 行设计稿) |

---

## Verdict

**✅ 通过 — 1 个轻微 informational 问题**

唯一问题是 User-Agent 硬编码版本号，建议修复但不阻塞合并。其余实现质量良好，安全设计合理。