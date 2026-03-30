# M5：前后端衔接与正式前端基础盘

本文件用于锁定 M5 的目标、分层和执行顺序，避免在正式前端阶段继续围绕 Streamlit 反复摇摆。

## 1. M5 的核心判断

M4 已经证明：

- `core + CLI` 已经能跑通主要业务能力
- `Streamlit` 适合验证流程，但不适合作为正式工作台
- 真正的问题不在状态机和 Provider，而在 UI 框架的交互上限

因此，M5 的目标不是继续“修 Streamlit”，而是：

1. 保留现有 Python 核心层
2. 补一层薄 API
3. 启动正式 Web 前端

## 2. 目标分层

```text
web (正式前端)
  ↓
api (薄接口层)
  ↓
core (pipeline / storage / settings / providers / state machine)
```

### 2.1 core

继续复用已有代码：

- `/Users/daidai/Documents/ai-icon-pipeline/src/ai_icon_pipeline/pipeline.py`
- `/Users/daidai/Documents/ai-icon-pipeline/src/ai_icon_pipeline/storage.py`
- `/Users/daidai/Documents/ai-icon-pipeline/src/ai_icon_pipeline/settings.py`
- `/Users/daidai/Documents/ai-icon-pipeline/src/ai_icon_pipeline/providers/`
- `/Users/daidai/Documents/ai-icon-pipeline/src/ai_icon_pipeline/state_machine.py`

约束：

- 不把新的业务规则重新写到前端
- 不把新的业务规则重新写到 API
- API 和 Web 都只调用 core

### 2.2 api

定位：

- 本地单体应用里的薄接口层
- 不是重服务化，不做复杂拆分
- 只负责把 core 能力包装成前端可调用接口

建议第一版技术选型：

- `FastAPI`

第一批接口建议：

- `GET /tasks`
- `POST /tasks`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/items`
- `POST /tasks/{task_id}/items`
- `PATCH /tasks/{task_id}/items/{item_id}`
- `POST /tasks/{task_id}/items/{item_id}/steps/{step}/run`
- `POST /tasks/{task_id}/items/{item_id}/steps/{step}/approve`
- `POST /tasks/{task_id}/items/{item_id}/steps/{step}/rollback`
- `GET /tasks/{task_id}/items/{item_id}/artifacts`
- `POST /tasks/{task_id}/items/{item_id}/artifacts/{step}/{version}/use`
- `GET /providers`
- `POST /providers`
- `PATCH /providers/{provider_id}`
- `POST /providers/{provider_id}/sync-models`
- `GET /tasks/{task_id}/items/{item_id}/image-jobs`
- `POST /tasks/{task_id}/items/{item_id}/image-jobs/poll`
- `POST /tasks/{task_id}/items/{item_id}/image-jobs/cancel`

### 2.3 web

定位：

- 正式工作台
- 给美术 / 策划 / 设计同事用
- 替代 Streamlit 的主要工作流

建议第一版技术选型：

- `React`
- 构建工具可选：
  - `Vite`
  - 或 `Next.js`（如果后面想更完整扩展）

第一版页面结构建议：

- 左侧：
  - 批次列表
  - 新建批次
  - 设置
- 主内容：
  - 批次详情
  - 条目工作台
- 弹窗：
  - 新建批次
  - 设置
  - 新建条目
- 条目工作台：
  - 当前条目摘要
  - 设计说明
  - 出图指令
  - 候选池
  - 版本历史
  - 事件日志

## 3. M5 不做什么

M5 不做：

- 继续把 Streamlit 打磨成正式产品前端
- 新造第二套状态机
- 在前端直接读写任务目录
- 把 provider 逻辑分散到 UI 层
- 一开始就做多人协作 / SaaS 化

## 4. M5 的执行顺序

### M5.1 API 骨架

目标：

- 把现有 core 暴露成可调用接口
- 先跑通批次 / 条目 / step / image job / provider

### M5.2 Web 骨架

目标：

- 跑起正式前端
- 做出基本导航与工作台骨架
- 接最少但完整的一条主流程

### M5.3 Streamlit 降级

目标：

- 保留 Streamlit 作为内部验证台
- 但不再继续重投入其产品交互

### M5.4 包装与交付方向

目标：

- 评估最终给同事的使用形态：
  - 本地 Web App
  - 本地桌面壳（如 Tauri/Electron）

第一阶段建议：

- 先做“本地启动一个服务 + 自动打开浏览器”的形态

## 5. 验收标准

M5 结束时，至少应满足：

1. 正式前端可以浏览批次和条目
2. 正式前端可以执行核心流程动作
3. 正式前端可以查看候选池和异步生成状态
4. 设置页可以管理 provider
5. Streamlit 不再是主入口
6. core 与 CLI 不因 UI 迁移被推翻
