---
name: item-workflow
description: Drive the workflow for a single item in AI Icon Pipeline, including status inspection, generating or redoing briefs and image prompts, generating candidate images, polling results, rolling back steps, and resolving runtime models. Use this skill whenever the user focuses on one item, one step, prompt regeneration, rollback, or current model selection.
---

# Item Workflow

这个 skill 负责一个 item 从输入到候选图的推进。

它是最核心的工作流 skill，但它不负责 provider 初始化，也不替用户做主观视觉判断。

## 什么时候用

当用户想做这些事时，进入这个 skill：

- 查看某个 item 当前状态
- 生成或重做 brief
- 生成或重做出图指令
- 生成候选图
- 轮询或取消候选图后台任务
- 回退某一步
- 查看这一项实际会用哪个 provider / model
- 修正单个条目的原始描述或局部配置

## 核心目标

完成 item 工作流后，应该尽量让用户得到一个明确结果：

- 当前 item 在哪一步
- 本次动作是否推进成功
- 当前候选或后台任务情况如何
- 下一步是继续推进，还是进入 Web UI 审图

## 前置检查

在真正推进 item 之前，先确认：

1. provider 和模型已经可用
2. 当前 item 存在
3. 当前状态允许执行用户要做的动作
4. 当前这轮要用的 provider / model 是否已经明确

如果问题根源明显是 provider 未配置或模型不可用，就转回 `provider-manager`。

## 工作步骤

进入这个 skill 后，优先按这个顺序做：

1. 读取当前 item 状态。
2. 如果刚创建 item，先做一次 `item show` 自检。
3. 确认用户要处理的是哪一步，还是要直接跑主流程。
4. 如果用户要“快速跑一轮”，优先考虑 `pipeline run --item-id ...`。
5. 在生成前先确认本轮 provider / model。
6. 如有需要，解析 runtime model。
7. 再决定是否应该 `run`、`approve`、`rollback`、`poll` 或 `cancel`。
8. 如果 `image_generation` 是异步 provider，要把“成功提交并拿到 task_id”视为一个单独交付节点。
9. 执行动作后重新汇总当前状态。
10. 如果已经进入候选图阶段且需要人做视觉判断，就导回 Web UI。

## 生成前确认卡

在真正执行生成前，优先给出一个很短的确认摘要：

- `task_id`
- `item_id`
- 当前将处理哪一步，或是否直接 `pipeline run --item-id`
- brief provider / model
- prompt provider / model
- image provider / model / `sync|async`
- 是否自动批准中间步骤

如果用户明显想走 CLI-first，不要频繁把他打断到 UI；但这些关键配置仍然要先拍板。

## CLI-First 策略

如果用户明确表示先纯 CLI，默认这样处理：

- 创建和更新 item 用 CLI
- 推进主流程优先用 `pipeline run --item-id`
- 查询后台任务和当前状态继续留在 CLI
- 只有到真正看图、选图时才切回 Web UI

这样可以把“前半段尽量不打断”的策略写清楚。

## 异步出图的完成定义

如果本轮 `image_generation` 走的是异步 provider，默认分成两个阶段：

1. `submit success`
2. `result ready`

第一阶段达到后，只要已经：

- 写入本地 `image_generation` artifact
- 拿到远端 `task_id`
- 状态进入 `queued / processing / image_generating`

就应该把这一轮先交付给用户。

这时默认不要继续长轮询。

应该明确告诉用户：

- 当前 task / item
- 当前 provider / model
- 当前远端任务已在跑
- 去 CLI 继续查状态还是去 Web UI 看对应 item

只有用户明确要求，或后续确实需要继续做批准/导出时，再回来轮询或继续下一步。

## 候选图阶段的边界

CLI/agent 可以做：

- 查询 pending 任务
- 轮询后台任务
- 取消后台任务
- 查询当前候选状态

CLI/agent 不应该做：

- 替用户决定哪张最好
- 假装能在纯文本里完成视觉筛选

当用户需要比较候选图时，要引导到：

- `http://127.0.0.1:5173/`

并明确告诉用户：

- 打开哪个 task / item
- 切到哪个页签，通常是“候选池”

## 应看的仓库文件

单 item 工作流相关，优先看：

- [`../../src/ai_icon_pipeline/pipeline.py`](../../src/ai_icon_pipeline/pipeline.py)
- [`../../src/ai_icon_pipeline/state_machine.py`](../../src/ai_icon_pipeline/state_machine.py)
- [`../../src/ai_icon_pipeline/provider_runtime.py`](../../src/ai_icon_pipeline/provider_runtime.py)
- [`../../src/ai_icon_pipeline/storage.py`](../../src/ai_icon_pipeline/storage.py)
- [`../../src/ai_icon_pipeline/cli.py`](../../src/ai_icon_pipeline/cli.py)
- [`../../web/src/components/ItemWorkspace.tsx`](../../web/src/components/ItemWorkspace.tsx)
- [`../../web/src/hooks/useWorkbenchController.ts`](../../web/src/hooks/useWorkbenchController.ts)

## 输出格式

处理单 item 请求时，优先保持这种结构：

- 当前 item 状态
- 本次处理的步骤
- 已执行动作
- 当前版本 / 候选 / 后台任务摘要
- 下一步建议

如果是失败或阻塞，尽量明确卡在：

- 配置层
- prompt 层
- 提交层
- 轮询层
- 下载层

## 何时转交别的 Skill

这些场景应该转交：

- provider 或模型有问题：转 `provider-manager`
- 用户要看整个批次状态或批量推进：转 `batch-operator`
- 用户要星标、导出、整理候选池：转 `candidate-curator`

## 反模式

避免这些问题：

- 不看状态机就直接强推下一步
- provider 明显没 ready 还继续跑 item
- 没确认本轮 provider / model 就直接生成
- 异步提交成功后还默认继续消耗 token 长轮询
- 明明需要人眼看图，还继续在 CLI 里做“选择”
- 把单 item 的问题扩大成整批问题
