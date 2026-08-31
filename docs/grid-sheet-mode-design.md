# Grid Sheet Mode Design

本文档描述新增“批次级切图 / 网格图”生产模式的设计边界。

## Document Status

- Status: MVP implemented
- Owner: project maintainers / agents working on grid sheet mode
- Last updated: 2026-05-06
- Scope: product model, storage shape, API/CLI/UI sketch, implementation sequence

相关入口：

- [README.md](../README.md)
- [README_en.md](../README_en.md)
- [AGENTS.md](../AGENTS.md)
- [Grid Sheet Mode PRD](./grid-sheet-mode-prd.md)

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
一个 task 先对既定 item 做 brief / 意图识别，再打包成 bound slots。
容量内剩余格子会补成 emergent slots，一起生成网格大图。
确认切分后，tile 先进入 Sheet Review，不直接污染 item 候选池。
只有人工采纳的 tile 才回填成对应 item 的候选图，并默认星标。
涌现好图先进入批次级涌现池，除非用户明确绑定或创建 item。
最终采用仍然回到 item 维度。
```

关键边界：

- `rows * cols` 是 sheet 容量，不是 item 数量。
- item 只代表用户明确指定的目标资产。
- emergent slot 只是 sheet prompt 的空余槽位，不预创建 item 记录。
- emergent pool 是批次级素材池，用来保存“好但尚未归属”的 tile。

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

第一版只支持矩形网格切图；后续再支持自动检测分隔线和非矩形网格。

当前切图校准策略：

- 默认按整张 source image 做 rows x cols 等分。
- 如果模型画出的格子和系统蓝线不对齐，用户可以拖动外框和中间每条 x/y 切线，再按当前切线重切。
- `split_config` 需要保存 crop box、source image size、x/y line positions，保证同一次审图可复现。
- crop box 由第一条和最后一条 x/y line 派生；中间 line 允许非等距，以处理模型输出的局部偏移。

## Storage Layout

建议新增 task 级目录：

```text
tasks/task_001/
  sheets/
    sheet_v001/
      sheet.json
      images/
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
  "source_image_path": "images/source.png",
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
      "image_path": "images/tiles/r01c01.png",
      "status": "split"
    }
  ]
}
```

## Sheet Review And Candidate Backfill

切图完成后，tile 应该先进入 Sheet Review。Review 是 grid sheet 模式的人工筛选层，不是技术中间态。

tile review 状态：

- `pending`: 待审，默认状态，不进入 item 候选池。
- `selected`: 已采纳，可以回填到目标 item。
- `rejected`: 废弃，不进入 item 候选池。
- `emergent`: 涌现好图，保存到批次级涌现池，后续可绑定已有 item 或创建新 item 并采纳。

采纳规则：

- 绑定槽位：采纳后复制 tile 到对应 item 的 `images/`，写入 `image_generation` artifact，并加入该 item 的 `starred_image_versions`。
- 重新绑定：采纳前可把 tile 绑定到另一个已有 item。
- 涌现槽位：先标记为 `emergent` 并保存到涌现池；命名后可创建新 item，再采纳并星标。

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

## Prompt Strategy

`grid_sheet` 不能复用单 item prompt，但仍然应该复用 brief / 意图识别。

### Single Target Variants

`grid_sheet` 还支持 `single_target_variants` 槽位策略：一个明确 item 占满整张 sheet，所有格子都是该 item 的候选变体，不属于 emergent pool。产品 planner 根据 item brief 生成每格差异维度，并保留同一资产身份、用途、视角和主体类别；差异只用于候选探索，例如轮廓、材质、配色、主题装饰组合和光效强度。

- Agent 不手工逐格命题或改写 variant brief。
- variant brief 必须由产品 planner 生成并保存 provider/model provenance。
- 所有 variant tile 的 `target_item_id` 指向同一个 item，可分别采纳并进入该 item 候选池。
- 参考图属于 sheet run 输入；provider 提交前先上传并以真实 `image_urls` 参数传入，不能只在 prompt 中声称使用参考图。
- 参考图默认只约束资产类型、视角、构图、比例和材质语言，不要求复制参考图中的具体城池。

规划 sheet 时，既定目标 item 必须先生成 brief。sheet prompt 的输入是一组 slots，其中 bound slots 来自明确 item，emergent slots 只来自本轮 sheet 的空余容量：

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
      "kind": "bound",
      "title": "Healing Potion",
      "description": "brief-normalized visual description"
    },
    {
      "cell": "r01c02",
      "kind": "emergent",
      "title": "涌现辅助技能 01",
      "description": "same batch world and style, lightweight defensive or utility skill icon, do not duplicate bound slots"
    }
  ]
}
```

