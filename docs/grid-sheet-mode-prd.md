# Grid Sheet Mode PRD

## Document Status

- Status: Draft for implementation planning
- Owner: project maintainers / agents working on grid sheet mode
- Last updated: 2026-05-08
- Related design: [grid-sheet-mode-design.md](./grid-sheet-mode-design.md)

本 PRD 描述 `grid_sheet` 模式从“能跑通”升级到“产品心智清晰、可验收、可维护”的目标状态。

---

## 1. Executive Summary

### Problem Statement

现有 `single` 流程以 item 为中心，适合单张精修；但 `grid_sheet` 模式一次生成的是整张网格图，再人工切片和回填候选。若继续把 sheet 生成硬塞进 item 流程，用户会分不清“当前是在生成 item、规划 sheet、审 tile，还是回填候选”。

### Proposed Solution

将 `grid_sheet` 明确为批次级 Sheet Run 工作流：item 只代表用户明确指定的目标资产，rows x cols 只代表本次 sheet 的出图容量。Agent 先为明确 item 做 brief / 意图识别，再把 bound slots 和剩余 emergent slots 汇总成整张 sheet prompt；人类在 Sheet Review 中基于真实切分线挑选 tile；被采纳的 bound tile 才回填到 item 候选池并默认星标，涌现好图先进入批次级涌现池。

### Success Criteria

- 用户能在批次页一眼区分 `single` 与 `grid_sheet` 两种生产模式，并知道当前批次处在哪个阶段。
- 一个 6x6 sheet 从规划、生成、切分、人工采纳到候选池回填，可以在 Web UI 中端到端完成，不需要手动改本地文件。
- 一个 6x6 sheet 的容量是 36 个槽位，但如果用户只指定 10 个目标资产，批次仍只有 10 个 item，其余 26 个槽位是 emergent slots，不预创建成 item。
- `grid_sheet` 规划前，所有既定 item 都有 brief 快照；sheet prompt 中每个 bound slot 都能追溯到对应 item brief。
- 只有人工采纳的 tile 才进入 item 候选池，默认星标，且候选来源显示 `sheet_id + cell_id`。
- 用户可以把涌现好图保存到涌现池、绑定到已有 item，或创建新 item；这些操作不会污染未采纳 item 的候选池。

---

## 2. User Experience & Functionality

### User Personas

- **资产生产者 / 人类审图者**：负责定义批次方向、审查 sheet 质量、挑选 tile、确认最终候选。
- **Agent / CLI 操作者**：负责批次编排、brief 补齐、sheet prompt 生成、provider 调用、状态查询和导出。
- **维护者 / 二次开发者**：负责接入新 provider、维护 prompt 模板、调整 sheet 状态流和 UI。

### Primary Mental Model

```text
single:
  item -> brief -> single image prompt -> candidate images -> human picks

grid_sheet:
  fixed item targets + emergent pool policy
    -> item briefs
    -> sheet plan = bound slots + emergent slots
    -> one sheet image
    -> tile review
    -> selected bound tiles become item candidates
    -> useful emergent tiles enter emergent pool or become new items
```

`grid_sheet` 模式下，item 不再承担 sheet 的中间状态，也不等于 sheet 格子数。item 只是“明确目标资产桶”和“最终候选池”；sheet run 才承担本轮网格生成、切分和审图记录；涌现池承接“好但尚未命名 / 尚未绑定”的额外 tile。

关键心智：

- `rows * cols` 是本轮 sheet 的出图容量，不是 item 数量。
- 固定目标 item 数量由用户控制，可以小于、等于或大于单张 sheet 容量。
- emergent slot 是 prompt 里的空余槽位，不是预创建 item。
- emergent pool 是批次级素材暂存区，不参与 item 状态机。

### Detailed Workflow

#### 1. Create Batch

人类 / Agent 应完成：

- 选择出图模式为 `grid_sheet`。
- 设置网格参数，例如 6x6、8x8。
- 设置批次背景：项目世界观、资产用途、整体风格、禁忌项。
- 新增明确目标 item，例如 10 个技能图标。即使 sheet 是 6x6，系统也不应因此自动生成 36 个 item。
- 设置是否允许涌现内容，以及涌现槽位的默认策略。

系统应完成：

