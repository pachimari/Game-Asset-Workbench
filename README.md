# AI Icon Pipeline

[English README](./README_en.md)

一个以 **local-first** 为核心的 AI 图标生产工作台，支持批次生成、人工审图、候选星标、最终确认与 ZIP 导出。

这个项目把三件事放在了一起：

- **React Web 工作台**：负责看图、筛图、星标、确认
- **Python API + Core Pipeline**：负责编排、状态流转、存储、Provider 适配
- **CLI**：负责批量操作、自动化、Agent 驱动和查询

它的定位不是“纯自动生成一切”，而是一个混合工作流：

- **Agent / CLI** 负责驱动任务、配置 Provider、推进流程
- **人类** 在 Web 里做视觉判断、筛选候选图、确认最终采用

## 这是什么

AI Icon Pipeline 用来把一批游戏图标需求，跑过一条完整的生产流程：

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

## 产品形态

### Web UI 负责什么

Web 工作台最适合做这些事：

- 浏览批次
- 查看条目状态
- 对比候选图
- 星标多张好图
- 选择当前候选 / 当前采用
- 导出星标结果

简单说：
**Web UI 负责视觉判断。**

### CLI 负责什么

CLI 最适合做这些事：

- 创建和更新批次
- 创建条目
- 跑 pipeline
- 查看批次指标
- 解析某一步实际生效的 provider / model
- 管理 provider
- 导出结果

简单说：
**CLI 负责自动化、批量控制和 Agent 编排。**

## 本地运行

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
cd /path/to/ai-icon-pipeline
PYTHONPATH=src python3 -m ai_icon_pipeline.api_launcher --reload
```

前端：

```bash
cd /path/to/ai-icon-pipeline/web
npm install
npm run dev -- --host 127.0.0.1
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

## Web 工作流

典型使用方式：

1. 新建批次
2. 设置批次级的项目背景和统一风格要求
3. 新增条目，或导入 CSV / 表格
4. 跑设计说明、出图指令、候选图生成
5. 在候选池里筛图
6. 星标你觉得好的图
7. 确认当前候选
8. 导出整批星标图

## CLI 快速开始

如果你想安装成命令：

```bash
cd /path/to/ai-icon-pipeline
python3 -m pip install -e .
```

也可以直接运行：

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli --help
```

### 创建一个批次

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli task create \
  --task-name "三国奇幻首批图标" \
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

这个项目现在的定位，是一个实用的图标生产工作台，而不是一个泛化 SaaS 平台。

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
