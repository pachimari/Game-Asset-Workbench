# Game Asset Workbench

[English README](./README_en.md)

一个以 **local-first** 为核心的游戏资产生产工作台，支持批次生成、人工审图、候选星标、最终确认与 ZIP 导出。

这个项目把三件事放在了一起：

- **React Web 工作台**：负责看图、筛图、星标、确认
- **Python API + Core Pipeline**：负责编排、状态流转、存储、Provider 适配
- **CLI**：负责批量操作、自动化、Agent 驱动和查询

它的定位不是“纯自动生成一切”，而是一个支持 **Agent 协作** 和 **人工手动接管** 的混合工作流：

- **Agent / CLI 和 Web UI 都可以驱动主要工作流**
- 更推荐用 **Agent / CLI** 来推进流程、配置 Provider、批量操作和查询状态
- 更推荐在 **Web UI** 里做视觉判断、候选对比、星标筛选和最终确认
- 两端不是硬切开的，而是可以来回切换、互相接力

## 这是什么

Game Asset Workbench 用来把一批游戏资产需求，跑过一条完整的生产流程：

1. 创建批次，设置统一背景和风格要求
2. 手动新增条目，或从 CSV / 表格批量导入
3. 为每个条目生成：
   - 设计说明
   - 出图指令
   - 候选图
4. 在 Web UI 中查看候选图
5. 星标你觉得好的结果
6. 确认当前采用图
7. 导出整批星标图为 ZIP

这个项目最重要的几个关键词是：

- **local-first**
- **human-in-the-loop**
- **batch-oriented**
- **multi-provider**
- **CLI + Web**

## 生产模式

当前稳定工作流是 **单图模式**：每个 item 独立生成候选图，再在 Web UI 中筛选、星标、确认。

项目也支持第二种 **批次级网格切图模式**：一个批次一次生成网格 sheet，切分成 tiles 后回填到各个 item 的候选池。这个模式用于道具、技能、材料、宝箱等大量同风格小资产，不用于替代原画、角色等单张精修流程。

设计细节、决策记录和更新记录见：

- [docs/grid-sheet-mode-design.md](./docs/grid-sheet-mode-design.md)
- [docs/grid-sheet-mode-prd.md](./docs/grid-sheet-mode-prd.md)

## 产品形态

### Web UI 更适合什么

Web 工作台最适合做这些事：

- 浏览批次
- 查看条目状态
- 对比候选图
- 星标多张好图
- 选择当前候选 / 当前采用
- 导出星标结果

简单说：
**Web UI 最适合做需要看图和手动接管的部分。**

### CLI / Agent 更适合什么

CLI 最适合做这些事：

- 创建和更新批次
- 创建条目
- 跑 pipeline
- 查看批次指标
- 解析某一步实际生效的 provider / model
- 管理 provider
- 导出结果

Agent / CLI 最适合做这些事：

- 配置 provider
- 批量推进 task / item
- 查询状态和指标
- 导出结果
- 自动化重复操作

简单说：
**CLI / Agent 更适合做自动化、批量控制和协作推进。**

但这不是硬限制：

- 你可以让 Agent 推进流程，再回 Web UI 审图
- 也可以主要用 Web UI 手动操作，再用 CLI 做查询或导出
- 这个项目支持两端共同驱动同一条工作流

## 给 Agent 的入口

如果是 agent 第一次接手这个仓库，推荐按这个顺序读取：

1. [AGENTS.md](./AGENTS.md)
2. [skills/SKILL.md](./skills/SKILL.md)
3. 再按任务类型进入具体子 skill：
   - [skills/provider-manager/SKILL.md](./skills/provider-manager/SKILL.md)
   - [skills/batch-operator/SKILL.md](./skills/batch-operator/SKILL.md)
   - [skills/item-workflow/SKILL.md](./skills/item-workflow/SKILL.md)
   - [skills/candidate-curator/SKILL.md](./skills/candidate-curator/SKILL.md)

推荐心智是：

- `AGENTS.md` 负责讲仓库结构、关键文件和验证方式
- `skills/SKILL.md` 负责做项目级路由
- 子 skill 负责具体工作流

如果任务涉及视觉判断，agent 不应该假装终端足够，而应根据 skill 约定把用户导回 Web UI。

## 安装与本地运行

### Python 依赖

Python 侧正式依赖定义在 [pyproject.toml](./pyproject.toml)。

为了让第一次上手更直接，这个仓库也提供了一个简洁入口：

- [requirements.txt](./requirements.txt)

推荐先运行：

```bash
python3 -m pip install -r requirements.txt
```

如果你更习惯 editable 安装，也可以：

```bash
python3 -m pip install -e .[api]
```

### 前端依赖

前端依赖在 `web/` 目录里，第一次运行前需要：

```bash
(cd web && npm install)
```

### 最快方式

macOS：

- 双击 `start_local.command`
- 用 `stop_local.command` 停止

Windows：

- 双击 `start_local.bat`
- 用 `stop_local.bat` 停止

### 手动方式

后端：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.api_launcher --reload
```

前端：

```bash
(cd web && npm install && npm run dev -- --host 127.0.0.1)
```

打开：

- Web：`http://127.0.0.1:5173/`
- API 健康检查：`http://127.0.0.1:8000/health`

## 简单共享部署

默认配置是本地优先，只允许本机访问。

如果你想把它放到公司内网里，给小团队共用，可以开远程访问并加一个共享 token：