- 将 `image_generation_mode` 保存为 `grid_sheet`。
- 在批次页显示该批次是 Sheet Run 工作流。
- 隐藏或弱化逐 item 直接出图入口，避免误导用户。

#### 2. Generate Item Briefs

Agent 应完成：

- 对每个既定 item 运行 brief / 意图识别。
- brief 输入包含 item 原始描述、批次背景、统一风格要求。
- brief 输出聚焦“这个资产格子要画什么”，不生成单图 prompt。
- 对已有候选图但缺少 brief 的 item，允许补 sidecar brief，不重置 item 状态。
- 只对明确 item 做 item brief；emergent slots 可以在 sheet planning 阶段生成轻量方向，但不创建 item brief artifact。

系统应完成：

- 为每个 bound slot 保存 brief 快照。
- 在 Sheet Run 中记录 brief 来源版本，保证后续 prompt 可追溯。

#### 3. Plan Sheet Run

Agent 应完成：

- 根据 rows x cols 计算总槽位。
- 将明确 item briefs 放入 bound slots。默认 row-major 先放固定目标，也可后续支持人工排序。
- 若槽位多于明确 item 数量，用 emergent slots 补齐。例如 6x6 + 10 个明确 item = 10 个 bound slots + 26 个 emergent slots。
- emergent slots 必须生成明确但轻量的方向，例如“同风格的辅助技能图标：防御 / 位移 / 控制 / 回复 / 陷阱 / 召唤”等，而不是让模型完全自由发挥，也不是重复同一句泛化描述。
- 输出 row-major 顺序的 `slot_lines`。

系统应完成：

- 新建 `sheet_vXXX`。
- 保存 slots、slot kind、item 绑定关系、brief snapshot 和 prompt 输入。
- 对 emergent slots 保存 `emergent_direction` / suggested title，但 `item_id` 为空。
- 允许后续新建多个 Sheet Run，而不会删除旧 sheet。

#### 4. Compose Sheet Prompt

Agent 应完成：

- 使用 `grid_sheet_prompt_template`。
- 填充 `{{rows}}`、`{{cols}}`、`{{cell_count}}`。
- 填充 `{{project_background}}` 和 `{{style_requirements}}`。
- 填充 `{{slot_lines}}`。
- 追加 `grid_sheet_negative_prompt`。
- 对 bound slots，`slot_lines` 使用 item brief 的视觉语义。
- 对 emergent slots，`slot_lines` 使用本轮规划生成的涌现方向，并明确它们是可自由发明但需同世界观、同风格、不重复已绑定目标的槽位。

系统应完成：

- 将完整 sheet prompt 保存为 artifact。
- 在 UI 中可查看 prompt，不要求用户逐 item 手动编辑。
- 后续可扩展为人工审批 prompt 后再提交。

#### 5. Generate Sheet

Agent / CLI 应完成：

- 按批次默认 provider 提交整张 sheet 生成。
- 对 APIMart GPT-Image-2 使用 `async_image` 协议。
- 轮询异步任务，下载 source image。

系统应完成：

- 在 generating 阶段显示 sheet 正在生成的状态。
- 不使用虚假的真实进度百分比；可以显示等待动画。
- 保存 provider、model、remote task id、source image path。

#### 6. Quality Check And Split

系统应完成：

- 在 source image 上覆盖真实数学切分线，而不是只依赖模型自己画出的格线。
- 按 rows / cols / padding / gap 切出 tiles。
- 在 Sheet Review 中展示整张图和每个 tile。
- 标出 tile 的 cell id、slot kind、绑定 item、review 状态。

人类应完成：

- 检查是否存在越界、错格、合并格、空格、主体跨格、风格跑偏等问题。
- 决定是否继续审 tile，还是重新生成一张 sheet。

#### 7. Review Tiles

人类应完成：

- 对每个 tile 选择：采纳、废弃、绑定到已有 item、创建新 item、标记为涌现好图。
- 对 bound slot，如果 tile 质量好但语义更适合另一个 item，可以重新绑定。
- 对 emergent slot，如果是好图但暂不进入 item，可以保存到涌现池。

系统应完成：

- `pending`: 默认待审，不进入候选池。
- `selected`: 已采纳，允许回填到目标 item。
- `rejected`: 废弃，留在 sheet 历史。
- `emergent`: 涌现好图，进入批次级涌现池，等待命名、绑定或创建 item。

