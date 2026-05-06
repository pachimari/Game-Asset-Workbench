# Grid Sheet Mode Design

本文档描述新增“批次级切图 / 网格图”生产模式的设计边界。

## Document Status

- Status: design draft
- Owner: project maintainers / agents working on grid sheet mode
- Last updated: 2026-05-06
- Scope: product model, storage shape, API/CLI/UI sketch, implementation sequence

相关入口：

- [README.md](../README.md)
- [README_en.md](../README_en.md)
- [AGENTS.md](../AGENTS.md)

它的目标不是替换现有单图流程，而是在同一个工作台中支持两类资产生产方式：

- `single`: 现有逐条 item 出图流程，适合原画、角色、大物件、需要单张精修的资产。
- `grid_sheet`: 批次级网格大图流程，适合道具、技能、宝箱、材料、图标等大量同风格小资产。

第一版明确采用 **批次级模式**：一个 task 只能选择一种出图模式，不允许同一批次里混用 `single` 和 `grid_sheet`。

## Why Batch-Level

网格图会改变产品心智：

- 一次 provider 调用生成的是一张 sheet，而不是某个 item 的一张候选图。
- sheet 需要切分、校准、回填到多个 item。
- 人工审图也会先看整张 sheet，再看每个 tile。

如果允许同一批次内 item 级混用，用户很容易分不清：

- 当前按钮是在给一个 item 出图，还是在给整个批次出 sheet。
- 某张候选图是直接生成的，还是从 sheet 切出来的。
- 星标和采用到底作用在 version、candidate、tile 还是 item 上。

因此第一版只做批次级模式，保持工作流清晰。

## Product Model

### Single Mode

现有流程保持不变：

```text
task
  item
    brief_generation
    image_prompt
    image_generation
    candidate_pool
    starred
    approved
```

核心心智：

```text
一个 item 多次生成候选图，人从候选池里挑一张采用。
```

### Grid Sheet Mode

新增批次级流程：

```text
task
  items
  sheet_generation
  sheet_review
  tile_split
  item_candidate_backfill
  item_review
```

核心心智：

```text
一个 task 先把多个 item 打包成 sheet slots，一次生成网格大图。
确认切分后，每个 tile 回填成对应 item 的候选图。
最终采用仍然回到 item 维度。
```

## Runtime Config

建议扩展 `configs/runtime_config.json`：

```json
{
  "image_generation_mode": "single",
  "image_aspect_ratio": "1:1",
  "image_resolution": "1K",
  "grid_rows": 8,
  "grid_cols": 8,
  "grid_padding": 0,
  "grid_gap": 0,
  "grid_cell_count": 64
}
```

字段说明：

- `image_generation_mode`: `single` 或 `grid_sheet`。
- `grid_rows`: sheet 行数，第一版建议 1-12。
- `grid_cols`: sheet 列数，第一版建议 1-12。
- `grid_padding`: sheet 外边距像素，用于切图校准。
- `grid_gap`: 格子间距像素，用于切图校准。
- `grid_cell_count`: 派生值，等于 `grid_rows * grid_cols`，用于 UI 展示和 packer 规划。

第一版可以只支持矩形等分切图。后续再支持非等距网格、自动检测分隔线、手动拖拽切线。

## Storage Layout

建议新增 task 级目录：

```text
tasks/task_001/
  sheets/
    sheet_v001/
      sheet.json
      source.png
      tiles/
        r01c01.png
        r01c02.png
        ...
```

`sheet.json` 示例：

```json
{
  "sheet_id": "sheet_v001",
  "status": "generated",
  "provider": "custom_apimart",
  "model": "gpt-image-2",
  "created_at": "2026-05-06T12:00:00+00:00",
  "input": {
    "rows": 8,
    "cols": 8,
    "item_ids": ["item_001", "item_002"],
    "prompt_version": "sheet_prompt_v001",
    "image_aspect_ratio": "1:1",
    "image_resolution": "2K"
  },
  "source_image_path": "source.png",
  "split_config": {
    "rows": 8,
    "cols": 8,
    "padding": 0,
    "gap": 0
  },
  "slots": [
    {
      "cell_id": "r01c01",
      "row": 1,
      "col": 1,
      "item_id": "item_001",
      "title": "Healing Potion"
    }
  ],
  "tiles": [
    {
      "cell_id": "r01c01",
      "item_id": "item_001",
      "image_path": "tiles/r01c01.png",
      "status": "split"
    }
  ]
}
```

## Item Candidate Backfill

切图完成后，tile 应该进入原有 item 候选池。

建议先复用现有 `image_generation` artifact，但在 candidate 上增加来源字段：

```json
{
  "candidate_id": "sheet_v001_r01c01",
  "image_path": "sheet_v001_r01c01.png",
  "source": "grid_sheet",
  "sheet_id": "sheet_v001",
  "cell_id": "r01c01",
  "row": 1,
  "col": 1
}
```

这样 Web 的 item 工作台可以继续展示候选池，同时让用户知道这张图来自某个 sheet。

第一版避免改动星标模型太深：仍然按 image generation version 选择当前候选。后续如果要在一个 version 下支持多个 tile 精准星标，再升级为 candidate-level reference。

## Prompt Strategy

`grid_sheet` 不能复用单 item prompt。

需要新增 sheet prompt 生成逻辑，输入是一组 slots：

