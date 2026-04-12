# AGENTS

本文件是给后续协作者和 agent 的项目工作手册。

它不替代 README。

- [README.md](./README.md) 负责对外说明项目是什么、怎么跑、怎么用
- `AGENTS.md` 负责说明这个仓库内部怎么理解、怎么改、怎么验证

## 项目定位

这是一个 **local-first 的游戏资产生产工作台**。

项目采用混合工作流：

- **Agent / CLI**：负责批次编排、流程推进、Provider 管理、状态查询、导出
- **Web UI**：负责人类视觉审图、候选筛选、星标和最终确认

请不要把这个项目当成“纯文本就能完成全部工作流”的系统。

对于候选图筛选、最终采用判断这类视觉决策，默认应该回到 Web UI。

## 目录地图

### Python Core

- [src/ai_icon_pipeline/storage.py](./src/ai_icon_pipeline/storage.py)
  本地文件存储、task/item/artifact 读写、批次指标
- [src/ai_icon_pipeline/pipeline.py](./src/ai_icon_pipeline/pipeline.py)
  核心流程推进、生成/轮询/状态恢复
- [src/ai_icon_pipeline/state_machine.py](./src/ai_icon_pipeline/state_machine.py)
  条目状态机和允许的步骤迁移
- [src/ai_icon_pipeline/provider_runtime.py](./src/ai_icon_pipeline/provider_runtime.py)
  brief / prompt 上下文合并，运行时 provider 选择
- [src/ai_icon_pipeline/settings.py](./src/ai_icon_pipeline/settings.py)
  Provider 与全局设置

### API / CLI

- [src/ai_icon_pipeline/api.py](./src/ai_icon_pipeline/api.py)
  FastAPI 应用和 Web API
- [src/ai_icon_pipeline/api_launcher.py](./src/ai_icon_pipeline/api_launcher.py)
  API 启动入口
- [src/ai_icon_pipeline/cli.py](./src/ai_icon_pipeline/cli.py)
  CLI 分组命令、任务编排、导出、runtime 解析

### Provider 适配

- [src/ai_icon_pipeline/providers/openai_compatible.py](./src/ai_icon_pipeline/providers/openai_compatible.py)
- [src/ai_icon_pipeline/providers/async_image.py](./src/ai_icon_pipeline/providers/async_image.py)
- [src/ai_icon_pipeline/providers/gemini_native.py](./src/ai_icon_pipeline/providers/gemini_native.py)
- [src/ai_icon_pipeline/providers/registry.py](./src/ai_icon_pipeline/providers/registry.py)

如果要接新的第三方，优先判断它属于哪一类协议：

- `openai_compatible`
- `async_image`
- `gemini_native`

尽量不要为单个站点重写整条链路。

### Web UI

- [web/src/components/BatchDashboard.tsx](./web/src/components/BatchDashboard.tsx)
  批次页、条目概览、批量导入、流程指标
- [web/src/components/ItemWorkspace.tsx](./web/src/components/ItemWorkspace.tsx)
  条目工作台、候选池、版本历史、操作区
- [web/src/components/GlobalSettings.tsx](./web/src/components/GlobalSettings.tsx)
  Provider 与全局设置
- [web/src/hooks/useWorkbenchController.ts](./web/src/hooks/useWorkbenchController.ts)
  Web 状态编排
- [web/src/lib/api.ts](./web/src/lib/api.ts)
  前端 API 调用
- [web/src/lib/itemImport.ts](./web/src/lib/itemImport.ts)
  CSV / TSV / 表格导入解析与模板

## 常见任务应该去哪改

### 改批次级设置、指标、导出

优先看：

- [web/src/components/BatchDashboard.tsx](./web/src/components/BatchDashboard.tsx)
- [src/ai_icon_pipeline/storage.py](./src/ai_icon_pipeline/storage.py)
- [src/ai_icon_pipeline/api.py](./src/ai_icon_pipeline/api.py)

### 改条目工作台、候选池、版本历史

优先看：

- [web/src/components/ItemWorkspace.tsx](./web/src/components/ItemWorkspace.tsx)
- [web/src/hooks/useWorkbenchController.ts](./web/src/hooks/useWorkbenchController.ts)

### 改 provider 接入、模型同步、运行时模型选择

优先看：

- [src/ai_icon_pipeline/settings.py](./src/ai_icon_pipeline/settings.py)
- [src/ai_icon_pipeline/provider_runtime.py](./src/ai_icon_pipeline/provider_runtime.py)
- [src/ai_icon_pipeline/providers/registry.py](./src/ai_icon_pipeline/providers/registry.py)
- 具体协议文件：
  - [src/ai_icon_pipeline/providers/openai_compatible.py](./src/ai_icon_pipeline/providers/openai_compatible.py)
  - [src/ai_icon_pipeline/providers/async_image.py](./src/ai_icon_pipeline/providers/async_image.py)
  - [src/ai_icon_pipeline/providers/gemini_native.py](./src/ai_icon_pipeline/providers/gemini_native.py)

### 改 CLI 能力

优先看：

- [src/ai_icon_pipeline/cli.py](./src/ai_icon_pipeline/cli.py)

CLI 当前主要按这些心智分组：

- `task`
- `item`
- `step`
- `artifact`
- `image`
- `provider`
- `runtime`
- `export`
- `pipeline`

## CLI 心智模型

这个项目的 CLI 不是“一个个零散命令”，而是一套工作流控制面。

### `task`

负责批次：

- 创建
- 更新
- 查看
- 指标

### `item`

负责条目源数据：

- 新增
- 更新
- 查看

### `step`

负责生成阶段推进：

- run
- approve
- rollback

### `artifact`

负责版本：

- list
- show
- use

### `image`

负责候选图层面的操作：

- pending
- poll
- cancel
- star / unstar
- starred

### `provider`

负责 Provider 管理：

- list / show
- add / update / delete
- sync-models

### `runtime`

负责解析某一步到底会用哪个 provider / model。

### `export`

负责导出，例如整批星标图 ZIP。

## 什么时候应该回到 Web UI

当任务涉及这些内容时，默认应该引导用户回到 Web UI：

- 比较候选图
- 做视觉判断
- 星标多张图
- 确认最终采用图

CLI 可以做：

- 列出星标
- 导出星标
- 查询当前采用版本

但不应该假装纯文本就能替代视觉审图。

## 本地启动

### 最快方式

macOS：

- `start_local.command`
- `stop_local.command`

Windows：

- `start_local.bat`
- `stop_local.bat`

### 手动方式

后端：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.api_launcher --reload
```

前端：

```bash
cd web
npm install
npm run dev -- --host 127.0.0.1
```

默认端口：

- 前端：`5173`
- 后端：`8000`

## 验证命令

### Python 侧

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=src python3 -m compileall src
```

### 前端

```bash
cd web
npm run lint
npm run build
```

## 修改约定

### 安全边界

- 默认按 local-first 思路考虑
- 不要重新暴露任意文件路径
- `/files` 只允许图片和导出，不要把内部状态文件重新放出来

### Provider 改动

- 优先做协议层适配，不要先做站点专属逻辑
- 站点级补丁如果必须存在，尽量配置化

### UI 改动

- 批次页优先看“批量控制”和“指标”
- 条目页优先看“中间主画布”和“候选筛选”
- 不要让操作区抢过图片本身

### CLI / Agent 改动

- 如果某个能力已经在 Web 里跑通，CLI 应尽量提供对应入口
- 如果某个任务本质依赖视觉判断，CLI 应该输出状态并引导回 Web，而不是伪造纯文本体验