#### 8. Promote Selected Tiles

系统应完成：

- 只有 `selected` tile 可以被批量回填。
- 回填时将 tile 复制到对应 item 的 `images/`。
- 写入 `image_generation` artifact，并记录来源 `grid_sheet`、`sheet_id`、`cell_id`、row、col。
- 默认星标该候选。
- `emergent` tile 不会自动进入任何 item；只有用户执行“绑定到已有 item”或“创建新 item 并采纳”后，才进入 item 候选池。
- item 工作台中显示候选来源。

人类应完成：

- 在 item 工作台最终比较候选、保留星标、确认采用或导出。

### User Stories

- As a human reviewer, I want to see the real split overlay on the generated sheet so that I can judge whether the sheet can be safely cropped.
- As a human reviewer, I want to click a tile and decide whether it is accepted, rejected, rebound, or emergent so that only useful tiles enter item candidates.
- As a human reviewer, I want to create 10 fixed targets in a 6x6 batch without seeing 36 item rows so that the sheet capacity does not become fake product work.
- As an agent operator, I want a single command/API flow for plan/generate/poll/split/backfill so that I can run large asset batches without manual file work.
- As a prompt maintainer, I want separate single-image and grid-sheet templates so that grid sheet prompts can optimize for cell separation, row-major assignment, and cropping safety.
- As a project maintainer, I want provider integrations grouped by protocol so that APIMart GPT-Image-2 can reuse `async_image` instead of becoming a site-specific provider type.

### Acceptance Criteria

- A `grid_sheet` batch creation flow includes mode, rows, cols, project background, style requirements, and asset domain.
- A user can add or import item targets before sheet planning.
- Item count remains the count of explicit user targets; sheet capacity and emergent slot count are displayed separately.
- Adding a new target item after a previous sheet run increases future bound slot count, but does not mutate old sheet slots.
- Planning a sheet auto-generates missing item briefs for bound slots.
- Planning does not create item records for emergent slots.
- Planning does not destroy existing item status or existing candidate images.
- Sheet prompt includes explicit slot assignments and emergent slot briefs.
- Generated sheet can be displayed with a real overlay grid.
- Split tiles can be reviewed individually.
- Review actions include accept, reject, bind to existing item, create new item, and mark emergent.
- Backfill only promotes accepted tiles.
- Emergent tiles can be saved to a batch-level emergent pool without being promoted.
- Promoted tiles are visible in item candidate pool and starred by default.
- Item candidate source displays sheet and cell metadata.
- CLI and Web APIs expose equivalent flow controls.
- Documentation explains `single` vs `grid_sheet` without requiring reading source code.

### Non-Goals

- Do not mix `single` and `grid_sheet` within the same task in V1.
- Do not auto-judge visual quality with vision models in V1.
- Do not attempt arbitrary non-grid segmentation in V1.
- Do not replace the item candidate pool and final review workflow in V1.
- Do not make APIMart GPT-Image-2 a new hardcoded provider type; it remains an `async_image` preset/config.

---

## 3. AI System Requirements

### Tool Requirements

- **Brief model**: used for item-level intent recognition.
- **Image provider**: supports grid sheet generation; APIMart GPT-Image-2 is supported through `async_image`.
- **Prompt templates**:
  - `brief_prompt_template`
  - `image_prompt_template`
  - `grid_sheet_prompt_template`
  - `grid_sheet_negative_prompt`
- **Local processing**: deterministic image split by rows/cols/padding/gap.
- **Web UI**: human visual review and candidate promotion.

### Prompt Requirements

Brief prompt must:

- Normalize vague item requests into visual intent.
- Preserve each item's semantic identity.
- Avoid overfitting to sheet layout details.

Grid sheet prompt must:

- Explicitly declare exact rows and columns.
- Define row-major order.
- Include one slot line per cell.
- Separate bound slots from emergent slots, while preserving a single row-major `slot_lines` list for model execution.
- For bound slots, carry over item brief semantics.
- For emergent slots, provide varied lightweight directions generated during sheet planning.
- Require one independent asset subject per cell.
- Require safe margins for strict mathematical crop.
- Forbid text, labels, numbering, logos, watermarks, signatures, UI badges, and subjects crossing cell boundaries.

