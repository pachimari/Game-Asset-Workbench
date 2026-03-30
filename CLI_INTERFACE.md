# CLI 正式接口设计稿

本文件定义 `ai-icon-pipeline` 从“开发态命令集合”升级为“正式 CLI 接口”的目标形态。

目标用户有两类：
- 人类操作者：开发、策划、技术美术、自动化脚本维护者
- 外部 AI Agent：通过 CLI 稳定发现能力、执行命令、解析结果

该设计稿优先服务于：
- 后续 agent 接管
- 后续正式 UI / 本地桌面壳复用
- 后续薄 API 层设计

## 1. 设计目标

正式 CLI 应满足：

1. 命令稳定
2. 参数稳定
3. 输出稳定
4. 错误可机读
5. 能力可发现
6. 状态机可发现
7. 异步任务可管理

换句话说，CLI 不只是“能敲命令”，而是项目的一个正式运行时接口。

## 2. 现状与差距

当前 CLI 已经具备不少能力：
- 批次创建
- 条目创建/修改
- 阶段运行
- 审核
- 版本切换
- 回退
- 手动编辑设计说明/出图指令

但距离正式接口还差：
- 缺少统一命令命名体系
- 输出未统一支持 `--json`
- 缺少 `capabilities/schema`
- 缺少异步图片任务管理命令
- 缺少 provider / runtime 相关命令
- help 更偏人类调试，不够 agent-friendly

## 3. 命令树设计

建议从当前平铺命令，逐步收敛到分组命令。

迁移策略：
- 旧平铺命令继续保留，避免打断现有脚本、现有 agent、现有文档
- 新分组命令作为正式推荐入口
- `schema command` 与 `capabilities` 同时暴露旧命令与新别名
- 后续文档、外部 agent、新 UI 优先使用分组命令树

例如：

```text
旧命令: ai-icon-pipeline create-task
新命令: ai-icon-pipeline task create

旧命令: ai-icon-pipeline show-item
新命令: ai-icon-pipeline item show

旧命令: ai-icon-pipeline run-step
新命令: ai-icon-pipeline step run
```

### 3.1 Task

```text
ai-icon-pipeline task create
ai-icon-pipeline task list
ai-icon-pipeline task show
ai-icon-pipeline task update
```

职责：
- 创建批次
- 列出批次
- 查看批次
- 修改批次级设置

### 3.2 Item

```text
ai-icon-pipeline item create
ai-icon-pipeline item list
ai-icon-pipeline item show
ai-icon-pipeline item update
```

职责：
- 创建条目
- 列出条目
- 查看条目
- 修改条目原始需求与运行参数

### 3.3 Step

```text
ai-icon-pipeline step run
ai-icon-pipeline step approve
ai-icon-pipeline step rollback
```

职责：
- 运行阶段
- 通过阶段
- 回退阶段

### 3.4 Artifact

```text
ai-icon-pipeline artifact list
ai-icon-pipeline artifact show
ai-icon-pipeline artifact use
```

职责：
- 列版本
- 看版本
- 切换当前采用版本

### 3.5 Edit

```text
ai-icon-pipeline brief edit
ai-icon-pipeline prompt edit
```

职责：
- 手动编辑设计说明
- 手动编辑出图指令

### 3.6 Image

```text
ai-icon-pipeline image submit
ai-icon-pipeline image poll
ai-icon-pipeline image cancel
ai-icon-pipeline image pending
```

职责：
- 提交候选图生成任务
- 轮询异步图片任务
- 取消本地等待中的异步图片任务
- 查看当前未完成图片任务

### 3.7 Provider

```text
ai-icon-pipeline provider list
ai-icon-pipeline provider show
ai-icon-pipeline provider add
ai-icon-pipeline provider update
ai-icon-pipeline provider delete
ai-icon-pipeline provider sync-models
```

职责：
- 管理内置 / 第三方 provider 实例
- 同步模型列表

### 3.8 Runtime

```text
ai-icon-pipeline runtime resolve
ai-icon-pipeline runtime show
```

职责：
- 解析某个条目当前阶段实际生效的 provider/model/runtime
- 用于调试全局默认、批次覆盖、条目覆盖

### 3.9 Agent

```text
ai-icon-pipeline capabilities
ai-icon-pipeline schema command
ai-icon-pipeline schema state-machine
ai-icon-pipeline workflow help
```

职责：
- 给外部 agent 做能力发现
- 输出参数 schema
- 输出状态机约束
- 输出推荐工作流

## 4. 输出规范

正式 CLI 的关键命令应统一支持：

```text
--json
```

### 4.1 人类输出

默认输出适合人类阅读：
- 简洁
- 可扫描
- 带必要提示

