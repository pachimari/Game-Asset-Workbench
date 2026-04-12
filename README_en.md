# AI Icon Pipeline

[中文说明](./README.md)

A local-first AI icon production workbench for batch generation, human review, candidate starring, and export.

This project combines:

- a **React web workbench** for visual review
- a **Python API + core pipeline** for orchestration and state management
- a **CLI** for batch operations, automation, and agent-friendly control

It is designed for a mixed workflow:

- **Agent / CLI** drives tasks, providers, and pipeline steps
- **Human reviewers** use the web UI to compare images, star candidates, and confirm the final pick

## What It Does

AI Icon Pipeline helps you run a batch of game icon requests through a staged workflow:

1. Create a batch with shared project background and style rules
2. Add items manually or import them from CSV / table data
3. Generate:
   - design briefs
   - image prompts
   - candidate images
4. Review candidates in the web UI
5. Star good options, confirm a chosen candidate, and export starred images as ZIP

Core ideas:

- **local-first**
- **human-in-the-loop**
- **batch-oriented**
- **multi-provider**
- **CLI + Web**

## Product Shape

### Web UI

The web workbench is the best place to:

- browse batches
- inspect item state
- compare candidates visually
- star multiple good images
- choose the current candidate
- export starred results

The UI is where visual judgment happens.

### CLI

The CLI is best for:

- creating and updating tasks
- driving pipeline steps
- querying metrics and runtime resolution
- managing providers
- exporting assets

The CLI is where automation and agent orchestration happen.

## Run Locally

### Fastest Option

macOS:

- double-click `start_local.command`
- stop with `stop_local.command`

Windows:

- double-click `start_local.bat`
- stop with `stop_local.bat`

### Manual Option

Backend:

```bash
cd /path/to/ai-icon-pipeline
PYTHONPATH=src python3 -m ai_icon_pipeline.api_launcher --reload
```

Frontend:

```bash
cd /path/to/ai-icon-pipeline/web
npm install
npm run dev -- --host 127.0.0.1
```

Open:

- Web: `http://127.0.0.1:5173/`
- API health: `http://127.0.0.1:8000/health`

## Simple Shared Deployment

The default setup is local-only.

If you want to run it on an internal server for a small team, you can expose the API with a simple shared token:

```bash
export AI_ICON_PIPELINE_API_ALLOW_REMOTE=1
export AI_ICON_PIPELINE_API_TOKEN="replace-with-a-shared-token"
export AI_ICON_PIPELINE_API_ALLOWED_ORIGINS="https://your-internal-ui.example.com"
PYTHONPATH=src python3 -m ai_icon_pipeline.api_launcher --host 0.0.0.0 --port 8000
```

Current scope:

- good for **local use**
- works for **small internal shared deployment**
- **not** a full multi-user SaaS yet

## Web Workflow

Typical workflow in the UI:

1. Create a batch
2. Set batch-wide project background and style rules
3. Add items one by one or import with CSV
4. Run design brief, prompt, and image generation
5. Review candidates in the candidate pool
6. Star the good ones
7. Confirm the current candidate
8. Export starred images as ZIP

## CLI Quick Start

Install editable package if you want the `ai-icon-pipeline` command:

```bash
cd /path/to/ai-icon-pipeline
python3 -m pip install -e .
```

You can also run everything with:

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli --help
```

### Create a Task

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli task create \
  --task-name "三国奇幻首批图标" \
  --project-background "三国奇幻，强调武将与雷电元素" \
  --style-requirements "高对比、单主体、避免文字"
```

### Create an Item

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli item create task_001 \
  --asset-type "skill_icon" \
  --title "雷暴" \
  --description "对敌人造成雷电伤害并附带麻痹效果" \
  --category "combat"
```

### Run the Pipeline

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli pipeline run task_001
```

Or stop after each stage for manual review:

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli pipeline run task_001 --no-auto-approve
PYTHONPATH=src python3 -m ai_icon_pipeline.cli step approve task_001 item_001 brief_generation
PYTHONPATH=src python3 -m ai_icon_pipeline.cli step run task_001 item_001 image_prompt
```

### Check Batch Metrics

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli task metrics task_001 --json
```

### Resolve Effective Provider / Model

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli runtime resolve task_001 item_001 --step image_generation --json
```

### Work With Starred Candidates

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli image starred task_001 --json
PYTHONPATH=src python3 -m ai_icon_pipeline.cli export starred task_001 --json
```

## Provider Support

The project currently supports three protocol families:

- `openai_compatible`
- `async_image`
- `gemini_native`

Why this matters:

- many third-party providers claim compatibility, but differ in real behavior
- the project adapts them behind a common pipeline model
- provider configuration is available in the web settings UI and through the CLI

Examples already exercised in this repo's development flow include:

- OpenAI-compatible providers
- ToAPIs-style async image providers
- Gemini-native third-party providers such as DMX-style endpoints

## CSV Import

The batch dashboard supports:

- CSV import
- TSV import
- direct paste from spreadsheets

It also provides a downloadable CSV template in the UI.

Notes:

- **CSV** = comma-separated values
- **TSV** = tab-separated values
- TSV is often the easiest format when pasting directly from Excel or Feishu sheets

## Example Input

You can start from the example file:

- [examples/batch.example.json](./examples/batch.example.json)

Create a task from JSON:

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli task create --input-file examples/batch.example.json
```

## Repository Layout

```text
src/ai_icon_pipeline   Python core, API, CLI, providers, storage, state machine
web/                   React workbench
tests/                 focused regression tests
examples/              minimal example inputs
tasks/                 local runtime task data (ignored in git)
```

## Current Scope

This repository is intentionally scoped as a practical production workbench, not a general SaaS platform.

Today it is strong at:

- local-first batch orchestration
- human review of visual candidates
- provider switching and runtime resolution
- candidate starring and ZIP export
- agent-friendly CLI control

It does **not** yet try to be:

- a hosted multi-tenant product
- a full permissions / user-management system
- a pure text-only image review workflow

The intended model is:

- use **agents and CLI** for automation
- use the **web UI** for visual review

## Validation

Typical local verification commands:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=src python3 -m compileall src
cd web && npm run lint
cd web && npm run build
```