### Evaluation Strategy

Manual evaluation is required in V1:

- **Semantic match**: selected bound tiles should match their item brief.
- **Crop safety**: selected tiles should remain readable after strict crop.
- **Style consistency**: selected tiles should share camera angle, material, lighting, background, and icon scale.
- **Emergent usefulness**: emergent tiles should be relevant enough to become future items or reserve candidates.
- **Mental model clarity**: users should be able to explain that 6x6 is capacity, not item count.

Suggested batch-level metrics:

- Accepted tile rate per sheet.
- Bound slot success rate.
- Emergent useful tile rate.
- Emergent pool save-to-use rate.
- Re-generation rate caused by sheet-level layout failure.
- Average accepted candidates per item after N sheet runs.

---

## 4. Technical Specifications

### Architecture Overview

```text
Task
  mode: grid_sheet
  items: explicit target asset buckets
  emergent_pool: useful unbound tiles
  sheets/
    sheet_v001/
      slots: bound + emergent slot plan
      slot brief snapshots
      sheet prompt artifact
      provider task metadata
      source image
      tiles
      review states
  item candidate pools
    promoted selected tiles
```

### Core Data Objects

#### Item

Represents an explicit target asset bucket and final candidate pool. It does not represent a sheet cell.

Required in grid mode:

- `item_id`
- `title`
- `raw_request`
- `brief_generation` or sidecar brief snapshot
- candidate image versions
- starred image versions

#### Sheet Run

Represents one whole-sheet generation attempt.

Required:

- `sheet_id`
- `status`
- `rows`
- `cols`
- `slots`
- `prompt`
- `provider`
- `model`
- `remote_task_id`
- `source_image_path`
- `tiles`

#### Emergent Pool Entry

Represents a useful tile that the user wants to keep, but has not yet bound to a target item.

Required:

- `pool_entry_id`
- `source_sheet_id`
- `source_cell_id`
- `image_path`
- `suggested_title`
- `suggested_tags`
- `review_note`
- `created_item_id`: optional, set only after creating a new item from the pool entry
- `target_item_id`: optional, set only after binding the pool entry to an existing item

#### Slot

Represents a planned cell before generation.

Required:

- `cell_id`
- `row`
- `col`
- `kind`: `bound` or `emergent`
- `item_id`: required for bound, empty for emergent
- `title`
- `brief_snapshot`: required for bound
- `emergent_direction`: required for emergent

#### Tile

Represents a cropped cell after split.

Required:

- `cell_id`
- `row`
- `col`
- `image_path`
- `review_status`
- `target_item_id`
- `promoted_image_version`
- `emergent_pool_entry_id`

### API Requirements

Batch / sheet APIs:

```text
GET  /tasks/{task_id}/sheets
GET  /tasks/{task_id}/sheets/{sheet_id}
POST /tasks/{task_id}/sheets/plan
POST /tasks/{task_id}/sheets/{sheet_id}/generate
POST /tasks/{task_id}/sheets/{sheet_id}/poll
POST /tasks/{task_id}/sheets/{sheet_id}/split
POST /tasks/{task_id}/sheets/{sheet_id}/backfill
```

Tile review APIs:

```text
POST /tasks/{task_id}/sheets/{sheet_id}/tiles/{cell_id}/review
POST /tasks/{task_id}/sheets/{sheet_id}/tiles/{cell_id}/promote
POST /tasks/{task_id}/sheets/{sheet_id}/tiles/{cell_id}/create-item
```

Emergent pool APIs:

```text
GET  /tasks/{task_id}/emergent-pool
POST /tasks/{task_id}/sheets/{sheet_id}/tiles/{cell_id}/save-emergent
POST /tasks/{task_id}/emergent-pool/{pool_entry_id}/bind
POST /tasks/{task_id}/emergent-pool/{pool_entry_id}/create-item
```

### CLI Requirements

```text
sheet list TASK_ID
sheet show TASK_ID SHEET_ID
sheet plan TASK_ID
sheet generate TASK_ID SHEET_ID
sheet poll TASK_ID SHEET_ID
sheet split TASK_ID SHEET_ID
sheet review TASK_ID SHEET_ID CELL_ID STATUS
sheet promote TASK_ID SHEET_ID CELL_ID ITEM_ID
sheet backfill TASK_ID SHEET_ID
sheet emergent-list TASK_ID
sheet emergent-bind TASK_ID POOL_ENTRY_ID ITEM_ID
sheet emergent-create-item TASK_ID POOL_ENTRY_ID TITLE
```

