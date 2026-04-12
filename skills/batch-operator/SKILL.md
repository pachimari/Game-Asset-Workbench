---
name: batch-operator
description: Handle batch-level operations inside AI Icon Pipeline, including creating batches, updating batch settings, importing CSV or TSV items, running the whole batch, reading batch metrics, and exporting batch results. Use this skill whenever the user talks about the whole batch, bulk import, one-click runs, batch metrics, or batch-level exports.
---

# Batch Operator

这个 skill 负责批次级控制。

它关心的是整个 task 的节奏、设置和结果，不负责单个 item 的细节调试，也不替用户做视觉判断。

## 什么时候用

当用户想做这些事时，进入这个 skill：

- 创建批次
- 更新批次级背景设定、风格要求、全局限制
- 从 CSV / TSV 导入条目
- 推进整个批次
- 查看批次流程指标
- 导出整批星标图或结果
- 了解这批现在卡在哪

## 核心目标

完成批次工作流后，应该尽量让用户得到一个明确结果：

- 这批是否已经准备好可以运行
- 这批现在推进到哪一步
- 这批的关键指标怎么样
- 用户下一步该继续批量推进，还是下钻到某个 item

## 工作步骤

进入这个 skill 后，优先按这个顺序处理：

1. 确认 provider 是否 ready。
2. 查看当前 task 是否存在。
3. 如果用户要建批次，先创建 task，再导入或新增 item。
4. 如果用户要调整批次级设定，优先改 task 配置。
5. 如果用户要推进整批，先给出一张很短的生成前确认卡。
6. 如果用户是想“直接跑一轮”，默认优先使用 `pipeline run`。
7. 如果用户要推进整批，先看当前状态和失败项，再执行批次操作。
8. 运行后重新汇总当前状态和指标。
9. 如果用户要看效果，读取批次指标而不是只看零散状态。

## 生成前确认卡

在真正执行批次生成前，优先用很短的摘要确认：

- `task_id`
- item 范围
- brief provider / model
- prompt provider / model
- image provider / model
- 是否直接使用 `pipeline run`

如果用户没有明确指定 provider / model，不要默认当成“无所谓”。

## 创建后自检

如果这个 skill 执行了创建动作，立刻做最小自检：

- `task create` 后接 `task show`
- 如果又创建了 item，再对关键 item 做 `item show`

不要创建完就立刻继续整批推进而不做确认。

## 适合用 CLI/Agent 做的事

这些任务通常可以直接在 CLI/agent 里完成：

- 创建 task
- 更新 task 级设置
- 导入 batch 示例或 CSV/TSV
- 查看 metrics
- 导出星标 ZIP
- 汇总某批次当前状态

其中“先跑一轮主流程”默认优先考虑：

- `pipeline run <task_id>`

## 不适合在这里硬做的事

这些不应该在 batch skill 里硬处理：

- 某一个 item 的细节返工
- 视觉筛选哪张候选图最好
- provider 接口兼容性诊断

对应地应该转交：

- 单 item 细节：`item-workflow`
- provider 问题：`provider-manager`
- 候选图筛选和星标整理：`candidate-curator`

## 应看的仓库文件

批次相关改动或查询，优先看：

- [`../../src/ai_icon_pipeline/storage.py`](../../src/ai_icon_pipeline/storage.py)
- [`../../src/ai_icon_pipeline/api.py`](../../src/ai_icon_pipeline/api.py)
- [`../../src/ai_icon_pipeline/cli.py`](../../src/ai_icon_pipeline/cli.py)
- [`../../web/src/components/BatchDashboard.tsx`](../../web/src/components/BatchDashboard.tsx)
- [`../../web/src/lib/itemImport.ts`](../../web/src/lib/itemImport.ts)

## 输出格式

处理批次请求时，优先用这种结构：

- 批次当前状态
- 已执行动作
- 关键指标或进度摘要
- 下一步建议

如果下一步需要人工视觉判断，要明确指出应该去 Web UI。

## 反模式

避免这些问题：

- provider 还没准备好就直接跑整批
- 没确认 provider / model 就直接开跑
- 用单 item 视角回答批次问题
- 只告诉用户“成功/失败”，不说整批节奏和下一步
- 明明该下钻某个 item，却继续留在批次层空转
