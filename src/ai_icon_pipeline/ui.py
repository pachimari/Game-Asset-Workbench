from __future__ import annotations

from pathlib import Path
import json
import sys

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
        update_item,
    )


STEP_LABELS = {
    STEP_BRIEF_GENERATION: "设计说明",
    STEP_IMAGE_PROMPT: "出图指令",
    STEP_IMAGE_GENERATION: "候选图",
}


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


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


def _task_label(task: dict) -> str:
    return f"{task['task_id']} · {task.get('task_name', 'Untitled')} · {task.get('status', 'unknown')}"


def _item_label(item: dict) -> str:
    title = item.get("title") or item.get("asset_type", "item")
    return f"{item['item_id']} · {title} · {item.get('status', 'unknown')}"


def _artifact_or_none(task_id: str, item_id: str, step: str, version: str | None) -> dict | None:
    if not version:
        return None
    try:
        return load_artifact(task_id, item_id, step, version)
    except ValueError:
        return None


def _render_task_creation() -> None:
    with st.sidebar.expander("创建 Task", expanded=False):
        with st.form("create_task_form"):
            task_name = st.text_input("Task 名称", value="未命名图标批次")
            project_context = st.text_input("项目上下文", value="通用项目")
            asset_domain = st.text_input("资产域", value="game_icon_assets")
            submitted = st.form_submit_button("创建空 Task", use_container_width=True)
        if submitted:
            try:
                task = create_task(
                    task_name=task_name,
                    project_context=project_context,
                    asset_domain=asset_domain,
                )
            except Exception as exc:
                st.sidebar.error(str(exc))
            else:
                st.sidebar.success(f"已创建 {task['task_id']}")
                st.session_state["selected_task_id"] = task["task_id"]
                _rerun()


def _render_sidebar(tasks: list[dict]) -> str | None:
    st.sidebar.title("工作台")
    st.sidebar.caption("Task 列表、批次选择和基础操作。")
    _render_task_creation()

    if not tasks:
        st.sidebar.info("还没有 task，可以先从上面的表单创建。")
        return None

    task_lookup = {task["task_id"]: task for task in tasks}
    current_task_id = st.session_state.get("selected_task_id")
    if current_task_id not in task_lookup:
        current_task_id = tasks[0]["task_id"]

    selected_label = st.sidebar.selectbox(
        "Task",
        options=[task["task_id"] for task in tasks],
        index=[task["task_id"] for task in tasks].index(current_task_id),
        format_func=lambda task_id: _task_label(task_lookup[task_id]),
        key="selected_task_id",
    )

    if st.sidebar.button("Refresh", use_container_width=True):
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


def _render_task_actions(task_id: str) -> None:
    st.markdown("### Task 操作")
    left, mid, right = st.columns(3)
    with left:
        if st.button("批量自动跑完整个 Task", key=f"run-task-{task_id}", use_container_width=True):
            try:
                run_pipeline(task_id)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("已批量跑完整个 task。")
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
        if st.button("刷新 Task", key=f"refresh-task-{task_id}", use_container_width=True):
            _rerun()


def _render_item_management(task: dict) -> None:
    task_id = task["task_id"]
    create_tab, import_tab = st.tabs(["新增 Item", "批量导入 Items"])

    with create_tab:
        with st.form(f"create-item-form-{task_id}"):
            asset_type = st.text_input("资产类型", value="generic_icon")
            title = st.text_input("名称")
            description = st.text_area("需求描述", height=120)
            category = st.text_input("分类")
            extra_context = st.text_area("额外上下文", height=80)
            submitted = st.form_submit_button("新增 Item", use_container_width=True)
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
                st.success(f"已创建 {item['item_id']}")
                st.session_state[f"selected-item-{task_id}"] = item["item_id"]
                _rerun()

    with import_tab:
        example = {
            "items": [
                {
                    "asset_type": "skill_icon",
                    "title": "雷暴",
                    "description": "对敌人造成雷电伤害并附带麻痹效果",
                    "category": "combat",
                }
            ]
        }
        with st.form(f"import-items-form-{task_id}"):
            batch_text = st.text_area(
                "Items JSON",
                value=json.dumps(example, ensure_ascii=False, indent=2),
                height=220,
            )
            submitted = st.form_submit_button("批量导入", use_container_width=True)
        if submitted:
            try:
                payload = json.loads(batch_text)
                raw_items = payload["items"] if isinstance(payload, dict) else payload
                created = []
                for raw_item in raw_items:
                    created.append(
                        create_item(
                            task_id,
                            asset_type=raw_item.get("asset_type", "generic_icon"),
                            title=raw_item.get("title", ""),
                            description=raw_item.get("description", ""),
                            category=raw_item.get("category", ""),
                            extra_context=raw_item.get("extra_context", ""),
                        )["item_id"]
                    )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success(f"已导入 {len(created)} 个 item。")
                _rerun()


