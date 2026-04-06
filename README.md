# AI 游戏图标资产生成流水线

本项目的目标是做一个**本地可跑通、可演示、可迭代**的 Demo：输入一批游戏内图标资产需求，经过多阶段 AI 处理和人工审核，最终产出可用的图标，并保留全过程记录。

详细设计见 [PRD.md](./PRD.md)。README 只保留项目概览和执行方向。
M5 的正式前端迁移基线见 [M5_WEB_FOUNDATION.md](./M5_WEB_FOUNDATION.md)。
M6 的产品化收口计划见 [M6_PRODUCTIZATION_PLAN.md](./M6_PRODUCTIZATION_PLAN.md)。

如果后续要把本项目作为外部 AI Agent 的正式工具接口，见 [CLI_INTERFACE.md](./CLI_INTERFACE.md)。
当前 CLI 同时支持：
- 旧的平铺命令，例如 `create-task`、`show-item`、`run-step`
- 新的分组命令，例如 `task create`、`item show`、`step run`

## 项目目标

- 跑通一条完整 SOP：批量任务输入 -> 需求整理 -> 出图指令生成 -> 图片生成 -> 人工审核 -> 落盘/导出
- 强调 Human-in-the-Loop，而不是一开始追求全自动
- 支持演示、复盘、回放和后续 Prompt 迭代

## 当前技术路线

- **编排层**：Python 本地编排代码
- **界面层**：React + TypeScript + Vite（当前正式工作台）
- **验证台**：Streamlit（保留为内部验证入口）
- **文本 Agent**：需求整理 Agent、出图指令生成 Agent
- **聊天意图路由**：Claude Code CLI（可选，用于自然语言转结构化 action）
- **图像生成**：Gemini Image API
- **存储**：本地文件系统

当前统一以 **Gemini Image API** 为图像生成后端，不再以 Stable Diffusion 作为主线方案。

当前正式主线已经切到 **Python core + FastAPI + React Web 工作台**。Streamlit 继续保留为内部验证台，而不是最终产品前端。

## 快速开始

开发阶段推荐直接运行：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline --help
```

如果你想把它安装成命令：

```bash
python3 -m pip install -e .
```

如果你要启动 M3 工作台，安装 UI 依赖：

```bash
python3 -m pip install "streamlit>=1.36"
```

启动 Streamlit 工作台：

```bash
python3 -m streamlit run src/ai_icon_pipeline/ui.py
```

如果你要启动 M5 的本地 API 骨架，安装 API 依赖：

```bash
python3 -m pip install "fastapi>=0.115" "uvicorn>=0.30"
```

启动本地 API：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.api_launcher --reload
```

启动 M5 正式前端：

```bash
cd web
npm install
npm run dev
```

默认开发地址：

- 前端：`http://127.0.0.1:4173`
- 本地 API：`http://127.0.0.1:8000`

先创建一个空批次：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline create-task \
  --task-name "三国奇幻首批图标" \
  --project-background "三国奇幻，强调武将与雷电元素" \
  --style-requirements "高对比、单主体、避免文字"
```

再在批次里新增一个条目：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline create-item task_001 \
  --asset-type "skill_icon" \
  --title "雷暴" \
  --description "对敌人造成雷电伤害并附带麻痹效果" \
  --category "combat"
```

查看任务：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline show-task task_001
```

直接跑完整个 task 的 mock 流水线：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline run-pipeline task_001
```

查看某个 item：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline show-item task_001 item_001
```

如果你想停在每个生成节点做人工检查：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline run-pipeline task_001 --no-auto-approve
PYTHONPATH=src python3 -m ai_icon_pipeline approve-step task_001 item_001 brief_generation
PYTHONPATH=src python3 -m ai_icon_pipeline run-step task_001 item_001 image_prompt
```

M2 常用命令：