```json
{
  "grid": {
    "rows": 8,
    "cols": 8,
    "order": "row_major"
  },
  "style_requirements": "...",
  "slots": [
    {
      "cell": "r01c01",
      "title": "Healing Potion",
      "description": "red potion bottle with golden cork"
    }
  ]
}
```

Prompt 约束重点：

- 生成一张完整网格 sheet。
- 按 row-major 顺序放置每个资产。
- 每个格子只包含一个独立主体。
- 格子之间要有清晰留白或分隔，便于切分。
- 禁止文字、编号、水印。
- 统一风格、材质、光照和背景。
- 不要让主体跨格。

## State Flow

建议新增 task 级 sheet 状态，不要塞进 item 状态机：

```text
sheet_draft
sheet_prompt_generated
sheet_prompt_approved
sheet_generating
sheet_generated
sheet_split_pending
sheet_split
sheet_backfilled
```

item 自身状态在 backfill 之后可以进入：

```text
image_generated
```

这样 item 工作台仍然只负责“看候选、星标、采用”，不承担 sheet 生成状态。

## API Sketch

建议新增 task 级 API：

```text
GET  /tasks/{task_id}/sheets
POST /tasks/{task_id}/sheets/plan
POST /tasks/{task_id}/sheets/{sheet_id}/generate
POST /tasks/{task_id}/sheets/{sheet_id}/poll
POST /tasks/{task_id}/sheets/{sheet_id}/split
POST /tasks/{task_id}/sheets/{sheet_id}/backfill
```

其中：

- `plan`: 根据 rows/cols 和 item 列表生成 sheet slots。
- `generate`: 调 provider 出整张 sheet。
- `split`: 按 split config 切图。
- `backfill`: 把 tiles 写入对应 item 候选池。

## CLI Sketch

建议新增 `sheet` 分组：

```text
sheet plan task_001
sheet generate task_001 sheet_v001
sheet poll task_001 sheet_v001
sheet split task_001 sheet_v001 --rows 8 --cols 8 --padding 0 --gap 0
sheet backfill task_001 sheet_v001
sheet list task_001
sheet show task_001 sheet_v001
```

CLI 只负责流程推进和状态查询。视觉判断仍然回到 Web UI。

## Web UI Sketch

批次页新增模式设置：

```text
出图模式: 单图模式 / 网格切图模式
行数
列数
padding
gap
```

`grid_sheet` 模式下，批次页新增 sheet 工作区：

- Sheet 列表
- 当前 sheet 原图预览
- 网格 overlay
- 切图参数调整
- tile 预览
- 回填到 item 候选池

item 工作台只增加来源展示：

```text
来源: sheet_v001 r03c07
```

## First Implementation Slice

建议按以下顺序做：

1. **Runtime config only**
   增加 `image_generation_mode`、`grid_rows`、`grid_cols`、`grid_padding`、`grid_gap`。

2. **Storage primitives**
   新增 `sheets/` 目录、`sheet.json` 读写、sheet list/show。

3. **Pure split**
   不接 provider，先支持上传或指定已有 `source.png`，按 rows/cols 切出 tiles。

4. **Backfill**
   把 tiles 写入 item 的候选池，Web item 工作台能看到。

5. **Provider generation**
   用 `async_image` / APIMart 生成整张 sheet。

6. **Prompt generation**
   新增 sheet prompt 模板与 packer。

7. **Web sheet review**
   做整张图预览、overlay、切图参数调整和 backfill 操作。

## Non-Goals For V1

第一版不做：

- 同一 task 内混用 `single` 和 `grid_sheet`。
- 自动视觉识别每个格子的边界。
- 自动判断 tile 质量。
- candidate-level 星标重构。
- 多 sheet 跨批次复用。
- 图生图参考图融合。

这些可以等基础流程跑通后再加。

## Decision Log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-05-06 | `grid_sheet` 第一版是批次级模式，不做 item 级混用。 | 混用会让生成入口、候选来源、星标/采用语义变得混乱。 |
| 2026-05-06 | 保留现有 `single` 流程，不用 `grid_sheet` 替代。 | 原画、角色、大图仍需要逐 item 精修。 |
| 2026-05-06 | tile 切分后回填到 item 候选池，最终采用仍回到 item 维度。 | Web UI 的人工审图和最终确认心智可以复用。 |
| 2026-05-06 | 第一版不重构 candidate-level 星标。 | 避免把数据模型升级和 sheet MVP 绑在一起，降低首版风险。 |

## Update Log

| Date | Change |
| --- | --- |
| 2026-05-06 | 新增 grid sheet mode 设计草案。 |
| 2026-05-06 | 在 README、README_en、AGENTS 中加入 grid sheet 文档入口和维护提醒。 |
| 2026-05-06 | 实施第一片 runtime config：批次级 `image_generation_mode` 与网格切图参数可保存和展示。 |

## Open Questions

需要实现前确认：

1. `grid_sheet` 的默认尺寸是 8x8，还是 6x6 更适合首版？
2. 超过一个 sheet 容量时，是自动生成多个 sheet，还是先只处理前 N 个 item？
3. sheet prompt 是否复用已有 item brief，还是直接从 item 原始输入生成 slots？
4. backfill 后是否自动把每个 item 的当前候选设为对应 tile？
5. 切分结果是否复制进 item `images/`，还是只在 candidate 中引用 sheet tile 路径？