def _render_task_summary(task: dict, items: list[dict]) -> None:
    summary = task.get("items_summary", {})
    st.markdown(
        f"""
        <div class="hero">
          <div class="kicker">Task Workspace</div>
          <h1>{task.get('task_name', task['task_id'])}</h1>
          <p>{task.get('project_context', 'No project context')} · {task.get('asset_domain', 'game_icon_assets')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    stats = [
        ("Task 状态", task.get("status", "unknown")),
        ("Item 数量", str(task.get("item_count", len(items)))),
        ("已完成", str(summary.get("completed", 0))),
        ("进行中", str(summary.get("in_progress", 0))),
    ]
    for col, (label, value) in zip(cols, stats):
        col.markdown(
            f'<div class="stat"><span class="kicker">{label}</span><strong>{value}</strong></div>',
            unsafe_allow_html=True,
        )

    task_rows = [
        {
            "Item ID": item["item_id"],
            "名称": item.get("title"),
            "资产类型": item.get("asset_type"),
            "状态": item.get("status"),
            "设计说明": item["current_versions"].get("brief_generation"),
            "出图指令": item["current_versions"].get("image_prompt"),
            "候选图": item["current_versions"].get("image_generation"),
        }
        for item in items
    ]
    st.markdown("### Items")
    st.dataframe(task_rows, use_container_width=True, hide_index=True)


def _current_action(status: str) -> tuple[str | None, str | None]:
    mapping = {
        "draft": ("run", STEP_BRIEF_GENERATION),
        "brief_generated": ("approve", STEP_BRIEF_GENERATION),
        "brief_approved": ("run", STEP_IMAGE_PROMPT),
        "prompt_generated": ("approve", STEP_IMAGE_PROMPT),
        "prompt_approved": ("run", STEP_IMAGE_GENERATION),
        "image_generated": ("approve", STEP_IMAGE_GENERATION),
    }
    return mapping.get(status, (None, None))


def _render_action_bar(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    status = item["status"]
    action_kind, step = _current_action(status)

    left, mid, right = st.columns([1.2, 1.2, 1.4])
    with left:
        if st.button("自动跑完整个 Item", key=f"autorun-{item_id}", use_container_width=True):
            try:
                run_pipeline(task_id, item_id=item_id)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("Item 已跑完。")
                _rerun()
    with mid:
        if action_kind == "run":
            if st.button(f"运行{STEP_LABELS[step]}", key=f"run-{item_id}-{step}", use_container_width=True):
                try:
                    run_step(task_id, item_id, step)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success(f"已运行 {STEP_LABELS[step]}。")
                    _rerun()
        elif action_kind == "approve":
            if st.button(
                f"通过{STEP_LABELS[step]}",
                key=f"approve-{item_id}-{step}",
                use_container_width=True,
            ):
                try:
                    approve_step(task_id, item_id, step)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success(f"已通过 {STEP_LABELS[step]}。")
                    _rerun()
        else:
            st.button("当前无直接操作", disabled=True, use_container_width=True, key=f"idle-{item_id}")
    with right:
        if st.button("刷新 Item", key=f"refresh-{item_id}", use_container_width=True):
            _rerun()


def _render_current_outputs(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    brief = _artifact_or_none(task_id, item_id, STEP_BRIEF_GENERATION, item["current_versions"].get("brief_generation"))
    prompt = _artifact_or_none(task_id, item_id, STEP_IMAGE_PROMPT, item["current_versions"].get("image_prompt"))
    image = _artifact_or_none(task_id, item_id, STEP_IMAGE_GENERATION, item["current_versions"].get("image_generation"))

    left, right = st.columns([1.05, 0.95])
    with left:
        st.markdown("### 当前设计说明")
        if brief:
            st.caption("设计说明是原始需求和出图指令之间的结构化中间层，会把名称、主体、关键词和视觉重点整理清楚。")
            _show_json(brief)
        else:
            st.info("还没有设计说明版本。")
        st.markdown("### 当前出图指令")
        if prompt:
            st.caption("这里能看到名称如何进入最终 prompt，包括名称本身和图标主体。")
            _show_json(prompt)
        else:
            st.info("还没有出图指令版本。")
    with right:
        st.markdown("### 当前候选图")
        image_root = item_dir(task_id, item_id) / "images"
        approved_path = image_root / "approved.png"
        if approved_path.exists():
            st.image(str(approved_path), caption="已通过图片", use_container_width=True)
        if image and image.get("output", {}).get("candidates"):
            cols = st.columns(min(3, len(image["output"]["candidates"])))
            for idx, candidate in enumerate(image["output"]["candidates"]):
                path = image_root / candidate["image_path"]
                if path.exists():
                    cols[idx % len(cols)].image(
                        str(path),
                        caption=f"{candidate['candidate_id']} · {item['current_versions'].get('image_generation')}",
                        use_container_width=True,
                    )
        elif not approved_path.exists():
            st.info("还没有生成候选图。")


def _render_versions(task_id: str, item: dict) -> None:
    item_id = item["item_id"]
    st.markdown("### 版本历史")
    for step in [STEP_BRIEF_GENERATION, STEP_IMAGE_PROMPT, STEP_IMAGE_GENERATION]:
        artifacts = list_artifacts(task_id, item_id, step)
        current = item["current_versions"].get(step)
        with st.expander(f"{STEP_LABELS[step]} Versions", expanded=bool(artifacts)):
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
            title = st.text_input("名称", value=brief_output.get("title", item.get("title", "")))
            description = st.text_area(
                "需求整理",
                value=brief_output.get("description", item.get("description", "")),
                height=120,
            )
            keywords = st.text_input(
                "关键词（逗号分隔）",
                value=", ".join(brief_output.get("keywords", [])),
            )
            icon_subject = st.text_input(
                "图标主体",
                value=brief_output.get("icon_subject", ""),
            )
            visual_focus = st.text_input(
                "视觉重点",
                value=brief_output.get("visual_focus", ""),
            )
            note = st.text_input("备注", value="手动编辑设计说明")
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
                "Prompt",
                value=prompt_output.get("prompt", ""),
                height=140,
            )
            negative_prompt = st.text_area(
                "负向 Prompt",
                value=prompt_output.get("negative_prompt", ""),
                height=100,
            )
            note = st.text_input("备注", value="手动编辑出图指令")
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
    task_events, item_events = st.tabs(["Task 事件", "Item 事件"])
    with task_events:
        _show_json(load_task_events(task_id))
    with item_events:
        _show_json(load_item_events(task_id, item_id))


def _render_item_workspace(task_id: str, item: dict) -> None:
    st.markdown(
        f"""
        <div class="panel">
          <div class="kicker">当前 Item</div>
          <h3 style="margin:0.15rem 0 0.25rem 0;">{item.get('title') or item['item_id']}</h3>
          <p style="margin:0;color:#475569;">{item.get('asset_type')} · {item.get('category') or 'uncategorized'} · {item.get('status')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("编辑 Item 原始需求", expanded=False):
        with st.form(f"update-item-form-{task_id}-{item['item_id']}"):
            asset_type = st.text_input("资产类型", value=item.get("asset_type", "generic_icon"))
            title = st.text_input("名称", value=item.get("title", ""))
            description = st.text_area("原始描述", value=item.get("description", ""), height=120)
            category = st.text_input("分类", value=item.get("category", ""))
            extra_context = st.text_area("额外上下文", value=item.get("extra_context", ""), height=80)
            submitted = st.form_submit_button("保存 Item 并重置下游版本", use_container_width=True)
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
                st.success("已更新 item，相关下游版本已按需重置。")
                _rerun()
    _render_action_bar(task_id, item)
    current_tab, versions_tab, edits_tab, events_tab = st.tabs(
        ["当前输出", "版本历史", "手动编辑", "事件日志"]
    )
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
              <div class="kicker">还没有 Task</div>
              <h1>先创建一个批次容器</h1>
              <p>Task 现在只承载批次元数据，创建后再在 Task 内新增或导入 item。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    task = load_task(selected_task_id)
    items = list_items(selected_task_id)
    _render_task_summary(task, items)
    _render_task_actions(selected_task_id)
    with st.expander("Task 内 Item 管理", expanded=not items):
        _render_item_management(task)

    if not items:
        st.warning("这个 task 还没有 item。先在上面的 Item 管理里新增或导入。")
        st.stop()

    item_lookup = {item["item_id"]: item for item in items}
    current_item_id = st.selectbox(
        "选择 Item",
        options=[item["item_id"] for item in items],
        format_func=lambda item_id: _item_label(item_lookup[item_id]),
        key=f"selected-item-{selected_task_id}",
    )
    _render_item_workspace(selected_task_id, item_lookup[current_item_id])
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