```bash
# 列出 task 下的所有 item
PYTHONPATH=src python3 -m ai_icon_pipeline list-items task_001

# 查看某一步的历史版本
PYTHONPATH=src python3 -m ai_icon_pipeline list-artifacts task_001 item_001 brief_generation

# 查看某个具体版本
PYTHONPATH=src python3 -m ai_icon_pipeline show-artifact task_001 item_001 image_prompt v001

# 手动修改 brief
PYTHONPATH=src python3 -m ai_icon_pipeline edit-brief task_001 item_001 \
  --description "对敌人造成高压雷电伤害并附带短暂麻痹效果" \
  --keywords "thunder,stun,burst" \
  --visual-focus "闪电束与爆裂电弧"

# 手动修改 prompt
PYTHONPATH=src python3 -m ai_icon_pipeline edit-prompt task_001 item_001 \
  --prompt "game icon asset, 雷暴, centered lightning arc, blue-white energy burst"

# 切换当前采用版本
PYTHONPATH=src python3 -m ai_icon_pipeline set-current-version task_001 item_001 image_generation v001

# 回退到上一个阶段继续迭代
PYTHONPATH=src python3 -m ai_icon_pipeline rollback-step task_001 item_001 image_prompt
```

也可以直接从 JSON 文件创建批次并附带条目：

```json
{
  "task_name": "三国奇幻首批图标",
  "project_background": "三国奇幻",
  "style_requirements": "高对比、单主体、避免文字",
  "asset_domain": "game_icon_assets",
  "items": [
    {
      "asset_type": "skill_icon",
      "title": "雷暴",
      "description": "对敌人造成雷电伤害并附带麻痹效果",
      "category": "combat"
    },
    {
      "asset_type": "buff_icon",
      "title": "灼烧",
      "description": "持续造成火焰伤害",
      "category": "status"
    }
  ]
}
```

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline create-task --input-file batch.json
```

## 核心流程

```text
输入：批次设定（项目背景 + 统一风格要求）+ 多个图标条目
   ↓
需求整理 Agent
   - 输出：标题、描述、关键词、视觉重点
   ↓
人工审核
   - 通过 / 重跑 / 手动修改
   ↓
出图指令生成 Agent
   - 输出：Gemini 可用的图像 prompt 与约束
   ↓
人工审核
   - 通过 / 重跑 / 手动修改 / 回退
   ↓
图像生成程序
   - 调用 Gemini Image API
   - 生成多个候选图
   ↓
人工审核
   - 通过 / 重跑出图 / 返回修改 prompt
   ↓
