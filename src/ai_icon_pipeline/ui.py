from __future__ import annotations

from pathlib import Path
import csv
import json
import io
import sys

import pandas as pd
import streamlit as st

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ai_icon_pipeline.config import STEP_BRIEF_GENERATION, STEP_IMAGE_GENERATION, STEP_IMAGE_PROMPT
    from ai_icon_pipeline.pipeline import (
        approve_step,
        edit_brief,
        edit_prompt,
        rollback_step,
        run_pipeline,
        run_step,
        set_current_version,
    )
    from ai_icon_pipeline.storage import (
        create_item,
        create_task,
        item_dir,
        list_artifacts,
        list_items,
        list_tasks,
        load_artifact,
        load_item,
        load_item_events,
        load_task,
        load_task_events,
        update_task_settings,
        update_item,
    )
else:
    from .config import STEP_BRIEF_GENERATION, STEP_IMAGE_GENERATION, STEP_IMAGE_PROMPT
    from .pipeline import (
        approve_step,
        edit_brief,
        edit_prompt,
        rollback_step,
        run_pipeline,
        run_step,
        set_current_version,
    )
    from .storage import (
        create_item,
        create_task,
        item_dir,
        list_artifacts,
        list_items,
        list_tasks,
        load_artifact,
        load_item,
        load_item_events,
        load_task,
        load_task_events,
        update_task_settings,
        update_item,
    )


STEP_LABELS = {
    STEP_BRIEF_GENERATION: "设计说明",
    STEP_IMAGE_PROMPT: "出图指令",
    STEP_IMAGE_GENERATION: "候选图",
}

STATUS_LABELS = {
    "draft": "待开始",
    "brief_generated": "待确认设计说明",
    "brief_approved": "可生成出图指令",
    "prompt_generated": "待确认出图指令",
    "prompt_approved": "可生成候选图",
    "image_generated": "待确认候选图",
    "completed": "已完成",
    "failed": "失败",
    "archived": "已归档",
}

OVERVIEW_CARD_COLUMNS = 4


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def _reset_keys(keys: list[str]) -> None:
    for key in keys:
        st.session_state.pop(key, None)


