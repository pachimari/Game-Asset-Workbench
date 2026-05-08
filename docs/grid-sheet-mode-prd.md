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

将 `grid_sheet` 明确为批次级 Sheet Run 工作流：既定 item 仍先做 brief / 意图识别，Agent 将 item briefs 与 emergent slots 汇总成整张 sheet prompt；图片模型只生成一张 sheet；人类在 Sheet Review 中基于真实切分线挑选 tile；被采纳的 tile 才回填到 item 候选池并默认星标。

### Success Criteria

- 用户能在批次页一眼区分 `single` 与 `grid_sheet` 两种生产模式，并知道当前批次处在哪个阶段。
- 一个 6x6 sheet 从规划、生成、切分、人工采纳到候选池回填，可以在 Web UI 中端到端完成，不需要手动改本地文件。
- `grid_sheet` 规划前，所有既定 item 都有 brief 快照；sheet prompt 中每个 bound slot 都能追溯到对应 item brief。
- 只有人工采纳的 tile 才进入 item 候选池，默认星标，且候选来源显示 `sheet_id + cell_id`。
- 用户可以把涌现好图保留、绑定到已有 item，或创建新 item；这些操作不会污染未采纳 item 的候选池。

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
  batch targets -> item briefs -> sheet plan -> one sheet image -> tile review -> selected tiles become item candidates
```

`grid_sheet` 模式下，item 不再承担 sheet 的中间状态。item 只是“目标资产桶”和“最终候选池”；sheet run 才承担本轮网格生成、切分和审图记录。

### Detailed Workflow

#### 1. Create Batch

人类 / Agent 应完成：

- 选择出图模式为 `grid_sheet`。
- 设置网格参数，例如 6x6、8x8。
- 设置批次背景：项目世界观、资产用途、整体风格、禁忌项。
- 新增既定目标 item，例如 10 个技能图标。
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

系统应完成：

- 为每个 bound slot 保存 brief 快照。
- 在 Sheet Run 中记录 brief 来源版本，保证后续 prompt 可追溯。

#### 3. Plan Sheet Run

Agent 应完成：

- 根据 rows x cols 计算总槽位。
- 将既定 item briefs 放入 bound slots。
- 若槽位多于 item 数量，用 emergent slots 补齐。
- emergent slots 必须生成明确 brief，例如“同风格但未指定的辅助技能图标”，而不是让模型完全自由发挥。
- 输出 row-major 顺序的 `slot_lines`。

系统应完成：

- 新建 `sheet_vXXX`。
- 保存 slots、slot kind、item 绑定关系、brief snapshot 和 prompt 输入。
- 允许后续新建多个 Sheet Run，而不会删除旧 sheet。

#### 4. Compose Sheet Prompt

Agent 应完成：

- 使用 `grid_sheet_prompt_template`。
- 填充 `{{rows}}`、`{{cols}}`、`{{cell_count}}`。
- 填充 `{{project_background}}` 和 `{{style_requirements}}`。
- 填充 `{{slot_lines}}`。
- 追加 `grid_sheet_negative_prompt`。

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
- 对 emergent slot，如果是好图但暂不进入 item，可以只标记为涌现好图。

系统应完成：

- `pending`: 默认待审，不进入候选池。
- `selected`: 已采纳，允许回填到目标 item。
- `rejected`: 废弃，留在 sheet 历史。
- `emergent`: 涌现好图，留在 sheet 层等待命名、绑定或创建 item。

#### 8. Promote Selected Tiles

系统应完成：

- 只有 `selected` tile 可以被批量回填。
- 回填时将 tile 复制到对应 item 的 `images/`。
- 写入 `image_generation` artifact，并记录来源 `grid_sheet`、`sheet_id`、`cell_id`、row、col。
- 默认星标该候选。
- item 工作台中显示候选来源。

人类应完成：

- 在 item 工作台最终比较候选、保留星标、确认采用或导出。

### User Stories

- As a human reviewer, I want to see the real split overlay on the generated sheet so that I can judge whether the sheet can be safely cropped.
- As a human reviewer, I want to click a tile and decide whether it is accepted, rejected, rebound, or emergent so that only useful tiles enter item candidates.
- As an agent operator, I want a single command/API flow for plan/generate/poll/split/backfill so that I can run large asset batches without manual file work.
- As a prompt maintainer, I want separate single-image and grid-sheet templates so that grid sheet prompts can optimize for cell separation, row-major assignment, and cropping safety.
- As a project maintainer, I want provider integrations grouped by protocol so that APIMart GPT-Image-2 can reuse `async_image` instead of becoming a site-specific provider type.

### Acceptance Criteria

- A `grid_sheet` batch creation flow includes mode, rows, cols, project background, style requirements, and asset domain.
- A user can add or import item targets before sheet planning.
- Planning a sheet auto-generates missing item briefs for bound slots.
- Planning does not destroy existing item status or existing candidate images.
- Sheet prompt includes explicit slot assignments and emergent slot briefs.
- Generated sheet can be displayed with a real overlay grid.
- Split tiles can be reviewed individually.
- Review actions include accept, reject, bind to existing item, create new item, and mark emergent.
- Backfill only promotes accepted tiles.
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
- Separate bound slots from emergent slots.
- Require one independent asset subject per cell.
- Require safe margins for strict mathematical crop.
- Forbid text, labels, numbering, logos, watermarks, signatures, UI badges, and subjects crossing cell boundaries.

### Evaluation Strategy

Manual evaluation is required in V1:

- **Semantic match**: selected bound tiles should match their item brief.
- **Crop safety**: selected tiles should remain readable after strict crop.
- **Style consistency**: selected tiles should share camera angle, material, lighting, background, and icon scale.
- **Emergent usefulness**: emergent tiles should be relevant enough to become future items or reserve candidates.

Suggested batch-level metrics:

- Accepted tile rate per sheet.
- Bound slot success rate.
- Emergent useful tile rate.
- Re-generation rate caused by sheet-level layout failure.
- Average accepted candidates per item after N sheet runs.

---

## 4. Technical Specifications

### Architecture Overview

```text
Task
  mode: grid_sheet
  items: target asset buckets
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

