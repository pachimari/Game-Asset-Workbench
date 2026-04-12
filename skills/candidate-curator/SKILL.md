---
name: candidate-curator
description: Curate candidate image state in AI Icon Pipeline, including listing candidates, starring or unstarring versions, setting the current candidate, checking adopted versions, exporting starred images, and routing visual review back to the Web UI. Use this skill whenever the user mentions candidate images, stars, current selection, exporting good images, visual picking, or version curation.
---

# Candidate Curator

这个 skill 负责候选图整理，不负责生成流程本身。

它适合处理的是“候选池怎么整理、怎么导出、当前采用是什么”，而不是 provider 配置或整个批次推进。

## 什么时候用

当用户想做这些事时，进入这个 skill：

- 查看某个 item 的候选图状态
- 星标或取消星标候选图
- 查看当前已星标版本
- 设置当前候选
- 看当前采用版本
- 导出星标图
- 整理某个 item 或整个批次的候选结果

## 核心边界

这个 skill 可以帮助管理候选图状态，但不应该替用户做主观视觉判断。

它可以做：

- 查询
- 标记
- 切换当前候选
- 导出

它不应该做：

- 只靠文本判断哪张最好
- 伪装成已经完成了视觉筛选

## 视觉筛选规则

当用户需要：

- 直接比较多张候选图
- 决定最终采用哪张
- 检查细节、风格、构图是否更好

要明确引导回 Web UI：

- `http://127.0.0.1:5173/`

并指出：

- 应打开哪个 item
- 应切到“候选池”

## 工作步骤

进入这个 skill 后，优先按这个顺序做：

1. 看用户是在处理单个 item，还是整个批次的候选结果。
2. 如果是查询类任务，先汇总当前候选、当前候选版本、星标情况。
3. 如果是状态变更类任务，再执行 star / unstar / use / export。
4. 如果任务需要视觉比较，就停在可交接的状态，并导回 Web UI。

## 应看的仓库文件

候选图整理相关，优先看：

- [`../../src/ai_icon_pipeline/storage.py`](../../src/ai_icon_pipeline/storage.py)
- [`../../src/ai_icon_pipeline/api.py`](../../src/ai_icon_pipeline/api.py)
- [`../../src/ai_icon_pipeline/cli.py`](../../src/ai_icon_pipeline/cli.py)
- [`../../web/src/components/ItemWorkspace.tsx`](../../web/src/components/ItemWorkspace.tsx)
- [`../../web/src/components/BatchDashboard.tsx`](../../web/src/components/BatchDashboard.tsx)

## 输出格式

处理候选图请求时，优先用这种结构：

- 当前候选状态
- 当前星标状态
- 已执行动作
- 是否需要回 Web UI 做最终筛选

## 何时转交别的 Skill

这些场景应该转交：

- 需要重新生成候选图：转 `item-workflow`
- provider 接不上、模型拉不到：转 `provider-manager`
- 用户要看整个批次推进和指标：转 `batch-operator`

## 反模式

避免这些问题：

- 把“能导出”误说成“已经完成了最终筛选”
- 在 CLI 里替用户做审美判断
- 用户明明在处理整个批次，却只回答单个 item 的候选状态