Prompt 约束重点：

- 生成一张完整网格 sheet。
- 按 row-major 顺序放置每个资产。
- bound slot 来自 item brief，不直接使用未理解的 raw item。
- emergent slot 用来补足空余格子，要求同世界观、同风格、但不重复 bound slot 主题；它不是 item，不写入 item 状态机。
- 若明确 item 少于 sheet 容量，`slot_lines` 应由固定目标行 + 多条有差异的涌现方向组成，而不是把空格都写成同一句“自由发挥”。
- 每个格子只包含一个独立主体。
- 格子之间要有清晰留白或分隔，便于切分。
- 不鼓励模型绘制装饰性外框、卡片边框或复杂网格线；真实切线以系统 overlay 为准。
- 禁止文字、编号、水印。
- 统一风格、材质、光照和背景。
- 不要让主体跨格。

模板配置：

- `grid_sheet_prompt_template`: 整张 sheet 的正向模板。
- `grid_sheet_negative_prompt`: 整张 sheet 的负向模板。

模板变量：

- `{{rows}}`
- `{{cols}}`
- `{{cell_count}}`
- `{{project_background}}`
- `{{style_requirements}}`
- `{{slot_lines}}`

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
GET  /tasks/{task_id}/sheets/{sheet_id}
POST /tasks/{task_id}/sheets/plan
POST /tasks/{task_id}/sheets/{sheet_id}/generate
POST /tasks/{task_id}/sheets/{sheet_id}/poll
POST /tasks/{task_id}/sheets/{sheet_id}/split
POST /tasks/{task_id}/sheets/{sheet_id}/backfill
GET  /tasks/{task_id}/emergent-pool
POST /tasks/{task_id}/sheets/{sheet_id}/tiles/{cell_id}/save-emergent
POST /tasks/{task_id}/emergent-pool/{pool_entry_id}/bind
POST /tasks/{task_id}/emergent-pool/{pool_entry_id}/create-item
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
sheet split task_001 sheet_v001
sheet backfill task_001 sheet_v001
sheet list task_001
sheet show task_001 sheet_v001
sheet emergent-list task_001
sheet emergent-bind task_001 pool_001 item_011
sheet emergent-create-item task_001 pool_001 "火球术"
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
- 系统真实切分线 overlay
- 切图参数调整
- tile 预览
- tile 审图：采纳、废弃、重新绑定、创建 item、标记涌现好图
- 涌现池：保存好但未归属的 tile，后续绑定到已有 item 或创建新 item
- 采纳到 item 候选池并默认星标

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

4. **Sheet Review**
   先在 Web UI 里显示真实切分线、tile 预览和审图状态，不默认全量回填。

5. **Provider generation**
   用 `async_image` / APIMart 生成整张 sheet。

6. **Prompt generation**
   新增 sheet prompt 模板与 packer。

7. **Candidate promotion**
   只把人工采纳的 tile 写入 item 候选池，并默认星标。

## Implemented MVP

当前已实现：

