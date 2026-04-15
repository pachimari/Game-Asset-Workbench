---
name: batch-operator
description: Handle batch-level operations inside Game Asset Workbench, including creating batches, updating batch settings, importing CSV or TSV items, running the whole batch, reading batch metrics, and exporting batch results. Use this skill whenever the user talks about the whole batch, bulk import, one-click runs, batch metrics, or batch-level exports.
---

# Batch Operator

这个 skill 负责批次级控制。

它关心的是整个 task 的节奏、设置和结果，不负责单个 item 的细节调试，也不替用户做视觉判断。

## 什么时候用

当用户想做这些事时，进入这个 skill：

- 创建批次
- 更新批次级背景设定、风格要求、全局限制
- 更新批次级长宽比和分辨率
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
7. 如果 `image_generation` 使用的是异步 provider，要把“成功提交”视为一个单独交付节点。
8. 如果用户要推进整批，先看当前状态和失败项，再执行批次操作。
9. 运行后重新汇总当前状态和指标。
10. 如果用户要看效果，读取批次指标而不是只看零散状态。

## 生成前确认卡

在真正执行批次生成前，优先用很短的摘要确认：

- `task_id`
- item 范围
- brief provider / model
- prompt provider / model
- image provider / model / `sync|async`
- image provider 的图片并发上限
- 本次批次级 `image_concurrency`
- 默认长宽比
- 默认分辨率
- 是否直接使用 `pipeline run`

如果用户没有明确指定 provider / model，不要默认当成“无所谓”。

如果用户还没有明确这轮的基础出图规格，也不要默认跳过。至少要确认：

- 是继续沿用当前批次默认值
- 还是这轮要改成新的长宽比 / 分辨率

如果是异步 provider，还要在确认卡里提前说清：

- 这轮的完成标准先是“提交成功”
- 不承诺 agent 会一直等到最终图片返回

如果用户提到了吞吐、批量出图、想加快整批候选生成，还要主动确认两层并发：

- provider 当前 `image_max_concurrency` 是多少
- 这次 `pipeline run` 是否需要显式带 `--image-concurrency`

不要把这两层混成一个参数。

## 创建后自检

如果这个 skill 执行了创建动作，立刻做最小自检：

- `task create` 后接 `task show`
- 如果又创建了 item，再对关键 item 做 `item show`

不要创建完就立刻继续整批推进而不做确认。

## 适合用 CLI/Agent 做的事

这些任务通常可以直接在 CLI/agent 里完成：

- 创建 task
- 更新 task 级设置
- 更新默认长宽比和分辨率
- 导入 batch 示例或 CSV/TSV
- 查看 metrics
- 导出星标 ZIP
- 汇总某批次当前状态

其中“先跑一轮主流程”默认优先考虑：

- `pipeline run <task_id>`

如果用户明确要提高批次吞吐，可以进一步用：

- `pipeline run <task_id> --image-concurrency <n>`

但要同时说明：

- 这只是批次调度并发
- 单个 provider 的真实生图提交仍然受 `image_max_concurrency` 限制

如果图片阶段是异步 provider，默认到“已提交成功并拿到远端任务 id”就可以先交付。

## 图片阶段节奏控制

如果用户要整批跑图片，不要默认把它理解成“适合高并发猛冲”。

当前项目里，批次推进默认是串行的。遇到图片 provider 的临时负载错误时，优先用“放慢提交节奏”而不是“继续机械重试”来处理。

批量图片阶段的优先建议顺序是：

1. 先继续使用 `pipeline run <task_id>`
2. 如果出现 `429`、`503`、`负载已饱和`、`load saturated`，优先加：
   - `--delay <秒数>`
3. 先观察同一 provider / model 是否稳定恢复
4. 连续两次以上仍在提交层失败，再建议切换 provider 或 model

不要把图片阶段的提交层负载问题误判成：

- prompt 写得不好
- 用户设定有问题
- 必须立刻改批次内容

更准确的说法通常是：

- `配置层` 没问题
- `prompt 层` 已正常产出
- `提交层` 遇到了 provider 侧临时负载限制

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

如果是异步 provider，还应明确写出：

- 哪些 item 已成功提交
- 哪些 item 仍在后台运行
- 用户现在该去 CLI 继续查状态，还是去 Web UI 看对应 item

如果下一步需要人工视觉判断，要明确指出应该去 Web UI。

## 反模式

避免这些问题：

- provider 还没准备好就直接跑整批
- 没确认 provider / model 就直接开跑
- 明明已经成功提交异步任务，还继续无意义长轮询
- 用单 item 视角回答批次问题
- 只告诉用户“成功/失败”，不说整批节奏和下一步
- 明明该下钻某个 item，却继续留在批次层空转
