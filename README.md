# AI 游戏图标资产生成流水线

本项目的目标是做一个**本地可跑通、可演示、可迭代**的 Demo：输入一批游戏内图标资产需求，经过多阶段 AI 处理和人工审核，最终产出可用的图标，并保留全过程记录。

详细设计见 [PRD.md](./PRD.md)。README 只保留项目概览和执行方向。

## 项目目标

- 跑通一条完整 SOP：批量任务输入 -> 需求整理 -> 出图指令生成 -> 图片生成 -> 人工审核 -> 落盘/导出
- 强调 Human-in-the-Loop，而不是一开始追求全自动
- 支持演示、复盘、回放和后续 Prompt 迭代

## 当前技术路线

- **编排层**：Python 本地编排代码
- **界面层**：Streamlit
- **文本 Agent**：需求整理 Agent、出图指令生成 Agent
- **聊天意图路由**：Claude Code CLI（可选，用于自然语言转结构化 action）
- **图像生成**：Gemini Image API
- **存储**：本地文件系统

当前统一以 **Gemini Image API** 为图像生成后端，不再以 Stable Diffusion 作为主线方案。

## 快速开始

开发阶段推荐直接运行：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline --help
```

如果你想把它安装成命令：

```bash
python3 -m pip install -e .
```

创建一个单 item 批任务：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline create-task \
  --task-name "三国奇幻首批图标" \
  --project-context "三国奇幻" \
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

也可以直接从 JSON 文件批量创建：

```json
{
  "task_name": "三国奇幻首批图标",
  "project_context": "三国奇幻",
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
输入：批量任务上下文 + 多个图标 item
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

## 里程碑

- **M0**：设计定版
- **M1**：CLI 核心流水线
- **M2**：版本化与审核能力
- **M3**：Streamlit 工作台
- **M4**：受控聊天 Agent
- **M5**：Demo 打磨与展示

每个里程碑都应保持可演示、可回退。