- `src/ai_icon_pipeline/sheets.py`
  - `plan_grid_sheet`: 按批次 runtime 配置生成 sheet slots；规划前自动补齐既定 item 的 brief，bound slots 使用 brief，剩余容量补 emergent slots；prompt 使用全局 `grid_sheet_prompt_template`。
  - `submit_grid_sheet_generation`: 通过 `async_image` provider 提交整张 sheet 生成任务。
  - `poll_grid_sheet_generation`: 轮询异步任务，下载整张 source image。
  - `split_grid_sheet`: 按 rows/cols/padding/gap 等分切图。
  - `review_grid_sheet_tile`: 更新 tile 的 pending/selected/rejected/emergent 审图状态。
  - `promote_grid_sheet_tile`: 把单个 tile 复制进目标 item，并写入星标 `image_generation` artifact。
  - `create_item_from_grid_sheet_tile`: 从涌现 tile 创建新 item 并采纳。
  - `backfill_grid_sheet`: 仅批量回填已 `selected` 且尚未 promoted 的 tile。
- API 已提供 sheet list/show/plan/generate/poll/split/backfill，以及 tile review/promote/create-item。
- CLI 已提供 `sheet` 分组和等价 flat commands。
- Web 批次页在 `grid_sheet` 模式下显示 Targets / Sheet Runs / Tile Review 三段式工作区，支持规划、提交、轮询、切图、真实切分线 overlay、tile 审图和采纳入池。
- Item 工作台会展示候选来源，如 `sheet_v001 · r01c01`。

当前不自动调用视觉判断，tile 质量筛选仍然回到 Web UI。

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
| 2026-05-07 | tile 切分后先进入 Sheet Review，不默认全量回填。 | grid sheet 经常出现语义或网格失败，必须先人工筛选，避免污染 item 候选池。 |
| 2026-05-07 | 被采纳的 tile 进入 item 候选池时默认星标。 | 采纳本身就是一次人工视觉判断，应直接成为高优先级候选。 |
| 2026-05-06 | V1 只处理前 `rows * cols` 个明确目标 item，超过容量的明确 item 留待下一张 sheet。 | 先保证一个 sheet 的端到端链路可验收，再做自动多 sheet 编排。 |
| 2026-05-06 | `plan_grid_sheet` 优先读取已生成 brief，没有 brief 时使用 raw item。 | 兼容已有流程，同时允许导入 item 后直接规划 sheet。 |
| 2026-05-07 | `backfill_grid_sheet` 只处理已 `selected` 且未 promoted 的 tile。 | 保留 CLI 批量入口，但语义从“全量回填”改成“采纳选中”。 |
| 2026-05-06 | tile 复制进 item `images/`，不只引用 sheet tile。 | 保持导出、预览和候选池文件访问路径与现有单图流程一致。 |
| 2026-05-07 | grid sheet 规划前自动为既定 item 补齐 brief；空余容量补 emergent slots。 | 网格出图也需要意图识别，但不需要逐 item 生成单图 prompt；涌现内容应该有明确 slot 语义。 |
| 2026-05-08 | 已有候选图但缺少 brief 的 item，grid sheet 规划可补 sidecar brief，不重置 item 状态或候选图。 | 重新跑新 sheet 不应强迫用户回滚旧流程，brief 在这里服务新的 sheet 规划。 |
| 2026-05-08 | 后续产品心智按 Targets / Sheet Runs / Tile Review 三个区组织。 | item 是目标资产桶和最终候选池，sheet run 才承载整张网格生成、切分和审图中间态。 |
| 2026-05-08 | sheet 容量不等于 item 数量；emergent slots 不预创建 item，涌现好图进入批次级涌现池。 | 用户可能只要 10 个明确图标，却用 6x6 生成 36 个槽位；把 26 个空余槽位膨胀成 item 会让产品心智失真。 |
| 2026-05-08 | Sheet Review 需要支持 crop box 调整后等距重切。 | 图像模型经常画出“看起来像网格”的装饰边界，但它不保证和数学裁切线对齐；校准层比只靠 prompt 更可靠。 |
| 2026-05-08 | Sheet Review 支持逐条拖动 x/y 切线，外框也作为可拖动切线保存。 | 只调外框无法修正某一行或某一列的局部偏移；真实切片必须以用户校准后的数学线为准。 |
| 2026-08-12 | 新增 `single_target_variants` 槽位策略；一个 item 可占满整张 sheet 作为多候选变体。 | “同一主题出 16 个版本择优”不是 15 个涌现资产，也不应膨胀成 16 个 item。 |
| 2026-08-12 | Grid Sheet i2i 参考图必须通过 provider 的上传与 `image_urls` 字段真实提交。 | 仅把本地路径或“参考此图”写进文本不构成图生图。 |