```bash
export AI_ICON_PIPELINE_API_ALLOW_REMOTE=1
export AI_ICON_PIPELINE_API_TOKEN="replace-with-a-shared-token"
export AI_ICON_PIPELINE_API_ALLOWED_ORIGINS="https://your-internal-ui.example.com"
PYTHONPATH=src python3 -m ai_icon_pipeline.api_launcher --host 0.0.0.0 --port 8000
```

当前边界很明确：

- 适合 **本地使用**
- 也支持 **简单的内网共享部署**
- **不是**完整的多用户 SaaS

## 推荐工作流

一条最顺手的用法通常是：

1. 新建批次
2. 设置批次级的项目背景和统一风格要求
3. 新增条目，或导入 CSV / 表格
4. 用 Agent / CLI 推进设计说明、出图指令、候选图生成
5. 在 Web UI 的候选池里筛图
6. 星标你觉得好的图
7. 确认当前候选
8. 导出整批星标图

如果你更喜欢手动操作，也可以直接在 Web UI 里逐步推进，而不是强制走 CLI。

## CLI 快速开始

如果你已经按上面的方式安装过 `requirements.txt`，下面这些命令就可以直接用了。

先看一眼命令入口：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli --help
```

### 创建一个批次

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli task create \
  --task-name "三国奇幻首批资产" \
  --project-background "三国奇幻，强调武将与雷电元素" \
  --style-requirements "高对比、单主体、避免文字"
```

### 新增一个条目

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli item create task_001 \
  --asset-type "skill_icon" \
  --title "雷暴" \
  --description "对敌人造成雷电伤害并附带麻痹效果" \
  --category "combat"
```

### 跑完整流程

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli pipeline run task_001
```

如果你想每一步都停下来人工确认：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli pipeline run task_001 --no-auto-approve
PYTHONPATH=src python3 -m ai_icon_pipeline.cli step approve task_001 item_001 brief_generation
PYTHONPATH=src python3 -m ai_icon_pipeline.cli step run task_001 item_001 image_prompt
```

### 查看批次指标

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli task metrics task_001 --json
```

### 查看某一步实际用了哪个模型

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli runtime resolve task_001 item_001 --step image_generation --json
```

### 查看和导出星标图

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli image starred task_001 --json
PYTHONPATH=src python3 -m ai_icon_pipeline.cli export starred task_001 --json
```

### 网格切图批次

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli task update task_001 \
  --image-generation-mode grid_sheet \
  --grid-rows 8 \
  --grid-cols 8

PYTHONPATH=src python3 -m ai_icon_pipeline.cli sheet plan task_001 --json
PYTHONPATH=src python3 -m ai_icon_pipeline.cli sheet generate task_001 sheet_v001 --json
PYTHONPATH=src python3 -m ai_icon_pipeline.cli sheet poll task_001 sheet_v001 --json
PYTHONPATH=src python3 -m ai_icon_pipeline.cli sheet split task_001 sheet_v001 --json
PYTHONPATH=src python3 -m ai_icon_pipeline.cli sheet backfill task_001 sheet_v001 --json
```

规划 sheet 时，系统会先为缺失 brief 的既定 item 自动生成意图识别；容量内剩余格子会作为涌现槽写入整张 sheet 的 `slot_lines`。

切图后应先回到 Web UI 做 Sheet Review：用系统真实切分线检查每个 tile，只把人工采纳的 tile 写入 item 候选池。被采纳的 tile 会自动成为对应 item 的星标候选图；废弃或待定 tile 不会污染候选池。

## Provider 支持

当前支持三类协议：

- `openai_compatible`
- `async_image`
- `gemini_native`

这很重要，因为现实里的第三方 Provider 并不总是完全标准：

- 有些是 OpenAI 兼容
- 有些是异步任务型出图
- 有些更接近 Gemini 原生接口

这个项目做的事情，就是把它们适配进同一套 pipeline 里。

目前开发过程中已经实际验证过这三类协议接入路径：

- OpenAI-compatible image/text provider
- async image provider
- Gemini-native provider

## CSV / TSV 导入

批次页支持：

- CSV 导入
- TSV 导入
- 直接粘贴表格内容

UI 里也提供了可下载的 CSV 模板。

这里顺手解释一下：

- **CSV** = 逗号分隔
- **TSV** = Tab 分隔

通常从 Excel / 飞书表格复制出来时，TSV 会更自然一些。

## 示例输入

你可以直接从这个例子开始：

- [examples/batch.example.json](./examples/batch.example.json)

例如：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli task create --input-file examples/batch.example.json
```

## 仓库结构

```text
src/ai_icon_pipeline   Python core、API、CLI、provider 适配、存储、状态机
web/                   React 工作台
tests/                 关键回归测试
examples/              最小示例输入
tasks/                 本地运行时任务数据（git 忽略）
```

## 当前边界

这个项目现在的定位，是一个实用的游戏资产生产工作台，而不是一个泛化 SaaS 平台。

它现在比较强的地方是：

- 本地优先的批量编排
- 人类参与的视觉筛选
- 多 provider 切换和运行时解析
- 星标候选与 ZIP 导出
- 适合 Agent 驱动的 CLI

它当前**不试图**解决这些问题：

- 多租户 SaaS
- 完整用户与权限系统
- 纯文本替代视觉审图

也就是说：

- **Agent / CLI** 负责自动化和编排
- **Web UI** 负责看图和做最终判断

## 本地验证

常用验证命令：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=src python3 -m compileall src
cd web && npm run lint
cd web && npm run build
```
