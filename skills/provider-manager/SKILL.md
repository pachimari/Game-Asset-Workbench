---
name: provider-manager
description: Manage provider setup inside Game Asset Workbench, including protocol selection, model sync, endpoint fit, and availability debugging. Use this skill whenever the user mentions providers, syncing models, third-party endpoints, base URLs, API keys, protocol types, default models, missing models, compatibility questions, or first-time setup.
---

# Provider Manager

这个 skill 负责把 provider 配置这条线处理清楚。

它适合解决的是“能不能接上”“模型能不能拉到”“这一步到底该选哪种协议”，而不是批次推进或视觉筛图。

## 什么时候用

遇到这些情况时，优先进入这个 skill：

- 首次使用项目，需要先完成环境准备
- 新增 provider
- 编辑 provider
- 选择 provider_type
- 同步模型
- 检查默认模型为什么不可用
- 判断第三方接口应归入哪类协议
- 排查图片或文本生成失败是否由 provider 配置引起

## 核心目标

完成 provider 工作流后，应该尽量让用户得到一个明确结果：

- 至少一个可用 provider
- 至少一个可用模型
- 当前工作流知道该默认用哪个 provider / model

如果还达不到这一步，就不要把用户推进 batch 或 item 工作流。

## 协议分类

当前项目按协议层而不是按站点名来理解 provider。

优先把接口归入以下三类之一：

### `openai_compatible`

适用于：

- 提供 `/models`
- 提供 OpenAI 风格文本或图片接口
- 认证方式接近 Bearer token

通常是默认首选。

### `async_image`

适用于：

- 图片生成要先提交任务
- 后续通过任务 id 轮询
- 取消、查询状态、下载结果是分开的

它通常只参与候选图阶段。

### `gemini_native`

适用于：

- 接口本身更接近 Gemini 原生风格
- 图片或内容生成不是标准 OpenAI 兼容接口
- 需要 query key / Bearer fallback 或 Gemini 原生返回结构

## 工作步骤

进入这个 skill 后，优先按这个顺序处理：

1. 看当前有没有 provider。
2. 看目标 provider 的 `provider_type` 是否选对。
3. 看 `base_url` 和 `api_key` 是否合理。
4. 尝试同步模型，或检查已有模型列表。
5. 确认默认模型是否覆盖用户当前要做的步骤。
6. 如果失败，再判断是协议不匹配、模型不可用，还是 provider 自身不稳定。

## 稳定性记忆

如果同一个 provider / model 在同一批任务，或者最近的调试过程中，连续两次以上出现同步断连、远端提前断开、或类似的提交层网络异常，就不要机械地继续重试。

这时应优先建议：

- 切换到备用 provider
- 或至少换一个更稳定的 model

不要把这种问题误判成 prompt 质量问题。

## 判断标准

如果用户只提供了一个第三方地址，不要立刻假设它是 OpenAI 兼容。

优先根据这些线索判断：

- 是否有 `/models`
- 生成图片时是同步返回还是异步提交任务
- 返回结构里是否有任务 id
- 是否更像原生 Gemini 风格

如果证据不够，就先保守选择最像的协议，并明确告诉用户这是当前假设。

## 应看的仓库文件

排查或修改 provider 相关逻辑时，优先看：

- [`../../src/ai_icon_pipeline/settings.py`](../../src/ai_icon_pipeline/settings.py)
- [`../../src/ai_icon_pipeline/provider_runtime.py`](../../src/ai_icon_pipeline/provider_runtime.py)
- [`../../src/ai_icon_pipeline/providers/registry.py`](../../src/ai_icon_pipeline/providers/registry.py)
- [`../../src/ai_icon_pipeline/providers/openai_compatible.py`](../../src/ai_icon_pipeline/providers/openai_compatible.py)
- [`../../src/ai_icon_pipeline/providers/async_image.py`](../../src/ai_icon_pipeline/providers/async_image.py)
- [`../../src/ai_icon_pipeline/providers/gemini_native.py`](../../src/ai_icon_pipeline/providers/gemini_native.py)
- [`../../web/src/components/GlobalSettings.tsx`](../../web/src/components/GlobalSettings.tsx)

如果是 CLI 路径，还要看：

- [`../../src/ai_icon_pipeline/cli.py`](../../src/ai_icon_pipeline/cli.py)

## 输出格式

处理 provider 问题时，优先给出这种结构：

- 当前 provider 状态
- 协议判断
- 已执行动作
- 当前可用模型
- 下一步建议

如果问题还没解决，要明确卡在：

- 协议判断
- 鉴权
- 模型发现
- 提交层
- 轮询层
- 下载层

如果这个 provider 是异步图片接口，还要明确告诉用户：

- 交付阈值是“成功提交并拿到 task_id”
- 不是“必须轮询到最终图片返回”

## 何时转交别的 Skill

这些场景应该结束 provider 工作流并转交：

- provider 已可用，用户要创建或推进整个批次：转 `batch-operator`
- provider 已可用，用户要推进某一个 item：转 `item-workflow`
- provider 已可用，用户要星标/导出候选图：转 `candidate-curator`

## 反模式

避免这些问题：

- 首次使用时跳过 provider 检查
- 看到图片生成失败就直接归因成 prompt 问题
- 只凭站点名决定协议，不看真实接口形态
- 同一个 provider/model 连续断连还机械重试
- provider 根本没 ready，就继续推进工作流