输出：审核通过的图标 + 全过程记录
```

## 设计原则

- **CLI First**：先做命令行流水线，跑通核心链路，再做 Streamlit 包装层
- **按钮保底**：所有关键动作都可通过按钮完成
- **聊天增强**：自然语言交互存在，但 MVP 先支持有限 action 集
- **版本可追溯**：每次重跑、手改、审核、回退都要可记录、可回放
- **Prompt 可演进**：不在 README/PRD 中写死最终美术 Prompt，只预留规范接口

## MVP 范围

MVP 重点不是“最聪明的 Agent”，而是“最稳定的闭环”：

- 批任务创建与执行
- item 级需求整理、Prompt 生成、图片生成三阶段
- 每阶段人工审核
- 单步重跑和手动修改
- 本地落盘
- 基础指标记录
- 手动编辑与版本切换

MVP 暂不追求：

- 复杂图像编辑
- SaaS 化部署
- 多人协作
- 全自动 Meta-Agent 调优

## 聊天能力定位

聊天是本项目里更重、也更有实验价值的形态，但不是唯一入口。

MVP 先支持有限结构化 action，例如：

- `rerun_brief_generation`
- `rerun_prompt`
- `rerun_image`
- `edit_brief`
- `edit_prompt`
- `change_color`
- `rollback_step`
- `approve_current_step`

如果聊天意图识别失败，系统应回退到按钮操作，而不是阻断流程。

## 数据落盘思路

每个 task 保存为独立目录，核心是两层：

- `task.json`：批任务快照
- `items/item_xxx/`：每个子任务的状态、产物、日志

典型目录结构：

```text
tasks/task_001/
├── task.json
├── events.jsonl
├── configs/
├── items/
│   ├── item_001/
│   │   ├── item.json
│   │   ├── metrics.json
│   │   ├── events.jsonl
│   │   ├── artifacts/
│   │   └── images/
│   └── item_002/
└── exports/
```

## 推荐执行顺序

1. 先补齐任务 schema、状态机、action schema
2. 实现 CLI 核心流水线
3. 加入版本化、审核和回退
4. 再做 Streamlit 工作台
5. 最后叠加受控聊天和展示能力

## 当前架构判断

- **Streamlit 保留**：继续作为本地验证工作台使用，帮助快速验证流程、模型、Provider、Agent 行为
- **核心层优先**：`pipeline / storage / settings / providers` 持续作为长期保留的核心能力
- **UI 不再重投入**：除必要可用性修正外，不再把 Streamlit 继续打磨成最终产品前端
- **后续迁移方向**：当 M4 完成后，再补一层轻 API，并迁移到更适合产品化交互的 Web 前端

这意味着：当前阶段继续推进 M4 不会白做，后续换前端时也不会推翻已有 Provider、模型继承、任务版本化与流水线逻辑。

## M3 工作台

M3 提供了一个基于 Streamlit 的本地工作台，核心能力包括：

- 批任务列表与恢复
- item 详情查看
- 当前 brief / prompt / image 结果预览
- 版本历史查看与切换
- 手动编辑 brief / prompt
- 回退到 brief 或 prompt 阶段
- 任务创建表单

## 里程碑

- **M0**：设计定版
- **M1**：CLI 核心流水线
- **M2**：版本化与审核能力
- **M3**：Streamlit 工作台
- **M4A**：Provider / 模型 / 设置系统
- **M4B**：真实生成链路接入
- **M4C**：受控聊天 Agent
- **M5**：前后端衔接与正式前端基础盘
- **M6**：正式前端产品化与交付形态

每个里程碑都应保持可演示、可回退。

### M4 说明

M4 不再被视为“只做聊天 Agent”的阶段，而是拆成三块连续能力：

- **M4A：Provider / 模型 / 设置系统**
  - 全局设置弹窗
  - 页面填写 API Key，本地保存
  - Gemini / DeepSeek 模型列表从 API 拉取
  - 支持全局默认、批次覆盖、条目阶段覆盖
- **M4B：真实生成链路接入**
  - Gemini：需求整理 / 出图指令 / 候选图
  - DeepSeek：需求整理 / 出图指令
  - artifact 记录 provider、model、请求配置
- **M4C：受控聊天 Agent**
  - 自然语言转结构化 action
  - 解析失败可回退按钮
  - 先做有限 action 集，不做自由开放式代理

### M5 说明

当 M4 的核心能力稳定后，M5 不再继续重投入 Streamlit，而是开始正式前后端分层：

- 保留现有 Python 核心层
- 新增轻量 API 层（例如 FastAPI）
- 将 Streamlit 逐步替换为真正的 Web 前端
- 避免把业务逻辑继续堆在 UI 壳里，控制技术债

M5 的目标不是一次性做完最终产品，而是先把这几层打稳：

- `core`：继续复用现有 `pipeline / storage / settings / providers`
- `api`：补一个给正式 UI 调用的薄接口层
- `web`：开始搭正式工作台骨架，替代 Streamlit 的核心工作流

### M6 说明

当 M5 的 API 与正式前端基础盘稳定后，再进入 M6：

- 打磨产品级交互与视觉设计
- 完善批次/条目工作台
- 优化异步生成、候选池、设置与弹窗体验
- 评估本地桌面壳或本地 Web App 的交付方式