### 4.2 机器输出

`--json` 输出必须：
- 字段名稳定
- 结构稳定
- 不混入额外说明文字

### 4.3 推荐返回结构

对于执行类命令，推荐返回：

```json
{
  "ok": true,
  "action": "step.run",
  "task_id": "task_001",
  "item_id": "item_003",
  "step": "image_generation",
  "from_status": "prompt_approved",
  "to_status": "image_generating",
  "current_versions": {
    "brief_generation": "v003",
    "image_prompt": "v005",
    "image_generation": "v007"
  },
  "message": "Submitted image generation job."
}
```

对于失败输出，推荐：

```json
{
  "ok": false,
  "error_code": "STATE_TRANSITION_INVALID",
  "message": "Cannot run step 'image_generation' while item status is 'draft'"
}
```

## 5. 错误规范

建议统一 error code，而不是只抛文本。

推荐错误码：
- `TASK_NOT_FOUND`
- `ITEM_NOT_FOUND`
- `ARTIFACT_NOT_FOUND`
- `STATE_TRANSITION_INVALID`
- `PROVIDER_NOT_FOUND`
- `MODEL_NOT_FOUND`
- `IMAGE_JOB_NOT_FOUND`
- `PROVIDER_REQUEST_FAILED`
- `VALIDATION_ERROR`

## 6. Schema / 能力发现

### 6.1 Capabilities

```bash
ai-icon-pipeline capabilities --json
```

返回示例：

```json
{
  "supports_json": true,
  "commands": [
    "task.create",
    "task.list",
    "task.show",
    "item.create",
    "item.update",
    "step.run",
    "step.approve",
    "step.rollback",
    "artifact.list",
    "artifact.use",
    "image.submit",
    "image.poll",
    "image.cancel"
  ]
}
```

### 6.2 Command Schema

```bash
ai-icon-pipeline schema command step.run --json
```

返回应包括：
- 命令名
- 必填参数
- 可选参数
- 输出 schema
- 常见错误码

### 6.3 State Machine Schema

```bash
ai-icon-pipeline schema state-machine --json
```

返回应包括：
- 所有状态
- 所有阶段
- 每个阶段允许从哪些状态运行
- 每个阶段允许在什么状态被 approve

## 7. 异步图片协议

第三方图片接口不是都同步返回图片，因此 CLI 必须显式支持异步协议。

推荐流程：

1. `image submit`
2. `image pending`
3. `image poll`
4. `image cancel`

### 7.1 Submit

提交后应返回：
- 本地 artifact version
- provider task id
- 当前状态

### 7.2 Poll

轮询后应返回：
- provider task id
- remote status
- progress
- 是否已落盘候选图

### 7.3 Cancel

取消应是“停止本地等待”，而不是承诺远端任务一定被 provider 真取消。

因此更准确的含义是：
- 本地标记为 `cancelled_local`
- 条目状态回退到可继续操作的状态

## 8. Help 规范

help 不该只列参数，还要包含：

- 命令作用
- 适用场景
- 参数说明
- 示例
- 常见工作流

推荐格式：

```text
ai-icon-pipeline step run

作用:
  运行某个条目的一个阶段。

允许阶段:
  brief_generation
  image_prompt
  image_generation

示例:
  ai-icon-pipeline step run --task-id task_001 --item-id item_003 --step image_generation
  ai-icon-pipeline step run --task-id task_001 --item-id item_003 --step image_generation --json
```

## 9. Agent 友好约束

为了让外部 AI agent 稳定使用，CLI 应保证：

1. 命令名不要频繁改
2. `--json` 字段不要频繁改
3. help 和 schema 真实反映现状
4. 状态流转不要依赖 UI 才能理解
5. 异步任务有完整 submit/poll/cancel 协议

## 10. 推荐实施顺序

### Phase 1
- 保留当前平铺命令
- 给核心命令补 `--json`
- 加 `capabilities`

### Phase 2
- 加 `schema command`
- 加 `schema state-machine`
- 统一错误码

### Phase 3
- 重构为分组命令树
- 增加 provider/runtime/image async 命令

### Phase 4
- 将 CLI 作为正式 agent runtime 接口
- 后续 Web UI 与本地 agent 都复用它或复用同一层核心接口

## 11. 与后续正式 UI 的关系

正式 UI 不会直接替代 CLI。

更合理的架构是：

- `core`：pipeline / storage / providers / settings
- `cli`：正式命令行接口
- `api`：未来轻量本地 API
- `ui`：正式前端

因此，CLI 规范化不是临时工作，而是在给：
- 外部 agent
- 自动化脚本
- 正式 UI 后端接口

共同打基础。