## Update Log

| Date | Change |
| --- | --- |
| 2026-05-06 | 新增 grid sheet mode 设计草案。 |
| 2026-05-06 | 在 README、README_en、AGENTS 中加入 grid sheet 文档入口和维护提醒。 |
| 2026-05-06 | 实施第一片 runtime config：批次级 `image_generation_mode` 与网格切图参数可保存和展示。 |
| 2026-05-06 | 实施 grid sheet MVP：storage/API/CLI/Web 接线、专用 sheet prompt、等分切图、tile 回填候选池。 |
| 2026-05-07 | 新增 Sheet Review：真实切分线 overlay、tile 审图状态、单 tile 采纳并星标、从 tile 创建 item。 |
| 2026-05-07 | 将 grid sheet prompt 纳入全局模板页，新增 `grid_sheet_prompt_template` 和 `grid_sheet_negative_prompt`。 |
| 2026-05-07 | grid sheet 规划改为 brief-first，并自动生成 emergent slots 填满 sheet 容量。 |
| 2026-05-08 | grid sheet brief 补齐支持已有候选图 item，不再因 `image_generated` 状态阻断规划。 |
| 2026-05-08 | 新增 [Grid Sheet Mode PRD](./grid-sheet-mode-prd.md)，用于指导下一阶段 UI 心智和验收标准。 |
| 2026-08-12 | 设计补充单目标多变体与 Grid Sheet i2i 参考图输入。 |
| 2026-05-08 | Web grid sheet 工作区改成 Targets / Sheet Runs / Tile Review 三列结构，减少 item 流程和 sheet 流程的心智混淆。 |
| 2026-05-08 | 更新 PRD 和设计记录：固定目标 item 数量与 sheet 容量拆开，新增批次级涌现池作为涌现 tile 的归属。 |
| 2026-05-08 | 新增切图校准要求：prompt 禁止装饰网格倾向，UI 支持 crop box 外框调整和重切。 |
| 2026-05-08 | 切图校准从外框等距升级为完整 x/y line 调整：前端可拖动每条线，API/CLI/存储保存 `x_lines_percent` 与 `y_lines_percent`。 |
| 2026-05-09 | 明确 Sheet Run 操作语义：新建规划会自动切到最新 sheet；提交出图只作用于当前 sheet；“回填”改文案为“入池已采纳 tile”。 |
| 2026-05-09 | 统一前端产品语言：用户界面尽量使用“目标、整图、切片、格位、模型服务、提示词”，减少 Sheet/Tile/Provider/Prompt/brief 等工程词外露。 |

## Open Questions

后续迭代再确认：

1. 是否加入自动多 sheet 编排，一次覆盖超过 `rows * cols` 的整批 item。
2. 是否加入自动识别模型边界并吸附切线，减少人工拖动成本。
3. 是否加入 sheet 级 prompt 人工编辑 / 审批版本。
4. 是否升级 candidate-level 星标，让同一 artifact 下多个 candidate 能独立星标。
5. grid 模式 UI 是否把 `item` 展示为 `target`，以降低与旧单图流程的心智冲突。
6. 涌现池是否作为 Tile Review 内的筛选面板，还是在批次页作为独立第四区。
7. 涌现池条目需要哪些最小元数据，才能顺畅升级成正式 item。