CLI should report state and file paths, but visual judgment should remain in Web UI.

### UI Requirements

Batch page in `grid_sheet` mode should show three primary zones, with the Emergent Pool visible inside Tile Review or as an adjacent fourth panel:

1. **Targets**
   - Explicit item target list only.
   - Add/import item. Adding an item changes future bound slot count, not old sheet runs.
   - Brief status per item.
   - Candidate count and starred count.
   - Sheet capacity, bound slot count, and emergent slot count shown as separate numbers.

2. **Sheet Runs**
   - Sheet version list.
   - Current sheet status.
   - Plan / generate / poll / split actions.
   - Provider/model metadata.

3. **Tile Review**
   - Source sheet preview with real overlay grid.
   - Tile grid.
   - Active tile detail.
   - Review actions: accept, reject, bind, create item, mark emergent.
   - Promotion status.
   - Emergent Pool panel: saved emergent tiles, rename, bind to existing item, create item from saved tile.

Item workspace should remain focused on final candidate review:

- Display promoted tile candidates.
- Show source `sheet_id` and `cell_id`.
- Support star/unstar and final approval.

### Security & Privacy

- Local-first storage remains the default.
- `/files` must only expose images and exports needed by UI.
- Provider API keys must remain in provider settings and never be written into sheet artifacts.
- Downloaded provider image URLs should be copied into local storage before review/export.

---

## 5. Risks & Roadmap

### Technical Risks

- **Model layout instability**: image model may draw uneven cells or subjects crossing boundaries. Mitigation: real overlay grid, strict prompt, manual review, and regeneration.
- **User mental model drift**: users may expect item buttons to generate grid sheets. Mitigation: separate Targets / Sheet Runs / Tile Review zones.
- **Candidate pollution**: poor tiles could flood item candidate pools. Mitigation: only accepted tiles promote.
- **Prompt overconstraint**: too many rules may reduce creativity. Mitigation: keep emergent slots explicit but flexible.
- **Provider shape changes**: third-party async APIs may differ. Mitigation: protocol-level `async_image` provider and configurable response paths where needed.

### Phased Rollout

#### MVP: Current Foundation

- Batch-level `grid_sheet` mode.
- APIMart GPT-Image-2 through `async_image`.
- Sheet planning, generation, polling, splitting.
- Real overlay grid.
- Tile review and selected tile promotion.
- Grid sheet prompt templates.

#### v1.1: Product Mindset Cleanup

- Treat item count as explicit target count only; do not pre-create item records for emergent slots.
- Add batch-level Emergent Pool and save/reuse actions.
- Refine UI into Targets / Sheet Runs / Tile Review / Emergent Pool zones where needed.
- Add sheet-level prompt preview and optional approval.
- Make emergent slot planning visible before generation.
- Improve copy so users know planning does not delete old sheets.
- Add review summary: accepted, rejected, saved emergent, unreviewed.

#### v1.2: Better Review Ergonomics

- Keyboard shortcuts for tile review.
- Batch select / batch reject.
- Rebind dropdown with search.
- Create item from emergent tile with naming flow.
- Filter tiles by pending / selected / rejected / emergent.
- Lightweight emergent slot direction editor before generation.

#### v2.0: Advanced Automation

- Automatic multi-sheet planning for item count > capacity.
- Optional vision-based sheet quality warning.
- Adjustable cut lines and split presets.
- Candidate-level scoring and comparison across sheet runs.
- Image-to-image reference support for sheet generation.

### Open Questions

- Should item be renamed to target in grid mode UI, while keeping storage as item?
- How much metadata should an emergent pool entry require before it can become a formal item?
- Should sheet prompt require human approval before generation, or be visible but auto-approved?
- Should accepted tiles instantly promote, or should there be a separate “apply selected tiles” confirmation?
- Should multiple accepted tiles for the same item from different sheets be ranked by sheet/run metadata?
- Should emergent pool entries be exportable independently from item-approved assets?