Represents a target asset bucket and final candidate pool.

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

#### Slot

Represents a planned cell before generation.

Required:

- `cell_id`
- `row`
- `col`
- `kind`: `bound` or `emergent`
- `item_id`: optional for emergent
- `title`
- `brief_snapshot`

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
```

CLI should report state and file paths, but visual judgment should remain in Web UI.

### UI Requirements

Batch page in `grid_sheet` mode should show three explicit zones:

1. **Targets**
   - Existing item list.
   - Add/import item.
   - Brief status per item.
   - Candidate count and starred count.

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

- Refactor UI into Targets / Sheet Runs / Tile Review zones.
- Add sheet-level prompt preview and optional approval.
- Make emergent slot planning visible before generation.
- Improve copy so users know planning does not delete old sheets.
- Add review summary: accepted, rejected, emergent, unreviewed.

#### v1.2: Better Review Ergonomics

- Keyboard shortcuts for tile review.
- Batch select / batch reject.
- Rebind dropdown with search.
- Create item from emergent tile with naming flow.
- Filter tiles by pending / selected / rejected / emergent.

#### v2.0: Advanced Automation

- Automatic multi-sheet planning for item count > capacity.
- Optional vision-based sheet quality warning.
- Adjustable cut lines and split presets.
- Candidate-level scoring and comparison across sheet runs.
- Image-to-image reference support for sheet generation.

### Open Questions

- Should item be renamed to target in grid mode UI, while keeping storage as item?
- Should emergent slots be generated by brief model during planning, or remain template-only with broad rules?
- Should sheet prompt require human approval before generation, or be visible but auto-approved?
- Should accepted tiles instantly promote, or should there be a separate “apply selected tiles” confirmation?
- Should multiple accepted tiles for the same item from different sheets be ranked by sheet/run metadata?