def _reset_task_ui_state(task_id: str, item_id: str | None = None) -> None:
    keys = [
        f"item-grid-{task_id}",
        f"bulk-paste-{task_id}",
        f"batch-task-name-{task_id}",
        f"batch-project-background-{task_id}",
        f"batch-style-requirements-{task_id}",
    ]
    if item_id:
        keys.extend(
            [
                f"source-asset-type-{item_id}",
                f"source-title-{item_id}",
                f"source-description-{item_id}",
                f"source-category-{item_id}",
                f"source-extra-context-{item_id}",
                f"brief-title-{item_id}",
                f"brief-description-{item_id}",
                f"brief-keywords-{item_id}",
                f"brief-icon-subject-{item_id}",
                f"brief-visual-focus-{item_id}",
                f"brief-note-{item_id}",
                f"prompt-text-{item_id}",
                f"prompt-negative-{item_id}",
                f"prompt-note-{item_id}",
            ]
        )
    _reset_keys(keys)


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .app-shell {
          padding: 0.6rem 0 1.2rem 0;
        }
        .hero {
          background: linear-gradient(135deg, #f6f0df 0%, #d7ebe7 52%, #d8e1f7 100%);
          border: 1px solid rgba(44, 62, 80, 0.12);
          border-radius: 20px;
          padding: 1.1rem 1.2rem;
          margin-bottom: 1rem;
        }
        .hero h1 {
          font-size: 1.9rem;
          margin: 0 0 0.35rem 0;
          color: #1f2937;
        }
        .hero p {
          margin: 0;
          color: #334155;
        }
        .panel {
          border: 1px solid rgba(30, 41, 59, 0.12);
          border-radius: 18px;
          padding: 0.9rem 1rem;
          background: rgba(255, 255, 255, 0.74);
          box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
          margin-bottom: 0.9rem;
        }
        .kicker {
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-size: 0.75rem;
          color: #64748b;
        }
        .stat {
          border-radius: 16px;
          padding: 0.8rem 0.9rem;
          background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(246,248,251,0.9));
          border: 1px solid rgba(100, 116, 139, 0.15);
        }
        .stat strong {
          display: block;
          font-size: 1.15rem;
          color: #0f172a;
        }
        .code-box {
          background: #0f172a;
          color: #e2e8f0;
          padding: 0.75rem 0.9rem;
          border-radius: 14px;
          overflow-x: auto;
          font-family: Menlo, Monaco, monospace;
          font-size: 0.84rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _show_json(payload: dict | list) -> None:
    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")


def _switcher(label: str, options: list[str], *, key: str, default: str) -> str:
    if key not in st.session_state:
        st.session_state[key] = default
    if hasattr(st, "segmented_control"):
        return st.segmented_control(
            label,
            options=options,
            selection_mode="single",
            default=st.session_state[key],
            key=key,
            label_visibility="collapsed",
        )
    return st.radio(
        label,
        options=options,
        horizontal=True,
        key=key,
        label_visibility="collapsed",
    )


def _task_label(task: dict) -> str:
    return f"{task['task_id']} · {task.get('task_name', '未命名批次')} · {STATUS_LABELS.get(task.get('status', 'draft'), task.get('status', 'draft'))}"


def _item_label(item: dict) -> str:
    title = item.get("title") or item.get("asset_type", "条目")
    return f"{item['item_id']} · {title} · {STATUS_LABELS.get(item.get('status', 'draft'), item.get('status', 'draft'))}"


def _artifact_or_none(task_id: str, item_id: str, step: str, version: str | None) -> dict | None:
    if not version:
        return None
    try:
        return load_artifact(task_id, item_id, step, version)
    except ValueError:
        return None


def _render_task_creation() -> None:
    with st.sidebar.expander("创建批次", expanded=False):
        with st.form("create_task_form"):
            task_name = st.text_input("批次名称", value="未命名图标批次")
            project_background = st.text_area(
                "项目背景",
                placeholder="例如：三国奇幻、末日科幻、西幻卡牌",
                height=120,
                help="支持多段文本。作为低权重背景信息，帮助系统理解这批图的世界观与用途。",
            )
            style_requirements = st.text_area(
                "统一风格要求",
                placeholder="例如：高对比、单主体、清晰轮廓、避免文字",
                height=120,
                help="支持多段文本。作为低权重风格补充，不会压过每个条目自身的需求。",
            )
            submitted = st.form_submit_button("创建空批次", use_container_width=True)
        if submitted:
            try:
                task = create_task(
                    task_name=task_name,
                    project_background=project_background,
                    style_requirements=style_requirements,
                )
            except Exception as exc:
                st.sidebar.error(str(exc))
            else:
                st.sidebar.success(f"已创建 {task['task_id']}")
                st.session_state["selected_task_id"] = task["task_id"]
                _rerun()


def _render_sidebar(tasks: list[dict]) -> str | None:
    st.sidebar.title("工作台")
    st.sidebar.caption("批次列表与基础操作。")
    _render_task_creation()

    if not tasks:
        st.sidebar.info("还没有 task，可以先从上面的表单创建。")
        return None

    task_lookup = {task["task_id"]: task for task in tasks}
    current_task_id = st.session_state.get("selected_task_id")
    if current_task_id not in task_lookup:
        current_task_id = tasks[0]["task_id"]

    selected_label = st.sidebar.selectbox(
        "选择批次",
        options=[task["task_id"] for task in tasks],
        index=[task["task_id"] for task in tasks].index(current_task_id),
        format_func=lambda task_id: _task_label(task_lookup[task_id]),
        key="selected_task_id",
    )

    if st.sidebar.button("刷新批次列表", use_container_width=True):
        _rerun()

    return selected_label


def _artifact_source_label(artifact: dict) -> str:
    provider = artifact.get("provider")
    if provider == "manual":
        return "手动编辑"
    if provider:
        return f"自动生成 · {provider}"
    return "自动生成"


def _render_artifact_preview(task_id: str, item_id: str, step: str, artifact: dict) -> None:
    if step == STEP_IMAGE_GENERATION:
        image_root = item_dir(task_id, item_id) / "images"
        candidates = artifact.get("output", {}).get("candidates", [])
        if not candidates:
            st.info("当前版本还没有候选图。")
            return
        cols = st.columns(min(3, len(candidates)))
        for idx, candidate in enumerate(candidates):
            image_path = image_root / candidate["image_path"]
            if image_path.exists():
                cols[idx % len(cols)].image(
                    str(image_path),
                    caption=candidate["candidate_id"],
                    use_container_width=True,
                )
        return

    output = artifact.get("output", {})
    st.code(json.dumps(output, ensure_ascii=False, indent=2), language="json")


def _render_brief_readable(artifact: dict) -> None:
    output = artifact.get("output", {})
    keywords = output.get("keywords", [])
    st.markdown(
        f"""
        <div class="panel">
          <div class="kicker">名称</div>
          <p style="margin:0.15rem 0 0.8rem 0;color:#0f172a;font-size:1.05rem;"><strong>{output.get('title', '未命名')}</strong></p>
          <div class="kicker">需求整理</div>
          <p style="margin:0.15rem 0 0.8rem 0;color:#334155;white-space:pre-wrap;">{output.get('description', '暂无')}</p>
          <div class="kicker">图标主体</div>
          <p style="margin:0.15rem 0 0.8rem 0;color:#334155;">{output.get('icon_subject', '暂无')}</p>
          <div class="kicker">视觉重点</div>
          <p style="margin:0.15rem 0 0.8rem 0;color:#334155;">{output.get('visual_focus', '暂无')}</p>
          <div class="kicker">关键词</div>
          <p style="margin:0.15rem 0;color:#334155;">{', '.join(keywords) if keywords else '暂无'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_prompt_readable(artifact: dict) -> None:
    output = artifact.get("output", {})
    st.markdown(
        f"""
        <div class="panel">
          <div class="kicker">出图指令</div>
          <p style="margin:0.15rem 0 0.8rem 0;color:#334155;white-space:pre-wrap;">{output.get('prompt', '暂无')}</p>
          <div class="kicker">负向指令</div>
          <p style="margin:0.15rem 0 0.8rem 0;color:#334155;white-space:pre-wrap;">{output.get('negative_prompt', '暂无')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _current_preview_path(task_id: str, item: dict) -> Path | None:
    item_id = item["item_id"]
    image_root = item_dir(task_id, item_id) / "images"
    approved_path = image_root / "approved.png"
    if approved_path.exists():
        return approved_path

    image_version = item["current_versions"].get(STEP_IMAGE_GENERATION)
    if not image_version:
        return None

    image_artifact = _artifact_or_none(task_id, item_id, STEP_IMAGE_GENERATION, image_version)
    if not image_artifact:
        return None

    candidates = image_artifact.get("output", {}).get("candidates", [])
    if not candidates:
        return None

    candidate_path = image_root / candidates[0]["image_path"]
    if candidate_path.exists():
        return candidate_path
    return None


def _default_output_view(item: dict) -> str:
    status = item.get("status", "draft")
    if status in {"draft", "brief_generated", "brief_approved"}:
        return "设计说明"
    if status in {"prompt_generated", "prompt_approved"}:
        return "出图指令"
    if status in {"image_generated", "completed"}:
        return "当前候选图"
    return "总览"


def _candidate_paths(task_id: str, item_id: str, image_artifact: dict | None) -> list[tuple[str, Path]]:
    if not image_artifact:
        return []
    image_root = item_dir(task_id, item_id) / "images"
    candidates = image_artifact.get("output", {}).get("candidates", [])
    resolved: list[tuple[str, Path]] = []
    for index, candidate in enumerate(candidates, start=1):
        path = image_root / candidate["image_path"]
        if path.exists():
            resolved.append((f"候选 {index}", path))
    return resolved


def _render_entry_overview(task_id: str, items: list[dict]) -> None:
    st.markdown("### 条目概览")
    st.caption("这里直接看每个条目的当前结果。点“选中条目”后，下方会自动切到条目工作台。")
    if not items:
        st.info("当前批次还没有条目。")
        return

    current_selected = st.session_state.get(f"selected-item-{task_id}")
    for start in range(0, len(items), OVERVIEW_CARD_COLUMNS):
        row_items = items[start : start + OVERVIEW_CARD_COLUMNS]
        columns = st.columns(OVERVIEW_CARD_COLUMNS)
        for col, item in zip(columns, row_items):
            preview_path = _current_preview_path(task_id, item)
            is_selected = item["item_id"] == current_selected
            with col:
                st.markdown(
                    f"""
                    <div class="panel" style="border-width:{'2px' if is_selected else '1px'}; border-color:{'#ef4444' if is_selected else 'rgba(30, 41, 59, 0.12)'};">
                      <div class="kicker">{item['item_id']}</div>
                      <h4 style="margin:0.25rem 0 0.35rem 0;color:#0f172a;">{item.get('title') or '未命名条目'}</h4>
                      <p style="margin:0.15rem 0;color:#475569;">{item.get('asset_type', 'generic_icon')} · {STATUS_LABELS.get(item.get('status', 'draft'), item.get('status', 'draft'))}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if preview_path:
                    st.image(str(preview_path), width=140)
                else:
                    st.info("还没有候选图")
                summary_lines = [
                    f"设计说明：{item['current_versions'].get(STEP_BRIEF_GENERATION) or '无'}",
                    f"出图指令：{item['current_versions'].get(STEP_IMAGE_PROMPT) or '无'}",
                    f"候选图：{item['current_versions'].get(STEP_IMAGE_GENERATION) or '无'}",
                ]
                st.caption(" | ".join(summary_lines))
                if st.button(
                    "选中条目" if not is_selected else "当前条目",
                    key=f"overview-open-{item['item_id']}",
                    use_container_width=True,
                    disabled=is_selected,
                ):
                    st.session_state[f"selected-item-{task_id}"] = item["item_id"]
                    st.session_state[f"workspace-view-{task_id}"] = "条目工作台"
                    _reset_task_ui_state(task_id, item["item_id"])
                    _rerun()


def _parse_pasted_rows(raw_text: str) -> list[dict]:
    text = raw_text.strip()
    if not text:
        return []

    delimiter = "\t" if "\t" in text else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return []

    header_aliases = {
        "名称": "title",
        "title": "title",
        "需求描述": "description",
        "description": "description",
        "资产类型": "asset_type",
        "asset_type": "asset_type",
        "分类": "category",
        "category": "category",
        "条目补充说明": "extra_context",
        "额外上下文": "extra_context",
        "extra_context": "extra_context",
    }
    first_row = [cell.strip() for cell in rows[0]]
    normalized_header = [header_aliases.get(cell.lower() if cell.isascii() else cell, "") for cell in first_row]
    has_header = any(normalized_header)

    parsed = []
    if has_header:
        headers = normalized_header
        for raw_row in rows[1:]:
            payload = {}
            for index, value in enumerate(raw_row):
                if index >= len(headers):
                    continue
                field = headers[index]
                if field:
                    payload[field] = value.strip()
            if any(payload.values()):
                parsed.append(payload)
        return parsed

    fallback_fields = ["title", "description", "asset_type", "category", "extra_context"]
    for raw_row in rows:
        payload = {}
        for index, value in enumerate(raw_row):
            if index >= len(fallback_fields):
                continue
            payload[fallback_fields[index]] = value.strip()
        if any(payload.values()):
            parsed.append(payload)
    return parsed


def _create_items_from_paste(task_id: str, raw_text: str) -> list[str]:
    parsed_rows = _parse_pasted_rows(raw_text)
    if not parsed_rows:
        raise ValueError("没有解析到可用条目。请检查粘贴内容。")

    created_ids = []
    for row in parsed_rows:
        item = create_item(
            task_id,
            title=row.get("title", ""),
            description=row.get("description", ""),
            asset_type=row.get("asset_type", "") or "generic_icon",
            category=row.get("category", ""),
            extra_context=row.get("extra_context", ""),
        )
        created_ids.append(item["item_id"])
    return created_ids


def _render_batch_settings(task: dict) -> None:
    task_id = task["task_id"]
    st.markdown("### 批次设定")
    with st.form(f"batch-settings-{task_id}"):
        task_name = st.text_input("批次名称", value=task.get("task_name", ""), key=f"batch-task-name-{task_id}")
        project_background = st.text_area(
            "项目背景",
            value=task.get("project_background", ""),
            height=120,
            help="支持多段文本。作为低权重背景信息，不会压过条目自身需求。",
            key=f"batch-project-background-{task_id}",
        )
        style_requirements = st.text_area(
            "统一风格要求",
            value=task.get("style_requirements", ""),
            height=120,
            help="支持多段文本。用于约束整体风格和禁用项。",
            key=f"batch-style-requirements-{task_id}",
        )
        submitted = st.form_submit_button("保存批次设定", use_container_width=True)
    if submitted:
        try:
            update_task_settings(
                task_id,
                task_name=task_name,
                project_background=project_background,
                style_requirements=style_requirements,
            )
        except Exception as exc:
            st.error(str(exc))
        else:
            st.success("批次设定已保存。")
            _rerun()


def _render_task_actions(task_id: str) -> None:
    st.markdown("### 批次操作")
    left, mid, right = st.columns(3)
    with left:
        if st.button("批量自动跑完整个批次", key=f"run-task-{task_id}", use_container_width=True):
            try:
                run_pipeline(task_id)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("已批量跑完整个批次。")
                _rerun()
    with mid:
        if st.button("批量跑到待审核", key=f"run-task-review-{task_id}", use_container_width=True):
            try:
                run_pipeline(task_id, auto_approve=False)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("已推进到待审核节点。")
                _rerun()
    with right:
        if st.button("刷新批次", key=f"refresh-task-{task_id}", use_container_width=True):
            _reset_task_ui_state(task_id, st.session_state.get(f"selected-item-{task_id}"))
            _rerun()


def _render_item_selector(task_id: str, items: list[dict]) -> str | None:
    if not items:
        return None

    current_selected = st.session_state.get(f"selected-item-{task_id}")
    if current_selected not in {item["item_id"] for item in items}:
        current_selected = items[0]["item_id"]

    option_ids = [item["item_id"] for item in items]
    selected_item_id = st.radio(
        "当前条目",
        options=option_ids,
        index=option_ids.index(current_selected),
        format_func=lambda item_id: _item_label(next(item for item in items if item["item_id"] == item_id)),
        key=f"selected-item-radio-{task_id}",
    )
    if st.session_state.get(f"selected-item-{task_id}") != selected_item_id:
        st.session_state[f"selected-item-{task_id}"] = selected_item_id
        _reset_task_ui_state(task_id, selected_item_id)
        _rerun()
    return selected_item_id


def _render_item_management(task: dict) -> None:
    task_id = task["task_id"]
    items = list_items(task_id)

    with st.expander("新增条目", expanded=not items):
        with st.form(f"quick-create-item-{task_id}"):
            default_index = 0
            asset_type_options = ["skill_icon", "buff_icon", "item_icon", "generic_icon"]
            asset_type = st.selectbox("资产类型", options=asset_type_options, index=default_index)
            title = st.text_input("名称", placeholder="例如：雷暴")
            description = st.text_area(
                "需求描述",
                placeholder="例如：对敌人造成雷电伤害并附带麻痹效果",
                height=120,
            )
            category = st.text_input("分类", value="combat")
            extra_context = st.text_area(
                "条目补充说明",
                placeholder="例如：用于技能栏第一格，强调中心发光和电弧外扩",
                height=80,
                help="这里写这一条素材专属的补充信息。批次共用的规范请写在“项目背景/统一风格要求”里。",
            )
            submitted = st.form_submit_button("新增条目并打开详情", use_container_width=True)
        if submitted:
            try:
                item = create_item(
                    task_id,
                    asset_type=asset_type,
                    title=title,
                    description=description,
                    category=category,
                    extra_context=extra_context,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state[f"selected-item-{task_id}"] = item["item_id"]
                st.success(f"已创建 {item['item_id']}。")
                _rerun()

    columns = ["条目ID", "名称", "资产类型", "需求描述", "分类", "条目补充说明", "状态"]
    rows = []
    for item in items:
        rows.append(
            {
                "条目ID": item["item_id"],
                "名称": item.get("title", ""),
                "资产类型": item.get("asset_type", "generic_icon"),
                "需求描述": item.get("description", ""),
                "分类": item.get("category", ""),
                "条目补充说明": item.get("extra_context", ""),
                "状态": STATUS_LABELS.get(item.get("status", "draft"), item.get("status", "draft")),
            }
        )

    st.markdown("### 条目表")
    st.caption("这里用于批量编辑已有条目。当前条目的切换在上方单独处理，避免多选状态混乱。")
    editor_df = pd.DataFrame(rows, columns=columns)
    edited_df = st.data_editor(
        editor_df,
        num_rows="fixed",
        hide_index=True,
        use_container_width=True,
        key=f"item-grid-{task_id}",
        column_config={
            "条目ID": st.column_config.TextColumn("条目ID", disabled=True),
            "名称": st.column_config.TextColumn("名称"),
            "资产类型": st.column_config.TextColumn("资产类型"),
            "需求描述": st.column_config.TextColumn("需求描述", width="large"),
            "分类": st.column_config.TextColumn("分类"),
            "条目补充说明": st.column_config.TextColumn("条目补充说明", width="medium"),
            "状态": st.column_config.TextColumn("状态", disabled=True),
        },
        disabled=["条目ID", "状态"],
    )
    edited_rows = edited_df.to_dict("records")

    action_left, action_mid = st.columns([1.1, 1.4])
    with action_left:
        if st.button("保存条目表格变更", key=f"save-item-grid-{task_id}", use_container_width=True):
            try:
                existing_ids = {item["item_id"] for item in items}
                for row in edited_rows:
                    title = str(row.get("名称", "") or "").strip()
                    description = str(row.get("需求描述", "") or "").strip()
                    asset_type = str(row.get("资产类型", "") or "generic_icon").strip() or "generic_icon"
                    category = str(row.get("分类", "") or "").strip()
                    extra_context = str(row.get("条目补充说明", "") or "").strip()
                    item_id = str(row.get("条目ID", "") or "").strip()

                    if not any([title, description, category, extra_context, item_id]):
                        continue

                    if item_id and item_id in existing_ids:
                        update_item(
                            task_id,
                            item_id,
                            asset_type=asset_type,
                            title=title,
                            description=description,
                            category=category,
                            extra_context=extra_context,
                        )
            except Exception as exc:
                st.error(str(exc))
            else:
                _reset_task_ui_state(task_id, st.session_state.get(f"selected-item-{task_id}"))
                st.success("条目表格已保存。")
                _rerun()
    with action_mid:
        st.caption("支持增量保存。已存在的条目会更新，空白新行会跳过。")

    with st.expander("批量粘贴条目", expanded=not items):
        st.caption("推荐粘贴 TSV（制表符分隔）或 CSV。顺序建议：名称、需求描述、资产类型、分类、条目补充说明。也支持首行表头。")
        example = "名称\t需求描述\t资产类型\t分类\t条目补充说明\n雷暴\t对敌人造成雷电伤害并附带麻痹效果\tskill_icon\tcombat\t用于技能栏第一格"
        pasted = st.text_area(
            "多行粘贴",
            value=example if not items else "",
            height=180,
            key=f"bulk-paste-{task_id}",
        )
        if st.button("从粘贴内容新增条目", key=f"bulk-import-{task_id}", use_container_width=True):
            try:
                created_ids = _create_items_from_paste(task_id, pasted)
            except Exception as exc:
                st.error(str(exc))
            else:
                if created_ids:
                    st.session_state[f"selected-item-{task_id}"] = created_ids[0]
                st.success(f"已新增 {len(created_ids)} 个条目。")
                _rerun()


def _render_task_summary(task: dict, items: list[dict]) -> None:
    summary = task.get("items_summary", {})
    st.markdown(
        f"""
        <div class="hero">
          <div class="kicker">批次工作台</div>
          <h1>{task.get('task_name', task['task_id'])}</h1>
          <p>{task.get('asset_domain', 'game_icon_assets')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    background = task.get("project_background", "").strip() or "未填写"
    style_requirements = task.get("style_requirements", "").strip() or "未填写"
    info_left, info_right = st.columns(2)
    info_left.markdown(
        f"""
        <div class="panel">
          <div class="kicker">项目背景</div>
          <p style="margin:0.2rem 0;color:#334155;white-space:pre-wrap;">{background}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    info_right.markdown(
        f"""
        <div class="panel">
          <div class="kicker">统一风格要求</div>
          <p style="margin:0.2rem 0;color:#334155;white-space:pre-wrap;">{style_requirements}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    stats = [
        ("批次状态", STATUS_LABELS.get(task.get("status", "draft"), task.get("status", "draft"))),
        ("条目数量", str(task.get("item_count", len(items)))),
        ("已完成", str(summary.get("completed", 0))),
        ("进行中", str(summary.get("in_progress", 0))),
    ]
    for col, (label, value) in zip(cols, stats):
        col.markdown(
            f'<div class="stat"><span class="kicker">{label}</span><strong>{value}</strong></div>',
            unsafe_allow_html=True,
        )

    _render_entry_overview(task["task_id"], items)


def _item_main_action(item: dict) -> tuple[str | None, str | None]:
    status = item["status"]
    mapping = {
        "draft": ("生成设计说明", "先把原始需求整理成可用于出图的设计说明"),
        "brief_generated": ("继续生成出图指令", "采纳当前设计说明并继续生成出图指令"),
        "brief_approved": ("生成出图指令", "基于当前设计说明生成出图指令"),
        "prompt_generated": ("继续生成候选图", "采纳当前出图指令并继续生成候选图"),
        "prompt_approved": ("生成候选图", "基于当前出图指令生成候选图"),
        "image_generated": ("采纳当前候选图", "将当前候选图设为结果并完成条目"),
        "completed": ("已完成", "当前条目已经完成"),
    }
    return mapping.get(status, (None, None))


def _run_main_action(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    status = item["status"]

    if status == "draft":
        run_step(task_id, item_id, STEP_BRIEF_GENERATION)
        return
    if status == "brief_generated":
        approve_step(task_id, item_id, STEP_BRIEF_GENERATION)
        run_step(task_id, item_id, STEP_IMAGE_PROMPT)
        return
    if status == "brief_approved":
        run_step(task_id, item_id, STEP_IMAGE_PROMPT)
        return
    if status == "prompt_generated":
        approve_step(task_id, item_id, STEP_IMAGE_PROMPT)
        run_step(task_id, item_id, STEP_IMAGE_GENERATION)
        return
    if status == "prompt_approved":
        run_step(task_id, item_id, STEP_IMAGE_GENERATION)
        return
    if status == "image_generated":
        approve_step(task_id, item_id, STEP_IMAGE_GENERATION)
        return
    if status == "completed":
        return
    raise ValueError(f"Unsupported item status: {status}")


def _item_secondary_action(item: dict) -> tuple[str | None, str | None]:
    status = item["status"]
    mapping = {
        "brief_generated": ("重新生成设计说明", STEP_BRIEF_GENERATION),
        "brief_approved": ("返回设计说明", STEP_BRIEF_GENERATION),
        "prompt_generated": ("重新生成出图指令", STEP_IMAGE_PROMPT),
        "prompt_approved": ("返回出图指令", STEP_IMAGE_PROMPT),
        "image_generated": ("重新生成候选图", STEP_IMAGE_GENERATION),
    }
    return mapping.get(status, (None, None))


def _run_secondary_action(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    status = item["status"]

    if status == "brief_generated":
        run_step(task_id, item_id, STEP_BRIEF_GENERATION)
        return
    if status == "brief_approved":
        rollback_step(task_id, item_id, STEP_BRIEF_GENERATION)
        return
    if status == "prompt_generated":
        run_step(task_id, item_id, STEP_IMAGE_PROMPT)
        return
    if status == "prompt_approved":
        rollback_step(task_id, item_id, STEP_IMAGE_PROMPT)
        return
    if status == "image_generated":
        run_step(task_id, item_id, STEP_IMAGE_GENERATION)
        return
    raise ValueError(f"No secondary action for item status: {status}")


def _render_action_bar(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    status = item["status"]
    action_label, action_hint = _item_main_action(item)

    st.markdown(
        f"""
        <div class="panel">
          <div class="kicker">当前阶段</div>
          <p style="margin:0.15rem 0 0.2rem 0;font-size:1.05rem;color:#0f172a;"><strong>{STATUS_LABELS.get(status, status)}</strong></p>
          <p style="margin:0;color:#475569;">{action_hint or '当前没有可执行动作。'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, mid, right = st.columns([1.5, 1.15, 1.0])
    with left:
        if st.button(
            action_label or "当前无动作",
            key=f"main-action-{item_id}",
            use_container_width=True,
            disabled=status == "completed",
        ):
            try:
                _run_main_action(task_id, item)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success(f"已执行：{action_label}")
                _rerun()
    with mid:
        secondary_label, secondary_step = _item_secondary_action(item)
        if secondary_label:
            if st.button(secondary_label, key=f"secondary-{item_id}-{secondary_step}", use_container_width=True):
                try:
                    _run_secondary_action(task_id, item)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success(f"已执行：{secondary_label}")
                    _rerun()
        else:
            st.button("暂无次动作", disabled=True, use_container_width=True, key=f"idle-{item_id}")
    with right:
        if st.button("刷新条目", key=f"refresh-{item_id}", use_container_width=True):
            _reset_task_ui_state(task_id, item_id)
            _rerun()


def _render_current_outputs(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    brief = _artifact_or_none(task_id, item_id, STEP_BRIEF_GENERATION, item["current_versions"].get("brief_generation"))
    prompt = _artifact_or_none(task_id, item_id, STEP_IMAGE_PROMPT, item["current_versions"].get("image_prompt"))
    image = _artifact_or_none(task_id, item_id, STEP_IMAGE_GENERATION, item["current_versions"].get("image_generation"))
    output_view_key = f"output-view-{task_id}-{item_id}"
    output_view_status_key = f"{output_view_key}-status"
    expected_view = _default_output_view(item)
    if st.session_state.get(output_view_status_key) != item.get("status"):
        st.session_state[output_view_key] = expected_view
        st.session_state[output_view_status_key] = item.get("status")

    selected_view = _switcher(
        "当前输出页签",
        ["总览", "设计说明", "出图指令", "当前候选图"],
        key=output_view_key,
        default=expected_view,
    )

    image_root = item_dir(task_id, item_id) / "images"
    approved_path = image_root / "approved.png"
    approved_exists = approved_path.exists()
    candidate_paths = _candidate_paths(task_id, item_id, image)
    candidate_version = item["current_versions"].get(STEP_IMAGE_GENERATION) or "未生成"

    focus_key = f"candidate-focus-{task_id}-{item_id}-{candidate_version}"
    if approved_exists:
        default_focus = "已采纳结果"
    elif candidate_paths:
        default_focus = candidate_paths[0][0]
    else:
        default_focus = ""
    if focus_key not in st.session_state:
        st.session_state[focus_key] = default_focus
    focus_label = st.session_state.get(focus_key, default_focus)

    def render_candidate_area() -> None:
        st.markdown("### 当前候选图")
        if not approved_exists and not candidate_paths:
            st.info("还没有生成候选图。")
            return

        options = []
        if approved_exists:
            options.append(("已采纳结果", approved_path))
        options.extend(candidate_paths)
        option_map = {label: path for label, path in options}
        if focus_label not in option_map:
            st.session_state[focus_key] = options[0][0]
        current_focus = st.session_state.get(focus_key, options[0][0])
        current_path = option_map.get(current_focus, options[0][1])

        st.caption(f"当前候选图版本：{candidate_version}")
        st.image(str(current_path), caption=current_focus, use_container_width=True)
        thumb_cols = st.columns(min(4, len(options)))
        for index, (label, path) in enumerate(options):
            with thumb_cols[index % len(thumb_cols)]:
                st.image(str(path), caption=label, width=120)
                if st.button(
                    "查看这张",
                    key=f"candidate-thumb-{item_id}-{label}",
                    use_container_width=True,
                    disabled=label == current_focus,
                ):
                    st.session_state[focus_key] = label
                    _rerun()

    if selected_view == "总览":
        overview_left, overview_right = st.columns([1.0, 1.0], gap="large")
        with overview_left:
            st.markdown("### 当前设计说明")
            if brief:
                _render_brief_readable(brief)
            else:
                st.info("还没有设计说明版本。")
            st.markdown("### 当前出图指令")
            if prompt:
                _render_prompt_readable(prompt)
            else:
                st.info("还没有出图指令版本。")
        with overview_right:
            render_candidate_area()
        return

    if selected_view == "设计说明":
        st.caption("设计说明是原始需求和出图指令之间的中间层。项目背景会作为语义参考，统一风格要求会作为后续出图约束。")
        if brief:
            _render_brief_readable(brief)
        else:
            st.info("还没有设计说明版本。")
        return

    if selected_view == "出图指令":
        st.caption("这里会显示最终用于出图的主指令和负向指令。统一风格要求会显式进入这里的约束层。")
        if prompt:
            _render_prompt_readable(prompt)
        else:
            st.info("还没有出图指令版本。")
        return

    render_candidate_area()


def _render_versions(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    st.markdown("### 版本历史")
    for step in [STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT, STEP_IMAGE_GENERATION]:
        artifacts = list_artifacts(task_id, item_id, step)
        current = item["current_versions"].get(step)
        with st.expander(f"{STEP_LABELS[step]}版本", expanded=bool(artifacts)):
            if not artifacts:
                st.info("还没有版本。")
                continue
            version_map = {artifact["version"]: artifact for artifact in artifacts}
            version_options = [artifact["version"] for artifact in artifacts]
            default_index = version_options.index(current) if current in version_options else 0
            selected_version = st.radio(
                f"选择 {STEP_LABELS[step]} 版本",
                options=version_options,
                index=default_index,
                horizontal=True,
                format_func=lambda version: (
                    f"{version}"
                    f" · {_artifact_source_label(load_artifact(task_id, item_id, step, version))}"
                    f"{' · 当前使用' if version == current else ''}"
                ),
                key=f"select-{item_id}-{step}",
            )
            selected_artifact = load_artifact(task_id, item_id, step, selected_version)
            meta_left, meta_right = st.columns([1.1, 1.4])
            with meta_left:
                st.markdown(
                    f"""
                    <div class="panel">
                      <div class="kicker">版本信息</div>
                      <p style="margin:0.2rem 0;color:#0f172a;"><strong>{selected_version}</strong></p>
                      <p style="margin:0.2rem 0;color:#475569;">来源：{_artifact_source_label(selected_artifact)}</p>
                      <p style="margin:0.2rem 0;color:#475569;">创建时间：{selected_artifact.get('created_at', '未知')}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if selected_version != current:
                    if st.button(
                        f"切换为当前版本",
                        key=f"use-version-{item_id}-{step}",
                        use_container_width=True,
                    ):
                        try:
                            set_current_version(task_id, item_id, step, selected_version)
                        except Exception as exc:
                            st.error(str(exc))
                        else:
                            st.success(f"已切换到 {selected_version}。")
                            _rerun()
                else:
                    st.button("当前已选中", disabled=True, use_container_width=True, key=f"current-{item_id}-{step}")
            with meta_right:
                st.markdown("#### 预览")
                _render_artifact_preview(task_id, item_id, step, selected_artifact)


def _render_manual_edits(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    brief_artifact = _artifact_or_none(
        task_id,
        item_id,
        STEP_BRIEF_GENERATION,
        item["current_versions"].get("brief_generation"),
    )
    prompt_artifact = _artifact_or_none(
        task_id,
        item_id,
        STEP_IMAGE_PROMPT,
        item["current_versions"].get("image_prompt"),
    )

    left, right = st.columns(2)
    with left:
        st.markdown("### 编辑设计说明")
        with st.form(f"edit-brief-form-{item_id}"):
            brief_output = brief_artifact.get("output", {}) if brief_artifact else {}
            title = st.text_input(
                "名称",
                value=brief_output.get("title", item.get("title", "")),
                key=f"brief-title-{item_id}",
            )
            description = st.text_area(
                "需求整理",
                value=brief_output.get("description", item.get("description", "")),
                height=120,
                key=f"brief-description-{item_id}",
            )
            keywords = st.text_input(
                "关键词（逗号分隔）",
                value=", ".join(brief_output.get("keywords", [])),
                key=f"brief-keywords-{item_id}",
            )
            icon_subject = st.text_input(
                "图标主体",
                value=brief_output.get("icon_subject", ""),
                key=f"brief-icon-subject-{item_id}",
            )
            visual_focus = st.text_input(
                "视觉重点",
                value=brief_output.get("visual_focus", ""),
                key=f"brief-visual-focus-{item_id}",
            )
            note = st.text_input("备注", value="手动编辑设计说明", key=f"brief-note-{item_id}")
            submitted = st.form_submit_button("保存设计说明版本", use_container_width=True)
        if submitted:
            try:
                edit_brief(
                    task_id,
                    item_id,
                    title=title,
                    description=description,
                    keywords=[keyword.strip() for keyword in keywords.split(",") if keyword.strip()],
                    icon_subject=icon_subject,
                    visual_focus=visual_focus,
                    note=note,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                _reset_task_ui_state(task_id, item_id)
                st.success("已保存设计说明版本。")
                _rerun()
        if st.button("回退到设计说明阶段", key=f"rollback-brief-{item_id}", use_container_width=True):
            try:
                rollback_step(task_id, item_id, STEP_BRIEF_GENERATION)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("已回退到设计说明阶段。")
                _rerun()

    with right:
        st.markdown("### 编辑出图指令")
        with st.form(f"edit-prompt-form-{item_id}"):
            prompt_output = prompt_artifact.get("output", {}) if prompt_artifact else {}
            prompt_text = st.text_area(
                "出图指令",
                value=prompt_output.get("prompt", ""),
                height=140,
                key=f"prompt-text-{item_id}",
            )
            negative_prompt = st.text_area(
                "负向指令",
                value=prompt_output.get("negative_prompt", ""),
                height=100,
                key=f"prompt-negative-{item_id}",
            )
            note = st.text_input("备注", value="手动编辑出图指令", key=f"prompt-note-{item_id}")
            submitted = st.form_submit_button("保存出图指令版本", use_container_width=True)
        if submitted:
            try:
                edit_prompt(
                    task_id,
                    item_id,
                    prompt=prompt_text,
                    negative_prompt=negative_prompt,
                    note=note,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                _reset_task_ui_state(task_id, item_id)
                st.success("已保存出图指令版本。")
                _rerun()
        if st.button("回退到出图指令阶段", key=f"rollback-prompt-{item_id}", use_container_width=True):
            try:
                rollback_step(task_id, item_id, STEP_IMAGE_PROMPT)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("已回退到出图指令阶段。")
                _rerun()


def _render_events(task_id: str, item_id: str) -> None:
    task_events, item_events = st.tabs(["批次事件", "条目事件"])
    with task_events:
        _show_json(load_task_events(task_id))
    with item_events:
        _show_json(load_item_events(task_id, item_id))


def _render_item_workspace(task_id: str, item: dict) -> None:
    st.markdown(
        f"""
        <div class="panel">
          <div class="kicker">当前条目</div>
          <h3 style="margin:0.15rem 0 0.25rem 0;">{item.get('title') or item['item_id']}</h3>
          <p style="margin:0;color:#475569;">{item.get('asset_type')} · {item.get('category') or '未分类'} · {STATUS_LABELS.get(item.get('status', 'draft'), item.get('status', 'draft'))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("编辑条目原始需求", expanded=False):
        with st.form(f"update-item-form-{task_id}-{item['item_id']}"):
            asset_type = st.text_input(
                "资产类型",
                value=item.get("asset_type", "generic_icon"),
                key=f"source-asset-type-{item['item_id']}",
            )
            title = st.text_input("名称", value=item.get("title", ""), key=f"source-title-{item['item_id']}")
            description = st.text_area(
                "原始描述",
                value=item.get("description", ""),
                height=120,
                key=f"source-description-{item['item_id']}",
            )
            category = st.text_input("分类", value=item.get("category", ""), key=f"source-category-{item['item_id']}")
            extra_context = st.text_area(
                "条目补充说明",
                value=item.get("extra_context", ""),
                height=80,
                key=f"source-extra-context-{item['item_id']}",
            )
            submitted = st.form_submit_button("保存条目并按需重置下游版本", use_container_width=True)
        if submitted:
            try:
                update_item(
                    task_id,
                    item["item_id"],
                    asset_type=asset_type,
                    title=title,
                    description=description,
                    category=category,
                    extra_context=extra_context,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                _reset_task_ui_state(task_id, item["item_id"])
                st.success("已更新条目，相关下游版本已按需重置。")
                _rerun()
    _render_action_bar(task_id, item)
    current_tab, versions_tab, edits_tab, events_tab = st.tabs(["当前输出", "版本历史", "手动编辑", "事件日志"])
    with current_tab:
        _render_current_outputs(task_id, item)
    with versions_tab:
        _render_versions(task_id, item)
    with edits_tab:
        _render_manual_edits(task_id, item)
    with events_tab:
        _render_events(task_id, item["item_id"])


def main() -> None:
    st.set_page_config(
        page_title="AI 图标流水线工作台",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()
    st.markdown('<div class="app-shell">', unsafe_allow_html=True)
    tasks = list_tasks()
    selected_task_id = _render_sidebar(tasks)

    if not selected_task_id:
        st.markdown(
            """
            <div class="hero">
              <div class="kicker">还没有批次</div>
              <h1>先创建一个批次容器</h1>
              <p>批次只承载项目背景和统一风格要求，创建后再在批次内新增或粘贴条目。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    task = load_task(selected_task_id)
    items = list_items(selected_task_id)
    _render_task_summary(task, items)
    workspace_view = _switcher(
        "工作区视图",
        ["批次信息", "条目工作台"],
        key=f"workspace-view-{selected_task_id}",
        default=st.session_state.get(f"workspace-view-{selected_task_id}", "批次信息"),
    )

    if workspace_view == "批次信息":
        _render_batch_settings(task)
        _render_task_actions(selected_task_id)
    else:
        left_col, right_col = st.columns([0.95, 1.15], gap="large")
        with left_col:
            current_item_id = _render_item_selector(selected_task_id, items)
            _render_item_management(task)

        if not items:
            with right_col:
                st.warning("这个批次还没有条目。先在左侧新增条目，或者直接粘贴多行条目。")
            st.stop()

        item_lookup = {item["item_id"]: item for item in items}
        if current_item_id not in item_lookup:
            current_item_id = items[0]["item_id"]
            st.session_state[f"selected-item-{selected_task_id}"] = current_item_id

        with right_col:
            _render_item_workspace(selected_task_id, item_lookup[current_item_id])
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
