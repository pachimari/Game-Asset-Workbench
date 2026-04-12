---
name: ai-icon-pipeline-router
description: Use this skill as the default entry point for work inside AI Icon Pipeline. Trigger when the user asks to continue this project, operate a batch, work on an item, configure a provider, sync models, review candidates, export results, or generally "use the icon pipeline". On first use, always check whether at least one provider and model are configured before attempting any generation workflow.
---

# AI Icon Pipeline 总入口

这是 AI Icon Pipeline 仓库内的顶层路由 skill。

它的职责不是把所有事情都塞进一个大 prompt 里，而是先判断：**下一步应该进入哪个工作流。**

这个项目天然分成两种工作方式：

- **Agent / CLI** 负责编排、配置、查询、导出、推进流程。
- **Web UI** 负责人类视觉审阅、候选图比较、星标筛选、最终确认。

如果任务依赖主观视觉判断，不要假装终端就够了，要主动把用户导回 Web 工作台。

## 首次使用规则

当用户是第一次使用项目，或者当前环境看起来还没准备好时，优先检查 provider 是否就绪，再做其他事情。

至少要确认这几件事：

1. 是否已经存在至少一个 provider。
2. provider 的协议类型是否合理。
3. 模型是否已经同步，或者已经具备可用模型。
4. 当前要跑的流程，是否已经有可用的默认模型。

如果 provider 还没准备好，就先进入 provider 工作流。

不要在环境未就绪时，直接开始创建批次或生成图片。

## CLI-First 模式

如果用户明确表示：

- 先纯 CLI
- 先不要进 Web
- 最后再去看图

那么默认进入 **CLI-first mode**。

在这个模式下：

- 前半程尽量留在 CLI / agent 内完成
- 只在真正需要视觉判断时再切回 Web UI
- 不要在每一步都打断用户去打开页面

但要记住，CLI-first 不等于 UI-never。

一旦进入这些场景，仍然要明确交接回 Web：

- 看候选图
- 比较哪张更好
- 星标筛选
- 最终采用

## 异步 Provider 交付边界

对于 `async_image` provider，要把“链路成功”和“最终图片就绪”分开看。

默认交付阈值是：

1. `image_generation` artifact 已经写入
2. 已拿到远端 `task_id`
3. 当前状态已经进入 `queued`、`processing`、`pending` 或 `image_generating`

只要满足这三条，就可以视为：

- 提交成功
- 链路已通
- 可以把当前节点交付给用户

这时不要默认继续长时间主动轮询。

更合理的做法是：

- 告诉用户当前 task / item / provider / model
- 明确说明这是异步任务，正在后台跑
- 告诉用户去哪里看状态
- 需要时再回来做后续批准、筛图、导出

不要让 agent 假装必须全程陪跑到最终图片落地。

## 路由规则

根据用户目标，只选择一个最主要的工作流进入。

### 路由到 Provider 管理

当用户想做这些事时，优先进入 provider 工作流：

- 新增或编辑 provider
- 选择协议类型
- 同步模型
- 排查模型为什么拉不到
- 判断某个接口属于哪类 provider
- 修复由 provider 配置导致的生成失败

如果首次使用检查没有通过，这也应该是默认入口。

### 路由到批次操作

当用户想做这些事时，进入 batch 工作流：

- 创建批次
- 更新批次级设置
- 从 CSV 或 TSV 导入条目
- 推进整个批次
- 查看批次指标
- 导出批次级结果

这条路由关心的是整个批次，不是某一个 item。

对于“帮我跑一轮”“整批推进”“直接跑到候选图”的请求，默认优先考虑：

- `pipeline run`

而不是先把流程拆成一层层手动 `step run`。

### 路由到条目工作流

当用户想做这些事时，进入 item 工作流：

- 查看某一个 item
- 生成或重做 brief
- 生成或重做出图指令
- 生成或轮询候选图
- 回退步骤
- 查看单个 item 的 runtime model 解析结果

这条路由负责把一个 item 往前推进。

如果用户要的是“快速跑一轮单条目主流程”，也应优先考虑：

- `pipeline run --item-id ...`

