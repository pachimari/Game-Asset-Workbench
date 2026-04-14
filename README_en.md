# Game Asset Workbench

[中文说明](./README.md)

A local-first workbench for generating, reviewing, starring, and exporting game assets.

This project combines:

- a **React web workbench** for visual review
- a **Python API + core pipeline** for orchestration and state management
- a **CLI** for batch operations, automation, and agent-friendly control

It is designed for a mixed workflow with both agent assistance and direct manual control:

- **Agent / CLI and the Web UI can both drive the workflow**
- **Agent / CLI** is the recommended path for orchestration, provider setup, batch control, and status-driven work
- **Web UI** is the recommended path for visual review, candidate comparison, starring, and final confirmation
- The two sides are meant to hand work back and forth, not live in strict isolation

## What It Does

Game Asset Workbench helps you run a batch of game asset requests through a staged workflow:

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

### What the Web UI Is Best At

The web workbench is the best place to:

- browse batches
- inspect item state
- compare candidates visually
- star multiple good images
- choose the current candidate
- export starred results

The UI is the best place for visual judgment and manual takeover.

### What CLI / Agents Are Best At

The CLI is best for:

- creating and updating tasks
- driving pipeline steps
- querying metrics and runtime resolution
- managing providers
- exporting assets
- repetitive orchestration with an agent

The CLI / agent path is best for automation, batch control, and workflow coordination.

That is a recommendation, not a hard boundary:

- you can let an agent drive the workflow and switch to the UI for review
- you can also work mostly in the UI and use the CLI for inspection or export
- both surfaces can move the same project forward

## Entry Point For Agents

If an agent is picking up this repository for the first time, the recommended reading order is:

1. [AGENTS.md](./AGENTS.md)
2. [skills/SKILL.md](./skills/SKILL.md)
3. then the relevant child skill:
   - [skills/provider-manager/SKILL.md](./skills/provider-manager/SKILL.md)
   - [skills/batch-operator/SKILL.md](./skills/batch-operator/SKILL.md)
   - [skills/item-workflow/SKILL.md](./skills/item-workflow/SKILL.md)
   - [skills/candidate-curator/SKILL.md](./skills/candidate-curator/SKILL.md)

Recommended mental model:

- `AGENTS.md` explains the repository structure, important files, and validation commands
- `skills/SKILL.md` acts as the project-level router
- child skills handle the concrete workflows

When a task depends on visual judgment, agents should follow the skill boundary and route the user back to the Web UI instead of pretending the terminal is enough.

## Install And Run Locally

### Python Dependencies

Python dependencies are defined in [pyproject.toml](./pyproject.toml).

For first-time users, this repo also ships a simpler install entry:

- [requirements.txt](./requirements.txt)

Recommended install:

```bash
python3 -m pip install -r requirements.txt
```

If you prefer an editable install instead:

```bash
python3 -m pip install -e .[api]
```

### Frontend Dependencies

Install frontend dependencies once before running the web app:

```bash
(cd web && npm install)
```

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
PYTHONPATH=src python3 -m ai_icon_pipeline.api_launcher --reload
```

Frontend:

```bash
(cd web && npm install && npm run dev -- --host 127.0.0.1)
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

## Recommended Workflow

A common and effective flow is:

1. Create a batch
2. Set batch-wide project background and style rules
3. Add items one by one or import with CSV
4. Use an agent or CLI to drive brief, prompt, and image generation
5. Review candidates in the candidate pool
6. Star the good ones
7. Confirm the current candidate
8. Export starred images as ZIP

If you prefer manual control, you can also drive the stages directly from the UI instead of relying on the CLI.

## CLI Quick Start

If you already installed `requirements.txt`, you can start using the CLI right away.

Inspect the available commands with:

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli --help
```

### Create a Task

```bash
PYTHONPATH=src python3 -m ai_icon_pipeline.cli task create \
  --task-name "三国奇幻首批资产" \
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
- async image providers
- Gemini-native providers

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