### 路由到候选图整理

当用户想做这些事时，进入 candidate 工作流：

- 星标或取消星标候选图
- 查看当前已星标候选
- 设置当前候选
- 导出星标图片
- 整理候选池状态

如果任务只是查询状态或导出结果，CLI/agent 就够了。

如果任务是**判断哪张图最好**，就必须把用户导回 Web UI。

## 视觉审阅边界

Web UI 才是视觉审阅的主场。

当用户需要做这些事时，要主动引导回工作台：

- 直接比较多张候选图
- 决定最终采用哪张
- 检查构图、风格、脸部、细节、氛围是否合适
- 在最终确认前回看星标图

默认本地地址：

- `http://127.0.0.1:5173/`

把用户导回 Web UI 时，要说清楚：

- 应该打开哪个批次或哪个 item
- 应该切到哪个页签
- 为什么这件事更适合在 UI 里做，而不是继续在 CLI 里做

## 工作方式

当这个 skill 触发时，优先按这个顺序做：

1. 判断环境是否 ready。
2. 选定一个主路由。
3. 简短说明本次进入哪条路由。
4. 执行或准备下一步最具体的动作。
5. 如果需要视觉判断，就在该停的地方停下，并导回 UI。

不要一次性把所有命令都倒给用户。先选对路，再做下一步。

## 生成前确认卡

当任务即将真正开始生成，尤其是在 `pipeline run` 之前，先给用户一个很短的确认卡。

至少确认这些项目：

- `task_id`
- 本次处理的是整批还是某几个 item
- brief 用哪个 provider / model
- prompt 用哪个 provider / model
- image_generation 用哪个 provider / model / `sync|async`
- 本次是否直接使用 `pipeline run`
- 是否默认自动批准中间步骤

不要在这些关键配置没有对齐时悄悄开跑。

如果信息已明确，就用一句很短的摘要让用户确认；不要把确认卡写成冗长报告。

## 创建后自检

当你执行了创建类动作后，不要立刻假设数据就一定完好。

至少做一次最小自检：

- `task create` 之后，立刻 `task show`
- `item create` 之后，立刻 `item show`

如果列表命令不可用或当前有缺陷，优先用 show 类命令做确认。

目标是尽早发现：

- 数据写坏
- 配置未落盘
- 结构不完整
- CLI 输出和实际存储不一致

## 子 Skill 入口

完成路由判断后，按需继续读取对应子 skill：

- Provider 管理：[`provider-manager/SKILL.md`](./provider-manager/SKILL.md)
- 批次操作：[`batch-operator/SKILL.md`](./batch-operator/SKILL.md)
- 条目工作流：[`item-workflow/SKILL.md`](./item-workflow/SKILL.md)
- 候选图整理：[`candidate-curator/SKILL.md`](./candidate-curator/SKILL.md)

只继续打开当前任务真正需要的那一个，不要四个一起读。

## 输出格式

路由后的响应，优先保持这种结构：

- 当前状态
- 已选路由
- 已执行动作或下一步动作
- 当前应继续留在 CLI，还是该切回 Web UI

如果是生成相关问题，尽量再明确补一句：

- 当前卡在哪一层：`配置层 / prompt 层 / 提交层 / 轮询层 / 下载层`

保持具体、可执行，不要泛泛而谈。

## 仓库上下文

在做较大改动前，先查看：

- [`AGENTS.md`](../AGENTS.md)

那里会说明：

- 仓库结构
- 常见改动应该看哪些文件
- 验证命令
- CLI 和 Web 的职责边界

## 验证提醒

代码改动后，只跑和当前改动相关的验证。

常用检查：

- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'`
- `PYTHONPATH=src python3 -m compileall src`
- `cd web && npm run lint`
- `cd web && npm run build`

## 反模式

要避免这些问题：

- provider 还没配好就直接开始生成
- 在 CLI 里替用户做主观审美判断
- 对异步任务提交成功后，还默认长时间陪跑轮询
- 把批次级问题当成单 item 问题处理
- 在没有证据时，把单 item 故障直接归因成 provider 问题
- 不做路由判断，直接把一堆命令全抛给用户
